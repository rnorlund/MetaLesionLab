"""Tip of the Tongue web app: Test Studio, Scorer and Model Lab over one small JSON API.

Run:  uvicorn metalesionlab.web.app:app      (or: python -m metalesionlab.web)
Data: TOT_DATA_DIR (default <repo>/runs) holds sets/, scenes/, lesion/ and cache/.

Every route that calls a Meta API has a per-visitor daily limit (limits.py); MetaAPI itself
refuses calls past the global budget, which the app reports as a friendly 503.
Other settings: TOT_PUBLIC=1 (visitors can edit only the sets they built),
TOT_ALLOW_BUILDS=0 (no image generation), TOT_TRUST_PROXY=1 (rate-limit by X-Forwarded-For).
"""
from __future__ import annotations

import hashlib
import importlib
import io
import json
import logging
import os
import re
import secrets
import shutil
import threading
import time
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

import httpx
import openai
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from metalesionlab import meta_api
from metalesionlab.meta_api import BudgetExceeded, MetaAPI, load_api_key
from metalesionlab.naming_errors import LANGUAGE_NAMES, classify, spark_semantic_judge
from metalesionlab.web import exports
from metalesionlab.web.limits import client_ip, limit_for, limiter

log = logging.getLogger("tot.web")

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("TOT_DATA_DIR", meta_api.REPO_ROOT / "runs")).resolve()
SETS_DIR = DATA_DIR / "sets"
SCENES_DIR = DATA_DIR / "scenes"
LESION_DIR = DATA_DIR / "lesion"
CACHE_DIR = DATA_DIR / "cache"
SAMPLE_LAB = HERE / "sample_lab" / "sample_conditions.json"

PUBLIC = os.environ.get("TOT_PUBLIC") == "1"
ALLOW_BUILDS = os.environ.get("TOT_ALLOW_BUILDS", "1") == "1"
VERIFIED_LANGS = {"en", "es"}  # checked end to end; the rest are labeled experimental
MAX_WORDS = int(os.environ.get("TOT_MAX_WORDS", "24"))
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_CLIP_S = {"naming": 30, "description": 240, "fluency": 120}
NAMING_PAD_S = 0.7  # silence added around a naming clip before transcription
COST_PER_CANDIDATE = meta_api.IMAGE_PRICE + meta_api.SAM_PRICE + 0.002  # image, SAM check, Spark naming
THUMB_WIDTHS = {160, 320, 640}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
SET_ID = re.compile(r"^[\w-]{1,64}$")
CODES = ["Correct", "Semantic", "Formal", "Mixed", "Nonword", "Neologism", "Unrelated", "Description",
         "NoResponse", "Visual"]
AUDIO_SUFFIXES = {"audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
                  "audio/aac": ".aac", "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav",
                  "audio/wave": ".wav"}
BUDGET_MSG = ("This demo has reached its spending cap for Meta API calls, so new scoring and picture "
              "generation are paused. Browsing, review and exports still work.")

app = FastAPI(title="Tip of the Tongue", version="0.1.0", docs_url="/api/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


# --- errors ----------------------------------------------------------------------------

@app.exception_handler(BudgetExceeded)
def _budget_exceeded(_request: Request, _exc: BudgetExceeded):
    return JSONResponse({"detail": BUDGET_MSG}, status_code=503)


@app.exception_handler(openai.OpenAIError)
@app.exception_handler(httpx.HTTPError)
def _upstream_error(_request: Request, exc: Exception):
    log.warning("Meta API error: %s", exc)
    return JSONResponse({"detail": f"The Meta Model API returned an error ({type(exc).__name__}). "
                                   "Please try again in a minute."}, status_code=502)


# --- shared helpers --------------------------------------------------------------------

_api: MetaAPI | None = None
_api_lock = threading.Lock()


def get_api() -> MetaAPI:
    global _api
    with _api_lock:
        if _api is None:
            try:
                _api = MetaAPI()
            except RuntimeError as e:
                raise HTTPException(503, "The Meta Model API key isn't set on this server, so live "
                                         "scoring and picture generation are off.") from e
        return _api


def api_key_present() -> bool:
    try:
        return bool(load_api_key())
    except RuntimeError:
        return False


def optional_module(name: str, what: str):
    """Import a module that may not be installed yet; 501 with a clear message if it isn't."""
    try:
        return importlib.import_module(name)
    except ImportError as e:
        raise HTTPException(501, f"{what} isn't available on this server yet ({name} could not be "
                                 f"imported: {e}).") from e


def has_module(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


_judge_lock = threading.Lock()


@lru_cache(maxsize=1)
def _spark_judge():
    return spark_semantic_judge(get_api(), CACHE_DIR / "semantic_judge.json")


def judge(target: str, response: str, lang: str) -> bool:
    """The Muse Spark meaning judge; its disk cache isn't thread-safe, so calls take turns."""
    with _judge_lock:
        return _spark_judge()(target, response, lang)


def norm_code(code) -> str | None:
    if not code:
        return None
    key = re.sub(r"[^a-z]", "", str(code).lower())
    return next((c for c in CODES if c.lower() == key), str(code))


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def write_json(path: Path, data) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    os.replace(tmp, path)


def safe_child(base: Path, rel: str) -> Path:
    path = (base / rel).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise HTTPException(404, "Not found")
    return path


def image_response(path: Path, width: int | None) -> FileResponse:
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise HTTPException(404, "Not found")
    headers = {"Cache-Control": "public, max-age=300"}
    if width not in THUMB_WIDTHS:
        return FileResponse(path, headers=headers)
    key = hashlib.sha1(f"{path}|{path.stat().st_mtime_ns}|{width}".encode()).hexdigest()
    thumb = CACHE_DIR / "thumbs" / f"{key}.webp"
    if not thumb.exists():
        thumb.parent.mkdir(parents=True, exist_ok=True)
        img = Image.open(path).convert("RGB")
        img.thumbnail((width, width))
        tmp = thumb.with_suffix(".tmp")
        img.save(tmp, "WEBP", quality=85)
        os.replace(tmp, thumb)
    return FileResponse(thumb, media_type="image/webp", headers=headers)


def check_lang(lang: str) -> str:
    if lang not in LANGUAGE_NAMES:
        raise HTTPException(422, f"Unsupported language '{lang}'. Choose one of: {', '.join(LANGUAGE_NAMES)}.")
    return lang


# --- pages -----------------------------------------------------------------------------

PAGES = {"/": "index.html", "/studio": "studio.html", "/scorer": "scorer.html", "/lab": "lab.html"}


def _page(name: str):
    def page():
        return FileResponse(HERE / "pages" / name, headers={"Cache-Control": "no-cache"})
    return page


for _route, _name in PAGES.items():
    app.add_api_route(_route, _page(_name), methods=["GET"], include_in_schema=False)


@app.get("/api/status")
def status(request: Request):
    ip = client_ip(request)
    return {
        "features": {"meta_api": api_key_present(),
                     "audio": has_module("metalesionlab.audio") and shutil.which("ffmpeg") is not None,
                     "scorer": has_module("metalesionlab.scorer"), "builds": ALLOW_BUILDS},
        "public": PUBLIC,
        "languages": [{"code": c, "name": n, "verified": c in VERIFIED_LANGS} for c, n in LANGUAGE_NAMES.items()],
        "limits": {b: {"per_day": limit_for(b), "remaining": limiter.remaining(b, ip)}
                   for b in ("build", "scene", "score")},
        "max_words": MAX_WORDS,
        "budget": {"spent_usd": round(meta_api.spent(), 2), "cap_usd": meta_api.BUDGET_USD},
    }


# --- Test Studio -----------------------------------------------------------------------

jobs: dict[str, dict] = {}  # builds started by this server process
_build_slots = threading.Semaphore(int(os.environ.get("TOT_BUILD_SLOTS", "2")))
_manifest_lock = threading.Lock()


class NewSet(BaseModel):
    name: str = Field("", max_length=60)
    lang: str = "en"
    words: str = Field(..., max_length=4000)
    style: Literal["line", "color"] = "line"
    candidates: int = Field(2, ge=1, le=3)


class ItemEdit(BaseModel):
    image: str | None = None
    alternates: list[str] | None = Field(None, max_length=12)
    status: Literal["kept", "review", "excluded"] | None = None


def set_path(set_id: str) -> Path:
    if not SET_ID.match(set_id) or not (SETS_DIR / set_id).is_dir():
        raise HTTPException(404, f"No set called '{set_id}'.")
    return SETS_DIR / set_id


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40] or "set"


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def set_summary(d: Path) -> dict:
    meta = read_json(d / "webmeta.json") or {}
    manifest = read_json(d / "manifest.json")
    job = jobs.get(d.name)
    if job:
        state, error = job["status"], job.get("error")
    elif manifest:
        state, error = "done", None
    elif meta.get("status") == "error":
        state, error = "error", meta.get("error")
    else:
        state, error = "incomplete", None
    items = (manifest or {}).get("items", [])
    statuses = [it.get("status") for it in items]
    return {
        "id": d.name, "name": meta.get("name") or d.name, "status": state, "error": error,
        "lang": (manifest or meta).get("lang"), "style": (manifest or meta).get("style"),
        "n_items": len(items) or len(meta.get("words", [])), "kept": statuses.count("kept"),
        "review": statuses.count("review"), "excluded": statuses.count("excluded"),
        "created": meta.get("created") or d.stat().st_mtime,
        "source": meta.get("source", "folder"), "editable": not PUBLIC,  # else only with the edit token
    }


@app.get("/api/sets")
def list_sets():
    if not SETS_DIR.is_dir():
        return []
    sets = [set_summary(d) for d in SETS_DIR.iterdir() if d.is_dir() and SET_ID.match(d.name)]
    return sorted(sets, key=lambda s: -s["created"])


@app.get("/api/sets/{set_id}")
def get_set(set_id: str):
    d = set_path(set_id)
    meta = read_json(d / "webmeta.json") or {}
    out = set_summary(d)
    drawn = sorted(str(p.relative_to(d)) for p in (d / "candidates").glob("*.png")) if (d / "candidates").is_dir() else []
    expected = len(meta.get("words", [])) * meta.get("candidates", 0) or None
    out["progress"] = {"drawn": len(drawn), "expected": expected}
    out["manifest"] = read_json(d / "manifest.json") if out["status"] == "done" else None
    if out["manifest"] is None:
        out["drawn_files"] = drawn
    return out


def _build(set_id: str, words: list[str], lang: str, style: str, candidates: int) -> None:
    from metalesionlab.test_studio import build_set

    job, out_dir = jobs[set_id], SETS_DIR / set_id
    with _build_slots:
        job.update(status="running", started=time.time())
        try:
            build_set(words, lang, out_dir, style=style, candidates=candidates, workers=4, api=get_api())
            job["status"] = "done"
        except BudgetExceeded:
            job.update(status="error", error=BUDGET_MSG)
        except Exception as e:  # report any failure to the page instead of losing it in a thread
            log.exception("build %s failed", set_id)
            job.update(status="error", error=f"The build stopped: {type(e).__name__}: {e}")
        job["finished"] = time.time()
        meta = read_json(out_dir / "webmeta.json") or {}
        meta.update(status=job["status"], error=job.get("error"), finished=job["finished"])
        write_json(out_dir / "webmeta.json", meta)


@app.post("/api/sets", status_code=202)
def create_set(body: NewSet, request: Request):
    if not ALLOW_BUILDS:
        raise HTTPException(403, "Building new picture sets is turned off on this demo. You can browse "
                                 "and export the existing sets, or run Tip of the Tongue yourself.")
    lang = check_lang(body.lang)
    lines, seen = [], set()
    for line in body.words.splitlines():
        word = line.partition(":")[0].strip().lower()
        if not word or word in seen:
            continue
        if len(line) > 80:
            raise HTTPException(422, f"'{line[:30]}…' is too long; use one word per line.")
        seen.add(word)
        lines.append(line.strip())
    if not lines:
        raise HTTPException(422, "Add at least one word, one per line.")
    if len(lines) > MAX_WORDS:
        raise HTTPException(422, f"This demo builds up to {MAX_WORDS} words at a time ({len(lines)} given).")
    estimate = len(lines) * body.candidates * COST_PER_CANDIDATE
    if meta_api.spent() + estimate > meta_api.BUDGET_USD:
        raise HTTPException(503, BUDGET_MSG)
    get_api()
    limiter.take("build", client_ip(request))

    SETS_DIR.mkdir(parents=True, exist_ok=True)
    base = slugify(body.name or f"{lang}-set")
    set_id, k = base, 1
    while (SETS_DIR / set_id).exists():
        k += 1
        set_id = f"{base}-{k}"
    (SETS_DIR / set_id).mkdir()
    token = secrets.token_urlsafe(18)
    write_json(SETS_DIR / set_id / "webmeta.json", {
        "name": body.name.strip() or set_id, "lang": lang, "style": body.style, "candidates": body.candidates,
        "words": lines, "created": time.time(), "source": "web", "status": "queued",
        "token_sha": _token_hash(token)})
    jobs[set_id] = {"status": "queued", "created": time.time()}
    threading.Thread(target=_build, args=(set_id, lines, lang, body.style, body.candidates), daemon=True).start()
    return {"id": set_id, "status": "queued", "edit_token": token, "estimate_usd": round(estimate, 2)}


def check_edit(d: Path, token: str | None) -> None:
    if not PUBLIC:
        return
    meta = read_json(d / "webmeta.json") or {}
    if not token or meta.get("token_sha") != _token_hash(token):
        raise HTTPException(403, "On this public demo you can edit only the sets you built in this browser.")


@app.patch("/api/sets/{set_id}/items/{index}")
def edit_item(set_id: str, index: int, body: ItemEdit, x_edit_token: str | None = Header(None)):
    """Reviewer changes: pick a different candidate picture, set accepted alternate names, or the status."""
    d = set_path(set_id)
    check_edit(d, x_edit_token)
    with _manifest_lock:
        manifest = read_json(d / "manifest.json")
        if not manifest:
            raise HTTPException(409, "This set is still being built.")
        if not 0 <= index < len(manifest["items"]):
            raise HTTPException(404, "No such item.")
        item = manifest["items"][index]
        if body.image is not None:
            if body.image not in {c["file"] for c in item.get("candidates", [])}:
                raise HTTPException(422, "That picture isn't one of this item's candidates.")
            item["image"] = body.image
            item["status"] = body.status or "kept"
        if body.alternates is not None:
            alts = [a.strip().lower() for a in body.alternates if a.strip()]
            item["alternates"] = list(dict.fromkeys(a for a in alts if len(a) <= 40 and a != item["word"]))
        if body.status is not None:
            if body.status == "kept" and not item.get("image"):
                raise HTTPException(422, "Choose a picture before keeping this item.")
            item["status"] = body.status
        item["reviewed"] = True
        write_json(d / "manifest.json", manifest)
    return item


@app.get("/media/sets/{set_id}/{path:path}")
def set_media(set_id: str, path: str, w: int | None = None):
    return image_response(safe_child(set_path(set_id), path), w)


def _manifest_or_409(d: Path) -> dict:
    manifest = read_json(d / "manifest.json")
    if not manifest:
        raise HTTPException(409, "This set has no results yet.")
    return manifest


def _download(content: bytes, media_type: str, filename: str) -> Response:
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename=\"{filename}\""})


@app.get("/api/sets/{set_id}/norms.csv")
def export_norms(set_id: str):
    d = set_path(set_id)
    return _download(exports.norms_csv(_manifest_or_409(d)).encode("utf-8-sig"), "text/csv; charset=utf-8",
                     f"{set_id}_norms.csv")


@app.get("/api/sets/{set_id}/cards.pdf")
def export_cards(set_id: str, per_page: int = 4, word: bool = True, page: Literal["letter", "a4"] = "letter",
                 review: bool = False):
    if per_page not in exports.CARD_GRIDS:
        raise HTTPException(422, f"per_page must be one of {sorted(exports.CARD_GRIDS)}.")
    d = set_path(set_id)
    meta = read_json(d / "webmeta.json") or {}
    pdf = exports.cards_pdf(_manifest_or_409(d), d, meta.get("name") or set_id, per_page=per_page,
                            show_word=word, page_format=page, include_review=review)
    return _download(pdf, "application/pdf", f"{set_id}_cards.pdf")


@app.get("/api/sets/{set_id}/set.zip")
def export_zip(set_id: str):
    d = set_path(set_id)
    return _download(exports.set_zip(_manifest_or_409(d), d, set_id), "application/zip", f"{set_id}.zip")


def set_item(set_id: str | None, index: int | None) -> dict | None:
    if not set_id or index is None:
        return None
    manifest = read_json(set_path(set_id) / "manifest.json") or {}
    items = manifest.get("items", [])
    return items[index] if 0 <= index < len(items) else None


# --- picture-description scenes --------------------------------------------------------

class NewScene(BaseModel):
    lang: str = "en"
    theme: str | None = Field(None, max_length=80)


def scene_files() -> list[Path]:
    if not SCENES_DIR.is_dir():
        return []
    return sorted([*SCENES_DIR.glob("*.json"), *SCENES_DIR.glob("*/*.json")], key=lambda p: -p.stat().st_mtime)


def scene_public(scene: dict) -> dict:
    image = Path(str(scene.get("image_file", "")))
    if image.is_absolute():
        try:
            image = image.resolve().relative_to(SCENES_DIR.resolve())
        except ValueError:
            image = Path(image.name)
    public = {k: v for k, v in scene.items() if k not in ("token_sha", "image_file", "prompt")}
    return {**public, "image_url": f"/media/scenes/{image.as_posix()}" if scene.get("image_file") else None,
            "editable": not PUBLIC}


def scene_path(scene_id: str, missing_ok: bool = False) -> Path | None:
    for path in scene_files():
        scene = read_json(path)
        if isinstance(scene, dict) and str(scene.get("id")) == scene_id:
            return path
    if missing_ok:
        return None
    raise HTTPException(404, f"No scene called '{scene_id}'.")


def load_scene(scene_id: str) -> dict:
    return read_json(scene_path(scene_id))


@app.get("/api/scenes")
def list_scenes():
    scenes = [read_json(p) for p in scene_files()]
    return [scene_public(s) for s in scenes if isinstance(s, dict) and "id" in s and "content_units" in s]


@app.post("/api/scenes", status_code=201)
def create_scene(body: NewScene, request: Request):
    if not ALLOW_BUILDS:
        raise HTTPException(403, "Drawing new scenes is turned off on this demo.")
    scorer = optional_module("metalesionlab.scorer", "Picture description")
    lang = check_lang(body.lang)
    api = get_api()
    limiter.take("scene", client_ip(request))
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    scene = scorer.make_scene(api, lang, theme=(body.theme or None), out_dir=SCENES_DIR)
    token = secrets.token_urlsafe(18)
    path = scene_path(str(scene["id"]), missing_ok=True) or SCENES_DIR / f"{slugify(str(scene['id']))}.json"
    scene = {**scene, "lang": scene.get("lang", lang), "token_sha": _token_hash(token)}
    write_json(path, scene)
    return {**scene_public(scene), "edit_token": token}


class SceneEdit(BaseModel):
    content_units: list[str] = Field(..., min_length=1, max_length=30)


@app.patch("/api/scenes/{scene_id}")
def edit_scene(scene_id: str, body: SceneEdit, x_edit_token: str | None = Header(None)):
    """The reviewer's corrected list of content units (what a full description should mention)."""
    path = scene_path(scene_id)
    scene = read_json(path)
    if PUBLIC and (not x_edit_token or scene.get("token_sha") != _token_hash(x_edit_token)):
        raise HTTPException(403, "On this public demo you can edit only the scenes you drew in this browser.")
    units = list(dict.fromkeys(u.strip()[:120] for u in body.content_units if u.strip()))
    if not units:
        raise HTTPException(422, "Keep at least one content unit.")
    scene.update(content_units=units, units_edited=True)
    write_json(path, scene)
    return scene_public(scene)


@app.get("/media/scenes/{path:path}")
def scene_media(path: str, w: int | None = None):
    return image_response(safe_child(SCENES_DIR, path), w)


# --- Scorer ----------------------------------------------------------------------------

class TypedNaming(BaseModel):
    target: str = Field(..., min_length=1, max_length=60)
    response: str = Field("", max_length=400)
    lang: str = "en"
    set_id: str | None = None
    item: int | None = None
    second_rater: bool = True


def _picture_for_rater(set_id: str | None, item: dict | None) -> bytes | None:
    if not item or not item.get("image"):
        return None
    img = Image.open(SETS_DIR / set_id / item["image"]).convert("RGB")
    img.thumbnail((512, 512))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def score_naming(target: str, response: str, lang: str, set_id: str | None, item: dict | None,
                 second_rater: bool) -> dict:
    """Code one response; a set item supplies the target, accepted alternates and the picture."""
    if item:
        target = item["word"]
    alternates = tuple(item.get("alternates", [])) if item else ()
    coding = classify(target, response, lang, alternates=alternates, judge=judge)
    out = {"target": target, "response": response, "code": coding.code, "head": coding.head,
           "lexical": coding.lexical, "semantic": coding.semantic, "phonological": coding.phonological,
           "alternates": list(alternates), "second": None, "second_status": "off", "agree": None}
    if second_rater:
        if not has_module("metalesionlab.scorer"):
            out["second_status"] = "unavailable"
        else:
            from metalesionlab.scorer import second_rater as rate
            try:
                second = rate(get_api(), target, response, lang, image=_picture_for_rater(set_id, item))
                code = norm_code(second.get("code"))
                out.update(second={"code": code, "rationale": second.get("rationale", "")}, second_status="ok",
                           agree=code == coding.code)
            except BudgetExceeded:
                raise
            except Exception as e:
                log.warning("second rater failed: %s", e)
                out["second_status"] = "error"
    return out


def read_upload(audio: UploadFile) -> tuple[bytes, str]:
    data = audio.file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "The recording is empty. Check that the microphone is allowed and try again.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That recording is too large (12 MB at most).")
    suffix = Path(audio.filename or "").suffix.lower()
    if not suffix:
        suffix = AUDIO_SUFFIXES.get((audio.content_type or "").split(";")[0].strip().lower(), ".webm")
    return data, suffix


def transcribe_upload(audio: UploadFile, task: str, lang: str, request: Request) -> tuple[str, float]:
    """Convert to 16 kHz WAV, check the length, count against the visitor's limit, then transcribe
    with the test's language as a hint. Short naming clips get a silent lead-in, without which
    Muse Voice Transcribe sometimes returns nothing."""
    audio_mod = optional_module("metalesionlab.audio", "Voice scoring")
    data, suffix = read_upload(audio)
    try:
        wav = audio_mod.to_wav16k(data, suffix)
        duration = float(audio_mod.duration_s(wav))
    except audio_mod.FFmpegMissing as e:
        raise HTTPException(503, "Voice scoring needs ffmpeg on the server to read browser recordings, and it "
                                 "isn't installed. Typed responses still work.") from e
    except Exception as e:
        log.warning("audio conversion failed: %s", e)
        raise HTTPException(400, "Couldn't read that recording. Try again, or use typed responses.") from e
    if duration > MAX_CLIP_S[task]:
        raise HTTPException(413, f"The recording is {duration:.0f} s; {MAX_CLIP_S[task]} s is the most for this task.")
    if task == "naming":
        wav = audio_mod.pad_silence(wav, NAMING_PAD_S)
    api = get_api()
    limiter.take("score", client_ip(request))
    body = api.transcribe(wav, language=lang)
    return str(body.get("transcript") or "").strip(), round(duration, 2)


@app.post("/api/score/naming")
def score_naming_audio(request: Request, audio: UploadFile = File(...), target: str = Form(..., max_length=60),
                       lang: str = Form("en"), set_id: str | None = Form(None), item: int | None = Form(None),
                       second_rater: bool = Form(True)):
    check_lang(lang)
    entry = set_item(set_id, item)
    transcript, duration = transcribe_upload(audio, "naming", lang, request)
    return {**score_naming(target, transcript, lang, set_id, entry, second_rater),
            "transcript": transcript, "duration_s": duration}


@app.post("/api/score/naming/text")
def score_naming_text(body: TypedNaming, request: Request):
    check_lang(body.lang)
    entry = set_item(body.set_id, body.item)
    get_api()
    limiter.take("score", client_ip(request))
    return score_naming(body.target, body.response, body.lang, body.set_id, entry, body.second_rater)


@app.post("/api/score/description")
def score_description(request: Request, scene_id: str = Form(...), lang: str = Form("en"),
                      transcript: str | None = Form(None, max_length=6000), audio: UploadFile | None = File(None)):
    scorer = optional_module("metalesionlab.scorer", "Picture-description scoring")
    check_lang(lang)
    scene = load_scene(scene_id)
    duration = None
    if audio is not None:
        transcript, duration = transcribe_upload(audio, "description", lang, request)
    elif transcript and transcript.strip():
        get_api()
        limiter.take("score", client_ip(request))
    else:
        raise HTTPException(422, "Send a recording or a typed description.")
    result = scorer.score_description(get_api(), transcript, scene, lang, duration_s=duration)
    return {"scene_id": scene_id, "transcript": transcript, "duration_s": duration, **result}


@app.post("/api/score/fluency")
def score_fluency(request: Request, category: str = Form(..., max_length=60), lang: str = Form("en"),
                  transcript: str | None = Form(None, max_length=4000), audio: UploadFile | None = File(None)):
    scorer = optional_module("metalesionlab.scorer", "Category-fluency scoring")
    check_lang(lang)
    duration = None
    if audio is not None:
        transcript, duration = transcribe_upload(audio, "fluency", lang, request)
    elif transcript and transcript.strip():
        get_api()
        limiter.take("score", client_ip(request))
    else:
        raise HTTPException(422, "Send a recording or a typed list.")
    result = scorer.score_fluency(get_api(), transcript, category, lang)
    return {"category": category, "transcript": transcript, "duration_s": duration, **result}


# --- Model Lab -------------------------------------------------------------------------

_lab_cache: dict[Path, tuple[int, list[dict]]] = {}


def _conditions_in(path: Path) -> list[dict]:
    """Condition dicts from one JSON file: a condition, a list of them, or {"conditions": [...]}."""
    mtime = path.stat().st_mtime_ns
    if path in _lab_cache and _lab_cache[path][0] == mtime:
        return _lab_cache[path][1]
    data = read_json(path)
    if isinstance(data, dict) and isinstance(data.get("conditions"), list):
        data = data["conditions"]
    found = [c for c in (data if isinstance(data, list) else [data])
             if isinstance(c, dict) and "id" in c and isinstance(c.get("items"), list)]
    _lab_cache[path] = (mtime, found)
    return found


def lab_conditions() -> tuple[list[dict], bool]:
    """Real conditions from TOT_DATA_DIR/lesion when there are any, else the shipped sample."""
    real = [c for p in sorted(LESION_DIR.glob("*.json")) for c in _conditions_in(p)] if LESION_DIR.is_dir() else []
    if real:
        return real, False
    return _conditions_in(SAMPLE_LAB), True


def is_baseline(c: dict) -> bool:
    spec = c.get("spec") or {}
    return "intact" in str(c["id"]).lower() or str(spec.get("site", "")).lower() in ("", "none", "intact")


def accuracy_pct(c: dict) -> float | None:
    acc = c.get("accuracy")
    if acc is None and c.get("items"):
        acc = sum(it.get("code") == "Correct" for it in c["items"]) / len(c["items"])
    return None if acc is None else round(acc * 100 if acc <= 1 else acc, 1)


def describe_spec(spec: dict) -> str:
    if not spec or str(spec.get("site", "")).lower() in ("", "none", "intact"):
        return "Intact model"
    parts = [f"{spec['localizer']} localizer" if spec.get("localizer") else str(spec.get("site"))]
    layers = spec.get("layers")
    if isinstance(layers, list) and layers:
        nums = sorted(int(x) for x in layers)
        parts.append(f"layers {nums[0]}–{nums[-1]}" if nums == list(range(nums[0], nums[-1] + 1)) and len(nums) > 1
                     else "layers " + ", ".join(map(str, nums)))
    elif layers:
        parts.append(f"layers {layers}")
    if spec.get("method"):
        parts.append(str(spec["method"]))
    if spec.get("fraction") is not None:
        frac = float(spec["fraction"])
        parts.append(f"{frac * 100:g}% of units" if frac <= 1 else f"{frac:g}% of units")
    elif spec.get("units") is not None:
        parts.append(f"{spec['units']} units")
    return " · ".join(parts)


def condition_summary(c: dict, sample: bool) -> dict:
    counts = c.get("counts")
    if not counts:
        counts = {}
        for it in c["items"]:
            counts[it.get("code", "?")] = counts.get(it.get("code", "?"), 0) + 1
    return {"id": c["id"], "label": c.get("label") or describe_spec(c.get("spec") or {}), "spec": c.get("spec") or {},
            "accuracy": accuracy_pct(c), "counts": counts, "n_items": len(c["items"]),
            "baseline": is_baseline(c), "sample": sample or bool(c.get("sample")), "note": c.get("note")}


@app.get("/api/lab/conditions")
def lab_list():
    conditions, sample = lab_conditions()
    return {"sample": sample, "conditions": [condition_summary(c, sample) for c in conditions]}


@app.get("/api/lab/conditions/{cond_id}")
def lab_condition(cond_id: str):
    conditions, sample = lab_conditions()
    c = next((c for c in conditions if str(c["id"]) == cond_id), None)
    if c is None:
        raise HTTPException(404, f"No condition '{cond_id}'.")
    set_id = c.get("set") or "demo_en"
    pictures = {}
    if SET_ID.match(set_id) and (manifest := read_json(SETS_DIR / set_id / "manifest.json")):
        pictures = {it["word"]: f"/media/sets/{set_id}/{it['image']}" for it in manifest["items"] if it.get("image")}
    items = [{**it, "image_url": pictures.get(it.get("word"))} for it in c["items"]]
    return {**condition_summary(c, sample), "items": items}

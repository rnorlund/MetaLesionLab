"""Naming Assessment routes: timed picture naming with latency (/assess for clinicians and
researchers, /take for anyone), session reports, parallel forms, the public test's reference
range, and personal tests made from a photo.

Privacy: audio and photos are processed in memory and sent to the Meta Model API; nothing about
the person is written to disk. Session results stay in the browser (IndexedDB). The only thing
stored here is the summary a volunteer chooses to contribute to the public test's reference range
(language, set, accuracy, median latency, optional age band, date): no audio, transcripts, names
or IP addresses.

Measurements only; no diagnosis or prognosis. Included by app.py with one line.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
import time
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from metalesionlab import assessment
from metalesionlab.meta_api import BudgetExceeded

log = logging.getLogger("tot.assess")
router = APIRouter()
HERE = Path(__file__).resolve().parent
NORMS_PUBLIC = HERE.parents[1] / "public_data"
LANGUAGE_SUPPORT = HERE.parents[1] / "public_data" / "language_support.json"
RECEIPT_KEY = os.environ.get("TOT_RECEIPT_KEY", "").encode() or secrets.token_bytes(32)
RECEIPT_MAX_AGE_S = 3 * 3600
TRANSCRIBE_LEAD_S = 0.05  # transcribe from just before the picture appeared
MAX_TIME_LIMIT_S = 60.0
CONTRIBUTIONS_PER_DAY = 3
DISCLAIMER = "For use by clinicians and researchers. Measurements only; no diagnosis or prognosis."


def _web():
    """The main app module, looked up at call time (tests patch its settings)."""
    from metalesionlab.web import app as web
    return web


def _warm_wordnet() -> None:
    """Load WordNet once in the background (20-40 s with current NLTK), holding the lock scoring
    uses, so the first visitor's answers wait for it instead of racing it."""
    from metalesionlab.naming_errors import WORDNET_LOCK, _wordnet
    try:
        with WORDNET_LOCK:
            _wordnet().morphy("cats")
    except Exception as e:  # scoring still loads it on first use
        log.warning("WordNet warm-up failed: %s", e)


router.add_event_handler("startup", lambda: threading.Thread(target=_warm_wordnet, daemon=True).start())


# --- pages -------------------------------------------------------------------------------

def _page(name: str):
    def page():
        return FileResponse(HERE / "pages" / name, headers={"Cache-Control": "no-cache"})
    return page


router.add_api_route("/assess", _page("assess.html"), methods=["GET"], include_in_schema=False)
router.add_api_route("/take", _page("take.html"), methods=["GET"], include_in_schema=False)


# --- sets ----------------------------------------------------------------------------------

def kept_items(set_id: str) -> list[dict]:
    web = _web()
    manifest = web.read_json(web.set_path(set_id) / "manifest.json") or {}
    return [{**it, "index": i} for i, it in enumerate(manifest.get("items", []))
            if it.get("status") == "kept" and it.get("image")]


def set_version(items: list[dict]) -> str:
    """Changes whenever the kept pictures or words change, so reference ranges never mix versions."""
    key = json.dumps([(it["word"], it["image"]) for it in items], ensure_ascii=False)
    return hashlib.sha1(key.encode()).hexdigest()[:10]


def is_public_test(set_id: str | None) -> bool:
    return bool(set_id) and set_id.startswith("demo_")


# How to answer, per language: spoken scoring is most reliable in these forms (docs/languages.md).
ANSWER_FORMS = {
    "en": {"instruction": "Say the name with one word.", "example": "cat"},
    "es": {"instruction": "Say the word with un or una.", "example": "un gato"},
    "fr": {"instruction": "Say the word with un or une.", "example": "un chat"},
    "pt": {"instruction": "Say the word with um or uma.", "example": "um gato"},
    "zh": {"instruction": "Say the word with a measure word, such as 一只 or 一个.", "example": "一只猫"},
    "hi": {"instruction": "Say the word on its own.", "example": "बिल्ली"},
    # Oct 27 (docs/languages.md): the form that scored best with synthesized voices.
    "de": {"instruction": "Say it in a short sentence: Das ist ein … or Das ist eine ….",
           "example": "Das ist eine Katze"},
    "it": {"instruction": "Say the word with its article: un, una or un'.", "example": "un gatto"},
    "nl": {"instruction": "Say the word with its article: een.", "example": "een kat"},
    "ja": {"instruction": "Say the word with です.", "example": "猫です"},
    "ko": {"instruction": "Say the word on its own.", "example": "고양이"},
    "ar": {"instruction": "Say the word with the article al- (ال).", "example": "القطة"},
    "tr": {"instruction": "Say the word with bir.", "example": "bir kedi"},
    "pl": {"instruction": "Say it in a short sentence: To jest ….", "example": "To jest kot"},
    "id": {"instruction": "Say it in a short sentence: Ini ….", "example": "Ini kucing"},
    "vi": {"instruction": "Say the word with its classifier, such as con or cái.", "example": "con mèo"},
}


def language_table() -> list[dict]:
    """Every scoring language with its measured status (public_data/language_support.json):
    verified, works with review, or experimental; and how to answer for the best scoring."""
    web = _web()
    support = web.read_json(LANGUAGE_SUPPORT) or {}
    status = {row.get("language"): row.get("status") for row in support.get("table", []) if isinstance(row, dict)}
    return [{"code": code, "name": name, "status": status.get(name) or "experimental",
             **ANSWER_FORMS.get(code, {"instruction": "Say the word on its own.", "example": None})}
            for code, name in web.LANGUAGE_NAMES.items()]


@router.get("/api/assess/config")
def config():
    web = _web()
    languages = language_table()
    verified = {l["code"] for l in languages if l["status"] == "verified"}
    public = []
    for s in web.list_sets():  # the public test uses the demo sets in verified languages
        if s["demo"] and s["status"] == "done" and s["kept"] >= 5 and s["lang"] in verified:
            items = kept_items(s["id"])
            public.append({"id": s["id"], "lang": s["lang"], "n_items": len(items), "version": set_version(items)})
    order = [l["code"] for l in languages]
    public.sort(key=lambda p: order.index(p["lang"]) if p["lang"] in order else 99)
    return {"time_limit_s": assessment.DEFAULT_TIME_LIMIT_S, "max_time_limit_s": MAX_TIME_LIMIT_S,
            "norms_min_n": assessment.NORMS_MIN_N, "age_bands": list(assessment.AGE_BANDS),
            "languages": languages, "public_sets": public, "disclaimer": DISCLAIMER}


# --- scoring one response ----------------------------------------------------------------------

def _alternates(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        val = json.loads(raw)
        items = val if isinstance(val, list) else [val]
    except ValueError:
        items = raw.replace("|", ";").split(";")
    return [str(a).strip().lower()[:40] for a in items if str(a).strip()][:12]


def _code(target: str, transcript: str, lang: str, set_id: str | None, item: int | None,
          alternates: list[str], second_rater: bool) -> dict:
    """Doubled transcripts collapse, the first complete attempt is coded, the second rater looks."""
    web = _web()
    entry = web.set_item(set_id, item) if set_id else None
    if entry is None:  # a private set: target and alternates come from the browser, no picture
        entry = {"word": target.strip().lower(), "alternates": alternates}
        set_id = None
    elif alternates:
        entry = {**entry, "alternates": list(dict.fromkeys([*entry.get("alternates", []), *alternates]))}
    collapsed = web.collapse_repeat(transcript, lang, entry["word"])
    first = assessment.first_complete_response(collapsed, lang, entry["word"])
    out = web.score_naming(entry["word"], first["scored"], lang, set_id, entry, second_rater)
    return {**out, "transcript": transcript, "response": transcript, "scored_response": first["scored"],
            "attempts": first["attempts"], "split": first["split"]}


def _receipt(set_id: str | None, item: int | None, lang: str, code: str, latency_ms: float | None) -> str | None:
    if not is_public_test(set_id) or item is None:
        return None
    payload = {"set": set_id, "v": set_version(kept_items(set_id)), "item": item, "lang": lang, "code": code,
               "latency_ms": None if latency_ms is None else round(latency_ms), "t": int(time.time()),
               "nonce": secrets.token_hex(4)}
    return assessment.sign_receipt(payload, RECEIPT_KEY)


@router.post("/api/assess/naming")
def score_timed(request: Request, audio: UploadFile = File(...), target: str = Form(..., max_length=60),
                lang: str = Form("en"), picture_onset_ms: float = Form(..., ge=0, le=10000),
                time_limit_s: float = Form(assessment.DEFAULT_TIME_LIMIT_S, gt=0, le=MAX_TIME_LIMIT_S),
                set_id: str | None = Form(None), item: int | None = Form(None),
                alternates: str | None = Form(None, max_length=600), second_rater: bool = Form(False)):
    """One timed naming response: speech onset and latency from the audio, then transcription
    (with the test's language as a hint), first-complete-attempt coding and, if asked, Muse Spark."""
    web = _web()
    web.check_lang(lang)
    audio_mod = web.optional_module("metalesionlab.audio", "Voice scoring")
    data, suffix = web.read_upload(audio)
    try:
        wav = audio_mod.to_wav16k(data, suffix)
        clip_s = float(audio_mod.duration_s(wav))
    except audio_mod.FFmpegMissing as e:
        raise HTTPException(503, "This recording needs ffmpeg on the server to convert it. The assessment page "
                                 "sends WAV, which doesn't; reload the page and try again.") from e
    except Exception as e:
        log.warning("audio conversion failed: %s", e)
        raise HTTPException(400, "Couldn't read that recording. Please try again.") from e
    onset_s = picture_onset_ms / 1000
    if onset_s >= clip_s:
        raise HTTPException(422, "The picture onset is after the end of the recording.")
    if clip_s - onset_s > time_limit_s + 0.5:  # never score speech after the time limit
        wav = audio_mod.trim(wav, 0, onset_s + time_limit_s)
        clip_s = onset_s + time_limit_s

    timing = audio_mod.detect_speech(wav, search_from_s=onset_s)
    latency_ms = None if timing.onset_s is None else (timing.onset_s - onset_s) * 1000
    duration_ms = None if timing.onset_s is None else (timing.offset_s - timing.onset_s) * 1000
    reached_limit = clip_s - onset_s >= time_limit_s - 0.05
    flags = []
    if timing.speech_at_start:
        flags.append("speech_at_onset")
        latency_ms = None
    if timing.lead_in_noisy:
        flags.append("noisy_lead_in")
    silent = timing.onset_s is None and timing.peak_dbfs < timing.threshold_dbfs + 6

    if silent:  # nothing above the background: no response, and nothing to send for transcription
        transcript = ""
    else:
        api = web.get_api()
        web.limiter.take("score", web.client_ip(request))
        clip = audio_mod.trim(wav, max(0.0, onset_s - TRANSCRIBE_LEAD_S), None)
        clip = audio_mod.pad_silence(clip, web.NAMING_PAD_S)
        body = api.transcribe(clip, language=lang)  # retries network and 5xx failures itself
        transcript = str(body.get("transcript") or "").strip()
        if timing.onset_s is None and transcript:
            flags.append("no_onset_found")
    out = _code(target, transcript, lang, set_id, item, _alternates(alternates), second_rater and bool(transcript))
    timeout = out["code"] == "NoResponse" and reached_limit
    if out["code"] == "NoResponse":  # a refusal or silence has no naming latency
        latency_ms = duration_ms = None
    out.update(latency_ms=None if latency_ms is None else round(latency_ms),
               duration_ms=None if duration_ms is None else round(duration_ms),
               timeout=timeout, flags=flags, clip_s=round(clip_s, 2), picture_onset_ms=round(picture_onset_ms),
               vad=timing.as_dict(), receipt=_receipt(set_id, item, lang, out["code"], latency_ms))
    return out


class Rescore(BaseModel):
    target: str = Field(..., min_length=1, max_length=60)
    response: str = Field("", max_length=400)
    lang: str = "en"
    set_id: str | None = None
    item: int | None = None
    alternates: list[str] = Field(default_factory=list, max_length=12)
    second_rater: bool = False


@router.post("/api/assess/rescore")
def rescore(body: Rescore, request: Request):
    """Code a corrected transcript (a reviewer fixing what the recognizer heard)."""
    web = _web()
    web.check_lang(body.lang)
    web.get_api()
    web.limiter.take("score", web.client_ip(request))
    return _code(body.target, body.response.strip(), body.lang, body.set_id, body.item,
                 [a.strip().lower() for a in body.alternates if a.strip()], body.second_rater)


# --- reference panel and report ------------------------------------------------------------------

def reference_panel() -> dict:
    """Published PNT group results (175 items, different pictures): controls and pooled aphasia
    groups. Group references, not norms for any one person or for these pictures."""
    hp = _web().lab_human()
    controls = []
    for c in hp.get("controls", []):
        pct = c.get("correct_percent")
        if isinstance(pct, dict):
            lo, hi = min(pct.values()), max(pct.values())
            acc = f"{lo:g}–{hi:g}%" if lo != hi else f"{lo:g}%"
        elif c.get("correct") is not None:
            acc = f"{100 * c['correct']:g}%"
        else:
            continue
        controls.append({"label": "Adults without brain injury", "n": c.get("n"), "accuracy": acc,
                         "source": c["source"]["short"], "citation": c["source"]["citation"], "note": c["source"].get("note")})
    groups = []
    for p in hp.get("pooled", []):
        shares = p["shares"]
        groups.append({"label": p["name"], "accuracy": f"{100 * shares.get('Correct', 0):.0f}%", "shares": shares,
                       "missing": p.get("missing", []), "source": p["source"]["short"],
                       "citation": p["source"]["citation"], "note": p.get("mapping")})
    return {"codes": hp.get("codes", []), "controls": controls, "groups": groups,
            "caption": "Published group results on the Philadelphia Naming Test (175 items; different pictures "
                       "and procedure). Group references only, not norms for this person or this test."}


@router.get("/api/assess/reference")
def reference():
    return reference_panel()


class ReportItem(BaseModel):
    n: int | None = None
    target: str = Field("", max_length=80)
    transcript: str | None = Field(None, max_length=400)
    scored_response: str | None = Field(None, max_length=400)
    code: str | None = None
    second: dict | None = None
    reviewer: str | None = None
    latency_ms: float | None = None
    reviewer_latency_ms: float | None = None
    duration_ms: float | None = None
    timeout: bool = False
    practice: bool = False
    flags: list[str] = Field(default_factory=list)


class ReportSession(BaseModel):
    speaker: str = Field("", max_length=24)
    set_name: str = Field("", max_length=80)
    private_set: bool = False
    lang: str = "en"
    started: str | None = None
    time_limit_s: float = assessment.DEFAULT_TIME_LIMIT_S
    form: str | None = Field(None, max_length=20)
    second_rater: bool = False
    items: list[ReportItem] = Field(..., max_length=400)


class ReportBody(BaseModel):
    session: ReportSession
    history: list[dict] = Field(default_factory=list, max_length=60)  # this speaker's earlier sessions


@router.post("/api/assess/report.pdf")
def report_pdf(body: ReportBody):
    """A one-page session report (with an item appendix). Rendered in memory; nothing is kept."""
    from metalesionlab.web import assess_report

    session = body.session.model_dump()
    pdf = assess_report.render(session, assessment.summarize(session["items"]), reference_panel(), body.history)
    speaker = "".join(c if c.isalnum() or c in "-_" else "_" for c in session["speaker"]) or "session"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="naming_report_{speaker}.pdf"'})


# --- parallel forms -----------------------------------------------------------------------------

class FormsBody(BaseModel):
    lang: str = "en"
    words: list[str] = Field(..., min_length=4, max_length=400)


@router.post("/api/assess/forms")
def forms(body: FormsBody):
    """Two halves matched on word frequency and length, for re-testing without repeating items."""
    _web().check_lang(body.lang)
    words = [w.strip()[:60] for w in body.words]
    if any(not w for w in words):
        raise HTTPException(422, "Every item needs a target word.")
    return assessment.parallel_forms(words, body.lang)


# --- the public test's reference range ------------------------------------------------------------

_norms_lock = threading.Lock()
_contributions: dict[str, list[float]] = {}


def norms_dir() -> Path:
    """TIPPA_NORMS_DIR on a host whose data folder is read-only or not persistent, else DATA_DIR/norms."""
    custom = os.environ.get("TIPPA_NORMS_DIR")
    return Path(custom) if custom else _web().DATA_DIR / "norms"


def norms_records(set_id: str, version: str) -> list[dict]:
    path = norms_dir() / f"{set_id}.jsonl"
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [r for r in rows if r.get("set_version") == version]


def norms_status(set_id: str) -> dict:
    items = kept_items(set_id)
    version = set_version(items)
    live = assessment.norms_summary(norms_records(set_id, version))
    out = {**live, "set": set_id, "set_version": version, "source": "live"}
    published = _web().read_json(NORMS_PUBLIC / f"naming_norms_{set_id}.json")
    if isinstance(published, dict) and published.get("set_version") == version and published.get("n", 0) > live["n"]:
        out = {**published, "source": "public_data"}
    return out


@router.get("/api/assess/norms/{set_id}")
def get_norms(set_id: str):
    if not is_public_test(set_id):
        raise HTTPException(404, "Reference ranges are collected only for the public demo tests.")
    return norms_status(set_id)


class Contribution(BaseModel):
    receipts: list[str] = Field(..., min_length=1, max_length=200)
    consent: bool
    adult_no_condition: bool
    age_band: str | None = None


@router.post("/api/assess/norms/{set_id}", status_code=201)
def contribute(set_id: str, body: Contribution, request: Request):
    """Add one volunteer's session summary to the reference range. Only the summary is stored."""
    web = _web()
    if not is_public_test(set_id):
        raise HTTPException(404, "Reference ranges are collected only for the public demo tests.")
    if not (body.consent and body.adult_no_condition):
        raise HTTPException(422, "Contributions need both confirmations.")
    if body.age_band and body.age_band not in assessment.AGE_BANDS:
        raise HTTPException(422, "Unknown age band.")
    items = kept_items(set_id)
    version = set_version(items)
    receipts = [assessment.read_receipt(r, RECEIPT_KEY) for r in body.receipts]
    now = time.time()
    if any(r is None for r in receipts):
        raise HTTPException(422, "These results can't be checked (the server may have restarted). Please take the test again.")
    if any(r["set"] != set_id or r["v"] != version or now - r["t"] > RECEIPT_MAX_AGE_S for r in receipts):
        raise HTTPException(422, "These results are from a different or older version of the test.")
    if len({r["lang"] for r in receipts}) != 1 or sorted(r["item"] for r in receipts) != sorted(it["index"] for it in items):
        raise HTTPException(422, "Only complete tests can be added: every picture needs a scored answer.")

    fingerprint = hashlib.sha256("|".join(sorted(body.receipts)).encode()).hexdigest()
    who = hashlib.sha256(web.client_ip(request).encode() + RECEIPT_KEY).hexdigest()  # in memory only
    with _norms_lock:
        recent = [t for t in _contributions.get(who, []) if now - t < 86400]
        if len(recent) >= CONTRIBUTIONS_PER_DAY:
            raise HTTPException(429, "Thank you! This browser has already added the most results allowed today.")
        d = norms_dir()
        d.mkdir(parents=True, exist_ok=True)
        seen = d / ".seen"
        if seen.exists() and fingerprint in seen.read_text().split():
            raise HTTPException(409, "These results have already been added. Thank you!")
        record = {"set": set_id, "set_version": version, "lang": receipts[0]["lang"],
                  **assessment.summary_from_receipts(receipts), "age_band": body.age_band,
                  "date": time.strftime("%Y-%m-%d", time.gmtime(now))}
        with (d / f"{set_id}.jsonl").open("a") as f:
            f.write(json.dumps(record) + "\n")
        with seen.open("a") as f:
            f.write(fingerprint + "\n")
        _contributions[who] = recent + [now]
    return {"stored": record, "norms": norms_status(set_id)}


# --- a personal test from a photo -----------------------------------------------------------------

photo_jobs: dict[str, dict] = {}
PHOTO_JOB_TTL_S = 1800


def _prune_photo_jobs() -> None:
    now = time.time()
    for k in [k for k, j in photo_jobs.items() if now - j["created"] > PHOTO_JOB_TTL_S]:
        photo_jobs.pop(k, None)


def _run_photo_job(job_id: str, photo: bytes, mime: str, lang: str, style: str, max_items: int) -> None:
    from metalesionlab import photo_test

    web = _web()
    job = photo_jobs[job_id]
    try:
        job["status"] = "running"
        result = photo_test.build_from_photo(web.get_api(), photo, mime, lang, style=style, max_items=max_items,
                                             judge=web.judge, progress=lambda msg: job.update(stage=msg))
        job.update(status="done", result=result)
    except BudgetExceeded:
        job.update(status="error", error=web.BUDGET_MSG)
    except Exception as e:
        log.exception("photo test %s failed", job_id)
        job.update(status="error", error=f"The test couldn't be made: {type(e).__name__}: {e}")
    finally:
        job["finished"] = time.time()


@router.post("/api/assess/photo-test", status_code=202)
def photo_test_start(request: Request, photo: UploadFile = File(...), lang: str = Form("en"),
                     style: str = Form("line"), max_items: int = Form(8, ge=2, le=12)):
    """Muse Spark lists the nameable objects in a photo, SAM 3.1 finds each one, and Muse Image
    redraws it as a line drawing (or it is cropped from the photo); then the Test Studio checks
    run. The photo is kept in memory only, and the result is handed back to the browser."""
    web = _web()
    web.check_lang(lang)
    if style not in ("line", "photo"):
        raise HTTPException(422, "style is 'line' or 'photo'.")
    if style == "line" and not web.ALLOW_BUILDS:
        raise HTTPException(403, "Drawing new pictures is turned off on this demo; choose real-photo crops instead.")
    data = photo.file.read(web.MAX_UPLOAD_BYTES + 1)
    if not data:
        raise HTTPException(400, "The photo is empty.")
    if len(data) > web.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That photo is too large (12 MB at most).")
    mime = (photo.content_type or "image/jpeg").split(";")[0]
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(415, "Send a JPEG, PNG or WebP photo.")
    web.get_api()
    web.limiter.take("build", web.client_ip(request))
    _prune_photo_jobs()
    job_id = secrets.token_urlsafe(12)
    photo_jobs[job_id] = {"status": "queued", "created": time.time(), "stage": "Starting"}
    threading.Thread(target=_run_photo_job, args=(job_id, data, mime, lang, style, max_items), daemon=True).start()
    return {"job": job_id, "status": "queued"}


@router.get("/api/assess/photo-test/{job_id}")
def photo_test_status(job_id: str):
    job = photo_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "No such job (results are kept for 30 minutes, then deleted).")
    out = {k: job.get(k) for k in ("status", "stage", "error")}
    if job["status"] == "done":
        out["result"] = job["result"]
        photo_jobs.pop(job_id, None)  # handed to the browser; the server keeps nothing
    return out

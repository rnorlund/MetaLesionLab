"""Draw a chair (/draw, and the pad on the landing page): draw a chair (or a cat, a house...) or upload a
photo of one drawn on paper, and see where it lands among Muse Image's doodles and 200 people's drawings
of the same thing, measured as in the Plato's Chair experiment.

POST /api/draw takes the canvas strokes and renders them the way the experiment rendered people's
drawings. POST /api/draw/upload takes a photo (the browser re-encodes it to a JPEG of at most 1024 px,
which drops EXIF and location) and treats it like Muse Image's pictures: flatten the paper, crop to the
ink. Photos of things or scenes get a friendly refusal. Both embed with Meta's DINOv2-base on the CPU
(metalesionlab/draw.py) and compare with precomputed reference data (web/data/draw.json).

The abstract ideas ("Draw the invisible": God, love, time…, web/data/draw_ideas.json) take the same routes but
are scored against Muse Image's 16 doodles only (draw.score_ai_only): Quick, Draw! has no people's drawings of
them, so the response carries no number about people.

No Meta API calls, so the spend guard lists both routes as free; they cost CPU instead, so they have
their own limits: per visitor per day and per minute (limits.py buckets "draw" and "draw_burst"), a
request-size cap, and DRAW_SLOTS embeddings at a time. The model loads on the first drawing only.

Drawings and photos are processed in memory and never stored or logged, unless donations are switched on
(TIPPA_DONATIONS=1) and the visitor opts in: see draw_donations.py. app.py includes this router.
"""
from __future__ import annotations

import base64
import io
import json
import os
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from metalesionlab import draw
from metalesionlab.web import app as web
from metalesionlab.web import draw_donations as donations
from metalesionlab.web.limits import DailyLimiter, client_ip, limit_for, limiter

router = APIRouter()

MAX_BODY = 512 * 1024  # 8,000 points of JSON is about 100 KB
WAIT_S = float(os.environ.get("DRAW_WAIT_S", "15"))
embedder = draw.LazyEmbedder()
slots = threading.BoundedSemaphore(max(1, int(os.environ.get("DRAW_SLOTS", "1"))))
burst = DailyLimiter(window_s=60)  # same mechanism as limits.limiter, a one-minute window
PRIVACY_OFF = "Drawings are processed in memory and never stored or logged."

_reference: draw.Reference | None = None
_ref_lock = threading.Lock()


def reference() -> draw.Reference:
    global _reference
    with _ref_lock:
        if _reference is None:
            try:
                _reference = draw.Reference.load(draw.DATA_PATH)
            except (OSError, ValueError, KeyError) as e:
                raise HTTPException(503, "The drawing game's reference data isn't on this server.") from e
        return _reference


def take_limits(ip: str) -> None:
    """One drawing from this visitor: at most draw_burst a minute and draw a day (429 past either)."""
    try:
        burst.take("draw_burst", ip)
    except HTTPException as e:
        raise HTTPException(429, f"That's a lot of drawings in a minute ({limit_for('draw_burst')} at most). "
                                 "Take a breath and try again shortly.", headers=e.headers) from None
    limiter.take("draw", ip)


async def read_capped(request: Request, cap: int, what: str) -> bytes:
    size = int(request.headers.get("content-length") or 0)
    if size > cap:
        raise HTTPException(413, f"That {what} is too big to score.")
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > cap:
            raise HTTPException(413, f"That {what} is too big to score.")
        chunks.append(chunk)
    return b"".join(chunks)


def concept_key(ref: draw.Reference, key) -> str:
    if not isinstance(key, str) or key not in ref.entries:
        raise HTTPException(422, f"Choose one of: {', '.join(ref.entries)}.")
    return key


def flag(value) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() in ("1", "true", "yes", "on"))


def seconds(value) -> float | None:
    try:
        s = float(value) / 1000.0
    except (TypeError, ValueError):
        return None
    return s if 0 <= s <= 3600 else None


def embed(picture):
    if not slots.acquire(timeout=WAIT_S):
        raise HTTPException(503, "Lots of people are drawing right now. Please try again in a few seconds.",
                            headers={"Retry-After": "5"})
    try:
        try:
            model = embedder.get()
        except (ImportError, OSError, RuntimeError) as e:
            raise HTTPException(503, "The drawing model isn't installed on this server, so drawings can't be "
                                     "scored here right now.") from e
        return model([picture])[0]
    finally:
        slots.release()


def maybe_donate(opts: dict, *, key: str, source: str, picture, result: dict, strokes=None, problem=None) -> dict | None:
    """The donation, only when switched on and the visitor ticked both boxes. Never affects the score."""
    if not donations.enabled() or not opts.get("donate"):
        return None
    if not opts.get("adult"):
        return {"status": "declined", "reason": "Donations are only for people who are 18 or older, so nothing "
                                                "was kept."}
    return donations.donate(concept=key, source=source, picture=picture, scores=result, blind=opts.get("blind"),
                            draw_seconds=opts.get("draw_seconds"), strokes=strokes, problem=problem)


def score_strokes(ref: draw.Reference, key: str, strokes, opts: dict) -> dict:
    try:
        picture = ref.prepare(key, draw.render(strokes))  # the clock: prepared as the people's clocks were
        simplified = draw.normalize_strokes(strokes)
    except draw.DrawingError as e:
        raise HTTPException(422, str(e)) from None
    result = ref.score(key, embed(picture))
    donated = maybe_donate(opts, key=key, source="pad", picture=picture, result=result, strokes=simplified)
    if donated:
        result["donation"] = donated
    return result


def data_url(picture) -> str:
    buf = io.BytesIO()
    picture.convert("L").save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def score_upload(ref: draw.Reference, key: str, data: bytes, opts: dict) -> dict:
    try:
        picture, stats = draw.prepare_upload(data)  # the photo itself goes no further than this
    except draw.DrawingError as e:
        raise HTTPException(422, str(e)) from None
    picture = ref.prepare(key, picture)  # the clock: prepared as the people's clocks were
    vec = embed(picture)
    result = ref.score(key, vec)
    # an idea's or a group's score holds no "is this a doodle at all?" distance, so that check is done apart
    stats["d_doodle"] = ref.doodle_distance(vec) if ref.ai_only(key) or ref.group(key) else result.get("d_doodle", 0)
    problem = draw.upload_problem(stats)
    if problem:
        raise HTTPException(422, problem)
    result["source"] = "upload"
    result["picture"] = data_url(picture)  # what DINOv2 saw: the cleaned-up drawing, for the page to show
    donated = maybe_donate(opts, key=key, source="upload", picture=picture, result=result, problem=problem)
    if donated:
        result["donation"] = donated
    return result


@router.get("/draw", include_in_schema=False)
def draw_page():
    return FileResponse(web.HERE / "pages" / "draw.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/draw/concepts")
def draw_concepts():
    """Reference data for the page: per-concept statistics, distances, the 2-D map and thumbnail sprites."""
    return reference().public()


@router.get("/api/draw/status")
def draw_status(request: Request):
    ip = client_ip(request)
    info = donations.public_info()
    return {"model_loaded": embedder.loaded,
            "backend": getattr(embedder.model, "backend", None),
            "model_file": draw.MODEL_PATH.is_file(),
            "limits": {"per_day": limit_for("draw"), "remaining_today": limiter.remaining("draw", ip),
                       "per_minute": limit_for("draw_burst"), "upload_mb": draw.MAX_UPLOAD_BYTES // (1024 * 1024)},
            "donations": info,
            "privacy": info["summary"] if info["enabled"] else PRIVACY_OFF}


@router.post("/api/draw")
async def draw_score(request: Request):
    """Score one drawing: {"concept": "chair", "strokes": [[[x, ...], [y, ...]], ...]} in canvas pixels.
    Optional: "blind" (drawn before seeing the AI's pictures), "draw_ms", and, with donations on,
    "donate" and "adult"."""
    take_limits(client_ip(request))
    raw = await read_capped(request, MAX_BODY, "drawing")
    try:
        body = json.loads(raw or b"null")
    except ValueError:
        raise HTTPException(422, "Send the drawing as JSON: {concept, strokes}.") from None
    if not isinstance(body, dict):
        raise HTTPException(422, "Send the drawing as JSON: {concept, strokes}.")
    ref = reference()
    key = concept_key(ref, body.get("concept"))
    opts = {"donate": flag(body.get("donate")), "adult": flag(body.get("adult")),
            "blind": flag(body.get("blind")) if "blind" in body else None, "draw_seconds": seconds(body.get("draw_ms"))}
    return await run_in_threadpool(score_strokes, ref, key, body.get("strokes"), opts)


@router.post("/api/draw/upload")
async def draw_upload(request: Request):
    """Score a photo of a drawing on paper: the image bytes as the body (JPEG, PNG or WebP), with
    ?concept=chair and, optionally, &blind=1&draw_ms=…&donate=1&adult=1."""
    take_limits(client_ip(request))
    q = request.query_params
    ref = reference()
    key = concept_key(ref, q.get("concept"))
    data = await read_capped(request, draw.MAX_UPLOAD_BYTES, "picture")
    opts = {"donate": flag(q.get("donate")), "adult": flag(q.get("adult")),
            "blind": flag(q.get("blind")) if "blind" in q else None, "draw_seconds": seconds(q.get("draw_ms"))}
    return await run_in_threadpool(score_upload, ref, key, data, opts)


def preload() -> threading.Thread:
    """Load the model and run it once in the background, so the first visitor's drawing doesn't wait for it
    (on a 2-CPU Space that load is the slow part). If it fails, the first drawing loads it as before."""
    def warm():
        try:
            reference().concept("chair")  # the landing page's thing: its vectors are read on first use too
            embedder.get()([draw.render([[[0, 40], [0, 40]]])])
        except Exception:  # noqa: BLE001
            pass

    t = threading.Thread(target=warm, name="draw-preload", daemon=True)
    t.start()
    return t


if flag(os.environ.get("DRAW_PRELOAD")):  # set in the Dockerfile
    preload()

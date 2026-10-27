"""Draw your chair (/draw): draw a chair (or a cat, a house...) and see where it lands among Muse Image's
doodles and 200 people's drawings of the same thing, measured as in the Plato's Chair experiment.

POST /api/draw takes the canvas strokes, renders them the way the experiment rendered people's
drawings, embeds them with Meta's DINOv2-base on the CPU (metalesionlab/draw.py) and compares the
result with precomputed reference data (web/data/draw.json, from scripts/draw_export.py).

No Meta API calls, so the spend guard lists the route as free; it costs CPU instead, so it has its own
limits: per visitor per day and per minute (limits.py buckets "draw" and "draw_burst"), a request-size
cap, and DRAW_SLOTS embeddings at a time. The model loads on the first drawing only: the app's startup
and the other pages never import onnxruntime or torch.

Drawings are processed in memory and never stored or logged; only the numbers go back to the browser.
app.py includes this router with one line.
"""
from __future__ import annotations

import json
import os
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from metalesionlab import draw
from metalesionlab.web import app as web
from metalesionlab.web.limits import DailyLimiter, client_ip, limit_for, limiter

router = APIRouter()

MAX_BODY = 512 * 1024  # 8,000 points of JSON is about 100 KB
WAIT_S = float(os.environ.get("DRAW_WAIT_S", "15"))
embedder = draw.LazyEmbedder()
slots = threading.BoundedSemaphore(max(1, int(os.environ.get("DRAW_SLOTS", "1"))))
burst = DailyLimiter(window_s=60)  # same mechanism as limits.limiter, a one-minute window

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


async def read_body(request: Request) -> dict:
    size = int(request.headers.get("content-length") or 0)
    if size > MAX_BODY:
        raise HTTPException(413, "That drawing is too big to score.")
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_BODY:
            raise HTTPException(413, "That drawing is too big to score.")
        chunks.append(chunk)
    try:
        body = json.loads(b"".join(chunks) or b"null")
    except ValueError:
        raise HTTPException(422, "Send the drawing as JSON: {concept, strokes}.") from None
    if not isinstance(body, dict):
        raise HTTPException(422, "Send the drawing as JSON: {concept, strokes}.")
    return body


def embed_and_score(ref: draw.Reference, key: str, strokes) -> dict:
    try:
        picture = draw.render(strokes)
    except draw.DrawingError as e:
        raise HTTPException(422, str(e)) from None
    if not slots.acquire(timeout=WAIT_S):
        raise HTTPException(503, "Lots of people are drawing right now. Please try again in a few seconds.",
                            headers={"Retry-After": "5"})
    try:
        try:
            model = embedder.get()
        except (ImportError, OSError, RuntimeError) as e:
            raise HTTPException(503, "The drawing model isn't installed on this server, so drawings can't be "
                                     "scored here right now.") from e
        vec = model([picture])[0]
    finally:
        slots.release()
    return ref.score(key, vec)


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
    return {"model_loaded": embedder.loaded,
            "backend": getattr(embedder.model, "backend", None),
            "model_file": draw.MODEL_PATH.is_file(),
            "limits": {"per_day": limit_for("draw"), "remaining_today": limiter.remaining("draw", ip),
                       "per_minute": limit_for("draw_burst")},
            "privacy": "Drawings are processed in memory and never stored or logged."}


@router.post("/api/draw")
async def draw_score(request: Request):
    """Score one drawing: {"concept": "chair", "strokes": [[[x, ...], [y, ...]], ...]} in canvas pixels."""
    take_limits(client_ip(request))
    body = await read_body(request)
    ref = reference()
    key = body.get("concept")
    if not isinstance(key, str) or key not in ref.entries:
        raise HTTPException(422, f"Choose one of: {', '.join(ref.entries)}.")
    return await run_in_threadpool(embed_and_score, ref, key, body.get("strokes"))

"""Play telephone with your own drawing (the Draw page's result card): Plato's Telephone, live, on the visitor's own key.

POST /api/plato/telephone/play takes the visitor's drawing as a data URL and plays the experiment of
plato_telephone.py with it: Muse Spark describes the picture (DESCRIBE_PROMPT, minimal reasoning), Muse Image draws
that description (image_prompt), Spark describes the new picture, and so on for up to 6 rounds. The answer is NDJSON,
one line per step: start, round (the description and the new picture, small), done (or error).

It runs ONLY on the visitor's own Meta API key (own_key.py, the X-Meta-Key header): the demo's budget never pays for
it. Nothing is stored (no files, no ledger) and the key is never logged or echoed; an API error is reported by its
type only. The guard's "telephone" rule limits the burst; a daily count per address is kept here, in memory.
"""
from __future__ import annotations

import base64
import binascii
import io
import json
import logging
import re

import httpx
import openai
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from PIL import Image, ImageOps, UnidentifiedImageError

from metalesionlab import meta_api
from metalesionlab import plato_telephone as T
from metalesionlab.web import own_key
from metalesionlab.web.agent_routes import _Counter
from metalesionlab.web.limits import client_ip

log = logging.getLogger("metalesionlab.telephone_live")
router = APIRouter()

MAX_ROUNDS = 6
DEFAULT_ROUNDS = 5
GAMES_A_DAY = 10  # per address
MAX_BYTES = 1_500_000  # decoded
MIN_SIDE = 32
SHOW_SIDE = 512  # the pictures sent back to the page
NO_KEY_MSG = "Telephone runs on your own Meta API key: add one under More → Use your own API key."
_DATA_URL = re.compile(r"data:image/(png|jpeg|webp);base64,", re.I)
_games = _Counter()


def _bad(msg: str) -> HTTPException:
    return HTTPException(422, msg)


def _prepare(data_url: str) -> bytes:
    """The visitor's picture as a PNG for Spark: RGB on white, at most SPARK_SIDE on the long side."""
    m = _DATA_URL.match(data_url or "")
    if not m:
        raise _bad("Send the drawing as a PNG, JPEG or WebP picture.")
    try:
        raw = base64.b64decode(data_url[m.end():], validate=True)
    except (binascii.Error, ValueError):
        raise _bad("That picture could not be read.")
    if len(raw) > MAX_BYTES:
        raise _bad("That picture is too large (1.5 MB at most).")
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError):
        raise _bad("That is not a picture we can read.")
    if min(im.size) < MIN_SIDE:
        raise _bad("That picture is too small.")
    buf = io.BytesIO()
    _shrink(_flat(im), T.SPARK_SIDE).save(buf, "PNG")
    return buf.getvalue()


def _flat(im: Image.Image) -> Image.Image:
    rgba = ImageOps.exif_transpose(im).convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, rgba).convert("RGB")


def _shrink(im: Image.Image, side: int) -> Image.Image:
    k = side / max(im.size)
    if k < 1:
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    return im


def _small(png: bytes) -> str:
    """A generated picture for the page: 512 px, WebP."""
    buf = io.BytesIO()
    _shrink(_flat(Image.open(io.BytesIO(png))), SHOW_SIDE).save(buf, "WEBP", quality=80)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def _describe(api, png: bytes) -> str:
    """Muse Spark's description of one picture, as in scripts/plato_telephone_run.py (an empty answer is asked again)."""
    msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": meta_api.image_data_url(png)}},
                                        {"type": "text", "text": T.DESCRIBE_PROMPT}]}]
    for _ in range(3):
        resp = meta_api.retry_network(lambda: api.chat(msg, reasoning_effort=T.REASONING_EFFORT),
                                       tries=3, base=2.0)
        out = (resp.choices[0].message.content or "").strip()
        if out:
            return out
    raise RuntimeError("empty description")


def _draw(api, description: str) -> bytes:
    for _ in range(2):
        imgs = meta_api.retry_network(lambda: api.generate_images(T.image_prompt(description), n=1),
                                       tries=3, base=2.0)
        if imgs:
            return imgs[0]
    raise RuntimeError("no picture")


def _events(api, png: bytes, rounds: int):
    yield {"type": "start", "rounds": rounds}
    for k in range(1, rounds + 1):
        text = _describe(api, png)
        png = _draw(api, text)
        yield {"type": "round", "n": k, "description": text, "image": _small(png)}
    yield {"type": "done"}


@router.post("/api/plato/telephone/play", include_in_schema=False)
async def play(request: Request):
    api = own_key.api_for(request)
    if api is None:
        raise HTTPException(403, NO_KEY_MSG)
    usage = "Send JSON: {\"image\": a data URL, \"rounds\": 1 to 6}."
    try:
        body = await request.json()
    except ValueError:
        raise _bad(usage)
    if not isinstance(body, dict):
        raise _bad(usage)
    rounds = body.get("rounds", DEFAULT_ROUNDS)
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= MAX_ROUNDS:
        raise _bad(f"rounds must be a whole number from 1 to {MAX_ROUNDS}.")
    image = body.get("image")
    png = _prepare(image if isinstance(image, str) else "")
    ip = client_ip(request)
    if _games.count(ip) >= GAMES_A_DAY:
        raise HTTPException(429, f"That is today's limit: {GAMES_A_DAY} games of telephone per visitor per day.")
    _games.take(ip)

    def stream():
        try:
            for ev in _events(api, png, rounds):
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except (openai.OpenAIError, httpx.HTTPError) as e:  # its type only: nothing of the key reaches the log or page
            log.warning("telephone: Meta API error on a visitor's own key: %s", type(e).__name__)
            yield json.dumps({"type": "error", "message": own_key.OWN_KEY_ERROR.format(kind=type(e).__name__)}) + "\n"
        except Exception as e:
            log.warning("telephone failed: %s", type(e).__name__)
            yield json.dumps({"type": "error", "message": f"Something went wrong ({type(e).__name__})."}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

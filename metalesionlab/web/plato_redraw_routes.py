"""Draw it again, live (/api/plato/redraw): Muse Image draws 8 new pictures of a thing, now, with the experiment's own
prompt, and the server measures them the way the experiment did (ink crop, Meta's DINOv2, cosine distances) against
the published numbers: are the new ones as alike as the published 16, and as close to Muse's usual one?

Roger (Nov 2): it answers "were these cherry-picked?" in front of the visitor. One free try per address a day on the
demo's budget (TIPPA_REDRAW_FREE_PER_DAY, default 1); with a visitor's own Meta API key (web/own_key.py) up to
TIPPA_REDRAW_OWN_PER_DAY (default 20), billed to them. The guard's "redraw" rule adds a per-minute limit and, for the
demo's budget, the daily dollar cap. Nothing is stored: the pictures go back in the response as small WebP images.
"""
from __future__ import annotations

import base64
import io
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import httpx
import numpy as np
import openai
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from PIL import Image
from pydantic import BaseModel, Field

from metalesionlab import draw, meta_api
from metalesionlab.plato import BY_KEY, ink_crop, prompt_for
from metalesionlab.web import agent_routes, own_key
from metalesionlab.web import app as web
from metalesionlab.web import draw_routes
from metalesionlab.web.limits import client_ip

log = logging.getLogger(__name__)
router = APIRouter()

N, PER_CALL = 8, 4  # two calls of 4, side by side, as the experiment drew its pictures in batches of 4
SHOW_SIDE = 256
TAG = "redraw"
free_tries = agent_routes._Counter()
own_tries = agent_routes._Counter()


def free_per_day() -> int:
    return int(os.environ.get("TIPPA_REDRAW_FREE_PER_DAY", "1"))


def own_per_day() -> int:
    return int(os.environ.get("TIPPA_REDRAW_OWN_PER_DAY", "20"))


def keys() -> list[str]:
    """Things the Draw page can measure (it has Muse Image's and people's reference vectors) and the experiment drew."""
    ref = draw_routes.reference()
    return [k for k, e in ref.entries.items() if "ai_loo" in e and k in BY_KEY]


def webp_url(png: bytes) -> str:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    img.thumbnail((SHOW_SIDE, SHOW_SIDE))
    out = io.BytesIO()
    img.save(out, "WEBP", quality=82)
    return "data:image/webp;base64," + base64.b64encode(out.getvalue()).decode()


def embed_all(pictures: list[Image.Image]) -> np.ndarray:
    if not draw_routes.slots.acquire(timeout=draw_routes.WAIT_S):
        raise HTTPException(503, "Lots of people are drawing right now. Please try again in a few seconds.",
                            headers={"Retry-After": "5"})
    try:
        return np.asarray(draw_routes.embedder.get()(pictures), dtype=np.float64)
    finally:
        draw_routes.slots.release()


def redraw(key: str, api) -> dict:
    prompt = prompt_for(BY_KEY[key], "doodle")
    with ThreadPoolExecutor(2) as pool:
        batches = list(pool.map(lambda _: api.generate_images(prompt, n=PER_CALL, ledger_tag=TAG), range(N // PER_CALL)))
    pngs = [p for b in batches for p in b][:N]
    if len(pngs) < 2:
        raise HTTPException(502, "Muse Image didn't return enough pictures. Please try again.")
    vecs = draw.unit(embed_all([ink_crop(Image.open(io.BytesIO(p)).convert("RGB")) for p in pngs]))
    concept = draw_routes.reference().concept(key)
    stats = draw_routes.reference().entries[key]["stats"]
    d = 1.0 - vecs @ vecs.T
    new_spread = float(d[np.triu_indices(len(vecs), 1)].mean())
    d_ai = 1.0 - vecs @ draw.unit(concept.ai_centroid)  # each new picture's distance from Muse's usual one
    people = np.asarray(concept.human_to_ai, float)     # people's drawings' distances from it
    return {
        "key": key, "label": draw_routes.reference().entries[key].get("label", key), "n": len(pngs), "prompt": prompt,
        "images": [webp_url(p) for p in pngs],
        "new_spread": round(new_spread, 4), "ai_spread": stats["ai_spread"], "human_spread": stats["human_spread"],
        "new_median_from_usual": round(float(np.median(d_ai)), 4),
        "people_median_from_usual": round(float(np.median(people)), 4),
        "people_farther_pct": round(float(100 * np.mean(people > np.median(d_ai))), 1),
    }


class Ask(BaseModel):
    key: str = Field(..., max_length=30)


@router.get("/api/plato/redraw/status")
def redraw_status(request: Request):
    mine = own_key.key_of(request.headers) is not None
    ip = client_ip(request)
    left = own_per_day() - own_tries.count(ip) if mine else free_per_day() - free_tries.count(ip)
    return {"enabled": mine or web.api_key_present(), "keys": keys(), "n": N, "own_key": mine,
            "tries_left_today": max(0, left), "cost_usd": round(N * meta_api.IMAGE_PRICE, 2)}


@router.post("/api/plato/redraw")
async def redraw_route(body: Ask, request: Request):
    """Muse Image draws N new pictures of `key` now, measured against the published numbers. Paid: about 8 cents."""
    key = (body.key or "").strip().lower()
    if key == "boat":
        key = "sailboat"  # the chair page's "boat" is the sailboat everyone drew (Quick, Draw! has no boat)
    if key not in keys():
        raise HTTPException(422, "Draw it again works for: " + ", ".join(keys()) + ".")
    ip = client_ip(request)
    mine = own_key.api_for(request)
    counter, cap = (own_tries, own_per_day()) if mine is not None else (free_tries, free_per_day())
    if counter.count(ip) >= cap:
        raise HTTPException(429, (f"That's your {cap} tries for today with your own key." if mine is not None else
                                  "That's today's free try. Add your own Meta API key (More → Use your own API key) "
                                  "to draw again as often as you like."))
    if mine is None and not web.api_key_present():
        raise HTTPException(503, "Draw it again needs the Meta Model API, which isn't set up on this server.")
    counter.take(ip)
    try:
        return await run_in_threadpool(redraw, key, mine or web.get_api())
    except meta_api.BudgetExceeded:
        raise HTTPException(503, "Today's budget for the live demo is used up. Add your own Meta API key "
                                 "(More → Use your own API key) to draw again now.") from None
    except (openai.OpenAIError, httpx.HTTPError) as e:
        if mine is not None:
            log.warning("redraw: Meta API error on a visitor's own key: %s", type(e).__name__)
            raise HTTPException(502, own_key.OWN_KEY_ERROR.format(kind=type(e).__name__)) from None
        log.warning("redraw: Meta API error: %s", e)
        raise HTTPException(502, f"Muse Image returned an error ({type(e).__name__}). Please try again in a minute.") from None

"""The damage zoo (/plato/zoo): how other open image models fall apart when damaged.

Open image models (Stable Diffusion 1.5 and XL, PixArt-Σ, Sana and others) drew a chair, God and four other things
while a growing share of their artificial neurons was switched off, in the part that reads the words or the part that
draws. Each model's damage runs from intact to where its pictures stop meaning anything, chosen by eye per model and
part, in 11 steps (scripts/damage_zoo.py; for fun, not pre-registered). The page replays the finished runs and makes
no API calls: it reads web/data/damage_zoo.json and one strip of 11 pictures per model, part and thing in
static/img/zoo/. It belongs to Damaged AI (site.DAMAGED_PAGES, a card in damaged_routes.CARDS); app.py includes this
router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "damage_zoo.json"
_cache: dict = {}


def load_data(path: Path | None = None) -> dict | None:
    """The page's data, cached until the file changes; None if missing, unreadable or not the right shape."""
    path = path or DATA
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return None
    hit = _cache.get(path)
    if hit and hit[0] == stamp:
        return hit[1]
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not (isinstance(data, dict) and isinstance(data.get("models"), list) and isinstance(data.get("things"), dict)):
        return None
    _cache[path] = (stamp, data)
    return data


@router.get("/plato/zoo", include_in_schema=False)
def zoo_page():
    return FileResponse(HERE / "pages" / "plato_zoo.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/zoo")
def zoo_data():
    """The models (name, maker, what reads the words, license, the 11 damage steps of each part, a caption per part),
    the things and the prompt. Pictures: /static/img/zoo/<model>-<part>-<thing>.webp, 11 frames side by side."""
    data = load_data()
    if data is None:
        raise HTTPException(503, "The damage zoo isn't on this server yet.")
    return data

"""Plato's Chair, damaged (/plato/damage): what an image model draws when its language part or its
drawing part is damaged, and what a damaged Glimmer reads in a chair.

The page reads one small file of statistics shipped with the app (web/data/plato_damage.json, written
by scripts/plato_damage_web.py from the data folder, which lives outside the repository) and the
precomputed slider pictures in static/img/plato_damage/. No Meta API calls. app.py includes this
router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "plato_damage.json"
_cache: dict = {}


def load_data(path: Path = DATA) -> dict | None:
    """The page's statistics, cached until the file changes; None if missing or unreadable."""
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
    if not isinstance(data, dict):
        return None
    _cache[path] = (stamp, data)
    return data


@router.get("/plato/damage", include_in_schema=False)
def plato_damage_page():
    return FileResponse(HERE / "pages" / "plato_damage.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/damage")
def plato_damage_data():
    """Statistics for the damage page: slider pictures, the dissociation, prototype drift, clocks and
    the damaged-Glimmer arm. Derived numbers only."""
    data = load_data()
    if data is None:
        raise HTTPException(503, "The damage experiment's statistics aren't on this server yet.")
    return data

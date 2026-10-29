"""Prisoners of the cave (a section of /plato/scale): does a model that has seen pictures draw a better chair than
its text-only twin?

The section replays a finished experiment (docs/plato_cave_twins.md) and makes no API calls. It reads the derived
statistics in public_data/plato_twins.json (written by scripts/plato_twins_analyze.py --public) and the twin walls
in static/img/plato_twins/ (sprites and wall.json, written by scripts/plato_twins_figures.py --web).
app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from metalesionlab import meta_api
from metalesionlab.web import app as web

router = APIRouter()

DATA = meta_api.REPO_ROOT / "public_data" / "plato_twins.json"
WALL = web.HERE / "static" / "img" / "plato_twins" / "wall.json"
_cache: dict = {}


def load(path: Path | None = None) -> dict | None:
    """A JSON file, cached until it changes; None if it's missing or unreadable."""
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
    _cache[path] = (stamp, data)
    return data


def usable(d, w) -> bool:
    return (isinstance(d, dict) and isinstance(d.get("rows"), list) and isinstance(d.get("predictions"), dict)
            and isinstance(w, dict) and isinstance(w.get("walls"), dict) and bool(w["walls"].get("chair")))


@router.get("/api/plato/twins")
def twins_data():
    """Each twin's results on the three requests (drawn chairs, drawn clocks, a described chair), the paired
    differences with bootstrap CIs, the pre-registered verdicts, one quoted sentence per model, and the walls'
    layout (which tile is which twin's drawing or failure)."""
    d, w = load(), load(WALL)
    if not usable(d, w):
        raise HTTPException(503, "The 'Prisoners of the cave' results aren't on this server yet.")
    return {**d, "wall": w}

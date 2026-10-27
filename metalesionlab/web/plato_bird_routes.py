"""Plato's Bird (/plato/bird): "name one member of the category bird", Muse Spark and Muse Glimmer against
people's first answers in the Banks & Connell (2023) category production norms (CC BY 4.0).

The page reads the derived statistics in public_data/plato_bird.json (written by
scripts/plato_bird_analyze.py --public) and picture strips in static/img/plato_bird/. No Meta API calls;
the "You vs. the AI" mini-game runs in the browser and stores nothing. app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab import meta_api
from metalesionlab.web import app as web

router = APIRouter()

DATA = meta_api.REPO_ROOT / "public_data" / "plato_bird.json"
_cache: dict = {}


def load(path: Path | None = None) -> dict | None:
    """The statistics file, cached until it changes; None if it's missing or unreadable."""
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


@router.get("/plato/bird", include_in_schema=False)
def plato_bird_page():
    return FileResponse(web.HERE / "pages" / "plato_bird.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/bird")
def plato_bird_data():
    """Per-category answer statistics (people, Muse Spark, Muse Glimmer), the 117-category summary and the
    picture comparison for the Plato's Bird page."""
    data = load()
    if not isinstance(data, dict):
        raise HTTPException(503, "The Plato's Bird statistics aren't on this server yet.")
    return data

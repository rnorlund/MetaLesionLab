"""Plato's Cave (/plato/cave): name the shadow.

The page replays a finished experiment (docs/plato_cave.md) and makes no Meta API calls. It reads the
statistics shipped with the app, web/data/plato_cave.json (written by scripts/plato_cave_web_export.py from
the data folder, which lives outside the repository), and pictures in static/img/plato_cave/. The
"Name the shadow" game runs in the visitor's browser and stores nothing. app.py includes this router with
one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab.web import app as web

router = APIRouter()

DATA = web.HERE / "data" / "plato_cave.json"
_cache: dict = {}


def _load(path: Path):
    """JSON from disk, cached until the file changes; None if it's missing or unreadable."""
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


def usable(d) -> bool:
    return (isinstance(d, dict) and isinstance(d.get("accuracy"), dict) and isinstance(d.get("game"), list)
            and bool(d["game"]))


@router.get("/plato/cave", include_in_schema=False)
def cave_page():
    return FileResponse(web.HERE / "pages" / "plato_cave.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/cave")
def cave_data():
    """Statistics for the Plato's Cave page: naming accuracy by version (original, outline, silhouette,
    cast shadow), what the AI said for the game's 12 shadows, error types, the word lens and the
    comparison with people's published silhouette norms."""
    d = _load(DATA)
    if not usable(d):
        raise HTTPException(503, "The Plato's Cave results aren't on this server yet.")
    return d

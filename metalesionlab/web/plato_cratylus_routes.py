"""Plato's Cratylus (/plato/cratylus): does an AI that never heard a word still draw "kiki" spiky?

The page replays a finished experiment (docs/plato_cratylus.md) and makes no Meta API calls. It reads the
statistics shipped with the app, web/data/plato_cratylus.json (written by scripts/plato_cratylus_web_export.py
from the data folder outside the repository), and pictures in static/img/plato_cratylus/. The
visitor's own bouba/kiki choice stays in the browser. app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab.web import app as web

router = APIRouter()

DATA = web.HERE / "data" / "plato_cratylus.json"
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
    return isinstance(d, dict) and isinstance(d.get("words"), list) and isinstance(d.get("choice"), dict) \
        and bool(d["words"])


@router.get("/plato/cratylus", include_in_schema=False)
def cratylus_page():
    return FileResponse(web.HERE / "pages" / "plato_cratylus.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/cratylus")
def cratylus_data():
    """Statistics for the Plato's Cratylus page: roundness of Muse Image's drawings for each made-up word,
    the pre-registered contrasts with CIs, and the choice arm (Glimmer, Spark) next to people's published
    rates."""
    d = _load(DATA)
    if not usable(d):
        raise HTTPException(503, "The Plato's Cratylus results aren't on this server yet.")
    return d

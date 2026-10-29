"""The clock test (/plato/clock): would an AI pass the clock-drawing item of the MoCA?

The page replays a finished, pre-registered run (docs/plato_clock_plan.md, docs/plato_clock.md) and makes no Meta API
calls. It reads one file of derived results shipped with the app, web/data/plato_clock.json, written by
scripts/plato_clock.py: Muse Image's clocks and their scores, and the people's side, which comes only from the private
analysis's public export (group averages of at least 20 adults and aggregate numbers; nothing per person). The draw
pad's clock (/draw?thing=clock) is served by draw_routes.py. app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab.web import app as web

router = APIRouter()

DATA = web.HERE / "data" / "plato_clock.json"
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
    """The parts the page can't do without: Muse's clocks and the people's averages."""
    return (isinstance(d, dict) and isinstance(d.get("muse"), dict) and bool(d["muse"].get("clocks"))
            and isinstance(d.get("people"), dict) and bool(d["people"].get("decades")))


@router.get("/plato/clock", include_in_schema=False)
def plato_clock_page():
    return FileResponse(web.HERE / "pages" / "plato_clock.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/clock")
def plato_clock_data():
    """Muse Image's clocks for the MoCA instruction (eye and Muse Spark scores, the time drawn), the age personas,
    the SVG clocks, /plato/damage's SDXL clocks with their checklist score, and the people's group averages and
    aggregate numbers. Derived results only."""
    d = _load(DATA)
    if not usable(d):
        raise HTTPException(503, "The clock test's results aren't on this server yet.")
    return d

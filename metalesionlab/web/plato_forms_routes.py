"""Plato's Forms (/plato/forms): what time an AI draws on a clock, and Plato's own bed and table.

The page replays two finished experiments (docs/plato_forms.md) and makes no Meta API calls. It reads
one small file of derived statistics shipped with the app, web/data/plato_forms.json, written by
scripts/plato_forms_export.py from the data folder (which lives outside the repository), and the
pictures in static/img/plato_forms/. app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab.web import app as web

router = APIRouter()

DATA = web.HERE / "data" / "plato_forms.json"
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
    """The parts the page can't do without: the clock groups and the bed/table block."""
    return (isinstance(d, dict) and isinstance(d.get("clock"), dict) and isinstance(d["clock"].get("groups"), dict)
            and bool(d["clock"]["groups"]) and isinstance(d.get("concepts"), dict))


@router.get("/plato/forms", include_in_schema=False)
def plato_forms_page():
    return FileResponse(web.HERE / "pages" / "plato_forms.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/forms")
def plato_forms_data():
    """The Platonic clock (share of clocks at about 10:10 for Muse Image, SDXL and people; time accuracy
    when a time is asked; every read time) and Plato's bed and table (spread against people, with
    their ranks among the 35 Plato's Chair concepts). Derived statistics only."""
    d = _load(DATA)
    if not usable(d):
        raise HTTPException(503, "The Plato's Forms results aren't on this server yet.")
    return d

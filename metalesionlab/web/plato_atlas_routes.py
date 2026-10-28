"""The Atlas of Forms (/plato/atlas): Plato's Chair for 135 everyday things, and a benchmark for any image model.

The page replays a finished experiment (docs/plato_atlas.md) and makes no Meta API calls. It reads the
statistics shipped with the app, web/data/plato_atlas.json (written by scripts/plato_atlas_web_export.py from
the data folder, which lives outside the repository), and the small WebP Forms and thumbnails in
static/img/plato_atlas/. app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab.web import app as web

router = APIRouter()

DATA = web.HERE / "data" / "plato_atlas.json"
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
    return (isinstance(d, dict) and isinstance(d.get("summary"), dict) and isinstance(d.get("concepts"), list)
            and bool(d["concepts"]))


@router.get("/plato/atlas", include_in_schema=False)
def atlas_page():
    return FileResponse(web.HERE / "pages" / "plato_atlas.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/atlas")
def atlas_data():
    """Statistics for the Atlas of Forms page: per concept the Muse/people spread ratio with its CI, rank,
    SDXL's ratio, word frequency and picture names; the summary, the pre-registered tests and the
    exploratory predictors."""
    d = _load(DATA)
    if not usable(d):
        raise HTTPException(503, "The Atlas of Forms results aren't on this server yet.")
    return d

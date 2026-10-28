"""An AI growing up (/plato/scale): does an AI's idea of a chair change with more data and with a bigger model?

The page replays a finished experiment (docs/plato_scale.md) and makes no Meta API calls. It reads the derived
statistics in public_data/plato_scale.json (written by scripts/plato_scale_analyze.py --public) and the walls of
chairs in static/img/plato_scale/ (sprites and wall.json, written by scripts/plato_scale_figures.py --web).
app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab import meta_api
from metalesionlab.web import app as web

router = APIRouter()

DATA = meta_api.REPO_ROOT / "public_data" / "plato_scale.json"
WALL = web.HERE / "static" / "img" / "plato_scale" / "wall.json"
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
    return (isinstance(d, dict) and isinstance(d.get("arm_b"), dict) and isinstance(d.get("arm_a"), dict)
            and isinstance(w, dict) and isinstance(w.get("models"), list) and bool(w["models"]))


@router.get("/plato/scale", include_in_schema=False)
def scale_page():
    return FileResponse(web.HERE / "pages" / "plato_scale.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/scale")
def scale_data():
    """Both arms' statistics (per model and per data size, with bootstrap CIs), the pre-registered verdicts, and the
    layout of the two walls (which tile is which model's drawing or failure)."""
    d, w = load(), load(WALL)
    if not usable(d, w):
        raise HTTPException(503, "The 'An AI growing up' results aren't on this server yet.")
    return {**d, "wall": w}

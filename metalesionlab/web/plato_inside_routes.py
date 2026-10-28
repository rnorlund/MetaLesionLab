"""Inside the model (/plato/inside): Muse Image's doodles and people's doodles of a thing, layer by layer inside
Meta's open model Muse Glimmer 30B. Muse's collapse to one point by the naming layers; people's stay spread out.

The page reads one file of derived statistics shipped with the app (web/data/plato_inside.json, written by
scripts/plato_inside_web_export.py from the data folder, which lives outside the repository): per thing and
layer, a precomputed 2-D map of the pictures, each source's spread, the collapse layer and the word-lens layer.
The thumbnails are sprites in static/img/plato_inside/. No Meta API calls. app.py includes this router with one
line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "plato_inside.json"
_cache: dict = {}


def load_data(path: Path | None = None) -> dict | None:
    """The page's statistics, cached until the file changes; None if missing, unreadable or not the right shape."""
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
    if not (isinstance(data, dict) and isinstance(data.get("concepts"), list) and data["concepts"]):
        return None
    _cache[path] = (stamp, data)
    return data


@router.get("/plato/inside", include_in_schema=False)
def plato_inside_page():
    return FileResponse(HERE / "pages" / "plato_inside.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/inside")
def plato_inside_data():
    """Per thing and layer: the map positions of Muse Image's and people's doodles inside Muse Glimmer 30B, how
    spread out each source is, where Muse's doodles collapse and where the word lens reads the name."""
    data = load_data()
    if data is None:
        raise HTTPException(503, "The inside-the-model statistics aren't on this server yet.")
    return data

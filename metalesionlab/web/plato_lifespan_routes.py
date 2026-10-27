"""The life of a chair (/plato/lifespan): do children growing up, and an image model being trained, converge on
the same chair? Plato's Meno: learning is recollecting the Forms.

The page reads the group-level statistics in public_data/plato_lifespan.json (written by
scripts/plato_lifespan_analyze.py --public) and picture strips in static/img/plato_lifespan/ (Quick, Draw!
drawings, Muse Image and Stable Diffusion pictures, and the sketch model's drawings; never a child's drawing).
No Meta API calls. app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab import meta_api
from metalesionlab.web import app as web

router = APIRouter()

DATA = meta_api.REPO_ROOT / "public_data" / "plato_lifespan.json"
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


@router.get("/plato/lifespan", include_in_schema=False)
def plato_lifespan_page():
    return FileResponse(web.HERE / "pages" / "plato_lifespan.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/lifespan")
def plato_lifespan_data():
    """Children's drawings by age (group-level), Stable Diffusion's five training stages, adults, Muse Image and a
    sketch model trained from scratch: recognizability, distance to the adult and Muse prototypes, and spread."""
    data = load()
    if not isinstance(data, dict):
        raise HTTPException(503, "The life-of-a-chair statistics aren't on this server yet.")
    return data

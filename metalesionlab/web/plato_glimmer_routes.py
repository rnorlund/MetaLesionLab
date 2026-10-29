"""Damage Meta's open AI: what does it forget first? (/plato/glimmer)

We switched off a share of Muse Glimmer 30B's artificial neurons, step by step, and asked it to draw a chair, a clock
and God (as drawing code) and to describe each in one sentence (docs/plato_glimmer_lesion.md). The page replays the
finished experiment and makes no API calls. It reads one small file of derived numbers and short sentences
(web/data/plato_glimmer.json, written by scripts/plato_glimmer_lesion_analyze.py web) and the drawings' sprites in
static/img/plato_glimmer/. It belongs to Damaged AI (site.DAMAGED_PAGES, a card in damaged_routes.CARDS); app.py
includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "plato_glimmer.json"
_cache: dict = {}


def load_data(path: Path | None = None) -> dict | None:
    """The page's numbers, cached until the file changes; None if missing, unreadable or not the right shape."""
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
    if not (isinstance(data, dict) and isinstance(data.get("conditions"), dict) and isinstance(data.get("damage"), list)):
        return None
    _cache[path] = (stamp, data)
    return data


@router.get("/plato/glimmer", include_in_schema=False)
def glimmer_page():
    return FileResponse(HERE / "pages" / "plato_glimmer.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/glimmer")
def glimmer_data():
    """Per damage step and thing: how many of 12 drawings were drawn and named correctly by an AI reader, how many
    descriptions were correct and well formed; the word-against-picture verdicts; and the sprite layout."""
    data = load_data()
    if data is None:
        raise HTTPException(503, "The damaged-Glimmer results aren't on this server yet.")
    return data

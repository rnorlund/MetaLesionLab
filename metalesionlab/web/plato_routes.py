"""Plato's Chair (/plato): Muse Image's 16 chairs next to 16 people's, and what Glimmer does with them.

The page reads one small file of statistics shipped with the app (web/data/plato.json, written by
scripts/plato_web_export.py from the data folder, which lives outside the repository) and figures in
static/img/plato/. The comparison with a second image model (SDXL) was still running when the page was
built, so the route prefers a newer results_sdxl.json in $PLATO_DIR when that folder exists. No Meta
API calls. app.py includes this router with one line.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab import plato_web
from metalesionlab.web import app as web

router = APIRouter()

DATA = web.HERE / "data" / "plato.json"
# Same default as metalesionlab/plato.py, which this module doesn't import (it needs numpy and PIL).
PLATO_DIR = Path(os.environ.get("PLATO_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/core"))

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


def live_sdxl(n_total: int) -> dict | None:
    """The SDXL comparison from the data folder, if this machine has it: results_sdxl.json, or SDXL
    fields inside results.json."""
    for name in ("results_sdxl.json", "results.json"):
        block = plato_web.sdxl_block(_load(PLATO_DIR / name), n_total)
        if block:
            return {**block, "source": "data folder"}
    return None


@router.get("/plato", include_in_schema=False)
def plato_page():
    return FileResponse(web.HERE / "pages" / "plato.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato")
def plato_data():
    """Statistics for the Plato's Chair page: spread of AI vs. human drawings per concept, six prompt
    languages, inside Muse Glimmer, and the second-image-model comparison (null while it's running)."""
    data = _load(DATA)
    if not isinstance(data, dict):
        raise HTTPException(503, "The Plato's Chair statistics aren't on this server yet.")
    out = dict(data)
    n_total = (data.get("core") or {}).get("n_concepts") or 35
    out["sdxl"] = live_sdxl(n_total) or ({**data["sdxl"], "source": "shipped"} if data.get("sdxl") else None)
    return out

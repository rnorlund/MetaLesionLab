"""Does damage hurt a second language first? (/lab/bilingual)

The controlled bilingual lesion test (docs/bilingual.md) ran on a GPU; this page replays it and makes no
Meta API calls. It reads the compact copy shipped with the app, web/data/bilingual.json, written by
scripts/bilingual_web_export.py from runs/bilingual/results.json (runs/ isn't in the repository).
app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab.web import app as web

router = APIRouter()

SHIPPED = web.HERE / "data" / "bilingual.json"
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
    """The parts the page can't do without."""
    return (isinstance(d, dict) and isinstance(d.get("summary"), dict) and isinstance(d.get("switching"), dict)
            and isinstance(d.get("dose"), list) and isinstance(d.get("lens"), dict) and bool(d["summary"]))


def report() -> dict:
    d = _load(SHIPPED)
    if not usable(d):
        raise HTTPException(503, "The bilingual test results aren't on this server yet.")
    return d


@router.get("/lab/bilingual", include_in_schema=False)
def bilingual_page():
    return FileResponse(web.HERE / "pages" / "bilingual.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/lab/bilingual")
def bilingual_results():
    """Same pictures and the same damage in English, Spanish, French and Portuguese: the extra accuracy
    lost per language, how often damaged answers fall back to English, dose-response with 95% CIs, and
    the intact word lens (the English name leads before the asked-for word)."""
    return report()

"""Plato's Telephone (/plato/telephone): Muse Spark describes a drawing, Muse Image draws the description, and so on
for 10 generations. What survives, and does every chain end at the textbook chair?

The page replays a finished experiment (docs/plato_telephone.md) and makes no Meta API calls. It reads the derived
statistics and Muse Spark's descriptions in public_data/plato_telephone.json (written by
scripts/plato_telephone_analyze.py --public) and the chains' filmstrips in static/img/plato_telephone/ (written by
scripts/plato_telephone_figures.py --web). Plato is quoted only from public_data/plato_passages.json: the API adds
the passages named in PASSAGES, word for word. app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab import meta_api
from metalesionlab.web import app as web

router = APIRouter()

DATA = meta_api.REPO_ROOT / "public_data" / "plato_telephone.json"
PASSAGE_FILE = meta_api.REPO_ROOT / "public_data" / "plato_passages.json"
PASSAGES = ["republic-597b", "republic-598b"]  # Republic X: three beds; the painter's copy of an appearance
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


def passages() -> list[dict]:
    d = load(PASSAGE_FILE) or {}
    by = {p["id"]: p for p in d.get("passages", [])}
    return [{k: by[i][k] for k in ("id", "work", "book", "stephanus", "speaker", "text", "translation", "source_url")
             if k in by[i]} for i in PASSAGES if i in by]


def usable(d) -> bool:
    return (isinstance(d, dict) and isinstance(d.get("chains"), list) and bool(d["chains"])
            and isinstance(d.get("curves"), dict) and isinstance(d.get("tests"), dict))


@router.get("/plato/telephone", include_in_schema=False)
def telephone_page():
    return FileResponse(web.HERE / "pages" / "plato_telephone.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/telephone")
def telephone_data():
    """The 30 chains (Muse Spark's descriptions, distance to Muse's default picture at every generation), the
    group curves with bootstrap CIs, the pre-registered tests, and the Plato passages the page quotes."""
    d = load()
    if not usable(d):
        raise HTTPException(503, "The Plato's Telephone results aren't on this server yet.")
    return {**d, "passages": passages()}

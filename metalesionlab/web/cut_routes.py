"""What can I cut? (/lab/cut): which of Muse Glimmer's 52 layers can go while your own tests still pass.

The results come from a GPU run (scripts/what_can_i_cut.py) and are replayed here: the page needs no
GPU and makes no Meta API calls. The route prefers TOT_DATA_DIR/compress/glimmer.json (the run's own
file) and falls back to the compact copy shipped with the app (web/data/cut_glimmer.json, written by
scripts/cut_web_export.py), since runs/ isn't in the repository. app.py includes this router with one line.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab.web import app as web

router = APIRouter()

SHIPPED = web.HERE / "data" / "cut_glimmer.json"
_cache: dict = {}


def _load(path: Path):
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


def _usable(d) -> bool:
    return isinstance(d, dict) and isinstance(d.get("layers"), list) and isinstance(d.get("greedy"), list) and "intact" in d


def report() -> dict:
    run, shipped = _load(web.DATA_DIR / "compress" / "glimmer.json"), _load(SHIPPED)
    if _usable(run):
        # The run's file has no per-answer lists; borrow the shipped ones when they describe the same cuts.
        same = _usable(shipped) and [c.get("removed") for c in shipped.get("pruned", [])] == [c.get("removed") for c in run.get("pruned", [])]
        return {**run, "answers_lost": run.get("answers_lost") or (shipped.get("answers_lost") if same else None),
                "source": "run"}
    if _usable(shipped):
        return {**shipped, "source": "shipped"}
    raise HTTPException(503, "The layer-removal results aren't on this server yet.")


@router.get("/lab/cut", include_in_schema=False)
def cut_page():
    return FileResponse(web.HERE / "pages" / "cut.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/lab/cut")
def cut_results():
    """Every layer skipped alone, the greedy removal path with both guards and the held-out check,
    and the cuts deleted for real with their measured size, memory and speed."""
    return report()

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

from metalesionlab import meta_api, plato_web
from metalesionlab.web import app as web

router = APIRouter()

DATA = web.HERE / "data" / "plato.json"
# The re-measurement with three other vision models (docs/plato_robustness.md): derived statistics only.
ROBUST = meta_api.REPO_ROOT / "public_data" / "plato_robustness.json"
ROBUST_DOC = "https://github.com/rnorlund/MetaLesionLab/blob/main/docs/plato_robustness.md"
EMBEDDERS = {"dinov2_base": "DINOv2-base", "dinov2_large": "DINOv2-large", "pe_core_l14": "PE-Core",
             "siglip2_so400m": "SigLIP 2"}  # short names; the page's own model first
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


def robustness() -> dict | None:
    """"Does it depend on DINOv2?": for each vision model, the median Muse/people ratio over the 35 things with
    its 95% CI, how many things Muse Image draws more alike than people, and where the reference's most and least
    uniform things rank. None when public_data/plato_robustness.json is missing."""
    d = _load(ROBUST)
    if not isinstance(d, dict):
        return None
    summary, names, concepts = d.get("summary") or {}, d.get("embedders") or {}, d.get("concepts") or {}

    def order(key):
        return [c["label"] for c in sorted(concepts.get(key) or [], key=lambda c: c["index"])]
    ref = order(next(iter(EMBEDDERS)))
    first, last = (ref[0], ref[-1]) if ref else (None, None)
    rows = []
    for key in EMBEDDERS:
        s = summary.get(key)
        if not s:
            continue
        o = order(key)
        rows.append({"key": key, "name": (names.get(key) or {}).get("name", key), "short": EMBEDDERS[key],
                     "maker": (names.get(key) or {}).get("maker"),
                     "median": s["index_median"], "ci95": s["index_median_ci95"], "below_1": s["concepts_below_1"],
                     "n": s["n_concepts"], "rho_vs_reference": s.get("rho_index_vs_reference"),
                     "rank_first": o.index(first) + 1 if first in o else None,
                     "rank_last": o.index(last) + 1 if last in o else None})
    return {"rows": rows, "first": first, "last": last, "doc": ROBUST_DOC} if rows else None


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
    out["robustness"] = robustness()
    return out

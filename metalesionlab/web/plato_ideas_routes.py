"""The invisible Forms (/plato/ideas): Muse Image asked to draw God, beauty, justice, the Good, love, time, death,
the soul, freedom, happiness and truth, 16 times each.

The page replays a finished experiment (docs/plato_ideas.md) and makes no Meta API calls. It reads the statistics
shipped with the app, web/data/plato_ideas.json (written by scripts/plato_ideas_web_export.py from the data folder,
which lives outside the repository), and the small WebP sprites in static/img/plato_ideas/. There are no people's
drawings of these ideas, so every number on the page is about the AI. app.py includes this router with one line.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from metalesionlab.web import app as web
from metalesionlab.web.plato_atlas_routes import _load

router = APIRouter()

DATA = web.HERE / "data" / "plato_ideas.json"


def usable(d) -> bool:
    return (isinstance(d, dict) and isinstance(d.get("summary"), dict) and isinstance(d.get("ideas"), list)
            and bool(d["ideas"]))


@router.get("/plato/ideas", include_in_schema=False)
def ideas_page():
    return FileResponse(web.HERE / "pages" / "plato_ideas.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/ideas")
def ideas_data():
    """Statistics for The invisible Forms: per idea Muse's emblem counts (Muse Glimmer's labels and the check by
    eye), its spread with a 95% CI and the sprite; the pre-registered tests; the things' spreads for comparison."""
    d = _load(DATA)
    if not usable(d):
        raise HTTPException(503, "The invisible Forms results aren't on this server yet.")
    return d

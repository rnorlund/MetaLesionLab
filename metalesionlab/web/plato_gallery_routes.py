"""The gallery (/plato/gallery): the most striking pictures from the Plato's Chair experiments, with a caption and
a link back to each experiment, and the data for the "From the lab" strip that site.py adds to every Plato page.

The items are curated by hand in data/gallery.json (captions, links, alt text); their pictures are WebP files in
static/img/gallery/ written by scripts/plato_gallery_export.py (the Draw page's damage strips reuse that page's
own frames). The page makes no Meta API calls. app.py includes this router with one line.

GET /api/plato/gallery returns the items whose pictures are all on this server, each with the pixel size of its
card picture (so cards keep their shape while loading). A sequence's card picture is a sprite: its frames side by
side in equal cells.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "gallery.json"
STATIC = HERE / "static"
CATEGORIES = ["Watch it degrade", "One ideal version", "Shadows", "Words and shapes", "Growing up"]

router = APIRouter()
_cache: dict = {}


def _static_file(url: str) -> Path | None:
    if not isinstance(url, str) or not url.startswith("/static/"):
        return None
    path = (STATIC / url[len("/static/"):]).resolve()
    return path if path.is_relative_to(STATIC.resolve()) and path.is_file() else None


def pictures(item: dict) -> list[str]:
    """Every picture an item shows: its card picture, its large picture and every frame (and pair panel)."""
    urls = [item.get("thumb"), item.get("image")]
    for f in (item.get("sequence") or {}).get("frames", []):
        urls += [f.get("src"), f.get("pair")]
    return [u for u in urls if u]


def _size(url: str) -> list[int] | None:
    path = _static_file(url)
    if not path:
        return None
    key = (path, path.stat().st_mtime_ns)
    if key not in _cache:
        with Image.open(path) as im:
            _cache[key] = list(im.size)
    return _cache[key]


def load(path: Path | None = None) -> dict | None:
    """The gallery, keeping only items whose pictures are all here; None if the file is missing or unreadable."""
    try:
        data = json.loads((path or DATA).read_text())
    except (OSError, ValueError):
        return None
    items = []
    for item in data.get("items", []):
        if item.get("category") not in CATEGORIES or not all(_static_file(u) for u in pictures(item)):
            continue
        items.append({**item, "thumb_size": _size(item["thumb"])})
    return {"categories": [c for c in CATEGORIES if any(i["category"] == c for i in items)],
            "credits": data.get("credits", []), "items": items}


# "From the lab": the band site.py adds to every Plato page but the gallery itself, after the page's content and
# before its footer. gallery-strip.js fills it from /api/plato/gallery and keeps it hidden if that fails.
STRIP = (
    '<section class="lab-strip" id="lab-strip" aria-labelledby="lab-strip-h" hidden>'
    '<div class="lab-strip-head"><div><h2 id="lab-strip-h">From the lab</h2>'
    '<p class="lab-strip-sub">Pictures our experiments made, many of an AI’s drawings falling apart. '
    'Open one for the story.</p></div>'
    '<div class="lab-strip-ctrl">'
    '<button type="button" class="lab-btn" data-lab-step="-1" aria-label="Previous pictures">'
    '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M7 1L3 5l4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></button>'
    '<button type="button" class="lab-btn" data-lab-step="1" aria-label="Next pictures">'
    '<svg viewBox="0 0 10 10" aria-hidden="true"><path d="M3 1l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></button>'
    '<button type="button" class="lab-btn" data-lab-pause aria-pressed="false"><span>Pause</span></button>'
    '<a class="lab-all" href="/plato/gallery">See all in the gallery</a></div></div>'
    '<div class="lab-strip-track"></div></section>'
    '<script src="/static/js/gallery-strip.js" defer></script>'
)
STRIP_CSS = '<link rel="stylesheet" href="/static/css/gallery-strip.css">'


def add_strip(page: str) -> str:
    """The band after the page's content (its last </main>, else the end of <body>), and its stylesheet."""
    at = page.rfind("</main>")
    at = at + len("</main>") if at >= 0 else page.rfind("</body>")
    if at < 0 or 'id="lab-strip"' in page:
        return page
    page = page[:at] + STRIP + page[at:]
    head = page.find("</head>")
    return page[:head] + STRIP_CSS + page[head:] if head >= 0 else page


@router.get("/plato/gallery", include_in_schema=False)
def gallery_page():
    return FileResponse(HERE / "pages" / "plato_gallery.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/gallery")
def gallery_data():
    """The gallery's items (title, caption, category, link, pictures, alt text, credit, optional sequence)."""
    d = load()
    if not d or not d["items"]:
        raise HTTPException(503, "The gallery isn't on this server yet.")
    return JSONResponse(d, headers={"Cache-Control": "public, max-age=300"})  # every Plato page's band asks for it

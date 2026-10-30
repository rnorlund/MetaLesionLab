"""Damaged AI (/damaged): the hub of the damage experiments, the site's second focus after Plato's question.

The first screen asks what happens to an AI's idea of a thing when the AI is damaged, and leads with the damage to
Meta's own open AI, Muse Glimmer: its drawings go before its words. It shows one chair and one clock at each step of
damage (static/img/plato_glimmer/steps, no God), answers in one sentence and draws two numbers (/api/plato/glimmer,
FirstLook.glimmer). A second section (#sdxl) shows Stable Diffusion XL, because Meta's Muse Image runs only on Meta's
servers: the rocking chair that damage to its language part turns into a car, with three numbers from
/api/plato/damage and /api/plato/ideas. All of it is drawn by static/js/plato_damaged.js with FirstLook
(plato_firstlook.js), the same code that draws /plato/damage's first screen. Below it, one card per damage result (CARDS), each opening its section; a card shows only when the app
serves its page. The cards' pictures are made from pictures the site already ships (scripts/plato_hub_thumbs.py).

No API calls. app.py includes this router with one line; the nav's "Damaged AI" button (site.py) appears once it is
served, and the damage experiments' pages (site.DAMAGED_PAGES) mark it as the current page.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from metalesionlab.web import site

router = APIRouter()

PAGE = Path(__file__).resolve().parent / "pages" / "damaged.html"

# One card per damage result, in the order a visitor meets them: the question, a one-line answer, and the section it
# opens. The picture is static/img/plato/hub/<slug>.webp (site.render_hub). No card shows any AI's God, so the blind
# "Draw God" on /draw stays blind: the ideas card shows death.
CARDS = [
    {"slug": "damaged-glimmer-draws", "path": "/plato/glimmer", "title": "What a damaged AI forgets first",
     "question": "Does a damaged AI lose the drawing or the words first?",
     "answer": "The drawing goes first: it stops drawing recognisable pictures before it stops describing, early or late."},
    {"slug": "damaged-painter", "path": "/plato/damage", "title": "Damage the painter",
     "question": "What happens to a drawing when we damage the AI that draws it?",
     "answer": "Words damage: a wheelchair becomes a bicycle. Drawing damage: it breaks up."},
    {"slug": "damaged-ideas", "path": "/plato/ideas#damage", "title": "God, death and other ideas under damage",
     "question": "What happens to an AI’s idea of death when we damage it?",
     "answer": "Words damage turns skulls into people, and God into an ordinary person."},
    {"slug": "damaged-clocks", "path": "/plato/damage#clock-h", "title": "Clocks under damage",
     "question": "Can a damaged AI still draw a clock?",
     "answer": "Drawing damage loses the numbers first; words damage loses the whole clock."},
    {"slug": "damaged-glimmer", "path": "/plato/damage#glim-h", "title": "Damage the AI that looks",
     "question": "What does a damaged AI that names pictures call a throne?",
     "answer": "“A plain, ordinary chair.” Random damage does the same."},
    {"slug": "damaged-janus", "path": "/plato/damage#janus-h", "title": "One model that draws and reads",
     "question": "Can one damage break an AI’s drawing and its reading at once?",
     "answer": "Yes: in Janus-Pro, an open AI from DeepSeek, reading fails first."},
    {"slug": "damaged-forget", "path": "/plato/lifespan#forget", "title": "Watch an AI forget what a chair is",
     "question": "What happens to a sketch AI’s chairs as we switch off its artificial neurons?",
     "answer": "Switch off a tenth and chairs fall apart, details first."},
    {"slug": "damaged-yourself", "path": "/draw", "title": "Damage it yourself",
     "question": "What would damage do to the thing you draw?",
     "answer": "Draw anything, then watch a damaged image AI draw it too."},
]
MARK = "<!--#damaged:hub-->"


def cards(app) -> list[dict]:
    """The cards whose pages the app serves."""
    return [c for c in CARDS if site.has_page(app, c["path"])]


@router.get("/damaged", include_in_schema=False)
def damaged_page(request: Request):
    page = PAGE.read_text(encoding="utf-8").replace(MARK, site.render_hub(cards(request.app)))
    return HTMLResponse(page, headers={"Cache-Control": "no-cache"})

"""Damaged AI (/damaged): the hub of the damage experiments, the site's second focus after Plato's question.

The first screen asks what happens to an AI's idea of a thing when the AI is damaged. It shows the rocking chair that
damage to the language part of Stable Diffusion XL turns into a car, answers in one sentence and draws three numbers.
Every picture and number on it comes from the experiments' own statistics (/api/plato/damage and /api/plato/ideas),
drawn by static/js/plato_damaged.js with FirstLook (plato_firstlook.js), the same code that draws /plato/damage's
first screen. Below it, one card per damage result (CARDS), each opening its section; a card shows only when the app
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
# opens. The picture is static/img/plato/hub/<slug>.webp (site.render_hub). The God card shows Stable Diffusion XL's
# God, as the gallery does, never Muse Image's.
CARDS = [
    {"slug": "damaged-painter", "path": "/plato/damage", "title": "Damage the painter",
     "question": "What happens to a drawing when we damage the AI that draws it?",
     "answer": "Damage the part that reads the words: a wheelchair becomes a bicycle. Damage the part that paints the picture: it breaks up."},
    {"slug": "damaged-god", "path": "/plato/ideas#damage", "title": "God under damage",
     "question": "What happens to God when we damage the AI drawing him?",
     "answer": "Damage the part that reads the words and God loses his beard or halo first, then becomes an ordinary person."},
    {"slug": "damaged-clocks", "path": "/plato/damage#clock-h", "title": "Clocks under damage",
     "question": "Can a damaged AI still draw a clock?",
     "answer": "Damage the part that paints the picture and the numbers go first. Damage the part that reads the words and the clock goes."},
    {"slug": "damaged-glimmer", "path": "/plato/damage#glim-h", "title": "Damage the AI that looks",
     "question": "What does a damaged AI that names pictures call a throne?",
     "answer": "“A plain, ordinary chair.” But switching off random neurons has the same effect."},
    {"slug": "damaged-janus", "path": "/plato/damage#janus-h", "title": "One model that draws and reads",
     "question": "Can one damage break an AI’s drawing and its reading at once?",
     "answer": "Yes, in Janus-Pro, an open AI from DeepSeek that reads and draws. Reading fails first; its wheelchair becomes a car."},
    {"slug": "damaged-yourself", "path": "/draw", "title": "Damage it yourself",
     "question": "What would damage do to the thing you draw?",
     "answer": "Draw anything, then watch an open image AI draw it too, with each of its parts damaged in turn."},
]
MARK = "<!--#damaged:hub-->"


def cards(app) -> list[dict]:
    """The cards whose pages the app serves."""
    return [c for c in CARDS if site.has_page(app, c["path"])]


@router.get("/damaged", include_in_schema=False)
def damaged_page(request: Request):
    page = PAGE.read_text(encoding="utf-8").replace(MARK, site.render_hub(cards(request.app)))
    return HTMLResponse(page, headers={"Cache-Control": "no-cache"})

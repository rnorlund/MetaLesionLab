"""Take-homes (/takehomes): the three most powerful messages of Plato's Chair, each as one picture.

1. Muse Image draws one chair; people draw many (the 16 + 16 chairs, with a stack toggle).
2. Damage the part that reads words and a rocking chair becomes a car (seven steps, dense tiles).
3. Ask Meta's AI to draw God: covered until the visitor has drawn (draw pad's sessionStorage "seen" flag) or chooses
   "Show me now", so /draw stays a blind draw.

The page makes no Meta API calls. Its numbers come from the shipped data files (plato.json, plato_ideas.json) and are
filled into the page here, so nothing is typed twice. app.py includes this router with one line.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from metalesionlab.web import app as web

router = APIRouter()

# the 7 steps of rocking chair to car (indices into static/img/plato_damage/dense/rocking_N.webp; N = noise x (N+1)/10)
STEPS = (0, 1, 3, 5, 6, 7, 9)


def numbers() -> dict:
    """The few numbers the page shows, read from the data files."""
    hero = json.loads((web.HERE / "data" / "plato.json").read_text())["hero"]
    chair = next(h for h in hero if h["key"] == "chair")
    ideas = json.loads((web.HERE / "data" / "plato_ideas.json").read_text())["ideas"]
    god = next(i for i in ideas if i["key"] == "god")
    return {"ai": f'{chair["ai_spread"]:.2f}', "people": f'{chair["human_spread"]:.2f}', "n": str(chair["n"]),
            "god_top": str(god["top"]["n"]), "god_n": str(god["n"]), "sprite": god["sprite"]}


def damage_row() -> str:
    out = []
    for k, i in enumerate(STEPS):
        label = "undamaged" if i == 0 else f"noise × {(i + 1) / 10:g}"
        what = "a rocking chair, undamaged" if i == 0 else f"the words part damaged, {label}"
        out.append(f'<li><span class="th-tile"><img src="/static/img/plato_damage/dense/rocking_{i}.webp" width="320" height="320" '
                   f'alt="Step {k + 1} of {len(STEPS)}: {what}" loading="lazy"></span><span class="th-lbl">{label}</span></li>')
    return "".join(out)


def god_cells(n: int, cols: int) -> str:
    return "".join(f'<span style="--c:{i % cols};--r:{i // cols}"></span>' for i in range(n))


@router.get("/takehomes", include_in_schema=False)
def takehomes_page():
    d = numbers()
    html = (web.HERE / "pages" / "takehomes.html").read_text()
    sprite = d["sprite"]
    for k, v in {"TH_AI": d["ai"], "TH_PEOPLE": d["people"], "TH_N": d["n"], "TH_GOD_TOP": d["god_top"], "TH_GOD_N": d["god_n"],
                 "TH_SPRITE": sprite["src"], "TH_COLS": str(sprite["cols"]), "TH_ROWS": str(-(-sprite["n"] // sprite["cols"])),
                 "TH_ROW": damage_row(), "TH_GOD_CELLS": god_cells(sprite["n"], sprite["cols"])}.items():
        html = html.replace("{{" + k + "}}", v)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

"""Take-homes (/takehomes): the three most powerful messages of Plato's Chair, each as one picture.

1. Muse Image draws one chair; people draw many (the 16 + 16 chairs, with a stack toggle).
2. Damage Meta's open AI, Muse Glimmer, and its drawings go before its words: one chair at each of six steps of damage,
   with the drawings an AI reader could still name and the descriptions still right, pooled over a chair, a clock and God
   (numbers computed from data/plato_glimmer.json; the pictures are static/img/plato_glimmer/steps, no God).
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

STEP_LABELS = ("undamaged", "5% off", "10% off", "15% off", "20% off", "30% off")  # share of Glimmer's neurons switched off


def numbers() -> dict:
    """The few numbers the page shows, read from the data files."""
    hero = json.loads((web.HERE / "data" / "plato.json").read_text())["hero"]
    chair = next(h for h in hero if h["key"] == "chair")
    ideas = json.loads((web.HERE / "data" / "plato_ideas.json").read_text())["ideas"]
    god = next(i for i in ideas if i["key"] == "god")
    return {"ai": f'{chair["ai_spread"]:.2f}', "people": f'{chair["human_spread"]:.2f}', "n": str(chair["n"]),
            "god_top": str(god["top"]["n"]), "god_n": str(god["n"]), "sprite": god["sprite"]}


def glimmer_steps() -> list[dict]:
    """Per damage step (least first) of Muse Glimmer's "all" damage: drawings named and descriptions right, pooled over the
    things, out of the answers at that step. Read from the data file, never typed."""
    data = json.loads((web.HERE / "data" / "plato_glimmer.json").read_text())
    out = []
    for step in data["damage"][0]["steps"]:
        cells = list(data["conditions"][step["cond"]].values())
        out.append({"cond": step["cond"], "named": sum(c["named"] for c in cells), "right": sum(c["correct"] for c in cells),
                    "n": sum(c["n"] for c in cells)})
    return out


def glimmer_row(steps: list[dict]) -> str:
    """One column per step, least damage at the left: the chair, the step label and two thin bars."""
    assert len(steps) == len(STEP_LABELS), "STEP_LABELS must name every step of the experiment"
    out = []
    for i, (st, label) in enumerate(zip(steps, STEP_LABELS)):
        what = "undamaged" if i == 0 else f"with {label.split()[0]} of its neurons switched off"
        vals = "".join(
            f'<span class="th-val {cls}"><span class="th-val-l">{name}</span><b>{st[key]} of {st["n"]}</b>'
            f'<span class="th-bar"><i style="width:{100 * st[key] / st["n"]:.1f}%"></i></span></span>'
            for cls, name, key in (("named", "named", "named"), ("right", "right", "right")))
        out.append(f'<li><span class="th-tile"><img src="/static/img/plato_glimmer/steps/chair_{i}.webp" width="300" height="300" '
                   f'alt="Muse Glimmer’s chair, {what}" loading="lazy"></span><span class="th-lbl">{label}</span>{vals}</li>')
    return "".join(out)


def god_cells(n: int, cols: int) -> str:
    return "".join(f'<span style="--c:{i % cols};--r:{i // cols}"></span>' for i in range(n))


@router.get("/takehomes", include_in_schema=False)
def takehomes_page():
    d = numbers()
    gs = glimmer_steps()
    fifth = gs[4]  # a fifth of the neurons off
    html = (web.HERE / "pages" / "takehomes.html").read_text()
    sprite = d["sprite"]
    for k, v in {"TH_AI": d["ai"], "TH_PEOPLE": d["people"], "TH_N": d["n"], "TH_GOD_TOP": d["god_top"], "TH_GOD_N": d["god_n"],
                 "TH_SPRITE": sprite["src"], "TH_COLS": str(sprite["cols"]), "TH_ROWS": str(-(-sprite["n"] // sprite["cols"])),
                 "TH_ROW": glimmer_row(gs), "TH_G_RIGHT": str(fifth["right"]), "TH_G_NAMED": str(fifth["named"]), "TH_G_N": str(fifth["n"]), "TH_GOD_CELLS": god_cells(sprite["n"], sprite["cols"])}.items():
        html = html.replace("{{" + k + "}}", v)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

"""Take-homes (/takehomes): the three most powerful messages of Plato's Chair, each as one picture.

1. Muse Image draws one chair; people draw many (the 16 + 16 chairs, with a stack toggle).
2. Copy a copy and the idea gets lost: a beanbag drawn, described and redrawn ten times becomes a croissant, then a
   window (seven of the eleven telephone pictures, left to right).
3. Written words lose what you meant: "I never said she stole my money" in seven stresses (playable), the transcripts
   a text-only AI receives, and the two scores (Meta's AI from the words, a simple program from the sound), all read
   from the Seven meanings data file (plato_phaedrus.json) and its audio route.

The page makes no Meta API calls. Its numbers come from the shipped data files and are filled into the page here,
so nothing is typed twice. app.py includes this router with one line.
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from metalesionlab.web import app as web

router = APIRouter()

# the telephone pictures shown (static/img/gallery/telephone-beanbag-N.webp), start at the left, with a plain alt text
COPIES = ((0, "a beanbag chair"), (2, "a croissant"), (3, "a thin, curved croissant shape"),
          (5, "a curved shape with spokes, like a fan"), (7, "a fan shape with spokes"),
          (8, "a half-round fan window, dark at the rim"), (10, "a half-round fan window with a grid arch"))


def numbers() -> dict:
    """The few numbers the page shows, read from the data files."""
    hero = json.loads((web.HERE / "data" / "plato.json").read_text())["hero"]
    chair = next(h for h in hero if h["key"] == "chair")
    return {"ai": f'{chair["ai_spread"]:.2f}', "people": f'{chair["human_spread"]:.2f}', "n": str(chair["n"])}


def copies_row() -> str:
    out = []
    for i, what in COPIES:
        label = "start" if i == 0 else f"copy {i}"
        alt = f"Start: {what}" if i == 0 else f"Copy {i} of 10: {what}"
        out.append(f'<li><span class="th-tile"><img src="/static/img/gallery/telephone-beanbag-{i}.webp" width="400" height="400" '
                   f'alt="{alt}" loading="lazy"></span><span class="th-lbl">{label}</span></li>')
    return "".join(out)


def meaning() -> dict:
    """The Seven meanings picture's parts, from plato_phaedrus.json (its first voice, which /plato/phaedrus plays first)."""
    d = json.loads((web.HERE / "data" / "plato_phaedrus.json").read_text())
    words, clips = d["words"], d["voices"][0]["clips"]
    says, wrote = [], []
    for k, c in enumerate(clips):
        shown = " ".join(f"<b>{w.upper()}</b>" if i == k else w for i, w in enumerate(words)) + "."
        label = "Play: " + " ".join(w.upper() if i == k else w for i, w in enumerate(words)) + "."
        says.append(f'<li><button type="button" class="th-play" data-src="{c["src"]}" aria-pressed="false" aria-label="{label}">'
                    f'<span class="th-ico" aria-hidden="true"></span></button><span class="th-say">{shown}</span></li>')
        wrote.append(f'<li>{c["transcript"].lower().rstrip(".")}</li>')
    spark, reader = d["spark"]["transcript"], d["reader"]
    n, guess = reader["n"], 1 / len(words)

    def bar(label: str, k: int, cls: str) -> str:
        return (f'<div class="th-bar {cls}"><p>{label}: <b>{k} of {n}</b></p><div class="th-track">'
                f'<i style="width:{100 * k / n:.1f}%"></i><u style="left:{100 * guess:.1f}%"><span>guessing: 1 in {len(words)}</span></u></div></div>')
    bars = bar("Meta’s AI, reading the words", spark["k"], "ai") + bar("A simple program, listening to the sound", reader["k"], "sound")
    return {"says": "".join(says), "wrote": "".join(wrote), "bars": bars, "spark_k": str(spark["k"]),
            "reader_k": str(reader["k"]), "n91": str(n)}


@router.get("/takehomes", include_in_schema=False)
def takehomes_page():
    d, m = numbers(), meaning()
    html = (web.HERE / "pages" / "takehomes.html").read_text()
    for k, v in {"TH_AI": d["ai"], "TH_PEOPLE": d["people"], "TH_N": d["n"], "TH_COPIES": copies_row(), "TH_SAYS": m["says"],
                 "TH_WROTE": m["wrote"], "TH_BARS": m["bars"], "TH_SPARK_K": m["spark_k"], "TH_READER_K": m["reader_k"],
                 "TH_N91": m["n91"]}.items():
        html = html.replace("{{" + k + "}}", v)
    return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

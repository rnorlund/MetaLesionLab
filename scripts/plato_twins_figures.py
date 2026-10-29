"""Prisoners of the cave: the twin walls and the page's sprites (docs/plato_cave_twins.md).

Usage: python -I scripts/plato_twins_figures.py [--web]

Reads $PLATO_TWINS_DIR/results.json, render.json, reader.json and png/. Writes to $PLATO_TWINS_DIR/figures/:
  wall_chairs.png  each twin's 12 chairs at temperature 1, text-only twin above its vision twin, 7B then 32B
  wall_clocks.png  the same for "a clock showing 10 past 11"
With --web also the page's sprites and wall.json in metalesionlab/web/static/img/plato_twins/ (the drawings as
masks, so they follow the light and dark themes, plus which tiles failed and which the reader named correctly).
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from metalesionlab import plato_scale as ps  # noqa: E402
from metalesionlab import plato_twins as pt  # noqa: E402
from metalesionlab.plato import ink_crop  # noqa: E402

D = pt.TWINS_DIR
FIG = D / "figures"
WEB = ROOT / "metalesionlab" / "web" / "static" / "img" / "plato_twins"

_spec = importlib.util.spec_from_file_location("plato_scale_figures", ROOT / "scripts" / "plato_scale_figures.py")
sf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sf)  # the scale experiment's wall and sprite drawing, so the two pages look alike

ARM_TEXT = {"text": "trained on text only", "vision": "also trained on pictures"}


def rows_for(task: str, res: dict) -> list:
    rend = json.loads((D / "render.json").read_text())
    reader = json.loads((D / "reader.json").read_text())["labels"]
    by = {(r["key"], r["task"], r["temp"]): r for r in res["rows"]}
    out = []
    for size in pt.SIZES:
        for m in pt.PAIRS[size]:
            name = pt.raw_name(m.key, task, pt.PRIMARY_TEMP)
            r = by[(m.key, task, pt.PRIMARY_TEMP)]
            samples = sorted(rend[name]["samples"], key=lambda s: s["i"])
            tiles = [ink_crop(Image.open(D / "png" / f"{name}_{s['i']}.png").convert("RGB")).convert("L")
                     if s["reason"] is None else ps.FAILURE_LABELS[s["reason"]] for s in samples]
            concept = pt.TASKS[task].concept
            out.append({"key": m.key, "group": f"{size} twins", "label": f"{m.label}",
                        "lines": [ARM_TEXT[m.arm], f"read as a {concept}: {r['read_as']} of 12",
                                  f"valid drawings: {r['valid']} of 12"],
                        "tiles": tiles, "size": size, "arm": m.arm,
                        "read": [reader[name].get(str(s["i"])) == concept for s in samples],
                        "fail": [None if s["reason"] is None else ps.FAILURE_LABELS[s["reason"]] for s in samples],
                        "read_as": r["read_as"], "valid": r["valid"]})
    return out


def web(chairs: list, clocks: list):
    WEB.mkdir(parents=True, exist_ok=True)
    sf.sprite(chairs, WEB / "wall_chair.webp")
    sf.sprite(clocks, WEB / "wall_clock.webp")
    out = {"cols": pt.N, "tile": sf.TILE,
           "about": "Tiles: ink-cropped renders of each twin's own answers at temperature 1, in answer order; a "
                    "failure has no drawing. read = the SigLIP 2 reader named it the asked-for thing.",
           "walls": {task: [{"key": r["key"], "size": r["size"], "arm": r["arm"], "row": k, "tiles": r["fail"],
                             "read": r["read"]} for k, r in enumerate(rows)]
                     for task, rows in (("chair", chairs), ("clock", clocks))}}
    (WEB / "wall.json").write_text(json.dumps(out, separators=(",", ":")))
    print("wrote", WEB / "wall.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", action="store_true")
    args = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.loads((D / "results.json").read_text())
    chairs, clocks = rows_for("chair", res), rows_for("clock", res)
    sf.wall(chairs, "Prisoners of the cave: chairs", "“Draw a simple chair as an SVG drawing …” · text only, no "
            "picture given · 12 answers per twin, temperature 1 · ink-cropped renders", FIG / "wall_chairs.png",
            label_w=330)
    sf.wall(clocks, "Prisoners of the cave: clocks", "“Draw a clock showing 10 past 11 as an SVG drawing …” · 12 "
            "answers per twin, temperature 1 · ink-cropped renders", FIG / "wall_clocks.png", label_w=330)
    if args.web:
        web(chairs, clocks)


if __name__ == "__main__":
    main()

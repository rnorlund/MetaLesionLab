"""Damage Meta's open AI: draw every answer's SVG code as a web browser shows it (docs/plato_glimmer_lesion_plan.md).

The house renderer (cairosvg, plato_scale.classify) is strict XML: one typo in the boilerplate, such as a repeated
width="256" or a misspelt namespace address, and nothing is drawn. Damage makes such typos common, while the drawing
itself may be fine. A web browser forgives them when the SVG sits inside a page. So, besides the strict "valid code"
measure, every answer's first <svg>...</svg> is put inline in a blank page, drawn by headless Chromium at its own size
on a 256 x 256 white box, and saved as a grayscale PNG. JavaScript is off and every network request is refused.

Runs with the system python3 (Playwright lives there), not the project venv:
  python3 scripts/plato_glimmer_lesion_browser.py --run raw      (or --run pilot)
Writes png_browser/<run>/<cond>/<thing>_<i>.png and <run>_browser.json (ink share, or why nothing was drawn).
"""
import argparse
import io
import json
import os
import re
from pathlib import Path

import numpy as np
from PIL import Image

D = Path(os.environ.get("PLATO_GLIMMER_LESION_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/glimmer_lesion"))
SVG = re.compile(r"<svg\b.*?</svg\s*>", re.I | re.S)  # as plato_scale.extract_svg
SIDE, INK_LEVEL, BLANK_BELOW, FLOODED_ABOVE = 256, 200, 0.001, 0.95  # as plato_scale
MAX_BYTES = 200_000
PAGE = ("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;background:#fff}"
        "#box{width:256px;height:256px;overflow:hidden;background:#fff;position:relative}</style></head>"
        "<body><div id='box'>{svg}</div></body></html>")


def main():
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="raw", choices=["raw", "pilot"])
    args = ap.parse_args()
    out_json = D / f"{args.run}_browser.json"
    res = json.loads(out_json.read_text()) if out_json.exists() else {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(java_script_enabled=False, viewport={"width": 300, "height": 300})
        ctx.route("**/*", lambda route: route.abort())  # set_content needs no request; images and fonts by URL fail
        page = ctx.new_page()
        for f in sorted((D / args.run).glob("*.json")):
            cond = f.stem
            if cond in res:
                continue
            rec = json.loads(f.read_text())
            res[cond] = {}
            for thing, v in rec["things"].items():
                rows = []
                for s in v["draw"]:
                    m = SVG.search(s["text"] or "")
                    row = {"i": s["i"]}
                    if not m:
                        row.update(reason="no_svg", ink=None)
                    elif len(m.group(0).encode()) > MAX_BYTES:
                        row.update(reason="too_big", ink=None)
                    else:
                        page.set_content(PAGE.replace("{svg}", m.group(0)), wait_until="load", timeout=10_000)
                        png = page.locator("#box").screenshot(timeout=10_000)
                        img = Image.open(io.BytesIO(png)).convert("L").resize((SIDE, SIDE))
                        ink = float((np.asarray(img) < INK_LEVEL).mean())
                        reason = "blank" if ink < BLANK_BELOW else "flooded" if ink > FLOODED_ABOVE else None
                        row.update(reason=reason, ink=round(ink, 5))
                        path = D / "png_browser" / args.run / cond / f"{thing}_{s['i']}.png"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        img.save(path)
                    rows.append(row)
                res[cond][thing] = rows
            drew = {t: sum(r["reason"] is None for r in rows) for t, rows in res[cond].items()}
            print(f"{cond:14s} drew {drew}", flush=True)
            out_json.write_text(json.dumps(res, indent=1))
        browser.close()


if __name__ == "__main__":
    main()

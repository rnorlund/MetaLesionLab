"""An AI growing up: the standalone animation mockup (one HTML file, assets embedded, under 3 MB).

Usage: python -I scripts/plato_scale_animation.py --out <dir>/index.html

The stages follow fixed rules (docs/plato_scale.md, "The animation"), so nothing is picked by eye:
- More data: the sketch model at 100, 1,000 and 20,000 chairs; seed 1's first 6 drawings (noise indices 0-5) at the
  last step, temperature 1, as strokes in the order the model drew them.
- A bigger brain: Qwen2.5 0.5B, 1.5B, 7B, 14B and 32B; each model's first 6 answers at temperature 1, rendered,
  failures labelled.
- Meta's models: Muse Glimmer 30B, then Muse Spark 1.3 and Muse Wonder 1.0 (API, size undisclosed), the same way.
Numbers in the captions come from $PLATO_SCALE_DIR/results.json.
"""
import argparse
import base64
import io
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from metalesionlab import plato_scale as ps  # noqa: E402
from metalesionlab.plato import ink_crop  # noqa: E402
from metalesionlab.plato_sketch import STEPS, sample_name  # noqa: E402

TEMPLATE = Path(__file__).with_name("plato_scale_animation_template.html")
N_TILES = 6
DATA_SIZES = [100, 1000, 20000]
MODEL_KEYS = ["qwen25_0.5b", "qwen25_1.5b", "qwen25_7b", "qwen25_14b", "qwen25_32b"]
META_KEYS = ["glimmer", "spark", "wonder"]
SKETCH_PARAMS_B = 0.00113  # the sketch decoder: LSTM 512 over stroke-5 plus a 20-component mixture head


def png_mask(path: Path, side: int = 112) -> str:
    """Ink as opaque black on transparent, as a data URI (the page masks it with the theme's line colour)."""
    g = ink_crop(Image.open(path).convert("RGB")).convert("L").resize((side, side), Image.LANCZOS)
    alpha = g.point(lambda v: 255 - v)
    im = Image.merge("LA", (Image.new("L", (side, side), 0), alpha))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def strokes_256(drawing) -> list:
    """Quick, Draw! strokes scaled to fit a 256 box with a margin, rounded to whole units."""
    xs = [x for s in drawing for x in s[0]]
    ys = [y for s in drawing for y in s[1]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    sc = 216 / max(x1 - x0, y1 - y0, 1)
    ox, oy = 128 - (x1 - x0) * sc / 2, 128 - (y1 - y0) * sc / 2
    return [[[round(ox + (x - x0) * sc) for x in s[0]], [round(oy + (y - y0) * sc) for y in s[1]]] for s in drawing]


def brain_scale(params_b: float) -> float:
    lo, hi = math.log10(0.5), math.log10(33)
    return round(max(0.24, 0.34 + 0.66 * (math.log10(params_b) - lo) / (hi - lo)), 3)


def build(res: dict, sizes=DATA_SIZES) -> dict:
    by_b = {(r["key"], r["temp"]): r for r in res["arm_b"]["rows"]}
    by_a = {(r["size"], r["checkpoint"], r["temp"]): r for r in res["arm_a"]["rows"]}
    meas = json.loads((ps.SCALE_DIR / "svg" / "measure.json").read_text())
    stages = []
    for size in sizes:
        f = ps.SCALE_DIR / "sketch" / "runs" / ps.run_name_a(size, 1) / "samples" / f"{sample_name(STEPS[-1], 1.0)}.json"
        drawings = json.loads(f.read_text())[:N_TILES]
        r = by_a[(size, "final", 1.0)]
        stages.append({
            "act": "data", "actLabel": "Act 1 · feed it more chairs", "pile": size, "brain": brain_scale(SKETCH_PARAMS_B),
            "ai": "a small sketch model", "aisub": "about 1 million parameters",
            "tiles": [{"strokes": strokes_256(d)} if d else {"fail": "a dot"} for d in drawings],
            "spread": r["spread"]["mean"], "fails": f"{r['recog']['mean']:.0%} look like chairs",
            "blab": f"learned from {size:,} people’s chairs · seed 1 · its first 6 drawings",
            "cap": (f"<b>{size:,} chairs.</b> Recognizable {r['recog']['mean']:.0%}; spread {r['spread']['mean']:.2f}, "
                    f"its teachers’ {r['train_spread']:.2f}."
                    "<cite>A Sketch-RNN-style model trained from scratch on Google Quick, Draw! chairs (3 seeds)</cite>")})
    for key in MODEL_KEYS + META_KEYS:
        m = ps.BY_KEY[key]
        r = by_b[(key, 1.0)]
        name = f"{key}_t1.0"
        samples = sorted(meas[name]["samples"], key=lambda s: s["i"])[:N_TILES]
        tiles = []
        for s in samples:
            if s["reason"] is None:
                tiles.append({"png": png_mask(ps.SCALE_DIR / "svg" / "png" / f"{name}_{s['i']}.png")})
            else:
                tiles.append({"fail": ps.FAILURE_LABELS[s["reason"]]})
        meta = key in META_KEYS
        api = m.kind == "api"
        spread = r["spread_ratio"]
        sp_text = f"spread {spread:.2f}× people’s" if spread is not None else "too few drawings for a spread"
        stages.append({
            "act": "meta" if meta else "model", "actLabel": "Act 3 · Meta’s models" if meta else "Act 2 · give it a bigger brain",
            "pile": 0, "brain": 1.0 if api else brain_scale(m.params_b), "unknown": api,
            "ai": m.label, "aisub": "size undisclosed" if api else f"{m.params_b:.1f}B parameters",
            "tiles": tiles, "spread": r["spread"], "fails": f"failed {r['failed']} of 12",
            "blab": f"“draw a simple chair as SVG” · its first 6 answers, temperature 1",
            "long": key == "wonder",
            "cap": (f"<b>{m.label}.</b> Failed {r['failed']} of 12; {sp_text}."
                    + ("<cite>Meta Model API · Meta doesn’t publish its size</cite>" if api else
                       "<cite>Meta’s open-weights model, 30B</cite>" if key == "glimmer" else
                       "<cite>Qwen2.5-Instruct, Alibaba, Apache-2.0</cite>"))})
    a = res["anchors"]
    return {"stages": stages, "step_ms": 2100, "people_spread": a["people"]["spread_n12"],
            "muse_spread": a["muse_image"]["spread"], "bar_max": 0.7}


def timeline(stages: list, step: int) -> tuple[list, int]:
    """The player's schedule (the template's JS does the same): stages every `step` ms from 2.1 s, 0.7 s more at
    each change of act, 0.9 s more on a long stage; the end card 0.3 s after the last."""
    t, at = 2100, []
    for i, st in enumerate(stages):
        if i and stages[i - 1]["act"] != st["act"]:
            t += 700
        at.append(t)
        t += step + (900 if st.get("long") else 0)
    return at, t + 300


def beats(stages: list, at: list, end: int, endline: str) -> str:
    import re

    def plain(html):
        return re.sub(r"<[^>]+>", " ", html).replace("  ", " ").strip()

    items = ['<li><span class="tc">0.0 s</span>“An AI growing up” is lettered by hand, then settles in the corner. '
             'A small brain appears on the ground.</li>']
    for st, t in zip(stages, at):
        cap = st["cap"].split("<cite>")[0]
        src = st["cap"].split("<cite>")[1].split("</cite>")[0] if "<cite>" in st["cap"] else ""
        what = (f"The pile grows to {st['pile']:,} chairs; the brain stays small." if st["act"] == "data" else
                "The brain shows a dashed outline and a question mark: Meta doesn’t publish its size." if st.get("unknown")
                else "The brain grows with the model’s size (log scale).")
        items.append(f'<li><span class="tc">{t / 1000:.1f} s</span>{plain(cap)} {what}'
                     f'<span class="src">Bubble: {st["blab"]}. {src}.</span></li>')
    items.append(f'<li><span class="tc">{end / 1000:.1f} s</span><b>End card.</b> “{plain(endline)}” '
                 'and Replay.</li>')
    return "".join(items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--text", type=Path, required=True, help="JSON with LEDE, ARIA, ENDLINE, ENDCITES, SOURCES, NOTES")
    ap.add_argument("--sizes", type=int, nargs="+", default=DATA_SIZES, help="data sizes for act 1 (a preview only)")
    args = ap.parse_args()
    res = json.loads((ps.SCALE_DIR / "results.json").read_text())
    assets = build(res, args.sizes)
    text = json.loads(args.text.read_text())
    html = TEMPLATE.read_text()
    at, end = timeline(assets["stages"], assets["step_ms"])
    seconds = round(end / 1000)
    text["BEATS"] = beats(assets["stages"], at, end, text["ENDLINE"])
    for k, v in {**text, "SECONDS": str(seconds)}.items():
        html = html.replace(f"__{k}__", v)
    html = html.replace("__ASSETS__", json.dumps(assets, separators=(",", ":")))
    assert "__" not in html.replace("window.__growing", ""), "unfilled placeholder"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)  # the page body: the artifact host wraps it in a document skeleton when published
    preview = args.out.with_name("preview.html")  # the same with a doctype and viewport, for local checks
    preview.write_text('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                       '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + html)
    print(f"wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB, about {seconds} s) and {preview.name}")


if __name__ == "__main__":
    main()

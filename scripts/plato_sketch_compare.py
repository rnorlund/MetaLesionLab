"""Watch an AI learn what a chair is: which model should the animation show? The pilot comparison.

For each candidate (the current small model at its own temperature and at a low one, the larger Sketch-RNN, the
pixel diffusion model, and Magenta's pretrained chair as a ceiling) it measures seed 1's 200 drawings at every
checkpoint the site's way (DINOv2: recognizable among 21 adult prototypes, distance to the adult chair prototype,
spread at matched n = 16) against the chairs that model learned from, renders the 16 animation tiles per
checkpoint, and writes a side-by-side page to choose from.

Usage: python -I scripts/plato_sketch_compare.py --out DIR [--small-low DIR]
Reads $PLATO_LIFESPAN_DIR/sketch/{seeds,big,diffusion,magenta}/ (see the scripts that write them). Writes
DIR/index.html, DIR/frames/<variant>/step<k>.webp and DIR/compare.json (group numbers only).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab.plato import DINO_MODEL, PLATO_DIR, cosine_distances, render_strokes, to_jsonable  # noqa: E402
from metalesionlab.plato_lifespan import CANDIDATES, LIFESPAN_DIR, matched_spread, proto_distances, prototype, recognized  # noqa: E402
from metalesionlab.plato_sketch import BIG, DIFF, N_REF, STEPS, sample_name  # noqa: E402

SK = LIFESPAN_DIR / "sketch"
CELL, GAP, PAPER = 160, 8, "#F7F6F1"


def protos():
    return np.stack([prototype(np.load(PLATO_DIR / "embeddings" / "human" / f"{k}.npz")["cls"].astype(np.float64))
                     for k in CANDIDATES])


def measure(x: np.ndarray, P: np.ndarray, ref_spread: float | None) -> dict:
    ki = CANDIDATES.index("chair")
    row = {"n": int(len(x)), "recog": float(recognized(x, ki, P).mean()),
           "d_adult": float(proto_distances(x, P[ki]).mean()),
           "spread": matched_spread(cosine_distances(x), 16, 200, np.random.default_rng(20261027))}
    if ref_spread is not None:
        row["delta"] = row["spread"] - ref_spread
    return row


def tile_strokes(d) -> Image.Image:
    if not d:
        return Image.new("RGB", (CELL, CELL), "white")
    return render_strokes(d, width=5).resize((CELL, CELL), Image.LANCZOS)


def tile_image(a: np.ndarray) -> Image.Image:
    return Image.fromarray(a).convert("RGB").resize((CELL, CELL), Image.LANCZOS)


def grid(tiles: list) -> Image.Image:
    side = 4 * CELL + 3 * GAP
    im = Image.new("RGB", (side, side), PAPER)
    for i, t in enumerate(tiles[:16]):
        im.paste(t, ((i % 4) * (CELL + GAP), (i // 4) * (CELL + GAP)))
    return im


def embed_drawings(drawings: list, out: Path) -> np.ndarray:
    """Embed (and cache) a set of drawings the site's way, for sets that were not embedded on the GPU."""
    if not out.exists():
        from metalesionlab.plato import Embedder, ink_crop

        kept = [d for d in drawings if d]
        v = Embedder(DINO_MODEL)([ink_crop(render_strokes(d)) for d in kept], batch=50)
        np.savez(out, cls=v["cls"].astype(np.float32), n_empty=len(drawings) - len(kept))
    return np.load(out)["cls"].astype(np.float64)


def variants(small_low: Path | None) -> list[dict]:
    """Each candidate: where its seed-1 drawings and embeddings are, at which steps, and its reference."""
    small = SK / "seeds" / "runs" / "chair_s1"
    big = SK / "big" / "runs" / "big_s1"
    diff = SK / "diffusion" / "runs" / "diff_s1"
    out = [{"key": "small_t1.0", "label": "Current: small Sketch-RNN, temperature 1", "kind": "strokes", "batch": 100,
            "steps": STEPS, "samples": lambda k: small / "samples" / f"{sample_name(k, 1.0)}.json",
            "emb": lambda k: small / "emb" / f"{sample_name(k, 1.0)}.npz", "ref": SK / "seeds" / "ref" / f"chair_train{N_REF}.npz",
            "about": "LSTM 512, 20,000 chairs, 25,600 steps of 100 (as on the site now)."}]
    if small_low:
        t = float(sorted(small_low.glob("samples/step0_t*.json"))[0].stem.split("_t")[1])
        out.append({"key": f"small_t{t:.1f}", "label": f"Current model, temperature {t:.1f}", "kind": "strokes", "batch": 100,
                    "steps": STEPS, "samples": lambda k, t=t: small_low / "samples" / f"{sample_name(k, t)}.json",
                    "emb": lambda k, t=t: small_low / "emb" / f"{sample_name(k, t)}.npz",
                    "ref": SK / "seeds" / "ref" / f"chair_train{N_REF}.npz",
                    "about": f"The same run and weights, sampled more cautiously (temperature {t:.1f}; drawn on a CPU)."})
    steps = [k for k in BIG["steps"] if (big / "emb" / f"{sample_name(k, 1.0)}.npz").exists()]
    if steps:
        for t in (0.4, 0.6, 1.0):
            out.append({"key": f"big_t{t:.1f}", "label": f"Larger Sketch-RNN, temperature {t:.1f}", "kind": "strokes",
                        "batch": 100, "steps": steps, "samples": lambda k, t=t: big / "samples" / f"{sample_name(k, t)}.json",
                        "emb": lambda k, t=t: big / "emb" / f"{sample_name(k, t)}.npz",
                        "ref": SK / "big" / "ref" / f"chair_train{N_REF}.npz",
                        "about": "LSTM 2,048, all 203,324 recognized chairs, 102,400 steps of 100 (about 50 passes), "
                                 "random scaling; 86 min on one L40S."})
    steps = [k for k in DIFF["steps"] if (diff / "emb" / f"step{k}.npz").exists()]
    if steps:
        out.append({"key": "diffusion", "label": f"Pixel diffusion, {DIFF['side']} px", "kind": "images", "batch": DIFF["batch"],
                    "steps": steps, "samples": lambda k: diff / "samples" / f"step{k}.npz",
                    "emb": lambda k: diff / "emb" / f"step{k}.npz",
                    "ref": SK / "diffusion" / "ref" / f"chair_train{N_REF}_{DIFF['side']}px.npz",
                    "about": f"A small UNet (18.5M parameters), all 203,324 chairs rendered as the site renders them, "
                             f"{DIFF['steps'][-1]:,} steps of {DIFF['batch']} (about 32 passes); deterministic DDIM, 50 steps; "
                             "106 min on one L40S. Measured against its training chairs at the same 64 px."})
    for t in (0.4,):
        m = SK / "magenta" / "magenta1024" / "samples" / f"t{t:.1f}.json"
        if m.exists():
            out.append({"key": f"magenta_t{t:.1f}", "label": f"Magenta's pretrained chair, temperature {t:.1f}", "kind": "strokes",
                        "batch": None, "steps": None, "samples": lambda k, m=m: m, "emb": lambda k, m=m: m.with_suffix(".npz"),
                        "ref": SK / "big" / "ref" / f"chair_train{N_REF}.npz",
                        "about": "Ceiling reference: Magenta's published Sketch-RNN chair (LSTM 1,024, 149,600 chairs, "
                                 "4.8 million steps). Its variety is set against 1,000 of all recognized chairs. "
                                 "No training path, so it can't be animated."})
    return out


def load_tiles(v: dict, k) -> list:
    f = v["samples"](k)
    if v["kind"] == "images":
        return [tile_image(a) for a in np.load(f)["images"][:16]]
    return [tile_strokes(d) for d in json.loads(f.read_text())[:16]]


def load_emb(v: dict, k) -> np.ndarray:
    f = v["emb"](k)
    if v["steps"] is None and not f.exists():
        return embed_drawings(json.loads(v["samples"](k).read_text()), f)
    return np.load(f)["cls"].astype(np.float64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--small-low", type=Path)
    ap.add_argument("--note", default="", help="a short recommendation shown at the top of the page")
    args = ap.parse_args()
    P = protos()
    res = {"embedding_model": DINO_MODEL, "note": args.note, "variants": []}
    for v in variants(args.small_low):
        ref = None
        if v["ref"] and v["ref"].exists():
            ref = measure(np.load(v["ref"])["cls"].astype(np.float64), P, None)
        rows, steps = [], v["steps"] or ["final"]
        fdir = args.out / "frames" / v["key"]
        fdir.mkdir(parents=True, exist_ok=True)
        for k in steps:
            x = load_emb(v, k)
            row = {"step": k, **measure(x, P, ref["spread"] if ref else None)} if len(x) >= 16 else {"step": k, "n": int(len(x))}
            if v["batch"] and k != "final":
                row["seen"] = k * v["batch"]
            rows.append(row)
            out = fdir / f"step{k}.webp"
            if not out.exists():
                grid(load_tiles(v, k)).save(out, "WEBP", quality=80, method=6)
        res["variants"].append({k: v[k] for k in ("key", "label", "kind", "about", "batch")} | {"ref": ref, "rows": rows})
        last = rows[-1]
        print(f"{v['key']:14s} final: recog {last.get('recog', float('nan')):.2f} d_adult {last.get('d_adult', float('nan')):.3f} "
              f"spread {last.get('spread', float('nan')):.3f} ref {ref['spread'] if ref else float('nan'):.3f}", flush=True)
    (args.out / "compare.json").write_text(json.dumps(to_jsonable(res), indent=1))
    (args.out / "index.html").write_text(page(res))
    print("wrote", args.out / "index.html")


def page(res: dict) -> str:
    data = json.dumps(to_jsonable(res))
    return PAGE.replace("/*DATA*/", data)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Which chair learner?</title>
<style>
:root { --paper:#F7F6F1; --panel:#FFFFFF; --ink:#111827; --ink2:#374151; --muted:#6B7280; --line:#E1E0D9; --people:#C2410C; --pick:#0D9488;
  --gutter: clamp(16px, 4vw, 96px); --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; --mono: ui-monospace, Menlo, monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --paper:#16171A; --panel:#1F2125; --ink:#F3F4F6; --ink2:#D1D5DB; --muted:#9CA3AF; --line:#34363C; } }
:root[data-theme="dark"] { --paper:#16171A; --panel:#1F2125; --ink:#F3F4F6; --ink2:#D1D5DB; --muted:#9CA3AF; --line:#34363C; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--sans); font-size: clamp(15px, calc(12px + 0.25vw), 19px); line-height: 1.5; }
main { padding: 24px var(--gutter) 64px; display: flex; flex-direction: column; gap: 28px; }
h1 { font-size: clamp(30px, calc(18px + 1.4vw), 56px); margin: 0; letter-spacing: -0.02em; line-height: 1.05; }
h2 { font-size: clamp(22px, calc(15px + 0.7vw), 34px); margin: 8px 0 0; }
p { margin: 0; max-width: 78ch; color: var(--ink2); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 340px), 1fr)); gap: clamp(14px, 1.5vw, 28px); }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: clamp(12px, 1vw, 20px); display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.card h3 { margin: 0; font-size: clamp(17px, calc(13px + 0.35vw), 23px); }
.card .about { font-size: 0.86em; color: var(--muted); }
.card img { width: 100%; height: auto; display: block; border-radius: 8px; background: #fff; }
.nums { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; font-variant-numeric: tabular-nums; }
.nums div { display: flex; flex-direction: column; } .nums span { font-size: 0.78em; color: var(--muted); } .nums b { font-size: 1.15em; }
.step { font-family: var(--mono); font-size: 0.9em; color: var(--ink2); display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.ctl { display: flex; gap: 10px; align-items: center; }
.ctl input { flex: 1; min-width: 0; accent-color: var(--ink); height: 30px; }
button { font: inherit; font-size: 0.9em; padding: 6px 14px; min-height: 36px; border-radius: 8px; border: 1px solid var(--line); background: var(--paper); color: var(--ink); cursor: pointer; }
.scroll { overflow-x: auto; } table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; font-size: 0.92em; }
th, td { padding: 7px 10px; border-bottom: 1px solid var(--line); text-align: right; white-space: nowrap; } th:first-child, td:first-child { text-align: left; white-space: normal; }
th { color: var(--muted); font-weight: 600; }
.note { border-left: 4px solid var(--pick); padding: 6px 0 6px 14px; color: var(--ink); }
.wide { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap: clamp(14px, 1.5vw, 28px); }
</style></head>
<body><main>
<h1>Watch an AI learn what a chair is: which model?</h1>
<p>Each panel is one run (seed 1) drawing the same 16 random starts. The numbers come from all 200 of its drawings at that step, measured as on the site: <b>recognizable</b> (DINOv2: the nearest adult prototype of 21 is the chair's), <b>distance</b> to the adults' average chair (lower is closer), and <b>variety</b> (spread at n = 16), next to the variety of the chairs that model learned from.</p>
<p id="note" class="note" hidden></p>
<h2>The last checkpoint, side by side</h2>
<div class="grid" id="finals"></div>
<h2>Watch each one learn</h2>
<p>Drag a slider or press Play. Same 16 random starts at every step: only the weights change.</p>
<div class="wide" id="players"></div>
<h2>The numbers at the end</h2>
<div class="scroll"><table id="tbl"></table></div>
<p id="foot" style="font-size:0.86em;color:var(--muted)">Drawings: Google Quick, Draw! (CC BY 4.0); the models' own drawings are shown. Sketch-RNN: Ha &amp; Eck (2017); Magenta's chair model is Apache-2.0. Similarity: Meta DINOv2 (Apache-2.0).</p>
</main>
<script>
var D = /*DATA*/;
if (D.note) { var nt = document.getElementById('note'); nt.textContent = D.note; nt.hidden = false; }
function pct(v) { return v == null ? '–' : Math.round(100 * v) + '%'; }
function f3(v) { return v == null ? '–' : v.toFixed(3); }
function sg(v) { return v == null ? '–' : (v < 0 ? '−' : '+') + Math.abs(v).toFixed(3); }
function el(t, a, kids) { var e = document.createElement(t); for (var k in (a || {})) e.setAttribute(k, a[k]); (kids || []).forEach(function (c) { e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); }); return e; }
function nums(r, ref) {
  return el('div', { class: 'nums' }, [
    el('div', null, [el('span', null, ['Recognizable']), el('b', null, [pct(r.recog)])]),
    el('div', null, [el('span', null, ['Distance to adults’ chair']), el('b', null, [f3(r.d_adult)])]),
    el('div', null, [el('span', null, ['Variety' + (ref ? ' (learned from ' + ref.spread.toFixed(3) + ')' : '')]), el('b', null, [f3(r.spread)])])]);
}
function stepTxt(v, r) {
  if (r.step === 'final') return 'Pretrained (final weights)';
  return 'Step ' + r.step.toLocaleString('en-US') + (r.seen != null ? ' · ' + r.seen.toLocaleString('en-US') + ' chairs seen' : '');
}
D.variants.forEach(function (v) {
  var last = v.rows[v.rows.length - 1];
  document.getElementById('finals').appendChild(el('div', { class: 'card' }, [el('h3', null, [v.label]),
    el('img', { src: 'frames/' + v.key + '/step' + last.step + '.webp', alt: '16 chairs: ' + v.label, loading: 'lazy' }),
    nums(last, v.ref), el('div', { class: 'about' }, [v.about])]));
  if (v.rows.length < 2) return;
  var img = el('img', { src: 'frames/' + v.key + '/step' + v.rows[0].step + '.webp', alt: v.label });
  var st = el('div', { class: 'step' }), box = el('div');
  var rng = el('input', { type: 'range', min: 0, max: v.rows.length - 1, value: 0, 'aria-label': 'Training stage: ' + v.label });
  var btn = el('button', { type: 'button' }, ['Play']), timer = null;
  function show(i) { var r = v.rows[i]; img.src = 'frames/' + v.key + '/step' + r.step + '.webp'; rng.value = i;
    st.textContent = stepTxt(v, r); box.innerHTML = ''; box.appendChild(nums(r, v.ref)); }
  function tick() { var i = (+rng.value + 1) % v.rows.length; show(i); timer = setTimeout(tick, i === v.rows.length - 1 ? 2400 : 800); }
  btn.addEventListener('click', function () { if (timer) { clearTimeout(timer); timer = null; btn.textContent = 'Play'; } else { btn.textContent = 'Pause'; tick(); } });
  rng.addEventListener('input', function () { show(+rng.value); });
  v.rows.forEach(function (r) { new Image().src = 'frames/' + v.key + '/step' + r.step + '.webp'; });
  document.getElementById('players').appendChild(el('div', { class: 'card' }, [el('h3', null, [v.label]), img, st, el('div', { class: 'ctl' }, [btn, rng]), box, el('div', { class: 'about' }, [v.about])]));
  show(0);
});
var head = el('tr', null, ['Model', 'Recognizable', 'Distance', 'Variety', 'Learned from', 'Variety − learned from'].map(function (x) { return el('th', null, [x]); }));
var tb = document.getElementById('tbl'); tb.appendChild(el('thead', null, [head]));
var body = el('tbody'); tb.appendChild(body);
D.variants.forEach(function (v) { var r = v.rows[v.rows.length - 1];
  body.appendChild(el('tr', null, [v.label, pct(r.recog), f3(r.d_adult), f3(r.spread), v.ref ? f3(v.ref.spread) : '–', sg(r.delta)].map(function (x) { return el('td', null, [x]); }))); });
</script></body></html>
"""

if __name__ == "__main__":
    main()

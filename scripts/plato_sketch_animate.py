"""Watch an AI learn what a chair is: the time-lapse and the stroke-by-stroke drawing (docs/plato_sketch_plan.md).

Chosen in the plan, before any run: seed 1, temperature 1.0, the first 16 of its 200 drawings (the same noise at
every checkpoint), all 20 checkpoints. Stroke by stroke: at the last step, the first of those 16 that DINOv2
calls a chair.

The larger model (--model big; the plan's addendum) is animated the same way: seed 1 at the temperature fixed in
the addendum (plato_sketch.MODELS), all 24 checkpoints.

Usage: python -I scripts/plato_sketch_animate.py [--model small|big] [--web]
Writes $PLATO_LIFESPAN_DIR/figures/sketch_<dir>_curves.png (the learning path over runs),
$PLATO_LIFESPAN_DIR/sketch[/big]/watch_it_learn.{mp4,gif} and stroke_by_stroke.{mp4,gif}; with --web also
static/img/plato_lifespan/sketch/learn_sprite.webp (the frames of the grid in 4 rows: 5 x 4 for the small model,
6 x 4 for the larger) and stroke_order.json. The page shows whichever model was exported last.
Needs ffmpeg (FFMPEG env var, default: ffmpeg on PATH, then /usr/local/fsl/bin/ffmpeg).
Drawings are the model's own; it learned from Google Quick, Draw! (CC BY 4.0).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from metalesionlab.plato import render_strokes  # noqa: E402
from metalesionlab.plato_lifespan import LIFESPAN_DIR  # noqa: E402
from metalesionlab.plato_sketch import MODELS, log_x, model_run_name, pen_frames, sample_name  # noqa: E402

# Set by main() from --model (plato_sketch.MODELS): "small" is the original plan's model, "big" the addendum's.
MODEL = "small"
ANIM, STEPS = MODELS[MODEL]["anim"], MODELS[MODEL]["steps"]
SEEDS_DIR = LIFESPAN_DIR / "sketch" / "seeds"
OUT = LIFESPAN_DIR / "sketch"
TEXT = {"small": {"sub": ("A small sketch model, trained from scratch on", "20,000 people’s chairs from Quick, Draw!"),
                  "cols": 5, "cell": 200},
        "big": {"sub": ("A sketch model, trained from scratch on", "203,324 people’s chairs from Quick, Draw!"),
                "cols": 6, "cell": 180}}
WEB = ROOT / "metalesionlab" / "web" / "static" / "img" / "plato_lifespan" / "sketch"
PAPER, WHITE, INK, INK2, MUTED, LINE = "#F7F6F1", "#FFFFFF", "#111827", "#374151", "#6B7280", "#E1E0D9"
PEOPLE = "#C2410C"
SPREAD_LO, SPREAD_HI = 0.20, 0.55  # the variety bar's scale
FONT_DIRS = ["/System/Library/Fonts", "/Library/Fonts", "/usr/share/fonts"]


def font(size: int, bold: bool = False, mono: bool = False):
    names = (["SFNSMono.ttf", "Menlo.ttc", "DejaVuSansMono.ttf"] if mono else
             ["SF-Pro-Display-Bold.otf", "HelveticaNeue.ttc", "DejaVuSans-Bold.ttf"] if bold else
             ["SF-Pro-Text-Regular.otf", "SFNS.ttf", "HelveticaNeue.ttc", "DejaVuSans.ttf"])
    for n in names:  # the first name found in any folder wins
        for d in FONT_DIRS:
            for p in Path(d).rglob(n):
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def ffmpeg() -> str:
    for c in (os.environ.get("FFMPEG"), shutil.which("ffmpeg"), "/usr/local/fsl/bin/ffmpeg"):
        if c and Path(c).exists():
            return c
    raise SystemExit("ffmpeg not found; set FFMPEG")


def drawings_at(step: int) -> list:
    f = SEEDS_DIR / "runs" / model_run_name(MODEL, "chair", ANIM["seed"]) / "samples" / f"{sample_name(step, ANIM['temp'])}.json"
    return json.loads(f.read_text())[: ANIM["n"]]


def tile(d, cell: int, width: int = 5) -> Image.Image:
    """One drawing, rendered like people's (render_strokes at 256 px; lines 5 px instead of the measured 3 px so
    they survive scaling down for display), scaled to the cell; blank if no drawing."""
    if not d:
        return Image.new("RGB", (cell, cell), WHITE)
    return render_strokes(d, width=width).resize((cell, cell), Image.LANCZOS)


def grid(drawings: list, cell: int, gap: int, bg: str = PAPER) -> Image.Image:
    side = 4 * cell + 3 * gap
    im = Image.new("RGB", (side, side), bg)
    for i, d in enumerate(drawings):
        im.paste(tile(d, cell), ((i % 4) * (cell + gap), (i // 4) * (cell + gap)))
    return im


# ---------- the time-lapse ----------

def timeline(n_ck: int, hold: int, fade: int, end_hold: int) -> list[tuple[int, int, float]]:
    """Frames as (checkpoint, next checkpoint, blend 0..1): hold each checkpoint, then cross-fade to the next."""
    out = []
    for i in range(n_ck):
        out += [(i, i, 0.0)] * (hold if i < n_ck - 1 else end_hold)
        if i < n_ck - 1:
            out += [(i, i + 1, (k + 1) / (fade + 1)) for k in range(fade)]
    return out


def overlay(im: Image.Image, step: int, xstep: float, recog: float | None, spread: float | None, ref: float, W: int):
    """The right-hand panel: title, step counter, a log training axis, recognizable, and the variety bar."""
    dr = ImageDraw.Draw(im)
    s = W / 1280
    x0 = int(720 * s)
    f = lambda px, **k: font(int(px * s), **k)  # noqa: E731
    dr.text((x0, int(56 * s)), "Watch an AI learn", font=f(40, bold=True), fill=INK)
    dr.text((x0, int(102 * s)), "what a chair is", font=f(40, bold=True), fill=INK)
    for k, line in enumerate(TEXT[MODEL]["sub"]):
        dr.text((x0, int((160 + 26 * k) * s)), line, font=f(19), fill=INK2)
    dr.text((x0, int(250 * s)), "TRAINING STEP", font=f(15, mono=True), fill=MUTED)
    dr.text((x0, int(270 * s)), f"{step:,}", font=f(64, mono=True), fill=INK)
    # log training axis 0 .. the last step
    ax0, ax1, ay = x0, int(1220 * s), int(372 * s)
    lx = lambda v: ax0 + (ax1 - ax0) * (log_x(v) - log_x(0)) / (log_x(STEPS[-1]) - log_x(0))  # noqa: E731
    dr.line([(ax0, ay), (ax1, ay)], fill=LINE, width=max(1, int(3 * s)))
    for t, lab in ((0, "0"), (100, "100"), (1000, "1k"), (10000, "10k"), (STEPS[-1], f"{STEPS[-1] / 1000:g}k")):
        dr.line([(lx(t), ay - int(5 * s)), (lx(t), ay + int(5 * s))], fill=MUTED, width=max(1, int(1.5 * s)))
        dr.text((lx(t), ay + int(10 * s)), lab, font=f(13, mono=True), fill=MUTED, anchor="ma")
    cx, r = lx(xstep), int(8 * s)
    dr.ellipse([cx - r, ay - r, cx + r, ay + r], fill=INK)
    # recognizable
    dr.text((x0, int(430 * s)), "Recognizable as a chair", font=f(19), fill=INK2)
    dr.text((ax1, int(424 * s)), "–" if recog is None else f"{recog:.0%}", font=f(28, bold=True), fill=INK, anchor="ra")
    # variety bar
    by = int(500 * s)
    dr.text((x0, by - int(30 * s)), "How varied its chairs are", font=f(19), fill=INK2)
    dr.text((ax1, by - int(36 * s)), "–" if spread is None else f"{spread:.2f}", font=f(28, bold=True), fill=INK, anchor="ra")
    bx = lambda v: ax0 + (ax1 - ax0) * (min(max(v, SPREAD_LO), SPREAD_HI) - SPREAD_LO) / (SPREAD_HI - SPREAD_LO)  # noqa: E731
    bh = int(22 * s)
    dr.rounded_rectangle([ax0, by + int(8 * s), ax1, by + int(8 * s) + bh], radius=bh // 2, fill="#E5E3DC")
    if spread is not None:
        dr.rounded_rectangle([ax0, by + int(8 * s), max(bx(spread), ax0 + bh), by + int(8 * s) + bh], radius=bh // 2, fill=INK2)
    rx = bx(ref)
    dr.line([(rx, by), (rx, by + int(16 * s) + bh)], fill=PEOPLE, width=max(2, int(4 * s)))
    dr.text((rx, by + int(22 * s) + bh), f"people’s chairs it learned from: {ref:.2f}", font=f(15), fill=PEOPLE, anchor="ma")
    dr.text((x0, int(626 * s)), "The same 16 random starts at every step: only the weights change.", font=f(15), fill=MUTED)
    dr.text((x0, int(648 * s)), f"Seed {ANIM['seed']}, temperature {ANIM['temp']:g}. Drawings: Google Quick, Draw! (CC BY 4.0).",
            font=f(15), fill=MUTED)
    dr.text((x0, int(670 * s)), "How varied: Meta DINOv2, 200 drawings per step.", font=f(15), fill=MUTED)


def time_lapse(anim: dict, frames_dir: Path, W: int = 1280, H: int = 720):
    cell, gap = 148, 8
    grids = [grid(drawings_at(st), cell, gap) for st in STEPS]
    plan = timeline(len(STEPS), hold=11, fade=8, end_hold=72)
    spread, recog, ref = anim["spread"], anim["recog"], anim["ref_spread"]

    def lerp(a, b, t):
        if a is None or b is None:
            return b if t >= 0.5 else a
        return a + (b - a) * t

    for k, (i, j, t) in enumerate(plan):
        im = Image.new("RGB", (W, H), PAPER)
        g = grids[i] if t == 0 else Image.blend(grids[i], grids[j], t)
        im.paste(g, (48, (H - g.height) // 2))
        xs = 10 ** (log_x(STEPS[i]) + (log_x(STEPS[j]) - log_x(STEPS[i])) * t) - 25
        overlay(im, STEPS[j] if t >= 0.5 else STEPS[i], xs, lerp(recog[i], recog[j], t), lerp(spread[i], spread[j], t), ref, W)
        im.save(frames_dir / f"f{k:04d}.png")
    return len(plan)


# ---------- stroke by stroke ----------

def stroke_frames(d: list, frames_dir: Path, step: int, side: int = 720, speed: float = 3.0):
    """The drawing as the model emits it, at a constant pen speed (Quick, Draw! units per frame): finished strokes in
    ink, the current one in orange with a ring at the pen; the pen lifts briefly between strokes."""
    pad, scale = 90, (side - 180) / 255.0
    xs = [x for s in d for x in s[0]]
    ys = [y for s in d for y in s[1]]
    dx, dy = (255 - max(xs)) / 2, (255 - max(ys)) / 2
    P = lambda x, y: (pad + (x + dx) * scale, pad + 30 + (y + dy) * scale)  # noqa: E731
    frames = [([], False)] * 12 + pen_frames(d, speed, pause=5) + [(None, False)] * 60
    for k, (strokes, down) in enumerate(frames):
        final = strokes is None
        strokes = [[list(s[0]), list(s[1])] for s in d] if final else strokes
        im = Image.new("RGB", (side, side), WHITE)
        dr = ImageDraw.Draw(im)
        for si, (sx, sy) in enumerate(strokes):
            pts = [P(x, y) for x, y in zip(sx, sy)]
            col = PEOPLE if (down and si == len(strokes) - 1) else INK
            if len(pts) == 1:
                pts = pts * 2
            dr.line(pts, fill=col, width=7, joint="curve")
            for x, y in (pts[0], pts[-1]):
                dr.ellipse([x - 3.5, y - 3.5, x + 3.5, y + 3.5], fill=col)
        if down:
            x, y = P(strokes[-1][0][-1], strokes[-1][1][-1])
            dr.ellipse([x - 11, y - 11, x + 11, y + 11], outline=PEOPLE, width=3)
        n_done = len(d) if final else len(strokes)
        dr.text((28, 24), f"Stroke {max(n_done, 1)} of {len(d)}" if strokes else "Ready…", font=font(26, bold=True), fill=INK)
        dr.text((28, 62), f"Training step {step:,}: drawn in the order the model chose", font=font(18), fill=MUTED)
        im.save(frames_dir / f"f{k:04d}.png")
    return len(frames)


def encode(frames_dir: Path, mp4: Path, gif: Path, fps: int, gif_fps: int, gif_width: int):
    ff = ffmpeg()
    subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames_dir / "f%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(mp4)], check=True)
    vf = f"fps={gif_fps},scale={gif_width}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=none"
    subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(frames_dir / "f%04d.png"),
                    "-vf", vf, "-loop", "0", str(gif)], check=True)


def first_recognized(step: int) -> int:
    """Index (0-15) of the first animation drawing that DINOv2 calls a chair (nearest adult prototype of 21).
    The embeddings hold the non-empty drawings in order, so they are mapped back to the drawing indices."""
    from metalesionlab.plato import PLATO_DIR
    from metalesionlab.plato_lifespan import CANDIDATES, prototype, recognized

    run = SEEDS_DIR / "runs" / model_run_name(MODEL, "chair", ANIM["seed"])
    alld = json.loads((run / "samples" / f"{sample_name(step, ANIM['temp'])}.json").read_text())
    x = np.load(run / "emb" / f"{sample_name(step, ANIM['temp'])}.npz")["cls"].astype(np.float64)
    protos = np.stack([prototype(np.load(PLATO_DIR / "embeddings" / "human" / f"{k}.npz")["cls"].astype(np.float64))
                       for k in CANDIDATES])
    kept = [i for i, d in enumerate(alld) if d]
    rec = dict(zip(kept, recognized(x, CANDIDATES.index("chair"), protos)))
    return next(i for i in range(ANIM["n"]) if rec.get(i))


def sprite(cell: int = 200, gap: int = 8, cols: int = 5) -> Image.Image:
    """The checkpoints' grids in one image (small model: 20, 5 across and 4 down; larger: 24, 6 x 4), for the page."""
    frames = [grid(drawings_at(st), cell, gap, bg=PAPER) for st in STEPS]
    fw = frames[0].width
    rows = -(-len(frames) // cols)
    sheet = Image.new("RGB", (cols * fw, rows * fw), PAPER)
    for i, fr in enumerate(frames):
        sheet.paste(fr, ((i % cols) * fw, (i // cols) * fw))
    return sheet


def curves_figure(res: dict, out: Path):
    """The learning path of every concept: recognizable, distance to the adult prototype and spread against
    training step, mean of the runs with a 95% band (t across runs) and each run thin; temperature 1."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    concepts = list(res["concepts"])
    names = {"recog": "Recognizable", "d_adult": "Distance to the adult prototype", "spread": "Spread (how varied)"}
    fig, axes = plt.subplots(len(concepts), 3, figsize=(13, 3.6 * len(concepts)), squeeze=False)
    x = np.log10(np.array(STEPS) + 25)
    for r, c in enumerate(concepts):
        b = res["concepts"][c]
        for j, m in enumerate(names):
            ax = axes[r, j]
            greys = ["#6B7280", "#9CA3AF", "#B8BCC4", "#D1D5DB"]
            for k, temp in enumerate(f"t{t:.1f}" for t in res["temps"]):
                col, lw = (INK, 2.2) if temp == "t1.0" else (greys[(k - 1) % len(greys)], 1.4)
                cv = b["curves"][temp][m]
                mean = np.array([np.nan if v is None else v for v in cv["mean"]], float)
                lo = np.array([np.nan if q[0] is None else q[0] for q in cv["ci95"]], float)
                hi = np.array([np.nan if q[1] is None else q[1] for q in cv["ci95"]], float)
                if temp == "t1.0":
                    ax.fill_between(x, lo, hi, color=INK, alpha=0.13, lw=0)
                    for vals in cv["per_seed"].values():
                        ax.plot(x, [np.nan if v is None else v for v in vals], color=INK, lw=0.7, alpha=0.3)
                ax.plot(x, mean, color=col, lw=lw, label=f"temperature {temp[1:]}")
            ax.axhline(b["reference"][m], color=MUTED, ls="--", lw=1.2, label="drawings it learned from")
            for age in ("2", "10"):
                if b.get("children") and age in b["children"]:
                    ax.axhline(b["children"][age][m], color=PEOPLE, lw=1, alpha=0.8)
                    ax.text(x[-1] + 0.05, b["children"][age][m], f"age {age}", color=PEOPLE, fontsize=8, va="center")
            ticks = [t for t in (0, 100, 1000, 10000, 100000) if t <= STEPS[-1]]
            ax.set_xticks(np.log10(np.array(ticks) + 25), [f"{t // 1000}k" if t >= 1000 else str(t) for t in ticks])
            ax.set_title(f"{c}: {names[m]}", fontsize=10, loc="left")
            ax.set_xlabel("training step", fontsize=9)
            ax.spines[["top", "right"]].set_visible(False)
            if r == 0 and j == 0:
                ax.legend(fontsize=8, frameon=False, loc="lower right")
    fig.suptitle("The sketch model learning, over runs: mean, 95% band across runs (temperature 1) and each run thin",
                 fontsize=11, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def main():
    global MODEL, ANIM, STEPS, SEEDS_DIR, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=sorted(MODELS), default="small")
    ap.add_argument("--web", action="store_true", help="also write the page's sprite and stroke-order drawing")
    ap.add_argument("--results", type=Path, help="default: sketch/<model dir>/results.json")
    args = ap.parse_args()
    MODEL = args.model
    ANIM, STEPS = MODELS[MODEL]["anim"], MODELS[MODEL]["steps"]
    SEEDS_DIR = LIFESPAN_DIR / "sketch" / MODELS[MODEL]["dir"]
    OUT = LIFESPAN_DIR / "sketch" / ("" if MODEL == "small" else MODELS[MODEL]["dir"])
    res = json.loads((args.results or SEEDS_DIR / "results.json").read_text())
    figs = LIFESPAN_DIR / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    print("figure:", curves_figure(res, figs / f"sketch_{MODELS[MODEL]['dir']}_curves.png"))
    anim = res["animation"]
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        n = time_lapse(anim, Path(tmp))
        encode(Path(tmp), OUT / "watch_it_learn.mp4", OUT / "watch_it_learn.gif", 24, 12, 640)
        print(f"time-lapse: {n} frames")
    # stroke by stroke: the first of the 16 that DINOv2 calls a chair at the last step (decided in the plan)
    last = drawings_at(STEPS[-1])
    idx = first_recognized(STEPS[-1])
    with tempfile.TemporaryDirectory() as tmp:
        n = stroke_frames(last[idx], Path(tmp), STEPS[-1])
        encode(Path(tmp), OUT / "stroke_by_stroke.mp4", OUT / "stroke_by_stroke.gif", 24, 12, 480)
        print(f"stroke by stroke: drawing {idx}, {n} frames")
    if args.web:
        WEB.mkdir(parents=True, exist_ok=True)
        sprite(cell=TEXT[MODEL]["cell"], cols=TEXT[MODEL]["cols"]).save(WEB / "learn_sprite.webp", "WEBP", quality=70, method=6)
        (WEB / "stroke_order.json").write_text(json.dumps({
            "about": f"One chair drawn by the sketch model ({MODELS[MODEL]['model']}; seed {ANIM['seed']}, temperature "
                     f"{ANIM['temp']:g}, training step {STEPS[-1]:,}), in the order it emitted its points; Quick, Draw! "
                     "coordinates (0-255). The model learned from Google Quick, Draw! (CC BY 4.0).",
            "model": MODEL, "seed": ANIM["seed"], "temp": ANIM["temp"], "step": STEPS[-1], "index": idx,
            "strokes": last[idx]}, separators=(",", ":")))
        for p in sorted(WEB.iterdir()):
            print(f"{p.name}: {p.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()

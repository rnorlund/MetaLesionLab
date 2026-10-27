"""The life of a chair: figures, and the small pictures for the /plato/lifespan page.

Usage: python -I scripts/plato_lifespan_figures.py [--web]   (after plato_lifespan_analyze.py)
Reads $PLATO_LIFESPAN_DIR/results.json and writes $PLATO_LIFESPAN_DIR/figures/:
  life_of_a_chair.png        the timeline strip: children aged 2-10 (no drawings: an icon array of how many in
                             10 are recognizable), adults (Quick, Draw!), Muse Image's Form, Stable Diffusion at
                             five training stages (the same seed throughout), and a slot for the damaged AI
  life_curves.{png,svg}      four measures vs. age (children) and vs. training steps (Stable Diffusion)
  life_paths.{png,svg}       recognizability vs. distance to the adult prototype: the two paths
--web also writes the page's picture strips to metalesionlab/web/static/img/plato_lifespan/ (WebP).

No child's drawing is drawn, shown or copied anywhere (CC BY-NC-SA 4.0 data, and they are children's).
Quick, Draw! drawings: Google, CC BY 4.0. Muse Image: our outputs. Stable Diffusion: CreativeML OpenRAIL-M.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab.plato import BY_KEY, PLATO_DIR, ink_crop  # noqa: E402
from metalesionlab.plato_lifespan import AGES, CHECKPOINTS, LIFESPAN_DIR, prototype, unit  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FIG = LIFESPAN_DIR / "figures"
WEB = REPO / "metalesionlab" / "web" / "static" / "img" / "plato_lifespan"
# reference palette (dataviz skill, as in plato_figures.py): Muse = slot 1 blue, people = slot 2 orange,
# Stable Diffusion = slot 3 aqua (as SDXL in the variety figures); slots 1-3 validate all-pairs.
SURFACE, INK, INK2, MUTED, GRIDC, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
MUSE_C, PEOPLE_C, SD_C = "#2a78d6", "#eb6834", "#1baf7a"
CREDIT = ("Children: Long et al. 2024, kiddraw (CC BY-NC-SA 4.0; statistics only, no drawings shown). "
          "Adults: Google Quick, Draw! (CC BY 4.0). AI: Muse Image; Stable Diffusion v1.1–v1.5 (CreativeML OpenRAIL-M). "
          "Similarity: Meta DINOv2.")
MEASURES = [("recog", "Recognizable", "share nearest its own thing (21 choices)", True),
            ("d_adult", "Distance to the adult Form", "cosine distance to the Quick, Draw! prototype", False),
            ("spread", "Variety (spread)", "mean pairwise distance, 16 drawings", False),
            ("d_muse", "Distance to Muse’s Form", "cosine distance to Muse Image’s prototype", False)]
CK = [c[0] for c in CHECKPOINTS]
KSTEPS = np.array([c[2] for c in CHECKPOINTS], float) / 1000

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"], "font.size": 11,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": BASE, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "svg.fonttype": "none",
})


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRIDC, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


# ---------- pictures we may show ----------

def adult_pictures(key: str, n: int = 8) -> list[Image.Image]:
    """Quick, Draw! drawings (CC BY 4.0) closest to the adult prototype, the most typical first."""
    z = np.load(PLATO_DIR / "embeddings" / "human" / f"{key}.npz")
    order = np.argsort(-(unit(z["cls"]) @ prototype(z["cls"])))[:n]
    return [ink_crop(Image.open(PLATO_DIR / "human" / key / z["files"][i]).convert("RGB")) for i in order]


def muse_pictures(key: str, n: int = 8) -> list[Image.Image]:
    """Muse Image's doodles, closest to Muse's prototype first."""
    z = np.load(PLATO_DIR / "embeddings" / "ai_doodle" / f"{key}.npz")
    k = BY_KEY[key].n_ai
    x, files = z["cls"][:k], list(z["files"])[:k]
    order = np.argsort(-(unit(x) @ prototype(x)))[:n]
    return [Image.open(PLATO_DIR / "ai" / "doodle" / key / files[i]).convert("RGB") for i in order]


def typical_seeds(key: str, n: int = 8) -> list[int]:
    """Seeds ordered by how close their v1.5 picture is to v1.5's prototype; the same seeds at every stage."""
    z = np.load(LIFESPAN_DIR / "embeddings" / "sd" / "v1.5" / f"{key}.npz")
    order = np.argsort(-(unit(z["cls"]) @ prototype(z["cls"])))[:n]
    return [int(str(z["files"][i])[1:].removesuffix(".png")) for i in order]


def sd_pictures(key: str, ckpt: str, seeds: list[int]) -> list[Image.Image]:
    return [Image.open(LIFESPAN_DIR / "ai" / "sd" / ckpt / key / f"s{s}.png").convert("RGB") for s in seeds]


# ---------- the timeline strip ----------

def chair_glyph(ax, x, y, s, color, lw=1.5):
    """A tiny front-view chair (backrest, seat, two legs) in a box of size s with its lower left at (x, y)."""
    kw = dict(color=color, lw=lw, solid_capstyle="round", solid_joinstyle="round")
    ax.plot([x + 0.24 * s, x + 0.24 * s, x + 0.76 * s, x + 0.76 * s], [y + 0.52 * s, y + 0.96 * s, y + 0.96 * s,
            y + 0.52 * s], **kw)
    ax.plot([x + 0.12 * s, x + 0.88 * s], [y + 0.5 * s, y + 0.5 * s], **kw)
    ax.plot([x + 0.2 * s, x + 0.2 * s], [y + 0.5 * s, y + 0.04 * s], **kw)
    ax.plot([x + 0.8 * s, x + 0.8 * s], [y + 0.5 * s, y + 0.04 * s], **kw)


def icon_array(ax, share: float, color: str, x0=0.08, y0=0.10, w=0.84):
    """Ten chair glyphs in two rows of five; round(10 * share) are solid, the rest faint."""
    k = int(round(10 * share))
    s = w / 5
    for i in range(10):
        r, c = divmod(i, 5)
        chair_glyph(ax, x0 + c * s + 0.1 * s, y0 + 0.2 + (1 - r) * s * 1.25, s * 0.8, color if i < k else GRIDC)


def timeline(res: dict, out: Path, key: str = "chair"):
    kids = res["children"]["cells"][key]
    stops = [("kid", a) for a in AGES] + [("adult", None), ("muse", None)] + [("sd", c) for c in CK] + [("damage", None)]
    seeds = typical_seeds(key, 1)
    adult_img = adult_pictures(key, 1)[0]
    muse_img = muse_pictures(key, 1)[0]
    n = len(stops)
    fig = plt.figure(figsize=(n * 1.25 + 0.6, 3.55))
    fig.text(0.008, 0.95, "The life of a chair", fontsize=17, fontweight="bold", va="top")
    fig.text(0.008, 0.865, "Children’s drawings are not shown: each child tile shows how many in 10 drawings look like a "
             "chair to the machine (nearest prototype of 21 things). Pictures: adults (Quick, Draw!), Muse Image, and "
             "Stable Diffusion from one seed at five training stages.", fontsize=8.6, color=INK2, va="top")
    groups = [(0, 9, "Children, age 2 to 10", PEOPLE_C), (9, 10, "Adults", PEOPLE_C), (10, 11, "Muse’s Form", MUSE_C),
              (11, 16, "Stable Diffusion, training stages", SD_C), (16, 17, "Damaged", MUTED)]
    L, R = 0.008, 0.995
    cw = (R - L) / n
    w_in, h_in = fig.get_size_inches()
    th = (cw - 0.005) * w_in / h_in  # square tiles
    for g0, g1, label, color in groups:
        fig.add_artist(plt.Line2D([L + g0 * cw + 0.003, L + g1 * cw - 0.003], [0.745, 0.745], color=color, lw=2.5,
                                  solid_capstyle="round"))
        fig.text(L + g0 * cw + 0.003, 0.765, label, fontsize=8.5, color=INK2, va="bottom")
    for i, (kind, val) in enumerate(stops):
        ax = fig.add_axes([L + i * cw + 0.0025, 0.715 - th, cw - 0.005, th])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color(GRIDC)
        if kind == "kid":
            c = kids[str(val)]
            icon_array(ax, c["recog"], PEOPLE_C)
            title, sub = f"age {val}", f"{c['recog']:.0%} · {c['d_adult']:.2f}"
        elif kind == "adult":
            ax.imshow(adult_img, extent=(0.06, 0.94, 0.06, 0.94))
            c = res["adults"]["cells"][key]
            title, sub = "adults", f"{c['recog']:.0%} · {c['d_adult']:.2f}"
        elif kind == "muse":
            ax.imshow(ink_crop(muse_img), extent=(0.06, 0.94, 0.06, 0.94))
            c = res["muse"]["cells"][key]
            title, sub = "Muse Image", f"{c['recog']:.0%} · {c['d_adult']:.2f}"
        elif kind == "sd":
            ax.imshow(sd_pictures(key, val, seeds)[0], extent=(0.02, 0.98, 0.02, 0.98))
            c = res["ai"]["cells"][key][val]
            title, sub = f"SD {val}", f"{c['recog']:.0%} · {c['d_adult']:.2f}"
        else:
            ax.text(0.5, 0.5, "damaged AI\nsee\n/plato/damage", ha="center", va="center", fontsize=8.5, color=MUTED)
            title, sub = "decline", "analogy only"
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        fig.text(L + (i + 0.5) * cw, 0.68 - th, title, ha="center", fontsize=9.5, fontweight="bold", va="top")
        fig.text(L + (i + 0.5) * cw, 0.605 - th, sub, ha="center", fontsize=8, color=INK2, va="top")
    fig.text(0.008, 0.06, "Under each tile: recognizable · distance to the adult Form (lower = closer). " + CREDIT,
             fontsize=7.2, color=MUTED)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


# ---------- curves ----------

def curves(res: dict, out_stem: Path, things: str = "all"):
    kid = res["children"]["curves"]
    ai = res["ai"][things]["curves"]
    ref_set = "children_things" if things == "all" else "tier1"
    fig, axes = plt.subplots(len(MEASURES), 2, figsize=(10.4, 12.4), sharey="row",
                             gridspec_kw={"width_ratios": [1.25, 1], "wspace": 0.08, "hspace": 0.42})
    for r, (m, title, sub, up) in enumerate(MEASURES):
        axk, axa = axes[r]
        y = np.array(kid[m]["mean"])
        lo, hi = np.array(kid[m]["ci95"]).T
        axk.fill_between(AGES, lo, hi, color=PEOPLE_C, alpha=0.12, lw=0)
        axk.plot(AGES, y, color=PEOPLE_C, lw=2, solid_capstyle="round")
        axk.plot(AGES, y, "o", color=PEOPLE_C, ms=6, mec=SURFACE, mew=1.5)
        ya = np.array(ai[m]["mean"])
        lo_a, hi_a = np.array(ai[m]["ci95"]).T
        for j in range(len(CK)):
            axa.plot([KSTEPS[j]] * 2, [lo_a[j], hi_a[j]], color=SD_C, lw=1.6, alpha=0.6, solid_capstyle="round")
        axa.plot(KSTEPS[:2], ya[:2], color=SD_C, lw=2)
        for j in range(2, len(CK)):  # v1.3, v1.4 and v1.5 each branch from v1.2
            axa.plot([KSTEPS[1], KSTEPS[j]], [ya[1], ya[j]], color=SD_C, lw=2)
        axa.plot(KSTEPS, ya, "o", color=SD_C, ms=6, mec=SURFACE, mew=1.5)
        for j, name in enumerate(CK):
            dy = 9 if name != "v1.4" else -14
            axa.annotate(name, (KSTEPS[j], ya[j]), xytext=(0, dy), textcoords="offset points", ha="center",
                         fontsize=8, color=INK2)
        for ax in (axk, axa):
            style(ax)
            ad = res["adults"][f"mean_over_{ref_set}"][m]
            mu = res["muse"][f"mean_over_{ref_set}"][m]
            ax.axhline(ad, color=PEOPLE_C, lw=1, alpha=0.8)
            ax.axhline(mu, color=MUSE_C, lw=1, alpha=0.8)
        axa.text(1.0, res["adults"][f"mean_over_{ref_set}"][m], " adults", transform=axa.get_yaxis_transform(),
                 va="center", fontsize=8.5, color=INK2)
        axa.text(1.0, res["muse"][f"mean_over_{ref_set}"][m], " Muse", transform=axa.get_yaxis_transform(),
                 va="center", fontsize=8.5, color=INK2)
        axk.set_title(f"{title}", loc="left", fontsize=12, fontweight="bold", pad=18)
        axk.text(0, 1.02, sub + ("  (higher = more recognizable)" if up else "  (lower = closer / narrower)"),
                 transform=axk.transAxes, fontsize=8.5, color=MUTED)
        axk.set_xticks(AGES)
        axa.set_xticks([0.5, 1.0, 1.5])
        axa.set_xlim(0.25, 1.7)
        if r == len(MEASURES) - 1:
            axk.set_xlabel("children’s age (years)")
            axa.set_xlabel("Stable Diffusion training steps (millions)")
        if m == "recog":
            for ax in (axk, axa):
                ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    axes[0][0].text(0, 1.32, "Children (ages 2–10)", transform=axes[0][0].transAxes, fontsize=13, color=INK)
    axes[0][1].text(0, 1.32, "Stable Diffusion (v1.1 → v1.5)", transform=axes[0][1].transAxes, fontsize=13, color=INK)
    n_k = len(res["children_things"])
    n_a = len(res["ai"][things]["things"])
    fig.text(0.06, 0.035, f"Means over {n_k} things (children) and {n_a} things (Stable Diffusion); bands and bars: 95% "
             "bootstrap CIs. v1.3, v1.4 and v1.5 each resume from v1.2.\n" + CREDIT, fontsize=7.5, color=MUTED)
    paths = []
    for ext in ("png", "svg"):
        p = out_stem.with_suffix(f".{ext}")
        fig.savefig(p, dpi=150, bbox_inches="tight")
        paths.append(p)
    plt.close(fig)
    return paths


def paths_figure(res: dict, out_stem: Path):
    """Recognizability (x) vs distance to the adult Form (y): children's path and the AI's."""
    kid = res["children"]["curves"]
    shared = res["comparison"]["things"]
    fig, ax = plt.subplots(figsize=(8.6, 6.2))
    style(ax)
    ax.grid(axis="x", color=GRIDC, lw=0.8)
    kx, ky = np.array(kid["recog"]["mean"]), np.array(kid["d_adult"]["mean"])
    ax.plot(kx, ky, color=PEOPLE_C, lw=2)
    ax.plot(kx, ky, "o", color=PEOPLE_C, ms=7, mec=SURFACE, mew=1.5)
    for a, x, y in zip(AGES, kx, ky):
        if a in (2, 4, 6, 8, 10):
            ax.annotate(f"age {a}", (x, y), xytext=(6, 6), textcoords="offset points", fontsize=9, color=INK2)
    cells = res["ai"]["cells"]
    ax_ = np.array([np.mean([cells[k][c]["recog"] for k in shared]) for c in CK])
    ay_ = np.array([np.mean([cells[k][c]["d_adult"] for k in shared]) for c in CK])
    ax.plot(ax_[:2], ay_[:2], color=SD_C, lw=2)
    for j in range(2, len(CK)):
        ax.plot([ax_[1], ax_[j]], [ay_[1], ay_[j]], color=SD_C, lw=2)
    ax.plot(ax_, ay_, "o", color=SD_C, ms=7, mec=SURFACE, mew=1.5)
    ax.annotate("SD v1.1", (ax_[0], ay_[0]), xytext=(-8, -14), textcoords="offset points", ha="right",
                fontsize=9, color=INK2)
    ax.annotate("SD v1.2–v1.5", (ax_[1], ay_[1]), xytext=(-8, 8), textcoords="offset points", ha="right",
                fontsize=9, color=INK2)
    ad = res["adults"]["mean_over_children_things"]
    mu = res["muse"]["mean_over_children_things"]
    ax.plot([ad["recog"]], [ad["d_adult"]], "s", color=PEOPLE_C, ms=10, mec=SURFACE, mew=2)
    ax.annotate("adults (Quick, Draw!)", (ad["recog"], ad["d_adult"]), xytext=(8, -4), textcoords="offset points",
                fontsize=9.5, color=INK)
    ax.plot([mu["recog"]], [mu["d_adult"]], "D", color=MUSE_C, ms=9, mec=SURFACE, mew=2)
    ax.annotate("Muse Image", (mu["recog"], mu["d_adult"]), xytext=(8, -4), textcoords="offset points",
                fontsize=9.5, color=INK)
    if "sdxl" in res:
        sx = res["sdxl"]["mean_over_children_things"]
        ax.plot([sx["recog"]], [sx["d_adult"]], "o", mfc=SURFACE, mec=SD_C, mew=2, ms=9)
        ax.annotate("SDXL", (sx["recog"], sx["d_adult"]), xytext=(8, -4), textcoords="offset points", fontsize=9.5,
                    color=INK)
    ax.set_xlabel("recognizable (share nearest its own thing, of 21)")
    ax.set_ylabel("distance to the adult Form (lower = closer)")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_title("Two roads to the Form", loc="left", fontsize=15, fontweight="bold", pad=34)
    ax.text(0, 1.015, f"Mean over the {len(shared)} things both drew. Children walk toward the adult Form as they grow; "
            "Stable Diffusion’s pictures are recognizable from its first public checkpoint, but stay far from it.",
            transform=ax.transAxes, fontsize=8.5, color=INK2, wrap=True)
    fig.text(0.01, 0.005, CREDIT, fontsize=6.8, color=MUTED)
    paths = []
    for ext in ("png", "svg"):
        p = out_stem.with_suffix(f".{ext}")
        fig.savefig(p, dpi=150, bbox_inches="tight")
        paths.append(p)
    plt.close(fig)
    return paths


# ---------- the sketch model that grows up on people's chairs ----------

SKETCH_STEPS = [0, 100, 200, 800, 3200, 25600]


def sketch_pictures(step: int, n: int = 8, temp: str = "1.0") -> list[Image.Image]:
    """The first n non-empty drawings the sketch model made at a training step, rendered like people's."""
    from metalesionlab.plato import render_strokes

    f = LIFESPAN_DIR / "sketch" / "samples" / f"step{step}_t{temp}.json"
    drawings = [d for d in json.loads(f.read_text()) if d][:n]
    return [ink_crop(render_strokes(d)) for d in drawings]


def sketch_figure(res: dict, out: Path):
    rows = res["sketch"]["steps"]["t1.0"]
    tr = res["sketch"]["training_drawings"]
    n = 8
    fig = plt.figure(figsize=(12.6, 1.35 * len(SKETCH_STEPS) + 1.5))
    fig.text(0.01, 0.985, "An AI that grows up on people’s chairs", fontsize=16, fontweight="bold", va="top")
    fig.text(0.01, 0.945, "A small sketch model (Sketch-RNN-style LSTM) trained from random weights on 20,000 Quick, Draw! "
             "chairs; the first 8 drawings at each training step (temperature 1), rendered like people’s.",
             fontsize=9, color=INK2, va="top")
    top, h = 0.9, 0.84 / len(SKETCH_STEPS)
    for r, step in enumerate(SKETCH_STEPS):
        row = rows[str(step)]
        y = top - (r + 1) * h
        fig.text(0.01, y + h * 0.62, f"step {step:,}", fontsize=11, fontweight="bold")
        fig.text(0.01, y + h * 0.32, f"{row['recog']:.0%} recognizable\ndistance {row['d_adult']:.2f} · "
                 f"spread {row['spread']:.2f}", fontsize=8.5, color=INK2)
        for i, im in enumerate(sketch_pictures(step, n)):
            ax = fig.add_axes([0.19 + i * 0.1, y + 0.005, 0.095, h - 0.01])
            ax.imshow(im)
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color(GRIDC)
    fig.text(0.01, 0.012, f"Its training drawings: {tr['recog']:.0%} recognizable, distance {tr['d_adult']:.2f}, spread "
             f"{tr['spread']:.2f}. Chance is 5%. Quick, Draw! drawings: Google, CC BY 4.0. Similarity: Meta DINOv2.",
             fontsize=8, color=MUTED)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


# ---------- web strips ----------

def strip(images: list[Image.Image], cell: int = 132, gap: int = 4) -> Image.Image:
    out = Image.new("RGB", (len(images) * cell + (len(images) - 1) * gap, cell), "white")
    for i, im in enumerate(images):
        t = im.convert("RGB").copy()
        t.thumbnail((cell, cell), Image.LANCZOS)
        out.paste(t, (i * (cell + gap) + (cell - t.width) // 2, (cell - t.height) // 2))
    return out


def web_assets(key: str = "chair", n: int = 6) -> list[Path]:
    WEB.mkdir(parents=True, exist_ok=True)
    seeds = typical_seeds(key, n)
    sets = {f"{key}_adults": adult_pictures(key, n), f"{key}_muse": [ink_crop(m) for m in muse_pictures(key, n)]}
    for c in CK:
        sets[f"{key}_sd_{c.replace('.', '')}"] = sd_pictures(key, c, seeds)
    if (LIFESPAN_DIR / "sketch" / "samples").exists():
        for step in SKETCH_STEPS:
            sets[f"sketch_step{step}"] = sketch_pictures(step, n)
    paths = []
    for name, ims in sets.items():
        p = WEB / f"{name}.webp"
        strip(ims).save(p, "WEBP", quality=72, method=6)
        paths.append(p)
    return paths


def series_card(res: dict, out: Path, key: str = "chair"):
    """The series card picture (1200 x 675): children as icon arrays (no drawings), then adults, Muse Image,
    Stable Diffusion v1.5, and the sketch model at its first and last step."""
    kids = res["children"]["cells"][key]
    fig = plt.figure(figsize=(12, 6.75), dpi=100)
    fig.patch.set_facecolor("#F7F6F1")
    fig.text(0.04, 0.9, "The life of a chair", fontsize=34, fontweight="bold", va="top")
    fig.text(0.04, 0.79, "Children walk toward the adult chair as they grow. Does an AI, as it trains?", fontsize=17,
             color=INK2, va="top")
    tiles = [("age 2", "icons", kids["2"]["recog"], PEOPLE_C), ("age 10", "icons", kids["10"]["recog"], PEOPLE_C),
             ("adults", adult_pictures(key, 1)[0], None, PEOPLE_C), ("Muse Image", ink_crop(muse_pictures(key, 1)[0]), None, MUSE_C),
             ("SD v1.5", sd_pictures(key, "v1.5", typical_seeds(key, 1))[0], None, SD_C)]
    if "sketch" in res:
        tiles.append(("sketch model", sketch_pictures(25600, 1)[0], None, INK2))
    w = 0.92 / len(tiles)
    for i, (lab, im, share, col) in enumerate(tiles):
        ax = fig.add_axes([0.04 + i * w + 0.006, 0.2, w - 0.012, (w - 0.012) * 12 / 6.75])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_facecolor("#FFFFFF")
        for sp in ax.spines.values():
            sp.set_color(GRIDC)
        if isinstance(im, str):
            icon_array(ax, share, col, x0=0.06, y0=0.06, w=0.88)
        else:
            ax.imshow(im, extent=(0.04, 0.96, 0.04, 0.96))
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        fig.add_artist(plt.Line2D([0.04 + i * w + 0.006, 0.04 + (i + 1) * w - 0.006], [0.17, 0.17], color=col, lw=4,
                                  solid_capstyle="round"))
        fig.text(0.04 + (i + 0.5) * w, 0.13, lab, ha="center", va="top", fontsize=15, fontweight="bold")
    fig.text(0.04, 0.035, "Children’s drawings are not shown: their tiles show how many in 10 look like a chair.", fontsize=11,
             color=MUTED)
    tmp = out.with_suffix(".png")
    fig.savefig(tmp, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)
    Image.open(tmp).convert("RGB").resize((1200, 675), Image.LANCZOS).save(out, "WEBP", quality=80, method=6)
    tmp.unlink()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", action="store_true")
    ap.add_argument("--results", type=Path, default=LIFESPAN_DIR / "results.json")
    args = ap.parse_args()
    res = json.loads(args.results.read_text())
    FIG.mkdir(parents=True, exist_ok=True)
    made = [timeline(res, FIG / "life_of_a_chair.png")]
    made += curves(res, FIG / "life_curves")
    made += curves(res, FIG / "life_curves_tier1", "tier1")
    made += paths_figure(res, FIG / "life_paths")
    if "sketch" in res:
        made.append(sketch_figure(res, FIG / "life_sketch.png"))
    if args.web:
        made += web_assets()
        card = REPO / "metalesionlab" / "web" / "static" / "img" / "plato" / "series" / "lifespan.webp"
        card.parent.mkdir(parents=True, exist_ok=True)
        made.append(series_card(res, card))
    for p in made:
        print(p, f"{p.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()

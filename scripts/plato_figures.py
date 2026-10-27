"""Plato's Chair, step 5: figures for the website and the demo video.

Usage: python -I scripts/plato_figures.py
Reads $PLATO_DIR/results.json and the cached embeddings; writes $PLATO_DIR/figures/:
  grid_<key>.png             "Ask an AI to draw 16 chairs" next to 16 people's chairs (chair, boat, face, person)
  similarity_chair_boat.*    within-concept similarity matrices, AI vs people, chair vs boat
  scatter_spread.*           AI spread vs human spread, one labeled point per concept
  index_ranked.*             homogenization index (AI spread / human spread) with 95% CIs
Human drawings: Google Quick, Draw! (CC BY 4.0); the credit is printed on every figure that shows them.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab.plato import BY_KEY, PLATO_DIR, cosine_distances, grid, ink_crop, load_dir, spread  # noqa: E402

FIG = PLATO_DIR / "figures"
# reference palette (dataviz skill): AI = slot 1 blue, people = slot 2 orange
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
AI_C, HUMAN_C = "#2a78d6", "#eb6834"
BLUES = LinearSegmentedColormap.from_list("blues", ["#fcfcfb", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
CREDIT = "AI: Meta Muse Image. People: Google Quick, Draw! dataset (CC BY 4.0). Similarity: Meta DINOv2."
HIGHLIGHT = {"chair", "sailboat", "face", "yoga"}

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"], "font.size": 11,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": "#c3c2b7", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "svg.fonttype": "none",
})


def human_subset(key: str, n: int) -> np.ndarray:
    """A typical set of n human drawings for the grids and matrices: of 200 random sets, the one whose
    spread is the median (so the picture neither flatters nor hides the human variety)."""
    rng = np.random.default_rng(7)
    d = cosine_distances(embeddings("human", key))
    sets = [np.sort(rng.choice(len(d), n, replace=False)) for _ in range(201)]
    spreads = np.array([spread(d, s) for s in sets])
    return sets[int(np.argsort(spreads)[len(spreads) // 2])]


def pictures(key: str, n: int) -> tuple[list[Image.Image], list[Image.Image], np.ndarray]:
    ai = [ink_crop(Image.open(f)) for f in load_dir(PLATO_DIR / "ai" / "doodle" / key)[:n]]
    idx = human_subset(key, n)
    files = load_dir(PLATO_DIR / "human" / key)
    hu = [ink_crop(Image.open(files[i])) for i in idx]
    return ai, hu, idx


def embeddings(source: str, key: str) -> np.ndarray:
    return np.load(PLATO_DIR / "embeddings" / source / f"{key}.npz")["cls"]


def grid_figure(key: str, row: dict) -> Path:
    c = BY_KEY[key]
    n = c.n_ai
    ai, hu, idx = pictures(key, n)
    noun = {"sailboat": "sailboats", "face": "faces", "yoga": "people doing yoga"}.get(key, c.label + "s")
    fig, axes = plt.subplots(1, 2, figsize=(12, 7.3 if n == 16 else 6.0))
    ai_spread = row["ai_spread"]
    hu_spread = spread(cosine_distances(embeddings("human", key)), idx)
    for ax, imgs, title, color, s in ((axes[0], ai, f"Ask an AI to draw {n} {noun}", AI_C, ai_spread),
                                      (axes[1], hu, f"Ask {n} people", HUMAN_C, hu_spread)):
        ax.imshow(grid(imgs, cols=4, cell=220, gap=10, bg=SURFACE))
        ax.set_axis_off()
        ax.set_title(title, fontsize=20, fontweight="bold", color=INK, pad=14, loc="left")
        ax.add_patch(plt.Rectangle((0, -0.058), 0.014, 0.034, transform=ax.transAxes, color=color, clip_on=False))
        ax.text(0.025, -0.041, f"spread {s:.2f}", transform=ax.transAxes, fontsize=14, color=INK2, va="center")
    fig.text(0.01, 0.015, CREDIT + "  Spread = mean distance between two pictures of the set.", fontsize=9,
             color=MUTED)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.11, wspace=0.06)
    out = FIG / f"grid_{key}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def similarity_figure(rows: dict) -> list[Path]:
    fig, axes = plt.subplots(2, 2, figsize=(9, 8.4))
    fig.subplots_adjust(left=0.05, right=0.84, top=0.88, bottom=0.06, wspace=0.08, hspace=0.16)
    mats = {}
    for key in ("chair", "sailboat"):
        n = BY_KEY[key].n_ai
        a = embeddings("ai_doodle", key)[:n]
        h = embeddings("human", key)[human_subset(key, n)]
        mats[key] = (1 - cosine_distances(a), 1 - cosine_distances(h))
    vmin = min(m.min() for pair in mats.values() for m in pair)
    for r, key in enumerate(("chair", "sailboat")):
        for col, (who, m) in enumerate((("AI", mats[key][0]), ("People", mats[key][1]))):
            ax = axes[r, col]
            show = m.copy()
            np.fill_diagonal(show, np.nan)
            im = ax.imshow(show, cmap=BLUES, vmin=vmin, vmax=1)
            off = m[np.triu_indices(len(m), 1)].mean()
            ax.set_title(f"{who}: {BY_KEY[key].label}s   mean {off:.2f}", fontsize=13, loc="left", color=INK)
            ax.set_xticks([])
            ax.set_yticks([])
            for s in ax.spines.values():
                s.set_visible(False)
    cax = fig.add_axes((0.87, 0.25, 0.022, 0.45))
    cbar = fig.colorbar(im, cax=cax)
    cbar.set_label("similarity between two pictures", color=INK2)
    cbar.outline.set_visible(False)
    fig.suptitle("Every pair of 16 pictures: darker = more alike", fontsize=16, fontweight="bold", x=0.05,
                 ha="left", y=0.96)
    fig.text(0.05, 0.015, CREDIT, fontsize=8.5, color=MUTED)
    outs = []
    for ext in ("png", "svg"):
        out = FIG / f"similarity_chair_boat.{ext}"
        fig.savefig(out, dpi=150)
        outs.append(out)
    plt.close(fig)
    return outs


def _place_labels(ax, xs, ys, labels, fontsize=9):
    """Labels right of each point, nudged vertically until boxes stop overlapping."""
    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = []
    for x, y, lab in zip(xs, ys, labels):
        t = ax.annotate(lab, (x, y), xytext=(5, 0), textcoords="offset points", fontsize=fontsize, color=INK2,
                        va="center")
        texts.append(t)
    for _ in range(200):
        moved = False
        boxes = [t.get_window_extent(renderer).expanded(1.02, 1.1) for t in texts]
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                if boxes[i].overlaps(boxes[j]):
                    lo, hi = (i, j) if boxes[i].y0 < boxes[j].y0 else (j, i)
                    for k, d in ((lo, -1.5), (hi, 1.5)):
                        dx, dy = texts[k].xyann
                        texts[k].xyann = (dx, dy + d)
                    moved = True
        if not moved:
            break
    return texts


def scatter_figure(rows: list[dict]) -> list[Path]:
    fig, ax = plt.subplots(figsize=(9, 7.2))
    xs = np.array([r["human_spread"] for r in rows])
    ys = np.array([r["ai_spread"] for r in rows])
    lo = 0
    hi = max(xs.max(), ys.max()) * 1.08
    ax.plot([lo, hi], [lo, hi], color=MUTED, lw=1, zorder=1)
    ax.text(hi * 0.97, hi * 0.97, "AI as varied as people", color=MUTED, fontsize=9, ha="right", va="bottom",
            rotation=0)
    for r, x, y in zip(rows, xs, ys):
        e = r["ai_spread_ci95"]
        ax.plot([x, x], e, color="#cde2fb", lw=1.5, zorder=2, solid_capstyle="round")
    colors = [AI_C if r["key"] in HIGHLIGHT else "#86b6ef" for r in rows]
    ax.scatter(xs, ys, s=[70 if r["key"] in HIGHLIGHT else 40 for r in rows], c=colors, edgecolors=SURFACE,
               linewidths=1.5, zorder=3)
    _place_labels(ax, xs, ys, [r["label"] for r in rows], fontsize=8.5)
    for t, r in zip(ax.texts[1:], rows):
        if r["key"] in HIGHLIGHT:
            t.set_fontweight("bold")
            t.set_color(INK)
    ax.set_xlim(0.15, hi)
    ax.set_ylim(0, hi)
    ax.set_xlabel("How varied people's drawings are (spread)")
    ax.set_ylabel("How varied the AI's drawings are (spread)")
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    rho = RESULTS["summary"]["rank_correlation_ai_vs_human_spread"]
    below = int((ys < xs).sum())
    head = ("Every concept sits below the line: the AI draws each idea more alike than people do"
            if below == len(rows) else f"{below} of {len(rows)} concepts sit below the line (AI more alike)")
    ax.set_title(f"{head}\nrank correlation {rho['rho']:.2f} [95% CI {rho['ci95'][0]:.2f}, {rho['ci95'][1]:.2f}], "
                 f"{len(rows)} concepts", fontsize=12.5, loc="left", color=INK)
    fig.text(0.01, 0.01, CREDIT + " Bars: 95% CI of the AI spread.", fontsize=8, color=MUTED)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.88, bottom=0.11)
    outs = []
    for ext in ("png", "svg"):
        out = FIG / f"scatter_spread.{ext}"
        fig.savefig(out, dpi=150)
        outs.append(out)
    plt.close(fig)
    return outs


def index_figure(rows: list[dict]) -> list[Path]:
    rs = sorted(rows, key=lambda r: r["homogenization_index"])
    fig, ax = plt.subplots(figsize=(7.5, 0.26 * len(rs) + 1.6))
    y = np.arange(len(rs))
    for yi, r in zip(y, rs):
        lo, hi = r["homogenization_index_ci95"]
        ax.plot([lo, hi], [yi, yi], color="#b7d3f6", lw=2, solid_capstyle="round", zorder=2)
    ax.scatter([r["homogenization_index"] for r in rs], y, s=[60 if r["key"] in HIGHLIGHT else 36 for r in rs],
               color=[AI_C if r["key"] in HIGHLIGHT else "#5598e7" for r in rs], edgecolors=SURFACE,
               linewidths=1.5, zorder=3)
    ax.axvline(1, color=MUTED, lw=1)
    ax.text(1.0, len(rs) - 0.3, " as varied as people", color=MUTED, fontsize=9, va="bottom")
    ax.set_yticks(y, [r["label"] for r in rs], fontsize=9.5)
    for t, r in zip(ax.get_yticklabels(), rs):
        t.set_color(INK if r["key"] in HIGHLIGHT else INK2)
        if r["key"] in HIGHLIGHT:
            t.set_fontweight("bold")
    ax.set_xlim(0, max(1.1, max(r["homogenization_index_ci95"][1] for r in rs) * 1.05))
    ax.set_ylim(-0.8, len(rs) - 0.2)
    ax.set_xlabel("AI spread / people's spread  (lower = AI more uniform)")
    ax.grid(True, axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("How much more alike the AI draws each concept", fontsize=13, loc="left", fontweight="bold")
    fig.text(0.01, 0.005, "Bars: 95% CI. " + CREDIT, fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    outs = []
    for ext in ("png", "svg"):
        out = FIG / f"index_ranked.{ext}"
        fig.savefig(out, dpi=150)
        outs.append(out)
    plt.close(fig)
    return outs


RESULTS = json.loads((PLATO_DIR / "results.json").read_text())


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    rows = RESULTS["concepts"]
    by = {r["key"]: r for r in rows}
    made = [grid_figure(k, by[k]) for k in ("chair", "sailboat", "face", "yoga") if k in by]
    if "chair" in by and "sailboat" in by:
        made += similarity_figure(by)
    made += scatter_figure(rows) + index_figure(rows)
    print("\n".join(str(p) for p in made))


if __name__ == "__main__":
    main()

"""Plato's Chair, is it just Muse? Figures comparing Muse Image, Stable Diffusion XL and people.

Usage: python -I scripts/plato_sdxl_figures.py   (after plato_sdxl_analyze.py)
Writes $PLATO_DIR/figures/:
  grid3_<key>.png              16 Muse | 16 SDXL | 16 people, ink-cropped as DINOv2 sees them (chair, umbrella, book)
  index_ranked_two_ai.*        AI spread / people's spread for both AIs, with 95% CIs, ranked by Muse
  scatter_muse_vs_sdxl.*       Muse spread vs SDXL spread, one labeled point per concept
Credits printed on every figure: SDXL (Stability AI, OpenRAIL++), Google Quick, Draw! (CC BY 4.0).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from plato_figures import (AI_C, FIG, GRID, HUMAN_C, INK, INK2, MUTED, SURFACE, _place_labels,  # noqa: E402
                           embeddings, human_subset)

from metalesionlab.plato import BY_KEY, PLATO_DIR, cosine_distances, grid, ink_crop, load_dir, spread  # noqa: E402

SDXL_C = "#1baf7a"  # reference palette slot 3 (aqua); Muse keeps slot 1 blue, people slot 2 orange
CREDIT = ("AI: Meta Muse Image; SDXL (Stability AI, OpenRAIL++). People: Google Quick, Draw! dataset "
          "(CC BY 4.0). Similarity: Meta DINOv2.")
HIGHLIGHT = {"chair", "umbrella", "bicycle", "book"}
RES = json.loads((PLATO_DIR / "results_sdxl.json").read_text())


def save(fig, name: str, exts=("png", "svg")) -> list[Path]:
    outs = []
    for ext in exts:
        out = FIG / f"{name}.{ext}"
        fig.savefig(out, dpi=150)
        outs.append(out)
    plt.close(fig)
    return outs


def grid3_figure(key: str, row: dict) -> list[Path]:
    """Muse | SDXL | people, 16 each (Muse has 12 for tier-2 concepts)."""
    c = BY_KEY[key]
    muse = [ink_crop(Image.open(f)) for f in load_dir(PLATO_DIR / "ai" / "doodle" / key)[:c.n_ai]]
    sdxl = [ink_crop(Image.open(f)) for f in load_dir(PLATO_DIR / "ai" / "sdxl_doodle" / key)[:16]]
    idx = human_subset(key, 16)
    hfiles = load_dir(PLATO_DIR / "human" / key)
    hu = [ink_crop(Image.open(hfiles[i])) for i in idx]
    hu_spread = spread(cosine_distances(embeddings("human", key)), idx)
    noun = {"sailboat": "sailboats", "face": "faces", "yoga": "people doing yoga"}.get(key, c.label + "s")
    fig, axes = plt.subplots(1, 3, figsize=(18, 7.6))
    panels = ((axes[0], muse, f"Meta Muse Image: {len(muse)} {noun}", AI_C, row["muse_spread"]),
              (axes[1], sdxl, f"Stable Diffusion XL: {len(sdxl)} {noun}", SDXL_C, row["sdxl_spread"]),
              (axes[2], hu, f"{len(hu)} people", HUMAN_C, hu_spread))
    for ax, imgs, title, color, s in panels:
        ax.imshow(grid(imgs, cols=4, cell=220, gap=10, bg=SURFACE))
        ax.set_axis_off()
        ax.set_anchor("N")  # a 12-picture panel stays top-aligned with the 16-picture ones
        ax.set_title(title, fontsize=17, fontweight="bold", color=INK, pad=12, loc="left")
        ax.add_patch(plt.Rectangle((0, -0.058), 0.016, 0.034, transform=ax.transAxes, color=color, clip_on=False))
        ax.text(0.028, -0.041, f"spread {s:.2f}", transform=ax.transAxes, fontsize=14, color=INK2, va="center")
    fig.suptitle(f"Same prompt, two AIs: \"a quick simple doodle sketch of {c.phrase}\"", fontsize=19,
                 fontweight="bold", x=0.01, ha="left", y=0.975, color=INK)
    fig.text(0.01, 0.015, CREDIT + "  Spread = mean distance between two pictures of the set. "
             "Pictures cropped to their ink, as the similarity model sees them.", fontsize=9, color=MUTED)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.86, bottom=0.11, wspace=0.05)
    return save(fig, f"grid3_{key}", ("png",))


def index_figure(rows: list[dict]) -> list[Path]:
    rs = sorted(rows, key=lambda r: r["muse_index"])
    fig, ax = plt.subplots(figsize=(8, 0.34 * len(rs) + 1.9))
    y = np.arange(len(rs))
    off = 0.17
    for name, color, dy, label in (("muse", AI_C, -off, "Meta Muse Image"),
                                   ("sdxl", SDXL_C, off, "Stable Diffusion XL")):
        for yi, r in zip(y, rs):
            lo, hi = r[f"{name}_index_ci95"]
            ax.plot([lo, hi], [yi + dy, yi + dy], color=color, alpha=0.35, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([r[f"{name}_index"] for r in rs], y + dy, s=40, color=color, edgecolors=SURFACE,
                   linewidths=1.5, zorder=3, label=label)
    ax.axvline(1, color=MUTED, lw=1)
    ax.text(1.0, -0.75, " as varied as people", color=MUTED, fontsize=9, va="center")
    ax.set_yticks(y, [r["label"] for r in rs], fontsize=9.5)
    for t, r in zip(ax.get_yticklabels(), rs):
        t.set_color(INK if r["key"] in HIGHLIGHT else INK2)
        if r["key"] in HIGHLIGHT:
            t.set_fontweight("bold")
    xmax = max(1.1, max(max(r["muse_index_ci95"][1], r["sdxl_index_ci95"][1]) for r in rs) * 1.04)
    ax.set_xlim(0, xmax)
    ax.set_ylim(len(rs) - 0.4, -0.9)  # most homogenized (by Muse) at the top
    ax.set_xlabel("AI spread / people's spread  (lower = AI more uniform)")
    ax.grid(True, axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="upper right", frameon=True, facecolor=SURFACE, edgecolor=GRID, fontsize=9.5)
    sm = RES["summary"]["sdxl_vs_human"]
    ax.set_title(f"How much more alike each AI draws a concept than people do\n"
                 f"median ratio: Muse {np.median([r['muse_index'] for r in rs]):.2f}, SDXL {sm['median_index']:.2f}"
                 f"; SDXL below people for {sm['concepts_with_index_below_1']} of {len(rs)} concepts",
                 fontsize=12, loc="left", color=INK)
    fig.text(0.01, 0.005, "Bars: 95% CI. Ranked by Muse. " + CREDIT, fontsize=7, color=MUTED)
    fig.tight_layout(rect=(0, 0.015, 1, 1))
    return save(fig, "index_ranked_two_ai")


def scatter_figure(rows: list[dict]) -> list[Path]:
    fig, ax = plt.subplots(figsize=(11, 7.6))
    xs = np.array([r["muse_spread"] for r in rows])
    ys = np.array([r["sdxl_spread"] for r in rows])
    hx = max(r["muse_spread_ci95"][1] for r in rows) * 1.06
    hy = max(r["sdxl_spread_ci95"][1] for r in rows) * 1.04
    d = min(hx, hy)
    ax.plot([0, d], [0, d], color=MUTED, lw=1, zorder=1)
    ax.text(d * 0.985, d * 0.96, "equally varied", color=MUTED, fontsize=9, ha="right", va="top")
    for r, x, yv in zip(rows, xs, ys):
        ax.plot([x, x], r["sdxl_spread_ci95"], color=GRID, lw=1.3, zorder=2, solid_capstyle="round")
        ax.plot(r["muse_spread_ci95"], [yv, yv], color=GRID, lw=1.3, zorder=2, solid_capstyle="round")
    ax.scatter(xs, ys, s=[70 if r["key"] in HIGHLIGHT else 40 for r in rows],
               c=[INK if r["key"] in HIGHLIGHT else INK2 for r in rows], edgecolors=SURFACE, linewidths=1.5,
               zorder=3)
    ax.set_xlim(0, hx)
    ax.set_ylim(0, hy)
    texts = _place_labels(ax, xs, ys, [r["label"] for r in rows], fontsize=8.5)
    for t, r, x, yv in zip(texts, rows, xs, ys):
        if r["key"] in HIGHLIGHT:
            t.set_fontweight("bold")
            t.set_color(INK)
        dx, dy = t.xyann
        if abs(dy) > 4:  # nudged away from its point: draw a leader line back to it
            ax.annotate("", (x, yv), xytext=(dx, dy), textcoords="offset points", zorder=1,
                        arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.6, "shrinkA": 0, "shrinkB": 3})
    ax.set_ylim(0, hy)
    ax.set_xlabel("How varied Meta Muse Image's drawings are (spread)")
    ax.set_ylabel("How varied Stable Diffusion XL's drawings are (spread)")
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    rho = RES["summary"]["rank_correlation_sdxl_vs_muse_spread"]
    above = int((ys > xs).sum())
    ax.set_title(f"SDXL varies more than Muse for {above} of {len(rows)} concepts\n"
                 f"do they vary the same concepts? rank correlation {rho['rho']:.2f} "
                 f"[95% CI {rho['ci95'][0]:.2f}, {rho['ci95'][1]:.2f}]", fontsize=12.5, loc="left", color=INK)
    fig.text(0.01, 0.01, CREDIT + " Bars: 95% CIs.", fontsize=7.5, color=MUTED)
    fig.subplots_adjust(left=0.1, right=0.97, top=0.88, bottom=0.11)
    return save(fig, "scatter_muse_vs_sdxl")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    rows = RES["concepts"]
    by = {r["key"]: r for r in rows}
    made = []
    for key in ("chair", "umbrella", "book"):
        if key in by:
            made += grid3_figure(key, by[key])
    made += index_figure(rows) + scatter_figure(rows)
    print("\n".join(str(p) for p in made))


if __name__ == "__main__":
    main()

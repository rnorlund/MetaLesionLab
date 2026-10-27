"""Plato's Bird figures, from $PLATO_BIRD_DIR/results.json, into $PLATO_BIRD_DIR/figures/; with --web, also
the page's picture strips (WebP) into metalesionlab/web/static/img/plato_bird/.

  name_<category>.{png,svg}    people's first answers next to Spark's 50 and Glimmer's 50 (T = 1)
  dominance_scatter.{png,svg}  top-answer share, AI vs. people, one dot per category (Spark and Glimmer)
  temperature.{png,svg}        mean top-answer share by sampling temperature
  pictures.png                 the 12 drawn categories, 12 Muse Image doodles each, with labels
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image, ImageDraw, ImageFont, ImageOps  # noqa: E402

from metalesionlab.plato_bird import BIRD_DIR, PICTURE_CATEGORIES  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FIG = BIRD_DIR / "figures"
WEB_IMG = REPO / "metalesionlab" / "web" / "static" / "img" / "plato_bird"
# validated together (dataviz validate_palette.js, all pairs, light surface #FCFCFB)
PEOPLE, SPARK, GLIMMER = "#C2410C", "#1D4ED8", "#0E9F6E"
INK, INK2, MUTED, GRID, SURFACE = "#111827", "#374151", "#6B7280", "#E5E7EB", "#FCFCFB"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#C3C2B7",
                     "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": INK2, "figure.facecolor": SURFACE,
                     "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE})


def nice(a: str) -> str:
    return a[:1].upper() + a[1:] if a and a != "(other)" else "Other answers"


def save(fig, name: str, svg: bool = True):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    if svg:
        fig.savefig(FIG / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def bars(ax, table, color, n_label, top=8):
    """Horizontal bars of answer shares (largest on top), value at the tip."""
    rows = [r for r in table if r[0] != "(other)"][:top]
    other = sum(r[1] for r in table) - sum(r[1] for r in rows)
    total = sum(r[1] for r in table)
    if other:
        rows = rows + [["(other)", other, other / total]]
    slots = top + 1  # every panel gets the same slots, so bars keep one thickness however few answers there are
    labels = [nice(r[0]) for r in rows]
    shares = [r[1] / total for r in rows]
    counts = [r[1] for r in rows]
    y = [slots - 1 - i for i in range(len(rows))]
    ax.barh(y, shares, height=0.62, color=[color if lab != "Other answers" else "#C3C2B7" for lab in labels])
    for yi, s, c in zip(y, shares, counts):
        ax.text(s + 0.02, yi, f"{c}", va="center", ha="left", fontsize=9, color=INK2)
    ax.set_yticks(y, labels, fontsize=10)
    ax.set_ylim(-0.6, slots - 0.4)
    ax.set_xlim(0, 1.12)
    ax.set_xticks([0, 0.5, 1], ["0", "50%", "100%"])
    ax.tick_params(axis="y", length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.set_title(n_label, loc="left", fontsize=11, color=INK, fontweight="bold")


def fig_name(res, category: str):
    row = next(r for r in res["categories"] + res["ai_only"] if r["category"] == category)
    t = row["tables"]
    panels = []
    if "human_first" in t:
        panels.append((t["human_first"], PEOPLE, f"{row['n_human']} people (UK), first answer"))
    panels.append((t["spark"], SPARK, "Muse Spark, 50 separate calls"))
    if t.get("glimmer_T1.0"):
        panels.append((t["glimmer_T1.0"], GLIMMER, "Muse Glimmer 30B, 50 samples (T = 1)"))
    fig, axes = plt.subplots(1, len(panels), figsize=(4.1 * len(panels), 3.6), sharex=True)
    for ax, (table, color, label) in zip(axes, panels):
        bars(ax, table, color, label)
    fig.suptitle(f"“Name one member of the category {category}.”", x=0.01, ha="left", fontsize=14,
                 color=INK, fontweight="bold")
    fig.text(0.01, -0.03, "Bars: share of answers; numbers: how many. People: Banks & Connell (2023), CC BY 4.0.",
             fontsize=8, color=MUTED)
    fig.tight_layout()
    save(fig, f"name_{category.replace(' ', '_')}")


# a few well-separated points per panel (the dense top row of the Spark panel stays unlabeled)
LABEL = {"spark": ["crime", "musical instrument", "gemstone"],
         "glimmer_T1.0": ["bird", "fruit", "hat", "tool", "fish", "month"]}


def fig_scatter(res):
    rows = res["categories"]
    srcs = [("spark", SPARK, "Muse Spark (50 calls)"), ("glimmer_T1.0", GLIMMER, "Muse Glimmer (50 samples, T = 1)")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.4), sharey=True)
    for ax, (src, color, title) in zip(axes, srcs):
        have = [r for r in rows if src in r]
        ax.plot([0, 1], [0, 1], color="#C3C2B7", lw=1.5, zorder=1, label="as concentrated as people")
        for dom, filled in (("Concrete", True), ("Abstract", False)):
            pts = [r for r in have if r["domain"] == dom]
            ax.scatter([r["human"]["dominance"] for r in pts], [r[src]["dominance"] for r in pts], s=34,
                       facecolors=color if filled else SURFACE, edgecolors=color, linewidths=1.4, zorder=3,
                       label=f"{dom} category ({len(pts)})")
        for r in have:
            if r["category"] in LABEL[src]:
                ax.annotate(r["category"], (r["human"]["dominance"], r[src]["dominance"]), xytext=(7, -3),
                            textcoords="offset points", fontsize=8.5, color=INK2)
        above = sum(r[src]["dominance"] > r["human"]["dominance"] + 1e-9 for r in have)
        d = res["summary"][src]["dominance"]
        ax.set_title(f"{title}\nabove people for {above} of {len(have)} categories; mean +{d['diff']['mean']:.2f} "
                     f"[{d['diff']['ci95'][0]:.2f}, {d['diff']['ci95'][1]:.2f}]" if d['diff']['mean'] >= 0 else
                     f"{title}\nabove people for {above} of {len(have)}; mean {d['diff']['mean']:+.2f} "
                     f"[{d['diff']['ci95'][0]:+.2f}, {d['diff']['ci95'][1]:+.2f}]", loc="left", fontsize=10.5, color=INK)
        ax.set_xlim(0, 1.03)
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("People: share of the most common first answer")
        ax.grid(color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.legend(frameon=False, fontsize=8.5, loc="lower right" if src == "spark" else "upper left")
    axes[0].set_ylabel("AI: share of its most common answer\n(at the people's sample size)")
    fig.suptitle("How stuck on one answer? 117 categories, AI vs. people", x=0.01, ha="left", fontsize=14,
                 color=INK, fontweight="bold")
    fig.tight_layout()
    save(fig, "dominance_scatter")


def fig_temperature(res):
    s = res["summary"]
    temps = sorted(s["logit_temperature"], key=float)
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot([float(t) for t in temps], [s["logit_temperature"][t]["dominance"]["mean"] for t in temps], color=GLIMMER,
            lw=2, marker="o", ms=5, label="Glimmer, its own probabilities re-weighted")
    samp = [(float(t), s[f"glimmer_T{t}"]["dominance"]["ai_mean"]["mean"]) for t in ("0.7", "1.0", "1.5")
            if f"glimmer_T{t}" in s]
    ax.scatter([a for a, _ in samp], [b for _, b in samp], s=60, facecolors=SURFACE, edgecolors=GLIMMER, lw=2, zorder=4,
               label="Glimmer, 50 samples (equal n)")
    ppl = s["spark"]["dominance"]["human_mean"]["mean"]
    ax.axhline(ppl, color=PEOPLE, lw=2)
    ax.text(2.13, ppl, f"people {ppl:.0%}", color=INK2, va="center", fontsize=9, clip_on=False)
    sp = s["spark"]["dominance"]["ai_mean"]["mean"]
    ax.axhline(sp, color=SPARK, lw=2)
    ax.text(2.13, sp, f"Spark, default {sp:.0%}", color=INK2, va="center", fontsize=9, clip_on=False)
    for k in s:
        if k.startswith("spark_T"):
            T = float(k.removeprefix("spark_T"))
            ax.scatter([T], [s[k]["dominance"]["mean"]], s=70, marker="D", color=SPARK, zorder=5,
                       label=f"Spark at T = {T:g} ({s[k]['n_categories']} categories, 20 calls each)")
    ax.set_xlabel("Sampling temperature")
    ax.set_ylabel("Mean share of the top answer")
    ax.set_ylim(0, 1.02)
    ax.set_xlim(0.4, 2.1)
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    ax.set_title("Diversity depends on the temperature", loc="left", fontsize=12, color=INK, fontweight="bold")
    fig.tight_layout()
    save(fig, "temperature")


def _font(size):
    for path in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
                 "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def tile(path: Path, cell: int) -> Image.Image:
    from metalesionlab.plato import ink_crop

    return ink_crop(Image.open(path).convert("RGB"), side=cell, margin=0.08)


def fig_pictures(res, web: bool):
    pics = res.get("pictures", {})
    cell, gap, label_w, pad = 120, 6, 330, 14
    f_big, f_small = _font(22), _font(15)
    rows = []
    for key, (phrase, _norm) in PICTURE_CATEGORIES.items():
        files = sorted((BIRD_DIR / "pictures" / key).glob("p*.png"), key=lambda p: int(p.stem[1:]))[:12]
        if not files:
            continue
        rows.append((key, phrase, [tile(f, cell) for f in files]))
    W = label_w + 12 * cell + 11 * gap + 2 * pad
    H = len(rows) * (cell + gap) + 2 * pad
    sheet = Image.new("RGB", (W, H), SURFACE)
    d = ImageDraw.Draw(sheet)
    for i, (key, phrase, tiles) in enumerate(rows):
        y = pad + i * (cell + gap)
        p = pics.get(key, {})
        lab = p.get("spark") or p.get("glimmer") or {}
        top = lab.get("top", ["?"])[0] if lab.get("top") else "?"
        share = lab.get("dominance") or 0
        named = (p.get("named_top", {}).get("spark") or ["?"])[0]
        d.text((pad, y + 18), f"“{phrase}”", fill=INK, font=f_big)
        d.text((pad, y + 52), f"draws: {top} ({round(share * 12)} of 12)", fill=INK2, font=f_small)
        d.text((pad, y + 76), f"names: {named}", fill=INK2, font=f_small)
        for j, t in enumerate(tiles):
            sheet.paste(t, (label_w + pad + j * (cell + gap), y))
        if web:
            WEB_IMG.mkdir(parents=True, exist_ok=True)
            strip = Image.new("RGB", (6 * 96 + 5 * 4, 2 * 96 + 4), "#FCFCFB")
            for j, f in enumerate(sorted((BIRD_DIR / "pictures" / key).glob("p*.png"), key=lambda p: int(p.stem[1:]))[:12]):
                strip.paste(tile(f, 96), ((j % 6) * 100, (j // 6) * 100))
            strip.save(WEB_IMG / f"{key}.webp", "WEBP", quality=72, method=6)
    FIG.mkdir(parents=True, exist_ok=True)
    sheet.save(FIG / "pictures.png", optimize=True)
    sheet.save(FIG / "pictures.webp", "WEBP", quality=80)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", action="store_true")
    args = ap.parse_args()
    res = json.loads((BIRD_DIR / "results.json").read_text())
    for cat in ("bird", "fish", "emotion", "fruit", "hat", "game", "gemstone", "musical instrument"):
        fig_name(res, cat)
    fig_scatter(res)
    fig_temperature(res)
    fig_pictures(res, args.web)
    print(f"figures in {FIG}")


if __name__ == "__main__":
    main()

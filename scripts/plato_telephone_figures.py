"""Plato's Telephone: figures and the page's pictures.

  python scripts/plato_telephone_figures.py [--web]

Reads $PLATO_TELEPHONE_DIR/results.json and the chain pictures. Writes to $PLATO_TELEPHONE_DIR/figures/:
  telephone_wall.png       one row per chain (30), generations 0-10 left to right, Muse's default at the right
  rows/<seed>_c<k>.png     each chain's row on its own
  convergence.{png,svg}    distance to the default, spread between and within seeds, words kept (three panels)
  last_words.png           each chair's descriptions at generations 0, 1, 5 and 10, the kind's name marked
With --web also the page's filmstrips, static/img/plato_telephone/<seed>_c<k>.webp (11 frames side by side)
and default_chair.webp (Muse's most typical default chair).
"""
import argparse
import json
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from metalesionlab import plato_telephone as T  # noqa: E402
from metalesionlab.plato import PLATO_DIR, ink_crop  # noqa: E402
from metalesionlab.plato_lifespan import proto_distances, prototype  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "metalesionlab" / "web" / "static" / "img" / "plato_telephone"
FIG = T.TELEPHONE_DIR / "figures"
BLUE, ORANGE, TEAL = "#1D4ED8", "#C2410C", "#0D9488"
INK, INK2, MUTED, GRID = "#111827", "#374151", "#6B7280", "#E1E0D9"
FONT = "/System/Library/Fonts/HelveticaNeue.ttc"


def font(size, bold=False):
    return ImageFont.truetype(FONT, size, index=1 if bold else 0)


def frame(path: Path, side: int) -> Image.Image:
    return ink_crop(Image.open(path).convert("RGB"), side=side)


def default_doodle(concept: str) -> Path:
    """The core default doodle nearest its own prototype: the most typical of Muse's default pictures."""
    z = np.load(PLATO_DIR / "embeddings" / "ai_doodle" / f"{concept}.npz")
    i = int(np.argmin(proto_distances(z["cls"], prototype(z["cls"]))))
    return PLATO_DIR / "ai" / "doodle" / concept / str(z["files"][i])


def row_image(seed: T.Seed, c: int, cell: int = 150, label_w: int = 190, gap: int = 6, with_default: bool = True,
              header: bool = False) -> Image.Image:
    d = T.chain_dir(seed, c)
    n = T.GENERATIONS + 1
    extra = (cell + 3 * gap + 24) if with_default else 0
    top = 30 if header else 0
    img = Image.new("RGB", (label_w + n * (cell + gap) + extra, cell + top + 8), "white")
    dr = ImageDraw.Draw(img)
    dr.text((8, top + cell // 2 - 22), seed.label, fill=INK, font=font(19, True))
    dr.text((8, top + cell // 2 + 2), f"chain {c + 1}" + ("  (control)" if seed.control else ""), fill=MUTED, font=font(15))
    for g in range(n):
        x = label_w + g * (cell + gap)
        p = d / T.pic_name(g)
        if p.exists():
            img.paste(frame(p, cell), (x, top))
        else:
            dr.rectangle((x, top, x + cell, top + cell), outline=GRID)
        if header:
            dr.text((x + cell // 2, 4), "start" if g == 0 else str(g), fill=MUTED, font=font(15), anchor="ma")
    if with_default:
        x = label_w + n * (cell + gap) + 2 * gap + 24
        dr.line((x - gap - 12, top + 10, x - gap - 12, top + cell - 10), fill=GRID, width=2)
        img.paste(frame(default_doodle(seed.concept), cell), (x, top))
        if header:
            dr.text((x + cell // 2, 4), "Muse's default", fill=BLUE, font=font(15, True), anchor="ma")
    return img


def wall():
    rows = []
    for i, s in enumerate(T.SEEDS):
        for c in range(T.CHAINS):
            rows.append(row_image(s, c, header=(i == 0 and c == 0)))
            if c == T.CHAINS - 1:
                rows.append(Image.new("RGB", (rows[-1].width, 14), "white"))
    title_h = 64
    W = max(r.width for r in rows)
    H = title_h + sum(r.height for r in rows)
    out = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(out)
    dr.text((8, 10), "Plato's Telephone: Muse Spark describes, Muse Image draws, 10 times over", fill=INK, font=font(26, True))
    dr.text((8, 42), "Each row is one chain. Generation 0 is Muse Image's own named-kind doodle; the last column is "
                     "Muse's default picture of the same thing.", fill=INK2, font=font(16))
    y = title_h
    for r in rows:
        out.paste(r, (0, y))
        y += r.height
    out.save(FIG / "telephone_wall.png")
    (FIG / "rows").mkdir(exist_ok=True)
    for s in T.SEEDS:
        for c in range(T.CHAINS):
            row_image(s, c, header=True).save(FIG / "rows" / f"{s.key}_c{c}.png")
    print("wall", out.size)


def convergence(r):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 10, "axes.edgecolor": GRID, "axes.linewidth": 1,
                         "xtick.color": MUTED, "ytick.color": MUTED, "axes.labelcolor": INK2, "text.color": INK})
    cv, ref, g = r["curves"], r["reference"], np.array(r["gens"])
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 5.0))

    def band(ax, name, col, label):
        m = np.array(cv[name]["mean"], float)
        lo = np.array([x[0] for x in cv[name]["ci95"]], float)
        hi = np.array([x[1] for x in cv[name]["ci95"]], float)
        ax.fill_between(g, lo, hi, color=col, alpha=0.09, lw=0)
        ax.plot(g, m, color=col, lw=2, solid_capstyle="round", label=label)
        ax.plot(g[[0, -1]], m[[0, -1]], "o", color=col, ms=6, mec="white", mew=2)
        return m

    ax = axes[0]
    first = True
    for k, v in r["per_seed"].items():
        if not v["control"]:
            ax.plot(g, [np.nan if x is None else x for x in v["d_proto"]], color=MUTED, lw=1, alpha=0.35,
                    label="one starting chair (mean of its 3 chains)" if first else None)
            first = False
    band(ax, "d_proto", BLUE, "8 starting chairs, mean (95% CI)")
    ax.axhline(ref["floor"]["chair"], color=INK2, lw=1)
    ax.text(10, ref["floor"]["chair"] + 0.012, "Muse's own default chairs", ha="right", color=INK2, fontsize=9)
    ax.set_title("Distance to Muse's default chair", loc="left", fontsize=11, fontweight="bold")
    ax.set_ylabel("cosine distance (DINOv2), lower = closer")
    ax.set_ylim(0, None)

    ax = axes[1]
    band(ax, "between", BLUE, "between different starting chairs")
    band(ax, "within", ORANGE, "between chains from the same chair")
    ax.axhline(ref["default_spread"]["chair"], color=INK2, lw=1)
    ax.text(10, ref["default_spread"]["chair"] + 0.012, "spread of Muse's default chairs", ha="right", color=INK2, fontsize=9)
    ax.set_title("How far apart the chains are", loc="left", fontsize=11, fontweight="bold")
    ax.set_ylabel("mean pairwise distance")
    ax.set_ylim(0, None)

    ax = axes[2]
    band(ax, "category_word", ORANGE, "description says \"chair\"")
    band(ax, "kind_word", BLUE, "description names the kind")
    band(ax, "label_kind", TEAL, "Spark labels the picture as the kind")
    ax.set_title("What the chain still says and shows", loc="left", fontsize=11, fontweight="bold")
    ax.set_ylabel("share of chains")
    ax.set_ylim(0, 1.05)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    for ax in axes:
        ax.legend(frameon=False, loc="upper left", bbox_to_anchor=(0, -0.16), fontsize=9)
        ax.set_xlabel("generation")
        ax.set_xticks(range(0, 11, 2))
        ax.grid(axis="y", color=GRID, lw=1)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(FIG / f"convergence.{ext}", dpi=200)
    plt.close(fig)


def last_words(r):
    """Descriptions of one chain per chair at generations 0, 1, 5 and 10; the kind's name is marked in blue.
    The chain shown is chain 1 for every seed (no choosing)."""
    gens = [0, 1, 5, 10]
    col_w, pad, lab_w = 430, 16, 170
    f, fb, fh = font(15), font(15, True), font(17, True)
    by = {(c["seed"], c["chain"]): c for c in r["chains"]}
    import re

    def wrap_words(text, width, pattern):
        """Lines of (word, marked) pairs; a word is marked if it overlaps a match of the kind's name in the
        whole text, so two-word names ("high chair", "bean bag") are marked too."""
        spans = [m.span() for m in re.finditer(pattern, text, flags=re.I)]
        words, pos = [], 0
        for w in text.split():
            at = text.find(w, pos)
            pos = at + len(w)
            words.append((w, any(a < pos and at < b for a, b in spans)))
        lines, cur = [], []
        for w in words:
            t = " ".join(x for x, _ in cur + [w])
            if f.getlength(t) > width and cur:
                lines.append(cur)
                cur = [w]
            else:
                cur = cur + [w]
        return lines + ([cur] if cur else [])

    blocks = []
    for s in T.CHAIR_SEEDS:
        ch = by[(s.key, 0)]
        cells = [wrap_words(ch["descriptions"][g] or "", col_w - 2 * pad, s.kind_word) for g in gens]
        blocks.append((s, ch, cells, max(len(x) for x in cells)))
    lh = 20
    H = 90 + sum(b[3] * lh + 28 for b in blocks)
    W = lab_w + len(gens) * col_w
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    dr.text((10, 10), "Last words: how Muse Spark's descriptions change along one chain per chair", fill=INK, font=font(22, True))
    dr.text((10, 40), "Blue: the kind's own name (rocking, throne, beanbag ...). Chain 1 of each chair, generations 0, 1, 5 and 10.",
            fill=INK2, font=f)
    for j, g in enumerate(gens):
        dr.text((lab_w + j * col_w + pad, 66), "start (generation 0)" if g == 0 else f"generation {g}", fill=MUTED, font=fb)
    y = 90
    for s, ch, cells, n in blocks:
        dr.line((10, y - 6, W - 10, y - 6), fill=GRID, width=1)
        dr.text((10, y), s.label, fill=INK, font=fh)
        for j, lines in enumerate(cells):
            x0 = lab_w + j * col_w + pad
            for li, line in enumerate(lines):
                x = x0
                for word, hit in line:
                    dr.text((x, y + li * lh), word, fill=BLUE if hit else INK2, font=fb if hit else f)
                    x += (fb if hit else f).getlength(word + " ")
        y += n * lh + 28
    img.save(FIG / "last_words.png")


def web():
    WEB.mkdir(parents=True, exist_ok=True)
    side = 176
    for s in T.SEEDS:
        for c in range(T.CHAINS):
            d = T.chain_dir(s, c)
            strip = Image.new("RGB", ((T.GENERATIONS + 1) * side, side), "white")
            for g in range(T.GENERATIONS + 1):
                p = d / T.pic_name(g)
                if p.exists():
                    strip.paste(frame(p, side), (g * side, 0))
            strip.convert("L").save(WEB / f"{s.key}_c{c}.webp", quality=58, method=6)
    frame(default_doodle("chair"), side).convert("L").save(WEB / "default_chair.webp", quality=58, method=6)
    total = sum(p.stat().st_size for p in WEB.glob("*.webp"))
    print(f"web pictures: {len(list(WEB.glob('*.webp')))} files, {total / 1024:.0f} KB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", action="store_true")
    args = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    r = json.loads((T.TELEPHONE_DIR / "results.json").read_text())
    wall()
    convergence(r)
    last_words(r)
    if args.web:
        web()


if __name__ == "__main__":
    main()

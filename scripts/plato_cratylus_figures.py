"""Plato's Cratylus figures ($CRATYLUS_DIR/figures/) and the web page's pictures (static/img/plato/cratylus/).

  bouba_kiki_wall.png   twelve Muse Image "bouba"s and twelve "kiki"s beside people's circles and stars
                        (Quick, Draw!, CC BY 4.0)
  roundness_by_word     solidity, corners and the human round-to-spiky axis for every word, with 95% CIs
  choice                p(round shape) for each word: Glimmer with the picture, Glimmer from words, Spark
  all_words.png         every drawing, one row per word
Reads $CRATYLUS_DIR/results.json (plato_cratylus_analyze.py analyze).
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from metalesionlab import plato_cratylus as pk  # noqa: E402
from metalesionlab.plato import ink_crop, load_dir  # noqa: E402

D = Path(os.environ.get("CRATYLUS_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/cratylus"))
FIG = D / "figures"
# flat in static/img/plato/ (the package data pattern and the Plato's Chair asset test expect no subfolders)
WEB = Path(__file__).resolve().parents[1] / "metalesionlab" / "web" / "static" / "img" / "plato"
FONT_SANS = "/System/Library/Fonts/Avenir Next.ttc"
FONT_SERIF_I = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"
INK, INK2, MUTED, GRID, PAPER = "#111827", "#374151", "#6B7280", "#E5E7EB", "#F7F6F1"
BLUE, ORANGE, AQUA, VIOLET, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#8a8984"
SOUND_COLOR = {"round": BLUE, "spiky": ORANGE, "mixed": VIOLET, "neutral": GRAY}


def font(path, size, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except OSError:
        return ImageFont.load_default()


def excluded() -> set:
    p = D / "excluded.json"
    return set(json.loads(p.read_text())) if p.exists() else set()


def ai_files(word: str) -> list[Path]:
    skip = excluded()
    s = pk.slug(word)
    return [p for p in load_dir(D / "ai" / s) if f"{s}/{p.name}" not in skip]


def tile(path: Path, cell: int) -> Image.Image:
    return ink_crop(Image.open(path).convert("RGB"), side=cell, margin=0.1)


def panel(paths: list[Path], cols: int, cell: int, gap: int, bg) -> Image.Image:
    rows = (len(paths) + cols - 1) // cols
    img = Image.new("RGB", (cols * cell + (cols - 1) * gap, rows * cell + (rows - 1) * gap), bg)
    for i, p in enumerate(paths):
        t = tile(p, cell)
        if bg != "white":  # drawings on the panel's paper color
            a = np.asarray(t.convert("L"), float) / 255
            paper = np.array(Image.new("RGB", (1, 1), bg).getpixel((0, 0)), float)
            t = Image.fromarray((a[..., None] * paper[None, None, :]).astype(np.uint8))
        img.paste(t, ((i % cols) * (cell + gap), (i // cols) * (cell + gap)))
    return img


def wall(out: Path, cell: int = 150) -> Image.Image:
    """Rows: AI 'bouba' beside people's circles, AI 'kiki' beside people's stars, and the twist: two made-up
    words with kiki's hard consonants and unrounded vowels ('keti', 'tepi'), which the AI draws round."""
    cols, gap = 4, 14
    paper = (252, 252, 251)
    rng = np.random.default_rng(7)
    circles = [load_dir(D / "human" / "circle")[i] for i in sorted(rng.choice(200, 12, replace=False))]
    stars = [load_dir(D / "human" / "star")[i] for i in sorted(rng.choice(200, 12, replace=False))]
    rows = [("bouba", ai_files("bouba")[:12], "Muse Image, asked for a shape called 'bouba'", BLUE,
             circles, "People's circles (Quick, Draw!)", ORANGE),
            ("kiki", ai_files("kiki")[:12], "Muse Image, asked for a shape called 'kiki'", BLUE,
             stars, "People's stars (Quick, Draw!)", ORANGE),
            ("keti", ai_files("keti")[:12], "...but a new word with kiki's sounds: 'keti'", BLUE,
             ai_files("tepi")[:12], "...and another: 'tepi' (Muse Image)", BLUE)]
    panels = [(panel(r[1], cols, cell, gap, paper), panel(r[4], cols, cell, gap, paper)) for r in rows]
    pw, ph = panels[0][0].size
    margin, head, mid, rowgap, label_w = 60, 96, 80, 56, 250
    W = label_w + 2 * pw + mid + 2 * margin
    H = len(rows) * (ph + head) + (len(rows) - 1) * rowgap + 2 * margin + 60
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    f_word, f_head, f_small = font(FONT_SERIF_I, 60), font(FONT_SANS, 28), font(FONT_SANS, 22)
    x_ai, x_h = margin + label_w, margin + label_w + pw + mid
    for i, (word, _, head_l, col_l, _, head_r, col_r) in enumerate(rows):
        y = margin + i * (ph + head + rowgap)
        tw = d.textlength(f"“{word}”", font=f_word)
        d.text((x_ai - 40 - tw, y + head + ph / 2 - 40), f"“{word}”", font=f_word, fill=INK)
        d.text((x_ai, y + 36), head_l, font=f_head, fill=col_l)
        d.text((x_h, y + 36), head_r, font=f_head, fill=col_r)
        for x, p in ((x_ai, panels[i][0]), (x_h, panels[i][1])):
            card = Image.new("RGB", (pw + 24, ph + 24), (252, 252, 251))
            img.paste(card, (x - 12, y + head - 12))
            img.paste(p, (x, y + head))
    d.text((margin, H - margin - 10), "Twelve separate pictures each; the AI never heard any of these words. Human "
           "drawings: Google Quick, Draw! (CC BY 4.0).", font=f_small, fill=MUTED)
    img.save(out)
    return img


def all_words(out: Path, cell: int = 96):
    words = [w for w in pk.WORDS]
    gap, label_w = 6, 330
    rows = []
    for w in words:
        files = ai_files(w.word)
        rows.append((w, files))
    W = label_w + 12 * (cell + gap)
    H = len(rows) * (cell + gap) + 20
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f = font(FONT_SANS, 22)
    for i, (w, files) in enumerate(rows):
        y = 10 + i * (cell + gap)
        d.text((10, y + cell / 2 - 14), w.word, font=f, fill=SOUND_COLOR[w.sound])
        for j, p in enumerate(files[:12]):
            img.paste(tile(p, cell), (label_w + j * (cell + gap), y))
    img.save(out)


def _style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


ORDER = ["bouba", "maluma", "bomu", "lobu", "bemi", "limi", "kotu", "tupo", "keti", "tepi", "kiki", "takete",
         "fana", "hasa", "nafa", "safa", pk.BASELINE]


def roundness_chart(res: dict, base: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    words = [w for w in ORDER if w in res["words"] and res["words"][w]["n"]]
    fig, axes = plt.subplots(1, 3, figsize=(10, 6.2), dpi=200, sharey=True)
    titles = {"solidity": "Solidity (area / convex hull)\n← spikier      rounder →",
              "corners": "Sharp corners\n← rounder      spikier →",
              "axis": "Position on people's round→spiky axis\n(0 = circles/clouds, 1 = stars/zigzags/lightning)"}
    y = np.arange(len(words))[::-1]
    for ax, m in zip(axes, ("solidity", "corners", "axis")):
        _style(ax)
        for yy, w in zip(y, words):
            e = res["words"][w][m]
            c = SOUND_COLOR[pk.BY_WORD[w].sound]
            if e["ci95"]:
                ax.hlines(yy, *e["ci95"], color=c, lw=2)
            ax.scatter([e["mean"]], [yy], s=46, color=c, edgecolor="white", linewidth=1.5, zorder=3)
        if m == "axis":
            ax.axvline(0, color=GRID, lw=1)
            ax.axvline(1, color=GRID, lw=1)
        ax.set_title(titles[m], fontsize=9.5, color=INK2, loc="left")
    axes[0].set_yticks(y, [w if w != pk.BASELINE else "no name" for w in words], fontsize=10)
    for t, w in zip(axes[0].get_yticklabels(), words):
        t.set_color(SOUND_COLOR[pk.BY_WORD[w].sound])
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", ls="", color=SOUND_COLOR[k], label=lab) for k, lab in
               (("round", "sounds round (soft consonants, rounded vowels)"), ("spiky", "sounds spiky (hard, unrounded)"),
                ("mixed", "mixed (grid)"), ("neutral", "neutral controls / no name"))]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    for ext in ("png", "svg"):
        fig.savefig(base.with_suffix(f".{ext}"), facecolor="white")
    plt.close(fig)


def choice_chart(res: dict, base: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ch = res.get("choice", {})
    words = [w for w in ORDER if w != pk.BASELINE]
    fig, ax = plt.subplots(figsize=(7.6, 5.6), dpi=200)
    _style(ax)
    y = np.arange(len(words))[::-1]
    series = [("glimmer_picture", "Glimmer, picture", BLUE, -0.2), ("glimmer_text", "Glimmer, words only", AQUA, 0.0),
              ("spark", "Spark, picture (6 answers)", VIOLET, 0.2)]
    for key, label, color, dy in series:
        data = ch.get(key, {})
        xs = [data.get(w, {}).get("p_round") for w in words]
        ok = [i for i, x in enumerate(xs) if x is not None]
        ax.scatter([xs[i] for i in ok], [y[i] + dy for i in ok], s=34, color=color, edgecolor="white", linewidth=1.2,
                   label=label, zorder=3)
    ax.axvline(0.5, color=MUTED, lw=1)
    ax.scatter([0.82], [y[words.index("bouba")] + 0.42], marker="D", s=40, color=ORANGE, zorder=4,
               label="People, Ćwiek et al. 2022 (first trials)")
    ax.scatter([1 - 0.68], [y[words.index("kiki")] + 0.42], marker="D", s=40, color=ORANGE, zorder=4)
    ax.set_yticks(y, words, fontsize=10)
    for t, w in zip(ax.get_yticklabels(), words):
        t.set_color(SOUND_COLOR[pk.BY_WORD[w].sound])
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("Probability of picking the round shape", color=INK2)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(base.with_suffix(f".{ext}"), facecolor="white")
    plt.close(fig)


def web_assets(wall_img: Image.Image):
    WEB.mkdir(parents=True, exist_ok=True)
    w = wall_img.copy()
    w.thumbnail((1600, 1600))
    w.save(WEB / "cratylus_wall.webp", quality=82, method=6)
    pair_dir = WEB
    for seed in (0, 3):
        img = pk.pair_image(pk.round_shape(seed), pk.spiky_shape(seed))
        img.thumbnail((640, 320))
        img.save(pair_dir / f"cratylus_pair_{seed}.webp", quality=85, method=6)
    # a strip per word for the page's word picker (6 drawings each)
    for w in pk.WORDS:
        files = ai_files(w.word)[:6]
        if not files:
            continue
        cell, gap = 140, 8
        strip = Image.new("RGB", (6 * cell + 5 * gap, cell), "white")
        for j, p in enumerate(files):
            strip.paste(tile(p, cell), (j * (cell + gap), 0))
        strip.save(WEB / f"cratylus_word_{pk.slug(w.word)}.webp", quality=78, method=6)
    total = sum(p.stat().st_size for p in WEB.glob("cratylus_*.webp"))
    print(f"web assets: {len(list(WEB.glob('cratylus_*.webp')))} files, {total / 1024:.0f} KB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-web", action="store_true")
    args = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.loads((D / "results.json").read_text())
    w = wall(FIG / "bouba_kiki_wall.png")
    all_words(FIG / "all_words.png")
    roundness_chart(res, FIG / "roundness_by_word")
    choice_chart(res, FIG / "choice")
    if not args.no_web:
        web_assets(w)
    print("figures ->", FIG)


if __name__ == "__main__":
    main()

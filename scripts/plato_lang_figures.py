"""Figures for the site and the video: doodle grids, average doodles, centroid heatmap, group-share plot.

Reads $PLATO_LANG_DIR/{ai,human,results.json}; writes $PLATO_LANG_DIR/figures/.
Native-script labels need Pillow with libraqm (for Arabic and Devanagari shaping) and macOS fonts.
Usage: python scripts/plato_lang_figures.py [--concepts house,chair] [--seed 0]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato_lang import CONCEPTS, COUNTRIES, LANGS, OUT, canonical_ai  # noqa: E402

FIG = OUT / "figures"
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
AI_COLOR, HUMAN_COLOR = "#2a78d6", "#eb6834"  # categorical slots 1 and 2
CREDIT = "Drawings: Quick, Draw! by Google, CC BY 4.0"
SHOWN = 4  # doodles per group in the grids

FONTS = {
    "latin": "/System/Library/Fonts/HelveticaNeue.ttc",
    "hi": "/System/Library/Fonts/Kohinoor.ttc",
    "zh": "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "ar": "/System/Library/Fonts/GeezaPro.ttc",
}


def font(size: int, script: str = "latin", bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONTS.get(script, FONTS["latin"])
    index = 1 if bold and script == "latin" else 0
    return ImageFont.truetype(path, size, index=index, layout_engine=ImageFont.Layout.RAQM)


def text(draw, xy, s, size, script="latin", fill=INK, anchor="mm", bold=False):
    kw = {"direction": "rtl"} if script == "ar" else {}
    draw.text(xy, s, font=font(size, script, bold), fill=fill, anchor=anchor, **kw)


def pick(paths: list[Path], k: int, seed: int) -> list[Path]:
    rng = np.random.default_rng(seed)
    return [paths[i] for i in sorted(rng.choice(len(paths), size=min(k, len(paths)), replace=False))]


def clean_ai(path: Path) -> Image.Image:
    """The AI doodle as drawn, with grey paper whitened so the grids read evenly."""
    gray = ImageOps.autocontrast(Image.open(path).convert("L"), cutoff=1)
    return gray.point(lambda v: 255 if v > 190 else v)


def tile(img: Image.Image, side: int) -> Image.Image:
    img = img.convert("RGB")
    img.thumbnail((side, side), Image.LANCZOS)
    out = Image.new("RGB", (side, side), "white")
    out.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return out


def grid(concept: str, domain: str, words: dict, seed: int) -> Path:
    """Columns = languages (AI) or countries (people); SHOWN random doodles each."""
    groups = list(LANGS) if domain == "ai" else list(COUNTRIES)
    cell, gap, left, top, bottom = 230, 18, 60, 210, 70
    W = left * 2 + len(groups) * cell + (len(groups) - 1) * gap
    H = top + SHOWN * cell + (SHOWN - 1) * gap + bottom
    fig = Image.new("RGB", (W, H), SURFACE)
    d = ImageDraw.Draw(fig)
    title = (f"“{concept}” drawn by Muse Image, prompted in six languages" if domain == "ai"
             else f"“{concept}” drawn by people in six countries")
    text(d, (W / 2, 52), title, 40, bold=True)
    for gi, g in enumerate(groups):
        x = left + gi * (cell + gap)
        if domain == "ai":
            text(d, (x + cell / 2, 125), words[g][concept], 40, script=g if g in FONTS else "latin")
            text(d, (x + cell / 2, 175), LANGS[g], 24, fill=INK2)
        else:
            text(d, (x + cell / 2, 135), COUNTRIES[g], 30)
        paths = sorted((OUT / domain / g / concept).glob("*.png"))
        for r, p in enumerate(pick(paths, SHOWN, seed + gi)):
            img = Image.open(p) if domain == "human" else clean_ai(p)
            fig.paste(tile(img, cell), (x, top + r * (cell + gap)))
    note = ("Muse Image 1.0 · 4 of 10 doodles per language, picked at random" if domain == "ai"
            else f"{CREDIT} · 4 of 200 recognized drawings per country, picked at random")
    text(d, (W / 2, H - 34), note, 22, fill=MUTED)
    FIG.mkdir(parents=True, exist_ok=True)
    out = FIG / f"grid_{domain}_{concept}.png"
    fig.save(out, optimize=True)
    return out


def average_image(paths: list[Path], domain: str) -> Image.Image:
    """Pixel average of the centred doodles: a ghost of the group's 'ideal' drawing."""
    acc = None
    for p in paths:
        img = canonical_ai(p) if domain == "ai" else Image.open(p).convert("L")
        a = 255.0 - np.asarray(img, dtype=np.float32)  # ink = high
        acc = a if acc is None else acc + a
    ink = acc / len(paths)
    ink = ink / max(ink.max(), 1e-6)  # stretch so the strongest shared line is black
    return ImageOps.autocontrast(Image.fromarray((255 - 255 * ink).astype(np.uint8)), cutoff=0.2)


def averages(concept: str, words: dict) -> Path:
    """Row 1: AI average per language. Row 2: people's average per country, matched columns."""
    langs, countries = list(LANGS), list(COUNTRIES)
    cell, gap, left, top = 230, 18, 60, 120
    W = left * 2 + 6 * cell + 5 * gap
    H = top + 2 * (cell + 95) + 80
    fig = Image.new("RGB", (W, H), SURFACE)
    d = ImageDraw.Draw(fig)
    text(d, (W / 2, 52), f"The average “{concept}”", 44, bold=True)
    for row, (domain, groups) in enumerate((("ai", langs), ("human", countries))):
        y = top + row * (cell + 95)
        label = "Muse Image, by prompt language (10 each)" if domain == "ai" else "People, by country (200 each)"
        text(d, (left, y + 12), label, 24, fill=AI_COLOR if domain == "ai" else HUMAN_COLOR, anchor="lm", bold=True)
        for gi, g in enumerate(groups):
            x = left + gi * (cell + gap)
            paths = sorted((OUT / domain / g / concept).glob("*.png"))
            fig.paste(tile(average_image(paths, domain), cell), (x, y + 32))
            name = LANGS[g] if domain == "ai" else COUNTRIES[g]
            text(d, (x + cell / 2, y + 32 + cell + 26), name, 24, fill=INK2)
    text(d, (W / 2, H - 34), f"Pixel average of the centred doodles · {CREDIT}", 22, fill=MUTED)
    out = FIG / f"average_{concept}.png"
    fig.save(out, optimize=True)
    return out


def heatmap(results: dict) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 13, "text.color": INK,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
    ramp = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
    cmap = LinearSegmentedColormap.from_list("blue", ramp)
    heat = results["heatmap"]
    mats = {dom: np.array(heat[dom]["between"]) * 1000 for dom in ("ai", "human")}
    vmax = max(m.max() for m in mats.values())
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.4), facecolor=SURFACE)
    names = {"ai": [LANGS[g] for g in heat["ai"]["groups"]], "human": [COUNTRIES[g] for g in heat["human"]["groups"]]}
    titles = {"ai": "Muse Image: prompt language vs prompt language", "human": "People: country vs country"}
    for ax, dom in zip(axes, ("ai", "human")):
        m = mats[dom].copy()
        np.fill_diagonal(m, np.nan)
        ax.imshow(m, cmap=cmap, vmin=0, vmax=vmax)
        k = len(names[dom])
        ax.set_xticks(range(k), names[dom], rotation=35, ha="right")
        ax.set_yticks(range(k), names[dom])
        ax.set_title(titles[dom], fontsize=14, color=INK, pad=12)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(length=0)
        for i in range(k):
            for j in range(k):
                if i != j:
                    v = mats[dom][i, j]
                    ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=11,
                            color="#ffffff" if v > 0.55 * vmax else INK)
    fig.suptitle("How far apart are the average doodles? (mean over 10 concepts)", fontsize=17, color=INK, y=0.98)
    fig.text(0.5, 0.015, "DINOv2 distance between group averages, minus what sampling noise alone gives (×1000; "
             "0 = no difference). " + CREDIT, ha="center", fontsize=10.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    out = FIG / "heatmap_centroids.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return out


def share_plot(results: dict) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "Helvetica Neue", "font.size": 13, "text.color": INK,
                         "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2})
    comp = results["comparison"]
    order = sorted(CONCEPTS, key=lambda c: comp[c]["share_ai"][0])
    fig, ax = plt.subplots(figsize=(10, 6.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    y = np.arange(len(order))
    for key, color, dy, label in (("share_ai", AI_COLOR, 0.17, "Muse Image: language of the prompt"),
                                  ("share_human", HUMAN_COLOR, -0.17, "People: country")):
        est = np.array([comp[c][key][0] for c in order]) * 100
        lo = np.array([comp[c][key][1] for c in order]) * 100
        hi = np.array([comp[c][key][2] for c in order]) * 100
        ax.hlines(y + dy, lo, hi, color=color, lw=2)
        ax.plot(est, y + dy, "o", ms=9, color=color, mec=SURFACE, mew=2, label=label)
    ax.axvline(0, color="#c3c2b7", lw=1)
    ax.set_yticks(y, order)
    ax.set_xlabel("Share of the variation in the drawings explained by group (%), 95% CI")
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(length=0)
    ax.legend(loc="lower right", frameon=False)
    ax.set_title("Which concepts change with language or country?", fontsize=17, color=INK, loc="left", pad=14)
    fig.text(0.01, 0.01, f"Muse Image: 10 doodles × 6 languages. People: 200 drawings × 6 countries. DINOv2 embeddings. "
             f"{CREDIT}", fontsize=9.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = FIG / "share_by_concept.png"
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return out


def contact_sheet(lang: str, words: dict) -> Path:
    """Check sheet: every concept for one language, 5 doodles each (for eyeballing, not publication)."""
    cell = 150
    fig = Image.new("RGB", (5 * cell + 200, len(CONCEPTS) * cell), "white")
    d = ImageDraw.Draw(fig)
    for r, c in enumerate(CONCEPTS):
        text(d, (100, r * cell + cell / 2 - 14), c, 20)
        text(d, (100, r * cell + cell / 2 + 14), words[lang][c], 20, script=lang if lang in FONTS else "latin")
        for k, p in enumerate(sorted((OUT / "ai" / lang / c).glob("*.png"))[:5]):
            fig.paste(tile(Image.open(p), cell - 6), (200 + k * cell, r * cell + 3))
    out = FIG / "check" / f"sheet_{lang}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.save(out, optimize=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concepts", default=",".join(CONCEPTS))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sheets", action="store_true", help="only the per-language check sheets")
    args = ap.parse_args()
    prompts = json.loads((OUT / "prompts.json").read_text())
    words = {lg: {c: v["word"] for c, v in items.items()} for lg, items in prompts.items()}
    FIG.mkdir(parents=True, exist_ok=True)
    if args.sheets:
        for lang in LANGS:
            print(contact_sheet(lang, words))
        return
    for c in args.concepts.split(","):
        print(grid(c, "ai", words, args.seed))
        print(grid(c, "human", words, args.seed))
        print(averages(c, words))
    results = json.loads((OUT / "results.json").read_text())
    print(heatmap(results))
    print(share_plot(results))


if __name__ == "__main__":
    main()

"""Plato's Cave figures ($CAVE_DIR/figures/) and the web page's pictures (static/img/plato/cave/, WebP).

  cave_wall.png          the hero: shadows on a firelit cave wall, with Muse Glimmer's guess under each
  versions_strip.png     original, outline, silhouette and shadow for a few objects
  accuracy_by_version    Glimmer (100 pictures) and Spark (50) by version, with 95% CIs
  word_lens              mean p(correct name) after each decoder layer, by version
  people_vs_ai           people's silhouette identification (Wagemans et al. 2008) vs Glimmer, 78 concepts
                         (kept out of the repository: the human data carry no licence)
Reads $CAVE_DIR/results.json (plato_cave_analyze.py analyze).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402

from metalesionlab import plato_cave as pc  # noqa: E402

D = pc.CAVE_DIR
FIG = D / "figures"
# flat in static/img/plato/ (the package data pattern and the Plato's Chair asset test expect no subfolders)
WEB = Path(__file__).resolve().parents[1] / "metalesionlab" / "web" / "static" / "img" / "plato"
FONT_SERIF_I = "/System/Library/Fonts/Supplemental/Georgia Italic.ttf"
FONT_SERIF = "/System/Library/Fonts/Supplemental/Georgia.ttf"
FONT_SANS = "/System/Library/Fonts/Avenir Next.ttc"
# chart colors (the dataviz reference palette; blue = AI, orange = people, as on the Plato's Chair page)
INK, INK2, MUTED, GRID = "#111827", "#374151", "#6B7280", "#E5E7EB"
BLUE, ORANGE, AQUA, VIOLET = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6"
VERSION_LABEL = {"original": "Original", "outline": "Outline", "silhouette": "Silhouette", "shadow": "Cast shadow"}
WALL_WORDS = ["rabbit", "scissors", "hat", "anchor", "guitar", "bicycle", "glove", "cat", "igloo", "helicopter",
              "bread", "umbrella"]


def font(path, size, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except OSError:
        return ImageFont.load_default()


def rock_wall(w: int, h: int, seed: int = 3) -> np.ndarray:
    """A firelit cave wall: a noise height map shaded as rock relief, warm light from below left and a dark
    vignette. RGB float 0-1."""
    rng = np.random.default_rng(seed)
    height = np.zeros((h, w))
    for scale, amp in ((120, 1.0), (50, 0.55), (18, 0.3), (6, 0.12), (2, 0.05)):
        n = ndi.gaussian_filter(rng.normal(0, 1, (h, w)), scale)
        height += amp * n / (n.std() or 1)
    gy, gx = np.gradient(height)
    relief = 1 + 6.0 * (-0.6 * gx + 0.8 * gy)  # lit from below left
    tone = (height - height.min()) / (height.max() - height.min())
    yy, xx = np.mgrid[0:h, 0:w]
    fire = np.exp(-(((xx - 0.15 * w) / (0.8 * w)) ** 2 + ((yy - 1.1 * h) / (0.9 * h)) ** 2))
    glow = 0.22 + 1.05 * fire
    vign = 1 - 0.6 * (((xx / w - 0.5) * 1.35) ** 2 + ((yy / h - 0.42) * 1.25) ** 2)
    light = np.clip(glow * vign, 0.04, 1.35)
    base = (0.55 + 0.25 * tone) * np.clip(relief, 0.6, 1.4)
    warm = np.array([1.0, 0.68, 0.42])
    return np.clip(base[..., None] * light[..., None] * warm[None, None, :] * 0.92, 0, 1)


def shadow_alpha(mask: np.ndarray, side: int, shear: float = 0.32, squash: float = 0.92, blur: float = 0.014) -> np.ndarray:
    """The silhouette sheared, squashed and blurred like the experiment's cast shadow, as alpha 0-1."""
    small = Image.fromarray((mask * 255).astype(np.uint8)).resize((side, side), Image.LANCZOS)
    pad = int(side * (shear + 0.1))
    canvas = Image.new("L", (side + pad, side), 0)
    canvas.paste(small, (0, 0))
    inv = (1, shear / squash, -shear * side / squash, 0, 1 / squash, side - side / squash)
    out = canvas.transform(canvas.size, Image.AFFINE, inv, resample=Image.BILINEAR)
    out = out.filter(ImageFilter.GaussianBlur(blur * side))
    return np.asarray(out, float) / 255


def silhouette_of(word: str) -> np.ndarray:
    img = Image.open(D / "stimuli" / "silhouette" / f"{word}.png").convert("L")
    return np.asarray(img) < 128


MASS_NOUNS = {"bread"}


def with_article(word: str) -> str:
    return word if word in MASS_NOUNS else ("an " if word[0] in "aeiou" else "a ") + word


def cave_wall(res: dict, words: list[str], cols: int = 4, cell: int = 420, out: Path | None = None) -> Image.Image:
    per = res["survival"]["per_item"]
    rows = (len(words) + cols - 1) // cols
    label_h = 110
    W, H = cols * cell + 120, rows * (cell + label_h) + 140
    wall = rock_wall(W, H)
    for i, word in enumerate(words):
        cx = 60 + (i % cols) * cell
        cy = 70 + (i // cols) * (cell + label_h)
        a = shadow_alpha(silhouette_of(word), int(cell * 0.78))
        h, w = a.shape
        x0, y0 = cx + (cell - w) // 2 + 10, cy + (cell - h) // 2
        region = wall[y0:y0 + h, x0:x0 + w]
        hh, ww = region.shape[:2]
        region *= (1 - 0.78 * a[:hh, :ww])[..., None]
    img = Image.fromarray((wall * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    f_guess, f_true = font(FONT_SERIF_I, 44), font(FONT_SANS, 24)
    for i, word in enumerate(words):
        cx = 60 + (i % cols) * cell
        ty = 70 + (i // cols) * (cell + label_h) + cell - 24
        said = per[word]["shadow"]["said"].strip().rstrip(".")
        said = said if len(said) <= 22 else said[:20] + "…"
        ok = per[word]["shadow"]["code"] == "Correct"
        col = (246, 236, 214) if ok else (255, 166, 77)
        text = f"“{said.lower() if ok else said}”"
        tw = d.textlength(text, font=f_guess)
        d.text((cx + (cell - tw) / 2, ty), text, font=f_guess, fill=col)
        sub = "correct" if ok else f"it was {with_article(word)}"
        sw = d.textlength(sub, font=f_true)
        d.text((cx + (cell - sw) / 2, ty + 56), sub, font=f_true, fill=(236, 222, 198) if ok else (240, 208, 168))
    f_title = font(FONT_SANS, 30)
    acc = res["glimmer_accuracy"]["shadow"]["accuracy"]
    cap = (f"What Muse Glimmer said for each shadow · it named {round(acc * 100)} of 100 shadows correctly")
    d.text((60, H - 60), cap, font=f_title, fill=(222, 204, 178))
    if out:
        img.save(out)
    return img


def versions_strip(words: list[str], out: Path, cell: int = 220) -> Image.Image:
    gap = 10
    W = len(pc.VERSIONS) * cell + (len(pc.VERSIONS) - 1) * gap
    H = len(words) * cell + (len(words) - 1) * gap + 50
    img = Image.new("RGB", (W, H), "#F7F6F1")
    d = ImageDraw.Draw(img)
    f = font(FONT_SANS, 22)
    for j, v in enumerate(pc.VERSIONS):
        t = VERSION_LABEL[v]
        d.text((j * (cell + gap) + (cell - d.textlength(t, font=f)) / 2, 10), t, font=f, fill=INK)
        for i, w in enumerate(words):
            tile = Image.open(D / "stimuli" / v / f"{w}.png").convert("RGB").resize((cell, cell), Image.LANCZOS)
            img.paste(tile, (j * (cell + gap), 50 + i * (cell + gap)))
    img.save(out)
    return img


def _style(ax):
    import matplotlib.pyplot as plt  # noqa: F401

    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=10)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def accuracy_chart(res: dict, base: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
    _style(ax)
    xs = np.arange(len(pc.VERSIONS))
    g = res["glimmer_accuracy"]
    ys = [g[v]["accuracy"] * 100 for v in pc.VERSIONS]
    lo = [g[v]["ci95"][0] * 100 for v in pc.VERSIONS]
    hi = [g[v]["ci95"][1] * 100 for v in pc.VERSIONS]
    ax.plot(xs - 0.08, ys, color=BLUE, lw=2, zorder=3)
    ax.vlines(xs - 0.08, lo, hi, color=BLUE, lw=2, zorder=3)
    ax.scatter(xs - 0.08, ys, s=60, color=BLUE, edgecolor="white", linewidth=2, zorder=4, label="Muse Glimmer 30B (100 pictures)")
    if "spark" in res:
        s = res["spark"]["accuracy"]
        ys2 = [s[v]["accuracy"] * 100 for v in pc.VERSIONS]
        ax.plot(xs + 0.08, ys2, color=VIOLET, lw=2, zorder=3)
        ax.vlines(xs + 0.08, [s[v]["ci95"][0] * 100 for v in pc.VERSIONS], [s[v]["ci95"][1] * 100 for v in pc.VERSIONS],
                  color=VIOLET, lw=2, zorder=3)
        ax.scatter(xs + 0.08, ys2, s=60, color=VIOLET, edgecolor="white", linewidth=2, zorder=4,
                   label=f"Muse Spark ({res['spark']['n_items']} of the pictures)")
    hp = res["human"]["published"]
    for x, v, key in ((1, "outline", "outline_mean_260"), (2, "silhouette", "silhouette_mean_260")):
        ax.scatter([x + 0.24], [hp[key] * 100], marker="D", s=46, color=ORANGE, edgecolor="white", linewidth=1.5,
                   zorder=4, label="People, Snodgrass–Vanderwart drawings\n(Wagemans et al. 2008, 260 objects)" if v == "outline" else None)
    ax.set_xticks(xs, [VERSION_LABEL[v] for v in pc.VERSIONS], fontsize=11, color=INK)
    ax.set_ylim(0, 103)
    ax.set_ylabel("Named correctly (%)", color=INK2, fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    for x, y in zip(xs, ys):
        ax.annotate(f"{y:.0f}%", (x - 0.08, y), textcoords="offset points", xytext=(-10, 0), ha="right",
                    va="center", fontsize=10, color=INK)
    ax.set_xlim(-0.5, len(xs) - 0.5)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(base.with_suffix(f".{ext}"), facecolor="white")
    plt.close(fig)


def lens_chart(res: dict, base: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7.2, 4.0), dpi=200)
    _style(ax)
    colors = {"original": INK, "outline": AQUA, "silhouette": BLUE, "shadow": ORANGE}
    for v in pc.VERSIONS:
        y = np.array(res["word_lens"][v]["mean_p_name_by_layer"])
        x = np.arange(1, len(y) + 1)
        ax.plot(x, y, color=colors[v], lw=2, label=VERSION_LABEL[v])
        dy = {"silhouette": 5, "outline": -6}.get(v, 0)
        ax.annotate(VERSION_LABEL[v], (x[-1], y[-1]), textcoords="offset points", xytext=(6, dy), va="center",
                    fontsize=9, color=INK2)
    ax.set_xlim(30, 57)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Decoder layer (the word lens reads the model's guess after each one)", color=INK2, fontsize=10)
    ax.set_ylabel("Mean p(correct name)", color=INK2, fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="upper left", title="100 pictures each", title_fontsize=9)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(base.with_suffix(f".{ext}"), facecolor="white")
    plt.close(fig)


def people_vs_ai(res: dict, base: Path):
    """Concept-level scatter (outside the repository only)."""
    import csv

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    norms = {}
    with (D / "human_norms" / "silhouette_norms.csv").open() as f:
        for r in csv.DictReader(f):
            if r["project_concept"]:
                norms[r["project_concept"]] = float(r["silhouette_rate"])
    per = res["survival"]["per_item"]
    words = [w for w in res["human"]["shared"]]
    x = np.array([norms[w] for w in words])
    y = np.array([per[w]["silhouette"]["p_name"] or 0 for w in words])
    ok = np.array([per[w]["silhouette"]["code"] == "Correct" for w in words])
    fig, ax = plt.subplots(figsize=(7.2, 5.0), dpi=200)
    _style(ax)
    ax.scatter(x[ok], y[ok], s=36, color=BLUE, edgecolor="white", linewidth=1.5, label="Glimmer named the silhouette")
    ax.scatter(x[~ok], y[~ok], s=40, color=ORANGE, marker="X", edgecolor="white", linewidth=1,
               label="Glimmer got it wrong")
    labelled = sorted([(a, b, w) for w, a, b in zip(words, x, y) if a < 30 or b < 0.3], key=lambda t: (t[1] < 0.3, t[0]))
    k = 0
    for a, b, w in labelled:
        dy = 3 + (12 * (k % 3) if b < 0.1 else 0)
        k += b < 0.1
        ax.annotate(w, (a, b), textcoords="offset points", xytext=(5, dy), fontsize=8, color=INK2)
    rho = res["human"]["silhouette"]["rho_p_name"]
    ax.set_xlabel("People who identified the silhouette (%), Wagemans et al. 2008", color=INK2, fontsize=10)
    ax.set_ylabel("Glimmer's p(correct name), silhouette", color=INK2, fontsize=10)
    ax.set_title(f"{len(words)} concepts · Spearman rho {rho['rho']:.2f} [{rho['ci95'][0]:.2f}, {rho['ci95'][1]:.2f}]",
                 fontsize=10, color=INK2, loc="left")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(base.with_suffix(f".{ext}"), facecolor="white")
    plt.close(fig)


def web_assets(res: dict, game_words: list[str], wall: Image.Image, strip: Image.Image):
    WEB.mkdir(parents=True, exist_ok=True)
    w = wall.copy()
    w.thumbnail((1600, 1600))
    w.save(WEB / "cave_wall.webp", quality=80, method=6)
    s = strip.copy()
    s.thumbnail((900, 2000))
    s.save(WEB / "cave_versions.webp", quality=82, method=6)
    for word in game_words:
        for v in ("shadow", "original"):
            im = Image.open(D / "stimuli" / v / f"{word}.png").convert("RGB").resize((320, 320), Image.LANCZOS)
            im.save(WEB / f"cave_{v}_{word}.webp", quality=78, method=6)
    total = sum(p.stat().st_size for p in WEB.glob("cave_*.webp"))
    print(f"web assets: {len(list(WEB.glob('cave_*.webp')))} files, {total / 1024:.0f} KB")


GAME_WORDS = ["rabbit", "anchor", "hat", "scissors", "glove", "bicycle", "sock", "guitar", "igloo", "cat",
              "eye", "helicopter"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-web", action="store_true")
    args = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    res = json.loads((D / "results.json").read_text())
    wall = cave_wall(res, WALL_WORDS, out=FIG / "cave_wall.png")
    strip = versions_strip(["cat", "scissors", "bicycle", "clock"], FIG / "versions_strip.png")
    accuracy_chart(res, FIG / "accuracy_by_version")
    lens_chart(res, FIG / "word_lens")
    people_vs_ai(res, FIG / "people_vs_ai")
    if not args.no_web:
        web_assets(res, GAME_WORDS, wall, strip)
    print("figures ->", FIG)


if __name__ == "__main__":
    main()

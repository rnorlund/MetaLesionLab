"""Plato's Forms: figures (PNG/SVG in $PLATO_FORMS_DIR/figures/) and the small WebP tiles the /plato/forms page
shows (metalesionlab/web/static/img/plato_forms/).

Usage: python -I scripts/plato_forms_figures.py [--only clock|concepts]
(after plato_forms_clock.py analyze and plato_forms_concepts.py analyze)

- clock_wall.png        16 Muse Image clocks, 16 SDXL clocks and 16 people's clocks, no time asked
- clock_faces.{png,svg} every read time drawn as a pair of hands on one dial, per source ("clock-face heatmap")
- clock_asked.{png,svg} requested time against the time drawn, Muse and SDXL, doodles and photos
- clock_average.png     the pixel average of each set of ink-cropped clocks (a model-free check)
- clock_asked_strip.png one Muse doodle per requested time
- forms_<bed|table>.png five rows of 16: Muse usual, any kind, named kinds, SDXL, people
- forms_rank.{png,svg}  the 35 core concepts' homogenization index with the bed and the table placed among them
Human drawings: Google Quick, Draw! (CC BY 4.0); a random 16 of the 200 cached drawings (seeded).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab.plato import PLATO_DIR, grid, ink_crop, load_dir  # noqa: E402
from metalesionlab.plato_forms import (CLOCK_TIMES, FORMS_CONCEPTS, FORMS_DIR, chance_ten_ten, hand_marks,  # noqa: E402
                                       is_ten_ten, parse_time, slug)

REPO = Path(__file__).resolve().parents[1]
FIG = FORMS_DIR / "figures"
WEB = REPO / "metalesionlab" / "web" / "static" / "img" / "plato_forms"
CLOCK = FORMS_DIR / "clock"
BLUE, ORANGE, TEAL, INK, MUTED, GRID = "#1D4ED8", "#C2410C", "#0D9488", "#111827", "#4B5563", "#E5E7EB"
plt.rcParams.update({"font.family": "sans-serif", "font.size": 11, "axes.edgecolor": "#9CA3AF",
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "svg.fonttype": "none"})


def people_sample(folder: Path, k: int = 16, seed: int = 20261027) -> list[Path]:
    files = load_dir(folder)
    rng = np.random.default_rng(seed)
    return [files[i] for i in sorted(rng.choice(len(files), k, replace=False))]


def tiles(paths: list[Path], crop: bool = True) -> list[Image.Image]:
    return [ink_crop(Image.open(p).convert("RGB")) if crop else Image.open(p).convert("RGB") for p in paths]


def webp(img: Image.Image, name: str, width: int, quality: int = 72) -> Path:
    WEB.mkdir(parents=True, exist_ok=True)
    img = img.convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    out = WEB / f"{name}.webp"
    img.save(out, "WEBP", quality=quality, method=6)
    return out


def save(fig, name: str, svg: bool = False) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=170, bbox_inches="tight", facecolor="white")
    if svg:
        fig.savefig(FIG / f"{name}.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------- clock ----------

def clock_wall(res: dict) -> None:
    sets = [("Muse Image", BLUE, CLOCK / "muse" / "doodle" / "any", "muse_doodle_default"),
            ("Stable Diffusion XL", TEAL, CLOCK / "sdxl" / "doodle" / "any", "sdxl_doodle_default"),
            ("People (Quick, Draw!)", ORANGE, PLATO_DIR / "human" / "clock", "people")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 6.4))
    for ax, (title, color, folder, group) in zip(axes, sets):
        paths = people_sample(folder) if group == "people" else load_dir(folder)[:16]
        sheet = grid(tiles(paths), cols=4, cell=150, gap=8)
        ax.imshow(sheet)
        ax.set_axis_off()
        g = res["groups"].get(group)
        eye = (res.get("byeye_no_time") or {}).get(group)
        sub = ""
        if g:
            t = g["ten_ten"]
            if eye:
                sure = eye["sure"] if eye["sure"] == eye["max"] else f"{eye['sure']}-{eye['max']}"
                sub = f"about 10:10: {sure} of {eye['n']} by eye ({t['k']} by the automatic reader)"
            else:
                sub = f"about 10:10: {t['k']} of {t['n']} ({100 * t['share']:.0f}%)"
        ax.set_title(f"{title}\n", fontsize=15, fontweight="bold", color=INK, loc="left")
        ax.text(0, -0.02, sub, transform=ax.transAxes, fontsize=13, color=color, fontweight="bold", va="top")
        if group == "people":
            ax.text(0, -0.09, "16 of 200 drawings, at random. Google Quick, Draw! (CC BY 4.0)", transform=ax.transAxes,
                    fontsize=10, color=MUTED, va="top")
    fig.suptitle('"A quick simple doodle sketch of a clock" (no time asked)', x=0.02, ha="left", fontsize=13,
                 color=MUTED, y=1.0)
    save(fig, "clock_wall")
    # web tiles
    webp(grid(tiles(load_dir(sets[0][2])[:16]), cols=4, cell=170, gap=10), "wall_muse", 720)
    webp(grid(tiles(load_dir(sets[1][2])[:16]), cols=4, cell=170, gap=10), "wall_sdxl", 720)
    webp(grid(tiles(people_sample(sets[2][2])), cols=4, cell=170, gap=10), "wall_people", 720)


def series_card() -> Path:
    """The Plato series card picture (static/img/plato/series/forms.webp, 1200 x 675): Muse Image's 16
    no-time clocks as drawn (no picking) beside 16 of people's, at random (the hero's sample)."""
    from PIL import ImageDraw, ImageFont

    W, H, pad, cell, gap = 1200, 675, 36, 116, 8
    card = Image.new("RGB", (W, H), "#FFFFFF")
    d = ImageDraw.Draw(card)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    halves = [("Muse Image", BLUE, load_dir(CLOCK / "muse" / "doodle" / "any")[:16]),
              ("People", ORANGE, people_sample(PLATO_DIR / "human" / "clock"))]
    for i, (label, color, paths) in enumerate(halves):
        x0 = pad + i * (W // 2)
        d.text((x0, pad), label, fill=color, font=font)
        d.rectangle((x0, pad + 44, x0 + 4 * cell + 3 * gap, pad + 50), fill=color)
        sheet = grid(tiles(paths), cols=4, cell=cell, gap=gap)
        card.paste(sheet, (x0, pad + 70))
    d.line((W // 2 - 12, pad + 70, W // 2 - 12, H - pad), fill="#E5E7EB", width=2)
    try:
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
    except OSError:
        small = ImageFont.load_default()
    d.text((W // 2 + pad - 12, H - pad + 6), "People’s drawings: Google Quick, Draw! (CC BY 4.0)", fill=MUTED, font=small,
           anchor="ls")
    out = REPO / "metalesionlab" / "web" / "static" / "img" / "plato" / "series" / "forms.webp"
    out.parent.mkdir(parents=True, exist_ok=True)
    card.save(out, "WEBP", quality=74, method=6)
    return out


def draw_dial(ax, counts: list, n: int, color: str, title: str, sub: str) -> None:
    """Every read time as a pair of hands; a hand's darkness and width grow with the number of clocks showing it."""
    th = np.linspace(0, 2 * np.pi, 300)
    ax.plot(np.sin(th), np.cos(th), color="#9CA3AF", lw=1.5)
    for k in range(60):
        a = 2 * np.pi * k / 60
        r0 = 0.9 if k % 5 == 0 else 0.95
        ax.plot([r0 * np.sin(a), np.sin(a)], [r0 * np.cos(a), np.cos(a)], color="#9CA3AF", lw=1.2 if k % 5 == 0 else 0.5)
    for num in (12, 3, 6, 9):
        a = 2 * np.pi * (num % 12) / 12
        ax.text(0.78 * np.sin(a), 0.78 * np.cos(a), str(num), ha="center", va="center", fontsize=12, color=MUTED)
    top = max([c for _, c in counts] or [1])
    for t, c in sorted(counts, key=lambda tc: tc[1]):
        h, m = parse_time(t)
        hm, mm = hand_marks(h, m)
        frac = c / n
        alpha = min(1.0, 0.12 + 0.88 * (c / top) ** 0.8)
        lw = 1.2 + 9 * frac
        for mark, length in ((hm, 0.5), (mm, 0.78)):
            a = 2 * np.pi * mark / 12
            ax.plot([0, length * np.sin(a)], [0, length * np.cos(a)], color=color, alpha=alpha, lw=lw,
                    solid_capstyle="round")
    ax.plot([0], [0], "o", color=INK, ms=4)
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-1.08, 1.08)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(title, fontsize=13, fontweight="bold", color=INK)
    ax.text(0, -1.22, sub, ha="center", va="top", fontsize=11, color=MUTED)


def clock_faces(res: dict) -> None:
    panels = [("muse_doodle_default", "Muse Image", BLUE), ("sdxl_doodle_default", "SDXL", TEAL),
              ("people", "People", ORANGE), ("muse_photo_default", "Muse Image, photo", BLUE),
              ("sdxl_photo_default", "SDXL, photo", TEAL)]
    panels = [p for p in panels if p[0] in res["groups"]]
    fig, axes = plt.subplots(1, len(panels), figsize=(3.6 * len(panels), 4.4))
    for ax, (g, title, color) in zip(np.atleast_1d(axes), panels):
        d = res["groups"][g]
        t = d["ten_ten"]
        nh = d["status"].get("no_hands", 0) + d["status"].get("unreadable", 0) + d["status"].get("unparsed", 0)
        draw_dial(ax, d["times"], d["n"], color, title,
                  f"n = {d['n']}; about 10:10: {100 * t['share']:.0f}%\nno hands or unreadable: {nh}")
    fig.suptitle("Every clock's hands on one dial (no time asked). Darker, thicker hands = more clocks.", x=0.02,
                 ha="left", fontsize=12, color=MUTED)
    save(fig, "clock_faces", svg=True)


def clock_asked(res: dict) -> None:
    panels = [("muse_doodle_asked", "Muse Image, doodle", BLUE), ("sdxl_doodle_asked", "SDXL, doodle", TEAL),
              ("muse_photo_asked", "Muse Image, photo", BLUE), ("sdxl_photo_asked", "SDXL, photo", TEAL)]
    panels = [p for p in panels if p[0] in res["groups"]]
    fig, axes = plt.subplots(1, len(panels), figsize=(4.2 * len(panels), 4.6), sharey=True)
    rng = np.random.default_rng(1)
    for ax, (g, title, color) in zip(np.atleast_1d(axes), panels):
        d = res["groups"][g]
        ax.axhspan(10 - 10 / 60 + 1 / 6, 10 + 1 / 6 + 10 / 60, color="#FDE68A", alpha=0.6, lw=0)
        ax.text(0.3, 10.17, "10:10", va="center", fontsize=9, color="#92400E")
        ax.plot([0, 12], [0, 12], color="#9CA3AF", lw=1, ls="--")
        for want, x in d["per_time"].items():
            wh, wm = parse_time(want)
            xv = (wh % 12) + wm / 60
            for r in x["read"]:
                jx = xv + rng.uniform(-0.18, 0.18)
                if r is None:
                    ax.plot(jx, -0.7, "x", color=MUTED, ms=5)
                    continue
                rh, rm = parse_time(r)
                yv = (rh % 12) + rm / 60
                ax.plot(jx, yv, "o", ms=6, color=color, alpha=0.75, mec="white", mew=0.8)
        ax.set_xlim(-0.5, 12.5)
        ax.set_ylim(-1.2, 12.3)
        ax.set_xticks(range(0, 13, 3), ["12", "3", "6", "9", "12"])
        ax.set_yticks(range(0, 13, 3), ["12", "3", "6", "9", "12"])
        ax.grid(color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        ax.set_xlabel("time asked for (hour)")
        ax.set_title(f"{title}\nright time: {100 * d['accuracy']:.0f}%; about 10:10: {100 * d['ten_ten']['share']:.0f}%",
                     fontsize=11.5, color=INK)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    np.atleast_1d(axes)[0].set_ylabel("time drawn (hour); x = no hands")
    save(fig, "clock_asked", svg=True)


def clock_average(res: dict) -> None:
    sets = [("Muse Image (16)", load_dir(CLOCK / "muse" / "doodle" / "any")[:16]),
            ("SDXL (16)", load_dir(CLOCK / "sdxl" / "doodle" / "any")[:16]),
            ("People (200)", load_dir(PLATO_DIR / "human" / "clock"))]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.9))
    avgs = []
    for ax, (title, paths) in zip(axes, sets):
        a = np.mean([np.asarray(ink_crop(Image.open(p).convert("RGB")).convert("L"), float) for p in paths], axis=0)
        avgs.append(a)
        ax.imshow(a, cmap="gray", vmin=a.min(), vmax=255)
        ax.set_axis_off()
        ax.set_title(f"average of {title}", fontsize=12, color=INK)
    fig.suptitle("Pixel average of each set of clocks, no time asked (no reading involved)", x=0.02, ha="left",
                 fontsize=11, color=MUTED)
    save(fig, "clock_average")
    for name, a in zip(("avg_muse", "avg_sdxl", "avg_people"), avgs):
        lo = a.min()
        img = Image.fromarray(np.clip((a - lo) / (255 - lo) * 255, 0, 255).astype(np.uint8)).convert("RGB")
        webp(img, name, 256, quality=80)


def asked_strip() -> None:
    ims, names = [], []
    for t in CLOCK_TIMES:
        files = load_dir(CLOCK / "muse" / "doodle" / slug(t))
        if files:
            ims.append(ink_crop(Image.open(files[0]).convert("RGB")))
            names.append(t)
    if not ims:
        return
    fig, axes = plt.subplots(1, len(ims), figsize=(1.6 * len(ims), 2.1))
    for ax, im, t in zip(axes, ims, names):
        ax.imshow(im)
        ax.set_axis_off()
        ax.set_title(t, fontsize=12, color=INK)
    fig.suptitle("Muse Image asked for each time (the first of its pictures)", x=0.01, ha="left", fontsize=11, color=MUTED)
    save(fig, "clock_asked_strip")
    webp(labeled_grid(ims, [f"asked {t}" for t in names], cols=5), "asked_muse", 900)


def labeled_grid(ims: list[Image.Image], labels: list[str], cols: int = 5, cell: int = 170, gap: int = 12) -> Image.Image:
    """Tiles with a caption under each (for the web page, where the image carries its own labels)."""
    from PIL import ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    lab_h = 32
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell + (cols - 1) * gap, rows * (cell + lab_h) + (rows - 1) * gap), "white")
    d = ImageDraw.Draw(sheet)
    for i, (im, lab) in enumerate(zip(ims, labels)):
        x, y = (i % cols) * (cell + gap), (i // cols) * (cell + lab_h + gap)
        tile = im.copy()
        tile.thumbnail((cell, cell))
        sheet.paste(tile, (x + (cell - tile.width) // 2, y))
        d.text((x + cell / 2, y + cell + 4), lab, fill=INK, font=font, anchor="mt")
    return sheet


# ---------- bed and table ----------

def concept_grids(cres: dict) -> None:
    rows = {r["key"]: r for r in cres["concepts"]}
    for c in FORMS_CONCEPTS:
        r = rows.get(c.key)
        if not r:
            continue
        conds = r["conditions"]
        lines = [("Muse Image, usual prompt", FORMS_DIR / "ai" / "doodle" / c.key, conds.get("default")),
                 (f'Muse Image, "any kind of {c.key}"', FORMS_DIR / "ai" / "doodle_any" / c.key, conds.get("any")),
                 ("Muse Image, one of each kind Muse Spark named", FORMS_DIR / "ai" / "doodle_listed" / c.key, conds.get("listed")),
                 ("Stable Diffusion XL, usual prompt", FORMS_DIR / "ai" / "sdxl_doodle" / c.key, conds.get("sdxl_default")),
                 ("People (Google Quick, Draw!, CC BY 4.0)", FORMS_DIR / "human" / c.key, None)]
        lines = [x for x in lines if load_dir(x[1])]
        fig, axes = plt.subplots(len(lines), 1, figsize=(16, 1.55 * len(lines) + 0.4))
        for ax, (label, folder, st) in zip(np.atleast_1d(axes), lines):
            paths = people_sample(folder) if "People" in label else load_dir(folder)[:16]
            ax.imshow(grid(tiles(paths), cols=16, cell=120, gap=6))
            ax.set_axis_off()
            spread = f"spread {st['spread']:.2f} ({st['ratio_vs_people']:.2f} of people's)" if st else \
                f"spread {r['human_spread']:.2f}"
            ax.set_title(f"{label}: {spread}", loc="left", fontsize=11.5, color=INK)
        fig.suptitle(f"{c.label.capitalize()} (Plato, Republic X)", x=0.01, ha="left", fontsize=15, fontweight="bold")
        save(fig, f"forms_{c.key}")
        webp(grid(tiles(load_dir(FORMS_DIR / "ai" / "doodle" / c.key)[:16]), cols=4, cell=170, gap=10), f"grid_{c.key}_ai", 720)
        webp(grid(tiles(people_sample(FORMS_DIR / "human" / c.key)), cols=4, cell=170, gap=10), f"grid_{c.key}_people", 720)
        if load_dir(FORMS_DIR / "ai" / "doodle_listed" / c.key):
            webp(grid(tiles(load_dir(FORMS_DIR / "ai" / "doodle_listed" / c.key)[:16]), cols=8, cell=150, gap=8),
                 f"kinds_{c.key}_ai", 900)


def forms_rank(cres: dict) -> None:
    core = json.loads((PLATO_DIR / "results.json").read_text())["concepts"]
    pts = [(c["label"], c["homogenization_index"], c["homogenization_index_ci95"], False) for c in core]
    pts += [(r["label"], r["homogenization_index"], r["homogenization_index_ci95"], True) for r in cres["concepts"]]
    pts.sort(key=lambda p: p[1])
    fig, ax = plt.subplots(figsize=(7.2, 10))
    for i, (label, v, ci95, new) in enumerate(pts):
        y = len(pts) - 1 - i
        em = new or label == "chair"
        ax.plot(ci95, [y, y], color=INK if new else "#93C5FD", lw=2 if new else 1.4, solid_capstyle="round")
        ax.plot(v, y, "o", ms=8 if new else 5.5, color=INK if new else BLUE, mec="white", mew=1.5)
        ax.text(-0.02, y, label, ha="right", va="center", fontsize=10.5 if em else 9.5,
                fontweight="bold" if em else "normal", color=INK, transform=ax.get_yaxis_transform())
    ax.axvline(1, color="#6B7280", lw=1)
    ax.text(1.02, len(pts) - 0.5, "as varied as people", fontsize=9, color=MUTED, va="bottom")
    ax.set_yticks([])
    ax.set_xlim(0, max(1.3, max(p[2][1] for p in pts) + 0.05))
    ax.set_ylim(-1, len(pts))
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_xlabel("Muse Image's spread / people's spread (95% CI)")
    ax.set_title("Bed and table (black) among the 35 core concepts\n(left = Muse Image draws it more alike than people do)",
                 loc="left", fontsize=12, color=INK)
    save(fig, "forms_rank", svg=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["clock", "concepts"])
    args = ap.parse_args()
    if args.only != "concepts" and (FORMS_DIR / "results_clock.json").exists():
        res = json.loads((FORMS_DIR / "results_clock.json").read_text())
        clock_wall(res)
        clock_faces(res)
        clock_asked(res)
        clock_average(res)
        asked_strip()
        print(f"series card: {series_card()}")
        print(f"clock figures in {FIG}; chance {chance_ten_ten():.3f}; e.g. 10:10 check {is_ten_ten((10, 10))}")
    if args.only != "clock" and (FORMS_DIR / "results_concepts.json").exists():
        cres = json.loads((FORMS_DIR / "results_concepts.json").read_text())
        concept_grids(cres)
        forms_rank(cres)
        print(f"bed and table figures in {FIG}")
    total = sum(p.stat().st_size for p in WEB.glob("*.webp")) if WEB.exists() else 0
    print(f"web tiles: {total / 1024:.0f} KB in {WEB}")


if __name__ == "__main__":
    main()

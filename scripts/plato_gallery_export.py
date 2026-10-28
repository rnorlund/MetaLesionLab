"""Export the pictures for the gallery (/plato/gallery) and the site-wide "From the lab" strip.

Writes WebP files into metalesionlab/web/static/img/gallery/, one set per item of
metalesionlab/web/data/gallery.json (the captions, links and alt text live there, written by hand):
- <id>.webp: the card picture. For a still, about 320 px tall. For a sequence, a sprite: every frame side by
  side in equal cells (a pair frame is its two panels side by side), which the cards play as a mini filmstrip.
- <id>-full.webp: a still's large picture, at most 1200 px wide.
- <id>-<k>.webp (and <id>-<k>b.webp, the second panel of a pair): a sequence's frames for the large view.
The Draw page's damage strips copy that page's own frames (static/img/draw_damage/) byte for byte.

Reads the finished experiments in PlatosChair/ (outside the repository) and makes no API calls ($0).
Never reads children's drawings (PlatosChair/lifespan/kiddraw_raw): the life-of-a-chair item shows children
only as icon arrays drawn from the published group statistics in docs/plato_lifespan.md.

    python scripts/plato_gallery_export.py            # everything
    python scripts/plato_gallery_export.py beanbag    # only items whose id contains "beanbag"
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from metalesionlab.plato import cosine_distances, ink_crop, load_dir, render_strokes, spread  # noqa: E402

ROOT = Path("/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair")
WEB = REPO / "metalesionlab" / "web" / "static" / "img"
OUT = WEB / "gallery"
FORBIDDEN = ("kiddraw", "children", "child_")  # no child's drawing is ever read, let alone shown

PAPER = (236, 234, 228)  # the gaps between tiles
WHITE = (255, 255, 255)
FILL, EMPTY = (194, 65, 12), (214, 211, 204)  # icon arrays: the site's people orange, and a quiet gray
THUMB_H, FULL_W, FRAME, SPRITE_H = 320, 1200, 400, 200


# ---------- reading and writing ----------

def src(rel: str) -> Path:
    if any(f in rel.lower() for f in FORBIDDEN):
        raise ValueError(f"refusing to read {rel}: children's data are never shown")
    p = ROOT / rel
    if not p.is_file():
        raise FileNotFoundError(p)
    return p


def pic(rel: str) -> Image.Image:
    return Image.open(src(rel)).convert("RGB")


def doodle(rel: str, side: int = FRAME) -> Image.Image:
    """A Muse Image (or similar) drawing on paper: paper flattened, cropped to its ink, square."""
    return ink_crop(pic(rel), side=side, margin=0.08)


def square(im: Image.Image, side: int = FRAME) -> Image.Image:
    return im.convert("RGB").resize((side, side), Image.LANCZOS) if im.size != (side, side) else im.convert("RGB")


def save(im: Image.Image, name: str, quality: int = 70, max_w: int | None = None, max_h: int | None = None) -> Path:
    im = im.convert("RGB")
    if max_w and im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    if max_h and im.height > max_h:
        im = im.resize((round(im.width * max_h / im.height), max_h), Image.LANCZOS)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.webp"
    im.save(path, "WEBP", quality=quality, method=6)
    return path


def grid(tiles: list[Image.Image], cols: int, cell: int, gap: int = 8, pad: int = 0, bg=PAPER,
         aspect: float = 1.0) -> Image.Image:
    """Tiles on white, in cells of cell x cell*aspect, with paper-coloured gaps."""
    ch = round(cell * aspect)
    rows = (len(tiles) + cols - 1) // cols
    W, H = cols * cell + (cols - 1) * gap + 2 * pad, rows * ch + (rows - 1) * gap + 2 * pad
    g = Image.new("RGB", (W, H), bg)
    for i, t in enumerate(tiles):
        x, y = pad + (i % cols) * (cell + gap), pad + (i // cols) * (ch + gap)
        tile = Image.new("RGB", (cell, ch), WHITE)
        t = ImageOps.contain(t.convert("RGB"), (cell, ch), Image.LANCZOS)
        tile.paste(t, ((cell - t.width) // 2, (ch - t.height) // 2))
        g.paste(tile, (x, y))
    return g


def side_by_side(parts: list[Image.Image], gap: int = 24, bg=PAPER, pad: int = 0) -> Image.Image:
    h = max(p.height for p in parts)
    W = sum(p.width for p in parts) + gap * (len(parts) - 1) + 2 * pad
    out = Image.new("RGB", (W, h + 2 * pad), bg)
    x = pad
    for p in parts:
        out.paste(p, (x, pad + (h - p.height) // 2))
        x += p.width + gap
    return out


def stacked(parts: list[Image.Image], gap: int = 24, bg=PAPER) -> Image.Image:
    w = max(p.width for p in parts)
    out = Image.new("RGB", (w, sum(p.height for p in parts) + gap * (len(parts) - 1)), bg)
    y = 0
    for p in parts:
        out.paste(p, ((w - p.width) // 2, y))
        y += p.height + gap
    return out


def sprite(frames: list, h: int = SPRITE_H, gap: int = 8) -> Image.Image:
    """Every frame side by side in equal cells; a pair frame is its two panels with a small gap."""
    cells = []
    for f in frames:
        if isinstance(f, tuple):
            a, b = (ImageOps.contain(x, (h * 4, h), Image.LANCZOS) for x in f)
            cell = Image.new("RGB", (a.width + gap + b.width, h), PAPER)
            cell.paste(a, (0, 0))
            cell.paste(b, (a.width + gap, 0))
        else:
            cell = f.resize((round(f.width * h / f.height), h), Image.LANCZOS)
        cells.append(cell)
    w = cells[0].width
    out = Image.new("RGB", (w * len(cells), h), WHITE)
    for i, c in enumerate(cells):
        out.paste(c.resize((w, h), Image.LANCZOS) if c.width != w else c, (i * w, 0))
    return out


def write_sequence(item_id: str, frames: list, quality: int = 68, sprite_quality: int = 62,
                   frame_files: bool = True) -> list[Path]:
    """The sprite (card) and, unless the frames already exist on the site, one file per frame (large view)."""
    out = [save(sprite(frames), item_id, quality=sprite_quality)]
    if frame_files:
        for k, f in enumerate(frames):
            if isinstance(f, tuple):
                out.append(save(f[0], f"{item_id}-{k}", quality=quality))
                out.append(save(f[1], f"{item_id}-{k}b", quality=quality))
            else:
                out.append(save(f, f"{item_id}-{k}", quality=quality))
    return out


def write_still(item_id: str, full: Image.Image, thumb: Image.Image | None = None, quality: int = 72) -> list[Path]:
    thumb = thumb if thumb is not None else full
    return [save(thumb, item_id, quality=quality - 4, max_h=THUMB_H, max_w=2 * THUMB_H + 80),
            save(full, f"{item_id}-full", quality=quality, max_w=FULL_W)]


# ---------- the items ----------

def telephone(start: str, chain: int) -> list[Image.Image]:
    return [doodle(f"telephone/chains/{start}/c{chain}/g{g:02d}.png") for g in range(11)]


def damage(cond: str, key: str, seed: int, run: str = "main") -> Image.Image:
    return square(pic(f"damage/{run}/{cond}/{key}/s{seed}.png"))


def damage_pairs(key: str, seed: int, lang: list[str], draw: list[str]) -> list[tuple]:
    intact = damage("intact", key, seed)
    pairs = [(intact, intact)]
    pairs += [(damage(a, key, seed), damage(b, key, seed)) for a, b in zip(lang, draw)]
    return pairs


def human_subset(root: Path, key: str, n: int = 16) -> list[int]:
    """The landing page's rule: of 201 random sets of n of people's drawings, the one with the median spread."""
    rng = np.random.default_rng(7)
    emb = np.load(root / "embeddings" / "human" / f"{key}.npz")["cls"]
    d = cosine_distances(emb)
    sets = [np.sort(rng.choice(len(d), n, replace=False)) for _ in range(201)]
    spreads = np.array([spread(d, s) for s in sets])
    return [int(i) for i in sets[int(np.argsort(spreads)[len(spreads) // 2])]]


def people(folder: str, idx: list[int], side: int = 256) -> list[Image.Image]:
    files = load_dir(src(f"{folder}/000.png").parent)
    return [ink_crop(Image.open(files[i]).convert("RGB"), side=side, margin=0.08) for i in idx]


def people_sample(folder: str, k: int = 16, seed: int = 20261027) -> list[Image.Image]:
    """The Forms page's rule for its people grids (scripts/plato_forms_figures.py)."""
    files = load_dir(src(f"{folder}/000.png").parent)
    rng = np.random.default_rng(seed)
    return [ink_crop(Image.open(files[i]).convert("RGB"), side=256, margin=0.08)
            for i in sorted(rng.choice(len(files), k, replace=False))]


def muse_dir(folder: str, n: int, side: int = 256) -> list[Image.Image]:
    files = load_dir(src(f"{folder}/c0_0.png").parent)[:n]
    return [ink_crop(Image.open(f).convert("RGB"), side=side, margin=0.08) for f in files]


def pictures(folder: str, n: int = 12, side: int = 256, crop: bool = True) -> list[Image.Image]:
    files = load_dir(src(f"{folder}/p0.png").parent)[:n]
    if crop:
        return [ink_crop(Image.open(f).convert("RGB"), side=side, margin=0.08) for f in files]
    return [Image.open(f).convert("RGB") for f in files]


def stack(tiles: list[Image.Image], p: float, side: int, alpha: float, cols: int = 4, gap: int = 8) -> Image.Image:
    """Tiles moving from a 4 x 4 grid (p = 0) onto one another (p = 1), multiplied like ink on paper."""
    cell = (side - (cols - 1) * gap) // cols
    acc = np.ones((side, side))
    a_now = 1 + (alpha - 1) * p
    for i, t in enumerate(tiles):
        c, r = i % cols, i // cols
        s = int(round(cell + (side - cell) * p))
        cx0, cy0 = c * (cell + gap) + cell / 2, r * (cell + gap) + cell / 2
        cx, cy = cx0 + (side / 2 - cx0) * p, cy0 + (side / 2 - cy0) * p
        g = np.asarray(t.convert("L").resize((s, s), Image.LANCZOS), float) / 255
        xs, ys = int(round(cx - s / 2)), int(round(cy - s / 2))
        xa, ya, xb, yb = max(xs, 0), max(ys, 0), min(xs + s, side), min(ys + s, side)
        acc[ya:yb, xa:xb] *= 1 - a_now * (1 - g[ya - ys:yb - ys, xa - xs:xb - xs])
    return Image.fromarray((np.clip(acc, 0, 1) * 255).astype(np.uint8)).convert("RGB")


def chair_icon(size: int, colour) -> Image.Image:
    """The site's Form chair (site.FORM_CHAIR), drawn as a small icon."""
    S = 4 * size
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = S / 64
    w = max(2, round(4.2 * k))
    lines = [[(21, 33), (21, 7), (43, 7), (43, 33)], [(21, 15), (43, 15)], [(29, 7), (29, 15)], [(35, 7), (35, 15)],
             [(16, 40), (16, 58)], [(48, 40), (48, 58)], [(21, 33), (21, 51)], [(43, 33), (43, 51)]]
    for ln in lines:
        d.line([(x * k, y * k) for x, y in ln], fill=colour, width=w, joint="curve")
    d.polygon([(21 * k, 33 * k), (16 * k, 40 * k), (48 * k, 40 * k), (43 * k, 33 * k)], fill=colour)
    return im.resize((size, size), Image.LANCZOS)


def icon_array(filled: int, side: int = FRAME) -> Image.Image:
    """10 chair icons, 5 x 2, the first `filled` in colour: how many in 10 drawings a model recognizes."""
    im = Image.new("RGB", (side, side), WHITE)
    icon = round(side / 5.6)
    gap_x = (side - 5 * icon) // 6
    y0 = (side - 2 * icon - icon // 3) // 2
    for i in range(10):
        c, r = i % 5, i // 5
        ic = chair_icon(icon, FILL if i < filled else EMPTY)
        im.paste(ic, (gap_x + c * (icon + gap_x), y0 + r * (icon + icon // 3)), ic)
    return im


def sketch(step: int) -> Image.Image:
    """The sketch model's first 4 drawings at a training step, 2 x 2 (not picked). As in docs/plato_lifespan.md, a
    drawing that is a single point is no drawing."""
    drawings = json.loads(src(f"lifespan/sketch/samples/step{step}_t1.0.json").read_text())
    first = [d for d in drawings if d and sum(len(s[0]) for s in d) > 1][:4]
    tiles = [ink_crop(render_strokes(d, side=384, width=6, pad=18), side=192, margin=0.1) for d in first]
    return grid(tiles, 2, (FRAME - 8) // 2, gap=8, bg=PAPER).resize((FRAME, FRAME), Image.LANCZOS)


def labelled(tiles: list[Image.Image], labels: list[str], cols: int, cell: int = 220, gap: int = 10) -> Image.Image:
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    lab = 34
    rows = (len(tiles) + cols - 1) // cols
    g = Image.new("RGB", (cols * cell + (cols - 1) * gap, rows * (cell + lab) + (rows - 1) * gap), PAPER)
    d = ImageDraw.Draw(g)
    for i, (t, s) in enumerate(zip(tiles, labels)):
        x, y = (i % cols) * (cell + gap), (i // cols) * (cell + lab + gap)
        tile = Image.new("RGB", (cell, cell + lab), WHITE)
        tt = ImageOps.contain(t, (cell, cell), Image.LANCZOS)
        tile.paste(tt, ((cell - tt.width) // 2, (cell - tt.height) // 2))
        g.paste(tile, (x, y))
        d.text((x + cell / 2, y + cell + 4), s, fill=(17, 24, 39), font=font, anchor="mt")
    return g


def build() -> dict:
    """id -> a function that writes the item's files and returns their paths."""
    B: dict = {}

    # -- Watch it degrade: Plato's Telephone (Muse Spark describes, Muse Image draws, ten times) --
    for item_id, start, chain in (("telephone-beanbag", "beanbag", 0), ("telephone-high-chair", "high_chair", 0),
                                  ("telephone-folding-chair", "folding_chair", 1), ("telephone-throne", "throne", 1)):
        B[item_id] = lambda i=item_id, s=start, c=chain: write_sequence(i, telephone(s, c))

    # -- the damaged painter: SDXL with its language part or its drawing part damaged --
    B["damage-rocking-chair"] = lambda: write_sequence("damage-rocking-chair", damage_pairs(
        "chair__rocking_chair", 1, ["text-noise@0.25", "text-noise@0.5", "text-noise@0.75", "text-noise@1"],
        ["unet-noise@0.75", "unet-noise@0.9", "unet-noise@1", "unet-noise@1.1"]))
    B["damage-wheelchair"] = lambda: write_sequence("damage-wheelchair", damage_pairs(
        "chair__wheelchair", 2, ["text-zero@0.2", "text-zero@0.25", "text-zero@0.29", "text-zero@0.31"],
        ["unet-zero@0.05", "unet-zero@0.1", "unet-zero@0.15", "unet-zero@0.2"]))
    B["damage-clock-numbers"] = lambda: write_sequence("damage-clock-numbers", [
        damage(c, "clock__6_30", 0, run="clocks") for c in ("intact", "unet-zero@0.1", "unet-zero@0.15", "unet-zero@0.2")])
    B["damage-clock-cyclist"] = lambda: write_sequence("damage-clock-cyclist", [
        damage(c, "clock__8_45", 0, run="clocks") for c in ("intact", "text-noise@0.5", "text-noise@0.75", "text-noise@1")])
    B["damage-janus-wheelchair"] = lambda: write_sequence("damage-janus-wheelchair", [
        square(pic(f"damage/janus_draw/{c}/chair__wheelchair/s0.png"), 384)
        for c in ("intact", "lm-zero@0.2", "lm-zero@0.35", "lm-zero@0.5")])

    # -- the Draw page's ten damage strips: the page's own frames, copied byte for byte (the gallery's data must
    #    not name that folder: tests/test_draw_damage.py keeps the damage pictures away from any scoring) --
    dd = json.loads((WEB / "draw_damage" / "draw_damage.json").read_text())
    for t in dd["things"]:
        def strip(t=t):
            item_id = f"draw-damage-{t['key']}"
            files = lambda u: WEB / u.removeprefix("/static/img/")  # noqa: E731
            load = lambda u: Image.open(files(u)).convert("RGB")  # noqa: E731
            intact = load(t["intact"])
            frames = [(intact, intact)] + [(load(a), load(b)) for a, b in zip(t["language"], t["drawing"])]
            out = [save(sprite(frames, h=160), item_id, quality=60)]
            copies = [(t["intact"], f"{item_id}-0")]
            for k, (a, b) in enumerate(zip(t["language"], t["drawing"]), 1):
                copies += [(a, f"{item_id}-{k}"), (b, f"{item_id}-{k}b")]
            for url, name in copies:
                out.append(OUT / f"{name}.webp")
                shutil.copyfile(files(url), out[-1])
            return out
        B[f"draw-damage-{t['key']}"] = strip

    # -- Shadows: Plato's Cave (Muse Glimmer names drawings, outlines, silhouettes and cast shadows) --
    for item_id, word in (("cave-rabbit", "rabbit"), ("cave-hat", "hat")):
        B[item_id] = lambda i=item_id, w=word: write_sequence(i, [
            square(pic(f"cave/stimuli/{v}/{w}.png")) for v in ("original", "outline", "silhouette", "shadow")])
    B["cave-wall"] = lambda: write_still("cave-wall", pic("cave/figures/cave_wall.png"), quality=66)
    B["cave-versions"] = lambda: write_still("cave-versions", pic("cave/figures/versions_strip.png"))

    # -- The Forms --
    def muse_people_chairs():
        muse = muse_dir("core/ai/doodle/chair", 16)
        ppl = people("core/human/chair", human_subset(ROOT / "core", "chair"))
        return muse, ppl

    def sixteen():
        muse, ppl = muse_people_chairs()
        full = side_by_side([grid(muse, 4, 140, pad=8), grid(ppl, 4, 140, pad=8)], gap=32, pad=0)
        return write_still("forms-sixteen-chairs", full)
    B["forms-sixteen-chairs"] = sixteen

    def stacking():
        muse, ppl = muse_people_chairs()
        frames = [(stack(muse, p, FRAME, 0.24), stack(ppl, p, FRAME, 0.32)) for p in (0, 0.55, 1)]
        return write_sequence("forms-stacked", frames)
    B["forms-stacked"] = stacking

    def clock_avg():
        sets = [load_dir(src("forms/clock/muse/doodle/any/c0_0.png").parent)[:16], load_dir(src("core/human/clock/000.png").parent)]
        avgs = []
        for files in sets:
            a = np.mean([np.asarray(ink_crop(Image.open(p).convert("RGB"), side=480).convert("L"), float) for p in files], axis=0)
            lo = a.min()
            avgs.append(Image.fromarray(np.clip((a - lo) / (255 - lo) * 255, 0, 255).astype(np.uint8)).convert("RGB"))
        full = side_by_side([grid([avgs[0]], 1, 480, pad=10), grid([avgs[1]], 1, 480, pad=10)], gap=32)
        return write_still("forms-clock-1010", full)
    B["forms-clock-1010"] = clock_avg

    def clock_asked():
        times = ["1:20", "2:35", "3:00", "4:55", "5:10", "6:30", "7:50", "8:15", "9:45", "10:40", "11:05", "12:25"]
        tiles, labels = [], []
        for t in times:
            folder = ROOT / "forms" / "clock" / "muse" / "doodle" / f"t{int(t.split(':')[0]):02d}{t.split(':')[1]}"
            files = load_dir(folder)
            if files:
                tiles.append(ink_crop(Image.open(files[0]).convert("RGB"), side=256, margin=0.08))
                labels.append(f"asked {t}")
        full = labelled(tiles, labels, cols=5, cell=190)
        thumb = labelled(tiles[:6], labels[:6], cols=3, cell=190)
        return write_still("forms-clock-asked", full, thumb)
    B["forms-clock-asked"] = clock_asked

    for concept in ("table", "bed"):
        def forms_grid(c=concept):
            muse = muse_dir(f"forms/ai/doodle/{c}", 16)
            ppl = people_sample(f"forms/human/{c}")
            full = side_by_side([grid(muse, 4, 140, pad=8), grid(ppl, 4, 140, pad=8)], gap=32)
            return write_still(f"forms-{c}", full)
        B[f"forms-{concept}"] = forms_grid

    def named_kinds():
        tiles = pictures("core/ai/doodle_listed/chair", 16)
        return write_still("forms-named-kinds", grid(tiles, 8, 140, pad=8), grid(tiles[:8], 4, 140, pad=8))
    B["forms-named-kinds"] = named_kinds

    def sdxl():
        muse = muse_dir("core/ai/doodle/chair", 9)
        sd = [square(Image.open(f).convert("RGB"), 256) for f in load_dir(src("core/ai/sdxl_doodle/chair/c0_0.png").parent)[:9]]
        ppl = people("core/human/chair", human_subset(ROOT / "core", "chair")[:9])
        full = side_by_side([grid(muse, 3, 120, pad=8), grid(sd, 3, 120, pad=8), grid(ppl, 3, 120, pad=8)], gap=28)
        thumb = side_by_side([grid(muse, 3, 120, pad=8), grid(sd, 3, 120, pad=8)], gap=28)
        return write_still("forms-sdxl", full, thumb)
    B["forms-sdxl"] = sdxl

    # -- Words and shapes: Cratylus and the Bird --
    def words(item_id, top, bottom):
        a, b = pictures(f"cratylus/ai/{top}"), pictures(f"cratylus/ai/{bottom}")
        full = stacked([grid(a, 6, 150, pad=8), grid(b, 6, 150, pad=8)], gap=20)
        thumb = side_by_side([grid(a[:6], 3, 150, pad=8), grid(b[:6], 3, 150, pad=8)], gap=24)
        return write_still(item_id, full, thumb)
    B["cratylus-bouba-kiki"] = lambda: words("cratylus-bouba-kiki", "bouba", "kiki")
    B["cratylus-keti"] = lambda: words("cratylus-keti", "kiki", "keti")

    def no_name():
        tiles = pictures("cratylus/ai/no_name")
        return write_still("cratylus-no-name", grid(tiles, 6, 150, pad=8), grid(tiles[:6], 3, 150, pad=8))
    B["cratylus-no-name"] = no_name

    def game():
        tiles = pictures("bird/pictures/game", crop=False)
        return write_still("bird-game", grid(tiles, 4, 280, pad=8, aspect=2 / 3), grid(tiles[:4], 2, 280, pad=8, aspect=2 / 3))
    B["bird-game"] = game

    def bird():
        tiles = pictures("bird/pictures/bird")
        return write_still("bird-sparrow", grid(tiles, 6, 150, pad=8), grid(tiles[:6], 3, 150, pad=8))
    B["bird-sparrow"] = bird

    # -- Growing up (no child's drawing anywhere) --
    B["lifespan-sketch"] = lambda: write_sequence("lifespan-sketch", [sketch(s) for s in (0, 100, 200, 800, 3200, 12800, 25600)])
    B["lifespan-sd-stages"] = lambda: write_sequence("lifespan-sd-stages", [
        square(pic(f"lifespan/ai/sd/{v}/chair/s8.png")) for v in ("v1.1", "v1.2", "v1.3", "v1.4", "v1.5")])
    # The chair's recognizability (docs/plato_lifespan.md, "The chair"): 53% at age 2, 80% at 6, 89% at 10, adults
    # 92%, each shown as the nearest whole number of 10 icons; then Muse Image's chair, the Form it draws.
    B["lifespan-life"] = lambda: write_sequence("lifespan-life", [
        icon_array(5), icon_array(8), icon_array(9), icon_array(9), doodle("core/ai/doodle/chair/c0_0.png")])
    return B


def main(argv: list[str]) -> None:
    builders = build()
    pick = [k for k in builders if not argv or any(a in k for a in argv)]
    total = 0
    for k in pick:
        paths = builders[k]()
        size = sum(p.stat().st_size for p in paths)
        total += size
        print(f"{k:28s} {len(paths):3d} files {size / 1024:7.1f} KB")
    every = sum(p.stat().st_size for p in OUT.glob("*.webp"))
    print(f"written now: {total / 1024:.0f} KB; static/img/gallery holds {every / 1024:.0f} KB")


if __name__ == "__main__":
    main(sys.argv[1:])

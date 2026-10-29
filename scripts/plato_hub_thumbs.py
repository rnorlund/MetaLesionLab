"""Card pictures for the Experiments hub (/plato): one 960 x 540 WebP per experiment that has no series picture yet,
put together from pictures the site already ships (static/img/...). Writes static/img/plato/hub/<slug>.webp.

    python scripts/plato_hub_thumbs.py                    every card
    python scripts/plato_hub_thumbs.py damaged-ideas ...  only these

The hub prefers these over static/img/plato/series/<slug>.webp (site.py: hub_image). They live in their own folder
because the landing page's series cards read static/img/plato/series/ before the blind draw, and some of these
show Muse Image's chairs. The invisible Forms card shows Plato pointing up, not Muse Image's drawings of God, so
the God drawn on /draw stays blind.

The Damaged AI hub (/damaged, damaged_routes.py) has its own cards, one per damage result: DAMAGED below writes
static/img/plato/hub/damaged-<card>.webp. Each puts the undamaged picture beside its damaged versions, blue under the
words part's (the part that reads the words) and orange under the drawing part's (the part that paints the picture),
in the site's plain words (docs/style_plain_language.md). No card shows any AI's God: the ideas card shows death,
so the blind "Draw God" on /draw (its first drawing) stays blind.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

IMG = Path(__file__).resolve().parents[1] / "metalesionlab" / "web" / "static" / "img"
OUT = IMG / "plato" / "hub"
W, H = 960, 540
PAPER = (251, 250, 245)


def canvas() -> Image.Image:
    return Image.new("RGB", (W, H), PAPER)


def flat(im: Image.Image) -> Image.Image:
    """RGBA or palette pictures on paper."""
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, PAPER)
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


def fit(im: Image.Image, w: int, h: int) -> Image.Image:
    im = flat(im)
    im.thumbnail((w, h), Image.LANCZOS)
    return im


def cells(sprite: Image.Image, cols: int, rows: int) -> list[Image.Image]:
    cw, ch = sprite.width // cols, sprite.height // rows
    return [sprite.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)) for r in range(rows) for c in range(cols)]


def inside() -> Image.Image:
    out = canvas()
    fig = fit(Image.open(IMG / "plato" / "spread_by_layer.webp"), W - 40, H - 40)
    out.paste(fig, ((W - fig.width) // 2, (H - fig.height) // 2))
    return out


def ideas() -> Image.Image:
    out = canvas()
    plato = fit(Image.open(IMG / "portraits" / "plato-pointing-up.webp"), W, H - 30)
    out.paste(plato, ((W - plato.width) // 2, H - plato.height))
    return out


def bird() -> Image.Image:
    out = canvas()
    fig = fit(Image.open(IMG / "gallery" / "bird-sparrow.webp"), W - 60, H - 40)
    out.paste(fig, ((W - fig.width) // 2, (H - fig.height) // 2))
    return out


def atlas() -> Image.Image:
    """Muse Image's first doodle of eight different things."""
    out = canvas()
    things = ["chair", "umbrella", "violin", "bicycle", "cat", "house", "cup", "airplane"]
    side, gap = 210, 14
    x0, y0 = (W - 4 * side - 3 * gap) // 2, (H - 2 * side - gap) // 2
    for i, t in enumerate(things):
        path = IMG / "plato_atlas" / f"{t}-fm.webp"
        if not path.is_file():
            continue
        tile = Image.new("RGB", (side, side), (255, 255, 255))
        pic = fit(Image.open(path), side - 16, side - 16)
        tile.paste(pic, ((side - pic.width) // 2, (side - pic.height) // 2))
        out.paste(tile, (x0 + (i % 4) * (side + gap), y0 + (i // 4) * (side + gap)))
    return out


def telephone() -> Image.Image:
    """Two chains of describe-then-draw: five of each chain's eleven copies."""
    out = canvas()
    side, gap = 168, 14
    for row, name in enumerate(("telephone-beanbag", "telephone-folding-chair")):
        frames = cells(Image.open(IMG / "gallery" / f"{name}.webp"), 11, 1)
        x0 = (W - 5 * side - 4 * gap) // 2
        y = 70 + row * (side + 64)
        for j, k in enumerate((0, 2, 4, 7, 10)):
            tile = Image.new("RGB", (side, side), (255, 255, 255))
            pic = fit(frames[k], side - 8, side - 8)
            tile.paste(pic, ((side - pic.width) // 2, (side - pic.height) // 2))
            out.paste(tile, (x0 + j * (side + gap), y))
    return out


def scale() -> Image.Image:
    """Three rows of the wall of chairs drawn as SVG by open language models, small to large: broken shapes, then
    boxes, then chairs."""
    out = canvas()
    wall = flat(Image.open(IMG / "plato_scale" / "wall_models.webp"))
    tile, cols, side, gap = 128, 8, 104, 10
    x0 = (W - cols * side - (cols - 1) * gap) // 2
    y0 = (H - 3 * side - 2 * gap) // 2
    for r, row in enumerate((2, 11, 16)):
        for c in range(cols):
            cell = wall.crop((c * tile, row * tile, (c + 1) * tile, (row + 1) * tile)).resize((side, side), Image.LANCZOS)
            out.paste(cell, (x0 + c * (side + gap), y0 + r * (side + gap)))
    return out


def phaedrus() -> Image.Image:
    """Seven meanings: the sentence with each word stressed in turn (left) and the one transcript a text-only AI
    gets for all seven (right)."""
    from matplotlib import get_data_path
    from PIL import ImageDraw, ImageFont

    fonts = Path(get_data_path()) / "fonts" / "ttf"
    sans, bold = (ImageFont.truetype(str(fonts / f), 25) for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"))
    mono = ImageFont.truetype(str(fonts / "DejaVuSansMono.ttf"), 19)
    ink, blue, grey = (17, 24, 39), (29, 78, 216), (107, 114, 128)
    words = "I never said she stole my money.".split()
    out = canvas()
    d = ImageDraw.Draw(out)
    y0, step = 64, 60
    for k in range(len(words)):
        x, y = 40, y0 + k * step
        for j, w in enumerate(words):
            stressed = j == k
            word = w.upper() if stressed else w
            font = bold if stressed else sans
            d.text((x, y), word, font=font, fill=blue if stressed else ink)
            width = d.textlength(word, font=font)
            if stressed:
                d.line((x, y + 32, x + width - (8 if w.endswith(".") else 0), y + 34), fill=blue, width=3)
            x += width + d.textlength(" ", font=sans)
        d.text((548, y + 5), "I never said she stole my money.", font=mono, fill=grey)
    d.line((526, 50, 526, H - 50), fill=(209, 213, 219), width=2)
    return out


MAKERS = {"inside": inside, "ideas": ideas, "bird": bird, "atlas": atlas, "telephone": telephone,
          "scale": scale, "phaedrus": phaedrus}


# --- the Damaged AI hub ------------------------------------------------------------------------------------------
INK, BLUE, ORANGE, GREY = (17, 24, 39), (29, 78, 216), (194, 65, 12), (107, 114, 128)


def _fonts(size: int):
    from matplotlib import get_data_path
    from PIL import ImageFont

    fonts = Path(get_data_path()) / "fonts" / "ttf"
    return tuple(ImageFont.truetype(str(fonts / f), size) for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"))


def strip(tiles: list[tuple[Image.Image | str, str, tuple]], side: int = 270, gap: int = 22, arrows: tuple = ()) -> Image.Image:
    """Square pictures in a row on paper, each with a coloured bar and a label under it; arrows: the gaps after these
    tiles get a →."""
    from PIL import ImageDraw

    out = canvas()
    d = ImageDraw.Draw(out)
    sans, bold = _fonts(30 if side >= 250 else 25)  # four tiles a row: "language part" fits under its own tile
    n = len(tiles)
    x0, y0 = (W - n * side - (n - 1) * gap) // 2, (H - side - 70) // 2
    for i, (src, label, colour) in enumerate(tiles):
        x = x0 + i * (side + gap)
        tile = Image.new("RGB", (side, side), (255, 255, 255))
        pic = flat(src if isinstance(src, Image.Image) else Image.open(IMG / src))
        k = side / max(pic.size)  # the pictures are 160-320 px: scaled to the tile either way
        pic = pic.resize((round(pic.width * k), round(pic.height * k)), Image.LANCZOS)
        tile.paste(pic, ((side - pic.width) // 2, (side - pic.height) // 2))
        out.paste(tile, (x, y0))
        d.rectangle((x, y0 + side, x + side - 1, y0 + side + 6), fill=colour)
        d.text((x + side / 2, y0 + side + 20), label, font=sans if colour == INK else bold, fill=colour, anchor="mt")
    for i in arrows:
        d.text((x0 + (i + 1) * (side + gap) - gap / 2, y0 + side / 2), "→", font=bold, fill=GREY, anchor="mm")
    return out


def damaged_painter() -> Image.Image:
    """The wheelchair: neurons switched off in the language part make it a bicycle; in the drawing part, stripes."""
    return strip([("plato_damage/wheelchair_intact.webp", "undamaged", INK),
                  ("plato_damage/wheelchair_text-zero_3.webp", "words part", BLUE),
                  ("plato_damage/wheelchair_unet-zero_3.webp", "drawing part", ORANGE)])


def damaged_ideas() -> Image.Image:
    """Stable Diffusion XL's death (the trio /plato/ideas shows): a skull; people; scribbles. Never a God."""
    undamaged, words, drawing = cells(Image.open(IMG / "plato_ideas" / "dmg" / "death_trio.webp"), 3, 1)
    return strip([(undamaged, "undamaged", INK), (words, "words part", BLUE), (drawing, "drawing part", ORANGE)])


def damaged_clocks() -> Image.Image:
    """Two clocks, each beside its own damaged twin: drawing damage takes the numbers, language damage the clock."""
    return strip([("gallery/damage-clock-numbers-0.webp", "undamaged", INK), ("gallery/damage-clock-numbers-1.webp", "drawing part", ORANGE),
                  ("gallery/damage-clock-cyclist-0.webp", "undamaged", INK), ("gallery/damage-clock-cyclist-2.webp", "words part", BLUE)],
                 side=200, gap=26, arrows=(0, 2))


def damaged_glimmer() -> Image.Image:
    """Muse Image's doodles of named kinds, the kind each shows, and the answer a damaged Glimmer settles on."""
    from PIL import ImageDraw

    named = cells(flat(Image.open(IMG / "gallery" / "forms-named-kinds-full.webp")), 8, 2)
    named = [c.crop((10, 10, c.width - 10, c.height - 10)) for c in named]  # inside the sheet's grey gutters
    picks = [(named[0], "rocking chair"), (named[6], "high chair"), (named[7], "wheelchair"), (named[13], "throne")]
    out = canvas()
    d = ImageDraw.Draw(out)
    sans, bold = _fonts(28)
    side, gap = 200, 20
    x0, y0 = (W - 4 * side - 3 * gap) // 2, (H - side - 150) // 2
    for i, (cell, name) in enumerate(picks):
        x = x0 + i * (side + gap)
        out.paste(cell.resize((side, side), Image.LANCZOS), (x, y0))
        d.text((x + side / 2, y0 + side + 16), name, font=sans, fill=INK, anchor="mt")
    y = y0 + side + 78
    d.line((x0, y, W - x0, y), fill=BLUE, width=4)
    d.text((W / 2, y + 26), "damaged, the AI says: “a plain, ordinary chair”", font=bold, fill=BLUE, anchor="mt")
    return out


def damaged_janus() -> Image.Image:
    """Janus-Pro's wheelchair as more of its language model is switched off: a tricycle, then a car."""
    return strip([("plato_damage/janus_wheelchair_intact.webp", "undamaged", INK),
                  ("plato_damage/janus_wheelchair_lm-zero_0.2.webp", "a little", BLUE),
                  ("plato_damage/janus_wheelchair_lm-zero_0.35.webp", "more", BLUE),
                  ("plato_damage/janus_wheelchair_lm-zero_0.5.webp", "a lot", BLUE)], side=200, gap=22)


def damaged_yourself() -> Image.Image:
    """A doodle of a chair (site.py's chair line icon), then the open model's chair from the draw pad, damaged each way."""
    from PIL import ImageDraw

    doodle = Image.new("RGB", (240, 240), (255, 255, 255))
    d = ImageDraw.Draw(doodle)
    k, ox = 2.6, -36
    for a, b, c, e in [(44, 14, 44, 54), (76, 14, 76, 54), (44, 16, 76, 16), (44, 26, 76, 26), (44, 36, 76, 36), (40, 54, 84, 54),
                       (84, 54, 80, 62), (80, 62, 44, 62), (44, 62, 40, 54), (44, 62, 44, 80), (80, 62, 80, 80), (48, 62, 46, 76),
                       (76, 62, 78, 76)]:
        d.line((ox + a * k, b * k, ox + c * k, e * k), fill=INK, width=6)
    return strip([(doodle, "you draw", INK), ("draw_damage/chair_intact.webp", "an open AI", INK),
                  ("draw_damage/chair_language_3.webp", "words part", BLUE),
                  ("draw_damage/chair_drawing_3.webp", "drawing part", ORANGE)], side=200, gap=26, arrows=(0,))


DAMAGED = {"damaged-painter": damaged_painter, "damaged-ideas": damaged_ideas, "damaged-clocks": damaged_clocks,
           "damaged-glimmer": damaged_glimmer, "damaged-janus": damaged_janus, "damaged-yourself": damaged_yourself}


def main(only: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, make in {**MAKERS, **DAMAGED}.items():
        if only and slug not in only:
            continue
        path, im = OUT / f"{slug}.webp", make()
        for quality in (80, 74, 68, 62):  # under the hub's 60 KB a card (tests/test_top_pages.py)
            im.save(path, "WEBP", quality=quality, method=6)
            if path.stat().st_size < 56_000:
                break
        print(f"{path.relative_to(IMG.parents[2])}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])

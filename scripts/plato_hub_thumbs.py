"""Card pictures for the Experiments hub (/plato): one 960 x 540 WebP per experiment that has no series picture yet,
put together from pictures the site already ships (static/img/...). Writes static/img/plato/hub/<slug>.webp.

    python scripts/plato_hub_thumbs.py

The hub prefers these over static/img/plato/series/<slug>.webp (site.py: hub_image). They live in their own folder
because the landing page's series cards read static/img/plato/series/ before the blind draw, and some of these
show Muse Image's chairs. The invisible Forms card shows Plato pointing up, not Muse Image's drawings of God, so
the God drawn on /draw stays blind.
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


def clock() -> Image.Image:
    """The clock test: the average clock of 315 adults (left, a group average from the study's public export) and of
    Muse Image's 16 clocks for the same words (right), on paper, each with a line saying whose it is."""
    from matplotlib import get_data_path
    from PIL import ImageDraw, ImageFont

    fonts = Path(get_data_path()) / "fonts" / "ttf"
    bold = ImageFont.truetype(str(fonts / "DejaVuSans-Bold.ttf"), 24)
    sans = ImageFont.truetype(str(fonts / "DejaVuSans.ttf"), 22)
    out = canvas()
    d = ImageDraw.Draw(out)
    side = 400
    for i, (src, who, what, colour) in enumerate((
            ("plato_clock/abc/form_315.webp", "315 adults", "their average clock", (194, 65, 12)),
            ("plato_clock/muse_avg.webp", "Meta’s AI", "its 16 clocks, averaged", (29, 78, 216)))):
        x = 60 + i * 450
        im = Image.open(IMG / src).convert("RGBA").resize((side, side), Image.LANCZOS)
        out.paste(im, (x, 22), im)
        d.text((x + 20, 444), who, font=bold, fill=(17, 24, 39))
        d.text((x + 20 + d.textlength(who + " ", font=bold), 446), what, font=sans, fill=(75, 85, 99))
        d.line((x + 20, 482, x + 120, 482), fill=colour, width=4)
    return out


MAKERS = {"inside": inside, "ideas": ideas, "bird": bird, "atlas": atlas, "telephone": telephone,
          "scale": scale, "phaedrus": phaedrus, "clock": clock}


def main(slugs: list[str] | None = None) -> None:
    """Every card picture, or only those named (python scripts/plato_hub_thumbs.py clock)."""
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, make in MAKERS.items():
        if slugs and slug not in slugs:
            continue
        path = OUT / f"{slug}.webp"
        make().save(path, "WEBP", quality=80, method=6)
        print(f"{path.relative_to(IMG.parents[2])}  {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    import sys

    main(sys.argv[1:] or None)

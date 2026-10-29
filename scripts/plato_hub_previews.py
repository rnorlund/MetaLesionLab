"""Hover previews for the Experiments hub cards (/plato) and the series cards (/): a horizontal strip of 16:9 frames
per experiment that has a sequence in the gallery, made from pictures the site already ships (static/img/gallery).
Writes static/img/plato/hub/preview-<slug>.webp.

    python scripts/plato_hub_previews.py

static/css/motion.css steps through a strip (background-position, steps()) while a card is hovered or focused, and
names each strip's frame count (--mo-n), so a change to FRAMES here needs the same count there
(tests/test_motion.py checks they match). Scenes (the damaged rocking chair) fill the frame; drawings sit whole in
the middle, on their own background colour.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageStat

IMG = Path(__file__).resolve().parents[1] / "metalesionlab" / "web" / "static" / "img"
OUT = IMG / "plato" / "hub"
W, H = 448, 252  # one frame; the cards are 16:9

# slug -> (gallery frames in order, "cover" for a scene that fills the frame or "contain" for a drawing)
FRAMES = {
    # Damage the painter: SDXL's rocking chair as its language part is damaged, until it draws a car
    "damage": ([f"damage-rocking-chair-{i}.webp" for i in (0, 1, 2, 3)], "cover"),
    # Plato's Telephone: a beanbag copied by Muse Spark and Muse Image becomes a croissant, a fan, a window
    "telephone": ([f"telephone-beanbag-{i}.webp" for i in (0, 2, 4, 7, 10)], "contain"),
    # Name the shadow: the drawing, its outline, its silhouette, its shadow on a wall
    "cave": ([f"cave-rabbit-{i}.webp" for i in (0, 1, 2, 3)], "contain"),
}


def edge_colour(im: Image.Image) -> tuple[int, int, int]:
    """The median colour of a picture's outer rows and columns: the background it sits on."""
    w, h = im.size
    strips = [im.crop((0, 0, w, 4)), im.crop((0, h - 4, w, h)), im.crop((0, 0, 4, h)), im.crop((w - 4, 0, w, h))]
    meds = [ImageStat.Stat(s).median for s in strips]
    return tuple(sorted(m[c] for m in meds)[len(meds) // 2] for c in range(3))


def frame(path: Path, how: str) -> Image.Image:
    im = Image.open(path).convert("RGB")
    if how == "cover":
        k = max(W / im.width, H / im.height)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        x, y = (im.width - W) // 2, (im.height - H) // 2
        return im.crop((x, y, x + W, y + H))
    out = Image.new("RGB", (W, H), edge_colour(im))
    pic = im.copy()
    pic.thumbnail((W - 24, H - 16), Image.LANCZOS)
    out.paste(pic, ((W - pic.width) // 2, (H - pic.height) // 2))
    return out


def strip(slug: str) -> Path:
    names, how = FRAMES[slug]
    out = Image.new("RGB", (W * len(names), H))
    for i, name in enumerate(names):
        out.paste(frame(IMG / "gallery" / name, how), (i * W, 0))
    path = OUT / f"preview-{slug}.webp"
    out.save(path, "WEBP", quality=64, method=6)  # each under 60 KB, like the hub pictures
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for slug in FRAMES:
        path = strip(slug)
        print(f"{path.relative_to(IMG.parents[3])}: {len(FRAMES[slug][0])} frames, {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()

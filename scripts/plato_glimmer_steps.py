"""Cut the featured "all" sprite of the Muse Glimmer damage experiment into one 300 px webp per step.

Input:  web/static/img/plato_glimmer/featured_all.webp  (columns = things in data order: chair, clock, god; rows = steps)
Output: web/static/img/plato_glimmer/steps/{chair,clock}_{0..5}.webp  (0 = undamaged ... 5 = 30% of neurons off)

Where no drawing came out (the sprite shows a grey square) the picture says so in words ("no drawing came out"), so a
visitor does not take a plain grey square for a broken image. God is deliberately not cut: the site never shows an AI's God drawing outside its own pages, so /draw's "Draw God" stays
blind (see the CARDS comment in metalesionlab/web/damaged_routes.py). Re-run after the sprite changes:
    python3 scripts/plato_glimmer_steps.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WEB = Path(__file__).resolve().parents[1] / "metalesionlab" / "web"
IMG = WEB / "static" / "img" / "plato_glimmer"
SHOW = ("chair", "clock")


def main() -> None:
    data = json.loads((WEB / "data" / "plato_glimmer.json").read_text())
    cell = data["sprites"]["feat"]
    things = [t["key"] for t in data["things"]]
    steps = data["damage"][0]["steps"]
    sprite = Image.open(IMG / "featured_all.webp").convert("RGB")
    assert sprite.size == (cell * len(things), cell * len(steps)), sprite.size
    out = IMG / "steps"
    out.mkdir(exist_ok=True)
    font = ImageFont.load_default(size=22)
    for thing in SHOW:
        c = things.index(thing)
        for r, step in enumerate(steps):
            tile = sprite.crop((c * cell, r * cell, (c + 1) * cell, (r + 1) * cell))
            if data["marks"][step["cond"]][thing]["drew"][data["featured"][thing]] != "1":  # this answer drew nothing
                ImageDraw.Draw(tile).text((cell // 2, cell // 2), "no drawing came out", fill=(70, 70, 70), font=font, anchor="mm")
            tile.save(out / f"{thing}_{r}.webp", "WEBP", quality=88)
    print(f"wrote {len(SHOW) * len(steps)} images to {out}")


if __name__ == "__main__":
    main()

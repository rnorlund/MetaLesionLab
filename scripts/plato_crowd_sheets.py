"""Ask it to be a crowd: contact sheets for looking by eye (written to $PLATO_CROWD_DIR/sheets/).

Usage:
  python scripts/plato_crowd_sheets.py --god-blind     God's 16 persona doodles in shuffled order, numbered 1-16,
                                                       no ages shown; the number -> file key goes to a separate file
  python scripts/plato_crowd_sheets.py --rows          per concept: the default doodles above, the persona doodles
                                                       below in age order with each age printed (for E3)
Pictures are ink-cropped as DINOv2 saw them. No network.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from metalesionlab import plato  # noqa: E402
from metalesionlab import plato_crowd as pc  # noqa: E402

SHEETS = pc.CROWD_DIR / "sheets"


def tile(path: Path, cell: int, caption: str | None) -> Image.Image:
    img = plato.ink_crop(Image.open(path).convert("RGB"), side=cell).convert("RGB")
    if caption:
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 9 * len(caption) + 8, 18), fill="white")
        d.text((4, 3), caption, fill="black")
    return img


def sheet(tiles: list[Image.Image], cols: int, cell: int, gap: int = 6) -> Image.Image:
    rows = (len(tiles) + cols - 1) // cols
    out = Image.new("RGB", (cols * cell + (cols - 1) * gap, rows * cell + (rows - 1) * gap), "lightgray")
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * (cell + gap), (i // cols) * (cell + gap)))
    return out


def god_blind() -> None:
    files = [p for p in plato.load_dir(pc.folder("god")) if "_age" in p.stem]
    order = np.random.default_rng(pc.SEED).permutation(len(files))
    tiles = [tile(files[j], 300, str(i + 1)) for i, j in enumerate(order)]
    SHEETS.mkdir(parents=True, exist_ok=True)
    sheet(tiles, 4, 300).save(SHEETS / "god_blind.png")
    (SHEETS / "god_blind_key.json").write_text(json.dumps({str(i + 1): files[j].name for i, j in enumerate(order)}, indent=1))
    print(f"wrote {SHEETS / 'god_blind.png'} ({len(files)} pictures); key in god_blind_key.json (don't open before labelling)")


def rows() -> None:
    SHEETS.mkdir(parents=True, exist_ok=True)
    for key in pc.KEYS:
        persona = [p for p in plato.load_dir(pc.folder(key)) if "_age" in p.stem]
        if not persona:
            continue
        default = plato.load_dir(pc.default_pictures_dir(key))
        tiles = [tile(p, 200, "default") for p in default] + [None] * (16 - len(default)) \
            + [tile(p, 200, str(pc.age_of(p.name))) for p in persona]
        blank = Image.new("RGB", (200, 200), "lightgray")
        sheet([t or blank for t in tiles], 8, 200).save(SHEETS / f"rows_{key}.png")
        print(f"wrote rows_{key}.png: {len(default)} default, {len(persona)} persona")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--god-blind", action="store_true")
    ap.add_argument("--rows", action="store_true")
    args = ap.parse_args()
    if args.god_blind:
        god_blind()
    if args.rows:
        rows()


if __name__ == "__main__":
    main()

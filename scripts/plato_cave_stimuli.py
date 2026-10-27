"""Plato's Cave stimuli: original, outline, silhouette and cast shadow for the 100 core pictures.

  build   write $CAVE_DIR/stimuli/<version>/<word>.png and stimuli/meta.json, plus a QC sheet

Data stay outside the repository ($CAVE_DIR, default PlatosChair/cave).
"""
import argparse
import json
import time

from PIL import Image, ImageDraw

from metalesionlab import plato_cave as pc
from metalesionlab.plato import grid


def cmd_build(args):
    items = pc.load_items()
    root = pc.CAVE_DIR / "stimuli"
    for v in pc.VERSIONS:
        (root / v).mkdir(parents=True, exist_ok=True)
    meta, tiles = [], []
    t0 = time.time()
    for i, it in enumerate(items):
        with Image.open(it.image) as im:
            v = pc.make_versions(im, radius=pc.RADIUS_OVERRIDES.get(it.word), seal=it.word in pc.OPEN_ITEMS,
                                 seed=i)
        for name, img in v.images.items():
            img.save(root / name / f"{it.word}.png", optimize=True)
        meta.append({"word": it.word, "alternates": list(it.alternates), "source_image": str(it.image),
                     "mask": v.source, "closing_radius": v.radius, "fill_ratio": round(v.fill_ratio, 3),
                     "solidity": round(v.solidity, 4)})
        tiles += [v.images[n] for n in pc.VERSIONS]
        if args.limit and i + 1 >= args.limit:
            break
    (root / "meta.json").write_text(json.dumps({"versions": list(pc.VERSIONS), "side": pc.SIDE, "items": meta},
                                               indent=1))
    sheet = grid(tiles, cols=8, cell=150, gap=4, bg="#dddddd")
    d = ImageDraw.Draw(sheet)
    for k, m in enumerate(meta):
        x, y = (k % 2) * 4 * 154, (k // 2) * 154
        d.text((x + 3, y + 3), f"{m['word']} {m['mask']} r{m['closing_radius']:g}", fill=(220, 0, 0))
    (pc.CAVE_DIR / "qc").mkdir(exist_ok=True)
    sheet.save(pc.CAVE_DIR / "qc" / "stimuli_sheet.png")
    print(f"{len(meta)} items in {time.time() - t0:.0f}s -> {root}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("build")
    p.add_argument("--limit", type=int, default=0)
    p.set_defaults(fn=cmd_build)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

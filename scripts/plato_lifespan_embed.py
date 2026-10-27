"""The life of a chair: embed children's drawings and Stable Diffusion pictures with Meta's DINOv2, locally.

Usage: python -I scripts/plato_lifespan_embed.py [--sources kids kids_png sd sd_g4] [--keys chair ...]

- kids      kiddraw stroke data (only drawings in stringent_cleaned_dataset), clipped to the visible canvas,
            simplified exactly like Quick, Draw! (to_quickdraw), rendered by plato.render_strokes, ink_crop.
            This is the primary rendering: identical to how the adult (Quick, Draw!) drawings were rendered.
- kids_png  the released 150 px PNGs on white, cropped to their ink by the alpha channel (robustness check).
- sd, sd_g4 Stable Diffusion pictures in $PLATO_LIFESPAN_DIR/ai/<sd|sd_g4>/<ckpt>/<key>/s<i>.png, ink_crop.

Writes $PLATO_LIFESPAN_DIR/embeddings/<source>/<key>.npz (sd: embeddings/<source>/<ckpt>/<key>.npz) with
file names, ages (kids) and the CLS and mean-patch tokens. No drawing is written anywhere. Cached: a set is
re-embedded only when its file list or PREP changes. Runs on this Mac (MPS or CPU).
"""
import argparse
import csv
import glob
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab.plato import DINO_MODEL, Embedder, ink_crop, render_strokes  # noqa: E402
from metalesionlab.plato_lifespan import (AI_KEYS, CHECKPOINTS, KEY_TO_KIDDRAW, LIFESPAN_DIR, SHARED_KEYS,  # noqa: E402
                                          clip_strokes, parse_svgs, to_quickdraw)

RAW = LIFESPAN_DIR / "kiddraw_raw"
PREP = {"kids": "clip 810 + to_quickdraw(eps 2) + render_strokes(256, w3) + ink_crop(256)",
        "kids_png": "alpha bbox crop + pad 6% + 256 px on white",
        "sd": "ink_crop(256)", "sd_g4": "ink_crop(256)"}


def alpha_crop(path: Path, side: int = 256, margin: float = 0.06) -> Image.Image | None:
    rgba = Image.open(path).convert("RGBA")
    box = rgba.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()
    if not box:
        return None
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    white.alpha_composite(rgba)
    g = white.convert("L").crop(box)
    w, h = g.size
    s = int(max(w, h) * (1 + 2 * margin)) or 1
    canvas = Image.new("L", (s, s), 255)
    canvas.paste(g, ((s - w) // 2, (s - h) // 2))
    return canvas.resize((side, side), Image.LANCZOS).convert("RGB")


def kid_rows(cat: str, stringent: set[str]):
    """(png name, age, svgs) for every drawing of one kiddraw category in the stringent set."""
    csv.field_size_limit(10 ** 9)
    seen = set()
    files = glob.glob(str(RAW / "strokes" / "full_dataset_with_strokes" / f"*_a {cat}.csv"))
    files += glob.glob(str(RAW / "strokes" / "full_dataset_with_strokes" / f"*_an {cat}.csv"))
    for f in sorted(files):
        for r in csv.DictReader(open(f, newline="")):
            name = f"{cat}_sketch_{r['age']}_{r['session_id']}.png"
            if name in stringent and name not in seen:
                seen.add(name)
                yield name, int(r["age"].removeprefix("age")), r["svgs"]


def save(out: Path, names, vecs, prep, **extra):
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, files=np.array(names), model=DINO_MODEL, prep=prep, **vecs, **extra)


def cached(out: Path, names, prep) -> bool:
    if not out.exists():
        return False
    old = np.load(out)
    return list(old["files"]) == list(names) and str(old["prep"]) == prep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", nargs="*", default=["kids", "sd"], choices=list(PREP))
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--device")
    args = ap.parse_args()
    embed = None
    t0 = time.time()
    stringent = {p.name for p in (RAW / "drawings" / "stringent_cleaned_dataset").glob("*.png")}
    for source in args.sources:
        if source in ("kids", "kids_png"):
            for key in args.keys or SHARED_KEYS:
                cat = KEY_TO_KIDDRAW[key]
                rows = sorted(kid_rows(cat, stringent))
                out = LIFESPAN_DIR / "embeddings" / source / f"{key}.npz"
                names, ages, imgs, dropped = [], [], [], 0
                for name, age, svgs in rows:
                    if source == "kids":
                        qd = to_quickdraw(clip_strokes(parse_svgs(svgs)))
                        img = ink_crop(render_strokes(qd)) if qd else None
                    else:
                        img = alpha_crop(RAW / "drawings" / "stringent_cleaned_dataset" / name)
                    if img is None:
                        dropped += 1
                        continue
                    names.append(name)
                    ages.append(age)
                    imgs.append(img)
                if not names:
                    sys.exit(f"no drawings found for {key} ({cat}): check the stroke files")
                if cached(out, names, PREP[source]):
                    continue
                embed = embed or Embedder(DINO_MODEL, args.device)
                save(out, names, embed(imgs), PREP[source], ages=np.array(ages), dropped=dropped)
                print(f"{source:8s} {key:10s} {len(names):5d} drawings, {dropped} without ink "
                      f"({time.time() - t0:.0f}s)", flush=True)
        else:
            for ckpt, *_ in CHECKPOINTS:
                for key in args.keys or AI_KEYS:
                    folder = LIFESPAN_DIR / "ai" / source / ckpt / key
                    files = sorted(folder.glob("s*.png"), key=lambda p: int(p.stem[1:]))
                    if not files:
                        continue
                    out = LIFESPAN_DIR / "embeddings" / source / ckpt / f"{key}.npz"
                    names = [f.name for f in files]
                    if cached(out, names, PREP[source]):
                        continue
                    embed = embed or Embedder(DINO_MODEL, args.device)
                    save(out, names, embed([ink_crop(Image.open(f).convert("RGB")) for f in files]), PREP[source])
                    print(f"{source:8s} {ckpt} {key:10s} {len(names):3d} pictures ({time.time() - t0:.0f}s)",
                          flush=True)
    print(f"done in {time.time() - t0:.0f}s" + (f" on {embed.device}" if embed else " (all cached)"))


if __name__ == "__main__":
    main()

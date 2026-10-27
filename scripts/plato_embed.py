"""Plato's Chair, step 3: embed every picture with Meta's DINOv2 (facebook/dinov2-base), locally.

Usage: python -I scripts/plato_embed.py [--keys chair ...] [--device mps|cpu]

Doodles (AI and human) are ink-cropped to a square first (see plato.ink_crop); photos are used as is.
Embeddings are cached per concept in $PLATO_DIR/embeddings/<source>/<key>.npz with the file list,
the CLS token and the mean patch token; a concept is re-embedded only when its files or PREP change.
Sources: ai_doodle (and ai_photo, ai_sdxl_doodle if present) and human. Runs on this Mac (MPS or CPU), never on a GPU server.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab.plato import CONCEPTS, DINO_MODEL, PLATO_DIR, Embedder, ink_crop, load_dir  # noqa: E402

PREP = "flatten_paper(21, 215) + ink_crop(256, margin 0.06, threshold 200, speck 3px)"  # change it and everything re-embeds
SOURCES = {"ai_doodle": PLATO_DIR / "ai" / "doodle", "ai_photo": PLATO_DIR / "ai" / "photo",
           "ai_sdxl_doodle": PLATO_DIR / "ai" / "sdxl_doodle",  # comparison generator (plato_sdxl_generate.py)
           "human": PLATO_DIR / "human"}


def prepare(path: Path, source: str) -> Image.Image:
    img = Image.open(path).convert("RGB")
    return img if source == "ai_photo" else ink_crop(img)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--device")
    args = ap.parse_args()
    keys = args.keys or [c.key for c in CONCEPTS]
    embed = None
    t0, count = time.time(), 0
    for source, root in SOURCES.items():
        for key in keys:
            files = load_dir(root / key)
            if not files:
                continue
            out = PLATO_DIR / "embeddings" / source / f"{key}.npz"
            names = [f.name for f in files]
            if out.exists():
                old = np.load(out)
                if list(old["files"]) == names and "prep" in old and str(old["prep"]) == PREP:
                    continue
            embed = embed or Embedder(DINO_MODEL, args.device)
            vecs = embed([prepare(f, source) for f in files])
            out.parent.mkdir(parents=True, exist_ok=True)
            np.savez(out, files=np.array(names), model=DINO_MODEL, prep=PREP, **vecs)
            count += len(files)
            print(f"{source:9s} {key:12s} {len(files):4d} pictures ({time.time() - t0:.0f}s)", flush=True)
    print(f"embedded {count} pictures in {time.time() - t0:.0f}s"
          + (f" on {embed.device}" if embed else " (all cached)"))


if __name__ == "__main__":
    main()

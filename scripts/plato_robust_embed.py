"""Plato's Chair, does it depend on DINOv2? Re-embed every picture with other vision models, locally.

Usage: python -I scripts/plato_robust_embed.py [--embedders dinov2_large pe_core_l14 siglip2_so400m]
                                               [--sources ...] [--keys ...] [--device mps|cpu] [--site DIR]

Same pictures and the same ink crop as scripts/plato_embed.py (plato_embed.prepare and PREP): each picture is
cropped once and given to every embedder, which then applies its own standard resize and normalization.
Embedders are listed in metalesionlab.plato_robust.EMBEDDERS. PE-Core loads through timm, which needs
torchvision; neither is a project dependency, so install them into a separate folder and pass it with --site
(default ~/MetaLesionLab_robust/pylib if it exists):
    pip install --no-deps --target ~/MetaLesionLab_robust/pylib torchvision==0.29.1 timm==1.0.30
(torchvision must match the installed torch; 0.29.1 goes with torch 2.14.1.)
Caches $PLATO_DIR/embeddings_robust/<embedder>/<source>/<key>.npz with the file list, model, feature, PREP
and 'emb' (DINOv2 also 'patch_mean'); a concept is re-embedded only when its files or PREP change.
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from plato_embed import PREP, SOURCES, prepare  # noqa: E402

from metalesionlab.plato import CONCEPTS, PLATO_DIR, load_dir  # noqa: E402
from metalesionlab.plato_robust import ALTERNATIVES, EMBEDDERS, ImageEmbedder  # noqa: E402

OUT = PLATO_DIR / "embeddings_robust"
DEFAULT_SITE = Path.home() / "MetaLesionLab_robust" / "pylib"


def cached(path: Path, names: list[str]) -> bool:
    if not path.exists():
        return False
    old = np.load(path)
    return list(old["files"]) == names and str(old["prep"]) == PREP


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedders", nargs="*", default=ALTERNATIVES, choices=list(EMBEDDERS))
    ap.add_argument("--sources", nargs="*", choices=list(SOURCES))
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--device")
    ap.add_argument("--site", type=Path, default=DEFAULT_SITE if DEFAULT_SITE.exists() else None)
    args = ap.parse_args()
    if args.site:
        sys.path.insert(0, str(args.site))
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    keys = args.keys or [c.key for c in CONCEPTS]
    models: dict[str, ImageEmbedder] = {}
    t0, count = time.time(), 0
    for source, root in SOURCES.items():
        if args.sources and source not in args.sources:
            continue
        for key in keys:
            files = load_dir(root / key)
            if not files:
                continue
            names = [f.name for f in files]
            todo = [t for t in args.embedders if not cached(OUT / t / source / f"{key}.npz", names)]
            if not todo:
                continue
            images = [prepare(f, source) for f in files]
            for tag in todo:
                if tag not in models:
                    print(f"loading {tag} ({EMBEDDERS[tag].model_id}) ...", flush=True)
                    models[tag] = ImageEmbedder(EMBEDDERS[tag], args.device)
                vecs = models[tag](images)
                out = OUT / tag / source / f"{key}.npz"
                out.parent.mkdir(parents=True, exist_ok=True)
                np.savez(out, files=np.array(names), model=EMBEDDERS[tag].model_id, feature=EMBEDDERS[tag].feature,
                         prep=PREP, **vecs)
            count += len(files)
            print(f"{source:16s} {key:12s} {len(files):4d} pictures x {len(todo)} embedders "
                  f"({time.time() - t0:.0f}s)", flush=True)
    device = next(iter(models.values())).device if models else None
    print(f"embedded {count} pictures in {time.time() - t0:.0f}s" + (f" on {device}" if device else " (all cached)"))


if __name__ == "__main__":
    main()

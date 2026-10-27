"""Draw your chair (/draw): precompute the reference data the page compares a visitor's drawing with.

Reads the Plato's Chair data folder ($PLATO_DIR, outside the repository): the cached DINOv2-base CLS
embeddings of Muse Image's first-run doodles and of 200 people's Quick, Draw! drawings per concept, the
pictures themselves, and results.json / results_variety.json. Writes:

  metalesionlab/web/data/draw.json            page data: per-concept statistics, leave-one-out
                                              distances, the 2-D map, sprite layout, and the 35 people's
                                              centroids (float16) for the "does it look like a chair?" check
  metalesionlab/web/data/draw/<key>.json      server only: centroids, the map's PCA axes, and every
                                              picture's unit vector as int8 (nearest-neighbour search)
  metalesionlab/web/static/img/draw/<key>_muse.webp, <key>_people.webp
                                              thumbnail sprites, ink-cropped as DINOv2 saw them

No raw drawing files are copied: people's drawings appear only as small thumbnails, credited on the page
(Google Quick, Draw!, CC BY 4.0). No network, no API calls.

    python scripts/draw_export.py [--keys chair umbrella ...]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from metalesionlab.draw import pack, pack_int8, unit  # noqa: E402
from metalesionlab.plato import (BY_KEY, CONCEPTS, DINO_MODEL, PLATO_DIR, QUICKDRAW_CREDIT, ink_crop,  # noqa: E402
                                 load_dir)

WEB = REPO / "metalesionlab" / "web"
OUT = WEB / "data" / "draw.json"
VEC_DIR = WEB / "data" / "draw"
IMG = WEB / "static" / "img" / "draw"
KEYS = ["chair", "umbrella", "bicycle", "house", "cat", "tree", "face", "sailboat", "cup", "book"]
PREP = "flatten_paper(21, 215) + ink_crop(256, margin 0.06, threshold 200, speck 3px)"  # scripts/plato_embed.py
SPRITES = {"muse": {"cell": 112, "cols": 8}, "people": {"cell": 80, "cols": 20}}


def load(source: str, key: str) -> tuple[list[str], np.ndarray]:
    d = np.load(PLATO_DIR / "embeddings" / source / f"{key}.npz")
    if str(d["prep"]) != PREP or str(d["model"]) != DINO_MODEL:
        raise SystemExit(f"{source}/{key}: embeddings were made with a different model or preparation")
    return [str(f) for f in d["files"]], unit(d["cls"].astype(np.float64))


def loo_distances(x: np.ndarray) -> np.ndarray:
    """Each row's cosine distance to the mean of the other rows (all rows unit length)."""
    total = x.sum(0)
    others = unit((total[None, :] - x) / (len(x) - 1))
    return 1.0 - (others * x).sum(1)


def pca_map(ai: np.ndarray, people: np.ndarray) -> tuple[np.ndarray, np.ndarray, list[float]]:
    """Two principal axes of the concept's unit vectors (Muse's and people's together), oriented so
    Muse's doodles sit on the left and toward the top of the map."""
    x = np.vstack([ai, people])
    mean = x.mean(0)
    _, s, vt = np.linalg.svd(x - mean, full_matrices=False)
    axes = vt[:2].copy()
    ai_xy = (ai - mean) @ axes.T
    if ai_xy[:, 0].mean() > 0:
        axes[0] *= -1
    if ai_xy[:, 1].mean() < 0:
        axes[1] *= -1
    explained = (s ** 2 / (s ** 2).sum())[:2]
    return mean, axes, [round(float(e), 3) for e in explained]


def sprite(files: list[Path], cell: int, cols: int, out: Path, thicken: bool = False) -> dict:
    """One WebP of thumbnails, ink-cropped as DINOv2 saw them. People's 3 px lines turn faint gray at
    80 px, so `thicken` widens them a little (display only; the embeddings are untouched)."""
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("L", (cols * cell, rows * cell), 255)
    for i, f in enumerate(files):
        tile = ink_crop(Image.open(f).convert("RGB")).convert("L")
        if thicken:
            tile = tile.filter(ImageFilter.MinFilter(3))
        tile = tile.resize((cell, cell), Image.LANCZOS)
        sheet.paste(tile, ((i % cols) * cell, (i // cols) * cell))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "WEBP", quality=78, method=6)
    return {"src": f"/static/img/draw/{out.name}", "cell": cell, "cols": cols, "n": len(files),
            "bytes": out.stat().st_size}


def stats_for(key: str, results: dict, variety: dict) -> dict:
    r = next(c for c in results["concepts"] if c["key"] == key)
    v = next((c for c in variety.get("concepts", []) if c["key"] == key), {})
    asked = None
    for cond, how in (("unusual", "asked for an unusual kind"), ("listed", "asked for a list of different kinds")):
        block = v.get(cond)
        if isinstance(block, dict) and block.get("ratio_vs_people") is not None:
            asked = {"prompt": cond, "how": how, "ratio_vs_people": round(block["ratio_vs_people"], 3),
                     "ratio_vs_people_ci95": [round(x, 3) for x in block.get("ratio_vs_people_ci95", [])],
                     "ratio_vs_default": round(block.get("ratio_vs_default") or 0, 3)}
            break
    return {"ai_spread": r["ai_spread"], "human_spread": r["human_spread"],
            "index": r["homogenization_index"], "index_ci95": r["homogenization_index_ci95"],
            "when_asked": asked}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", nargs="*", default=KEYS)
    args = ap.parse_args()
    results = json.loads((PLATO_DIR / "results.json").read_text())
    variety_path = PLATO_DIR / "results_variety.json"
    variety = json.loads(variety_path.read_text()) if variety_path.exists() else {}

    concepts = []
    for key in args.keys:
        c = BY_KEY[key]
        ai_files, ai = load("ai_doodle", key)
        people_files, people = load("human", key)
        ai_dir, people_dir = PLATO_DIR / "ai" / "doodle" / key, PLATO_DIR / "human" / key
        if [p.name for p in load_dir(ai_dir)] != ai_files or [p.name for p in load_dir(people_dir)] != people_files:
            raise SystemExit(f"{key}: picture files and embeddings don't match; run scripts/plato_embed.py")
        ai_c, people_c = ai.mean(0), people.mean(0)
        mean, axes, explained = pca_map(ai, people)
        r4 = lambda a: [round(float(v), 4) for v in a]  # noqa: E731
        (VEC_DIR / f"{key}.json").parent.mkdir(parents=True, exist_ok=True)
        (VEC_DIR / f"{key}.json").write_text(json.dumps({
            "key": key, "model": DINO_MODEL, "embedding": "CLS, unit length",
            "ai_centroid": pack(ai_c), "human_centroid": pack(people_c),
            "pca_mean": pack(mean), "pca_axes": pack(axes),
            "ai": pack_int8(ai), "people": pack_int8(people),
        }, separators=(",", ":")) + "\n")
        sprites = {
            "muse": sprite([ai_dir / f for f in ai_files], **SPRITES["muse"], out=IMG / f"{key}_muse.webp"),
            "people": sprite([people_dir / f for f in people_files], **SPRITES["people"], thicken=True,
                             out=IMG / f"{key}_people.webp"),
        }
        concepts.append({
            "key": key, "label": c.label, "n_ai": len(ai), "n_human": len(people),
            "vectors": f"draw/{key}.json",
            "stats": stats_for(key, results, variety),
            "ai_loo": r4(loo_distances(ai)),
            "human_loo": r4(loo_distances(people)),
            "human_to_ai": r4(1.0 - people @ unit(ai_c)),
            "ai_to_ai": r4(1.0 - ai @ unit(ai_c)),
            "map": {"ai": [r4(p) for p in (ai - mean) @ axes.T], "human": [r4(p) for p in (people - mean) @ axes.T],
                    "explained": explained},
            "sprites": sprites,
        })
        print(f"{key:9s} AI {len(ai):2d}, people {len(people)}; sprites "
              f"{sprites['muse']['bytes'] // 1024} + {sprites['people']['bytes'] // 1024} KB; "
              f"vectors {(VEC_DIR / f'{key}.json').stat().st_size // 1024} KB; map explains {sum(explained):.0%}")

    lib_keys = [c.key for c in CONCEPTS]
    lib = np.stack([load("human", k)[1].mean(0) for k in lib_keys])
    data = {
        "about": "Draw your chair: reference data for placing a visitor's drawing among Muse Image's doodles and "
                 "200 people's drawings of the same thing. Written by scripts/draw_export.py.",
        "model": DINO_MODEL, "embedding": "CLS token", "distance": "cosine", "prep": PREP,
        "ai_source": "Muse Image 1.0, first run of the Plato's Chair doodle prompt",
        "credits": [QUICKDRAW_CREDIT, "Embeddings: Meta DINOv2 (facebook/dinov2-base, Apache-2.0)",
                    "AI drawings: Meta Muse Image"],
        "concepts": concepts,
        "centroids": {"keys": lib_keys, "labels": {c.key: c.label for c in CONCEPTS}, "vectors": pack(lib, "float16")},
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    total = OUT.stat().st_size + sum(p.stat().st_size for p in VEC_DIR.glob("*.json")) + \
        sum(p.stat().st_size for p in IMG.glob("*.webp"))
    print(f"wrote {OUT.relative_to(REPO)} ({OUT.stat().st_size // 1024} KB); everything together {total / 1e6:.2f} MB")


if __name__ == "__main__":
    main()

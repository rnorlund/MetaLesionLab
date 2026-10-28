"""The Atlas of Forms benchmark: how uniformly does YOUR image model draw everyday things, next to people?

Point it at a folder of your model's drawings, one subfolder per concept:

    my_model/
      chair/        0.png 1.png ... (at least 4 pictures; 12 or more is better)
      teddy bear/   ...
      sea_turtle/   ...

and run
    python scripts/plato_benchmark.py my_model --name "My model" --out my_model_atlas.json

Subfolder names are Quick, Draw! category names from the Atlas's 135 concepts (spaces, "_" or "-" all work;
"boat", "lamp" and "person" mean sailboat, floor lamp and yoga). Others are listed and skipped. Pictures
can be PNG, JPEG or WebP, any size, ideally black line drawings on white, made with the Atlas prompt:
"A quick simple doodle sketch of {a chair}, black marker on plain white, like a 20-second drawing, no text,
no shading."

What it does, exactly as in the Atlas (docs/plato_atlas.md):
- ink-crops every picture (paper flattened, cropped to the ink, padded square, 256 px) and embeds it with
  Meta's DINOv2 (facebook/dinov2-base, CLS token);
- spread = mean pairwise cosine distance between a concept's pictures;
- the human reference is the first 200 recognized Quick, Draw! drawings of each concept (CC BY 4.0),
  streamed from Google's public bucket, rendered and embedded the same way, and cached in --cache
  (default ~/.cache/plato_atlas); the first run for a concept downloads and builds it, later runs reuse it;
- ratio = your spread / people's spread at the same n, with a 95% CI from independent bootstraps;
  below 1 means your model draws the thing more uniformly than people do;
- the median ratio over your concepts gets a two-level bootstrap CI, and Muse Image's and SDXL's ratios
  for the same concepts are read from public_data/plato_atlas.json for comparison.

Needs: numpy, scipy, pillow, httpx, torch and transformers (pip install -e . plus torch and transformers).
DINOv2 runs on CUDA, Apple MPS or the CPU (--device). Human drawings: Google Quick, Draw! dataset
(Google Creative Lab), CC BY 4.0, https://github.com/googlecreativelab/quickdraw-dataset
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from plato_embed import PREP  # noqa: E402  (the core's preparation string; change it and caches rebuild)

from metalesionlab import plato_atlas as A  # noqa: E402
from metalesionlab.plato import (DINO_MODEL, QUICKDRAW_CREDIT, cosine_distances, ink_crop,  # noqa: E402
                                 render_strokes, spread, stream_quickdraw, to_jsonable)

REPO = Path(__file__).resolve().parents[1]
REFERENCE = REPO / "public_data" / "plato_atlas.json"
CACHE = Path.home() / ".cache" / "plato_atlas"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
ALIASES = {"boat": "sailboat", "lamp": "floor lamp", "person": "yoga", "seesaw": "see saw",
           "roller skates": "rollerskates", "teddy bear": "teddy-bear", "tshirt": "t-shirt"}

Embed = Callable[[list], dict]  # list of PIL images -> {"cls": (n, d) array, ...}


def norm(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", name.strip().lower()))


def lookup() -> dict[str, A.AtlasConcept]:
    out = {}
    for c in A.CONCEPTS:
        for name in (c.quickdraw, c.label, c.key):
            out[norm(name)] = c
    for alias, qd in ALIASES.items():
        out[norm(alias)] = next(c for c in A.CONCEPTS if c.quickdraw == qd)
    return out


def match_folders(root: Path, only: list[str] | None = None) -> tuple[list[tuple[A.AtlasConcept, Path]], list[str]]:
    """(concept, folder) for every subfolder that names an Atlas concept, and the names that don't."""
    table, found, unknown = lookup(), [], []
    wanted = {table[norm(w)].key for w in only if norm(w) in table} if only else None
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        c = table.get(norm(d.name))
        if c is None:
            unknown.append(d.name)
        elif wanted is None or c.key in wanted:
            found.append((c, d))
    return found, unknown


def pictures(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT and not p.name.startswith("."))


def prepare(img: Image.Image) -> Image.Image:
    return ink_crop(img.convert("RGB"))


class DinoEmbed:
    """DINOv2 CLS embeddings, loaded on first use."""

    def __init__(self, device: str | None = None):
        self.device, self._e = device, None

    def __call__(self, images: list) -> dict:
        if self._e is None:
            from metalesionlab.plato import Embedder

            self._e = Embedder(DINO_MODEL, self.device)
            print(f"loaded {DINO_MODEL} on {self._e.device}", flush=True)
        return self._e(images)


def human_reference(c: A.AtlasConcept, cache: Path, embed: Embed, model_id: str = DINO_MODEL,
                    fetch: Callable = stream_quickdraw, n: int = A.N_HUMAN) -> np.ndarray:
    """People's CLS embeddings for one concept: from the cache, or streamed from Quick, Draw!, rendered,
    ink-cropped, embedded and cached (first `n` drawings with recognized=true, as in the Atlas)."""
    path = cache / "human" / f"{c.key}.npz"
    if path.exists():
        z = np.load(path)
        if str(z["model"]) == model_id and str(z["prep"]) == PREP and "n_target" in z and int(z["n_target"]) == n:
            return z["cls"]
    kept = []
    for attempt in range(5):
        try:
            kept = fetch(c.quickdraw, keep=n, max_lines=5000)
            if len(kept) < n:
                kept = fetch(c.quickdraw, keep=n, max_lines=20000)
            break
        except Exception as e:  # noqa: BLE001 - flaky networks: retry with backoff
            print(f"  {c.label}: download attempt {attempt + 1} failed ({type(e).__name__}); retrying", flush=True)
            time.sleep(5 * 2 ** attempt)
    if len(kept) < 8:
        raise RuntimeError(f"could not get people's drawings of {c.quickdraw!r}")
    vecs = embed([prepare(render_strokes(r["drawing"])) for r in kept])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, model=model_id, prep=PREP, quickdraw=c.quickdraw, n_target=n,
             key_ids=np.array([str(r.get("key_id")) for r in kept]), cls=vecs["cls"])
    return vecs["cls"]


def reference_rows(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {r["quickdraw"]: r for r in json.loads(path.read_text()).get("concepts", [])}


def run(root: Path, embed: Embed, cache: Path = CACHE, reference: Path = REFERENCE, only: list[str] | None = None,
        min_pictures: int = 4, model_id: str = DINO_MODEL, fetch: Callable = stream_quickdraw, name: str = "",
        seed: int = A.SEED, log=print) -> dict:
    rng = np.random.default_rng(seed)
    found, unknown = match_folders(root, only)
    ref = reference_rows(reference)
    rows, skipped, boots = [], [], []
    for c, folder in found:
        files = pictures(folder)
        if len(files) < min_pictures:
            skipped.append({"concept": c.label, "pictures": len(files), "reason": f"fewer than {min_pictures}"})
            continue
        a = embed([prepare(Image.open(f)) for f in files])["cls"]
        h = human_reference(c, cache, embed, model_id, fetch)
        s = A.spread_ratio(a, h, rng=rng)
        r = ref.get(c.quickdraw, {})
        row = {"concept": c.label, "quickdraw": c.quickdraw, "domain": c.domain, "n": s["n"],
               "spread": s["spread"], "spread_ci95": s["spread_ci95"], "human_spread": s["human_spread"],
               "human_spread_ci95": s["human_spread_ci95"], "ratio": s["ratio"], "ratio_ci95": s["ratio_ci95"],
               "share_of_human_sets_as_uniform": s["share_of_human_sets_as_uniform"],
               "muse_ratio": r.get("ratio"), "sdxl_ratio": r.get("sdxl_ratio"), "atlas_rank_muse": r.get("rank")}
        if r.get("human_spread_all") is not None:
            row["human_reference_check"] = abs(spread(cosine_distances(h)) - r["human_spread_all"])
        rows.append(row)
        boots.append(s["_ratio_boot"])
        log(f"{c.label:18s} n={s['n']:3d}  ratio {s['ratio']:.2f} [{s['ratio_ci95'][0]:.2f}, {s['ratio_ci95'][1]:.2f}]"
            + (f"   Muse {r['ratio']:.2f}" if r.get("ratio") is not None else ""))
    out = {"model": name or root.name, "benchmark": "The Atlas of Forms (Plato's Chair)",
           "embedding_model": model_id, "prep": PREP, "human_reference": f"first {A.N_HUMAN} recognized Quick, Draw! "
           "drawings per concept", "attribution": QUICKDRAW_CREDIT, "n_concepts": len(rows),
           "unknown_folders": unknown, "skipped": skipped, "concepts": sorted(rows, key=lambda r: r["ratio"])}
    if rows:
        ratios = np.array([r["ratio"] for r in rows])
        below = int((ratios < 1).sum())
        out["summary"] = {"median_ratio": float(np.median(ratios)), "median_ratio_ci95": A.median_ci(boots, rng=rng),
                          "below_1": below, "share_below_1_ci95": A.wilson_ci(below, len(rows)),
                          "ci_entirely_below_1": int(sum(r["ratio_ci95"][1] < 1 for r in rows)),
                          "ci_entirely_above_1": int(sum(r["ratio_ci95"][0] > 1 for r in rows))}
        for other in ("muse", "sdxl"):
            same = [r[f"{other}_ratio"] for r in rows if r.get(f"{other}_ratio") is not None]
            if same:
                out["summary"][f"{other}_median_ratio_same_concepts"] = float(np.median(same))
                out["summary"][f"{other}_n_same_concepts"] = len(same)
        checks = [r["human_reference_check"] for r in rows if "human_reference_check" in r]
        if checks and max(checks) > 0.01:
            out["warning"] = ("Your human reference differs from the Atlas's by up to "
                              f"{max(checks):.3f} in spread; check the cache and the model.")
    return out


def report(out: dict) -> str:
    lines = [f"\n{out['model']}: {out['n_concepts']} concepts"]
    s = out.get("summary")
    if s:
        lines.append(f"median ratio {s['median_ratio']:.2f} [95% CI {s['median_ratio_ci95'][0]:.2f}, "
                     f"{s['median_ratio_ci95'][1]:.2f}]; below 1 (more uniform than people) for {s['below_1']} of "
                     f"{out['n_concepts']}")
        for other, label in (("muse", "Muse Image"), ("sdxl", "SDXL")):
            if f"{other}_median_ratio_same_concepts" in s:
                lines.append(f"  {label} on the same {s[f'{other}_n_same_concepts']} concepts: median "
                             f"{s[f'{other}_median_ratio_same_concepts']:.2f}")
    if out["unknown_folders"]:
        lines.append(f"not Atlas concepts (skipped): {', '.join(out['unknown_folders'])}")
    for sk in out["skipped"]:
        lines.append(f"skipped {sk['concept']}: {sk['pictures']} pictures ({sk['reason']})")
    if out.get("warning"):
        lines.append("WARNING: " + out["warning"])
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Spread ratios of your model's drawings against people's (Quick, Draw!).")
    ap.add_argument("drawings", type=Path, nargs="?", help="folder with one subfolder of pictures per concept")
    ap.add_argument("--name", default="", help="your model's name, for the output")
    ap.add_argument("--out", type=Path, help="write the results as JSON here")
    ap.add_argument("--cache", type=Path, default=CACHE, help="where people's embeddings are cached")
    ap.add_argument("--reference", type=Path, default=REFERENCE, help="the Atlas's public results (for comparison)")
    ap.add_argument("--concepts", nargs="*", help="only these concepts")
    ap.add_argument("--min-pictures", type=int, default=4)
    ap.add_argument("--device", help="cuda, mps or cpu (default: the best available)")
    ap.add_argument("--list", action="store_true", help="print the 135 concept names and exit")
    args = ap.parse_args()
    if args.list:
        print("\n".join(c.quickdraw for c in A.CONCEPTS))
        return
    if args.drawings is None or not args.drawings.is_dir():
        ap.error(f"{args.drawings} is not a folder")
    out = run(args.drawings, DinoEmbed(args.device), args.cache, args.reference, args.concepts, args.min_pictures,
              name=args.name)
    print(report(out))
    if args.out:
        args.out.write_text(json.dumps(to_jsonable(out), indent=1, ensure_ascii=False))
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

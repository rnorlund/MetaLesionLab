"""Plato's Chair at full size: 200 of Muse Image's chairs against 200 people's, one for one.

Added Nov 1, after the main analysis, as a robustness check (not pre-registered). Roger asked whether 16 drawings
per thing is enough; the main analysis compares the AI's 16 with 200 random sets of 16 people's drawings, and this
asks the same question with no subsets at all.

    PLATO_DIR=.../PlatosChair/bigger python scripts/plato_generate.py --style doodle --keys chair --per-concept 200
    PLATO_DIR=.../PlatosChair/bigger python -I scripts/plato_embed.py --keys chair --sources ai_doodle
    python scripts/plato_bigger.py

Same prompt, same ink crop, same DINOv2 (CLS) and the same spread (mean pairwise cosine distance) as docs/plato.md.
People: the same 200 recognized Quick, Draw! chairs. Writes public_data/plato_bigger_chair.json (statistics only),
and, outside the repo, a contact sheet and the pixel average of the 200 chairs in PlatosChair/bigger/.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab.plato import bootstrap_spread, ci, cosine_distances, ink_crop, load_dir, spread, subsample_spread  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CORE = Path("/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/core")
BIG = Path("/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/bigger")
KEY = "chair"


def emb(root: Path, source: str) -> np.ndarray:
    return np.load(root / "embeddings" / source / f"{KEY}.npz")["cls"]


def main():
    rng = np.random.default_rng(20261101)
    a, h, a16 = emb(BIG, "ai_doodle"), emb(CORE, "human"), emb(CORE, "ai_doodle")
    da, dh, d16 = cosine_distances(a), cosine_distances(h), cosine_distances(a16)
    ai, hu = spread(da), spread(dh)
    ai_boot, hu_boot = bootstrap_spread(da, 2000, rng), bootstrap_spread(dh, 2000, rng)
    ratio = ai_boot / hu_boot
    subs_ai = subsample_spread(da, 16, 2000, rng)      # 16 of the 200, again and again: is the first 16 typical?
    subs_hu = subsample_spread(dh, 16, 2000, rng)
    out = {
        "what": "Muse Image's chair at full size: 200 doodles from the main prompt against 200 people's Quick, Draw! chairs",
        "added": "2026-11-01, after the main analysis; a robustness check, not pre-registered",
        "n_ai": int(len(a)), "n_people": int(len(h)),
        "ai_spread": ai, "ai_spread_ci95": ci(ai_boot),
        "people_spread": hu, "people_spread_ci95": ci(hu_boot),
        "ratio": ai / hu, "ratio_ci95": ci(ratio), "less_varied_pct": round(100 * (1 - ai / hu)),
        "first_16_spread": spread(d16), "first_16_ratio_vs_16_subsets_of_people": spread(d16) / float(subs_hu.mean()),
        "ai_16_subsets_spread_range95": ci(subs_ai),
        "people_16_subsets_spread_range95": ci(subs_hu),
        "ai_16_subsets_below_every_people_16_subset_share": float((subs_ai < subs_hu.min()).mean()),
        "method": "DINOv2-base CLS on ink-cropped pictures; spread = mean pairwise cosine distance; CIs from 2,000 bootstrap resamples of pictures",
    }
    (REPO / "public_data" / "plato_bigger_chair.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))

    # for looking, outside the repo: all 200 on one sheet, and their pixel average
    files = load_dir(BIG / "ai" / "doodle" / KEY)
    tiles = [ink_crop(Image.open(f).convert("RGB")).convert("L").resize((96, 96)) for f in files]
    cols = 20
    sheet = Image.new("L", (cols * 96, ((len(tiles) + cols - 1) // cols) * 96), 255)
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols) * 96, (k // cols) * 96))
    sheet.save(BIG / "chair_200_sheet.png")
    avg = np.mean([np.asarray(t.resize((256, 256)), dtype=float) for t in tiles], axis=0)
    avg = 255 * (avg - avg.min()) / max(1e-9, avg.max() - avg.min())
    Image.fromarray(avg.astype(np.uint8)).save(BIG / "chair_200_average.png")
    print("wrote", BIG / "chair_200_sheet.png", "and", BIG / "chair_200_average.png")


if __name__ == "__main__":
    main()

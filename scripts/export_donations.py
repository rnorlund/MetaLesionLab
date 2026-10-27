"""Draw a chair: turn donated drawings into a dataset folder for review before any sharing.

Reads the donations folder (TIPPA_DONATIONS_DIR, else <data dir>/donations; see
metalesionlab/web/draw_donations.py) and writes a self-contained folder:

  <out>/README.md            what the dataset is, how it was collected, the consent text, the fields
  <out>/LICENSE              Creative Commons Attribution 4.0 (CC BY 4.0), pending review
  <out>/drawings.jsonl       one line per donation (only the documented fields)
  <out>/png/<id>.png         the 256 px black-on-white pictures
  <out>/summary.json         counts by thing, source and blind/not

It never deletes or edits the donations themselves. Records without their picture, or with fields that
aren't in the schema, are skipped or trimmed and reported. Nothing here is uploaded anywhere: Roger
reviews the folder (and the IRB status) before anything is shared.

    python scripts/export_donations.py --out dist/draw_donations [--donations PATH] [--since 2026-11-01]
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

FIELDS = ["id", "date", "concept", "source", "blind", "draw_seconds", "scores", "strokes", "png", "model", "consent"]
SCORES = ["originality", "d_human", "d_ai", "people_closer_to_muse", "muse_closer", "own_rank", "d_doodle",
          "nearest_ai", "nearest_human"]
LICENSE = """Creative Commons Attribution 4.0 International (CC BY 4.0)

You are free to share and adapt this material for any purpose, even commercially, as long as you give
appropriate credit, provide a link to the license, and indicate if changes were made.

Full legal code: https://creativecommons.org/licenses/by/4.0/legalcode
"""


def readme(n: int, summary: dict, consent: dict) -> str:
    points = "\n".join(f"- **{k}:** {v}" for k, v in consent["points"])
    return f"""# Draw a chair: donated drawings

{n} drawings that visitors of the Draw a chair game chose to donate for research, with the scores the
game showed them. Each visitor ticked "{consent['label']}" and "{consent['adult']}".

**Status: for review.** Check the IRB status ({consent['irb']}) and look through the pictures before
sharing this folder.

## Consent text shown to donors (version {consent['version']})

{points}

## Files

- `drawings.jsonl`: one JSON object per drawing (fields below).
- `png/<id>.png`: the 256 x 256 black-on-white picture the embedding model saw. For photos of drawings on
  paper this is the cleaned-up drawing (paper flattened to white and cropped to the ink); the photo itself
  was never kept.
- `summary.json`: counts.

## Fields

| Field | Meaning |
|---|---|
| `id` | random UUID, not linked to any visitor, session, cookie or address |
| `date` | UTC date of the donation (no time) |
| `concept` | the thing drawn (Quick, Draw! category, e.g. `chair`, `sailboat`) |
| `source` | `pad` (drawn in the browser) or `upload` (photo of a drawing on paper) |
| `blind` | true if drawn before the page showed Muse Image's drawings in that browser tab |
| `draw_seconds` | time from the first stroke to "See where it lands" (pad only) |
| `scores` | `originality` (percentile among 200 people's drawings), `d_human` and `d_ai` (cosine distances to people's and Muse Image's average drawing), `people_closer_to_muse`, `muse_closer`, `own_rank` and `d_doodle` (nearest of 35 things' people centroids), `nearest_ai`, `nearest_human` |
| `strokes` | pad drawings only: the strokes in Quick, Draw! simplified format (0-255, RDP 2.0) |
| `png` | path of the picture |
| `model` | the embedding model (Meta DINOv2-base, CLS token) |
| `consent` | version of the consent text |

## Counts

```
{json.dumps(summary, indent=1)}
```

Reference drawings the scores compare with: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0;
Meta Muse Image. Embeddings: Meta DINOv2 (Apache-2.0).
"""


def main() -> int:
    from metalesionlab.web import draw_donations as donations

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--donations", type=Path, default=None)
    ap.add_argument("--since", default="", help="only donations on or after this date (YYYY-MM-DD)")
    args = ap.parse_args()
    src = args.donations or donations.donations_dir()
    log = src / "donations.jsonl"
    if not log.is_file():
        raise SystemExit(f"No donations at {log}.")
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} isn't empty; choose a new folder.")
    (out / "png").mkdir(parents=True, exist_ok=True)
    kept, skipped = [], Counter()
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            skipped["unreadable line"] += 1
            continue
        if args.since and str(rec.get("date", "")) < args.since:
            continue
        png = src / str(rec.get("png", ""))
        if not rec.get("id") or not png.is_file() or png.resolve().parent != (src / "png").resolve():
            skipped["missing picture"] += 1
            continue
        clean = {k: rec.get(k) for k in FIELDS}
        clean["scores"] = {k: (rec.get("scores") or {}).get(k) for k in SCORES}
        shutil.copyfile(png, out / "png" / f"{rec['id']}.png")
        clean["png"] = f"png/{rec['id']}.png"
        kept.append(clean)
    with open(out / "drawings.jsonl", "w", encoding="utf-8") as f:
        for rec in kept:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {"drawings": len(kept), "by_concept": dict(Counter(r["concept"] for r in kept)),
               "by_source": dict(Counter(r["source"] for r in kept)),
               "blind": dict(Counter(str(r["blind"]).lower() for r in kept)), "skipped": dict(skipped)}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    (out / "LICENSE").write_text(LICENSE)
    (out / "README.md").write_text(readme(len(kept), summary, donations.CONSENT))
    print(f"wrote {len(kept)} drawings to {out}" + (f"; skipped {dict(skipped)}" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""How much of Meta's AI the project used, for the home page's "Built on Meta" band and the README.

Added Nov 2. Counts calls per model in the spend ledger (runs/costs.jsonl: every Meta Model API call made while we
built and tested, not published) and adds the two open-weight Meta models we ran ourselves, which the ledger can't
see: Muse Glimmer's 10,020 kind labels (docs/plato.md) and the drawings DINOv2 compared in the Atlas of Forms
(public_data/plato_atlas.json). Writes public_data/meta_usage.json: counts only, no prompts, answers or pictures.
The live site's own calls (its ledger is on the Space) are not included.

    python scripts/meta_usage.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / "runs" / "costs.jsonl"
OUT = REPO / "public_data" / "meta_usage.json"
GLIMMER_LABELS = 10020  # Muse Glimmer's multiple-choice kind labels, docs/plato.md


def ledger_counts(lines) -> dict:
    """Per model: API calls, and items (pictures for Muse Image; one per call otherwise)."""
    calls, items = Counter(), Counter()
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not r.get("model"):
            continue
        calls[r["model"]] += 1
        items[r["model"]] += int(r.get("n") or 1)
    return {m: {"calls": calls[m], "items": items[m]} for m in sorted(calls)}


def about(n: int) -> str:
    """How the page shows a count: to the nearest hundred from 1,000 up, exact below."""
    return f"{round(n, -2):,}" if n >= 1000 else str(n)


def atlas_drawings() -> int:
    atlas = json.loads((REPO / "public_data" / "plato_atlas.json").read_text())
    people_per_thing = 200  # human_reference: the first 200 recognized Quick, Draw! drawings of each thing
    return sum(c["n_ai"] + (c.get("n_sdxl") or 0) + people_per_thing for c in atlas["concepts"])


def main():
    api = ledger_counts(LEDGER.read_text().splitlines())
    total = sum(v["calls"] for v in api.values())
    out = {
        "about": "How much of Meta's AI the project used: calls per model in our spend ledger while we built and "
                 "tested (Meta Model API), plus the two open-weight Meta models we ran ourselves. Counts only. "
                 "Written by scripts/meta_usage.py.",
        "api_models": api,
        "api_calls": total,
        "open_models": {"muse-glimmer-30b": {"kind_labels": GLIMMER_LABELS, "source": "docs/plato.md"},
                        "dinov2": {"atlas_drawings_compared": atlas_drawings(), "source": "public_data/plato_atlas.json"}},
        "shown": {"api_calls": about(total), "muse_spark_calls": about(api["muse-spark-1.3"]["calls"]),
                  "muse_image_pictures": about(api["muse-image-1.0"]["items"]),
                  "voice_clips": about(api["muse-voice-transcribe-1.0"]["calls"]),
                  "sam_checks": about(api["sam-3.1"]["calls"]), "wonder_drawings": about(api["muse-wonder-1.0"]["calls"]),
                  "glimmer_labels": f"{GLIMMER_LABELS:,}", "dinov2_drawings": f"{atlas_drawings() // 1000 * 1000:,}+"},
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    json.dump(out["shown"], sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()

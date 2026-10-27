"""Write the pre-registered Model Lab conditions of the n = 100 replication (docs/replication_plan.md).

Every dose comes from the earlier demo_en runs (runs/lesion/demo_en); nothing is tuned on the new
pictures. Output: scripts/replication/<file>.json, each a list for `scripts/model_lab.py batch`.

  featured_en.json    the featured localizer lesions with 5 random-unit controls each, for the new
                      localizers (built from core100 held-out drawings) and the original ones
  components_en.json  noise dose series at the three damage sites, 5 noise seeds each, plus the
                      vision tower's zero and mean lesions
  featured_es.json    the Spanish Model Lab test: naming-localizer lesion and 5 random controls

Usage: python scripts/replication_specs.py
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "replication"
SEEDS = [0, 1, 2, 3, 4]
# The featured localizer lesions of the Model Lab (metalesionlab/web/app.py FEATURED), with the
# fraction stored by the demo_en severity runs.
FEATURED = [("naming", "mlp", 0.2973), ("visual", "mlp", 0.2548), ("language", "mlp", 0.3173),
            ("naming", "heads", 0.4042)]
# Localizer names: the new ones (core100 held-out drawings; language is text only) and the originals.
NEW = {"naming": "naming_c100", "visual": "visual_c100", "language": "language_c100"}
OLD = {"naming": "naming_en", "visual": "visual_en", "language": "language_en"}
# Noise dose series (x the unit's sd) at the three damage sites: every dose the demo_en runs used
# between mild and severe. The featured doses are vision tower x4.223, layers 40-47 x2.828 and
# layers 0-7 x3.
SITES = {
    "vision_tower": [2.0, 3.364, 3.831, 4.223, 4.362, 5.657, 8.0],
    "layers:40-47": [1.0, 1.682, 2.181, 2.828, 3.0, 4.756, 6.168, 8.0],
    "layers:0-7": [1.0, 1.297, 1.682, 2.828, 3.0, 8.0],
}


def localizer_block(names: dict[str, str], which: list[tuple[str, str, float]]) -> list[dict]:
    out = []
    for contrast, kind, frac in which:
        rec = {"localizer": names[contrast], "kind": kind, "fraction": frac, "method": "mean"}
        out.append(rec)
        out += [{**rec, "control_seed": s} for s in SEEDS]
    return out


def featured_en() -> list[dict]:
    return localizer_block(NEW, FEATURED) + localizer_block(OLD, FEATURED)


def components_en() -> list[dict]:
    out = [{"site": "vision_tower", "method": "zero"}, {"site": "vision_tower", "method": "mean"}]
    for site, scales in SITES.items():
        for s in scales:
            out += [{"site": site, "method": "noise", "noise_scale": s, "seed": k} for k in SEEDS]
    return out


def featured_es() -> list[dict]:
    naming = [("naming", "mlp", 0.2973)]
    return localizer_block(NEW, naming) + localizer_block(OLD, naming)


def main():
    OUT.mkdir(exist_ok=True)
    for name, specs in (("featured_en", featured_en()), ("components_en", components_en()),
                        ("featured_es", featured_es())):
        (OUT / f"{name}.json").write_text(json.dumps(specs, indent=1) + "\n")
        print(f"{name}: {len(specs)} conditions")


if __name__ == "__main__":
    main()

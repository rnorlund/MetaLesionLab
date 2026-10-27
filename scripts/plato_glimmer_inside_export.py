"""Write public_data/plato_glimmer_inside.json: per-concept statistics from "Plato's Chair inside Glimmer".

Reads the data folder (outside the repository): inside_glimmer/results.json and the per-layer distance
matrices in inside_glimmer/raw/distances.npz. Writes derived statistics only (no pictures, embeddings
or distances): for each of the 35 concepts, how spread out Muse Image's doodles and people's drawings are
at a few stages inside Muse Glimmer 30B, the layer where Muse's doodles collapse, and how well Glimmer
names each source. Ask Socrates' glimmer_inside tool reads it (metalesionlab/socrates_agent.py).

Collapse layer: the first decoder layer from which Muse Image's doodles of a thing stay less than half as
spread out as people's drawings of it, through the last layer (52). Spread is the mean pairwise cosine
distance at the answer position, on states centered over all 920 pictures, as in docs/plato_glimmer.md.

    python scripts/plato_glimmer_inside_export.py [--dir PlatosChair/inside_glimmer]
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = Path("/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/inside_glimmer")
OUT = ROOT / "public_data" / "plato_glimmer_inside.json"
WEB = ROOT / "metalesionlab" / "web" / "data" / "plato.json"
LAYERS = [f"L{i}" for i in range(1, 53)]
STAGES = ["projector", "L13", "L26", "L39", "L46", "L52"]
RATIO = 0.5


def spread(z, key: str, i: int, n: int) -> float:
    d = z[key][i][:n, :n]
    iu = np.triu_indices(n, 1)
    return float(d[iu].mean())


def collapse_layer(muse: list[float], people: list[float]) -> int | None:
    ratios = [a / b for a, b in zip(muse, people)]
    for k in range(len(ratios)):
        if all(r < RATIO for r in ratios[k:]):
            return k + 1
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = ap.parse_args()
    res = json.loads((args.dir / "results.json").read_text())
    z = np.load(args.dir / "raw" / "distances.npz", allow_pickle=False)
    groups, sizes = [str(g) for g in z["groups"]], [int(s) for s in z["sizes"]]
    web = json.loads(WEB.read_text())
    labels = {c["key"]: c["label"] for c in web["core"]["concepts"]}

    concepts, curves = [], {"muse": [], "people": []}
    for key, pc in sorted(res["per_concept"].items()):
        ia, ih = groups.index(f"{key}|ai"), groups.index(f"{key}|human")
        muse = [spread(z, f"{L}|centered", ia, sizes[ia]) for L in LAYERS]
        people = [spread(z, f"{L}|centered", ih, sizes[ih]) for L in LAYERS]
        curves["muse"].append(muse)
        curves["people"].append(people)
        sp, nm = pc["spread"], pc["naming"]
        # A sanity check against the analysis: the recomputed spread matches results.json.
        assert abs(sp["L39"]["ai"] - muse[38]) < 2e-3 and abs(sp["L39"]["human"] - people[38]) < 2e-3, key
        merged: dict[str, int] = {}  # "chair" and "Chair" are one answer
        for a, n in nm["human"]["answers"].items():
            merged[a.strip().rstrip(".").lower()] = merged.get(a.strip().rstrip(".").lower(), 0) + n
        answers = sorted(merged.items(), key=lambda kv: -kv[1])[:4]
        concepts.append({
            "key": key,
            "label": labels.get(key, pc["label"]),
            "pictures": {"muse": sizes[ia], "people": sizes[ih]},
            "collapse_layer": collapse_layer(muse, people),
            "spread": {s: {"muse": round(sp[s]["ai"], 3), "people": round(sp[s]["human"], 3)} for s in STAGES},
            "named_correctly_pct": {"muse": round(100 * nm["ai"]["accuracy"], 1),
                                    "people": round(100 * nm["human"]["accuracy"], 1)},
            "name_appears_layer": {"muse": nm["ai"]["first_layer_median"], "people": nm["human"]["first_layer_median"]},
            "glimmer_answers_to_peoples_drawings": [{"answer": a[:40], "n": n} for a, n in answers],
        })
    layers = [c["collapse_layer"] for c in concepts if c["collapse_layer"]]
    inside = web.get("inside") or {}
    out = {
        "about": "Plato's Chair inside Muse Glimmer 30B: how spread out each concept's drawings are at several stages "
                 "inside the model, for Muse Image's doodles and for people's drawings (Google Quick, Draw!), where "
                 "Muse's doodles collapse, and how well Glimmer names them. Derived statistics only. Exploratory: "
                 "35 concepts, 12-16 pictures per source, one model. See docs/plato_glimmer.md.",
        "attribution": "Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0, "
                       "https://github.com/googlecreativelab/quickdraw-dataset",
        "models": {"namer": "Muse Glimmer 30B (Meta, open weights, self-hosted)", "doodles": "Muse Image 1.0 (Meta)"},
        "definitions": {
            "spread": "mean pairwise cosine distance between a concept's pictures at the answer position, on states "
                      "centered over all 920 pictures (higher = more varied)",
            "collapse_layer": f"the first decoder layer (of 52) from which Muse Image's doodles stay less than "
                              f"{RATIO:g} times as spread out as people's drawings of the same thing, through layer 52; "
                              "null if that never happens",
            "name_appears_layer": "median first layer where the word lens reads the accepted name (logit lens)",
            "stages": "projector = the picture after the vision adapter; L13...L52 = decoder layers",
        },
        "summary": {
            "n_concepts": len(concepts),
            "median_collapse_layer": statistics.median(layers),
            "earliest_collapse": min(layers), "latest_collapse": max(layers),
            "never_collapse": [c["label"] for c in concepts if c["collapse_layer"] is None],
            "named_correctly_pct": {"muse": round(100 * res["intact"]["accuracy"]["ai"], 1),
                                    "people": round(100 * res["intact"]["accuracy"]["human"], 1)},
            "mean_spread_by_layer": {
                "layers": list(range(1, 53)),
                "muse": [round(float(x), 3) for x in np.mean(curves["muse"], axis=0)],
                "people": [round(float(x), 3) for x in np.mean(curves["people"], axis=0)],
            },
            "people_spread_vs_naming_rho": (inside.get("naming") or {}).get("rho"),
            "people_spread_vs_naming_ci95": (inside.get("naming") or {}).get("ci95"),
        },
        "concepts": concepts,
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.1f} KB); median collapse layer {out['summary']['median_collapse_layer']}")


if __name__ == "__main__":
    main()

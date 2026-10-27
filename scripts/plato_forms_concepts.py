"""Plato's Forms: the bed and the table (Republic X) through the core Plato's Chair pipeline.

  human      the first 200 recognized Quick, Draw! drawings of each, rendered like the core's
             ($PLATO_FORMS_DIR/human/<key>/NNN.png, strokes.ndjson)
  embed      DINOv2 (CLS and patch mean) of every set, ink-cropped exactly as in plato_embed.py
             ($PLATO_FORMS_DIR/embeddings/<source>/<key>.npz)
  analyze    spread, homogenization index and CIs as in plato_analyze.py; ranks among the 35 core
             concepts (read from the core results.json and results_sdxl.json, never recomputed);
             between-concept baselines and recognisability against the core's cached embeddings
             -> $PLATO_FORMS_DIR/results_concepts.json

Pictures come from plato_forms_generate.py concepts (Muse) and plato_forms_sdxl.py concepts (SDXL).
The core data folder ($PLATO_DIR) is only read. Runs on the Mac (DINOv2 on MPS or CPU).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from plato_analyze import B_AI, B_HUMAN, SUBSETS, call_effect, concept_stats  # noqa: E402
from plato_analyze import load as core_load  # noqa: E402
from plato_embed import PREP, prepare  # noqa: E402

from metalesionlab.plato import (DINO_MODEL, PLATO_DIR, QUICKDRAW_CREDIT, QUICKDRAW_URL, Embedder,  # noqa: E402
                                 bootstrap_spread, ci, cosine_distances, load_dir, render_strokes, spread,
                                 stream_quickdraw, subsample_spread, to_jsonable)
from metalesionlab.plato_forms import FORMS_BY_KEY, FORMS_CONCEPTS, FORMS_DIR, REPUBLIC_X, rank_among  # noqa: E402

SOURCES = {"ai_doodle": "ai/doodle", "ai_doodle_any": "ai/doodle_any", "ai_doodle_listed": "ai/doodle_listed",
           "ai_sdxl_doodle": "ai/sdxl_doodle", "ai_sdxl_any": "ai/sdxl_any", "ai_sdxl_listed": "ai/sdxl_listed",
           "human": "human"}
# condition -> (source, generator's usual-prompt condition)
CONDITIONS = {"default": ("ai_doodle", "default"), "any": ("ai_doodle_any", "default"),
              "listed": ("ai_doodle_listed", "default"), "sdxl_default": ("ai_sdxl_doodle", "sdxl_default"),
              "sdxl_any": ("ai_sdxl_any", "sdxl_default"), "sdxl_listed": ("ai_sdxl_listed", "sdxl_default")}


def cmd_human(args):
    for key in args.keys:
        c = FORMS_BY_KEY[key]
        folder = FORMS_DIR / "human" / key
        if len(list(folder.glob("*.png"))) >= args.keep:
            print(f"{key}: already have {args.keep}")
            continue
        kept = stream_quickdraw(c.quickdraw, keep=args.keep, max_lines=args.max_lines)
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "strokes.ndjson").open("w") as f:
            for i, rec in enumerate(kept):
                render_strokes(rec["drawing"]).save(folder / f"{i:03d}.png")
                f.write(json.dumps(rec) + "\n")
        (folder / "meta.json").write_text(json.dumps({
            "concept": c.label, "quickdraw": c.quickdraw, "n": len(kept),
            "source": QUICKDRAW_URL.format(category=c.quickdraw), "license": "CC BY 4.0",
            "filter": "first drawings in file order with recognized=true",
            "countries": sorted({r["countrycode"] for r in kept if r.get("countrycode")})}, indent=1))
        print(f"{key}: kept {len(kept)}")


def cmd_embed(args):
    embed = None
    for source, rel in SOURCES.items():
        for key in args.keys:
            files = load_dir(FORMS_DIR / rel / key)
            if not files:
                continue
            out = FORMS_DIR / "embeddings" / source / f"{key}.npz"
            names = [f.name for f in files]
            if out.exists():
                old = np.load(out)
                if list(old["files"]) == names and str(old["prep"]) == PREP:
                    continue
            embed = embed or Embedder(DINO_MODEL, args.device)
            vecs = embed([prepare(f, source) for f in files])
            out.parent.mkdir(parents=True, exist_ok=True)
            np.savez(out, files=np.array(names), model=DINO_MODEL, prep=PREP, **vecs)
            print(f"{source:16s} {key:6s} {len(files):4d} pictures", flush=True)


def load(source: str, key: str, n: int | None = None, emb: str = "cls"):
    path = FORMS_DIR / "embeddings" / source / f"{key}.npz"
    if not path.exists():
        return None, None
    z = np.load(path)
    return (z[emb][:n], list(z["files"])[:n]) if n else (z[emb], list(z["files"]))


def unit_mean(x: np.ndarray) -> np.ndarray:
    return (x / np.linalg.norm(x, axis=1, keepdims=True)).mean(0)


def between(x: np.ndarray, centroids: dict[str, np.ndarray]) -> float:
    """Mean distance between a set and each core concept's set (1 - mu . mu_k), as in plato_analyze."""
    mu = unit_mean(x)
    return float(np.mean([1 - mu @ m for m in centroids.values()]))


def nearest_own(x: np.ndarray, centroids: dict[str, np.ndarray], key: str) -> float:
    keys = list(centroids)
    cs = np.stack([centroids[k] for k in keys])
    xn = x / np.linalg.norm(x, axis=1, keepdims=True)
    return float(np.mean(np.array(keys)[np.argmax(xn @ cs.T, axis=1)] == key))


def ranks(value: float, core_values: list[float]) -> dict:
    """Where a value would sit among the 35 core concepts if added alone (1 = smallest of 36)."""
    return {"rank": rank_among(value, core_values), "of": len(core_values) + 1,
            "core_min": float(min(core_values)), "core_median": float(np.median(core_values)),
            "core_max": float(max(core_values))}


def cmd_analyze(args):
    rng = np.random.default_rng(20261027)
    core = json.loads((PLATO_DIR / "results.json").read_text())
    core_sdxl = json.loads((PLATO_DIR / "results_sdxl.json").read_text())
    core_var = json.loads((PLATO_DIR / "results_variety.json").read_text())
    cc = core["concepts"]
    sc = core_sdxl["concepts"]
    core_n = {c["key"]: c["n_ai"] for c in cc}
    # the core's cached embeddings, read only: centroids of each concept per source
    cent = {"ai": {}, "human": {}, "sdxl": {}}
    for k, n in core_n.items():
        cent["ai"][k] = unit_mean(core_load("ai_doodle", k, n)[0])
        cent["human"][k] = unit_mean(core_load("human", k)[0])
        cent["sdxl"][k] = unit_mean(core_load("ai_sdxl_doodle", k)[0])
    hum37 = dict(cent["human"])
    sets = {}
    for c in FORMS_CONCEPTS:
        h, _ = load("human", c.key)
        if h is not None:
            hum37[c.key] = unit_mean(h)
    rows = []
    for c in FORMS_CONCEPTS:
        h, _ = load("human", c.key)
        a, files = load("ai_doodle", c.key, c.n_ai)
        if h is None or a is None or len(a) < c.n_ai:
            print(f"skip {c.key}: missing pictures")
            continue
        st = concept_stats(a, h, c.n_ai, rng)
        a2, _ = load("ai_doodle", c.key, c.n_ai, "patch_mean")
        h2, _ = load("human", c.key, None, "patch_mean")
        ai2 = spread(cosine_distances(a2))
        hu2 = float(subsample_spread(cosine_distances(h2), c.n_ai, SUBSETS, rng).mean())
        same, diff = call_effect(a, files)
        row = {"key": c.key, "label": c.label, "quickdraw": c.quickdraw, "kind": c.kind, "note": c.note,
               "n_ai": len(a), "n_human_pool": len(h),
               **{k: v for k, v in st.items() if not k.startswith("_")},
               "patch_mean": {"ai_spread": ai2, "human_spread": hu2, "homogenization_index": ai2 / hu2},
               "ai_same_call_distance": same, "ai_cross_call_distance": diff,
               "ai_between": between(a, cent["ai"]), "human_between": between(h, cent["human"]),
               "ai_nearest_human_centroid_is_own_of_37": nearest_own(a, hum37, c.key),
               "human_nearest_human_centroid_is_own_of_37": nearest_own(h, hum37, c.key)}
        row["ai_relative_spread"] = row["ai_spread"] / row["ai_between"]
        row["human_relative_spread"] = row["human_spread"] / row["human_between"]
        row["relative_homogenization_index"] = row["ai_relative_spread"] / row["human_relative_spread"]
        # which core concepts the AI and human pictures are confused with (nearest centroid, not own)
        keys37 = list(hum37)
        cs = np.stack([hum37[k] for k in keys37])
        for who, x in (("ai", a), ("human", h)):
            near = np.array(keys37)[np.argmax((x / np.linalg.norm(x, axis=1, keepdims=True)) @ cs.T, axis=1)]
            vals, counts = np.unique(near[near != c.key], return_counts=True)
            row[f"{who}_confused_with"] = {str(v): int(n) for v, n in sorted(zip(vals, counts), key=lambda t: -t[1])[:4]}
        boots = {"default": st["_ai_boot"]}
        row["conditions"] = {}
        for cond, (source, base) in CONDITIONS.items():
            if cond == "default":
                x = a
            else:
                x, _ = load(source, c.key)
                if x is None or len(x) < c.n_ai:
                    continue
                x = x[:c.n_ai]
            s2 = concept_stats(x, h, len(x), rng) if cond != "default" else st
            boots[cond] = s2["_ai_boot"]
            r = {"n": len(x), "spread": s2["ai_spread"], "spread_ci95": s2["ai_spread_ci95"],
                 "ratio_vs_people": s2["homogenization_index"], "ratio_vs_people_ci95": s2["homogenization_index_ci95"],
                 "nearest_own_human_centroid_of_37": nearest_own(x, hum37, c.key)}
            if cond != base and base in boots:
                r["ratio_vs_default"] = r["spread"] / row["conditions"][base]["spread"]
                r["ratio_vs_default_ci95"] = ci(boots[cond] / boots[base])
            row["conditions"][cond] = r
            sets[(cond, c.key)] = x
        if "sdxl_default" in boots:
            sd = row["conditions"]["sdxl_default"]
            row["muse_over_sdxl"] = row["ai_spread"] / sd["spread"]
            row["muse_over_sdxl_ci95"] = ci(boots["default"] / boots["sdxl_default"])
            row["sdxl_between"] = between(sets[("sdxl_default", c.key)], cent["sdxl"])
            row["sdxl_relative_spread"] = sd["spread"] / row["sdxl_between"]
        # ranks among the 35 core concepts, each value from the core result files
        row["ranks_among_core"] = {
            "homogenization_index": ranks(row["homogenization_index"], [x["homogenization_index"] for x in cc]),
            "ai_spread": ranks(row["ai_spread"], [x["ai_spread"] for x in cc]),
            "human_spread": ranks(row["human_spread"], [x["human_spread"] for x in cc]),
            "relative_homogenization_index": ranks(row["relative_homogenization_index"],
                                                   [x["relative_homogenization_index"] for x in cc]),
        }
        if "sdxl_default" in row["conditions"]:
            row["ranks_among_core"]["sdxl_spread"] = ranks(row["conditions"]["sdxl_default"]["spread"],
                                                           [x["sdxl_spread"] for x in sc])
            row["ranks_among_core"]["sdxl_index"] = ranks(row["conditions"]["sdxl_default"]["ratio_vs_people"],
                                                          [x["sdxl_index"] for x in sc])
            row["ranks_among_core"]["muse_over_sdxl"] = ranks(row["muse_over_sdxl"], [x["muse_over_sdxl"] for x in sc])
        vc = {x["key"]: x for x in core_var["concepts"]}
        for cond in ("any", "listed"):
            if cond in row["conditions"]:
                core_vals = [vc[k][cond]["ratio_vs_people"] for k in vc if cond in vc[k]]
                row["ranks_among_core"][f"{cond}_ratio_vs_people"] = ranks(row["conditions"][cond]["ratio_vs_people"],
                                                                           core_vals)
        kinds = FORMS_DIR / "ai" / "doodle_listed" / c.key / "kinds.json"
        row["listed_kinds"] = json.loads(kinds.read_text()) if kinds.exists() else None
        rows.append(row)
    sorted_idx = sorted(x["homogenization_index"] for x in cc)
    pred_b2 = {r["key"]: r["homogenization_index"] < sorted_idx[11] for r in rows}
    core_summary = {
        "n_concepts": len(cc), "median_index": float(np.median([x["homogenization_index"] for x in cc])),
        "index_12th_lowest": sorted_idx[11],
        "median_ai_spread": float(np.median([x["ai_spread"] for x in cc])),
        "median_human_spread": float(np.median([x["human_spread"] for x in cc])),
        "chair": {f: next(x for x in cc if x["key"] == "chair")[f] for f in
                  ("ai_spread", "human_spread", "homogenization_index", "homogenization_index_ci95")},
        "chair_index_rank": rank_among(next(x for x in cc if x["key"] == "chair")["homogenization_index"],
                                       [x["homogenization_index"] for x in cc if x["key"] != "chair"]),
        "bench": {f: next(x for x in cc if x["key"] == "bench")[f] for f in
                  ("ai_spread", "human_spread", "homogenization_index")},
    }
    results = {
        "experiment": "Plato's Forms: the bed and the table (Republic X) in the Plato's Chair pipeline",
        "republic_x": REPUBLIC_X, "embedding_model": DINO_MODEL, "prep": PREP,
        "spread": "mean pairwise cosine distance within a set (DINOv2 CLS)",
        "bootstraps": {"ai": B_AI, "human": B_HUMAN, "human_subsets": SUBSETS},
        "human_data": QUICKDRAW_CREDIT, "core_reference": core_summary,
        "prediction_B2_table_in_most_homogenized_third": pred_b2,
        "concepts": rows,
    }
    out = FORMS_DIR / "results_concepts.json"
    out.write_text(json.dumps(to_jsonable(results), indent=1, ensure_ascii=False))
    print(f"wrote {out}")
    for r in rows:
        rk = r["ranks_among_core"]
        print(f"\n{r['label'].upper()}: Muse {r['ai_spread']:.3f} {r['ai_spread_ci95']}  people {r['human_spread']:.3f} "
              f"index {r['homogenization_index']:.2f} {r['homogenization_index_ci95']} "
              f"(rank {rk['homogenization_index']['rank']}/36; core median {core_summary['median_index']:.2f})")
        print(f"  Muse spread rank {rk['ai_spread']['rank']}/36, people {rk['human_spread']['rank']}/36, "
              f"relative index {r['relative_homogenization_index']:.2f} (rank {rk['relative_homogenization_index']['rank']})")
        print(f"  patch-mean index {r['patch_mean']['homogenization_index']:.2f}; same/cross call "
              f"{r['ai_same_call_distance']:.3f}/{r['ai_cross_call_distance']:.3f}; own centroid AI "
              f"{r['ai_nearest_human_centroid_is_own_of_37']:.2f} human {r['human_nearest_human_centroid_is_own_of_37']:.2f}")
        print(f"  confused with: AI {r['ai_confused_with']} human {r['human_confused_with']}")
        for cond, x in r["conditions"].items():
            print(f"  {cond:13s} spread {x['spread']:.3f} {x['spread_ci95']} vs people {x['ratio_vs_people']:.2f} "
                  f"{x['ratio_vs_people_ci95']} vs default {x.get('ratio_vs_default', float('nan')):.2f} "
                  f"{x.get('ratio_vs_default_ci95')} own {x['nearest_own_human_centroid_of_37']:.2f}")
        print("  ranks:", {k: v["rank"] for k, v in rk.items()})
        if "muse_over_sdxl" in r:
            print(f"  Muse/SDXL {r['muse_over_sdxl']:.2f} {r['muse_over_sdxl_ci95']}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("human")
    p.add_argument("--keep", type=int, default=200)
    p.add_argument("--max-lines", type=int, default=5000)
    p.set_defaults(fn=cmd_human)
    p = sub.add_parser("embed")
    p.add_argument("--device")
    p.set_defaults(fn=cmd_embed)
    p = sub.add_parser("analyze")
    p.set_defaults(fn=cmd_analyze)
    for p in sub.choices.values():
        p.add_argument("--keys", nargs="*", default=list(FORMS_BY_KEY))
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

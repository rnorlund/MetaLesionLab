"""Plato's Chair, step 4: concept spread for AI vs human drawings, and the link to naming.

Usage: python -I scripts/plato_analyze.py [--naming-runs DIR] [--public public_data/plato_concept_spread.json]

Spread = mean pairwise cosine distance between DINOv2 embeddings of one concept's pictures.
- AI: the concept's n pictures (16 for tier 1, 12 for tier 2), with a bootstrap 95% CI over pictures.
- Human: 200 Quick, Draw! drawings, subsampled 200 times to the same n; the mean of those subsample
  spreads is the human spread, their 2.5-97.5% range is "what n random people give", and a bootstrap
  over the 200 drawings gives the CI of the human spread itself.
- Homogenization index = AI spread / human spread (CI from independent bootstraps of both).
- Between-concept baseline: mean distance from a concept's pictures to every other concept's pictures,
  in the same source. Relative spread = spread / that baseline.
Naming results (exploratory, n tiny): Muse Spark and Glimmer name agreement on the demo set and
per-item accuracy across Glimmer lesion conditions, read from --naming-runs (the main checkout's runs/).
Writes $PLATO_DIR/results.json and a small derived-statistics file for public_data/.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab.plato import (CONCEPTS, DEMO_MISSING, DINO_MODEL, PLATO_DIR, QUICKDRAW_CREDIT,  # noqa: E402
                                 bootstrap_spread, ci, cosine_distances, spearman_ci, spread, subsample_spread,
                                 to_jsonable)

REPO = Path(__file__).resolve().parents[1]
MAIN_RUNS = Path("/Users/super/Documents/Meta_Hacking_Challenge/MetaLesionLab/runs")
B_AI, B_HUMAN, SUBSETS = 2000, 500, 200


def load(source: str, key: str, n: int | None = None, emb: str = "cls"):
    path = PLATO_DIR / "embeddings" / source / f"{key}.npz"
    if not path.exists():
        return None, None
    z = np.load(path)
    vecs, files = z[emb], list(z["files"])
    return (vecs[:n], files[:n]) if n else (vecs, files)


def concept_stats(a: np.ndarray, h: np.ndarray, n: int, rng) -> dict:
    da, dh = cosine_distances(a), cosine_distances(h)
    ai = spread(da)
    ai_boot = bootstrap_spread(da, B_AI, rng)
    subs = subsample_spread(dh, n, SUBSETS, rng)
    hum = float(subs.mean())
    h_boot = bootstrap_spread(dh, B_HUMAN, rng)
    ratio = ai_boot[:B_HUMAN] / h_boot
    return {
        "ai_spread": ai, "ai_spread_ci95": ci(ai_boot),
        "human_spread": hum, "human_spread_ci95": ci(h_boot),
        "human_spread_range95_for_n": ci(subs),
        "homogenization_index": ai / hum, "homogenization_index_ci95": ci(ratio),
        "share_of_human_sets_as_uniform_as_ai": float((subs <= ai).mean()),
        "_ai_boot": ai_boot, "_subs": subs,
    }


def call_effect(a: np.ndarray, files: list[str]) -> tuple[float, float]:
    """Mean distance between pictures from the same API call vs from different calls."""
    d = cosine_distances(a)
    calls = np.array([f.split("_")[0] for f in files])
    same = calls[:, None] == calls[None, :]
    iu = np.triu_indices(len(files), 1)
    return float(d[iu][same[iu]].mean()), float(d[iu][~same[iu]].mean())


def naming_metrics(runs: Path) -> dict:
    """Per English demo word: Spark/Glimmer agreement and accuracy across Glimmer lesion conditions."""
    out = defaultdict(dict)
    manifest = runs / "sets" / "demo_en" / "manifest.json"
    if manifest.exists():
        for it in json.loads(manifest.read_text())["items"]:
            cands = it.get("candidates", [])
            out[it["word"]]["spark_name_agreement"] = (sum(c.get("spark_ok", False) for c in cands) / len(cands)
                                                       if cands else None)
    glimmer = runs / "sets" / "demo_en" / "glimmer_names.json"
    if glimmer.exists():
        for word, r in json.loads(glimmer.read_text()).items():
            out[word]["glimmer_intact_correct"] = float(r.get("code") == "Correct")
    for lang in ["en", "es"]:
        lesion = runs / "lesion" / f"demo_{lang}"
        if not (lesion / "index.json").exists():
            continue
        gloss = {}
        man = runs / "sets" / f"demo_{lang}" / "manifest.json"
        if man.exists():
            gloss = {it["word"]: it.get("gloss", it["word"]) for it in json.loads(man.read_text())["items"]}
        per = defaultdict(lambda: defaultdict(list))
        n_cond = 0
        for cond in json.loads((lesion / "index.json").read_text())["conditions"]:
            if cond["condition"] == "intact" or not (lesion / cond["file"]).exists():
                continue
            # conditions where every item fails (or every item passes) shift all items equally,
            # so they don't change the ranking of items; they are kept in the means
            family = (cond.get("recipe") or {}).get("localizer") or "layers/vision"
            items = json.loads((lesion / cond["file"]).read_text()).get("items", [])
            n_cond += 1
            for it in items:
                word = gloss.get(it["word"], it["word"]) if lang == "es" else it["word"]
                ok = float(it.get("code") == "Correct")
                per[word]["all"].append(ok)
                per[word][family.replace("_en", "")].append(ok)
        for word, fam in per.items():
            for name, vals in fam.items():
                out[word][f"lesion_{lang}_accuracy_{name}"] = float(np.mean(vals))
            out[word][f"lesion_{lang}_conditions"] = len(fam["all"])
        out["_meta"][f"lesion_{lang}_conditions"] = n_cond
    return dict(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--naming-runs", type=Path, default=MAIN_RUNS)
    ap.add_argument("--public", type=Path, default=REPO / "public_data" / "plato_concept_spread.json")
    args = ap.parse_args()
    rng = np.random.default_rng(20261026)

    rows, ai_all, hu_all, keys = [], {}, {}, []
    for c in CONCEPTS:
        a, files = load("ai_doodle", c.key, c.n_ai)
        h, _ = load("human", c.key)
        if a is None or h is None or len(a) < c.n_ai:
            print(f"skip {c.key}: AI {0 if a is None else len(a)}/{c.n_ai}, human {0 if h is None else len(h)}")
            continue
        keys.append(c.key)
        ai_all[c.key], hu_all[c.key] = a, h
        s = concept_stats(a, h, c.n_ai, rng)
        a2, _ = load("ai_doodle", c.key, c.n_ai, "patch_mean")
        h2, _ = load("human", c.key, None, "patch_mean")
        ai2, hu2 = spread(cosine_distances(a2)), float(subsample_spread(cosine_distances(h2), c.n_ai, SUBSETS, rng).mean())
        same, diff = call_effect(a, files)
        rows.append({"key": c.key, "label": c.label, "quickdraw": c.quickdraw, "tier": c.tier, "kind": c.kind,
                     "prompt_phrase": c.phrase, "note": c.note, "n_ai": len(a), "n_human_pool": len(h), **s,
                     "patch_mean": {"ai_spread": ai2, "human_spread": hu2, "homogenization_index": ai2 / hu2},
                     "ai_same_call_distance": same, "ai_cross_call_distance": diff})
    if not rows:
        sys.exit("no complete concepts yet")

    # between-concept baselines: mean cosine distance between sets = 1 - mu_c . mu_d (mu = mean unit vector)
    for source, sets in (("ai", ai_all), ("human", hu_all)):
        mus = {k: (v / np.linalg.norm(v, axis=1, keepdims=True)).mean(0) for k, v in sets.items()}
        for r in rows:
            others = [1 - mus[r["key"]] @ mus[k] for k in keys if k != r["key"]]
            r[f"{source}_between"] = float(np.mean(others))
            r[f"{source}_relative_spread"] = r[f"{source}_spread"] / r[f"{source}_between"]
    for r in rows:
        r["relative_homogenization_index"] = r["ai_relative_spread"] / r["human_relative_spread"]

    # sanity check: does each AI doodle sit nearest its own concept among the human drawings' centroids?
    hmus = np.stack([(hu_all[k] / np.linalg.norm(hu_all[k], axis=1, keepdims=True)).mean(0) for k in keys])
    for r in rows:
        a = ai_all[r["key"]]
        nearest = np.argmax((a / np.linalg.norm(a, axis=1, keepdims=True)) @ hmus.T, axis=1)
        r["ai_nearest_human_centroid_is_own"] = float(np.mean(np.array(keys)[nearest] == r["key"]))
    # and the reverse: each human drawing's nearest AI-doodle centroid
    amus = np.stack([(ai_all[k] / np.linalg.norm(ai_all[k], axis=1, keepdims=True)).mean(0) for k in keys])
    for r in rows:
        h = hu_all[r["key"]]
        nearest = np.argmax((h / np.linalg.norm(h, axis=1, keepdims=True)) @ amus.T, axis=1)
        r["human_nearest_ai_centroid_is_own"] = float(np.mean(np.array(keys)[nearest] == r["key"]))

    naming = naming_metrics(args.naming_runs)
    for r in rows:
        demo = next(c.demo_word for c in CONCEPTS if c.key == r["key"])
        r["naming"] = naming.get(demo, {}) if demo else {}

    by = {r["key"]: r for r in rows}
    col = lambda name, rs=rows: np.array([r[name] for r in rs])  # noqa: E731
    summary = {
        "n_concepts": len(rows),
        "rank_correlation_ai_vs_human_spread": spearman_ci(col("ai_spread"), col("human_spread"), rng=rng),
        "rank_correlation_ai_vs_human_relative_spread": spearman_ci(col("ai_relative_spread"),
                                                                    col("human_relative_spread"), rng=rng),
        "rank_correlation_patch_mean_embedding": spearman_ci([r["patch_mean"]["ai_spread"] for r in rows],
                                                             [r["patch_mean"]["human_spread"] for r in rows], rng=rng),
        "rank_agreement_cls_vs_patch_mean_index": spearman_ci(col("homogenization_index"),
                                                              [r["patch_mean"]["homogenization_index"] for r in rows],
                                                              rng=rng),
        "median_homogenization_index": float(np.median(col("homogenization_index"))),
        "median_relative_homogenization_index": float(np.median(col("relative_homogenization_index"))),
        "concepts_with_index_below_1": int((col("homogenization_index") < 1).sum()),
        "concepts_with_index_ci_below_1": int(sum(r["homogenization_index_ci95"][1] < 1 for r in rows)),
        "concepts_ai_below_every_human_subset": int(sum(r["share_of_human_sets_as_uniform_as_ai"] == 0 for r in rows)),
        "baseline_between_concepts": {"ai": float(col("ai_between").mean()), "human": float(col("human_between").mean())},
        "mean_within_spread": {"ai": float(col("ai_spread").mean()), "human": float(col("human_spread").mean())},
        "ai_same_vs_cross_call_distance": {"same_call": float(col("ai_same_call_distance").mean()),
                                           "cross_call": float(col("ai_cross_call_distance").mean())},
        "ai_doodles_nearest_own_human_centroid": float(col("ai_nearest_human_centroid_is_own").mean()),
        "human_drawings_nearest_own_ai_centroid": float(col("human_nearest_ai_centroid_is_own").mean()),
        "most_uniform_ai": [r["label"] for r in sorted(rows, key=lambda r: r["ai_spread"])[:6]],
        "most_varied_ai": [r["label"] for r in sorted(rows, key=lambda r: -r["ai_spread"])[:6]],
        "most_homogenized": [r["label"] for r in sorted(rows, key=lambda r: r["homogenization_index"])[:6]],
        "least_homogenized": [r["label"] for r in sorted(rows, key=lambda r: -r["homogenization_index"])[:6]],
        "by_kind": {k: {"n": int(sum(r["kind"] == k for r in rows)),
                        "mean_index": float(np.mean([r["homogenization_index"] for r in rows if r["kind"] == k])),
                        "mean_ai_spread": float(np.mean([r["ai_spread"] for r in rows if r["kind"] == k])),
                        "mean_human_spread": float(np.mean([r["human_spread"] for r in rows if r["kind"] == k]))}
                    for k in sorted({r["kind"] for r in rows})},
    }
    if "chair" in by and "sailboat" in by:
        ch, bo = by["chair"], by["sailboat"]
        summary["chair_vs_boat"] = {
            "ai": {"chair": ch["ai_spread"], "boat": bo["ai_spread"],
                   "boat_minus_chair_ci95": ci(bo["_ai_boot"] - ch["_ai_boot"])},
            "human": {"chair": ch["human_spread"], "boat": bo["human_spread"],
                      "boat_minus_chair_range95": ci(bo["_subs"] - ch["_subs"])},
            "index": {"chair": ch["homogenization_index"], "boat": bo["homogenization_index"]},
        }
    summary["person"] = {k: {f: by[k][f] for f in ("ai_spread", "ai_spread_ci95", "human_spread",
                                                   "human_spread_range95_for_n", "homogenization_index",
                                                   "homogenization_index_ci95")}
                         for k in ("face", "yoga") if k in by}

    # exploratory: does a concept's spread track how robust its name is under lesions? (n tiny)
    linked = [r for r in rows if r["naming"].get("lesion_en_accuracy_all") is not None]
    explore = {"note": "EXPLORATORY. Demo words that exist in Quick, Draw! only; n is tiny; no correction for "
                       "multiple tests. Spark and Glimmer agreement on the intact demo set are at ceiling, so "
                       "they cannot correlate with anything.", "n": len(linked)}
    if len(linked) >= 6:
        for target in ["lesion_en_accuracy_all", "lesion_en_accuracy_language",
                       "lesion_en_accuracy_naming", "lesion_en_accuracy_visual"]:
            ys = [r["naming"].get(target) for r in linked]
            if any(y is None for y in ys) or len(set(ys)) < 3:
                continue
            for pred in ["ai_spread", "human_spread", "homogenization_index", "human_relative_spread"]:
                explore[f"{pred} ~ {target}"] = spearman_ci([r[pred] for r in linked], ys, reps=2000, rng=rng)
    summary["naming_link_exploratory"] = explore

    results = {
        "experiment": "Plato's Chair: concept spread in AI vs human drawings",
        "embedding_model": DINO_MODEL, "embedding": "CLS token, cosine distance; patch-mean as a robustness check",
        "image_model": "muse-image-1.0", "style": "doodle",
        "spread": "mean pairwise cosine distance within a concept",
        "human_data": QUICKDRAW_CREDIT, "demo_words_without_quickdraw_category": DEMO_MISSING,
        "naming_meta": naming.get("_meta", {}),
        "summary": summary,
        "concepts": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
    }
    out = PLATO_DIR / "results.json"
    out.write_text(json.dumps(to_jsonable(results), indent=1, ensure_ascii=False))
    print(f"wrote {out}")

    public = {
        "about": "Plato's Chair: how spread out each concept is in AI drawings (Muse Image) vs human drawings "
                 "(Google Quick, Draw!), measured with Meta DINOv2 embeddings. Derived statistics only; "
                 "no drawings.",
        "attribution": QUICKDRAW_CREDIT,
        "spread": results["spread"], "embedding_model": DINO_MODEL,
        "summary": {k: summary[k] for k in ("n_concepts", "rank_correlation_ai_vs_human_spread",
                                            "median_homogenization_index", "baseline_between_concepts")},
        "concepts": [{k: r[k] for k in ("label", "quickdraw", "kind", "n_ai", "ai_spread", "ai_spread_ci95",
                                        "human_spread", "human_spread_ci95", "homogenization_index",
                                        "homogenization_index_ci95")} for r in rows],
    }
    args.public.write_text(json.dumps(to_jsonable(public), indent=1))
    print(f"wrote {args.public}")

    print(f"\n{'concept':10s} {'kind':22s} {'AI':>16s} {'human':>16s} {'index':>16s} {'rel':>5s}")
    for r in sorted(rows, key=lambda r: r["homogenization_index"]):
        print(f"{r['label']:10s} {r['kind']:22s} {r['ai_spread']:.3f} [{r['ai_spread_ci95'][0]:.3f},"
              f"{r['ai_spread_ci95'][1]:.3f}] {r['human_spread']:.3f} [{r['human_spread_range95_for_n'][0]:.3f},"
              f"{r['human_spread_range95_for_n'][1]:.3f}] {r['homogenization_index']:.2f} "
              f"[{r['homogenization_index_ci95'][0]:.2f},{r['homogenization_index_ci95'][1]:.2f}] "
              f"{r['relative_homogenization_index']:.2f}")
    print(json.dumps(to_jsonable({k: v for k, v in summary.items()}), indent=1))


if __name__ == "__main__":
    main()

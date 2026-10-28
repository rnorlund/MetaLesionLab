"""Plato's Chair, does it depend on DINOv2? The core, SDXL and variety headlines, per vision model.

Usage: python -I scripts/plato_robust_analyze.py [--public public_data/plato_robustness.json]
       (after scripts/plato_robust_embed.py; the plan is docs/plato_robustness_plan.md)

For every embedder in metalesionlab.plato_robust (DINOv2-base from the cached core embeddings, the others
from $PLATO_DIR/embeddings_robust/), per concept and exactly as plato_analyze.concept_stats:
- spread of each AI set (bootstrap CI over pictures) and people's spread at the same n (mean of 200 random
  sets), and their ratio with a CI from independent bootstraps;
- Muse/SDXL, "any kind"/usual, named kinds/usual and SDXL "any kind"/usual spread ratios (independent
  bootstraps of the two sets).
Across concepts: medians with a two-level bootstrap CI (plato_robust.hierarchical_median_ci), counts,
rank agreement of per-concept ratios with DINOv2-base, relative spread, recognisability, and the
pre-registered verdicts (plato_robust.verdict).
Writes $PLATO_DIR/results_robustness.json and derived statistics for public_data/plato_robustness.json.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from plato_analyze import B_AI, B_HUMAN, SUBSETS  # noqa: E402

from metalesionlab.plato import (BY_KEY, CONCEPTS, PLATO_DIR, QUICKDRAW_CREDIT, bootstrap_spread, ci,  # noqa: E402
                                 cosine_distances, spearman, spearman_ci, spread, subsample_spread, to_jsonable)
from metalesionlab.plato_robust import (ALTERNATIVES, ANY_BAND, EMBEDDERS, MIN_CONCEPTS_BELOW, MIN_RHO,  # noqa: E402
                                        REFERENCE, SKIPPED, hierarchical_median_ci, nearest_centroid_share,
                                        verdict)
from metalesionlab.plato_web import clean  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
# condition -> embedding source; Muse uses its first n_ai pictures, SDXL's usual prompt all 16
CONDITIONS = {"muse": "ai_doodle", "any": "ai_doodle_any", "unusual": "ai_doodle_unusual",
              "listed": "ai_doodle_listed", "sdxl": "ai_sdxl_doodle", "sdxl_any": "ai_sdxl_any",
              "sdxl_listed": "ai_sdxl_listed"}
# ratio name -> (numerator condition, denominator condition)
PAIRS = {"muse_over_sdxl": ("muse", "sdxl"), "any_vs_default": ("any", "muse"),
         "listed_vs_default": ("listed", "muse"), "unusual_vs_default": ("unusual", "muse"),
         "sdxl_any_vs_default": ("sdxl_any", "sdxl"), "sdxl_listed_vs_default": ("sdxl_listed", "sdxl")}
# ratio to people per condition, under the names used in the summary
VS_PEOPLE = {"muse": "index", "sdxl": "sdxl_index", "any": "any_vs_people", "listed": "listed_vs_people",
             "unusual": "unusual_vs_people", "sdxl_any": "sdxl_any_vs_people", "sdxl_listed": "sdxl_listed_vs_people"}
FOCUS = ["chair", "sailboat", "umbrella", "bicycle", "book", "face", "yoga"]


def load(tag: str, source: str, key: str, n: int | None = None, field: str | None = None) -> np.ndarray | None:
    """One concept's vectors: the cached core embeddings for the reference, embeddings_robust/ otherwise."""
    if tag == REFERENCE:
        path, field = PLATO_DIR / "embeddings" / source / f"{key}.npz", field or "cls"
    else:
        path, field = PLATO_DIR / "embeddings_robust" / tag / source / f"{key}.npz", field or "emb"
    if not path.exists():
        return None
    z = np.load(path)
    if field not in z:
        return None
    return z[field][:n] if n else z[field]


def concept_row(tag: str, c, rng) -> dict | None:
    """Every spread and ratio for one concept in one embedding space, with the bootstrap draws kept in
    '_draws' for the medians over concepts."""
    h = load(tag, "human", c.key)
    if h is None:
        return None
    dh = cosine_distances(h)
    h_boot = bootstrap_spread(dh, B_HUMAN, rng)
    human, subs = {}, {}
    row = {"key": c.key, "label": c.label, "tier": c.tier, "kind": c.kind, "_draws": {}, "_sets": {}}
    boots = {}
    for cond, source in CONDITIONS.items():
        n_want = 16 if cond == "sdxl" else c.n_ai
        a = load(tag, source, c.key, c.n_ai if cond == "muse" else None)
        if a is None or len(a) < n_want:
            continue
        n = len(a)
        if n not in subs:
            subs[n] = subsample_spread(dh, n, SUBSETS, rng)
            human[n] = float(subs[n].mean())
        da = cosine_distances(a)
        ai = spread(da)
        boot = bootstrap_spread(da, B_AI, rng)
        boots[cond] = boot
        draws = boot[:B_HUMAN] / h_boot
        name = VS_PEOPLE[cond]
        row[cond] = {"n": n, "spread": ai, "spread_ci95": ci(boot), "human_spread": human[n],
                     "ratio_vs_people": ai / human[n], "ratio_vs_people_ci95": ci(draws),
                     "share_of_human_sets_as_uniform": float((subs[n] <= ai).mean())}
        row["_draws"][name] = draws
        row["_sets"][cond] = a
    if "muse" not in row:
        return None
    row["human_spread"] = row["muse"]["human_spread"]
    row["human_spread_ci95"] = ci(h_boot)
    for name, (num, den) in PAIRS.items():
        if num in boots and den in boots:
            r = row[num]["spread"] / row[den]["spread"]
            draws = boots[num] / boots[den]
            row[name] = {"ratio": r, "ci95": ci(draws)}
            row["_draws"][name] = draws
    # DINOv2's patch-mean vector, a secondary check (reference and DINOv2-large only)
    if EMBEDDERS[tag].loader == "dinov2":
        a2 = load(tag, "ai_doodle", c.key, c.n_ai, "patch_mean")
        h2 = load(tag, "human", c.key, None, "patch_mean")
        if a2 is not None and h2 is not None:
            hu2 = float(subsample_spread(cosine_distances(h2), c.n_ai, SUBSETS, rng).mean())
            row["patch_mean_index"] = spread(cosine_distances(a2)) / hu2
    row["_human"] = h
    return row


def median_block(rows: list[dict], name: str, rng, value=None) -> dict | None:
    """Median over concepts of one per-concept ratio, its two-level CI, and counts below/above 1."""
    rs = [r for r in rows if name in r["_draws"]]
    if not rs:
        return None
    value = value or (lambda r: r[name]["ratio"])
    vals = np.array([value(r) for r in rs])
    n_draws = min(len(r["_draws"][name]) for r in rs)
    draws = np.stack([r["_draws"][name][:n_draws] for r in rs])
    per_ci = np.array([ci(r["_draws"][name]) for r in rs])
    return {"n_concepts": len(rs), "median": float(np.median(vals)),
            "median_ci95": hierarchical_median_ci(draws, rng=rng),
            "below_1": int((vals < 1).sum()), "ci_below_1": int((per_ci[:, 1] < 1).sum()),
            "ci_above_1": int((per_ci[:, 0] > 1).sum())}


def summarize(tag: str, rows: list[dict], ref_rows: list[dict] | None, rng) -> dict:
    by = {r["key"]: r for r in rows}
    keys = [r["key"] for r in rows]
    people = lambda cond: (lambda r: r[cond]["ratio_vs_people"])  # noqa: E731
    med = {VS_PEOPLE[cond]: median_block([r for r in rows if cond in r], VS_PEOPLE[cond], rng, people(cond))
           for cond in CONDITIONS}
    med.update({name: median_block(rows, name, rng) for name in PAIRS})
    idx = np.array([r["muse"]["ratio_vs_people"] for r in rows])
    s = {
        "n_concepts": len(rows),
        "index_median": med["index"]["median"], "index_median_ci95": med["index"]["median_ci95"],
        "concepts_below_1": med["index"]["below_1"], "concepts_ci_below_1": med["index"]["ci_below_1"],
        "concepts_below_every_human_subset": int(sum(r["muse"]["share_of_human_sets_as_uniform"] == 0 for r in rows)),
        "chair_index": by["chair"]["muse"]["ratio_vs_people"], "chair_index_ci95": by["chair"]["muse"]["ratio_vs_people_ci95"],
        "muse_over_sdxl_median": med["muse_over_sdxl"]["median"],
        "muse_over_sdxl_median_ci95": med["muse_over_sdxl"]["median_ci95"],
        "concepts_muse_below_sdxl": med["muse_over_sdxl"]["below_1"],
        "concepts_muse_below_sdxl_ci": med["muse_over_sdxl"]["ci_below_1"],
        "sdxl_index_median": med["sdxl_index"]["median"], "sdxl_index_median_ci95": med["sdxl_index"]["median_ci95"],
        "concepts_sdxl_below_1": med["sdxl_index"]["below_1"], "concepts_sdxl_ci_below_1": med["sdxl_index"]["ci_below_1"],
        "concepts_sdxl_ci_above_1": med["sdxl_index"]["ci_above_1"],
        "any_vs_default_median": med["any_vs_default"]["median"],
        "any_vs_default_median_ci95": med["any_vs_default"]["median_ci95"],
        "any_vs_people_median": med["any_vs_people"]["median"],
        "any_vs_people_median_ci95": med["any_vs_people"]["median_ci95"],
        "listed_vs_people_median": med["listed_vs_people"]["median"],
        "listed_vs_people_median_ci95": med["listed_vs_people"]["median_ci95"],
        "concepts_listed_above_people": med["listed_vs_people"]["n_concepts"] - med["listed_vs_people"]["below_1"],
        "listed_vs_default_median": med["listed_vs_default"]["median"],
        "listed_vs_default_median_ci95": med["listed_vs_default"]["median_ci95"],
        "unusual_vs_people_median": med["unusual_vs_people"]["median"],
        "unusual_vs_people_median_ci95": med["unusual_vs_people"]["median_ci95"],
        "sdxl_any_vs_default_median": med["sdxl_any_vs_default"]["median"],
        "sdxl_listed_vs_people_median": med["sdxl_listed_vs_people"]["median"],
        "mean_spread": {"muse": float(np.mean([r["muse"]["spread"] for r in rows])),
                        "sdxl": float(np.mean([r["sdxl"]["spread"] for r in rows if "sdxl" in r])),
                        "human": float(np.mean([r["human_spread"] for r in rows]))},
        "rank_correlation_muse_vs_human_spread": spearman_ci([r["muse"]["spread"] for r in rows],
                                                             [r["human_spread"] for r in rows], rng=rng),
        "medians": med,
    }
    # between-concept baseline and relative spread, as in plato_analyze
    for src, sets in (("muse", {r["key"]: r["_sets"]["muse"] for r in rows}), ("human", {r["key"]: r["_human"] for r in rows})):
        mus = {k: (v / np.linalg.norm(v, axis=1, keepdims=True)).mean(0) for k, v in sets.items()}
        for r in rows:
            r[f"{src}_between"] = float(np.mean([1 - mus[r["key"]] @ mus[k] for k in keys if k != r["key"]]))
    rel = [(r["muse"]["spread"] / r["muse_between"]) / (r["human_spread"] / r["human_between"]) for r in rows]
    for r, x in zip(rows, rel):
        r["relative_index"] = x
    s["baseline_between_concepts"] = {"muse": float(np.mean([r["muse_between"] for r in rows])),
                                      "human": float(np.mean([r["human_between"] for r in rows]))}
    s["relative_index_median"] = float(np.median(rel))
    s["concepts_relative_index_below_1"] = int((np.array(rel) < 1).sum())
    # recognisability: Muse doodles against people's centroids; people's drawings, left out of their own
    hum = {r["key"]: r["_human"] for r in rows}
    s["muse_nearest_own_human_centroid"] = float(np.mean(list(
        nearest_centroid_share({r["key"]: r["_sets"]["muse"] for r in rows}, hum).values())))
    s["sdxl_nearest_own_human_centroid"] = float(np.mean(list(
        nearest_centroid_share({r["key"]: r["_sets"]["sdxl"] for r in rows if "sdxl" in r}, hum).values())))
    loo = nearest_centroid_share(hum, hum, leave_one_out=True)
    s["human_nearest_own_human_centroid_loo"] = float(np.mean(list(loo.values())))
    order = sorted(rows, key=lambda r: r["muse"]["ratio_vs_people"])
    s["most_homogenized"] = [r["label"] for r in order[:6]]
    s["least_homogenized"] = [r["label"] for r in order[::-1][:6]]
    if all("patch_mean_index" in r for r in rows):
        pm = np.array([r["patch_mean_index"] for r in rows])
        s["patch_mean"] = {"index_median": float(np.median(pm)), "concepts_below_1": int((pm < 1).sum()),
                           "rank_agreement_with_main_vector": spearman_ci(idx, pm, rng=rng)}
    if ref_rows is not None:
        ref = {r["key"]: r for r in ref_rows}
        common = [r for r in rows if r["key"] in ref]
        for name, get in (("index", lambda r: r["muse"]["ratio_vs_people"]), ("muse_spread", lambda r: r["muse"]["spread"]),
                          ("human_spread", lambda r: r["human_spread"]), ("sdxl_index", lambda r: r["sdxl"]["ratio_vs_people"]),
                          ("muse_over_sdxl", lambda r: r["muse_over_sdxl"]["ratio"]),
                          ("listed_vs_people", lambda r: r["listed"]["ratio_vs_people"])):
            s[f"rank_agreement_{name}"] = spearman_ci([get(r) for r in common], [get(ref[r["key"]]) for r in common],
                                                      rng=rng)
        s["rho_index_vs_reference"] = s["rank_agreement_index"]["rho"]
    s["verdict"] = verdict(s)
    return s


def public_rows(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        row = {"label": r["label"], "quickdraw": BY_KEY[r["key"]].quickdraw, "tier": r["tier"],
               "muse_spread": r["muse"]["spread"], "human_spread": r["human_spread"]}
        for cond, name in VS_PEOPLE.items():
            if cond in r:
                row[name] = r[cond]["ratio_vs_people"]
                row[f"{name}_ci95"] = r[cond]["ratio_vs_people_ci95"]
        for name in ("muse_over_sdxl", "any_vs_default", "listed_vs_default"):
            if name in r:
                row[name], row[f"{name}_ci95"] = r[name]["ratio"], r[name]["ci95"]
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", type=Path, default=REPO / "public_data" / "plato_robustness.json")
    ap.add_argument("--out", type=Path, default=PLATO_DIR / "results_robustness.json")
    ap.add_argument("--embedders", nargs="*", default=[REFERENCE, *ALTERNATIVES], choices=list(EMBEDDERS))
    args = ap.parse_args()
    rng = np.random.default_rng(20261029)
    all_rows, summaries = {}, {}
    for tag in [t for t in [REFERENCE, *ALTERNATIVES] if t in args.embedders]:
        rows = [r for r in (concept_row(tag, c, rng) for c in CONCEPTS) if r is not None]
        complete = [r for r in rows if all(k in r for k in ("muse", "sdxl", "any", "listed", "sdxl_any", "sdxl_listed"))
                    and (r["tier"] != 1 or "unusual" in r)]
        if len(complete) < len(CONCEPTS):
            print(f"{tag}: only {len(complete)} of {len(CONCEPTS)} concepts fully embedded; skipped")
            continue
        all_rows[tag] = rows
        summaries[tag] = summarize(tag, rows, all_rows.get(REFERENCE) if tag != REFERENCE else None, rng)
        print(f"{tag}: done", flush=True)
    tags = list(summaries)
    # pairwise rank agreement of the per-concept index between all embedders (secondary)
    idx = {t: [r["muse"]["ratio_vs_people"] for r in all_rows[t]] for t in tags}
    matrix = {a: {b: spearman(idx[a], idx[b]) for b in tags} for a in tags}
    specs = {t: {k: getattr(EMBEDDERS[t], k) for k in ("name", "model_id", "maker", "license", "training", "feature")}
             for t in tags}
    rules = {"min_concepts_below": MIN_CONCEPTS_BELOW, "min_rho": MIN_RHO, "any_band": list(ANY_BAND),
             "plan": "docs/plato_robustness_plan.md"}
    strip = lambda r: {k: v for k, v in r.items() if not k.startswith("_")}  # noqa: E731
    results = {"experiment": "Plato's Chair: does the result depend on DINOv2?", "embedders": specs,
               "skipped": SKIPPED, "rules": rules, "summary": summaries, "rank_agreement_index_matrix": matrix,
               "concepts": {t: [strip(r) for r in all_rows[t]] for t in tags}}
    args.out.write_text(json.dumps(to_jsonable(results), indent=1, ensure_ascii=False))
    print(f"wrote {args.out}")
    public = {
        "about": "Plato's Chair, does it depend on DINOv2? The spread of Muse Image and SDXL doodles against "
                 "people's drawings (Google Quick, Draw!), measured in four vision models' embedding spaces: Meta "
                 "DINOv2-base (the reference), DINOv2-large, Meta Perception Encoder PE-Core-L14-336 and Google "
                 "SigLIP 2. Derived statistics only; no drawings or embeddings. See docs/plato_robustness.md.",
        "attribution": QUICKDRAW_CREDIT, "embedders": specs, "skipped": SKIPPED, "rules": rules,
        "spread": "mean pairwise cosine distance within a concept",
        "summary": {t: {k: v for k, v in s.items() if k != "medians"} for t, s in summaries.items()},
        "rank_agreement_index_matrix": matrix,
        "concepts": {t: public_rows(all_rows[t]) for t in tags},
    }
    args.public.write_text(json.dumps(clean(to_jsonable(public)), indent=1) + "\n")
    print(f"wrote {args.public}")
    report(summaries, all_rows)


def report(summaries: dict, all_rows: dict) -> None:
    f = lambda x: f"{x:.2f}"  # noqa: E731
    c = lambda v: f"[{v[0]:.2f}, {v[1]:.2f}]"  # noqa: E731
    for tag, s in summaries.items():
        print(f"\n== {tag} ({EMBEDDERS[tag].name})  core: {s['verdict']['core']}; variety: {s['verdict']['variety']}; "
              f"SDXL not below people: {s['verdict']['sdxl_not_below_people']}")
        print(f"  index median {f(s['index_median'])} {c(s['index_median_ci95'])}; below 1: {s['concepts_below_1']}/35 "
              f"(CI {s['concepts_ci_below_1']}); below every human set {s['concepts_below_every_human_subset']}")
        print(f"  chair {f(s['chair_index'])} {c(s['chair_index_ci95'])}")
        print(f"  Muse/SDXL {f(s['muse_over_sdxl_median'])} {c(s['muse_over_sdxl_median_ci95'])}; Muse below "
              f"{s['concepts_muse_below_sdxl']} (CI {s['concepts_muse_below_sdxl_ci']})")
        print(f"  SDXL/people {f(s['sdxl_index_median'])} {c(s['sdxl_index_median_ci95'])}; below 1 {s['concepts_sdxl_below_1']}"
              f" (CI below {s['concepts_sdxl_ci_below_1']}, above {s['concepts_sdxl_ci_above_1']})")
        print(f"  any/usual {f(s['any_vs_default_median'])} {c(s['any_vs_default_median_ci95'])}; any/people "
              f"{f(s['any_vs_people_median'])} {c(s['any_vs_people_median_ci95'])}")
        print(f"  named/people {f(s['listed_vs_people_median'])} {c(s['listed_vs_people_median_ci95'])} (above "
              f"{s['concepts_listed_above_people']}); named/usual {f(s['listed_vs_default_median'])} "
              f"{c(s['listed_vs_default_median_ci95'])}; unusual/people {f(s['unusual_vs_people_median'])}; "
              f"SDXL any/usual {f(s['sdxl_any_vs_default_median'])}")
        print(f"  mean spread {to_jsonable(s['mean_spread'])}; between {to_jsonable(s['baseline_between_concepts'])}; "
              f"relative index {f(s['relative_index_median'])} (below 1: {s['concepts_relative_index_below_1']})")
        print(f"  Muse vs human spread rho {f(s['rank_correlation_muse_vs_human_spread']['rho'])} "
              f"{c(s['rank_correlation_muse_vs_human_spread']['ci95'])}; recognisability Muse "
              f"{f(s['muse_nearest_own_human_centroid'])}, SDXL {f(s['sdxl_nearest_own_human_centroid'])}, "
              f"people LOO {f(s['human_nearest_own_human_centroid_loo'])}")
        print(f"  most homogenized {s['most_homogenized']}; least {s['least_homogenized']}")
        if "patch_mean" in s:
            print(f"  patch-mean: {to_jsonable(s['patch_mean'])}")
        for k in [k for k in s if k.startswith("rank_agreement_")]:
            print(f"  {k}: {f(s[k]['rho'])} {c(s[k]['ci95'])}")
        print(f"  checks: {s['verdict']['checks']}")
    by = {t: {r["key"]: r for r in rows} for t, rows in all_rows.items()}
    print(f"\n{'concept':10s} " + " ".join(f"{t[:14]:>14s}" for t in by))
    for r in sorted(all_rows[REFERENCE], key=lambda r: r["muse"]["ratio_vs_people"]):
        print(f"{r['label']:10s} " + " ".join(f"{by[t][r['key']]['muse']['ratio_vs_people']:14.2f}" for t in by))


if __name__ == "__main__":
    main()

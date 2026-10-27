"""Plato's Chair: can you prompt Muse Image out of the Platonic chair? Visual and conceptual variety by prompt.

Usage: python -I scripts/plato_variety_analyze.py [--public public_data/plato_variety.json]
       (after plato_generate.py --style doodle_any|doodle_unusual|doodle_listed, plato_embed.py, and
        plato_kinds_label.py, whose label files are copied to $PLATO_DIR/kinds/)

Conditions (Muse Image): default (the core doodle prompt), any ("a chair (any kind of chair)"), unusual
("... pick an unusual or different kind", tier 1 only) and listed (Muse Spark lists n_ai kinds, one
doodle of each). SDXL drew default, any and listed with the same seeds (the stretch comparison).

1. Visual spread (DINOv2), exactly as the core analysis (plato_analyze.concept_stats): spread with a
   bootstrap CI, ratio to people's spread at the same n with a CI from independent bootstraps, and the
   ratio to the same generator's default spread (CI from independent bootstraps of the two sets).
   Recognisability: share of pictures whose nearest human centroid (of 35) is their own concept.
2. Kinds (Muse Glimmer's multiple-choice labels; see plato_kinds_label.py). Validation on the listed
   pictures, whose kind is known: accuracy, lenient accuracy (the right kind or "plain"), confusions.
   Per condition: distinct kinds, Simpson diversity (chance two pictures show different kinds; CI by
   bootstrap over pictures), entropy, share "plain", share "can't tell", and the prototype (most common
   kind). People: all cached drawings for Simpson and shares; distinct kinds at the AI's n by subsampling.
   "Reliable" concepts are those where Glimmer labels at least half of the listed pictures correctly.
3. Is people's visual spread kinds or drawing noise? The spread of people's drawings of their prototype
   kind alone, against all their drawings (same n).
Writes $PLATO_DIR/results_variety.json and derived statistics for public_data/plato_variety.json.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from plato_analyze import SUBSETS, concept_stats, load  # noqa: E402

from metalesionlab.plato import (BY_KEY, CONCEPTS, DINO_MODEL, PLATO_DIR, QUICKDRAW_CREDIT, TIER1,  # noqa: E402
                                 bootstrap_simpson, ci, cosine_distances, kind_diversity,
                                 spearman_ci, spread, subsample_spread, to_jsonable, variety_phrase)
from metalesionlab.plato_web import clean  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
# condition -> (embedding/label source, generator, default condition of that generator)
CONDITIONS = {
    "default": ("ai_doodle", "muse", "default"), "any": ("ai_doodle_any", "muse", "default"),
    "unusual": ("ai_doodle_unusual", "muse", "default"), "listed": ("ai_doodle_listed", "muse", "default"),
    "sdxl_default": ("ai_sdxl_doodle", "sdxl", "sdxl_default"), "sdxl_any": ("ai_sdxl_any", "sdxl", "sdxl_default"),
    "sdxl_listed": ("ai_sdxl_listed", "sdxl", "sdxl_default"),
}
MUSE = ["default", "any", "unusual", "listed"]
TIER1_KEYS = [k.replace(" ", "_") for k in TIER1]
RELIABLE = 0.5  # a concept's kind labels count as reliable if Glimmer gets >= half its listed pictures right
CONFIDENT = 0.6  # sensitivity check: a specific kind with a lower option probability counts as "plain"
SPARK_CREDIT = "Kind lists: Muse Spark 1.3 (Meta). Kind labels: Muse Glimmer 30B (Meta, open weights, self-hosted)."


def labels_for(source: str, key: str, root: Path = PLATO_DIR / "kinds") -> dict | None:
    """Glimmer's labels for one group: options, plain/none option text, and file -> label text."""
    path = root / f"{source}__{key}.json"
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    opts = d["options"]
    items = [it for it in d["items"] if it.get("label") is not None]
    return {"options": opts, "plain": opts[-2], "none": opts[-1], "n_kinds": len(opts) - 2,
            "files": [it["file"] for it in items], "labels": [opts[it["label"]] for it in items],
            "index": [it["label"] for it in items], "conf": [max(it["p"]) for it in items],
            "orders_agree": float(np.mean([it["label_fwd"] == it["label_rev"] for it in items])) if items and
            "label_fwd" in items[0] else None,
            "letter_mass": float(np.mean([np.mean(it["letter_mass"]) for it in items])) if items and
            "letter_mass" in items[0] else None}


def validate(lab: dict) -> dict:
    """Listed pictures: p<i>.png shows kind i. Accuracy, lenient accuracy (right kind or plain), shares."""
    truth = np.array([int(f.split(".")[0][1:]) for f in lab["files"]])
    pred = np.array(lab["index"])
    k = lab["n_kinds"]
    correct = pred == truth
    return {"n": len(truth), "accuracy": float(correct.mean()), "lenient_accuracy": float((correct | (pred == k)).mean()),
            "share_plain": float((pred == k).mean()), "share_none": float((pred == k + 1).mean()),
            "share_other_kind": float(((pred < k) & ~correct).mean()), "chance": 1 / (k + 2),
            "_correct": correct, "_conf": np.array(lab["conf"]), "_specific": pred < k,
            "confusions": [(lab["options"][t], lab["options"][p]) for t, p in zip(truth, pred) if t != p and p < k]}


def calibration(val: dict) -> dict | None:
    """How far to trust a specific-kind label: precision of Glimmer's specific-kind answers on the listed
    pictures, for confident (option probability >= CONFIDENT) and unsure answers."""
    if not val:
        return None
    correct = np.concatenate([v["_correct"] for v in val.values()])
    conf = np.concatenate([v["_conf"] for v in val.values()])
    spec = np.concatenate([v["_specific"] for v in val.values()])
    sure = conf >= CONFIDENT
    mean = lambda m: float(correct[m].mean()) if m.any() else None  # noqa: E731
    return {"threshold": CONFIDENT, "share_confident": float(sure.mean()),
            "accuracy_confident": mean(sure), "accuracy_unsure": mean(~sure),
            "specific_precision_confident": mean(spec & sure), "specific_precision_unsure": mean(spec & ~sure),
            "n_specific_confident": int((spec & sure).sum()), "n_specific_unsure": int((spec & ~sure).sum())}


def kinds_stats(lab: dict, n_eq: int, rng) -> dict:
    """Kind diversity of one group, with a bootstrap CI for Simpson and distinct kinds at n_eq pictures."""
    labels = lab["labels"]
    out = kind_diversity(labels, plain=lab["plain"], none=lab["none"])
    boot = bootstrap_simpson(labels, none=lab["none"], reps=1000, rng=rng)
    out["simpson_ci95"] = ci(boot[np.isfinite(boot)]) if np.isfinite(boot).sum() > 10 else None
    out["_simpson_boot"] = boot
    if len(labels) > n_eq:  # people: distinct kinds among random sets of the AI's size
        subs = [kind_diversity([labels[i] for i in rng.choice(len(labels), n_eq, replace=False)],
                               lab["plain"], lab["none"])["distinct"] for _ in range(SUBSETS)]
        out["distinct_at_n"] = float(np.mean(subs))
    else:
        out["distinct_at_n"] = float(out["distinct"])
    out["n_eq"] = n_eq
    # sensitivity: specific kinds Glimmer is unsure of (option probability < CONFIDENT) count as plain
    sure = [x if x in (lab["plain"], lab["none"]) or c >= CONFIDENT else lab["plain"]
            for x, c in zip(labels, lab["conf"])]
    d = kind_diversity(sure, plain=lab["plain"], none=lab["none"])
    out["confident"] = {f: d[f] for f in ("simpson", "distinct", "share_plain", "prototype")}
    return out


def human_noise(key: str, lab: dict, n: int, rng) -> dict | None:
    """People's visual spread within their prototype kind vs over all their drawings, both at n pictures."""
    h, files = load("human", key)
    if h is None:
        return None
    row = {f: i for i, f in enumerate(files)}
    proto = Counter(x for x in lab["labels"] if x != lab["none"]).most_common(1)[0][0]
    idx = np.array([row[f] for f, x in zip(lab["files"], lab["labels"]) if x == proto and f in row])
    if len(idx) < n + 4:
        return {"prototype": proto, "n_prototype": int(len(idx))}
    d = cosine_distances(h)
    within = float(subsample_spread(d[np.ix_(idx, idx)], n, SUBSETS, rng).mean())
    overall = float(subsample_spread(d, n, SUBSETS, rng).mean())
    return {"prototype": proto, "n_prototype": int(len(idx)), "spread_within_prototype": within,
            "spread_all": overall, "share_of_spread_within_prototype": within / overall}


def nearest_own_share(a: np.ndarray, centroids: np.ndarray, keys: list[str], key: str) -> float:
    """Share of pictures whose nearest human centroid (cosine, among all concepts) is their own concept's."""
    an = a / np.linalg.norm(a, axis=1, keepdims=True)
    return float(np.mean(np.array(keys)[np.argmax(an @ centroids.T, axis=1)] == key))


def visual(rng) -> tuple[list[dict], dict]:
    """Per concept and condition: spread, ratio to people, ratio to the generator's default, recognisability."""
    rows, sets, hu_all = {}, {cond: {} for cond in CONDITIONS}, {}
    boots = {}
    for c in CONCEPTS:
        h, _ = load("human", c.key)
        if h is None:
            continue
        hu_all[c.key] = h
        row = {"key": c.key, "label": c.label, "tier": c.tier, "n_human_pool": len(h)}
        for cond, (source, _, _) in CONDITIONS.items():
            n = c.n_ai if cond == "default" else None
            a, _ = load(source, c.key, n)
            want = 16 if cond == "sdxl_default" else c.n_ai
            if a is None or len(a) < want:
                continue
            st = concept_stats(a, h, len(a), rng)
            sets[cond][c.key] = a
            boots[(cond, c.key)] = st["_ai_boot"]
            row[cond] = {"n": len(a), "spread": st["ai_spread"], "spread_ci95": st["ai_spread_ci95"],
                         "human_spread": st["human_spread"], "ratio_vs_people": st["homogenization_index"],
                         "ratio_vs_people_ci95": st["homogenization_index_ci95"],
                         "share_of_human_sets_as_uniform": st["share_of_human_sets_as_uniform_as_ai"]}
        rows[c.key] = row
    keys = list(hu_all)
    mus = np.stack([(hu_all[k] / np.linalg.norm(hu_all[k], axis=1, keepdims=True)).mean(0) for k in keys])
    for cond, (_, _, base) in CONDITIONS.items():
        for k in [k for k in keys if k in sets[cond]]:
            r = rows[k][cond]
            r["nearest_own_human_centroid"] = nearest_own_share(sets[cond][k], mus, keys, k)
            if cond != base and (base, k) in boots:
                b0, b1 = boots[(base, k)], boots[(cond, k)]
                r["ratio_vs_default"] = r["spread"] / rows[k][base]["spread"]
                r["ratio_vs_default_ci95"] = ci(b1 / b0)
    return list(rows.values()), {"keys": keys}


def summarize_visual(rows: list[dict], cond: str, keys: list[str] | None = None) -> dict | None:
    rs = [r for r in rows if cond in r and (keys is None or r["key"] in keys)]
    if not rs:
        return None
    ratio = np.array([r[cond]["ratio_vs_people"] for r in rs])
    out = {"n_concepts": len(rs), "median_ratio_vs_people": float(np.median(ratio)),
           "concepts_above_people": int((ratio > 1).sum()),
           "concepts_ci_above_people": int(sum(r[cond]["ratio_vs_people_ci95"][0] > 1 for r in rs)),
           "concepts_ci_below_people": int(sum(r[cond]["ratio_vs_people_ci95"][1] < 1 for r in rs)),
           "mean_spread": float(np.mean([r[cond]["spread"] for r in rs])),
           "mean_human_spread": float(np.mean([r[cond]["human_spread"] for r in rs])),
           "nearest_own_human_centroid": float(np.mean([r[cond]["nearest_own_human_centroid"] for r in rs]))}
    vd = [r[cond]["ratio_vs_default"] for r in rs if "ratio_vs_default" in r[cond]]
    if vd:
        out["median_ratio_vs_default"] = float(np.median(vd))
        out["concepts_ci_above_default"] = int(sum(r[cond]["ratio_vs_default_ci95"][0] > 1 for r in rs
                                                   if "ratio_vs_default" in r[cond]))
    out["poorly_recognised"] = {r["label"]: r[cond]["nearest_own_human_centroid"] for r in rs
                                if r[cond]["nearest_own_human_centroid"] < 0.5}
    return out


def kinds(rows: list[dict], rng) -> dict:
    """Validation, then kind diversity per condition and people, and the default-vs-people comparison."""
    val, val_sdxl = {}, {}
    for c in CONCEPTS:
        for cond, store in (("ai_doodle_listed", val), ("ai_sdxl_listed", val_sdxl)):
            lab = labels_for(cond, c.key)
            if lab:
                store[c.key] = validate(lab)
    by = {r["key"]: r for r in rows}
    reliable = [k for k, v in val.items() if v["accuracy"] >= RELIABLE]
    per = {}
    for c in CONCEPTS:
        row = {}
        for cond, (source, _, _) in list(CONDITIONS.items()) + [("people", ("human", None, None))]:
            lab = labels_for(source, c.key)
            if not lab:
                continue
            if cond == "default":  # the core analysis uses the first n_ai Muse pictures
                keep = set(sorted(lab["files"], key=lambda f: (len(f), f))[:c.n_ai])
                for f in ("files", "labels", "index"):
                    lab[f] = [x for x, name in zip(lab[f], lab["files"]) if name in keep]
            row[cond] = kinds_stats(lab, c.n_ai, rng)
            row[cond]["orders_agree"] = lab["orders_agree"]
            row[cond]["letter_mass"] = lab["letter_mass"]
            if cond == "people":
                row["people_noise"] = human_noise(c.key, lab, c.n_ai, rng)
        if "default" in row and "people" in row:
            d, p = row["default"], row["people"]
            diff = p["_simpson_boot"][:len(d["_simpson_boot"])] - d["_simpson_boot"]
            row["people_vs_default"] = {"same_prototype": d["prototype"] == p["prototype"],
                                        "simpson_difference": p["simpson"] - d["simpson"]
                                        if np.isfinite(d["simpson"]) and np.isfinite(p["simpson"]) else None,
                                        "simpson_difference_ci95": ci(diff[np.isfinite(diff)])
                                        if np.isfinite(diff).sum() > 10 else None}
        per[c.key] = row
        if c.key in by:
            by[c.key]["kinds"] = {k: {f: v for f, v in s.items() if not f.startswith("_")} if isinstance(s, dict) else s
                                  for k, s in row.items()}
    conds = [*CONDITIONS, "people"]

    def summary(keys: list[str]) -> dict:
        out = {}
        for cond in conds:
            rs = [per[k][cond] for k in keys if cond in per.get(k, {})]
            if not rs:
                continue
            simp = np.array([r["simpson"] for r in rs], float)
            out[cond] = {"n_concepts": len(rs), "median_simpson": float(np.nanmedian(simp)),
                         "mean_simpson": float(np.nanmean(simp)),
                         "mean_distinct_at_n": float(np.mean([r["distinct_at_n"] for r in rs])),
                         "mean_effective_kinds": float(np.nanmean([r["effective_kinds"] for r in rs])),
                         "mean_share_plain": float(np.nanmean([r["share_plain"] for r in rs])),
                         "mean_simpson_confident": float(np.nanmean([r["confident"]["simpson"] for r in rs])),
                         "mean_share_plain_confident": float(np.nanmean([r["confident"]["share_plain"] for r in rs])),
                         "mean_share_none": float(np.mean([r["share_none"] for r in rs])),
                         "mean_prototype_share": float(np.nanmean([r["prototype_share"] for r in rs])),
                         "concepts_prototype_plain": int(sum(r["prototype"] is not None and
                                                             r["prototype"].startswith(("a plain", "a person in a plain"))
                                                             for r in rs))}
        pv = [per[k]["people_vs_default"] for k in keys if "people_vs_default" in per.get(k, {})]
        if pv:
            out["people_vs_default"] = {
                "n_concepts": len(pv), "same_prototype": int(sum(x["same_prototype"] for x in pv)),
                "people_more_kinds": int(sum((x["simpson_difference"] or 0) > 0 for x in pv)),
                "people_more_kinds_ci": int(sum(x["simpson_difference_ci95"] is not None and
                                                x["simpson_difference_ci95"][0] > 0 for x in pv)),
                "default_more_kinds_ci": int(sum(x["simpson_difference_ci95"] is not None and
                                                 x["simpson_difference_ci95"][1] < 0 for x in pv))}
        noise = [per[k]["people_noise"] for k in keys if (per.get(k, {}).get("people_noise") or {}).get("spread_all")]
        if noise:
            out["people_spread_within_prototype"] = {
                "n_concepts": len(noise),
                "median_share": float(np.median([x["share_of_spread_within_prototype"] for x in noise]))}
        return out

    acc = np.array([v["accuracy"] for v in val.values()])
    conf = Counter(pair for v in val.values() for pair in v["confusions"])
    validation = {
        "n_concepts": len(val), "n_pictures": int(sum(v["n"] for v in val.values())),
        "accuracy": float(np.sum([v["accuracy"] * v["n"] for v in val.values()]) / max(1, sum(v["n"] for v in val.values()))),
        "lenient_accuracy": float(np.sum([v["lenient_accuracy"] * v["n"] for v in val.values()]) /
                                  max(1, sum(v["n"] for v in val.values()))),
        "median_concept_accuracy": float(np.median(acc)) if len(acc) else None,
        "mean_chance": float(np.mean([v["chance"] for v in val.values()])) if val else None,
        "share_plain": float(np.mean([v["share_plain"] for v in val.values()])) if val else None,
        "share_none": float(np.mean([v["share_none"] for v in val.values()])) if val else None,
        "share_other_kind": float(np.mean([v["share_other_kind"] for v in val.values()])) if val else None,
        "reliable_concepts": reliable, "reliable_threshold": RELIABLE,
        "calibration": calibration(val),
        "per_concept": {k: {f: x for f, x in v.items() if f != "confusions" and not f.startswith("_")}
                        for k, v in val.items()},
        "top_confusions": [{"true": t, "labeled": p, "n": n} for (t, p), n in conf.most_common(12)],
        "sdxl_listed": ({"n_concepts": len(val_sdxl),
                         "accuracy": float(np.mean([v["accuracy"] for v in val_sdxl.values()])),
                         "lenient_accuracy": float(np.mean([v["lenient_accuracy"] for v in val_sdxl.values()]))}
                        if val_sdxl else None),
    }
    all_keys = [c.key for c in CONCEPTS]
    return {"validation": validation, "all": summary(all_keys), "reliable": summary(reliable),
            "tier1": summary(TIER1_KEYS), "tier1_reliable": summary([k for k in TIER1_KEYS if k in reliable]),
            "_per": per}


def spark_check(per: dict) -> dict | None:
    """Agreement between Muse Spark (a sample) and Glimmer on the same pictures; Spark's listed accuracy."""
    root = PLATO_DIR / "kinds_spark"
    if not root.exists():
        return None
    out, pairs = {}, {}
    for path in sorted(root.glob("*.json")):
        d = json.loads(path.read_text())
        g = labels_for(d["source"], d["key"])
        if not g:
            continue
        gl = dict(zip(g["files"], g["index"]))
        # Simpson on the shared sample, per concept (pairs of recognisable pictures with different kinds),
        # averaged over concepts so that the larger chair sample does not dominate
        none = len(d["options"]) - 1
        for who, labs in (("spark", [it["label"] for it in d["items"] if it["file"] in gl]),
                          ("glimmer", [gl[it["file"]] for it in d["items"] if it["file"] in gl])):
            labs = [x for x in labs if x is not None and x != none]
            n_pairs = len(labs) * (len(labs) - 1) // 2
            if n_pairs:
                diff = sum(a != b for i, a in enumerate(labs) for b in labs[i + 1:])
                pairs.setdefault((d["source"], who), []).append(diff / n_pairs)
        for it in d["items"]:
            if it["file"] not in gl:
                continue
            s = out.setdefault(d["source"], {"n": 0, "agree": 0, "spark_parsed": 0, "spark_correct": 0,
                                             "glimmer_correct": 0, "spark_plain": 0, "glimmer_plain": 0,
                                             "spark_none": 0, "glimmer_none": 0, "agree_category": 0})
            s["n"] += 1
            k = len(d["options"]) - 2
            cat = lambda i: "none" if i is None or i == k + 1 else "plain" if i == k else "kind"  # noqa: E731
            s["spark_parsed"] += it["label"] is not None
            s["agree"] += it["label"] == gl[it["file"]]
            s["agree_category"] += cat(it["label"]) == cat(gl[it["file"]])
            s["spark_plain"] += it["label"] == k
            s["glimmer_plain"] += gl[it["file"]] == k
            s["spark_none"] += cat(it["label"]) == "none"
            s["glimmer_none"] += cat(gl[it["file"]]) == "none"
            if d["source"].endswith("listed"):
                t = int(it["file"].split(".")[0][1:])
                s["spark_correct"] += it["label"] == t
                s["glimmer_correct"] += gl[it["file"]] == t
    for s in out.values():
        n = max(s["n"], 1)
        s.update(agreement=s["agree"] / n, category_agreement=s["agree_category"] / n)
        for who in ("spark", "glimmer"):  # among recognisable pictures (not "can't tell"): plain vs a specific kind
            rec = max(s["n"] - s[f"{who}_none"], 1)
            s[f"{who}_share_none"] = s[f"{who}_none"] / n
            s[f"{who}_share_plain_of_recognisable"] = s[f"{who}_plain"] / rec
            s[f"{who}_share_specific_of_recognisable"] = 1 - s[f"{who}_plain"] / rec
    for (source, who), rates in pairs.items():
        if source in out:
            out[source][f"{who}_mean_simpson"] = float(np.mean(rates))
            out[source][f"{who}_simpson_concepts"] = len(rates)
        if s["spark_correct"] or s["glimmer_correct"]:
            s.update(spark_accuracy=s["spark_correct"] / n, glimmer_accuracy=s["glimmer_correct"] / n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", type=Path, default=REPO / "public_data" / "plato_variety.json")
    args = ap.parse_args()
    rng = np.random.default_rng(20261028)
    rows, _ = visual(rng)
    vis = {"all": {c: summarize_visual(rows, c) for c in CONDITIONS},
           "tier1": {c: summarize_visual(rows, c, TIER1_KEYS) for c in CONDITIONS}}
    k = kinds(rows, rng)
    per = k.pop("_per")
    spark = spark_check(per)
    # across concepts: does people's visual spread track how many kinds they draw?
    pairs = [(r["default"]["human_spread"], per[r["key"]]["people"]["simpson"]) for r in rows
             if "default" in r and "people" in per.get(r["key"], {})]
    pairs = [(a, b) for a, b in pairs if np.isfinite(b)]
    link = spearman_ci([a for a, _ in pairs], [b for _, b in pairs], rng=rng) if len(pairs) >= 8 else None
    results = {
        "experiment": "Plato's Chair: can you prompt Muse Image out of the Platonic chair?",
        "conditions": {"default": "core doodle prompt", "any": variety_phrase(BY_KEY["chair"], "any"),
                       "unusual": variety_phrase(BY_KEY["chair"], "unusual") + " (tier 1 only)",
                       "listed": "Muse Spark lists n_ai kinds; Muse Image draws each once",
                       "sdxl_*": "Stable Diffusion XL, same prompts and seeds"},
        "embedding_model": DINO_MODEL, "spread": "mean pairwise cosine distance within a concept",
        "credits": [QUICKDRAW_CREDIT, SPARK_CREDIT],
        "visual": vis, "kinds": k, "spark_check": spark,
        "rank_correlation_people_spread_vs_people_kind_diversity": link,
        "concepts": rows,
    }
    out = PLATO_DIR / "results_variety.json"
    out.write_text(json.dumps(to_jsonable(results), indent=1, ensure_ascii=False))
    print(f"wrote {out}")
    public = clean(to_jsonable(public_block(results)))  # NaN -> null: browsers cannot parse NaN
    args.public.write_text(json.dumps(public, indent=1) + "\n")
    print(f"wrote {args.public}")
    report(results)


def public_block(res: dict) -> dict:
    """Derived statistics only: per concept and condition, no pictures, embeddings or per-picture labels."""
    keep_v = ("n", "spread", "spread_ci95", "ratio_vs_people", "ratio_vs_people_ci95", "ratio_vs_default",
              "ratio_vs_default_ci95", "nearest_own_human_centroid")
    keep_k = ("n", "distinct", "distinct_at_n", "simpson", "simpson_ci95", "effective_kinds", "share_plain",
              "share_none", "prototype", "prototype_share")
    concepts = []
    for r in res["concepts"]:
        row = {"label": r["label"], "quickdraw": BY_KEY[r["key"]].quickdraw, "tier": r["tier"],
               "human_spread": (r.get("default") or {}).get("human_spread")}
        for cond in CONDITIONS:
            if cond in r:
                row[cond] = {f: r[cond][f] for f in keep_v if f in r[cond]}
        kk = r.get("kinds") or {}
        row["kinds"] = {cond: {f: kk[cond][f] for f in keep_k if f in kk[cond]} for cond in [*CONDITIONS, "people"]
                        if cond in kk}
        if "people_vs_default" in kk:
            row["kinds"]["people_vs_default"] = kk["people_vs_default"]
        if (kk.get("people_noise") or {}).get("spread_all"):
            row["kinds"]["people_spread_within_prototype"] = kk["people_noise"]
        concepts.append(row)
    val = dict(res["kinds"]["validation"])
    return {
        "about": "Plato's Chair, can you prompt it out of the Platonic chair? How varied Muse Image's doodles are "
                 "under four prompts (default, any kind, an unusual kind, each of Muse Spark's listed kinds), "
                 "against people's drawings (Google Quick, Draw!), visually (Meta DINOv2 spread) and in which "
                 "KIND of object they show (Muse Glimmer multiple-choice labels). Derived statistics only; no "
                 "drawings. See docs/plato.md.",
        "attribution": QUICKDRAW_CREDIT, "credits": res["credits"], "conditions": res["conditions"],
        "spread": res["spread"], "embedding_model": res["embedding_model"],
        "visual_summary": res["visual"], "kinds_summary": {k: v for k, v in res["kinds"].items() if k != "validation"},
        "labeler_validation": {k: v for k, v in val.items() if k != "per_concept"},
        "labeler_validation_per_concept": val["per_concept"],
        "spark_check": res["spark_check"],
        "rank_correlation_people_spread_vs_people_kind_diversity": res["rank_correlation_people_spread_vs_people_kind_diversity"],
        "concepts": concepts,
    }


def report(res: dict) -> None:
    print("\nVISUAL (median ratio vs people; vs default; recognisability)")
    for scope in ("all", "tier1"):
        for cond, s in res["visual"][scope].items():
            if s:
                print(f"  {scope:6s} {cond:13s} n={s['n_concepts']:2d} vs people {s['median_ratio_vs_people']:.2f} "
                      f"(above {s['concepts_above_people']}, CI above {s['concepts_ci_above_people']}, CI below "
                      f"{s['concepts_ci_below_people']}) vs default {s.get('median_ratio_vs_default', float('nan')):.2f} "
                      f"own-centroid {s['nearest_own_human_centroid']:.2f}")
    v = res["kinds"]["validation"]
    if not v["n_pictures"]:
        print("\nno labeler validation yet (label the listed pictures)")
        return
    print(f"\nLABELER: accuracy {v['accuracy']:.2f} lenient {v['lenient_accuracy']:.2f} chance {v['mean_chance']:.2f} "
          f"plain {v['share_plain']:.2f} none {v['share_none']:.2f}; reliable {len(v['reliable_concepts'])}: "
          f"{v['reliable_concepts']}")
    for kk, x in sorted(v["per_concept"].items(), key=lambda kv: -kv[1]["accuracy"]):
        print(f"  {kk:12s} acc {x['accuracy']:.2f} lenient {x['lenient_accuracy']:.2f} plain {x['share_plain']:.2f}")
    print("  top confusions:", v["top_confusions"][:8])
    print("  calibration:", to_jsonable(v["calibration"]))
    for scope in ("all", "reliable", "tier1"):
        print(f"\nKINDS ({scope})")
        for cond, s in res["kinds"][scope].items():
            print(f"  {cond:18s} {json.dumps(to_jsonable(s))}")
    print("\nSPARK CHECK", json.dumps(to_jsonable(res["spark_check"])))
    print("people spread vs kinds", to_jsonable(res["rank_correlation_people_spread_vs_people_kind_diversity"]))
    print(f"\n{'concept':10s} " + " ".join(f"{c:>9s}" for c in MUSE) + "   kinds: default people (Simpson; prototype)")
    for r in res["concepts"]:
        kk = r.get("kinds") or {}
        vals = " ".join(f"{r[c]['ratio_vs_people']:9.2f}" if c in r else f"{'':9s}" for c in MUSE)
        d, p = kk.get("default") or {}, kk.get("people") or {}
        print(f"{r['label']:10s} {vals}   {d.get('simpson', float('nan')):.2f} {p.get('simpson', float('nan')):.2f}; "
              f"{d.get('prototype')} | {p.get('prototype')} ({p.get('prototype_share', float('nan')):.2f})")


if __name__ == "__main__":
    main()

"""Embed every doodle with DINOv2 and measure how the "ideal" object moves across languages and countries.

Steps (each cached under $PLATO_LANG_DIR):
  embed    DINOv2-base CLS + mean-patch embeddings for AI doodles (canonicalized) and human renders
           -> emb/ai.npz, emb/human.npz
  analyze  spread, centroid shift with a permutation baseline, group share with bootstrap CIs, AI vs
           human comparison at equal n, concept ranking, language-country alignment -> results.json

Runs locally (MPS or CPU); costs nothing. Reads only PNGs we rendered or generated.
Usage: python scripts/plato_lang_analyze.py [embed] [analyze] [--perm 2000] [--boot 2000]
"""
import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato_lang import (  # noqa: E402
    CONCEPTS, COUNTRIES, DINO, LANG_COUNTRY, LANGS, OUT, QD_CREDIT, Dino, bootstrap, canonical_ai, ci,
    cosine_distances, group_measures, permutation_test, uniform_lines,
)

AI_N = 10  # doodles per language per concept
HUMAN_N = 200  # drawings per country per concept
EMB = OUT / "emb"


def files(domain: str) -> dict[tuple[str, str], list[Path]]:
    groups = LANGS if domain == "ai" else COUNTRIES
    return {(g, c): sorted((OUT / domain / g / c).glob("*.png")) for g in groups for c in CONCEPTS}


def cache_path(domain: str, variant: str = "raw") -> Path:
    return EMB / (f"{domain}.npz" if variant == "raw" else f"{domain}_{variant}.npz")


def prep(job):
    """The image DINOv2 sees: canonical AI doodle or human render; 'uniform' redraws lines at one width."""
    domain, variant, path = job
    img = canonical_ai(path) if domain == "ai" else _load(path)
    return uniform_lines(img) if variant == "uniform" else img


def embed(domain: str, dino: Dino | None, variant: str = "raw") -> Dino | None:
    from concurrent.futures import ProcessPoolExecutor
    cache = cache_path(domain, variant)
    have = {}
    if cache.exists():
        z = np.load(cache)
        have = {k: (z["cls"][i], z["patch"][i]) for i, k in enumerate(z["keys"])}
    paths = [p for ps in files(domain).values() for p in ps]
    keys = [str(p.relative_to(OUT)) for p in paths]
    todo = [(k, p) for k, p in zip(keys, paths) if k not in have]
    if todo:
        dino = dino or Dino()
        t0 = time.time()
        pool = ProcessPoolExecutor(6)
        for i in range(0, len(todo), 256):
            chunk = todo[i:i + 256]
            images = list(pool.map(prep, [(domain, variant, p) for _, p in chunk], chunksize=8))
            e = dino.embed(images)
            for j, (k, _) in enumerate(chunk):
                have[k] = (e["cls"][j], e["patch"][j])
            print(f"  {domain} {variant}: {min(i + 256, len(todo))}/{len(todo)} ({time.time() - t0:.0f}s, "
                  f"{dino.device})", flush=True)
        pool.shutdown()
    keys = sorted(have)
    EMB.mkdir(parents=True, exist_ok=True)
    np.savez(cache, keys=np.array(keys), cls=np.stack([have[k][0] for k in keys]),
             patch=np.stack([have[k][1] for k in keys]))
    print(f"{domain}: {len(keys)} embeddings in {cache}")
    return dino


def _load(path: Path):
    from PIL import Image
    return Image.open(path).convert("L")


def load(domain: str, kind: str = "cls", variant: str = "raw"):
    """{concept: (embeddings (N, d), labels (N,), group names)} with equal n per group."""
    z = np.load(cache_path(domain, variant))
    index = {k: i for i, k in enumerate(z["keys"])}
    groups = list(LANGS if domain == "ai" else COUNTRIES)
    n = AI_N if domain == "ai" else HUMAN_N
    out = {}
    for c in CONCEPTS:
        rows, labels = [], []
        for g_i, g in enumerate(groups):
            keys = sorted(k for k in index if k.startswith(f"{domain}/{g}/{c}/"))
            if len(keys) < n:
                raise SystemExit(f"{domain}/{g}/{c}: only {len(keys)} of {n} doodles")
            rows += [index[k] for k in keys[:n]]
            labels += [g_i] * n
        out[c] = (z[kind][rows], np.array(labels), groups)
    return out


def r(x, nd=4):
    return round(float(x), nd)


def triu_dict(mat, groups):
    return {f"{groups[i]}-{groups[j]}": r(mat[i, j]) for i, j in itertools.combinations(range(len(groups)), 2)}


def measure(emb, labels, groups, n_perm, n_boot, seed=0) -> dict:
    k = len(groups)
    D = cosine_distances(emb)
    m = group_measures(D, labels, k)
    perm = permutation_test(emb, labels, k, n_perm, seed)
    boot = bootstrap(emb, labels, k, n_boot, seed)
    iu = np.triu_indices(k, 1)
    null_mat = np.zeros((k, k))
    null_mat[iu] = perm["centroid_null_mean"]
    p_mat = np.ones((k, k))
    p_mat[iu] = perm["centroid_pair_p"]
    return {
        "n_per_group": int((labels == 0).sum()),
        "spread": {g: [r(m["W"][i]), r(boot["W_ci"][0][i]), r(boot["W_ci"][1][i])] for i, g in enumerate(groups)},
        "spread_mean": [r(m["W"].mean()), *[r(x) for x in ci(boot["W"].mean(1))]],
        "share": [r(m["share"]), r(boot["share_ci"][0]), r(boot["share_ci"][1])],
        "share_null_mean": r(perm["share_null_mean"]),
        "share_p": r(perm["share_p"]),
        "between": [r(m["B_mean"]), r(boot["B_mean_ci"][0]), r(boot["B_mean_ci"][1])],
        "centroid_mean": r(perm["centroid_mean"]),
        "centroid_mean_null": r(perm["centroid_mean_null"]),
        "centroid_mean_null_95": r(perm["centroid_mean_null_95"]),
        "centroid_mean_p": r(perm["centroid_mean_p"]),
        "centroid_ratio": r(perm["centroid_mean"] / perm["centroid_mean_null"], 3),
        "centroid_pairs": triu_dict(perm["centroid"], groups),
        "centroid_pairs_null": triu_dict(null_mat, groups),
        "centroid_pairs_p": triu_dict(p_mat, groups),
        "between_pairs": triu_dict(m["B"], groups),
        "_boot_share": boot["share"],
        "_boot_between": boot["B_mean"],
        "_boot_spread": boot["W"].mean(1),
    }


def equal_n(emb, labels, groups, n, reps, seed=0) -> dict:
    """Human measures recomputed on random subsamples of n per country, to match the AI's sample size."""
    rng = np.random.default_rng(seed)
    k = len(groups)
    D = cosine_distances(emb)
    idx = [np.flatnonzero(labels == g) for g in range(k)]
    share, cmean, spread = np.empty(reps), np.empty(reps), np.empty(reps)
    from metalesionlab.plato_lang import centroid_distances
    iu = np.triu_indices(k, 1)
    for t in range(reps):
        pick = np.concatenate([rng.choice(ii, n, replace=False) for ii in idx])
        lab = labels[pick]
        m = group_measures(D[np.ix_(pick, pick)], lab, k)
        share[t], spread[t] = m["share"], m["W"].mean()
        cmean[t] = centroid_distances(emb[pick], lab, k)[iu].mean()
    return {"n_per_group": n, "share": [r(share.mean()), *[r(x) for x in ci(share)]],
            "centroid_mean": [r(cmean.mean()), *[r(x) for x in ci(cmean)]],
            "spread_mean": [r(spread.mean()), *[r(x) for x in ci(spread)]]}


def alignment(ai, human, n_concepts) -> dict:
    """Does the AI's drift for a language point the same way as people's drift for the matching country?

    Per concept, each group's centroid minus the mean of its domain's six centroids; cosine between the
    AI deviation for language L and the human deviation for country C. Statistic: mean cosine over the
    five matched pairs (en-US, es-MX, hi-IN, zh-TW, ar-SA) and all concepts. Null: every way of
    assigning the six countries to the six languages (720), the same assignment for all concepts."""
    langs, countries = list(LANGS), list(COUNTRIES)
    cos = np.zeros((n_concepts, len(langs), len(countries)))
    for ci_, c in enumerate(CONCEPTS):
        dev = {}
        for name, (emb, labels, groups) in (("ai", ai[c]), ("human", human[c])):
            cents = np.stack([emb[labels == g].mean(0) for g in range(len(groups))])
            d = cents - cents.mean(0)
            dev[name] = d / np.linalg.norm(d, axis=1, keepdims=True)
        cos[ci_] = dev["ai"] @ dev["human"].T
    matched = [(langs.index(lg), countries.index(ct)) for lg, ct in LANG_COUNTRY.items()]
    stat = lambda perm: np.mean([cos[:, i, perm[j]] for i, j in matched])
    obs = stat(list(range(len(countries))))
    null = np.array([stat(p) for p in itertools.permutations(range(len(countries)))])
    per_pair = {f"{lg}-{ct}": r(cos[:, langs.index(lg), countries.index(ct)].mean()) for lg, ct in LANG_COUNTRY.items()}
    mismatched = np.mean([cos[:, i, j] for i in range(len(langs)) for j in range(len(countries))
                          if (i, j) not in matched])
    return {"matched_mean_cos": r(obs), "mismatched_mean_cos": r(mismatched),
            "null_mean": r(null.mean()), "null_95": r(np.quantile(null, 0.95)),
            "p": r((null >= obs).mean()), "per_pair": per_pair,
            "per_concept_matched": {c: r(np.mean([cos[k, i, j] for i, j in matched])) for k, c in enumerate(CONCEPTS)}}


def validity(ai, human) -> dict:
    """Free sanity check: is each AI doodle closest to the human centroid of its own concept?"""
    cents = np.stack([human[c][0].mean(0) for c in CONCEPTS])
    cents /= np.linalg.norm(cents, axis=1, keepdims=True)
    hits = {lang: [] for lang in LANGS}
    misses = []
    for ci_, c in enumerate(CONCEPTS):
        emb, labels, groups = ai[c]
        guess = (emb @ cents.T).argmax(1)
        for g_i, g in enumerate(groups):
            sel = labels == g_i
            hits[g].append(float((guess[sel] == ci_).mean()))
            misses += [f"{g}/{c}->{CONCEPTS[j]}" for j in guess[sel] if j != ci_]
    return {"nearest_human_concept_accuracy": {g: r(np.mean(v), 3) for g, v in hits.items()},
            "overall": r(np.mean([np.mean(v) for v in hits.values()]), 3), "misses": misses}


def spearman(a, b):
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def analyze(n_perm: int, n_boot: int, kind: str = "cls", variant: str = "raw") -> dict:
    ai, human = load("ai", kind, variant), load("human", kind, variant)
    res = {"ai": {}, "human": {}, "human_equal_n": {}}
    for c in CONCEPTS:
        t0 = time.time()
        res["ai"][c] = measure(*ai[c], n_perm, n_boot)
        res["human"][c] = measure(*human[c], max(500, n_perm // 2), max(500, n_boot // 2))
        res["human_equal_n"][c] = equal_n(*human[c], AI_N, 1000)
        print(f"  {kind}/{variant} {c}: share AI {res['ai'][c]['share']} vs human {res['human'][c]['share']} "
              f"({time.time() - t0:.0f}s)", flush=True)

    # AI vs people
    diffs, comp = [], {}
    for c in CONCEPTS:
        a, h = res["ai"][c], res["human"][c]
        nb = min(len(a["_boot_share"]), len(h["_boot_share"]))
        d = a["_boot_share"][:nb] - h["_boot_share"][:nb]
        diffs.append(d)
        comp[c] = {"share_ai": a["share"], "share_human": h["share"],
                   "share_diff": [r(a["share"][0] - h["share"][0]), *[r(x) for x in ci(d)]],
                   "centroid_ratio_ai": a["centroid_ratio"], "centroid_ratio_human": h["centroid_ratio"],
                   "spread_ai": a["spread_mean"], "spread_human": h["spread_mean"]}
    nb = min(len(d) for d in diffs)
    mean_ai = np.mean([res["ai"][c]["_boot_share"][:nb] for c in CONCEPTS], axis=0)
    mean_h = np.mean([res["human"][c]["_boot_share"][:nb] for c in CONCEPTS], axis=0)
    spread_ai = np.mean([res["ai"][c]["_boot_spread"][:nb] for c in CONCEPTS], axis=0)
    spread_h = np.mean([res["human"][c]["_boot_spread"][:nb] for c in CONCEPTS], axis=0)
    between_ai = np.mean([res["ai"][c]["_boot_between"][:nb] for c in CONCEPTS], axis=0)
    between_h = np.mean([res["human"][c]["_boot_between"][:nb] for c in CONCEPTS], axis=0)
    b_ai = np.array([res["ai"][c]["between"][0] for c in CONCEPTS])
    b_h = np.array([res["human"][c]["between"][0] for c in CONCEPTS])
    share_ai = np.array([res["ai"][c]["share"][0] for c in CONCEPTS])
    share_h = np.array([res["human"][c]["share"][0] for c in CONCEPTS])
    rng = np.random.default_rng(0)
    rho = spearman(share_ai, share_h)
    rho_null = np.array([spearman(share_ai, rng.permutation(share_h)) for _ in range(5000)])
    summary = {
        "mean_share_ai": [r(share_ai.mean()), *[r(x) for x in ci(mean_ai)]],
        "mean_share_human": [r(share_h.mean()), *[r(x) for x in ci(mean_h)]],
        "mean_share_diff": [r(share_ai.mean() - share_h.mean()), *[r(x) for x in ci(mean_ai - mean_h)]],
        "mean_share_human_equal_n": r(np.mean([res["human_equal_n"][c]["share"][0] for c in CONCEPTS])),
        "concepts_ai_gt_human": int((share_ai > share_h).sum()),
        "concepts_ai_sig": [c for c in CONCEPTS if res["ai"][c]["share_p"] < 0.05],
        "concepts_human_sig": [c for c in CONCEPTS if res["human"][c]["share_p"] < 0.05],
        "mean_spread_ai": [r(spread_ai.mean()), *[r(x) for x in ci(spread_ai)]],
        "mean_spread_human": [r(spread_h.mean()), *[r(x) for x in ci(spread_h)]],
        "mean_between_ai": [r(b_ai.mean()), *[r(x) for x in ci(between_ai)]],
        "mean_between_human": [r(b_h.mean()), *[r(x) for x in ci(between_h)]],
        "concepts_between_ai_gt_human": [c for c, a, h in zip(CONCEPTS, b_ai, b_h) if a > h],
        "rank_ai": sorted(CONCEPTS, key=lambda c: -res["ai"][c]["share"][0]),
        "rank_human": sorted(CONCEPTS, key=lambda c: -res["human"][c]["share"][0]),
        "spearman_ai_human": r(rho, 3),
        "spearman_p": r((np.abs(rho_null) >= abs(rho)).mean(), 4),
    }
    # average centroid-distance matrices across concepts (for the heatmap)
    heat = {}
    for dom, groups in (("ai", list(LANGS)), ("human", list(COUNTRIES))):
        k = len(groups)
        obs, null, between = np.zeros((k, k)), np.zeros((k, k)), np.zeros((k, k))
        for c in CONCEPTS:
            for key, mat in (("centroid_pairs", obs), ("centroid_pairs_null", null), ("between_pairs", between)):
                for pair, v in res[dom][c][key].items():
                    a, b = pair.split("-")
                    i, j = groups.index(a), groups.index(b)
                    mat[i, j] += v / len(CONCEPTS)
                    mat[j, i] = mat[i, j]
        heat[dom] = {"groups": groups, "centroid": np.round(obs, 4).tolist(),
                     "centroid_null": np.round(null, 4).tolist(), "between": np.round(between, 4).tolist()}
    for dom in ("ai", "human"):
        for c in CONCEPTS:
            for key in [k for k in res[dom][c] if k.startswith("_")]:
                del res[dom][c][key]
    return {**res, "comparison": comp, "summary": summary, "heatmap": heat,
            "alignment": alignment(ai, human, len(CONCEPTS)), "validity": validity(ai, human)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("steps", nargs="*", default=["embed", "analyze"])
    ap.add_argument("--perm", type=int, default=2000)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--domains", default="human,ai")
    args = ap.parse_args()
    if "embed" in args.steps:
        dino = None
        for variant in ("raw", "uniform"):
            for domain in args.domains.split(","):
                dino = embed(domain, dino, variant)
    if "analyze" in args.steps:
        main_res = analyze(args.perm, args.boot, "cls")
        robust = analyze(min(args.perm, 1000), min(args.boot, 1000), "patch")
        uniform = analyze(min(args.perm, 1000), min(args.boot, 1000), "cls", "uniform")
        short = lambda res: {"summary": res["summary"],  # noqa: E731
                             "share": {c: {"ai": res["ai"][c]["share"], "human": res["human"][c]["share"]}
                                       for c in CONCEPTS},
                             "between": {c: {"ai": res["ai"][c]["between"], "human": res["human"][c]["between"]}
                                         for c in CONCEPTS},
                             "heatmap": res["heatmap"]}
        prompts = json.loads((OUT / "prompts.json").read_text())
        results = {
            "experiment": "Plato's chair across languages and countries",
            "date": time.strftime("%Y-%m-%d"),
            "models": {"drawings": "Muse Image 1.0 (muse-image-1.0)", "translation": "Muse Spark 1.3",
                       "embeddings": f"{DINO} (Apache-2.0), CLS token, L2-normalized"},
            "human_data": QD_CREDIT,
            "concepts": CONCEPTS, "languages": LANGS, "countries": COUNTRIES, "language_country": LANG_COUNTRY,
            "n": {"ai_per_language": AI_N, "human_per_country": HUMAN_N},
            "prompts": {lg: {c: v["prompt"] for c, v in items.items()} for lg, items in prompts.items()},
            "words": {lg: {c: v["word"] for c, v in items.items()} for lg, items in prompts.items()},
            "measures": {
                "spread": "mean cosine distance between two doodles of the same group",
                "share": "between-group variance / total variance (unbiased U-statistics; ~0 if the group "
                         "doesn't matter); 95% bootstrap CI; p from shuffling group labels",
                "centroid": "cosine distance between two groups' average embeddings; null = label shuffling",
                "between": "mean cross-group distance minus mean within-group spread (half the squared "
                           "distance between true group means; ~0 if groups don't differ)",
            },
            **main_res,
            "robustness_patch_mean": short(robust),
            "style_control_uniform_lines": {
                "about": "Every doodle (AI and human) binarized, strokes merged across gaps up to 4 px, thinned "
                         "to a skeleton and redrawn 3 px wide, then re-embedded: removes line weight and "
                         "sketchiness, keeps the form (heavily sketched doodles get some artifacts)",
                **short(uniform)},
        }
        (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1))
        print(json.dumps(results["summary"], indent=1))
        print(json.dumps(results["alignment"], indent=1))
        print(f"wrote {OUT / 'results.json'}")


if __name__ == "__main__":
    main()

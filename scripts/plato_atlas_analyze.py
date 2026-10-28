"""The Atlas of Forms, step 4: spread ratios for 135 concepts, the pre-registered tests and the predictors.

Usage: python -I scripts/plato_atlas_analyze.py pixels [--workers 6]   (Form averages and pixel spreads)
       python -I scripts/plato_atlas_analyze.py stats                  (everything else)

pixels  For each concept, ink-crops the pictures exactly as for the embeddings and writes
        - the pixel-average Forms of 12 pictures: Muse's first 12, people's seeded random 12 of 200,
          SDXL's first 12 ($PLATO_ATLAS_DIR/forms/<key>_{muse,people,sdxl}.png, 256 px), and the 12
          ink-cropped pictures of each as a strip for the page (<key>_{muse,people}_tiles.png);
        - the model-free pixel spread of Muse's analysis set, SDXL's set and all 200 people
          ($PLATO_ATLAS_DIR/pixels.json).
stats   DINOv2 spread and the Muse/human ratio (plato_atlas.spread_ratio) for every concept, SDXL's
        ratio, Muse vs SDXL, patch-mean and pixel robustness checks, recognizability among the 135,
        the confirmatory tests H1-H2 on the 98 new concepts, the atlas ranking, and the exploratory
        predictors P1-P4 -> $PLATO_ATLAS_DIR/results.json and public_data/plato_atlas.json.
Core and forms data are only read. Plan: docs/plato_atlas_plan.md.
"""
import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab import plato_atlas as A  # noqa: E402
from metalesionlab.plato import (DINO_MODEL, QUICKDRAW_CREDIT, ci, cosine_distances, load_dir,  # noqa: E402
                                 spearman_ci, spread, to_jsonable)

REPO = Path(__file__).resolve().parents[1]
FORMS_OUT = A.ATLAS_DIR / "forms"
PIXELS = A.ATLAS_DIR / "pixels.json"
RESULTS = A.ATLAS_DIR / "results.json"
PUBLIC = REPO / "public_data" / "plato_atlas.json"
N_FORM = 12
SDXL_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"


# ---------- pixels: Forms and the model-free spread ----------

def people_sample(n_pool: int, idx: int, k: int = N_FORM) -> list[int]:
    """The seeded random 12 of people's 200 drawings shown on the page for concept number idx."""
    rng = np.random.default_rng(A.SEED + idx)
    return sorted(int(i) for i in rng.choice(n_pool, k, replace=False))


def tile_strip(grays: list[np.ndarray], side: int = 128) -> Image.Image:
    """The pictures side by side in one row (each side x side px), for the page's thumbnails."""
    strip = Image.new("L", (side * len(grays), side), 255)
    for i, g in enumerate(grays):
        strip.paste(Image.fromarray(g.astype(np.uint8)).resize((side, side), Image.LANCZOS), (i * side, 0))
    return strip


def pixels_for(idx: int) -> tuple[str, dict]:
    c = A.CONCEPTS[idx]
    f = A.folders(c)
    muse = load_dir(f["ai_doodle"])[:c.n_ai]
    sdxl = load_dir(f["ai_sdxl_doodle"])
    people = load_dir(f["human"])
    out = {"n_muse": len(muse), "n_sdxl": len(sdxl), "n_people": len(people)}
    if len(muse) < 2 or len(people) < N_FORM:
        return c.key, out
    g_muse = [A.ink_gray(p) for p in muse]
    g_people = [A.ink_gray(p) for p in people]
    g_sdxl = [A.ink_gray(p) for p in sdxl]
    out["pixel_spread"] = {"muse": A.pixel_spread(g_muse), "people": A.pixel_spread(g_people),
                           "sdxl": A.pixel_spread(g_sdxl) if len(g_sdxl) > 1 else None}
    pick = people_sample(len(people), idx)
    out["people_sample"] = [people[i].name for i in pick]
    FORMS_OUT.mkdir(parents=True, exist_ok=True)
    sets = {"muse": g_muse[:N_FORM], "people": [g_people[i] for i in pick], "sdxl": g_sdxl[:N_FORM]}
    for name, grays in sets.items():
        if grays:
            Image.fromarray(A.form_average(grays)).save(FORMS_OUT / f"{c.key}_{name}.png")
            tile_strip(grays).save(FORMS_OUT / f"{c.key}_{name}_tiles.png")
    out["form_n"] = {k: len(v) for k, v in sets.items()}
    return c.key, out


def cmd_pixels(args):
    done = json.loads(PIXELS.read_text()) if PIXELS.exists() else {}
    todo = [i for i, c in enumerate(A.CONCEPTS) if (args.redo or "pixel_spread" not in done.get(c.key, {}))
            and (not args.keys or c.key in args.keys) and (not args.origin or c.origin == args.origin)]
    with ProcessPoolExecutor(args.workers) as pool:
        for key, out in pool.map(pixels_for, todo):
            done[key] = out
            ps = out.get("pixel_spread", {})
            print(f"{key:16s} muse {out['n_muse']:2d} sdxl {out['n_sdxl']:2d} people {out['n_people']:3d}  "
                  f"pixel spread muse {ps.get('muse', float('nan')):.3f} people {ps.get('people', float('nan')):.3f}",
                  flush=True)
            PIXELS.write_text(json.dumps(to_jsonable(done), indent=1))
    print(f"wrote {PIXELS}")


# ---------- stats ----------

def load(c: A.AtlasConcept, source: str, emb: str = "cls", n: int | None = None):
    path = A.embedding_path(c, source)
    if not path.exists():
        return None
    z = np.load(path)
    return z[emb][:n] if n else z[emb]


def unit_mean(x: np.ndarray) -> np.ndarray:
    return (x / np.linalg.norm(x, axis=1, keepdims=True)).mean(0)


def zipf(c: A.AtlasConcept) -> float:
    from wordfreq import zipf_frequency

    return float(zipf_frequency(c.quickdraw.replace("-", " ").replace("_", " "), "en"))


def summarize(rows: list[dict], key: str = "ratio", boot_key: str = "_ratio_boot", rng=None) -> dict:
    if not rows:
        return {"n": 0}
    vals = np.array([r[key] for r in rows])
    below = int((vals < 1).sum())
    out = {"n": len(rows), "median": float(np.median(vals)), "mean": float(vals.mean()),
           "below_1": below, "share_below_1": below / len(rows), "share_below_1_ci95": A.wilson_ci(below, len(rows))}
    if boot_key and rows and boot_key in rows[0]:
        out["median_ci95"] = A.median_ci([r[boot_key] for r in rows], rng=rng)
        out["ci_entirely_below_1"] = int(sum(r[f"{key}_ci95"][1] < 1 for r in rows))
        out["ci_entirely_above_1"] = int(sum(r[f"{key}_ci95"][0] > 1 for r in rows))
    return out


def boot_diff(x: np.ndarray, y: np.ndarray, reps: int, rng) -> dict:
    """Difference in means x - y with a bootstrap CI (resampling within groups) and a permutation p."""
    d = float(x.mean() - y.mean())
    boots = np.array([rng.choice(x, len(x)).mean() - rng.choice(y, len(y)).mean() for _ in range(reps)])
    pooled = np.concatenate([x, y])
    perm = []
    for _ in range(reps):
        p = rng.permutation(pooled)
        perm.append(p[:len(x)].mean() - p[len(x):].mean())
    return {"diff": d, "ci95": ci(boots), "p_perm": float((np.abs(perm) >= abs(d) - 1e-12).mean()),
            "n": [len(x), len(y)]}


def ols_boot(y: np.ndarray, X: np.ndarray, names: list[str], reps: int, rng) -> dict:
    """OLS with an intercept; bootstrap CIs over concepts for each coefficient."""
    Xd = np.column_stack([np.ones(len(y)), X])
    beta = np.linalg.lstsq(Xd, y, rcond=None)[0]
    resid = y - Xd @ beta
    r2 = 1 - resid.var() / y.var()
    boots = []
    for _ in range(reps):
        i = rng.integers(0, len(y), len(y))
        boots.append(np.linalg.lstsq(Xd[i], y[i], rcond=None)[0])
    boots = np.array(boots)
    return {"n": len(y), "r2": float(r2),
            "coefficients": {n: {"b": float(beta[j + 1]), "ci95": ci(boots[:, j + 1])} for j, n in enumerate(names)},
            "intercept": float(beta[0])}


def cmd_stats(args):
    rng = np.random.default_rng(A.SEED)
    pix = json.loads(PIXELS.read_text()) if PIXELS.exists() else {}
    rows, muse_all, hum_all, skipped = [], {}, {}, []
    for c in A.CONCEPTS:
        a = load(c, "ai_doodle", n=c.n_ai)
        h = load(c, "human")
        if a is None or h is None or len(a) < 8:
            skipped.append({"key": c.key, "n_ai": 0 if a is None else len(a), "n_human": 0 if h is None else len(h)})
            print(f"skip {c.key}: {skipped[-1]}")
            continue
        s = A.spread_ratio(a, h, rng=rng)
        row = {"key": c.key, "label": c.label, "quickdraw": c.quickdraw, "domain": c.domain, "natural": c.natural,
               "origin": c.origin, "n_ai": len(a), "n_human_pool": len(h), "zipf": zipf(c),
               "muse_spread": s["spread"], "muse_spread_ci95": s["spread_ci95"],
               "human_spread": s["human_spread"], "human_spread_ci95": s["human_spread_ci95"],
               "human_spread_range95_for_n": s["human_spread_range95_for_n"],
               "human_spread_all": spread(cosine_distances(h)),
               "ratio": s["ratio"], "ratio_ci95": s["ratio_ci95"],
               "share_of_human_sets_as_uniform": s["share_of_human_sets_as_uniform"],
               "_ratio_boot": s["_ratio_boot"], "_ai_boot": s["_ai_boot"]}
        # SDXL against the same people, and Muse against SDXL
        sx = load(c, "ai_sdxl_doodle")
        if sx is not None and len(sx) >= 8:
            t = A.spread_ratio(sx, h, rng=rng)
            row.update({"n_sdxl": len(sx), "sdxl_spread": t["spread"], "sdxl_spread_ci95": t["spread_ci95"],
                        "sdxl_ratio": t["ratio"], "sdxl_ratio_ci95": t["ratio_ci95"],
                        "_sdxl_ratio_boot": t["_ratio_boot"],
                        "muse_over_sdxl": s["spread"] / t["spread"],
                        "muse_over_sdxl_ci95": ci(s["_ai_boot"] / t["_ai_boot"]),
                        "muse_minus_sdxl_ci95": ci(s["_ai_boot"] - t["_ai_boot"])})
        # robustness: patch-mean embeddings and the model-free pixel spread
        a2, h2 = load(c, "ai_doodle", "patch_mean", c.n_ai), load(c, "human", "patch_mean")
        p = A.spread_ratio(a2, h2, rng=rng, reps_ai=200, reps_human=100, subsets=100)
        row["patch_mean"] = {"muse_spread": p["spread"], "human_spread": p["human_spread"], "ratio": p["ratio"]}
        ps = pix.get(c.key, {}).get("pixel_spread")
        if ps:
            row["pixel"] = {"muse_spread": ps["muse"], "people_spread": ps["people"], "ratio": ps["muse"] / ps["people"],
                            "sdxl_ratio": ps["sdxl"] / ps["people"] if ps.get("sdxl") else None}
        rows.append(row)
        muse_all[c.key], hum_all[c.key] = a, h
        print(f"{c.key:16s} {c.origin:5s} ratio {row['ratio']:.2f} [{row['ratio_ci95'][0]:.2f}, "
              f"{row['ratio_ci95'][1]:.2f}]  sdxl {row.get('sdxl_ratio', float('nan')):.2f}", flush=True)

    keys = [r["key"] for r in rows]
    # recognizability: does each Muse doodle sit nearest its own concept's human centroid, among all 135?
    hmus = np.stack([unit_mean(hum_all[k]) for k in keys])
    for r in rows:
        a = muse_all[r["key"]]
        nearest = np.argmax((a / np.linalg.norm(a, axis=1, keepdims=True)) @ hmus.T, axis=1)
        r["muse_nearest_human_centroid_is_own"] = float(np.mean(np.array(keys)[nearest] == r["key"]))
    # ranks: 1 = most Platonic (lowest ratio)
    for rank, r in enumerate(sorted(rows, key=lambda r: r["ratio"]), 1):
        r["rank"] = rank

    new = [r for r in rows if r["origin"] == "new"]
    core = [r for r in rows if r["origin"] == "core"]
    with_sdxl = [r for r in rows if "sdxl_ratio" in r]
    new_sdxl = [r for r in new if "sdxl_ratio" in r]
    h1 = summarize(new, rng=rng)
    confirm = {
        "H1_median_below_1": {"median": h1["median"], "ci95": h1["median_ci95"],
                              "confirmed": bool(h1["median_ci95"][1] < 1)},
        "H2_most_below_1": {"below_1": h1["below_1"], "n": h1["n"], "share": h1["share_below_1"],
                            "wilson_ci95": h1["share_below_1_ci95"],
                            "confirmed": bool(h1["share_below_1_ci95"][0] > 0.5)},
        "expected_size": {"median_in_0.40_0.60": bool(0.40 <= h1["median"] <= 0.60),
                          "share_below_1_at_least_0.85": bool(h1["share_below_1"] >= 0.85)},
    }
    pm = lambda rs: summarize([{"ratio": r["patch_mean"]["ratio"]} for r in rs], boot_key=None)  # noqa: E731
    px = lambda rs: summarize([{"ratio": r["pixel"]["ratio"]} for r in rs if "pixel" in r], boot_key=None)  # noqa: E731
    sd = lambda rs: summarize(rs, "sdxl_ratio", "_sdxl_ratio_boot", rng=rng)  # noqa: E731

    def muse_vs_sdxl(rs):
        if not rs:
            return {"n": 0}
        return {"n": len(rs), "muse_more_uniform": int(sum(r["muse_over_sdxl"] < 1 for r in rs)),
                "ci_excludes_zero": int(sum(r["muse_minus_sdxl_ci95"][1] < 0 for r in rs)),
                "median_muse_over_sdxl": float(np.median([r["muse_over_sdxl"] for r in rs])),
                "exceptions": [r["label"] for r in rs if r["muse_over_sdxl"] >= 1]}

    # exploratory predictors, all concepts
    col = lambda name, rs=rows: np.array([r[name] for r in rs], float)  # noqa: E731
    log_ratio = np.log(col("ratio"))
    nat = np.array([r["natural"] for r in rows])
    predictors = {
        "note": "EXPLORATORY (pre-registered as such): bootstrap 95% CIs over concepts (5,000) and permutation p; "
                "no correction for multiple tests.",
        "P1_muse_spread_vs_human_spread": spearman_ci(col("muse_spread"), col("human_spread"), rng=rng),
        "P1_ratio_vs_human_spread": spearman_ci(col("ratio"), col("human_spread"), rng=rng),
        "P1_note": "The ratio's denominator is people's spread, so its correlation with people's spread is partly "
                   "mechanical; the Muse-spread correlation is the informative one.",
        "P2_ratio_vs_zipf": spearman_ci(col("ratio"), col("zipf"), rng=rng),
        "P2_muse_spread_vs_zipf": spearman_ci(col("muse_spread"), col("zipf"), rng=rng),
        "P2_human_spread_vs_zipf": spearman_ci(col("human_spread"), col("zipf"), rng=rng),
        "P3_natural_minus_artifact_log_ratio": boot_diff(log_ratio[nat], log_ratio[~nat], 5000, rng),
        "P3_median_ratio": {"natural": float(np.median(col("ratio")[nat])),
                            "artifact": float(np.median(col("ratio")[~nat])),
                            "n_natural": int(nat.sum()), "n_artifact": int((~nat).sum())},
        "P4_ols_log_muse_spread": ols_boot(np.log(col("muse_spread")),
                                           np.column_stack([np.log(col("human_spread")), col("zipf"),
                                                            nat.astype(float)]),
                                           ["log_human_spread", "zipf", "natural"], 5000, rng),
        "sdxl_spread_vs_human_spread": spearman_ci(col("sdxl_spread", with_sdxl), col("human_spread", with_sdxl),
                                                   rng=rng),
        "muse_spread_vs_sdxl_spread": spearman_ci(col("muse_spread", with_sdxl), col("sdxl_spread", with_sdxl),
                                                  rng=rng),
    }
    domains = {}
    for d in A.DOMAINS:
        rs = [r for r in rows if r["domain"] == d]
        if rs:
            domains[d] = {"n": len(rs), "median_ratio": float(np.median([r["ratio"] for r in rs])),
                          "mean_ratio": float(np.mean([r["ratio"] for r in rs])),
                          "below_1": int(sum(r["ratio"] < 1 for r in rs)),
                          "most_platonic": min(rs, key=lambda r: r["ratio"])["label"],
                          "least_platonic": max(rs, key=lambda r: r["ratio"])["label"]}
    ranked = sorted(rows, key=lambda r: r["ratio"])
    summary = {
        "n_concepts": len(rows), "n_new": len(new), "skipped": skipped,
        "confirmatory_new_98": confirm,
        "new": h1, "all": summarize(rows, rng=rng), "core": summarize(core, rng=rng),
        "sdxl": {"new": sd(new_sdxl), "all": sd(with_sdxl)},
        "muse_vs_sdxl": {"new": muse_vs_sdxl(new_sdxl), "all": muse_vs_sdxl(with_sdxl)},
        "robustness": {"patch_mean": {"new": pm(new), "all": pm(rows)},
                       "pixel": {"new": px(new), "all": px(rows)},
                       "pixel_vs_dino_ratio": spearman_ci([r["pixel"]["ratio"] for r in rows if "pixel" in r],
                                                          [r["ratio"] for r in rows if "pixel" in r], rng=rng),
                       "cls_vs_patch_mean_ratio": spearman_ci(col("ratio"),
                                                              [r["patch_mean"]["ratio"] for r in rows], rng=rng)},
        "recognizability": {"mean_share_nearest_own": float(col("muse_nearest_human_centroid_is_own").mean()),
                            "new": float(np.mean([r["muse_nearest_human_centroid_is_own"] for r in new])),
                            "zero": [r["label"] for r in rows if r["muse_nearest_human_centroid_is_own"] == 0]},
        "most_platonic": [r["label"] for r in ranked[:10]],
        "least_platonic": [r["label"] for r in ranked[::-1][:10]],
        "above_1": [r["label"] for r in rows if r["ratio"] >= 1],
        "mean_spread": {"muse": float(col("muse_spread").mean()), "people": float(col("human_spread").mean()),
                        "sdxl": float(col("sdxl_spread", with_sdxl).mean())},
        "predictors": predictors, "domains": domains,
    }
    results = {
        "experiment": "The Atlas of Forms: Plato's Chair for 135 everyday things",
        "plan": "docs/plato_atlas_plan.md", "embedding_model": DINO_MODEL,
        "embedding": "CLS token, cosine distance, ink-cropped; patch mean and a pixel spread as robustness checks",
        "image_model": "muse-image-1.0", "comparison_model": SDXL_MODEL, "human_data": QUICKDRAW_CREDIT,
        "summary": summary, "concepts": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
    }
    RESULTS.write_text(json.dumps(to_jsonable(results), indent=1, ensure_ascii=False))
    print(f"wrote {RESULTS}")

    keep = ("rank", "label", "quickdraw", "domain", "natural", "origin", "n_ai", "zipf", "muse_spread",
            "muse_spread_ci95", "human_spread", "human_spread_ci95", "human_spread_all", "ratio", "ratio_ci95",
            "n_sdxl", "sdxl_spread", "sdxl_spread_ci95", "sdxl_ratio", "sdxl_ratio_ci95", "muse_over_sdxl",
            "muse_over_sdxl_ci95", "patch_mean", "pixel", "muse_nearest_human_centroid_is_own")
    public = {
        "about": "The Atlas of Forms: how uniformly Meta's Muse Image (and Stable Diffusion XL) draws 135 everyday "
                 "things, against people's drawings from Google Quick, Draw!, measured with Meta DINOv2. Derived "
                 "statistics only: no drawings and no embeddings. ratio = model spread / people's spread "
                 "(below 1 = more uniform than people); rank 1 = most Platonic. Muse's numbers are its defaults "
                 "for one doodle prompt; asked for variety, Muse can draw more varied pictures (docs/plato.md).",
        "attribution": QUICKDRAW_CREDIT,
        "models": {"muse": "muse-image-1.0 (Meta)", "sdxl": f"{SDXL_MODEL} (CreativeML OpenRAIL++-M)",
                   "embedding": f"{DINO_MODEL} (Meta, Apache-2.0)"},
        "prompt": A.prompt_for(A.BY_KEY["chair"]).replace("a chair", "{phrase}"),
        "spread": "mean pairwise cosine distance between DINOv2 CLS embeddings of ink-cropped pictures",
        "human_reference": f"the first {A.N_HUMAN} drawings with recognized=true in each Quick, Draw! simplified "
                           "file, rendered at 256 px; human_spread is the mean over 200 random subsets of the "
                           "model's n; human_spread_all is the spread of all 200 (independent of n)",
        "plan": "docs/plato_atlas_plan.md", "benchmark": "scripts/plato_benchmark.py",
        "summary": {k: summary[k] for k in ("n_concepts", "n_new", "confirmatory_new_98", "new", "all", "core",
                                            "sdxl", "muse_vs_sdxl", "robustness", "recognizability", "most_platonic",
                                            "least_platonic", "above_1", "mean_spread", "predictors", "domains")},
        "concepts": [{k: r[k] for k in keep if k in r} for r in sorted(rows, key=lambda r: r["rank"])],
    }
    args.public.write_text(json.dumps(to_jsonable(public), indent=1, ensure_ascii=False))
    print(f"wrote {args.public}")
    print(json.dumps(to_jsonable({k: summary[k] for k in ("confirmatory_new_98", "new", "all", "core")}), indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pixels")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--redo", action="store_true")
    p.add_argument("--keys", nargs="*")
    p.add_argument("--origin", choices=["core", "forms", "new"])
    s = sub.add_parser("stats")
    s.add_argument("--public", type=Path, default=PUBLIC)
    args = ap.parse_args()
    {"pixels": cmd_pixels, "stats": cmd_stats}[args.cmd](args)


if __name__ == "__main__":
    main()

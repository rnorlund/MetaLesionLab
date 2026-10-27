"""Plato's Chair: is it just Muse? The same 35 concepts drawn by Stable Diffusion XL.

Usage: python -I scripts/plato_sdxl_analyze.py   (after plato_sdxl_generate.py and plato_embed.py)

Reads the cached DINOv2 embeddings (ai_doodle = Muse Image, ai_sdxl_doodle = SDXL, human = Quick, Draw!)
and writes $PLATO_DIR/results_sdxl.json. The statistics are the core ones (plato_analyze.concept_stats):
- SDXL spread: its 16 pictures, bootstrap 95% CI over pictures;
- SDXL/human ratio: human drawings subsampled to 16, CI from independent bootstraps of both;
- Muse vs SDXL: difference and ratio of spreads, CIs from independent bootstraps of the two picture sets
  (Muse has 16 pictures for tier 1 and 12 for tier 2; mean pairwise distance does not depend on n);
- relative spread (within / between-concept distance in the same source) and recognisability;
- style measures per picture, on what DINOv2 sees: ink coverage, mid-gray share of the raw picture, and
  "full bleed" (ink reaching all four edges: a frame, a scene or a background), plus the spread of the
  pictures that are not full bleed, as a partial style control.
Across concepts: rank correlations of SDXL spread with human and Muse spread (and a partial one).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402
from plato_analyze import B_AI, SUBSETS, concept_stats, load  # noqa: E402
from scipy.stats import rankdata  # noqa: E402

from metalesionlab.plato import (CONCEPTS, DINO_MODEL, PLATO_DIR, QUICKDRAW_CREDIT, bootstrap_spread, ci,  # noqa: E402
                                 cosine_distances, flatten_paper, ink_crop, load_dir, spearman_ci, spread,
                                 subsample_spread, to_jsonable)

SDXL = "stabilityai/stable-diffusion-xl-base-1.0"
SDXL_CREDIT = "SDXL: Stable Diffusion XL base 1.0 (Stability AI), CreativeML OpenRAIL++-M license"
FOCUS = ["umbrella", "bicycle", "chair", "book", "sailboat", "face", "yoga"]
MIN_CLEAN = 6  # concepts need this many non-full-bleed pictures for the style-controlled spread


def style(path: Path) -> dict:
    """Ink coverage of the ink-cropped picture, mid-gray share of the raw one, and full bleed."""
    img = Image.open(path).convert("RGB")
    raw = np.asarray(img.convert("L"), dtype=np.float32)
    flat = flatten_paper(img.convert("L"))
    mask = flat.filter(ImageFilter.MaxFilter(3)).point(lambda v: 255 if v < 200 else 0)
    box = mask.getbbox()
    w, h = flat.size
    bleed = bool(box) and (box[2] - box[0]) >= 0.95 * w and (box[3] - box[1]) >= 0.95 * h
    cropped = np.asarray(ink_crop(img).convert("L"))
    hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255
    color = float(((hsv[..., 1] > 0.3) & (hsv[..., 2] > 0.2)).mean()) > 0.01  # >1% clearly colored pixels
    return {"ink": float((cropped < 200).mean()), "midgray": float(((raw >= 60) & (raw <= 200)).mean()),
            "bleed": bleed, "color": color}


def style_rows(folder: Path, n: int | None = None) -> list[dict]:
    return [style(f) for f in load_dir(folder, n)]


def partial_spearman(x, y, z) -> float:
    """Rank correlation of x and y with z partialled out (Pearson partial on ranks)."""
    rx, ry, rz = (rankdata(v) for v in (x, y, z))
    r = np.corrcoef([rx, ry, rz])
    return float((r[0, 1] - r[0, 2] * r[1, 2]) / np.sqrt((1 - r[0, 2] ** 2) * (1 - r[1, 2] ** 2)))


def partial_spearman_ci(x, y, z, reps: int = 5000, rng=None) -> dict:
    rng = rng or np.random.default_rng(0)
    x, y, z = (np.asarray(v, float) for v in (x, y, z))
    n = len(x)
    rho = partial_spearman(x, y, z)
    with np.errstate(invalid="ignore", divide="ignore"):  # a degenerate resample gives NaN; it is dropped
        boots = np.array([partial_spearman(x[i], y[i], z[i]) for i in (rng.integers(0, n, n) for _ in range(reps))])
    perm = np.array([partial_spearman(x, rng.permutation(y), z) for _ in range(reps)])
    return {"rho": rho, "ci95": ci(boots[np.isfinite(boots)]),
            "p_perm": float((np.abs(perm) >= abs(rho) - 1e-12).mean()), "n": n}


def between(sets: dict[str, np.ndarray], keys: list[str]) -> dict[str, float]:
    """Mean cosine distance from a concept's pictures to every other concept's pictures (= 1 - mu_c . mu_d)."""
    mus = {k: (v / np.linalg.norm(v, axis=1, keepdims=True)).mean(0) for k, v in sets.items()}
    return {k: float(np.mean([1 - mus[k] @ mus[o] for o in keys if o != k])) for k in keys}


def nearest_own(src: dict[str, np.ndarray], ref: dict[str, np.ndarray], keys: list[str]) -> dict[str, float]:
    mus = np.stack([(ref[k] / np.linalg.norm(ref[k], axis=1, keepdims=True)).mean(0) for k in keys])
    out = {}
    for k in keys:
        a = src[k] / np.linalg.norm(src[k], axis=1, keepdims=True)
        out[k] = float(np.mean(np.array(keys)[np.argmax(a @ mus.T, axis=1)] == k))
    return out


def main():
    rng = np.random.default_rng(20261027)
    muse_results = {r["key"]: r for r in json.loads((PLATO_DIR / "results.json").read_text())["concepts"]}
    rows, keys = [], []
    muse_all, sdxl_all, hu_all = {}, {}, {}
    boots = {}
    for c in CONCEPTS:
        s, files = load("ai_sdxl_doodle", c.key)
        m, _ = load("ai_doodle", c.key, c.n_ai)
        h, _ = load("human", c.key)
        if s is None or m is None or h is None or len(s) < 16:
            print(f"skip {c.key}: SDXL {0 if s is None else len(s)}/16")
            continue
        keys.append(c.key)
        muse_all[c.key], sdxl_all[c.key], hu_all[c.key] = m, s, h
        st = concept_stats(s, h, len(s), rng)  # SDXL vs people, exactly as Muse vs people in the core run
        muse_boot = bootstrap_spread(cosine_distances(m), B_AI, rng)
        muse = spread(cosine_distances(m))
        mr = muse_results.get(c.key, {})
        s2, _ = load("ai_sdxl_doodle", c.key, None, "patch_mean")
        h2, _ = load("human", c.key, None, "patch_mean")
        sd2 = spread(cosine_distances(s2))
        hu2 = float(subsample_spread(cosine_distances(h2), len(s2), SUBSETS, rng).mean())
        boots[c.key] = (st["_ai_boot"], muse_boot)
        rows.append({
            "key": c.key, "label": c.label, "quickdraw": c.quickdraw, "tier": c.tier, "kind": c.kind,
            "n_sdxl": len(s), "n_muse": len(m), "n_human_pool": len(h),
            "sdxl_spread": st["ai_spread"], "sdxl_spread_ci95": st["ai_spread_ci95"],
            "sdxl_spread_first_n_muse": spread(cosine_distances(s[:c.n_ai])),
            "human_spread": st["human_spread"], "human_spread_ci95": st["human_spread_ci95"],
            "human_spread_range95_for_n": st["human_spread_range95_for_n"],
            "sdxl_index": st["homogenization_index"], "sdxl_index_ci95": st["homogenization_index_ci95"],
            "share_of_human_sets_as_uniform_as_sdxl": st["share_of_human_sets_as_uniform_as_ai"],
            "muse_spread": muse, "muse_spread_ci95": ci(muse_boot),
            "muse_index": mr.get("homogenization_index"), "muse_index_ci95": mr.get("homogenization_index_ci95"),
            "sdxl_minus_muse": st["ai_spread"] - muse, "sdxl_minus_muse_ci95": ci(st["_ai_boot"] - muse_boot),
            "muse_over_sdxl": muse / st["ai_spread"], "muse_over_sdxl_ci95": ci(muse_boot / st["_ai_boot"]),
            "patch_mean": {"sdxl_spread": sd2, "human_spread": hu2, "sdxl_index": sd2 / hu2,
                           "muse_spread": mr.get("patch_mean", {}).get("ai_spread")},
            "sdxl_seeds": json.loads((PLATO_DIR / "ai" / "sdxl_doodle" / c.key / "meta.json").read_text())
                              .get("seeds", {}),
            "_sdxl_files": files,
        })
    if not rows:
        sys.exit("no SDXL concepts embedded yet")
    by = {r["key"]: r for r in rows}

    # between-concept baselines, relative spread and recognisability, per source
    b_s, b_m, b_h = between(sdxl_all, keys), between(muse_all, keys), between(hu_all, keys)
    near_s, near_m = nearest_own(sdxl_all, hu_all, keys), nearest_own(muse_all, hu_all, keys)
    for r in rows:
        k = r["key"]
        r["sdxl_between"], r["muse_between"], r["human_between"] = b_s[k], b_m[k], b_h[k]
        r["sdxl_relative_spread"] = r["sdxl_spread"] / b_s[k]
        r["muse_relative_spread"] = r["muse_spread"] / b_m[k]
        r["human_relative_spread"] = r["human_spread"] / b_h[k]
        r["sdxl_relative_index"] = r["sdxl_relative_spread"] / r["human_relative_spread"]
        r["sdxl_nearest_human_centroid_is_own"] = near_s[k]
        r["muse_nearest_human_centroid_is_own"] = near_m[k]

    # style: what kind of pictures each source makes, and spread without the full-bleed ones
    print("measuring style ...", flush=True)
    for r in rows:
        c = next(c for c in CONCEPTS if c.key == r["key"])
        st_s = style_rows(PLATO_DIR / "ai" / "sdxl_doodle" / c.key)
        st_m = style_rows(PLATO_DIR / "ai" / "doodle" / c.key, c.n_ai)
        st_h = style_rows(PLATO_DIR / "human" / c.key)
        for name, st in (("sdxl", st_s), ("muse", st_m), ("human", st_h)):
            r[f"{name}_style"] = {"ink_coverage": float(np.mean([x["ink"] for x in st])),
                                  "ink_coverage_sd": float(np.std([x["ink"] for x in st])),
                                  "midgray_share": float(np.mean([x["midgray"] for x in st])),
                                  "full_bleed_share": float(np.mean([x["bleed"] for x in st])),
                                  "color_share": float(np.mean([x["color"] for x in st]))}
        clean = np.array([not x["bleed"] for x in st_s])
        r["sdxl_clean_n"] = int(clean.sum())
        if clean.sum() >= MIN_CLEAN:
            d = cosine_distances(sdxl_all[c.key][clean])
            r["sdxl_clean_spread"] = spread(d)
            r["sdxl_clean_index"] = spread(d) / r["human_spread"]

    col = lambda name, rs=rows: np.array([r[name] for r in rs], dtype=float)  # noqa: E731
    sx, mu, hu = col("sdxl_spread"), col("muse_spread"), col("human_spread")
    diff_lo = np.array([r["sdxl_minus_muse_ci95"][0] for r in rows])
    diff_hi = np.array([r["sdxl_minus_muse_ci95"][1] for r in rows])
    rank_s = {r["key"]: int(i) for i, r in zip(rankdata(sx, method="ordinal"), rows)}
    rank_m = {r["key"]: int(i) for i, r in zip(rankdata(mu, method="ordinal"), rows)}
    clean_rows = [r for r in rows if "sdxl_clean_spread" in r]
    style_mean = {src: {f: float(np.mean([r[f"{src}_style"][f] for r in rows]))
                        for f in ("ink_coverage", "ink_coverage_sd", "midgray_share", "full_bleed_share",
                                  "color_share")}
                  for src in ("muse", "sdxl", "human")}
    top = lambda name, sign=1, rs=rows: [r["label"] for r in sorted(rs, key=lambda r: sign * r[name])[:6]]  # noqa: E731
    summary = {
        "n_concepts": len(rows),
        "sdxl_vs_human": {
            "median_index": float(np.median(col("sdxl_index"))),
            "concepts_with_index_below_1": int((col("sdxl_index") < 1).sum()),
            "concepts_with_index_ci_below_1": int(sum(r["sdxl_index_ci95"][1] < 1 for r in rows)),
            "concepts_with_index_ci_above_1": int(sum(r["sdxl_index_ci95"][0] > 1 for r in rows)),
            "concepts_sdxl_below_every_human_subset": int(sum(r["share_of_human_sets_as_uniform_as_sdxl"] == 0
                                                              for r in rows)),
            "median_relative_index": float(np.median(col("sdxl_relative_index"))),
            "concepts_with_relative_index_below_1": int((col("sdxl_relative_index") < 1).sum()),
            "concepts_with_index_below_1_patch_mean": int(sum(r["patch_mean"]["sdxl_index"] < 1 for r in rows)),
            "median_index_patch_mean": float(np.median([r["patch_mean"]["sdxl_index"] for r in rows])),
            "concepts_with_index_above_1": [r["label"] for r in rows if r["sdxl_index"] >= 1],
        },
        "muse_vs_sdxl": {
            "concepts_muse_more_uniform": int((mu < sx).sum()),
            "concepts_muse_more_uniform_ci": int((diff_lo > 0).sum()),
            "concepts_sdxl_more_uniform_ci": int((diff_hi < 0).sum()),
            "concepts_sdxl_more_uniform": [r["label"] for r in rows if r["sdxl_spread"] < r["muse_spread"]],
            "median_muse_over_sdxl": float(np.median(col("muse_over_sdxl"))),
            "mean_spread": {"muse": float(mu.mean()), "sdxl": float(sx.mean()), "human": float(hu.mean())},
            "baseline_between_concepts": {"muse": float(col("muse_between").mean()),
                                          "sdxl": float(col("sdxl_between").mean()),
                                          "human": float(col("human_between").mean())},
            "median_relative_spread": {"muse": float(np.median(col("muse_relative_spread"))),
                                       "sdxl": float(np.median(col("sdxl_relative_spread"))),
                                       "human": float(np.median(col("human_relative_spread")))},
        },
        "rank_correlation_sdxl_vs_human_spread": spearman_ci(sx, hu, rng=rng),
        "rank_correlation_sdxl_vs_muse_spread": spearman_ci(sx, mu, rng=rng),
        "rank_correlation_muse_vs_human_spread": spearman_ci(mu, hu, rng=rng),
        "partial_rank_correlation_sdxl_vs_muse_given_human": partial_spearman_ci(sx, mu, hu, rng=rng),
        "rank_correlation_sdxl_vs_muse_index": spearman_ci(col("sdxl_index"), [r["muse_index"] for r in rows],
                                                           rng=rng),
        "rank_correlation_sdxl_vs_human_relative_spread": spearman_ci(col("sdxl_relative_spread"),
                                                                      col("human_relative_spread"), rng=rng),
        "rank_correlation_sdxl_vs_human_patch_mean": spearman_ci([r["patch_mean"]["sdxl_spread"] for r in rows],
                                                                 [r["patch_mean"]["human_spread"] for r in rows],
                                                                 rng=rng),
        "rank_correlation_sdxl_vs_muse_patch_mean": spearman_ci([r["patch_mean"]["sdxl_spread"] for r in rows],
                                                                [r["patch_mean"]["muse_spread"] for r in rows],
                                                                rng=rng),
        "sdxl_16_vs_first_n_muse_spread": spearman_ci(sx, col("sdxl_spread_first_n_muse"), rng=rng),
        "most_uniform_sdxl": top("sdxl_spread"), "most_varied_sdxl": top("sdxl_spread", -1),
        "most_uniform_muse": top("muse_spread"), "most_varied_muse": top("muse_spread", -1),
        "most_homogenized_sdxl": top("sdxl_index"), "least_homogenized_sdxl": top("sdxl_index", -1),
        "focus": {k: {"muse_spread": by[k]["muse_spread"], "muse_spread_ci95": by[k]["muse_spread_ci95"],
                      "sdxl_spread": by[k]["sdxl_spread"], "sdxl_spread_ci95": by[k]["sdxl_spread_ci95"],
                      "human_spread": by[k]["human_spread"],
                      "muse_index": by[k]["muse_index"], "muse_index_ci95": by[k]["muse_index_ci95"],
                      "sdxl_index": by[k]["sdxl_index"], "sdxl_index_ci95": by[k]["sdxl_index_ci95"],
                      "muse_over_sdxl": by[k]["muse_over_sdxl"], "muse_over_sdxl_ci95": by[k]["muse_over_sdxl_ci95"],
                      "rank_most_uniform_muse": rank_m[k], "rank_most_uniform_sdxl": rank_s[k]}
                  for k in FOCUS if k in by},
        "style": {**style_mean,
                  "rank_correlation_sdxl_spread_vs_full_bleed_share": spearman_ci(
                      sx, [r["sdxl_style"]["full_bleed_share"] for r in rows], rng=rng),
                  "note": "ink_coverage: share of the ink-cropped 256 px picture darker than 200 (what DINOv2 "
                          "sees); midgray_share: share of the raw picture between 60 and 200 (gray paper, "
                          "shading, backgrounds); full_bleed_share: pictures whose ink reaches all four edges "
                          "(a frame, a scene or a background); color_share: pictures with more than 1% clearly "
                          "colored pixels."},
        "style_controlled": {
            "note": f"SDXL spread over its pictures that are not full bleed, for concepts with >= {MIN_CLEAN} "
                    "such pictures; human spread unchanged. A partial control: it removes frames and scenes, "
                    "not hatching or shading.",
            "n_concepts": len(clean_rows),
            "median_index": float(np.median([r["sdxl_clean_index"] for r in clean_rows])) if clean_rows else None,
            "concepts_with_index_below_1": int(sum(r["sdxl_clean_index"] < 1 for r in clean_rows)),
            "concepts_muse_more_uniform": int(sum(r["muse_spread"] < r["sdxl_clean_spread"] for r in clean_rows)),
            "rank_correlation_vs_human": (spearman_ci([r["sdxl_clean_spread"] for r in clean_rows],
                                                      [r["human_spread"] for r in clean_rows], rng=rng)
                                          if len(clean_rows) >= 8 else None),
        },
        "recognisability": {"sdxl_nearest_own_human_centroid": float(col("sdxl_nearest_human_centroid_is_own").mean()),
                            "muse_nearest_own_human_centroid": float(col("muse_nearest_human_centroid_is_own").mean()),
                            "sdxl_poorly_recognised": {r["label"]: r["sdxl_nearest_human_centroid_is_own"] for r in rows
                                                       if r["sdxl_nearest_human_centroid_is_own"] < 0.3}},
    }
    results = {
        "experiment": "Plato's Chair, is it just Muse? Stable Diffusion XL vs Muse Image vs people",
        "image_models": {"muse": "muse-image-1.0", "sdxl": SDXL},
        "sdxl_settings": {k: v for k, v in json.loads((PLATO_DIR / "ai" / "sdxl_doodle" / rows[0]["key"] /
                                                       "meta.json").read_text()).items()
                          if k in ("negative_prompt", "dtype", "steps", "size", "guidance_scale", "scheduler",
                                   "saved_side", "license")},
        "prompt": "same doodle prompt as the Muse run (metalesionlab.plato.STYLES['doodle'])",
        "embedding_model": DINO_MODEL, "embedding": "CLS token, cosine distance; patch-mean as a robustness check",
        "spread": "mean pairwise cosine distance within a concept",
        "credits": [SDXL_CREDIT, QUICKDRAW_CREDIT],
        "summary": summary,
        "concepts": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows],
    }
    out = PLATO_DIR / "results_sdxl.json"
    out.write_text(json.dumps(to_jsonable(results), indent=1, ensure_ascii=False))
    print(f"wrote {out}\n")

    print(f"{'concept':10s} {'Muse':>6s} {'SDXL [95% CI]':>20s} {'human':>6s} {'SDXL/hum [95% CI]':>20s} "
          f"{'Muse/SDXL':>10s} bleed")
    for r in sorted(rows, key=lambda r: r["sdxl_index"]):
        print(f"{r['label']:10s} {r['muse_spread']:6.3f} {r['sdxl_spread']:6.3f} [{r['sdxl_spread_ci95'][0]:.3f},"
              f"{r['sdxl_spread_ci95'][1]:.3f}] {r['human_spread']:6.3f} {r['sdxl_index']:6.2f} "
              f"[{r['sdxl_index_ci95'][0]:.2f},{r['sdxl_index_ci95'][1]:.2f}] {r['muse_over_sdxl']:10.2f} "
              f"{r['sdxl_style']['full_bleed_share']:.2f}")
    print(json.dumps(to_jsonable({k: v for k, v in summary.items() if k != "focus"}), indent=1))
    print(json.dumps(to_jsonable(summary["focus"]), indent=1))


if __name__ == "__main__":
    main()

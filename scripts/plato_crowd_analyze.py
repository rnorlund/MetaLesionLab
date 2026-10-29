"""Ask it to be a crowd, step 2: embed the persona doodles and run the tests of docs/plato_crowd_plan.md.

Usage: python -I scripts/plato_crowd_analyze.py [--device mps|cpu]

Reads $PLATO_CROWD_DIR/ai/persona/<key>/pNN_ageAA.png and the cached house embeddings (DINOv2-base CLS of the
ink-cropped first-run doodles in core/ and ideas/, and of people's 200 Quick, Draw! drawings per thing). Persona
pictures are embedded the same way and cached in $PLATO_CROWD_DIR/embeddings/ai_persona/<key>.npz. Before using the
cache it re-embeds four default chairs and checks they match (cosine >= 0.999). Writes $PLATO_CROWD_DIR/results.json.
God's labels by eye are read from $PLATO_CROWD_DIR/labels_by_eye.json when it exists. No network, no API calls.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab import plato, plato_ideas  # noqa: E402
from metalesionlab import plato_crowd as pc  # noqa: E402

OUT = pc.CROWD_DIR / "results.json"
EMB = pc.CROWD_DIR / "embeddings" / "ai_persona"


def load_npz(path: Path) -> tuple[list[str], np.ndarray, np.ndarray]:
    z = np.load(path)
    if str(z["prep"]) != pc.PREP or str(z["model"]) != plato.DINO_MODEL:
        raise SystemExit(f"{path}: made with a different model or preparation")
    return [str(f) for f in z["files"]], z["cls"].astype(np.float64), z["patch_mean"].astype(np.float64)


def check_embedder(embed: plato.Embedder) -> float:
    """Re-embed four default chairs; their CLS vectors must match the cache."""
    files, cls, _ = load_npz(plato.PLATO_DIR / "embeddings" / "ai_doodle" / "chair.npz")
    imgs = [plato.ink_crop(Image.open(plato.PLATO_DIR / "ai" / "doodle" / "chair" / f).convert("RGB")) for f in files[:4]]
    got = embed(imgs)["cls"]
    cos = float((pc.unit(got) * pc.unit(cls[:4])).sum(1).min())
    if cos < 0.999:
        raise SystemExit(f"re-embedded default chairs differ from the cache (min cosine {cos:.4f})")
    return cos


def embed_persona(keys, device) -> tuple[dict, float]:
    embed = plato.Embedder(plato.DINO_MODEL, device)
    check = check_embedder(embed)  # every run, so results.json always records it
    out = {}
    for key in keys:
        files = [p for p in plato.load_dir(pc.folder(key)) if "_age" in p.stem]
        if not files:
            continue
        path = EMB / f"{key}.npz"
        names = [f.name for f in files]
        if path.exists():
            z = np.load(path)
            if list(z["files"]) == names and str(z["prep"]) == pc.PREP:
                out[key] = load_npz(path)
                continue
        vecs = embed([plato.ink_crop(Image.open(f).convert("RGB")) for f in files])
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, files=np.array(names), model=plato.DINO_MODEL, prep=pc.PREP, **vecs)
        print(f"embedded {key}: {len(files)} pictures", flush=True)
        out[key] = load_npz(path)
    return out, check


def human_centroids() -> tuple[list[str], np.ndarray]:
    """People's centroid for each of the 35 core things (for recognisability, E5)."""
    keys, cents = [], []
    for c in plato.CONCEPTS:
        p = plato.PLATO_DIR / "embeddings" / "human" / f"{c.key}.npz"
        if p.exists():
            keys.append(c.key)
            cents.append(pc.centroid(load_npz(p)[1]))
    return keys, np.array(cents)


def ratio_ci(a_boot, b_boot) -> list[float]:
    n = min(len(a_boot), len(b_boot))
    return plato.ci(a_boot[:n] / b_boot[:n])


def concept_block(key, persona, rng, hc_keys, hc) -> dict:
    p_files, p_cls, p_pm = persona
    ages = np.array([pc.age_of(f) for f in p_files], float)
    d_files, d_cls, d_pm = load_npz(pc.default_embeddings_path(key))
    dp, dd = plato.cosine_distances(p_cls), plato.cosine_distances(d_cls)
    p_s, d_s = plato.spread(dp), plato.spread(dd)
    p_boot, d_boot = plato.bootstrap_spread(dp, pc.B_AI, rng), plato.bootstrap_spread(dd, pc.B_AI, rng)
    dist = pc.distance_to(p_cls, pc.centroid(d_cls))
    d_loo = pc.loo_distances(d_cls)
    pm_p, pm_d = plato.cosine_distances(p_pm), plato.cosine_distances(d_pm)
    b = {
        "key": key, "label": pc.label(key), "n_persona": len(p_files), "n_default": len(d_files),
        "ages": [int(a) for a in ages], "ages_missing": [a for a in pc.AGES if a not in set(ages.astype(int))],
        "persona_spread": p_s, "persona_spread_ci95": plato.ci(p_boot),
        "default_spread": d_s, "default_spread_ci95": plato.ci(d_boot),
        "diff": p_s - d_s, "diff_ci95": plato.ci(p_boot - d_boot),
        "ratio_vs_default": p_s / d_s, "ratio_vs_default_ci95": ratio_ci(p_boot, d_boot),
        "age_rho": plato.spearman(ages, dist), "age_rho_u": plato.spearman(np.abs(ages - 50), dist),
        "dist_to_default_centroid": [float(x) for x in dist],
        "default_loo_max": float(d_loo.max()), "default_loo_median": float(np.median(d_loo)),
        "outside_default": int((dist > d_loo.max()).sum()),
        "patch_mean": {"persona_spread": plato.spread(pm_p), "default_spread": plato.spread(pm_d)},
        "_p_boot": p_boot, "_d_boot": d_boot,
        "_pm_p_boot": plato.bootstrap_spread(pm_p, pc.B_AI, rng), "_pm_d_boot": plato.bootstrap_spread(pm_d, pc.B_AI, rng),
    }
    hp = pc.people_embeddings_path(key)
    if hp is not None:
        _, h_cls, _ = load_npz(hp)
        dh = plato.cosine_distances(h_cls)
        subs = plato.subsample_spread(dh, len(pc.AGES), pc.SUBSETS, rng)
        hum = float(subs.mean())
        h_boot = plato.bootstrap_spread(dh, pc.B_HUMAN, rng)
        nearest = [hc_keys[i] for i in np.argmax(pc.unit(p_cls) @ hc.T, axis=1)]
        nearest_d = [hc_keys[i] for i in np.argmax(pc.unit(d_cls) @ hc.T, axis=1)]
        b.update({
            "people_spread": hum, "people_spread_ci95": plato.ci(h_boot), "people_range95_for_16": plato.ci(subs),
            "persona_vs_people": p_s / hum, "persona_vs_people_ci95": ratio_ci(p_boot, h_boot),
            "default_vs_people": d_s / hum, "default_vs_people_ci95": ratio_ci(d_boot, h_boot),
            "reaches_people": bool(p_s >= hum), "default_reaches_people": bool(d_s >= hum),
            "share_of_people_sets_as_uniform": float((subs <= p_s).mean()),
            "recognisable": float(np.mean([n == key for n in nearest])),
            "recognisable_default": float(np.mean([n == key for n in nearest_d])),
            "nearest_other": sorted({n for n in nearest if n != key}),
        })
        b["persona_clearly_below_people"] = b["persona_vs_people_ci95"][1] < 1
        b["default_clearly_below_people"] = b["default_vs_people_ci95"][1] < 1
    return b


def god_labels() -> dict | None:
    path = pc.CROWD_DIR / "labels_by_eye.json"
    if not path.exists():
        return None
    lab = json.loads(path.read_text())
    rows = lab["labels"]  # file -> {"emblem": short name, "halo": bool, "note": str}
    emblems = [s for s, _ in plato_ideas.BY_KEY["god"].emblems]
    names = [r["emblem"] for r in rows.values()]
    conc = plato_ideas.concentration(names, emblems)
    both = sum(r["emblem"] == "bearded man" and r["halo"] for r in rows.values())
    by_age = {str(pc.age_of(f)): r for f, r in sorted(rows.items(), key=lambda kv: pc.age_of(kv[0]))}
    return {"n": len(rows), "concentration": conc, "bearded_man": names.count("bearded man"),
            "halo": sum(bool(r["halo"]) for r in rows.values()), "bearded_man_with_halo": both,
            "by_age": by_age, "how": lab.get("how"), "sha256_before_ages_seen": lab.get("sha256")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device")
    args = ap.parse_args()
    rng = np.random.default_rng(pc.SEED)
    persona, check = embed_persona(pc.KEYS, args.device)
    hc_keys, hc = human_centroids()
    blocks = {k: concept_block(k, persona[k], rng, hc_keys, hc) for k in pc.KEYS if k in persona}
    things = [blocks[k] for k in pc.THINGS if k in blocks and blocks[k]["n_persona"] >= pc.MIN_PICTURES]

    diffs = np.array([b["diff"] for b in things])
    boots = pc.paired_mean_diff_boot([b["_p_boot"] for b in things], [b["_d_boot"] for b in things], pc.B_PAIRED, rng)
    pm_diffs = np.array([b["patch_mean"]["persona_spread"] - b["patch_mean"]["default_spread"] for b in things])
    pm_boots = pc.paired_mean_diff_boot([b["_pm_p_boot"] for b in things], [b["_pm_d_boot"] for b in things], pc.B_PAIRED, rng)
    h1 = {"D": float(diffs.mean()), "ci95": plato.ci(boots), "p_signflip_one_sided": pc.signflip_p(diffs, rng=rng),
          "n_things": len(things), "n_persona_above_default": int((diffs > 0).sum()),
          "n_diff_ci_above_0": int(sum(b["diff_ci95"][0] > 0 for b in things)),
          "median_ratio_vs_default": float(np.median([b["ratio_vs_default"] for b in things])),
          "mean_persona_spread": float(np.mean([b["persona_spread"] for b in things])),
          "mean_default_spread": float(np.mean([b["default_spread"] for b in things])),
          "mean_people_spread": float(np.mean([b["people_spread"] for b in things]))}
    h1["passes"] = h1["ci95"][0] > 0
    e4 = {"D": float(pm_diffs.mean()), "ci95": plato.ci(pm_boots), "n_persona_above_default": int((pm_diffs > 0).sum())}
    h2 = {"n_reach_people": int(sum(b["reaches_people"] for b in things)),
          "reach": [b["key"] for b in things if b["reaches_people"]],
          "n_clearly_below_people": int(sum(b["persona_clearly_below_people"] for b in things)),
          "median_persona_vs_people": float(np.median([b["persona_vs_people"] for b in things])),
          "default_n_reach_people": int(sum(b["default_reaches_people"] for b in things)),
          "default_n_clearly_below_people": int(sum(b["default_clearly_below_people"] for b in things)),
          "median_default_vs_people": float(np.median([b["default_vs_people"] for b in things]))}
    h2["prediction_holds"] = h2["n_reach_people"] <= 3
    dist = {b["key"]: np.array(b["dist_to_default_centroid"]) for b in things}
    ages = {b["key"]: np.array(b["ages"], float) for b in things}
    h3 = pc.age_trend(dist, ages, rng=rng)
    e2 = pc.age_trend(dist, {k: np.abs(a - 50) for k, a in ages.items()}, rng=rng)

    if h1["passes"] and h2["n_reach_people"] >= 6:
        verdict = "default_not_limit"
    elif h1["passes"]:
        verdict = "some_variety"
    else:
        verdict = "no_change"

    god = blocks.get(pc.IDEA)
    if god:
        god = {**god, "labels_by_eye": god_labels()}
    res = {
        "plan": "docs/plato_crowd_plan.md", "model": plato.DINO_MODEL, "prep": pc.PREP, "ages": list(pc.AGES),
        "prompt_example": pc.prompt_for("chair", 34), "embedder_check_min_cosine": check,
        "verdict": verdict, "H1": h1, "H2": h2, "H3": h3,
        "exploratory": {"E1_outside_default": {b["key"]: b["outside_default"] for b in things},
                        "E2_u_shape": e2, "E4_patch_mean": e4,
                        "E5_recognisable": {b["key"]: [b["recognisable"], b["recognisable_default"]] for b in things}},
        "things": [{k: v for k, v in b.items() if not k.startswith("_")} for b in things],
        "god": {k: v for k, v in god.items() if not k.startswith("_")} if god else None,
        "left_out": [k for k in pc.THINGS if k not in {b["key"] for b in things}],
    }
    OUT.write_text(json.dumps(plato.to_jsonable(res), indent=1))
    print(f"H1: D = {h1['D']:+.3f} {np.round(h1['ci95'], 3)}, p = {h1['p_signflip_one_sided']:.4f}; "
          f"{h1['n_persona_above_default']}/{len(things)} up; median x{h1['median_ratio_vs_default']:.2f}")
    print(f"H2: {h2['n_reach_people']}/{len(things)} reach people ({', '.join(h2['reach']) or 'none'}); "
          f"{h2['n_clearly_below_people']} clearly below; median persona/people {h2['median_persona_vs_people']:.2f}")
    print(f"H3: mean rho {h3['mean_rho']:+.3f} {np.round(h3['ci95'], 3)}, p = {h3['p_perm_two_sided']:.4f}")
    print(f"verdict: {verdict}")
    for b in things + ([god] if god else []):
        ppl = f"people {b['people_spread']:.3f}" if "people_spread" in b else ""
        print(f"  {b['key']:9s} default {b['default_spread']:.3f} persona {b['persona_spread']:.3f} "
              f"{np.round(b['persona_spread_ci95'], 3)} x{b['ratio_vs_default']:.2f} {ppl} rho {b['age_rho']:+.2f}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

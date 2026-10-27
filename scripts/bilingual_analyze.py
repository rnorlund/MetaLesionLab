"""Analyze the bilingual lesion test (runs/bilingual/raw, from scripts/bilingual_run.py). No GPU.

Pre-specified primary measure (fixed before any lesioned run was seen): for each non-English
variant, the accuracy drop from intact in that language minus the drop in English on the same
pictures, averaged over every main lesion condition and seed, on pictures named correctly intact
in both languages. 95% CI from a bootstrap over pictures (shared across conditions) and seeds
within condition; p from a sign-flip permutation test over pictures.

Writes runs/bilingual/results.json and runs/bilingual/figures/*.png.

Usage: python scripts/bilingual_analyze.py [--dir runs/bilingual] [--sets runs/sets] [--boot 4000]
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from metalesionlab import bilingual as B

NON_EN = ("es", "fr", "pt", "es_xen")
VARIANTS = ("en",) + NON_EN
MAIN_EXCLUDE = ("intact", "robustness")  # families left out of the main lesion pool
GROUPS = {"decoder noise": lambda f: f.startswith("layers"), "vision tower noise": lambda f: f == "vision_tower",
          "unit ablation or pruning": lambda f: f.startswith(("naming", "random", "pruned"))}
LABEL = {"en": "English", "es": "Spanish", "fr": "French", "pt": "Portuguese",
         "es_xen": "Spanish (English instruction)"}


def group_of(family: str) -> str:
    return next(g for g, test in GROUPS.items() if test(family))


def load(raw_dir: Path, items: list[B.BiItem]) -> dict:
    by = {it.en: it for it in items}
    runs = {}
    for f in sorted(raw_dir.glob("*.json")):
        r = json.loads(f.read_text())
        B.code_run(r, by)
        runs[(r["condition"], r["variant"], r["seed"])] = r
    return runs


def by_condition(runs: dict, plan: list[dict]) -> dict:
    """condition -> variant -> runs, keeping only seeds finished for every planned variant (so
    languages are always compared on the same seeds) and only complete conditions."""
    out = defaultdict(lambda: defaultdict(list))
    for (cond, var, _), r in runs.items():
        out[cond][var].append(r)
    done = {}
    for c in plan:
        got = out.get(c["name"], {})
        seeds = set.intersection(*[{r["seed"] for r in got.get(v, [])} for v in c["variants"]])
        if seeds:
            done[c["name"]] = {v: sorted([r for r in got[v] if r["seed"] in seeds], key=lambda r: r["seed"])
                               for v in c["variants"]}
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path("runs/bilingual"))
    ap.add_argument("--sets", type=Path, default=Path("runs/sets"))
    ap.add_argument("--boot", type=int, default=4000)
    args = ap.parse_args()
    t0 = time.time()
    items = B.matched_items(args.sets)
    words = [it.en for it in items]
    runs = load(args.dir / "raw", items)
    plan = json.loads((args.dir / "plan.json").read_text())
    conds = by_condition(runs, plan)
    meta_of = {c["name"]: c for c in plan}
    name_ids = json.loads((args.dir / "name_ids.json").read_text())["ids"]

    intact = {v: conds["intact"][v][0] for v in VARIANTS}
    base = {v: B.correct_matrix([intact[v]], words)[:, 0] for v in VARIANTS}
    common = {v: (base["en"] == 1) & (base[v] == 1) for v in NON_EN}
    main_conds = [c["name"] for c in plan if c["family"] not in ("intact",) and not c["family"].startswith("robustness")
                  and c["name"] in conds]
    missing = [c["name"] for c in plan if c["name"] not in conds]

    def mats(cond, var):
        return B.correct_matrix(conds[cond][var], words)

    # --- per condition --------------------------------------------------------------------
    per_cond = []
    for cname in [c["name"] for c in plan if c["name"] in conds]:
        c = meta_of[cname]
        row = {"condition": cname, "family": c["family"], "group": None if c["family"] in ("intact",) or
               c["family"].startswith("robustness") else group_of(c["family"]), "dose": c["dose"],
               "stats": c["stats"], "seeds": sorted(r["seed"] for r in conds[cname]["en"]), "by_variant": {}}
        for v in c["variants"]:
            if v not in conds[cname]:
                continue
            rs = conds[cname][v]
            m = mats(cname, v)
            sw = B.flag_matrix(rs, words, "switch")
            mixed = B.flag_matrix(rs, words, "mixed")
            entry = {"accuracy": round(float(m.mean()), 4),
                     "accuracy_ci95": B.bootstrap_mean([m], n_boot=args.boot)["ci95"],
                     "accuracy_by_seed": [r["accuracy"] for r in sorted(rs, key=lambda r: r["seed"])],
                     "switch_rate": round(float(sw.mean()), 4), "mixed_rate": round(float(mixed.mean()), 4),
                     "english_name_rate": round(float(B.flag_matrix(rs, words, "english_name").mean()), 4),
                     "counts": dict(sum((Counter(r["counts"]) for r in rs), Counter())),
                     "counts_switch_aware": dict(sum((Counter(r["counts_switch_aware"]) for r in rs), Counter()))}
            if v != "en" and cname != "intact":
                entry["drop_minus_en"] = B.bootstrap_drop_diff([(mats(cname, "en"), m)], base["en"], base[v],
                                                               keep=common[v], n_boot=args.boot)
            row["by_variant"][v] = entry
        per_cond.append(row)

    # --- pooled primary and secondary measures ----------------------------------------------
    def pooled(names: list[str], v: str, keep=True) -> dict:
        pairs = [(mats(n, "en"), mats(n, v)) for n in names if v in conds[n]]
        if not pairs:
            return None
        res = B.bootstrap_drop_diff(pairs, base["en"], base[v], keep=common[v] if keep else None, n_boot=args.boot)
        idx = np.flatnonzero(common[v]) if keep else np.arange(len(words))
        per_item = np.mean([((base[v][:, None] - l) - (base["en"][:, None] - e)).mean(1) for e, l in pairs], axis=0)
        res["p_sign_flip"] = round(B.sign_flip_test(per_item[idx]), 5)
        res["acc_en"] = round(float(np.mean([e[idx].mean() for e, _ in pairs])), 4)
        res["acc_lang"] = round(float(np.mean([l[idx].mean() for _, l in pairs])), 4)
        res["items_worse_in_lang"] = int((per_item[idx] > 1e-9).sum())
        res["items_worse_in_en"] = int((per_item[idx] < -1e-9).sum())
        return res

    families = sorted({meta_of[n]["family"] for n in main_conds}, key=lambda f: [c["family"] for c in plan].index(f))
    primary = {v: pooled(main_conds, v) for v in NON_EN}
    all_items = {v: pooled(main_conds, v, keep=False) for v in NON_EN}
    by_family = {f: {v: pooled([n for n in main_conds if meta_of[n]["family"] == f], v) for v in NON_EN}
                 for f in families}
    by_group = {g: {v: pooled([n for n in main_conds if group_of(meta_of[n]["family"]) == g], v) for v in NON_EN}
                for g in GROUPS}

    # --- language switching ------------------------------------------------------------------
    def switch_pool(names, v, key="switch", errors_only=False):
        ms = []
        for n in names:
            if v not in conds[n]:
                continue
            m = B.flag_matrix(conds[n][v], words, key)
            if errors_only:
                wrong = 1 - mats(n, v)
                m = np.where(wrong > 0, m, np.nan)
            ms.append(m)
        if errors_only:
            flat = np.concatenate([m.ravel() for m in ms])
            flat = flat[~np.isnan(flat)]
            return {"share_of_errors": round(float(flat.mean()), 4) if len(flat) else None, "n_errors": int(len(flat)),
                    "ci95": B.wilson(flat.sum(), len(flat)) if len(flat) else None}
        return B.bootstrap_mean(ms, n_boot=args.boot)

    switching = {"lesioned": {v: {"english_answers": switch_pool(main_conds, v),
                                  "english_name": switch_pool(main_conds, v, "english_name"),
                                  "mixed": switch_pool(main_conds, v, "mixed"),
                                  "english_share_of_errors": switch_pool(main_conds, v, errors_only=True)}
                              for v in NON_EN},
                 "reverse_on_english_trials": {"non_english_answers": switch_pool(main_conds, "en"),
                                               "mixed": switch_pool(main_conds, "en", "mixed")},
                 "intact": {v: {"switch_n": intact[v]["switch_n"], "mixed_n": intact[v]["mixed_n"],
                                "items": [r["en"] for r in intact[v]["items"] if r["switch"]]} for v in VARIANTS},
                 "by_family": {f: {v: switch_pool([n for n in main_conds if meta_of[n]["family"] == f], v)
                                   for v in VARIANTS} for f in families}}

    # --- dose-response -----------------------------------------------------------------------
    dose = {}
    for f in families:
        rows = []
        for n in main_conds:
            if meta_of[n]["family"] != f:
                continue
            pc = next(p for p in per_cond if p["condition"] == n)
            rows.append({"condition": n, "dose": meta_of[n]["dose"],
                         **{f"acc_{v}": pc["by_variant"][v]["accuracy"] for v in VARIANTS if v in pc["by_variant"]},
                         **{f"switch_{v}": pc["by_variant"][v]["switch_rate"] for v in VARIANTS if v in pc["by_variant"]}})
        dose[f] = sorted(rows, key=lambda r: r["dose"])

    # --- word lens: an English pivot? ---------------------------------------------------------
    pieces = B.strip_pieces(json.loads((args.dir / "name_ids.json").read_text())["pieces"])
    lens = {}
    lesioned_runs = lambda v: [r for n in main_conds for r in conds[n].get(v, [])]  # noqa: E731
    for v in NON_EN:
        lang = B.VARIANT_LANG[v]
        ok = B.disjoint_lens_items(items, name_ids, lang, pieces)
        entry = {"items": ok, "n_items": len(ok),
                 "intact": B.lens_pivot([intact[v]], ok, lang, pieces=pieces),
                 "lesioned": B.lens_pivot(lesioned_runs(v), ok, lang, pieces=pieces),
                 "by_group": {g: B.lens_pivot([r for n in main_conds if group_of(meta_of[n]["family"]) == g
                                               for r in conds[n].get(v, [])], ok, lang, pieces=pieces)
                              for g in GROUPS}}
        for k in ("intact", "lesioned"):
            e = entry[k]
            po, pl = np.array(e["mean_p_other"]), np.array(e["mean_p_lang"])
            lead = np.flatnonzero((po > pl) & (po >= B.CONFIDENT))
            e["english_leads_layers"] = lead.tolist()  # layers where the mean English p is above the target's
            e["peak_mean_p_english"] = round(float(po[:-1].max()), 4)
            e["peak_layer_english"] = int(po[:-1].argmax())
            e["final_mean_p_lang"], e["final_mean_p_english"] = round(float(pl[-1]), 4), round(float(po[-1]), 4)
            top = np.array(e["frac_top1_other"])
            e["peak_frac_top1_english"] = round(float(top[:-1].max()), 4)
            e["peak_frac_top1_english_layer"] = int(top[:-1].argmax())
        per_item = {}
        for row in intact[v]["items"]:
            if row["en"] not in ok:
                continue
            a, b = np.array(row["lens"]["logp"]["en"]), np.array(row["lens"]["logp"][lang])
            top_en = [i for i, t in enumerate(row["lens"]["top1"]) if t in pieces[row["en"]]["en"]]
            top_l = [i for i, t in enumerate(row["lens"]["top1"]) if t in pieces[row["en"]][lang]]
            per_item[row["en"]] = {"said": row["said"], "english_top1_layers": top_en, "target_top1_layers": top_l,
                                   "peak_p_english": round(float(np.exp(a[:-1]).max()), 4),
                                   "peak_layer_english": int(a[:-1].argmax()),
                                   "final_margin": round(float(b[-1] - a[-1]), 3),
                                   "top1_by_layer": row["lens"]["top1"]}
        entry["intact_items"] = per_item
        entry["intact_items_english_top1_any"] = sum(bool(x["english_top1_layers"][:1]) and
                                                     x["english_top1_layers"][0] < 51 for x in per_item.values())
        lens[v] = entry
    # Reverse reference: on English trials, does the Spanish name ever lead?
    ok_es = B.disjoint_lens_items(items, name_ids, "es", pieces)
    lens["reverse_en_trials_es_above_en"] = {
        "items": ok_es, "intact": B.lens_pivot([intact["en"]], ok_es, "en", other="es", pieces=pieces),
        "lesioned": B.lens_pivot(lesioned_runs("en"), ok_es, "en", other="es", pieces=pieces)}

    # --- does the intact lens predict which pictures switch under damage? ----------------------
    link = {}
    for v in NON_EN:
        ok = lens[v]["items"]
        sw = np.mean([B.flag_matrix(conds[n][v], words, "switch").mean(1) for n in main_conds], axis=0)
        err_l = np.mean([1 - mats(n, v).mean(1) for n in main_conds], axis=0)
        err_e = np.mean([1 - mats(n, "en").mean(1) for n in main_conds], axis=0)
        rows = []
        for i, w in enumerate(words):
            if w in ok:
                it = lens[v]["intact_items"][w]
                rows.append({"item": w, "peak_p_english": it["peak_p_english"], "final_margin": it["final_margin"],
                             "english_top1_layers": len([x for x in it["english_top1_layers"] if x < 51]),
                             "switch_rate": round(float(sw[i]), 4), "extra_errors": round(float(err_l[i] - err_e[i]), 4)})
        col = lambda k: [r[k] for r in rows]  # noqa: E731
        link[v] = {"items": rows, "n": len(rows),
                   "spearman_peak_p_english_vs_switch": _spearman(col("peak_p_english"), col("switch_rate")),
                   "spearman_peak_p_english_vs_extra_errors": _spearman(col("peak_p_english"), col("extra_errors")),
                   "spearman_final_margin_vs_switch": _spearman(col("final_margin"), col("switch_rate")),
                   "spearman_final_margin_vs_extra_errors": _spearman(col("final_margin"), col("extra_errors"))}

    # --- intact confidence ------------------------------------------------------------------
    confidence = {v: {"mean_final_p_target": round(float(np.mean([np.exp(r["lens"]["logp"][B.VARIANT_LANG[v]][-1])
                                                                   for r in intact[v]["items"]])), 4),
                      "median_final_logp_target": round(float(np.median([r["lens"]["logp"][B.VARIANT_LANG[v]][-1]
                                                                         for r in intact[v]["items"]])), 3)}
                  for v in VARIANTS}

    # --- robustness: the reference statistics ----------------------------------------------
    robust = []
    for c in plan:
        if not c["family"].startswith("robustness") or c["name"] not in conds:
            continue
        base_name = c["name"].split(" [")[0]
        r = {"condition": c["name"], "stats": c["stats"],
             "es_minus_en": B.bootstrap_drop_diff([(mats(c["name"], "en"), mats(c["name"], "es"))], base["en"],
                                                   base["es"], keep=common["es"], n_boot=args.boot),
             "acc_en": round(float(mats(c["name"], "en").mean()), 4), "acc_es": round(float(mats(c["name"], "es").mean()), 4)}
        if base_name in conds:
            r["pooled_stats"] = {"acc_en": round(float(mats(base_name, "en").mean()), 4),
                                 "acc_es": round(float(mats(base_name, "es").mean()), 4),
                                 "es_minus_en": B.bootstrap_drop_diff([(mats(base_name, "en"), mats(base_name, "es"))],
                                                                      base["en"], base["es"], keep=common["es"],
                                                                      n_boot=args.boot)}
        robust.append(r)
    robust_pool = {}
    for s in ("en", "es"):
        names = [c["name"] for c in plan if c["family"] == f"robustness stats {s}" and c["name"] in conds]
        if names:
            pairs = [(mats(n, "en"), mats(n, "es")) for n in names]
            robust_pool[s] = B.bootstrap_drop_diff(pairs, base["en"], base["es"], keep=common["es"], n_boot=args.boot)
            pooled_names = [n.split(" [")[0] for n in names if n.split(" [")[0] in conds]
            robust_pool["pooled_same_conditions"] = B.bootstrap_drop_diff(
                [(mats(n, "en"), mats(n, "es")) for n in pooled_names], base["en"], base["es"], keep=common["es"],
                n_boot=args.boot)

    # --- error types pooled over the main lesion conditions -----------------------------------
    errors = {}
    for v in VARIANTS:
        rs = [r for n in main_conds for r in conds[n].get(v, [])]
        errors[v] = {"counts": dict(sum((Counter(r["counts"]) for r in rs), Counter())),
                     "counts_switch_aware": dict(sum((Counter(r["counts_switch_aware"]) for r in rs), Counter())),
                     "trials": sum(r["n"] for r in rs)}

    # --- runs, slimmed (the full word lens stays in raw/) ---------------------------------------
    slim = []
    for (cname, v, seed), r in sorted(runs.items()):
        slim.append({k: r.get(k) for k in ("condition", "family", "dose", "seed", "variant", "lang", "stats", "skip",
                                           "accuracy", "correct", "n", "switch_n", "mixed_n", "english_name_n",
                                           "counts", "counts_switch_aware", "seconds")}
                    | {"items": [{k: row.get(k) for k in ("en", "target", "said", "code", "head", "lang_label", "switch",
                                                          "mixed", "english_name", "switch_code", "other_lang")}
                                 | {"final_logp": {lang: x[-1] for lang, x in row["lens"]["logp"].items()}}
                                 for row in r["items"]]})

    results = {
        "meta": {"model": "meta-models/Muse-Glimmer-30B", "precision": "decoder FP8; vision tower, projector, lm_head BF16",
                 "hardware": "1x NVIDIA L40S (axon-server02)", "pictures": words, "n_pictures": len(words),
                 "names": {it.en: it.names for it in items}, "prompts": B.PROMPTS, "variants": list(VARIANTS),
                 "reference_stats": "pooled over the 20 held-out demo_en drawings x en/es/fr/pt prompts (80 trials)",
                 "judge": "none (accuracy never depends on it; Semantic vs Unrelated does)",
                 "lens_confident_p": B.CONFIDENT, "n_runs": len(runs), "n_main_conditions": len(main_conds),
                 "missing_conditions": missing, "analyzed": time.strftime("%Y-%m-%d %H:%M"),
                 "primary_measure": ("(intact - lesioned accuracy in the language) - (intact - lesioned accuracy in "
                                     "English), same pictures, pictures correct intact in both languages, averaged "
                                     "over all main lesion conditions and seeds; bootstrap over pictures and seeds; "
                                     "sign-flip permutation test over pictures")},
        "intact": {v: {"accuracy": intact[v]["accuracy"], "correct": intact[v]["correct"],
                       "answers": {r["en"]: r["said"] for r in intact[v]["items"]}} for v in VARIANTS},
        "common_correct": {v: [w for w, k in zip(words, common[v]) if k] for v in NON_EN},
        "primary": primary, "all_pictures": all_items, "by_group": by_group, "by_family": by_family,
        "switching": switching, "dose_response": dose, "lens": lens, "lens_predicts_switch": link,
        "intact_confidence": confidence, "robustness_reference_stats": {"conditions": robust, "pooled": robust_pool},
        "error_types": errors, "conditions": per_cond, "runs": slim,
    }
    out = args.dir / "results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1, default=_json_default))
    print(f"{len(runs)} runs, {len(main_conds)} main conditions ({len(missing)} missing) -> {out} "
          f"in {time.time() - t0:.0f}s")
    for v in NON_EN:
        p = primary[v]
        print(f"  {v:7s} drop minus English {p['diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}] "
              f"p={p['p_sign_flip']:.4f}  acc en {p['acc_en']:.3f} vs {p['acc_lang']:.3f}  "
              f"(n={p['n_items']} pictures, {p['n_conditions']} conditions)")
    sw = switching["lesioned"]
    for v in NON_EN:
        print(f"  {v:7s} English answers {sw[v]['english_answers']['mean']:.3f} {sw[v]['english_answers']['ci95']}"
              f"  English name {sw[v]['english_name']['mean']:.3f}  mixed {sw[v]['mixed']['mean']:.3f}")
    rev = switching["reverse_on_english_trials"]["non_english_answers"]
    print(f"  reverse (non-English answers on English trials) {rev['mean']:.3f} {rev['ci95']}")


def _spearman(x, y, n_perm: int = 20000, seed: int = 0) -> dict:
    """Spearman's rho with a two-sided permutation p."""
    from scipy.stats import rankdata

    if len(x) < 3:
        return {"rho": None, "p": None}
    rx, ry = rankdata(x), rankdata(y)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return {"rho": None, "p": None}
    rho = float(np.corrcoef(rx, ry)[0, 1])
    rng = np.random.default_rng(seed)
    null = np.array([np.corrcoef(rx, rng.permutation(ry))[0, 1] for _ in range(n_perm)])
    p = (np.sum(np.abs(null) >= abs(rho) - 1e-12) + 1) / (n_perm + 1)
    return {"rho": round(rho, 3), "p": round(float(p), 4), "n": len(x)}


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


if __name__ == "__main__":
    main()

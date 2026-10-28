"""An AI growing up: the pre-registered analysis (docs/plato_scale_plan.md).

Usage: python -I scripts/plato_scale_analyze.py [--reps 2000] [--public public_data/plato_scale.json]

Reads $PLATO_SCALE_DIR/svg (Arm B: measure.json, emb/) and $PLATO_SCALE_DIR/sketch (Arm A: runs/n<size>_s<seed>/
{emb, meta.json}, ref/), and the 35 human prototypes and Muse Image's chairs in $PLATO_DIR/embeddings/.
Writes $PLATO_SCALE_DIR/results.json and, with --public, the derived statistics only (no drawings, SVG text or
embeddings) to public_data/plato_scale.json.
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from metalesionlab import plato_scale as ps  # noqa: E402
from metalesionlab.plato import CONCEPTS, DINO_MODEL, PLATO_DIR, ci, cosine_distances, spearman, subsample_spread  # noqa: E402
from metalesionlab.plato_lifespan import loo_proto_distances, matched_spread, proto_distances, prototype, recognized  # noqa: E402
from metalesionlab.plato_sketch import STEPS, boot_counts, boot_spread, sample_name, t_interval  # noqa: E402

KEYS = [c.key for c in CONCEPTS]
CHAIR = KEYS.index("chair")
EMB = "cls"
SVG_DIR = ps.SCALE_DIR / "svg"
SK_DIR = ps.SCALE_DIR / "sketch"
CREDITS = [
    "Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0, "
    "https://github.com/googlecreativelab/quickdraw-dataset (statistics only; no drawing is included)",
    "Similarity: Meta DINOv2 (facebook/dinov2-base), Apache-2.0",
    "Sketch model design after Sketch-RNN: Ha, D. & Eck, D. (2017), A Neural Representation of Sketch Drawings",
    "Language models: Qwen2.5 and Qwen3 (Alibaba Cloud), OLMo 2 (Allen Institute for AI), Muse Glimmer 30B (Meta), "
    "all Apache-2.0; Muse Spark 1.3 and Muse Wonder 1.0 through the Meta Model API",
    "Hypothesis tested: Huh, M., Cheung, B., Wang, T. & Isola, P. (2024), The Platonic Representation Hypothesis, "
    "ICML 2024, arXiv:2405.07987",
]


def no_nan(x):
    if isinstance(x, dict):
        return {k: no_nan(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [no_nan(v) for v in x]
    if isinstance(x, (float, np.floating)):
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else round(x, 4)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def ci_or_none(b):
    """95% CI of the finite replicates. A replicate that resamples a single picture has no pairs: it is undefined
    and dropped (only possible for the smallest sets, e.g. 4 rendered drawings)."""
    b = np.asarray(b, float)
    b = b[np.isfinite(b)]
    return ci(b) if len(b) else [float("nan"), float("nan")]


def within(X: np.ndarray) -> np.ndarray:
    """Cosine distances within one set, with an exact zero diagonal (rounding leaves about -2e-16 there, which
    would make a one-picture bootstrap replicate divide a tiny number by zero)."""
    d = cosine_distances(X)
    np.fill_diagonal(d, 0.0)
    return d


class Ref:
    """The human prototypes (35 concepts, 200 Quick, Draw! drawings each) and Muse Image's chair prototype."""

    def __init__(self, rng):
        self.H = {k: np.load(PLATO_DIR / "embeddings" / "human" / f"{k}.npz")[EMB].astype(np.float64) for k in KEYS}
        self.protos = np.stack([prototype(self.H[k]) for k in KEYS])
        self.people = self.protos[CHAIR]
        self.muse_x = np.load(PLATO_DIR / "embeddings" / "ai_doodle" / "chair.npz")[EMB].astype(np.float64)
        self.muse = prototype(self.muse_x)
        self.Dh = cosine_distances(self.H["chair"])
        self.rng = rng
        self._hs = {}

    def human_spread(self, n: int) -> float:
        """People's spread at n: the mean over 200 random n-subsets of the 200 reference chairs."""
        if n not in self._hs:
            self._hs[n] = float(subsample_spread(self.Dh, n, 200, np.random.default_rng([ps.GEN_SEED, n])).mean())
        return self._hs[n]

    def anchors(self) -> dict:
        """People's and Muse Image's own chairs on the same measures (prototypes left one out)."""
        hx, mx = self.H["chair"], self.muse_x
        return {
            "people": {"n": len(hx), "recog": float(recognized(hx, CHAIR, self.protos, loo_own=hx).mean()),
                       "spread_n12": self.human_spread(12), "spread_n16": self.human_spread(16),
                       "d_people": float(loo_proto_distances(hx).mean()),
                       "d_muse": float(proto_distances(hx, self.muse).mean())},
            "muse_image": {"n": len(mx), "recog": float(recognized(mx, CHAIR, self.protos).mean()),
                           "spread": float(cosine_distances(mx)[np.triu_indices(len(mx), 1)].mean()),
                           "d_people": float(proto_distances(mx, self.people).mean()),
                           "d_muse": float(loo_proto_distances(mx).mean())},
        }


# ---------- Arm B ----------

def arm_b(R: Ref, reps: int, rng) -> tuple[list, dict, dict]:
    meas = json.loads((SVG_DIR / "measure.json").read_text())
    rows, boots, X_by = [], {}, {}
    for m in ps.MODELS:
        for temp in ps.TEMPS_B:
            name = f"{m.key}_t{temp:.1f}"
            if name not in meas:
                continue
            samples = sorted(meas[name]["samples"], key=lambda s: s["i"])
            reasons = [s["reason"] for s in samples]
            fc = ps.failure_counts(reasons)
            z = np.load(SVG_DIR / "emb" / f"{name}.npz")
            X, idx = z[EMB].astype(np.float64), z["idx"].astype(int)
            n = len(samples)
            pos = {s["i"]: k for k, s in enumerate(samples)}
            rec = recognized(X, CHAIR, R.protos) if len(X) else np.zeros(0, bool)
            rec_all = np.zeros(n)
            for i, r in zip(idx, rec):
                rec_all[pos[int(i)]] = float(r)
            fail = np.array([r is not None for r in reasons], float)
            dp = proto_distances(X, R.people) if len(X) else np.zeros(0)
            dm = proto_distances(X, R.muse) if len(X) else np.zeros(0)
            nr = len(X)
            b = {"fail": ps.boot_mean(fail, reps, rng), "recog_all": ps.boot_mean(rec_all, reps, rng),
                 "d_people": ps.boot_mean(dp, reps, rng), "d_muse": ps.boot_mean(dm, reps, rng),
                 "spread": np.full(reps, np.nan)}
            spread = hs = ratio = None
            if nr >= 4:
                d = within(X)
                spread = float(d[np.triu_indices(nr, 1)].mean())
                b["spread"] = boot_spread(d, boot_counts(nr, reps, rng))
                hs = R.human_spread(nr)
                ratio = spread / hs
            framed = [s.get("framed") for s in samples if s["reason"] is None]
            row = {"key": m.key, "label": m.label, "family": m.family, "params_b": m.params_b, "kind": m.kind,
                   "temp": temp, "n": n, "failed": fc["failed"], "rendered": fc["rendered"],
                   "failure_rate": fc["rate"], "failure_ci95": ps.wilson(fc["failed"], n),
                   "failures": {k: fc[k] for k in ps.FAILURES},
                   "recog_all": float(rec_all.mean()), "recog_all_ci95": ci_or_none(b["recog_all"]),
                   "recog_rendered": float(rec.mean()) if nr else None,
                   "spread": spread, "spread_ci95": ci_or_none(b["spread"]) if spread is not None else None,
                   "human_spread": hs, "spread_ratio": ratio,
                   "d_people": float(dp.mean()) if nr else None, "d_people_ci95": ci_or_none(b["d_people"]) if nr else None,
                   "d_muse": float(dm.mean()) if nr else None, "d_muse_ci95": ci_or_none(b["d_muse"]) if nr else None,
                   "closer_to_muse": bool(dm.mean() < dp.mean()) if nr else None,
                   "framed_share": float(np.mean(framed)) if framed else None,
                   "unfinished": int(sum(1 for s in samples if s.get("finished") is False)),
                   "mean_tokens": float(np.mean([s["n_tokens"] for s in samples if s.get("n_tokens") is not None]))}
            rows.append(row)
            boots[name] = b
            X_by[name] = X
    return rows, boots, X_by


MEASURES_B = [("recog_all", "recog_all", +1, "P1"), ("spread", "spread", -1, "P2"), ("failure_rate", "fail", -1, "P3"),
              ("d_muse", "d_muse", 0, "E2"), ("d_people", "d_people", 0, "")]


def family_tests(rows: list, boots: dict) -> dict:
    by = {(r["key"], r["temp"]): r for r in rows}
    out = {}
    for fam in ps.FAMILIES:
        for temp in ps.TEMPS_B:
            ms = [m for m in ps.family_models(fam) if (m.key, temp) in by]
            if len(ms) < 2:
                continue
            res = {"models": [m.key for m in ms]}
            for col, bkey, pred, label in MEASURES_B:
                have = [m for m in ms if by[(m.key, temp)][col] is not None]
                if len(have) < 2:
                    res[col] = {"test": label, "verdict": "not testable", "n_sizes": len(have)}
                    continue
                x = [math.log10(m.params_b) for m in have]
                y = [by[(m.key, temp)][col] for m in have]
                rho = spearman(x, y) if len(set(y)) > 1 else 0.0
                small, large = have[0], have[-1]
                diff = boots[f"{large.key}_t{temp:.1f}"][bkey] - boots[f"{small.key}_t{temp:.1f}"][bkey]
                c = ci_or_none(diff)
                res[col] = {"test": label, "smallest": small.key, "largest": large.key,
                            "values": {m.key: by[(m.key, temp)][col] for m in have},
                            "contrast": by[(large.key, temp)][col] - by[(small.key, temp)][col], "contrast_ci95": c,
                            "spearman_log_params": rho, "n_sizes": len(have),
                            "verdict": ps.verdict(c, rho, pred) if pred else None}
            out[f"{fam}|{temp:.1f}"] = res
    return out


def cross_family(rows: list, X_by: dict, reps: int, rng) -> dict:
    """E1: in each size band, the energy distance between two different families' drawing distributions
    (2 E|a-b| - E|a-a'| - E|b-b'|, cosine distance; 0 = the same distribution) and the plain cross-model
    distance, averaged over the band's cross-family pairs, with a bootstrap over each model's drawings."""
    out = {}
    for temp in ps.TEMPS_B:
        bands = {}
        for r in rows:
            if r["temp"] != temp or r["kind"] != "open" or r["rendered"] < 4:
                continue
            band = ps.size_band(r["params_b"])
            if band:
                bands.setdefault(band, []).append(r)
        res = {}
        for band in ["<=2B", "4-8B", "13-15B", "30-33B"]:
            ms = bands.get(band, [])
            pairs = [(a, b) for i, a in enumerate(ms) for b in ms[i + 1:] if a["family"] != b["family"]]
            if not pairs:
                continue
            e_pt, c_pt, e_bt, c_bt = [], [], [], []
            for a, b in pairs:
                Xa, Xb = X_by[f"{a['key']}_t{temp:.1f}"], X_by[f"{b['key']}_t{temp:.1f}"]
                Daa, Dbb, Dab = within(Xa), within(Xb), cosine_distances(Xa, Xb)
                ca, cb = boot_counts(len(Xa), reps, rng), boot_counts(len(Xb), reps, rng)
                waa, wbb = boot_spread(Daa, ca), boot_spread(Dbb, cb)
                wab = ((ca @ Dab) * cb).sum(1) / (ca.sum(1) * cb.sum(1))
                within_a, within_b = Daa[np.triu_indices(len(Xa), 1)].mean(), Dbb[np.triu_indices(len(Xb), 1)].mean()
                e_pt.append(2 * Dab.mean() - within_a - within_b)
                c_pt.append(Dab.mean())
                e_bt.append(2 * wab - waa - wbb)
                c_bt.append(wab)
            res[band] = {"pairs": [f"{a['key']}~{b['key']}" for a, b in pairs],
                         "energy": float(np.mean(e_pt)), "energy_ci95": ci_or_none(np.mean(e_bt, 0)),
                         "cross": float(np.mean(c_pt)), "cross_ci95": ci_or_none(np.mean(c_bt, 0)),
                         "_boot_energy": np.mean(e_bt, 0)}
        names = list(res)
        if len(names) >= 2:
            first, last = names[0], names[-1]
            d = res[last]["_boot_energy"] - res[first]["_boot_energy"]
            res["trend"] = {"from": first, "to": last, "energy_change": res[last]["energy"] - res[first]["energy"],
                            "energy_change_ci95": ci_or_none(d),
                            "spearman_band_order": spearman(list(range(len(names))), [res[k]["energy"] for k in names])}
        for k in names:
            res[k].pop("_boot_energy")
        out[f"{temp:.1f}"] = res
    return out


# ---------- Arm A ----------

def arm_a(R: Ref, reps: int, rng) -> dict:
    train_all = np.load(SK_DIR / "ref" / "train_all.npz")
    T_all = train_all[EMB].astype(np.float64)
    if int(train_all["n_empty"]) != 0:
        raise SystemExit("training-chair embeddings are not in line order (some were empty)")
    H_out = np.load(SK_DIR / "ref" / "heldout.npz")[EMB].astype(np.float64)
    runs, seed_boots, curves = {}, {}, {}
    for size in ps.SIZES:
        for seed in ps.SEEDS_A:
            run = SK_DIR / "runs" / ps.run_name_a(size, seed)
            if not (run / "meta.json").exists():
                continue
            meta = json.loads((run / "meta.json").read_text())
            if "seconds" not in meta:
                continue
            lines = np.array(meta["subset_lines"])
            T = T_all[lines]
            pick = (np.arange(len(T)) if len(T) <= ps.N_TRAIN_REF else
                    np.sort(np.random.default_rng([ps.PERM_SEED, seed, 99]).choice(len(T), ps.N_TRAIN_REF, replace=False)))
            Tref = T[pick]
            Dt = within(Tref)
            tspread = matched_spread(Dt, 16, 200, np.random.default_rng([ps.PERM_SEED, size, seed]))
            tboot = boot_spread(Dt, boot_counts(len(Tref), reps, rng))
            # copying baseline: how close new people's chairs (held out) sit to this training subset
            held_nn = cosine_distances(H_out, T).min(1)
            best = ps.best_checkpoint(meta["heldout_loss"])
            rr = {"size": size, "seed": seed, "n_train": meta["n_train"], "best_step": best,
                  "heldout_loss": {int(k): v for k, v in meta["heldout_loss"].items()},
                  "train_loss": {int(k): v for k, v in meta["train_loss_eval"].items()},
                  "train_spread": tspread, "train_recog": float(recognized(Tref, CHAIR, R.protos).mean()),
                  "heldout_nn": float(held_nn.mean()), "points": {}}
            for ck, step in (("final", STEPS[-1]), ("best", best)):
                for temp in ps.TEMPS_A:
                    z = np.load(run / "emb" / f"{sample_name(step, temp)}.npz")
                    X, n_empty = z[EMB].astype(np.float64), int(z["n_empty"])
                    n_all = len(X) + n_empty
                    rec = recognized(X, CHAIR, R.protos) if len(X) else np.zeros(0, bool)
                    ind_rec = np.concatenate([rec.astype(float), np.zeros(n_empty)])
                    ind_fail = np.concatenate([np.zeros(len(X)), np.ones(n_empty)])
                    dp, dm = proto_distances(X, R.people), proto_distances(X, R.muse)
                    nn = cosine_distances(X, T).min(1)
                    d = within(X)
                    sp = matched_spread(d, 16, 200, np.random.default_rng([ps.PERM_SEED, size, seed, step]))
                    pt = {"n": len(X), "n_empty": n_empty, "fail": n_empty / n_all, "recog": float(ind_rec.mean()),
                          "recog_drawn": float(rec.mean()) if len(X) else None, "spread": sp,
                          "spread_minus_train": sp - tspread, "d_people": float(dp.mean()), "d_muse": float(dm.mean()),
                          "nn_train": float(nn.mean()), "copy_gap": float(nn.mean() - held_nn.mean())}
                    sb = boot_spread(d, boot_counts(len(X), reps, rng))
                    boots = {"fail": ps.boot_mean(ind_fail, reps, rng), "recog": ps.boot_mean(ind_rec, reps, rng),
                             "spread": sb, "spread_minus_train": sb - tboot,
                             "d_people": ps.boot_mean(dp, reps, rng), "d_muse": ps.boot_mean(dm, reps, rng),
                             "copy_gap": ps.boot_mean(nn, reps, rng) - ps.boot_mean(held_nn, reps, rng)}
                    rr["points"][f"{ck}|{temp:.1f}"] = pt
                    seed_boots[(size, seed, ck, temp)] = boots
            # the learning curve at temperature 1 (descriptive)
            curve = {}
            for step in STEPS:
                z = np.load(run / "emb" / f"{sample_name(step, ps.PRIMARY_TEMP_A)}.npz")
                X, n_empty = z[EMB].astype(np.float64), int(z["n_empty"])
                if len(X) >= 16:
                    rec = recognized(X, CHAIR, R.protos)
                    curve[step] = {"recog": float(rec.sum() / (len(X) + n_empty)),
                                   "spread": matched_spread(cosine_distances(X), 16, 50, np.random.default_rng(step)),
                                   "d_people": float(proto_distances(X, R.people).mean())}
            curves[(size, seed)] = curve
            runs[(size, seed)] = rr
    return summarize_a(runs, seed_boots, curves, reps, rng)


MEASURES_A = [("recog", +1, "P1"), ("spread", -1, "P2"), ("fail", -1, "P3"), ("spread_minus_train", 0, ""),
              ("d_people", 0, ""), ("d_muse", 0, "E2"), ("copy_gap", 0, "E3")]


def two_level(boot_by_seed: list, picks: np.ndarray) -> np.ndarray:
    sb = np.stack(boot_by_seed)  # S x R
    return sb[picks, np.arange(sb.shape[1])[:, None]].mean(1)


def summarize_a(runs: dict, seed_boots: dict, curves: dict, reps: int, rng) -> dict:
    rows, tests = [], {}
    S = len(ps.SEEDS_A)
    picks = rng.integers(0, S, (reps, S))
    for ck in ("final", "best"):
        for temp in ps.TEMPS_A:
            pkey = f"{ck}|{temp:.1f}"
            for size in ps.SIZES:
                seeds = [s for s in ps.SEEDS_A if (size, s) in runs]
                if not seeds:
                    continue
                row = {"size": size, "checkpoint": ck, "temp": temp, "n_seeds": len(seeds),
                       "best_steps": [runs[(size, s)]["best_step"] for s in seeds] if ck == "best" else None,
                       "train_spread": float(np.mean([runs[(size, s)]["train_spread"] for s in seeds]))}
                for col, _, _ in MEASURES_A:
                    vals = [runs[(size, s)]["points"][pkey][col] for s in seeds]
                    tb = t_interval(vals)
                    bb = two_level([seed_boots[(size, s, ck, temp)][col] for s in seeds], picks[:, :len(seeds)] % len(seeds))
                    row[col] = {"mean": tb["mean"], "t_ci95": tb["ci95"], "ci95": ci_or_none(bb), "per_seed": vals}
                rows.append(row)
            # the contrast 20,000 - 100 (paired by seed) and the slope on log10(n)
            lo, hi = ps.SIZES[0], ps.SIZES[-1]
            seeds = [s for s in ps.SEEDS_A if (lo, s) in runs and (hi, s) in runs]
            if not seeds:
                continue
            res = {}
            for col, pred, label in MEASURES_A:
                diff = [np.asarray(seed_boots[(hi, s, ck, temp)][col]) - np.asarray(seed_boots[(lo, s, ck, temp)][col])
                        for s in seeds]
                bb = two_level(diff, picks[:, :len(seeds)] % len(seeds))
                pts = [(math.log10(sz), runs[(sz, s)]["points"][pkey][col]) for (sz, s) in runs]
                x, y = np.array(pts).T
                slope = float(np.polyfit(x, y, 1)[0]) if len(set(y)) > 1 else 0.0
                per_seed = [runs[(hi, s)]["points"][pkey][col] - runs[(lo, s)]["points"][pkey][col] for s in seeds]
                c = ci_or_none(bb)
                res[col] = {"test": label, "contrast": float(np.mean(per_seed)), "ci95": c,
                            "t_ci95": t_interval(per_seed)["ci95"], "per_seed": per_seed, "slope_log10n": slope,
                            "verdict": ps.verdict(c, slope, pred) if pred else None}
            tests[pkey] = res
    run_rows = []
    for (size, seed), rr in sorted(runs.items()):
        run_rows.append({k: v for k, v in rr.items() if k not in ("heldout_loss", "train_loss")}
                        | {"heldout_loss_final": rr["heldout_loss"][STEPS[-1]],
                           "heldout_loss_best": rr["heldout_loss"][rr["best_step"]],
                           "train_loss_final": rr["train_loss"][STEPS[-1]]})
    curve_rows = []
    for size in ps.SIZES:
        seeds = [s for s in ps.SEEDS_A if (size, s) in curves]
        for step in STEPS:
            have = [curves[(size, s)][step] for s in seeds if step in curves[(size, s)]]
            loss = [runs[(size, s)]["heldout_loss"][step] for s in seeds]
            if have:
                curve_rows.append({"size": size, "step": step, "n_seeds": len(have),
                                   **{k: float(np.mean([h[k] for h in have])) for k in ("recog", "spread", "d_people")},
                                   "heldout_loss": float(np.mean(loss))})
    return {"rows": rows, "tests": tests, "runs": run_rows, "curves": curve_rows}


# ---------- main ----------

def predictions(fam_tests: dict, a_tests: dict) -> dict:
    """The plan's three predictions, primary verdicts first, then every check."""
    out = {}
    for col, label, a_col in (("recog_all", "P1", "recog"), ("spread", "P2", "spread"), ("failure_rate", "P3", "fail")):
        prim = fam_tests.get(f"{ps.PRIMARY_FAMILY}|{ps.PRIMARY_TEMP_B:.1f}", {}).get(col, {})
        checks = {k: v.get(col, {}).get("verdict") for k, v in fam_tests.items()}
        a_prim = a_tests.get(f"final|{ps.PRIMARY_TEMP_A:.1f}", {}).get(a_col, {})
        a_checks = {k: v.get(a_col, {}).get("verdict") for k, v in a_tests.items()}
        out[label] = {"model_size": {"primary": prim.get("verdict"), "contrast": prim.get("contrast"),
                                     "ci95": prim.get("contrast_ci95"), "checks": checks},
                      "data_size": {"primary": a_prim.get("verdict"), "contrast": a_prim.get("contrast"),
                                    "ci95": a_prim.get("ci95"), "checks": a_checks}}
    return out


def reader_check(rows: list) -> dict | None:
    """The exploratory zero-shot reader (scripts/plato_scale_reader.py, added after the plan): the share of samples
    Google SigLIP 2 reads as 'chair' among the 35 concept names. Failures count as not a chair, as in recog_all."""
    p = ps.SCALE_DIR / "reader_siglip.json"
    if not p.exists():
        return None
    r = json.loads(p.read_text())
    out = {"model": r["model"], "template": r["template"], "added_after_plan": True,
           "people": float(np.mean([x == "chair" for x in r["people"]])),
           "muse_image": float(np.mean([x == "chair" for x in r["muse_image"]])), "arm_b": {}, "arm_a": {}}
    n_by = {f"{x['key']}_t{x['temp']:.1f}": x["n"] for x in rows}
    for name, labels in r["arm_b"].items():
        key, temp = name.rsplit("_t", 1)
        out["arm_b"][f"{key}|{temp}"] = sum(v == "chair" for v in labels.values()) / n_by.get(name, ps.N_B)
    for size in ps.SIZES:
        for ck in ("final", "best"):
            vals = [sum(v == "chair" for v in e["labels"]) / e["n_all"] for s in ps.SEEDS_A
                    if (e := r["arm_a"].get(f"{ps.run_name_a(size, s)}|{ck}"))]
            if vals:
                out["arm_a"][f"{size}|{ck}"] = {"mean": float(np.mean(vals)), "range": [min(vals), max(vals)],
                                                "per_seed": vals}
    return out


def cost() -> dict:
    from metalesionlab import meta_api

    by = {}
    if meta_api.LEDGER.exists():
        for line in meta_api.LEDGER.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                if e.get("tag") in ("plato_scale", "plato_scale_paramcheck"):
                    by[e["model"]] = by.get(e["model"], 0.0) + e["usd"]
    return {"meta_api_usd": sum(by.values()), "by_model": by}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--public", type=Path)
    ap.add_argument("--skip-a", action="store_true", help="Arm B only (while Arm A is still training)")
    args = ap.parse_args()
    np.seterr(divide="ignore", invalid="ignore")  # a bootstrap of a tiny set can draw one picture: that replicate is NaN
    rng = np.random.default_rng(ps.GEN_SEED)
    R = Ref(rng)
    rows, boots, X_by = arm_b(R, args.reps, rng)
    fam = family_tests(rows, boots)
    e1 = cross_family(rows, X_by, args.reps, rng)
    A = {"rows": [], "tests": {}, "runs": [], "curves": []} if args.skip_a else arm_a(R, args.reps, rng)
    res = {"about": "An AI growing up: does an AI's idea of a chair change with more data and a bigger model? "
                    "docs/plato_scale.md; plan docs/plato_scale_plan.md",
           "credits": CREDITS, "prompt": ps.PROMPT, "embedder": f"{DINO_MODEL} ({EMB})", "reps": args.reps,
           "models": [{"key": m.key, "label": m.label, "family": m.family, "hf": m.hf, "revision": m.revision,
                       "params_b": m.params_b, "licence": m.licence, "kind": m.kind,
                       "precision": "fp8 weights" if m.fp8 else ("API" if m.kind == "api" else "bf16")}
                      for m in ps.MODELS],
           "skipped": ps.SKIPPED, "anchors": R.anchors(),
           "arm_b": {"rows": rows, "family_tests": fam, "cross_family": e1},
           "arm_a": A, "predictions": predictions(fam, A["tests"]), "reader_check": reader_check(rows),
           "cost": cost()}
    res = no_nan(res)
    (ps.SCALE_DIR / "results.json").write_text(json.dumps(res, indent=1))
    report(res)
    if args.public:
        errs = ps.validate_public(res)
        if errs:
            raise SystemExit("public file would be invalid: " + "; ".join(errs[:5]))
        args.public.write_text(json.dumps(res, indent=1) + "\n")
        print(f"wrote {args.public}")


def report(res: dict):
    a = res["anchors"]
    print(f"people: recog {a['people']['recog']:.2f} spread@12 {a['people']['spread_n12']:.3f}; "
          f"Muse Image: recog {a['muse_image']['recog']:.2f} spread {a['muse_image']['spread']:.3f}")
    print(f"{'model':18} {'T':>4} {'fail':>5} {'recog':>6} {'spread':>7} {'ratio':>6} {'dPeople':>8} {'dMuse':>6}")
    for r in res["arm_b"]["rows"]:
        f = lambda v: "   -  " if v is None else f"{v:6.3f}"  # noqa: E731
        print(f"{r['label']:18} {r['temp']:4.1f} {r['failure_rate']:5.2f} {r['recog_all']:6.2f} {f(r['spread'])} "
              f"{f(r['spread_ratio'])} {f(r['d_people'])} {f(r['d_muse'])}")
    for k, v in res["arm_b"]["family_tests"].items():
        print(k, {c: (round(v[c].get("contrast") or 0, 3), v[c].get("contrast_ci95"), v[c].get("verdict"))
                  for c in ("recog_all", "spread", "failure_rate") if c in v})
    print("E1", json.dumps(res["arm_b"]["cross_family"])[:600])
    for r in res["arm_a"]["rows"]:
        if r["temp"] == 1.0:
            print(r["checkpoint"], r["size"], {c: round(r[c]["mean"], 3) for c, _, _ in MEASURES_A})
    for k, v in res["arm_a"]["tests"].items():
        print("A", k, {c: (round(v[c]["contrast"], 3), v[c]["ci95"], v[c]["verdict"]) for c in v})
    print("predictions", json.dumps(res["predictions"])[:800])
    print("cost", res["cost"])


if __name__ == "__main__":
    main()

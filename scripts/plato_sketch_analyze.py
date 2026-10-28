"""Watch an AI learn what a chair is: the pre-registered analysis (docs/plato_sketch_plan.md).

Usage: python -I scripts/plato_sketch_analyze.py [--model small|big] [--reps 2000] [--public public_data/plato_lifespan.json]

--model small (default) is the original plan: the GPU runs copied to $PLATO_LIFESPAN_DIR/sketch/seeds/
(runs/<concept>_s<seed>/{emb,meta.json} and ref/). --model big is the plan's addendum, the larger Sketch-RNN in
sketch/big/ (runs/big_s<seed>/, ref/); its test uses the fresh seeds only (plato_sketch.MODELS). Also reads the adult (Quick, Draw!) prototypes of the 21 candidates in $PLATO_DIR/embeddings/human/. Per seed x
checkpoint x temperature: recognizable, distance to the adult prototype, spread (matched n = 16), spread minus
the 1,000 training drawings'. Across seeds: mean and 95% t-interval. The primary test (P1) and its relatives use
the two-level bootstrap as well (seeds, then drawings, plus the reference's drawings; 2,000 replicates).
Writes sketch/<dir>/results.json and, with --public, the model's block ("sketch_seeds" or "sketch_big") of the
page's statistics file (group-level numbers only: no drawings, no embeddings).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab.plato import DINO_MODEL, PLATO_DIR, ci, cosine_distances, to_jsonable  # noqa: E402
from metalesionlab.plato_lifespan import CANDIDATES, LIFESPAN_DIR, matched_spread, proto_distances, prototype, recognized  # noqa: E402
from metalesionlab.plato_sketch import (BOOT_SEED, MODELS, N_REF, QUICKDRAW_CREDIT, boot_counts, boot_spread,  # noqa: E402
                                        model_run_name, sample_name, t_interval, two_level_delta, verdict)

SEEDS_DIR = LIFESPAN_DIR / "sketch" / "seeds"  # the small model's runs; main() sets the model
CFG_NAME, CFG = "small", MODELS["small"]
MEASURES = ["recog", "d_adult", "spread", "delta"]
MIN_N = 16  # a set needs 16 drawings for the matched spread, as in the lifespan analysis


def load_emb(path: Path, emb: str) -> tuple[np.ndarray, dict]:
    z = np.load(path)
    return z[emb].astype(np.float64), {k: z[k] for k in z.files}


class Measurer:
    def __init__(self, emb: str, rng: np.random.Generator, reps: int):
        self.emb, self.rng, self.reps = emb, rng, reps
        self.protos = np.stack([prototype(np.load(PLATO_DIR / "embeddings" / "human" / f"{k}.npz")[emb].astype(np.float64))
                                for k in CANDIDATES])

    def point(self, x: np.ndarray, concept: str) -> tuple[dict, np.ndarray]:
        ki = CANDIDATES.index(concept)
        d = cosine_distances(x)
        row = {"n": len(x), "recog": float(recognized(x, ki, self.protos).mean()),
               "d_adult": float(proto_distances(x, self.protos[ki]).mean()),
               "spread": matched_spread(d, 16, 200, self.rng)}
        return row, d

    def boot(self, d: np.ndarray) -> np.ndarray:
        return boot_spread(d, boot_counts(len(d), self.reps, self.rng))


def test_block(seed_vals: dict, seed_boots: dict, ref_spread: float, ref_boot: np.ndarray, rng) -> dict:
    """P1-style test: per-seed delta (model spread - reference spread), the mean over seeds with its t-interval and
    two-level bootstrap CI, and the plan's verdict."""
    seeds = sorted(seed_vals)
    deltas = np.array([seed_vals[s] - ref_spread for s in seeds])
    tb = t_interval(deltas)
    sb = np.stack([seed_boots[s] for s in seeds])
    boot = two_level_delta(sb, ref_boot, rng)
    return {"per_seed": {str(s): {"spread": seed_vals[s], "delta": float(dv), "ci95": ci(seed_boots[s] - ref_boot)}
                         for s, dv in zip(seeds, deltas)},
            "model_spread": float(np.mean([seed_vals[s] for s in seeds])), "ref_spread": ref_spread,
            "mean_delta": tb["mean"], "t_ci95": tb["ci95"], "boot_ci95": ci(boot), "sd_across_seeds": tb["sd"],
            "relative": tb["mean"] / ref_spread, "n_seeds": len(seeds), "n_below_0": int((deltas < 0).sum()),
            "verdict": verdict(tb["ci95"], ci(boot))}


def analyze_concept(concept: str, M: Measurer, Mp: Measurer, refs_public: dict) -> dict | None:
    STEPS, TEMPS, LAST3, PRIMARY_TEMP = CFG["steps"], CFG["temps"], CFG["last3"], CFG["primary_temp"]
    runs = {s: SEEDS_DIR / "runs" / model_run_name(CFG_NAME, concept, s) for s in CFG["seeds"][concept]}
    runs = {s: p for s, p in runs.items() if (p / "emb").exists()}
    ref_path = SEEDS_DIR / "ref" / f"{concept}_train{N_REF}.npz"
    if not runs or not ref_path.exists():
        print(f"{concept}: no runs or no reference yet")
        return None
    rng = M.rng
    # the drawings it learned from
    xr, zr = load_emb(ref_path, "cls")
    ref_row, dr = M.point(xr, concept)
    ref_boot = M.boot(dr)
    ref_row.update({"spread_ci95": ci(ref_boot), "strokes": float(zr["strokes"].mean()), "points": float(zr["points"].mean())})
    xrt, _ = load_emb(SEEDS_DIR / "ref" / f"{concept}_train{N_REF}_roundtrip.npz", "cls")
    rt_row, drt = M.point(xrt, concept)
    rt_boot = M.boot(drt)
    xrp, _ = load_emb(ref_path, "patch_mean")
    rp_row, drp = Mp.point(xrp, concept)
    rp_boot = Mp.boot(drp)

    per = {}            # seed -> temp -> step -> row
    boots = {}          # (seed, temp, step) -> bootstrap spreads, for the steps the tests use
    boots_p = {}
    meta = {}
    for s, p in runs.items():
        meta[s] = json.loads((p / "meta.json").read_text()) if (p / "meta.json").exists() else {}
        per[s] = {}
        for temp in TEMPS:
            rows = {}
            for step in STEPS:
                f = p / "emb" / f"{sample_name(step, temp)}.npz"
                if not f.exists():
                    continue
                x, z = load_emb(f, "cls")
                row = {"n": int(len(x)), "n_empty": int(z["n_empty"])}
                if len(x) >= MIN_N:
                    pt, d = M.point(x, concept)
                    row.update(pt)
                    row["delta"] = row["spread"] - ref_row["spread"]
                    row["strokes"], row["points"] = float(z["strokes"].mean()), float(z["points"].mean())
                    if step in LAST3:
                        boots[(s, temp, step)] = M.boot(d)
                    if step == STEPS[-1] and temp == PRIMARY_TEMP:
                        xp, _ = load_emb(f, "patch_mean")
                        ptp, dp = Mp.point(xp, concept)
                        row["spread_patch_mean"] = ptp["spread"]
                        boots_p[s] = Mp.boot(dp)
                rows[step] = row
            per[s][temp] = rows

    # curves across seeds
    curves = {}
    for temp in TEMPS:
        c = {}
        for m in MEASURES + ["n", "strokes", "points"]:
            mean, lo, hi, ns, seedwise = [], [], [], [], {}
            for step in STEPS:
                vals = [per[s][temp].get(step, {}).get(m, np.nan) for s in runs]
                tb = t_interval(vals)
                mean.append(tb["mean"])
                lo.append(tb["ci95"][0])
                hi.append(tb["ci95"][1])
                ns.append(tb["n"])
            for s in runs:
                seedwise[str(s)] = [per[s][temp].get(step, {}).get(m, None) for step in STEPS]
            c[m] = {"mean": mean, "ci95": [[a, b] for a, b in zip(lo, hi)], "n_seeds": ns, "per_seed": seedwise}
        curves[f"t{temp}"] = c

    # P1 / P2: the last step at each temperature; robustness (a) last three steps, (b) round trip, (c) patch mean
    tests = {}
    last = STEPS[-1]
    for temp in TEMPS:
        ok = [s for s in runs if (s, temp, last) in boots]
        tests[f"t{temp}"] = {"last": test_block({s: per[s][temp][last]["spread"] for s in ok},
                                                {s: boots[(s, temp, last)] for s in ok}, ref_row["spread"], ref_boot, rng)}
        ok3 = [s for s in runs if all((s, temp, st) in boots for st in LAST3)]
        tests[f"t{temp}"]["last3"] = test_block(
            {s: float(np.mean([per[s][temp][st]["spread"] for st in LAST3])) for s in ok3},
            {s: np.mean([boots[(s, temp, st)] for st in LAST3], axis=0) for s in ok3}, ref_row["spread"], ref_boot, rng)
    okp = [s for s in runs if (s, PRIMARY_TEMP, last) in boots]
    fresh = [s for s in CFG["test_seeds"][concept] if s in runs]
    tests_all = None
    if fresh != list(runs) and len(fresh) >= 2:  # the addendum: the tests use the fresh seeds; all seeds alongside
        # (with fewer than 2 fresh runs, e.g. while they train, the tests stay over all runs: provisional only)
        tests_all, tests = tests, {}
        for temp in TEMPS:
            ok = [s for s in fresh if (s, temp, last) in boots]
            tests[f"t{temp}"] = {"last": test_block({s: per[s][temp][last]["spread"] for s in ok},
                                                    {s: boots[(s, temp, last)] for s in ok}, ref_row["spread"], ref_boot, rng)}
            ok3 = [s for s in fresh if all((s, temp, st) in boots for st in LAST3)]
            tests[f"t{temp}"]["last3"] = test_block(
                {s: float(np.mean([per[s][temp][st]["spread"] for st in LAST3])) for s in ok3},
                {s: np.mean([boots[(s, temp, st)] for st in LAST3], axis=0) for s in ok3}, ref_row["spread"], ref_boot, rng)
        okp = [s for s in okp if s in fresh]
        boots_p = {s: b for s, b in boots_p.items() if s in fresh}
    robust = {
        "roundtrip_reference": test_block({s: per[s][PRIMARY_TEMP][last]["spread"] for s in okp},
                                          {s: boots[(s, PRIMARY_TEMP, last)] for s in okp}, rt_row["spread"], rt_boot, rng),
        "patch_mean_embedding": test_block({s: per[s][PRIMARY_TEMP][last]["spread_patch_mean"] for s in boots_p}, boots_p,
                                 rp_row["spread"], rp_boot, rng),
    }

    # descriptive: when does it reach the children's and adults' recognizability, and get narrower than its teachers?
    t1 = curves[f"t{PRIMARY_TEMP}"]
    reach = {}
    for name, v in refs_public.get("recog_marks", {}).items():
        hit = [st for st, m in zip(STEPS, t1["recog"]["mean"]) if not np.isnan(m) and m >= v]
        reach[name] = {"recog": v, "first_step": hit[0] if hit else None}
    narrower_from = None
    for i, st in enumerate(STEPS):
        hi = [h for _, h in t1["delta"]["ci95"][i:]]
        if hi and all(not np.isnan(h) and h < 0 for h in hi):
            narrower_from = st
            break

    return {"concept": concept, "seeds": sorted(runs), "test_seeds": fresh,
            **({"tests_all_seeds": tests_all} if tests_all else {}),
            "n_train": {str(s): meta[s].get("n_train") for s in runs},
            "train_seconds": {str(s): meta[s].get("seconds") for s in runs},
            "reference": {**ref_row, "n_drawings": N_REF, "roundtrip": {**rt_row, "spread_ci95": ci(rt_boot)},
                          "patch_mean_spread": rp_row["spread"]},
            "adults": refs_public.get("adults"), "children": refs_public.get("children"),
            "curves": curves, "tests": tests, "robustness": robust, "recognizable_reached": reach,
            "narrower_than_training_from_step": narrower_from,
            "runs": {str(s): {f"t{temp}": {str(st): r for st, r in per[s][temp].items()} for temp in TEMPS} for s in runs}}


def embedding_check() -> dict | None:
    """The server's DINOv2 embeddings of the Mac run's 200 training chairs against the Mac's own."""
    a = SEEDS_DIR / "ref" / "chair_mac200_check.npz"
    b = LIFESPAN_DIR / "embeddings" / "sketch" / "train_sample.npz"
    if not (a.exists() and b.exists()):
        return None
    x, y = np.load(a)["cls"].astype(np.float64), np.load(b)["cls"].astype(np.float64)
    if len(x) != len(y):
        return {"error": f"{len(x)} vs {len(y)} drawings"}
    cos = 1 - np.diag(cosine_distances(x, y))
    return {"n": int(len(x)), "mean_cosine": float(cos.mean()), "min_cosine": float(cos.min()),
            "passes": bool(cos.mean() >= 0.999)}


def public_refs(pub: dict, concept: str) -> dict:
    out = {}
    if pub and concept in pub.get("adults", {}).get("cells", {}):
        a = pub["adults"]["cells"][concept]
        out["adults"] = {m: a[m] for m in ("recog", "d_adult", "spread")}
    if pub and concept in (pub.get("children") or {}).get("cells", {}):
        cc = pub["children"]["cells"][concept]
        out["children"] = {age: {m: cc[age][m] for m in ("recog", "d_adult", "spread")} for age in ("2", "6", "10")}
        out["recog_marks"] = {f"age {age}": cc[age]["recog"] for age in ("2", "6", "10")}
    if "adults" in out:
        out.setdefault("recog_marks", {})["adults"] = out["adults"]["recog"]
    return out


def main():
    global SEEDS_DIR, CFG, CFG_NAME
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=sorted(MODELS), default="small")
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--out", type=Path, help="default: sketch/<model dir>/results.json")
    ap.add_argument("--public", type=Path, help="update this model's block of this statistics file")
    args = ap.parse_args()
    CFG_NAME, CFG = args.model, MODELS[args.model]
    SEEDS_DIR = LIFESPAN_DIR / "sketch" / CFG["dir"]
    args.out = args.out or SEEDS_DIR / "results.json"
    STEPS, TEMPS, ANIM = CFG["steps"], CFG["temps"], CFG["anim"]
    rng = np.random.default_rng(BOOT_SEED)
    M = Measurer("cls", rng, args.reps)
    Mp = Measurer("patch_mean", rng, args.reps)
    pub_path = args.public or Path(__file__).resolve().parents[1] / "public_data" / "plato_lifespan.json"
    pub = json.loads(pub_path.read_text()) if pub_path.exists() else {}
    res = {"experiment": "Watch an AI learn what a chair is: the sketch model across seeds and temperatures",
           "plan": CFG["plan"], "model": CFG["model"], "embedding_model": DINO_MODEL, "reps": args.reps,
           "steps": STEPS, "temps": TEMPS, "primary_temp": CFG["primary_temp"], "n_samples": 200, "n_reference": N_REF,
           "batch": 100,  # drawings per training step, for both models (so step x 100 = chairs seen)
           "credits": {"drawings": QUICKDRAW_CREDIT, "model": "Sketch-RNN design: Ha & Eck (2017)",
                       "embedding": "Meta DINOv2, Apache-2.0"},
           "embedding_check": embedding_check() if args.model == "small" else None, "concepts": {}}
    for concept in CFG["seeds"]:
        block = analyze_concept(concept, M, Mp, public_refs(pub, concept))
        if block:
            res["concepts"][concept] = block
    if "chair" in res["concepts"]:
        ch = res["concepts"]["chair"]
        s = str(ANIM["seed"])
        rows = ch["runs"][s][f"t{ANIM['temp']}"]
        res["animation"] = {**ANIM, "steps": STEPS, "ref_spread": ch["reference"]["spread"],
                            "spread": [rows.get(str(st), {}).get("spread") for st in STEPS],
                            "recog": [rows.get(str(st), {}).get("recog") for st in STEPS],
                            "n": [rows.get(str(st), {}).get("n") for st in STEPS]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(no_nan(to_jsonable(res)), indent=1))
    print(f"wrote {args.out}")
    report(res)
    if args.public:
        pub[CFG["public_key"]] = no_nan(to_jsonable(public_block(res)))
        args.public.write_text(json.dumps(to_jsonable(pub), indent=1))
        print(f"updated {args.public}")


def no_nan(obj):
    """JSON has no NaN: missing values (e.g. a CI from a single run) become null."""
    if isinstance(obj, dict):
        return {k: no_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [no_nan(v) for v in obj]
    if isinstance(obj, float) and obj != obj:
        return None
    return obj


def public_block(res: dict) -> dict:
    """Everything but the per-seed raw rows (kept in results.json): curves, tests, references, the animation."""
    out = {k: v for k, v in res.items() if k != "concepts"}
    out["concepts"] = {c: {k: v for k, v in b.items() if k != "runs"} for c, b in res["concepts"].items()}
    for b in out["concepts"].values():  # per-run lines only for the three measures the page draws
        b["curves"] = {t: {m: (cv if m in ("recog", "d_adult", "spread") else {k: v for k, v in cv.items() if k != "per_seed"})
                           for m, cv in c.items()} for t, c in b["curves"].items()}
    return out


def report(res: dict):
    ec = res.get("embedding_check")
    if ec:
        print(f"embedding check: {ec}")
    for concept, b in res["concepts"].items():
        r = b["reference"]
        print(f"\n{concept.upper()} ({len(b['seeds'])} seeds). Training drawings: spread {r['spread']:.3f} "
              f"{[round(v, 3) for v in r['spread_ci95']]} recog {r['recog']:.2f} d_adult {r['d_adult']:.3f}; "
              f"round trip spread {r['roundtrip']['spread']:.3f}; strokes {r['strokes']:.1f} points {r['points']:.1f}")
        for temp in res["temps"]:
            c = b["curves"][f"t{temp}"]
            print(f"  T={temp}: step " + " ".join(f"{s:>6}" for s in res["steps"]))
            for m in ("recog", "d_adult", "spread", "delta", "n"):
                print(f"    {m:8s}" + " ".join(f"{v:6.3f}" if v == v else "   nan" for v in c[m]["mean"]))
        for key in ("tests", "tests_all_seeds"):
            if key not in b:
                continue
            print(f"  {key}:")
            for temp in res["temps"]:
                for which in ("last", "last3"):
                    t = b[key][f"t{temp}"][which]
                    print(f"  T={temp} {which:5s}: spread {t['model_spread']:.3f} vs {t['ref_spread']:.3f}; delta "
                          f"{t['mean_delta']:+.4f} t {[round(v, 4) for v in t['t_ci95']]} boot "
                          f"{[round(v, 4) for v in t['boot_ci95']]}; {t['n_below_0']}/{t['n_seeds']} below 0 -> {t['verdict']}")
        for name, t in b["robustness"].items():
            print(f"  robust {name}: delta {t['mean_delta']:+.4f} t {[round(v, 4) for v in t['t_ci95']]} boot "
                  f"{[round(v, 4) for v in t['boot_ci95']]} {t['n_below_0']}/{t['n_seeds']} -> {t['verdict']}")
        print(f"  reached: {b['recognizable_reached']}; narrower than training from step {b['narrower_than_training_from_step']}")


if __name__ == "__main__":
    main()

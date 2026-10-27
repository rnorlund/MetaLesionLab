"""The life of a chair: the pre-registered analysis (docs/plato_lifespan_plan.md).

Usage: python -I scripts/plato_lifespan_analyze.py [--reps 2000] [--kids kids|kids_png] [--sd sd|sd_g4]
                                                  [--out results.json] [--public public_data/plato_lifespan.json]

Per set of drawings (children: thing x age; adults: Quick, Draw!; Muse; SDXL; each SD checkpoint):
- spread: mean pairwise cosine distance, averaged over 200 random 16-drawing subsets (matched n)
- d_adult: mean cosine distance of each drawing to the adult (Quick, Draw!) prototype; adults leave-one-out
- d_muse: the same to Muse Image's prototype; Muse leave-one-out
- recog: share whose most similar adult prototype (21 candidates) is their own thing; adults leave-one-out
- disp16: distance from the set's centroid to the adult prototype at n = 16 (secondary, no CI)
Bootstrap: within every set, drawings are resampled (2,000 replicates); group effects resample things too,
using the same replicate index in every set, so the two levels combine. Seed 20261027.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab.plato import BY_KEY, DINO_MODEL, PLATO_DIR, QUICKDRAW_CREDIT, ci, cosine_distances, to_jsonable  # noqa: E402
from metalesionlab.plato_lifespan import (AGES, AI_KEYS, APPROXIMATE, CANDIDATES, CHECKPOINTS, KIDDRAW_CREDIT,  # noqa: E402
                                          LIFESPAN_DIR, SD_CREDIT, SHARED_KEYS, TIER1_KEYS, age_equivalent,
                                          loo_proto_distances, matched_spread, proto_distances, prototype,
                                          recognized, unit)

REPO = Path(__file__).resolve().parents[1]
MEASURES = ["spread", "d_adult", "d_muse", "recog"]
LABEL = {"spread": "spread", "d_adult": "distance to the adult prototype", "d_muse": "distance to Muse's prototype",
         "recog": "recognizability"}


def load(path: Path, emb: str = "cls", n: int | None = None):
    z = np.load(path)
    x = z[emb][:n] if n else z[emb]
    return x, z


class Cell:
    """One set of drawings of one thing: point estimates and bootstrap replicates of every measure."""

    def __init__(self, x: np.ndarray, key: str, refs: dict, rng, reps: int, self_ref: str | None = None):
        ki = CANDIDATES.index(key)
        self.n = len(x)
        d = cosine_distances(x)
        da = loo_proto_distances(x) if self_ref == "adult" else proto_distances(x, refs["adult"][ki])
        dm = loo_proto_distances(x) if self_ref == "muse" else proto_distances(x, refs["muse"][key])
        rec = recognized(x, ki, refs["adult"], loo_own=x if self_ref == "adult" else None).astype(float)
        self.point = {"spread": matched_spread(d, 16, 200, rng), "d_adult": float(da.mean()),
                      "d_muse": float(dm.mean()), "recog": float(rec.mean())}
        u = unit(x)
        if self.n > 16:
            subs = [rng.choice(self.n, 16, replace=False) for _ in range(200)]
            self.point["disp16"] = float(np.mean([1 - unit(u[s].mean(0)) @ refs["adult"][ki] for s in subs]))
        else:
            self.point["disp16"] = float(1 - unit(u.mean(0)) @ refs["adult"][ki])
        idx = rng.integers(0, self.n, (reps, self.n))
        c = np.zeros((reps, self.n))
        np.add.at(c, (np.repeat(np.arange(reps), self.n), idx.ravel()), 1)
        num = ((c @ d) * c).sum(1)
        den = c.sum(1) ** 2 - (c ** 2).sum(1)
        self.boot = {"spread": num / den, "d_adult": c @ da / self.n, "d_muse": c @ dm / self.n,
                     "recog": c @ rec / self.n}
        self.centroid = unit(u.mean(0))

    def row(self) -> dict:
        return {"n": self.n, **self.point, **{f"{m}_ci95": ci(self.boot[m]) for m in MEASURES}}


def group_curve(cells: dict, keys: list[str], xs: list, t: np.ndarray, m: str):
    """Mean over things at each x, with the point and per-replicate values (things resampled by t)."""
    pts = np.array([[cells[k][x].point[m] for x in xs] for k in keys])            # K x X
    boots = np.stack([np.stack([cells[k][x].boot[m] for x in xs]) for k in keys])  # K x X x R
    reps = boots.shape[2]
    rb = boots[t, :, np.arange(reps)[:, None]].mean(1)                            # R x X
    return pts.mean(0), rb


def slope_stats(cells: dict, keys: list[str], xs: list, xv: np.ndarray, t: np.ndarray, m: str) -> dict:
    """Mean over things of the OLS slope of measure m on xv, with the two-level bootstrap CI; plus the
    quadratic (centered at 6) for ages."""
    pts = np.array([[cells[k][x].point[m] for x in xs] for k in keys])
    boots = np.stack([np.stack([cells[k][x].boot[m] for x in xs]) for k in keys])  # K x X x R
    xc = xv - xv.mean()
    s_pt = pts @ xc / (xc @ xc)                     # K
    s_b = np.einsum("kxr,x->kr", boots, xc) / (xc @ xc)  # K x R
    reps = boots.shape[2]
    g = s_b[t, np.arange(reps)[:, None]].mean(1)     # R
    out = {"mean_slope": float(s_pt.mean()), "ci95": ci(g), "share_of_things_with_same_sign":
           float(np.mean(np.sign(s_pt) == np.sign(s_pt.mean()))),
           "per_thing": {k: float(s) for k, s in zip(keys, s_pt)}}
    return out, s_pt, g


def quad_stats(cells, keys, xs, t, m, center=6.0) -> dict:
    u = np.array(xs, float) - center
    X = np.column_stack([np.ones_like(u), u, u ** 2])
    pinv = np.linalg.pinv(X)                                                       # 3 x X
    pts = np.array([[cells[k][x].point[m] for x in xs] for k in keys])
    boots = np.stack([np.stack([cells[k][x].boot[m] for x in xs]) for k in keys])
    coef_pt = pts @ pinv.T                                                         # K x 3
    coef_b = np.einsum("kxr,cx->kcr", boots, pinv)                                 # K x 3 x R
    reps = boots.shape[2]
    gb = coef_b[t, :, np.arange(reps)[:, None]].mean(1)                            # R x 3
    b, c = coef_pt[:, 1].mean(), coef_pt[:, 2].mean()
    peak_b = center - gb[:, 1] / (2 * gb[:, 2])
    peak = center - b / (2 * c)
    return {"quadratic_coef": float(c), "quadratic_coef_ci95": ci(gb[:, 2]), "linear_coef_at_6": float(b),
            "peak_age": float(peak), "peak_age_ci95": ci(peak_b),
            "share_reps_peak_inside_2_10": float(np.mean((peak_b > 2) & (peak_b < 10) & (gb[:, 2] < 0))),
            "inverted_u_supported": bool(ci(gb[:, 2])[1] < 0 and 2 < ci(peak_b)[0] and ci(peak_b)[1] < 10)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--kids", default="kids", choices=["kids", "kids_png"])
    ap.add_argument("--sd", default="sd", choices=["sd", "sd_g4"])
    ap.add_argument("--emb", default="cls", choices=["cls", "patch_mean"])
    ap.add_argument("--drop", nargs="*", default=[], help="things to leave out (robustness: sailboat)")
    ap.add_argument("--out", type=Path, default=LIFESPAN_DIR / "results.json")
    ap.add_argument("--public", type=Path, help="write the derived-statistics file (primary run only)")
    args = ap.parse_args()
    rng = np.random.default_rng(20261027)
    R = args.reps

    # references: the adult (Quick, Draw!) prototypes of the 21 candidates and Muse's prototypes
    adult_x = {k: load(PLATO_DIR / "embeddings" / "human" / f"{k}.npz", args.emb)[0] for k in CANDIDATES}
    muse_x = {k: load(PLATO_DIR / "embeddings" / "ai_doodle" / f"{k}.npz", args.emb, BY_KEY[k].n_ai)[0]
              for k in CANDIDATES}
    refs = {"adult": np.stack([prototype(adult_x[k]) for k in CANDIDATES]),
            "muse": {k: prototype(v) for k, v in muse_x.items()}}

    adults = {k: {"adult": Cell(adult_x[k], k, refs, rng, R, "adult")} for k in CANDIDATES}
    muse = {k: {"muse": Cell(muse_x[k], k, refs, rng, R, "muse")} for k in CANDIDATES}
    sdxl = {}
    for k in CANDIDATES:
        p = PLATO_DIR / "embeddings" / "ai_sdxl_doodle" / f"{k}.npz"
        if p.exists():
            sdxl[k] = {"sdxl": Cell(load(p, args.emb)[0], k, refs, rng, R)}

    # children: thing x age
    kids, kid_keys = {}, []
    for k in SHARED_KEYS:
        if k in args.drop:
            continue
        p = LIFESPAN_DIR / "embeddings" / args.kids / f"{k}.npz"
        if not p.exists():
            print(f"no children's embeddings for {k}")
            continue
        x, z = load(p, args.emb)
        ages = z["ages"]
        kids[k] = {a: Cell(x[ages == a], k, refs, rng, R) for a in AGES}
        kids[k]["all"] = int(len(x))
        kid_keys.append(k)

    # AI: checkpoint x thing
    ck_names = [c[0] for c in CHECKPOINTS]
    ksteps = np.array([c[2] for c in CHECKPOINTS], float) / 1000  # millions of steps
    ai, ai_keys = {}, []
    for k in AI_KEYS:
        if k in args.drop:
            continue
        paths = [LIFESPAN_DIR / "embeddings" / args.sd / ck / f"{k}.npz" for ck in ck_names]
        if not all(p.exists() for p in paths):
            continue
        xs = [load(p, args.emb)[0] for p in paths]
        if any(len(x) < 16 for x in xs):
            continue
        ai[k] = {ck: Cell(x, k, refs, rng, R) for ck, x in zip(ck_names, xs)}
        ai_keys.append(k)

    def tsample(keys):
        return rng.integers(0, len(keys), (R, len(keys)))

    res = {"experiment": "The life of a chair: children's drawings by age vs. Stable Diffusion training stages",
           "plan": "docs/plato_lifespan_plan.md", "embedding_model": DINO_MODEL, "embedding": args.emb,
           "children_rendering": args.kids, "sd_run": args.sd, "reps": R, "dropped_things": args.drop,
           "credits": {"children": KIDDRAW_CREDIT, "adults": QUICKDRAW_CREDIT, "sd": SD_CREDIT,
                       "muse": "Muse Image 1.0 doodles from the core Plato's Chair run"},
           "candidates": CANDIDATES, "children_things": kid_keys, "ai_things": ai_keys,
           "approximate_matches": sorted(APPROXIMATE)}

    # ---------- children ----------
    if kid_keys:
        t = tsample(kid_keys)
        ages = np.array(AGES, float)
        res["children"] = {"n_drawings": {k: kids[k]["all"] for k in kid_keys},
                           "cells": {k: {str(a): kids[k][a].row() for a in AGES} for k in kid_keys}}
        curves, tests = {}, {}
        for m in MEASURES + ["disp16"]:
            if m == "disp16":
                pts = np.array([[kids[k][a].point[m] for a in AGES] for k in kid_keys])
                curves[m] = {"mean": pts.mean(0).tolist()}
                continue
            pt, rb = group_curve(kids, kid_keys, AGES, t, m)
            curves[m] = {"mean": pt.tolist(), "ci95": [ci(rb[:, i]) for i in range(len(AGES))]}
            s, s_pt, g = slope_stats(kids, kid_keys, AGES, ages, t, m)
            tests[m] = {"linear": s}
            if m == "spread":
                tests[m]["quadratic"] = quad_stats(kids, kid_keys, AGES, t, m)
            # gap between 10-year-olds and adults, and between 2- and 10-year-olds
            gap = np.array([kids[k][10].point[m] - adults[k]["adult"].point[m] for k in kid_keys])
            gap_b = np.stack([kids[k][10].boot[m] - adults[k]["adult"].boot[m] for k in kid_keys])
            tests[m]["age10_minus_adults"] = {"mean": float(gap.mean()),
                                              "ci95": ci(gap_b[t, np.arange(R)[:, None]].mean(1))}
            ch = np.array([kids[k][10].point[m] - kids[k][2].point[m] for k in kid_keys])
            ch_b = np.stack([kids[k][10].boot[m] - kids[k][2].boot[m] for k in kid_keys])
            tests[m]["age10_minus_age2"] = {"mean": float(ch.mean()),
                                            "ci95": ci(ch_b[t, np.arange(R)[:, None]].mean(1))}
        res["children"]["curves"] = curves
        res["children"]["tests"] = tests
        lin = {m: tests[m]["linear"] for m in MEASURES}
        res["children"]["predictions"] = {
            "C1_recognizability_rises": lin["recog"]["ci95"][0] > 0,
            "C2_closer_to_adult_prototype": lin["d_adult"]["ci95"][1] < 0,
            "C3_spread_rises_then_falls": tests["spread"]["quadratic"]["inverted_u_supported"],
            "C3_spread_linear_direction": ("down" if lin["spread"]["ci95"][1] < 0 else
                                           "up" if lin["spread"]["ci95"][0] > 0 else "unclear"),
            "C4_closer_to_muse_prototype": lin["d_muse"]["ci95"][1] < 0}

    # ---------- references ----------
    def ref_summary(cells, name, keys):
        out = {"cells": {k: cells[k][name].row() for k in keys if k in cells}}
        ks = [k for k in keys if k in cells]
        for m in MEASURES + ["disp16"]:
            out[f"mean_{m}"] = float(np.mean([cells[k][name].point[m] for k in ks]))
        return out

    res["adults"] = ref_summary(adults, "adult", CANDIDATES)
    res["muse"] = ref_summary(muse, "muse", CANDIDATES)
    if sdxl:
        res["sdxl"] = ref_summary(sdxl, "sdxl", CANDIDATES)
    for name, cells in (("adults", adults), ("muse", muse), ("sdxl", sdxl)):
        if name in res:
            for setname, keys in (("children_things", kid_keys), ("tier1", TIER1_KEYS), ("ai_things", ai_keys)):
                ks = [k for k in keys if k in cells]
                if ks:
                    res[name][f"mean_over_{setname}"] = {m: float(np.mean([cells[k][list(cells[k])[0]].point[m]
                                                                          for k in ks])) for m in MEASURES + ["disp16"]}

    # ---------- AI training stages ----------
    if ai_keys:
        res["ai"] = {"checkpoints": [{"name": c[0], "repo": c[1], "cumulative_ksteps": c[2], "parent": c[3]}
                                     for c in CHECKPOINTS],
                     "cells": {k: {ck: ai[k][ck].row() for ck in ck_names} for k in ai_keys}}
        for setname, keys in (("tier1", [k for k in TIER1_KEYS if k in ai]), ("all", ai_keys)):
            if not keys:
                continue
            t = tsample(keys)
            block = {"things": keys, "curves": {}, "tests": {}}
            for m in MEASURES:
                pt, rb = group_curve(ai, keys, ck_names, t, m)
                block["curves"][m] = {"mean": pt.tolist(), "ci95": [ci(rb[:, i]) for i in range(len(ck_names))]}
                s, _, _ = slope_stats(ai, keys, ck_names, ksteps, t, m)
                d = np.array([ai[k]["v1.5"].point[m] - ai[k]["v1.1"].point[m] for k in keys])
                db = np.stack([ai[k]["v1.5"].boot[m] - ai[k]["v1.1"].boot[m] for k in keys])
                block["tests"][m] = {"slope_per_million_steps": s,
                                     "v15_minus_v11": {"mean": float(d.mean()),
                                                       "ci95": ci(db[t, np.arange(R)[:, None]].mean(1)),
                                                       "per_thing": {k: float(v) for k, v in zip(keys, d)}}}
            block["curves"]["disp16"] = {"mean": np.mean([[ai[k][ck].point["disp16"] for ck in ck_names]
                                                          for k in keys], 0).tolist()}
            tt = block["tests"]
            block["predictions"] = {
                "A1_recognizability_rises": (tt["recog"]["slope_per_million_steps"]["ci95"][0] > 0
                                             and tt["recog"]["v15_minus_v11"]["ci95"][0] > 0),
                "A2_spread_narrows": (tt["spread"]["slope_per_million_steps"]["ci95"][1] < 0
                                      and tt["spread"]["v15_minus_v11"]["ci95"][1] < 0),
                "A3_d_adult_changes": not (tt["d_adult"]["slope_per_million_steps"]["ci95"][0] <= 0
                                           <= tt["d_adult"]["slope_per_million_steps"]["ci95"][1]),
                "A3_d_muse_changes": not (tt["d_muse"]["slope_per_million_steps"]["ci95"][0] <= 0
                                          <= tt["d_muse"]["slope_per_million_steps"]["ci95"][1])}
            res["ai"][setname] = block

    # ---------- does the AI's path resemble the children's? ----------
    shared = [k for k in kid_keys if k in ai]
    if len(shared) >= 3 and "children" in res:
        t = tsample(shared)
        comp = {"things": shared, "direction": {}}
        for m in MEASURES:
            kid_s, _, _ = slope_stats(kids, shared, AGES, np.array(AGES, float), t, m)
            d = np.array([ai[k]["v1.5"].point[m] - ai[k]["v1.1"].point[m] for k in shared])
            db = np.stack([ai[k]["v1.5"].boot[m] - ai[k]["v1.1"].boot[m] for k in shared])
            ai_ci = ci(db[t, np.arange(R)[:, None]].mean(1))

            def sign(lo, hi):
                return 1 if lo > 0 else -1 if hi < 0 else 0
            ks, as_ = sign(*kid_s["ci95"]), sign(*ai_ci)
            comp["direction"][m] = {"children_slope_per_year": kid_s["mean_slope"], "children_ci95": kid_s["ci95"],
                                    "ai_v15_minus_v11": float(d.mean()), "ai_ci95": ai_ci,
                                    "children_sign": ks, "ai_sign": as_,
                                    "agree": (ks == as_) if ks and as_ else None}
        clear = [v["agree"] for v in comp["direction"].values() if v["agree"] is not None]
        comp["resembles"] = bool(clear) and all(clear)
        comp["n_measures_both_clear"] = len(clear)
        # developmental age equivalent of each checkpoint, on recognizability
        kid_pt, kid_rb = group_curve(kids, shared, AGES, t, "recog")
        ae = {}
        for ck in ck_names:
            v_pt = float(np.mean([ai[k][ck].point["recog"] for k in shared]))
            v_b = np.stack([ai[k][ck].boot["recog"] for k in shared])[t, np.arange(R)[:, None]].mean(1)
            eq = [age_equivalent(v_b[b], AGES, kid_rb[b]) for b in range(R)]
            num = np.array([e for e in eq if not isinstance(e, str)], float)
            ae[ck] = {"recog": v_pt, "age_equivalent": age_equivalent(v_pt, AGES, kid_pt),
                      "ci95": ci(num) if len(num) > R * 0.5 else None,
                      "share_reps_below_2": float(np.mean([e == "<2" for e in eq])),
                      "share_reps_beyond_10": float(np.mean([e == ">10" for e in eq]))}
        for name, cells in (("adults", adults), ("muse", muse), ("sdxl", sdxl)):
            if all(k in cells for k in shared):
                v = float(np.mean([cells[k][list(cells[k])[0]].point["recog"] for k in shared]))
                ae[name] = {"recog": v, "age_equivalent": age_equivalent(v, AGES, kid_pt)}
        comp["age_equivalent_recognizability"] = ae
        comp["children_recog_curve"] = kid_pt.tolist()
        # same direction in DINOv2 space?
        m_k, n_k = [], []
        disp_ai = {k: ai[k]["v1.5"].centroid - ai[k]["v1.1"].centroid for k in shared}
        disp_kid = {k: kids[k][10].centroid - kids[k][2].centroid for k in shared}
        A = unit(np.stack([disp_ai[k] for k in shared]))
        B = unit(np.stack([disp_kid[k] for k in shared]))
        M = A @ B.T
        m_k = np.diag(M)
        n_k = np.array([(M[i].sum() + M[:, i].sum() - 2 * M[i, i]) / (2 * (len(shared) - 1))
                        for i in range(len(shared))])
        diff = m_k - n_k
        boot = np.array([diff[rng.integers(0, len(shared), len(shared))].mean() for _ in range(R)])
        comp["displacement_direction"] = {"matched_cosine": float(m_k.mean()), "mismatched_cosine": float(n_k.mean()),
                                          "difference": float(diff.mean()), "difference_ci95": ci(boot),
                                          "per_thing": {k: float(v) for k, v in zip(shared, m_k)}}
        res["comparison"] = comp

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(to_jsonable(res), indent=1))
    print(f"wrote {args.out}")
    report(res)
    if args.public:
        write_public(res, args.public)


def report(res):
    if "children" in res:
        c = res["children"]
        print("\nCHILDREN (mean over", len(res["children_things"]), "things), ages", AGES)
        for m in MEASURES + ["disp16"]:
            print(f"  {m:8s}", " ".join(f"{v:.3f}" for v in c["curves"][m]["mean"]))
        for m in MEASURES:
            s = c["tests"][m]["linear"]
            print(f"  slope {m:8s} {s['mean_slope']:+.4f} [{s['ci95'][0]:+.4f}, {s['ci95'][1]:+.4f}] "
                  f"same sign {s['share_of_things_with_same_sign']:.2f}; age10-adult "
                  f"{c['tests'][m]['age10_minus_adults']['mean']:+.3f} {c['tests'][m]['age10_minus_adults']['ci95']}")
        q = c["tests"]["spread"]["quadratic"]
        print(f"  spread quadratic c {q['quadratic_coef']:+.5f} {q['quadratic_coef_ci95']} peak {q['peak_age']:.1f} "
              f"{q['peak_age_ci95']} inverted U: {q['inverted_u_supported']}")
        print("  predictions", c["predictions"])
    for name in ("adults", "muse", "sdxl"):
        if name in res and "mean_over_children_things" in res[name]:
            print(f"  {name:7s}", {m: round(v, 3) for m, v in res[name]["mean_over_children_things"].items()})
    if "ai" in res:
        for setname in ("tier1", "all"):
            if setname not in res["ai"]:
                continue
            b = res["ai"][setname]
            print(f"\nAI ({setname}, {len(b['things'])} things), checkpoints v1.1..v1.5")
            for m in MEASURES + ["disp16"]:
                print(f"  {m:8s}", " ".join(f"{v:.3f}" for v in b["curves"][m]["mean"]))
            for m in MEASURES:
                tt = b["tests"][m]
                print(f"  {m:8s} slope/M {tt['slope_per_million_steps']['mean_slope']:+.4f} "
                      f"{tt['slope_per_million_steps']['ci95']}  v1.5-v1.1 {tt['v15_minus_v11']['mean']:+.3f} "
                      f"{tt['v15_minus_v11']['ci95']}")
            print("  predictions", b["predictions"])
    if "comparison" in res:
        cp = res["comparison"]
        print(f"\nCOMPARISON on {len(cp['things'])} things: resembles={cp['resembles']}")
        for m, v in cp["direction"].items():
            print(f"  {m:8s} kids {v['children_sign']:+d} ai {v['ai_sign']:+d} agree {v['agree']}")
        for k, v in cp["age_equivalent_recognizability"].items():
            print(f"  {k:6s} recog {v['recog']:.3f} age-equivalent {v['age_equivalent']} {v.get('ci95')}")
        print("  direction", {k: v for k, v in cp["displacement_direction"].items() if k != "per_thing"})


def write_public(res, path: Path):
    keep_cell = ("n", "spread", "spread_ci95", "d_adult", "d_adult_ci95", "d_muse", "d_muse_ci95", "recog",
                 "recog_ci95")
    pub = {
        "about": "The life of a chair: how children's drawings (ages 2-10) and Stable Diffusion's training stages "
                 "(v1.1-v1.5) relate to a shared prototype, measured with Meta DINOv2. Group-level derived "
                 "statistics only: no drawings, no embeddings, no per-drawing values. Every children's cell pools "
                 "at least 23 drawings. See docs/plato_lifespan.md.",
        "credits": res["credits"],
        "measures": {"spread": "mean pairwise cosine distance (matched n = 16)",
                     "d_adult": "mean cosine distance to the adult (Quick, Draw!) prototype",
                     "d_muse": "mean cosine distance to Muse Image's prototype",
                     "recog": "share nearest to their own thing's adult prototype among 21 (chance 0.048)"},
        "embedding_model": res["embedding_model"],
        "children": {"ages": AGES, "things": res.get("children_things"),
                     "cells": {k: {a: {f: v[f] for f in keep_cell} for a, v in cells.items()}
                               for k, cells in res["children"]["cells"].items()},
                     "curves": res["children"]["curves"],
                     "tests": {m: {kk: vv for kk, vv in v.items() if kk != "linear"} |
                               {"linear": {kk: vv for kk, vv in v["linear"].items()}}
                               for m, v in res["children"]["tests"].items()},
                     "predictions": res["children"]["predictions"]} if "children" in res else None,
        "adults": {k: res["adults"][k] for k in res["adults"] if k.startswith("mean")},
        "muse": {k: res["muse"][k] for k in res["muse"] if k.startswith("mean")},
        "sdxl": {k: res["sdxl"][k] for k in res["sdxl"] if k.startswith("mean")} if "sdxl" in res else None,
        "ai": res.get("ai"),
        "comparison": res.get("comparison"),
    }
    path.write_text(json.dumps(to_jsonable(pub), indent=1))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()

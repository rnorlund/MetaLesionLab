"""Plato's Telephone: embed every chain picture with DINOv2 and test the pre-registered predictions.

  python scripts/plato_telephone_analyze.py [--reps 2000] [--public]

Reads $PLATO_TELEPHONE_DIR/chains/<seed>/c<k>/ (g00..g10.png and chain.json) and labels_spark.json, and the
core run's default doodles as prototypes (PlatosChair/core/embeddings/ai_doodle/). Writes results.json and
embeddings.npz in $PLATO_TELEPHONE_DIR; with --public also public_data/plato_telephone.json (derived
statistics, per-chain curves and Muse Spark's descriptions; no pictures, no embeddings). Runs on this Mac.
See docs/plato_telephone_plan.md for the measures and tests.
"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab import plato_telephone as T  # noqa: E402
from metalesionlab.plato import (CONCEPTS, DINO_MODEL, PLATO_DIR, QUICKDRAW_CREDIT, STYLES, Embedder, ci, ink_crop,  # noqa: E402
                                 to_jsonable)
from metalesionlab.plato_lifespan import loo_proto_distances, ols_slope, proto_distances, prototype, unit  # noqa: E402

PREP = "flatten_paper(21, 215) + ink_crop(256, margin 0.06, threshold 200, speck 3px)"
NG = T.GENERATIONS + 1
GENS = list(range(NG))
REPO = Path(__file__).resolve().parents[1]


def load_chains():
    pics, texts, meta = {}, {}, {}
    for s in T.SEEDS:
        for c in range(T.CHAINS):
            d = T.chain_dir(s, c)
            m = json.loads((d / "chain.json").read_text()) if (d / "chain.json").exists() else {"steps": []}
            meta[(s.key, c)] = m
            pics[(s.key, c)] = [d / T.pic_name(g) if (d / T.pic_name(g)).exists() else None for g in GENS]
            descs = [None] * NG
            for st in m["steps"]:
                descs[st["gen"]] = st["description"]
            texts[(s.key, c)] = descs
    return pics, texts, meta


def embed_all(pics):
    cache = T.TELEPHONE_DIR / "embeddings.npz"
    files = sorted(str(p.relative_to(T.TELEPHONE_DIR)) for ps in pics.values() for p in ps if p is not None)
    have = {}
    if cache.exists():
        z = np.load(cache)
        if str(z["prep"]) == PREP:
            have = dict(zip(z["files"].tolist(), z["cls"]))
    todo = [f for f in files if f not in have]
    if todo:
        emb = Embedder(DINO_MODEL)
        t0 = time.time()
        vecs = emb([ink_crop(Image.open(T.TELEPHONE_DIR / f).convert("RGB")) for f in todo])["cls"]
        have.update(zip(todo, vecs))
        print(f"embedded {len(todo)} pictures in {time.time() - t0:.0f}s", flush=True)
    keep = sorted(have)
    np.savez(cache, files=np.array(keep), cls=np.array([have[f] for f in keep]), model=DINO_MODEL, prep=PREP)
    out = np.full((len(T.SEEDS), T.CHAINS, NG, 768), np.nan)
    for i, s in enumerate(T.SEEDS):
        for c in range(T.CHAINS):
            for g, p in enumerate(pics[(s.key, c)]):
                if p is not None:
                    out[i, c, g] = have[str(p.relative_to(T.TELEPHONE_DIR))]
    return out


def core_cls(source: str, key: str) -> np.ndarray:
    return np.load(PLATO_DIR / "embeddings" / source / f"{key}.npz")["cls"]


def nan_proto_dist(e: np.ndarray, proto: np.ndarray) -> np.ndarray:
    flat = e.reshape(-1, e.shape[-1])
    ok = ~np.isnan(flat[:, 0])
    out = np.full(len(flat), np.nan)
    out[ok] = proto_distances(flat[ok], proto)
    return out.reshape(e.shape[:-1])


def pair_dists(e: np.ndarray) -> np.ndarray:
    """(n_seeds, n_chains, n_seeds, n_chains) cosine distances, NaN where a picture is missing."""
    ns, nc, _ = e.shape
    flat = e.reshape(ns * nc, -1)
    ok = ~np.isnan(flat[:, 0])
    u = np.zeros_like(flat)
    u[ok] = unit(flat[ok])
    d = 1.0 - u @ u.T
    d[~ok, :] = np.nan
    d[:, ~ok] = np.nan
    return d.reshape(ns, nc, ns, nc)


def no_nan(o):
    """NaN (a measure with no data yet, e.g. labels not bought) becomes null, so the file is strict JSON."""
    if isinstance(o, dict):
        return {k: no_nan(v) for k, v in o.items()}
    if isinstance(o, list):
        return [no_nan(v) for v in o]
    if isinstance(o, float) and o != o:
        return None
    return o


def boot_summary(point, boots):
    boots = np.asarray(boots, float)
    boots = boots[~np.isnan(boots)]
    return {"mean": point, "ci95": ci(boots) if len(boots) else [float("nan")] * 2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--public", action="store_true")
    args = ap.parse_args()

    pics, texts, meta = load_chains()
    E = embed_all(pics)
    seeds = T.SEEDS
    idx_chair = [i for i, s in enumerate(seeds) if not s.control]
    n_pics = int((~np.isnan(E[..., 0])).sum())
    complete = sum(bool(m.get("complete")) for m in meta.values())
    print(f"{n_pics} pictures, {complete} of {len(meta)} chains complete", flush=True)

    # prototypes and reference levels (the core run's default doodles)
    protos, floor, default_spread = {}, {}, {}
    for k in ("chair", "hat", "clock"):
        x = core_cls("ai_doodle", k)
        protos[k] = prototype(x)
        floor[k] = float(loo_proto_distances(x).mean())
        u = unit(x)
        dd = 1 - u @ u.T
        default_spread[k] = float(dd[np.triu_indices(len(x), 1)].mean())
    grand = prototype(np.array([prototype(core_cls("ai_doodle", c.key)) for c in CONCEPTS]))
    human_chair = prototype(core_cls("human", "chair"))
    floor_grand_chair = float(proto_distances(core_cls("ai_doodle", "chair"), grand).mean())
    floor_human_chair = float(proto_distances(core_cls("ai_doodle", "chair"), human_chair).mean())

    # per picture measures
    d_proto = np.stack([nan_proto_dist(E[i], protos[s.concept]) for i, s in enumerate(seeds)])  # (10, 3, 11)
    d_start = np.full(d_proto.shape, np.nan)
    for i in range(len(seeds)):
        for c in range(T.CHAINS):
            if not np.isnan(E[i, c, 0, 0]):
                d_start[i, c] = nan_proto_dist(E[i, c], E[i, c, 0])
    d_other = {name: nan_proto_dist(E, p) for name, p in
               (("grand", grand), ("hat", protos["hat"]), ("clock", protos["clock"]), ("human_chair", human_chair))}

    # words and labels
    kind_w = np.full(d_proto.shape, np.nan)
    cat_w = np.full(d_proto.shape, np.nan)
    for i, s in enumerate(seeds):
        for c in range(T.CHAINS):
            for g, t in enumerate(texts[(s.key, c)]):
                if t is not None:
                    kind_w[i, c, g] = T.has_word(t, s.kind_word)
                    cat_w[i, c, g] = T.has_word(t, T.CATEGORY_WORD[s.concept])
    first_kind = np.full((len(seeds), T.CHAINS), np.nan)
    first_cat = np.full((len(seeds), T.CHAINS), np.nan)
    for i, s in enumerate(seeds):
        for c in range(T.CHAINS):
            t = texts[(s.key, c)]
            if all(x is not None for x in t):
                first_kind[i, c] = T.first_loss(T.presence(t, s.kind_word))
                first_cat[i, c] = T.first_loss(T.presence(t, T.CATEGORY_WORD[s.concept]))

    lab_path = T.TELEPHONE_DIR / "labels_spark.json"
    labels = json.loads(lab_path.read_text())["items"] if lab_path.exists() else {}
    lab_kind = np.full(d_proto.shape, np.nan)
    lab_cat = np.full(d_proto.shape, np.nan)
    lab_plain = np.full(d_proto.shape, np.nan)
    lab_opt = {}
    for i, s in enumerate(seeds):
        for c in range(T.CHAINS):
            for g in GENS:
                r = labels.get(f"{s.key}/c0/g00" if g == 0 else f"{s.key}/c{c}/g{g:02d}")
                if not r or r["label"] is None:
                    continue
                n = r["n_kinds"]
                lab_kind[i, c, g] = r["label"] == r["right"]
                lab_cat[i, c, g] = r["label"] != n + 1
                lab_plain[i, c, g] = r["label"] == n
                lab_opt[(s.key, c, g)] = r["option"]

    # ---------- bootstrap over chair seeds, then chains ----------
    ch = np.array(idx_chair)
    D = [pair_dists(E[ch, :, g]) for g in GENS]
    curves = {"d_proto": d_proto, "d_start": d_start, "kind_word": kind_w, "category_word": cat_w,
              "label_kind": lab_kind, "label_category": lab_cat, "label_plain": lab_plain,
              "d_grand": d_other["grand"], "d_hat": d_other["hat"], "d_clock": d_other["clock"],
              "d_human_chair": d_other["human_chair"]}

    def stats(w):
        out = {name: [T.weighted_mean(arr[ch][:, :, g], w) for g in GENS] for name, arr in curves.items()}
        out["between"] = [T.pair_mean(D[g], w, same_seed=False) for g in GENS]
        out["within"] = [T.pair_mean(D[g], w, same_seed=True) for g in GENS]
        out["p3_diff"] = T.weighted_mean(first_kind[ch] - first_cat[ch], w)
        out["first_kind"] = T.weighted_mean(first_kind[ch], w)
        out["first_cat"] = T.weighted_mean(first_cat[ch], w)
        out["kind_share"] = T.weighted_mean(np.nanmean(kind_w[ch], axis=2), w)
        out["cat_share"] = T.weighted_mean(np.nanmean(cat_w[ch], axis=2), w)
        return out

    point = stats(np.ones((len(ch), T.CHAINS)))
    rng = np.random.default_rng(T.BOOT_SEED)
    boots = [stats(T.cluster_weights(len(ch), T.CHAINS, rng)) for _ in range(args.reps)]

    def curve(name):
        return {"mean": point[name], "ci95": [ci(np.array([b[name][g] for b in boots
                                                           if not np.isnan(b[name][g])])) if not np.isnan(point[name][g])
                                              else [float("nan")] * 2 for g in GENS]}

    def contrast(fn):
        return boot_summary(fn(point), [fn(b) for b in boots])

    last = T.GENERATIONS
    res_curves = {name: curve(name) for name in list(curves) + ["between", "within"]}
    gens_x = np.array(GENS, float)
    tests = {
        "P1_drift_to_form": {
            "prediction": "distance to the default chair falls from g00 to g10",
            "g0": point["d_proto"][0], "g10": point["d_proto"][last],
            "change": contrast(lambda s: s["d_proto"][last] - s["d_proto"][0]),
            "slope_per_generation": contrast(lambda s: ols_slope(gens_x, s["d_proto"])),
            "gap_closed": contrast(lambda s: T.gap_closed(s["d_proto"][0], s["d_proto"][last], floor["chair"])),
        },
        "P1_specificity": {
            "prediction": "the drop toward the chair prototype is larger than toward the mean of all 35 prototypes",
            "change_chair": contrast(lambda s: s["d_proto"][last] - s["d_proto"][0]),
            "change_grand": contrast(lambda s: s["d_grand"][last] - s["d_grand"][0]),
            "change_hat": contrast(lambda s: s["d_hat"][last] - s["d_hat"][0]),
            "change_clock": contrast(lambda s: s["d_clock"][last] - s["d_clock"][0]),
            "change_human_chair": contrast(lambda s: s["d_human_chair"][last] - s["d_human_chair"][0]),
            "difference": contrast(lambda s: (s["d_proto"][last] - s["d_proto"][0]) - (s["d_grand"][last] - s["d_grand"][0])),
        },
        "P2_convergence": {
            "prediction": "between-seed spread falls from g00 to g10",
            "g0": point["between"][0], "g10": point["between"][last],
            "change": contrast(lambda s: s["between"][last] - s["between"][0]),
            "slope_per_generation": contrast(lambda s: ols_slope(gens_x, s["between"])),
            "within_g10": contrast(lambda s: s["within"][last]),
            "between_minus_within_g10": contrast(lambda s: s["between"][last] - s["within"][last]),
        },
        "P3_kind_first": {
            "prediction": "the kind word is lost before the category word",
            "first_loss_kind": contrast(lambda s: s["first_kind"]),
            "first_loss_category": contrast(lambda s: s["first_cat"]),
            "difference": contrast(lambda s: s["p3_diff"]),
            "share_with_kind_word": contrast(lambda s: s["kind_share"]),
            "share_with_category_word": contrast(lambda s: s["cat_share"]),
            "label_kind_g10": contrast(lambda s: s["label_kind"][last]),
            "label_category_g10": contrast(lambda s: s["label_category"][last]),
        },
    }
    for t in tests.values():
        for k, v in t.items():
            if isinstance(v, dict) and "ci95" in v:
                lo, hi = v["ci95"]
                v["excludes_zero"] = bool(hi < 0 or lo > 0)
    tests["P1_drift_to_form"]["supported"] = tests["P1_drift_to_form"]["change"]["ci95"][1] < 0
    tests["P1_specificity"]["supported"] = tests["P1_specificity"]["difference"]["ci95"][1] < 0
    tests["P2_convergence"]["supported"] = tests["P2_convergence"]["change"]["ci95"][1] < 0
    tests["P3_kind_first"]["supported"] = tests["P3_kind_first"]["difference"]["ci95"][1] < 0

    # ---------- per seed and per chain ----------
    per_seed, chains = {}, []
    for i, s in enumerate(seeds):
        dp = d_proto[i]
        per_seed[s.key] = {
            "label": s.label, "concept": s.concept, "kind": s.kind, "control": s.control,
            "d_proto": [float(np.nanmean(dp[:, g])) if not np.all(np.isnan(dp[:, g])) else None for g in GENS],
            "d_proto_chains_g10": [float(x) for x in dp[:, last]],
            "d_start_g10": float(np.nanmean(d_start[i, :, last])),
            "kind_word_share": [float(np.nanmean(kind_w[i, :, g])) for g in GENS],
            "category_word_share": [float(np.nanmean(cat_w[i, :, g])) for g in GENS],
            "first_loss_kind": first_kind[i].tolist(), "first_loss_category": first_cat[i].tolist(),
            "label_kind_g10": int(np.nansum(lab_kind[i, :, last])), "label_kind_g0": int(np.nansum(lab_kind[i, :1, 0])),
            "label_plain_g10": int(np.nansum(lab_plain[i, :, last])),
            "label_category_g10": int(np.nansum(lab_cat[i, :, last])),
        }
        if s.control:
            per_seed[s.key]["floor"] = floor[s.concept]
            per_seed[s.key]["d_proto_change"] = float(np.nanmean(dp[:, last] - dp[:, 0]))
        for c in range(T.CHAINS):
            t = texts[(s.key, c)]
            chains.append({
                "seed": s.key, "chain": c, "complete": bool(meta[(s.key, c)].get("complete")),
                "d_proto": [None if np.isnan(x) else float(x) for x in dp[c]],
                "d_start": [None if np.isnan(x) else float(x) for x in d_start[i, c]],
                "d_grand": [None if np.isnan(x) else float(x) for x in d_other["grand"][i, c]],
                "descriptions": t,
                "kind_word": [None if x is None else T.has_word(x, s.kind_word) for x in t],
                "category_word": [None if x is None else T.has_word(x, T.CATEGORY_WORD[s.concept]) for x in t],
                "labels": [lab_opt.get((s.key, c, g)) for g in GENS],
                "word_runs": T.word_runs(t) if all(x is not None for x in t) else {},
            })

    # ---------- words (exploratory; chair chains) ----------
    chair_chains = [c for c in chains if not T.BY_KEY[c["seed"]].control and all(c["descriptions"])]
    start_words = Counter(w for c in chair_chains for w in T.content_words(c["descriptions"][0]))
    end_words = Counter(w for c in chair_chains for w in T.content_words(c["descriptions"][-1]))
    n_cc = len(chair_chains)
    common = [w for w, n in start_words.most_common() if n >= 5]
    survival = {w: float(np.mean([c["word_runs"].get(w, 0) for c in chair_chains if w in c["word_runs"]])) for w in common}
    vocab = sorted(set(start_words) | set(end_words))
    shifts = sorted(((end_words[w] - start_words[w]) / n_cc, w) for w in vocab)
    words = {
        "n_chains": n_cc,
        "common_start_words_survival": dict(sorted(survival.items(), key=lambda kv: kv[1])),
        "rising": [{"word": w, "start": start_words[w] / n_cc, "end": end_words[w] / n_cc} for d, w in shifts[::-1][:15] if d > 0],
        "falling": [{"word": w, "start": start_words[w] / n_cc, "end": end_words[w] / n_cc} for d, w in shifts[:15] if d < 0],
        "mean_words_start": float(np.mean([len(T.content_words(c["descriptions"][0])) for c in chair_chains])) if n_cc else None,
        "mean_words_end": float(np.mean([len(T.content_words(c["descriptions"][-1])) for c in chair_chains])) if n_cc else None,
        "mean_chars": [float(np.mean([len(c["descriptions"][g]) for c in chair_chains])) for g in GENS] if n_cc else [],
    }

    # ---------- the most striking chains (rules fixed here, before looking at the wall) ----------
    def pick(fn):
        cands = [c for c in chains if not T.BY_KEY[c["seed"]].control and c["complete"]]
        best = max(cands, key=fn) if cands else None
        return {"seed": best["seed"], "chain": best["chain"]} if best else None
    striking = {
        "most_drift_to_form": pick(lambda c: c["d_proto"][0] - c["d_proto"][-1]),
        "farthest_from_start": pick(lambda c: c["d_start"][-1]),
        "most_faithful": pick(lambda c: -c["d_start"][-1]),
    }

    # ---------- cost ----------
    spend = T.TELEPHONE_DIR / "spend.jsonl"
    rows = [json.loads(x) for x in spend.read_text().splitlines() if x.strip()] if spend.exists() else []
    cost = {"total_usd": sum(r["usd"] for r in rows),
            "images": sum(1 for r in rows if r["kind"] == "image"), "images_usd": sum(r["usd"] for r in rows if r["kind"] == "image"),
            "descriptions": sum(1 for r in rows if r["kind"] == "chat" and "label" not in r),
            "descriptions_usd": sum(r["usd"] for r in rows if r["kind"] == "chat" and "label" not in r),
            "labels": sum(1 for r in rows if r["kind"] == "chat" and "label" in r),
            "labels_usd": sum(r["usd"] for r in rows if r["kind"] == "chat" and "label" in r)}

    lab_g0 = {s.key: lab_opt.get((s.key, 0, 0)) for s in seeds}
    results = {
        "experiment": "Plato's Telephone", "written": time.strftime("%Y-%m-%d"),
        "n_pictures": n_pics, "n_chains": len(meta), "n_complete": complete,
        "protocol": {"describe_prompt": T.DESCRIBE_PROMPT, "image_template": STYLES["doodle"].replace("{phrase}", "{description}"), "reasoning_effort": T.REASONING_EFFORT, "generations": T.GENERATIONS,
            "chains_per_seed": T.CHAINS, "spark_model": "muse-spark-1.3", "image_model": "muse-image-1.0",
            "embedding": DINO_MODEL + " CLS, " + PREP, "bootstrap": f"{args.reps} two-level (seeds, then chains), seed {T.BOOT_SEED}"},
        "seeds": [{"key": s.key, "label": s.label, "concept": s.concept, "kind": s.kind, "control": s.control,
                   "kind_word": s.kind_word, "label_g0": lab_g0[s.key]} for s in seeds],
        "reference": {"floor": floor, "default_spread": default_spread, "floor_grand_chair": floor_grand_chair,
                      "floor_human_chair": floor_human_chair,
                      "note": "floor: Muse's default doodles' leave-one-out distance to their own prototype; "
                              "default_spread: their mean pairwise distance (core run)"},
        "gens": GENS, "curves": res_curves, "tests": tests, "per_seed": per_seed, "words": words,
        "striking": striking, "chains": chains, "cost": cost,
        "credits": {"models": "Meta Muse Spark (muse-spark-1.3) and Muse Image (muse-image-1.0); similarity: Meta DINOv2 "
                              "(facebook/dinov2-base, Apache 2.0)", "human_prototype": QUICKDRAW_CREDIT},
    }
    results = no_nan(to_jsonable(results))
    (T.TELEPHONE_DIR / "results.json").write_text(json.dumps(results, indent=1, allow_nan=False))
    print_summary(results)
    if args.public:
        public = {k: v for k, v in results.items()}
        for c in public["chains"]:
            c.pop("word_runs", None)
        public["sprites"] = {f"{c['seed']}_c{c['chain']}": f"/static/img/plato_telephone/{c['seed']}_c{c['chain']}.webp"
                             for c in public["chains"]}
        public["about"] = ("Derived statistics from Plato's Telephone (docs/plato_telephone.md): DINOv2 distances of Muse Image "
                           "pictures along 30 describe-and-draw chains, Muse Spark's descriptions (model-generated text) "
                           "and its kind labels. No pictures or embeddings.")
        (REPO / "public_data" / "plato_telephone.json").write_text(json.dumps(public, indent=1, ensure_ascii=False, allow_nan=False))
        print("wrote public_data/plato_telephone.json")


def print_summary(r):
    c, t = r["curves"], r["tests"]
    f = lambda x: "nan" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"  # noqa: E731
    print("gen  d_proto  d_start  between  within  kindW  catW  labKind  labCat  labPlain  d_grand")
    for g in r["gens"]:
        print(f"{g:3d}  " + "  ".join(f(c[k]["mean"][g]) for k in ("d_proto", "d_start", "between", "within", "kind_word",
                                                                      "category_word", "label_kind", "label_category",
                                                                      "label_plain", "d_grand")))
    print("floor", r["reference"]["floor"], "default spread", r["reference"]["default_spread"])
    for name, v in t.items():
        print(name, "supported" if v.get("supported") else "NOT supported")
        for k, x in v.items():
            if isinstance(x, dict):
                print(f"   {k}: {f(x['mean'])} {[f(y) for y in x['ci95']]}")
    for k, v in r["per_seed"].items():
        print(f"{k:14s} d_proto g0 {f(v['d_proto'][0])} g10 {f(v['d_proto'][-1])}  kind word {[None if x is None else round(x, 2) for x in v['kind_word_share']]}"
              f"  first loss {v['first_loss_kind']}  label kind g10 {v['label_kind_g10']}/3")
    print("striking", r["striking"])
    print("words", json.dumps(r["words"])[:1500])
    print("cost", r["cost"])


if __name__ == "__main__":
    main()

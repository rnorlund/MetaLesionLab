"""Prisoners of the cave: the pre-registered analysis (docs/plato_cave_twins_plan.md).

Usage: python -I scripts/plato_twins_analyze.py [--public public_data/plato_twins.json]

Reads $PLATO_TWINS_DIR (raw/, render.json, reader.json, emb/, codes/) and the 35 human prototypes in
$PLATO_DIR/embeddings/. Writes $PLATO_TWINS_DIR/results.json and, with --public, the derived statistics (plus one
quoted sentence per model) to public_data/plato_twins.json.
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
from metalesionlab import plato_twins as pt  # noqa: E402
from metalesionlab.plato import CONCEPTS, PLATO_DIR, cosine_distances, subsample_spread  # noqa: E402
from metalesionlab.plato_lifespan import prototype, recognized  # noqa: E402
from metalesionlab.plato_sketch import boot_counts, boot_spread  # noqa: E402

D = pt.TWINS_DIR
KEYS = [c.key for c in CONCEPTS]
EMB = "cls"
CREDITS = [
    "Language models: Qwen2.5-7B-Instruct, Qwen2.5-32B-Instruct, Qwen2.5-VL-7B-Instruct and Qwen2.5-VL-32B-Instruct "
    "(Alibaba Cloud, Qwen team), Apache-2.0",
    "Reader: Google SigLIP 2 (google/siglip2-so400m-patch14-384), Apache-2.0",
    "Similarity: Meta DINOv2 (facebook/dinov2-base), Apache-2.0",
    "Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0 (statistics only; no drawing is included)",
    "Qwen2.5-VL: Bai, S. et al. (2025), Qwen2.5-VL Technical Report, arXiv:2502.13923",
]


# Noticed after the key was joined, not in the plan: how many of each twin's clocks (temperature 1, drawings only)
# have hour marks (dots, ticks or numerals) around the dial, counted by eye from figures/wall_clocks.png. Reported as
# a lead, never as a test.
POSTHOC_HOUR_MARKS = {"qwen25_7b": 1, "qwen25vl_7b": 0, "qwen25_32b": 0, "qwen25vl_32b": 8}
# The by-eye chair codes counted generously: the coder's sealed notes flag four drawings as "0, borderline" (S06,
# S09, S23, S37). Joined to the key afterwards, one is Qwen2.5 32B's and three are Qwen2.5-VL 32B's. Counting them as
# chairs gives these totals (temperature 1, of 12).
POSTHOC_EYE_CHAIR_LENIENT = {"qwen25_7b": 0, "qwen25vl_7b": 1, "qwen25_32b": 1, "qwen25vl_32b": 5}


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


def fisher_greater(k_vision: int, k_text: int, n: int = pt.N) -> float:
    from scipy.stats import fisher_exact

    return float(fisher_exact([[k_vision, n - k_vision], [k_text, n - k_text]], alternative="greater").pvalue)


class Ref:
    def __init__(self):
        H = {k: np.load(PLATO_DIR / "embeddings" / "human" / f"{k}.npz")[EMB].astype(np.float64) for k in KEYS}
        self.protos = np.stack([prototype(H[k]) for k in KEYS])
        self.Dh = cosine_distances(H["chair"])
        self._hs = {}

    def human_spread(self, n: int) -> float:
        """People's spread at n, as in the scale experiment (200 random n-subsets of the 200 reference chairs)."""
        if n not in self._hs:
            self._hs[n] = float(subsample_spread(self.Dh, n, 200, np.random.default_rng([ps.GEN_SEED, n])).mean())
        return self._hs[n]


def keyed_codes(sheet: str) -> dict:
    """The by-eye codes joined to their key: (model, task, temp, i) -> codes."""
    key = json.loads((D / "codes" / f"key_{sheet}.json").read_text())
    codes = json.loads((D / "codes" / f"codes_{sheet}.json").read_text())
    return {tuple(key[sid]): c for sid, c in codes.items()}


def svg_rows(R: Ref, rng) -> tuple[list, dict]:
    rend = json.loads((D / "render.json").read_text())
    reader = json.loads((D / "reader.json").read_text())["labels"]
    eye = {"chair": keyed_codes("chair"), "clock": keyed_codes("clock")}
    rows, per = [], {}
    for m in pt.MODELS:
        for t in pt.TASKS.values():
            if not t.svg:
                continue
            for temp in t.temps:
                name = pt.raw_name(m.key, t.key, temp)
                samples = sorted(rend[name]["samples"], key=lambda s: s["i"])
                reasons = [s["reason"] for s in samples]
                fc = ps.failure_counts(reasons)
                lab = reader[name]
                read = np.array([float(lab.get(str(s["i"])) == t.concept) for s in samples])
                labels = [lab.get(str(s["i"])) for s in samples if s["reason"] is None]
                valid = np.array([float(r is None) for r in reasons])
                z = np.load(D / "emb" / f"{name}.npz")
                X, idx = z[EMB].astype(np.float64), z["idx"].astype(int)
                own = KEYS.index(t.concept)
                rec = recognized(X, own, R.protos) if len(X) else np.zeros(0, bool)
                dino = np.zeros(pt.N)
                for i, r in zip(idx, rec):
                    dino[int(i)] = float(r)
                b_read = ps.boot_mean(read, pt.REPS, rng)
                row = {"key": m.key, "label": m.label, "size": m.size, "arm": m.arm, "task": t.key, "temp": temp,
                       "n": pt.N, "valid": int(valid.sum()), "failed": fc["failed"],
                       "failures": {k: fc[k] for k in ps.FAILURES},
                       "read_as": int(read.sum()), "read_as_ci95": pt.pct_ci(b_read),
                       "read_labels": {lb: labels.count(lb) for lb in sorted(set(labels), key=lambda x: -labels.count(x))},
                       "dino_recog": int(dino.sum()),
                       "with_text": int(sum(1 for s in samples if s.get("has_text_el"))),
                       "unfinished": int(sum(1 for s in samples if s.get("finished") is False)),
                       "mean_tokens": float(np.mean([s["n_tokens"] for s in samples if s.get("n_tokens") is not None])),
                       "reused": bool(m.scale_key and t.key == "chair")}
                vecs = {"valid": valid, "read": read, "dino": dino}
                nr = len(X)
                row["spread"] = row["spread_ci95"] = row["spread_ratio"] = None
                if t.key == "chair" and nr >= 4:
                    d = cosine_distances(X)
                    np.fill_diagonal(d, 0.0)
                    row["spread"] = float(d[np.triu_indices(nr, 1)].mean())
                    bs = boot_spread(d, boot_counts(nr, pt.REPS, rng))
                    bs = bs[np.isfinite(bs)]
                    row["spread_ci95"] = pt.pct_ci(bs)
                    row["human_spread"] = R.human_spread(nr)
                    row["spread_ratio"] = row["spread"] / row["human_spread"]
                    vecs["spread_d"] = d
                if temp == pt.PRIMARY_TEMP:
                    codes = eye[t.key]
                    if t.key == "chair":
                        e = np.array([float(codes[(m.key, "chair", temp, i)]["chair"]) for i in range(pt.N)])
                        row["eye_chair"] = int(e.sum())
                        vecs["eye"] = e
                    else:
                        cs = [codes[(m.key, "clock", temp, i)] for i in range(pt.N)]
                        row["eye_face"] = int(sum(c["face"] for c in cs))
                        row["eye_hands"] = int(sum(c["hands"] for c in cs))
                        row["eye_1110"] = int(sum(c["time"] == "11:10" for c in cs))
                        row["eye_other_time"] = int(sum(c["time"] == "other" for c in cs))
                        vecs["eye"] = np.array([float(c["time"] == "11:10") for c in cs])
                rows.append(row)
                per[name] = vecs
    return rows, per


def describe_rows(rng) -> tuple[list, dict, dict]:
    eye = keyed_codes("describe")
    rows, per, agree = [], {}, {p: ([], []) for p in pt.PARTS}
    for m in pt.MODELS:
        rec = json.loads((D / "raw" / f"{pt.raw_name(m.key, 'describe', 1.0)}.json").read_text())
        samples = sorted(rec["samples"], key=lambda s: s["i"])
        codes = [eye[(m.key, "describe", 1.0, s["i"])] for s in samples]
        kw = [pt.keyword_parts(s["text"]) for s in samples]
        score = np.array([pt.rubric_score(c) for c in codes], float)
        for p in pt.PARTS:
            agree[p][0].extend(c[p] for c in codes)
            agree[p][1].extend(k[p] for k in kw)
        b = ps.boot_mean(score, pt.REPS, rng)
        words = [len(s["text"].split()) for s in samples]
        rows.append({"key": m.key, "label": m.label, "size": m.size, "arm": m.arm, "task": "describe", "temp": 1.0,
                     "n": pt.N, "valid": pt.N, "failed": 0, "read_as": None, "read_as_ci95": None,
                     "score": float(score.mean()), "score_ci95": pt.pct_ci(b),
                     "all_three": int((score == 3).sum()),
                     "parts": {p: int(sum(c[p] for c in codes)) for p in pt.PARTS},
                     "keyword_parts": {p: int(sum(k[p] for k in kw)) for p in pt.PARTS},
                     "keyword_score": float(np.mean([pt.rubric_score(k) for k in kw])),
                     "mean_words": float(np.mean(words)), "unfinished": int(sum(1 for s in samples if not s["finished"]))})
        per[m.key] = score
    agreement = {p: {"percent": float(np.mean(np.array(a) == np.array(b))), "kappa": pt.cohen_kappa(a, b),
                     "eye_yes": int(sum(a)), "keyword_yes": int(sum(b))} for p, (a, b) in agree.items()}
    return rows, per, agreement


def diff(a, b, seed_off: int) -> dict:
    d = pt.boot_diff(a, b, seed=pt.BOOT_SEED + seed_off)
    return {"diff": float(np.mean(b) - np.mean(a)), "ci95": pt.pct_ci(d)}


def pairs(rows: list, per: dict, dper: dict, rng) -> dict:
    by = {(r["key"], r["task"], r["temp"]): r for r in rows}
    out = {}
    for k, (size, (tx, vi)) in enumerate(pt.PAIRS.items()):
        p = {}
        for task, temp in (("chair", 1.0), ("chair", 0.7), ("clock", 1.0)):
            a, b = per[pt.raw_name(tx.key, task, temp)], per[pt.raw_name(vi.key, task, temp)]
            tag = f"{task}_t{temp:.1f}"
            p[tag] = {"read_as": diff(a["read"], b["read"], 10 * k + 1), "valid": diff(a["valid"], b["valid"], 10 * k + 2),
                      "dino_recog": diff(a["dino"], b["dino"], 10 * k + 3),
                      "fisher_p_read": fisher_greater(int(b["read"].sum()), int(a["read"].sum()))}
            if "eye" in a:
                p[tag]["eye"] = diff(a["eye"], b["eye"], 10 * k + 4)
            if "spread_d" in a and "spread_d" in b:  # vision - text spread, each resampled independently
                sa = boot_spread(a["spread_d"], boot_counts(len(a["spread_d"]), pt.REPS, rng))
                sb = boot_spread(b["spread_d"], boot_counts(len(b["spread_d"]), pt.REPS, rng))
                ok = np.isfinite(sa) & np.isfinite(sb)
                p[tag]["spread"] = {"diff": by[(vi.key, task, temp)]["spread"] - by[(tx.key, task, temp)]["spread"],
                                    "ci95": pt.pct_ci((sb - sa)[ok])}
        p["describe"] = diff(dper[tx.key], dper[vi.key], 10 * k + 5)
        out[size] = p
    return out


def predictions(rows: list, pr: dict) -> dict:
    p1 = {s: pt.size_verdict(pr[s]["chair_t1.0"]["read_as"]["ci95"]) for s in pt.SIZES}
    desc = {(r["key"]): r for r in rows if r["task"] == "describe"}
    p2 = {s: pt.describe_verdict(desc[pt.PAIRS[s][0].key]["score"], desc[pt.PAIRS[s][1].key]["score"],
                                 pr[s]["describe"]["ci95"]) for s in pt.SIZES}
    p1_check = {s: pt.size_verdict(pr[s]["chair_t0.7"]["read_as"]["ci95"]) for s in pt.SIZES}
    return {"P1": {"text": "The twin that has seen pictures draws chairs that are read as chairs more often than its "
                           "text-only twin, at both sizes.", "by_size": p1, "verdict": pt.overall_verdict(p1),
                   "check_t0.7": {"by_size": p1_check, "verdict": pt.overall_verdict(p1_check)}},
            "P2": {"text": "Both twins describe a chair equally well in words.", "by_size": p2,
                   "verdict": "supported" if all(v == "supported" for v in p2.values()) else
                   ("not supported" if "not supported" in p2.values() else "unclear")}}


def quotes() -> list:
    out = []
    for m in pt.MODELS:
        rec = json.loads((D / "raw" / f"{pt.raw_name(m.key, 'describe', 1.0)}.json").read_text())
        s0 = next(s for s in rec["samples"] if s["i"] == 0)
        out.append({"key": m.key, "label": m.label, "size": m.size, "arm": m.arm, "sentence": pt.first_sentence(s0["text"])})
    return out


def hashes() -> list:
    f = ROOT / "docs" / "plato_cave_twins_codes.sha256"
    return [ln for ln in f.read_text().splitlines() if ln and not ln.startswith("#")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", type=Path)
    args = ap.parse_args()
    rng = np.random.default_rng(pt.BOOT_SEED)
    R = Ref()
    rows, per = svg_rows(R, rng)
    drows, dper, agreement = describe_rows(rng)
    pr = pairs(rows, per, dper, rng)
    rows_all = rows + drows
    preds = predictions(rows_all, pr)
    reader = json.loads((ps.SCALE_DIR / "reader_siglip.json").read_text())
    anchors = {"people_read_as_chair": float(np.mean([x == "chair" for x in reader["people"]])),
               "people_spread_n12": R.human_spread(12)}
    res = no_nan({
        "about": "Prisoners of the cave (docs/plato_cave_twins_plan.md): Qwen2.5 Instruct (text only) against "
                 "Qwen2.5-VL Instruct (also trained on pictures), 7B and 32B, text-only requests, 12 answers each.",
        "credits": CREDITS,
        "models": [{"key": m.key, "label": m.label, "size": m.size, "arm": m.arm, "hf": m.hf, "revision": m.revision,
                    "params_b": m.params_b, "licence": m.licence, "precision": "fp8 weights" if m.fp8 else "bf16",
                    "chair_reused_from_scale": bool(m.scale_key)} for m in pt.MODELS],
        "tasks": {k: {"prompt": t.prompt, "temps": list(t.temps)} for k, t in pt.TASKS.items()},
        "rows": rows_all, "pairs": pr, "predictions": preds, "describe_agreement": agreement,
        "quotes": quotes(), "hashes": hashes(), "anchors": anchors, "skipped": pt.SKIPPED,
        "posthoc": {"clock_hour_marks": POSTHOC_HOUR_MARKS, "eye_chair_lenient": POSTHOC_EYE_CHAIR_LENIENT,
                    "note": "Not planned. clock_hour_marks: clocks with hour marks around the dial, counted by eye after "
                            "the analysis. eye_chair_lenient: the by-eye chair counts with the coder's sealed "
                            "'borderline' drawings counted as chairs."},
    })
    (D / "results.json").write_text(json.dumps(res, indent=1))
    print("wrote", D / "results.json")
    if args.public:
        errs = pt.validate_public(res)
        if errs:
            raise SystemExit("\n".join(errs))
        args.public.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
        print("wrote", args.public)
    report(res)


def report(res: dict):
    for r in res["rows"]:
        if r["task"] == "describe":
            print(f"{r['label']:16s} describe: score {r['score']:.2f} {r['score_ci95']}, parts {r['parts']}, "
                  f"keywords {r['keyword_parts']}")
        else:
            extra = f" eye {r.get('eye_chair', r.get('eye_1110'))}" if r["temp"] == 1.0 else ""
            sp = f" spread {r['spread']} x{r['spread_ratio']}" if r.get("spread") is not None else ""
            print(f"{r['label']:16s} {r['task']} t{r['temp']}: valid {r['valid']}/12, read {r['read_as']}/12, "
                  f"dino {r['dino_recog']}/12{extra}{sp} labels {r['read_labels']}")
    for s, p in res["pairs"].items():
        print(s, json.dumps(p))
    print(json.dumps(res["predictions"], indent=1))
    print(json.dumps(res["describe_agreement"]))


if __name__ == "__main__":
    main()

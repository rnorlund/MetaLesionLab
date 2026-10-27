"""Plato's Cave, local analysis: codes, the Muse Spark sample, shape-based errors, the human norms and the
word lens, as pre-registered in docs/plato_cave_plan.md.

  spark    Muse Spark names a seeded random sample of 50 pictures in all four versions -> spark_names.json
  rate     Muse Spark second rater (scorer.second_rater, with the stimulus attached) for every incorrect
           real-word answer -> codes "Visual" (shape-based) errors; cached in $CAVE_DIR/cache
  analyze  -> $CAVE_DIR/results.json

Inputs in $CAVE_DIR: stimuli/ (plato_cave_stimuli.py), raw/cave_glimmer.json (the GPU run, copied back) and
human_norms/silhouette_norms.csv (Wagemans et al. 2008, Table 2; not in the repository).
"""
import argparse
import csv
import io
import json
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab import plato_cave as pc  # noqa: E402
from metalesionlab.plato import ci, to_jsonable  # noqa: E402

D = pc.CAVE_DIR
CACHE = D / "cache"
SPARK_N = 50
CODES = ("Correct", "Semantic", "Formal", "Mixed", "Unrelated", "Nonword", "Neologism", "Description", "NoResponse")
MAIN_JUDGE_CACHE = Path("/Users/super/Documents/Meta_Hacking_Challenge/MetaLesionLab/runs/cache/semantic_judge.json")


TAG = "plato_cave"  # ledger tag, so this experiment's spend can be totalled


def tagged_api():
    """MetaAPI whose chat calls carry this experiment's ledger tag (the judge and rater call api.chat)."""
    from metalesionlab.meta_api import MetaAPI

    class Tagged(MetaAPI):
        def chat(self, messages, **kw):
            kw.setdefault("ledger_tag", TAG)
            return super().chat(messages, **kw)

    return Tagged()


def stimuli_meta() -> dict:
    return json.loads((D / "stimuli" / "meta.json").read_text())


def alternates() -> dict[str, tuple[str, ...]]:
    return {it["word"]: tuple(it["alternates"]) for it in stimuli_meta()["items"]}


def judge():
    """The Muse Spark meaning judge with this experiment's own cache (seeded from the project's cache, so
    pairs already asked elsewhere aren't paid for again)."""
    from metalesionlab.naming_errors import spark_semantic_judge

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "semantic_judge.json"
    if not path.exists() and MAIN_JUDGE_CACHE.exists():
        shutil.copy(MAIN_JUDGE_CACHE, path)
    return spark_semantic_judge(tagged_api(), path)


def spark_sample() -> list[str]:
    words = [it["word"] for it in stimuli_meta()["items"]]
    rng = np.random.default_rng(0)
    return sorted(rng.choice(words, SPARK_N, replace=False).tolist())


def cmd_spark(args):
    from metalesionlab.meta_api import image_data_url, retry_network, spent
    from metalesionlab.model_lab import code_answer
    from metalesionlab.test_studio import _resized_png, naming_prompt

    if spent() > 70:
        raise SystemExit("ledger above $70")
    api, start = tagged_api(), spent()
    path = D / "spark_names.json"
    out = json.loads(path.read_text()) if path.exists() else {"prompt": naming_prompt("en"), "rows": []}
    seen = {(r["word"], r["version"]) for r in out["rows"]}
    alts = alternates()
    for word in spark_sample():
        for version in pc.VERSIONS:
            if (word, version) in seen:
                continue
            png = _resized_png((D / "stimuli" / version / f"{word}.png").read_bytes(), 512)
            reply = retry_network(lambda: api.chat([{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_data_url(png)}},
                {"type": "text", "text": naming_prompt("en")}]}]))
            said = (reply.choices[0].message.content or "").strip()
            code = code_answer(word, said, "en", alts[word]).code
            out["rows"].append({"word": word, "version": version, "said": said, "code": code})
            path.write_text(json.dumps(out, indent=0))
        print(word, [(r["version"][:4], r["said"]) for r in out["rows"] if r["word"] == word],
              f"ledger ${spent():.2f}", flush=True)


def glimmer_rows() -> list[dict]:
    r = json.loads((D / "raw" / "cave_glimmer.json").read_text())
    rows = r["items"]
    for row, pic in zip(rows, r["pictures"]):
        row["word"], row["version"] = pic["word"], pic["version"]
    return rows


def recode(rows: list[dict], j) -> None:
    from metalesionlab.model_lab import code_answer

    alts = alternates()
    for row in rows:
        c = code_answer(row["word"], row["said"], "en", alts[row["word"]], j)
        row["code"], row["head"] = c.code, c.head


def cmd_rate(args):
    from metalesionlab.meta_api import spent
    from metalesionlab import scorer

    if spent() > 70:
        raise SystemExit("ledger above $70")
    scorer.CACHE_DIR = CACHE  # this experiment's own cache file
    api, start = tagged_api(), spent()
    j = judge()
    rows = glimmer_rows()
    recode(rows, j)
    targets = [r for r in rows if r["code"] in ("Semantic", "Formal", "Mixed", "Unrelated")]
    if args.spark and (D / "spark_names.json").exists():
        sp = json.loads((D / "spark_names.json").read_text())["rows"]
        recode(sp, j)
        targets += [r for r in sp if r["code"] in ("Semantic", "Formal", "Mixed", "Unrelated")]
    print(f"{len(targets)} real-word errors to rate")
    for r in targets:
        png = (D / "stimuli" / r["version"] / f"{r['word']}.png").read_bytes()
        res = scorer.second_rater(api, r["word"], r["head"] or r["said"], "en", image=png)
        print(f"{r['version']:10s} {r['word']:12s} -> {r['said']!r:16} {r['code']:9s} rater {res['code']}", flush=True)
    print(f"run ${spent() - start:.2f}")


# --- analysis -------------------------------------------------------------------------

def boot(x, reps=2000, seed=0, stat=np.mean):
    rng = np.random.default_rng(seed)
    x = np.asarray(x, float)
    return np.array([stat(x[rng.integers(0, len(x), len(x))]) for _ in range(reps)])


def mcnemar_exact(b: int, c: int) -> float:
    from scipy.stats import binomtest

    n = b + c
    return 1.0 if n == 0 else float(binomtest(min(b, c), n, 0.5).pvalue)


def accuracy_table(rows, words) -> dict:
    by = {(r["word"], r["version"]): r for r in rows}
    out = {}
    orig = np.array([by[(w, "original")]["code"] == "Correct" for w in words if (w, "original") in by], float)
    for v in pc.VERSIONS:
        ok = np.array([by[(w, v)]["code"] == "Correct" for w in words if (w, v) in by], float)
        entry = {"accuracy": float(ok.mean()), "ci95": ci(boot(ok)), "n": int(len(ok))}
        if v != "original" and len(ok) == len(orig):
            d = ok - orig
            entry["diff_vs_original"] = float(d.mean())
            entry["diff_ci95"] = ci(boot(d, seed=1))
            entry["mcnemar_p"] = mcnemar_exact(int(((orig == 1) & (ok == 0)).sum()), int(((orig == 0) & (ok == 1)).sum()))
        out[v] = entry
    return out


def load_norms() -> dict[str, dict]:
    path = D / "human_norms" / "silhouette_norms.csv"
    out = {}
    with path.open() as f:
        for r in csv.DictReader(f):
            if r["project_concept"]:
                out[r["project_concept"]] = {"sv_name": r["sv_name"], "silhouette": float(r["silhouette_rate"]) / 100,
                                             "outline": float(r["outline_rate"]) / 100,
                                             "note": r["mapping_note"]}
    return out


MEDIUM_WORDS = ("shadow", "silhouette", "outline", "shape", "blob", "outline drawing")


def medium_answers(rows, words) -> dict:
    """Per version: answers that name the picture's medium or form instead of an object (shadow,
    silhouette, outline, shape, blob) and answers of "UFO"."""
    by = {(r["word"], r["version"]): r for r in rows}
    out = {}
    for v in pc.VERSIONS:
        rs = [by[(w, v)] for w in words if (w, v) in by]
        med = [r for r in rs if r["code"] != "Correct" and any(m in r["said"].lower() for m in MEDIUM_WORDS)]
        ufo = [r for r in rs if r["code"] != "Correct" and "ufo" in r["said"].lower()]
        just = [r for r in rs if r["said"].strip().lower().rstrip(".") == "shadow"]
        out[v] = {"n": len(rs), "medium": len(med), "medium_words": sorted(r["word"] for r in med),
                  "just_shadow": len(just), "just_shadow_words": sorted(r["word"] for r in just),
                  "ufo": len(ufo), "ufo_words": sorted(r["word"] for r in ufo)}
    return out


def cmd_analyze(args):
    from metalesionlab.plato_glimmer import spearman_ci
    from metalesionlab import scorer

    scorer.CACHE_DIR = CACHE
    j = judge()
    rows = glimmer_rows()
    recode(rows, j)
    words = [it["word"] for it in stimuli_meta()["items"]]
    by = {(r["word"], r["version"]): r for r in rows}
    res = {"n_pictures": len(words), "versions": list(pc.VERSIONS), "prompt": pc.NAMING_PROMPT}
    res["glimmer_accuracy"] = accuracy_table(rows, words)

    # which objects survive
    survive = {}
    for w in words:
        ok = {v: by[(w, v)]["code"] == "Correct" for v in pc.VERSIONS}
        survive[w] = ok
    res["survival"] = {
        "all_four": sorted(w for w, ok in survive.items() if all(ok.values())),
        "lost_as_silhouette": sorted(w for w, ok in survive.items() if ok["original"] and not ok["silhouette"]),
        "lost_as_shadow": sorted(w for w, ok in survive.items() if ok["original"] and not ok["shadow"]),
        "lost_in_all_three": sorted(w for w, ok in survive.items()
                                    if ok["original"] and not (ok["outline"] or ok["silhouette"] or ok["shadow"])),
        "original_wrong": sorted(w for w, ok in survive.items() if not ok["original"]),
        "per_item": {w: {v: {"said": by[(w, v)]["said"], "code": by[(w, v)]["code"],
                             "p_name": by[(w, v)].get("p_word_final"),
                             "first_layer": by[(w, v)].get("first_correct_layer")} for v in pc.VERSIONS}
                     for w in words}}
    # robustness score per item: mean p(name) at the last layer over the three reduced versions
    rob = {w: float(np.mean([by[(w, v)].get("p_word_final") or 0 for v in ("outline", "silhouette", "shadow")]))
           for w in words}
    res["survival"]["most_robust"] = sorted(rob, key=lambda w: -rob[w])[:15]
    res["survival"]["least_robust"] = sorted(rob, key=lambda w: rob[w])[:15]
    res["survival"]["robustness_p_name"] = rob

    # error types
    rater = scorer._rater_cache._load() if (CACHE / "second_rater.json").exists() else {}

    def rater_code(r):
        from metalesionlab.scorer import SECOND_RATER_PROMPT_VERSION
        import hashlib
        png = (D / "stimuli" / r["version"] / f"{r['word']}.png").read_bytes()
        key = f"v{SECOND_RATER_PROMPT_VERSION}|en|{r['word']}|{r['head'] or r['said']}|{hashlib.sha1(png).hexdigest()[:16]}"
        hit = rater.get(key)
        return hit["code"] if hit else None

    errors = {}
    for v in pc.VERSIONS:
        rs = [by[(w, v)] for w in words]
        counts = Counter(r["code"] for r in rs)
        real = [r for r in rs if r["code"] in ("Semantic", "Formal", "Mixed", "Unrelated")]
        rated = [(r, rater_code(r)) for r in real]
        rated = [(r, c) for r, c in rated if c]
        visual = [r for r, c in rated if c == "Visual"]
        n_err = sum(r["code"] != "Correct" for r in rs)
        errors[v] = {"counts": {c: counts.get(c, 0) for c in CODES}, "n_errors": n_err,
                     "real_word_errors": len(real), "rated": len(rated),
                     "visual": len(visual), "visual_share_of_rated": len(visual) / len(rated) if rated else None,
                     "visual_share_of_errors": len(visual) / n_err if n_err else None,
                     "rater_codes": dict(Counter(c for _, c in rated)),
                     "examples": [{"word": r["word"], "said": r["said"], "code": r["code"],
                                   "rater": c} for r, c in rated][:40]}
    res["errors"] = errors
    # exploratory (not pre-registered): answers that name the medium, not the object ("Shadow"), and "UFO"
    res["medium_answers"] = medium_answers(rows, words)

    # word lens
    lens = {}
    n_layers = len(rows[0]["p_word"]) if rows and rows[0].get("p_word") else 52
    for v in pc.VERSIONS:
        curve = np.array([by[(w, v)]["p_word"] for w in words], float)
        lens[v] = {"mean_p_name_by_layer": curve.mean(0).tolist()}
        if v != "original":
            pairs = [(by[(w, "original")]["first_correct_layer"], by[(w, v)]["first_correct_layer"]) for w in words
                     if by[(w, "original")]["code"] == "Correct" and by[(w, v)]["code"] == "Correct"
                     and by[(w, "original")]["first_correct_layer"] and by[(w, v)]["first_correct_layer"]]
            if pairs:
                d = np.array([b - a for a, b in pairs], float)
                lens[v]["first_layer_pairs"] = len(pairs)
                lens[v]["first_layer_original_mean"] = float(np.mean([a for a, _ in pairs]))
                lens[v]["first_layer_version_mean"] = float(np.mean([b for _, b in pairs]))
                lens[v]["first_layer_diff"] = float(d.mean())
                lens[v]["first_layer_diff_ci95"] = ci(boot(d, seed=2))
                lens[v]["first_layer_diff_median"] = float(np.median(d))
            stab = [(by[(w, "original")]["stable_correct_layer"], by[(w, v)]["stable_correct_layer"]) for w in words
                    if by[(w, "original")]["code"] == "Correct" and by[(w, v)]["code"] == "Correct"
                    and by[(w, "original")]["stable_correct_layer"] and by[(w, v)]["stable_correct_layer"]]
            if stab:
                d = np.array([b - a for a, b in stab], float)
                lens[v]["stable_layer_diff"] = float(d.mean())
                lens[v]["stable_layer_diff_ci95"] = ci(boot(d, seed=3))
    correct_orig = [by[(w, "original")]["first_correct_layer"] for w in words
                    if by[(w, "original")]["code"] == "Correct" and by[(w, "original")]["first_correct_layer"]]
    lens["n_layers"] = n_layers
    lens["original_first_layer_mean"] = float(np.mean(correct_orig)) if correct_orig else None
    res["word_lens"] = lens

    # human norms (Wagemans et al. 2008), concept level
    norms = load_norms()
    shared = [w for w in words if w in norms]
    hum = {}
    for v, hv in (("silhouette", "silhouette"), ("outline", "outline")):
        h = np.array([norms[w][hv] for w in shared])
        ai_ok = np.array([by[(w, v)]["code"] == "Correct" for w in shared], float)
        ai_p = np.array([by[(w, v)].get("p_word_final") or 0 for w in shared], float)
        hard = h < 0.5
        easy = h > 0.9
        hum[v] = {"n": len(shared), "human_mean": float(h.mean()), "ai_accuracy": float(ai_ok.mean()),
                  "rho_correct": spearman_ci(h, ai_ok, seed=4), "rho_p_name": spearman_ci(h, ai_p, seed=5),
                  "ai_acc_human_hard": float(ai_ok[hard].mean()) if hard.any() else None, "n_human_hard": int(hard.sum()),
                  "ai_acc_human_easy": float(ai_ok[easy].mean()) if easy.any() else None, "n_human_easy": int(easy.sum()),
                  "ai_acc_human_hard_ci95": ci(boot(ai_ok[hard])) if hard.sum() > 1 else None,
                  "ai_acc_human_easy_ci95": ci(boot(ai_ok[easy])) if easy.sum() > 1 else None}
        # 2 x 2 agreement: both find it hard / easy
        both_fail = [w for w in shared if norms[w][hv] < 0.5 and by[(w, v)]["code"] != "Correct"]
        human_only = [w for w in shared if norms[w][hv] < 0.5 and by[(w, v)]["code"] == "Correct"]
        ai_only = [w for w in shared if norms[w][hv] >= 0.5 and by[(w, v)]["code"] != "Correct"]
        hum[v].update({"both_fail": both_fail, "people_fail_ai_names": human_only, "ai_fails_people_name": ai_only})
    hum["shadow_vs_human_silhouette"] = {
        "rho_correct": spearman_ci([norms[w]["silhouette"] for w in shared],
                                   [float(by[(w, "shadow")]["code"] == "Correct") for w in shared], seed=6)}
    hum["shared"] = shared
    hum["published"] = {"silhouette_mean_260": 0.647, "outline_mean_260": 0.6185, "n_items": 260,
                        "participants": "356 first-year psychology students, University of Leuven (Flemish)",
                        "scoring": "written names, '% correct concept' (synonyms and basic-level names accepted)",
                        "source": pc.CREDIT_NORMS}
    res["human"] = hum

    # Spark sample
    sp_path = D / "spark_names.json"
    if sp_path.exists():
        sp = json.loads(sp_path.read_text())["rows"]
        recode(sp, j)
        sample = sorted({r["word"] for r in sp})
        res["spark_medium_answers"] = medium_answers(sp, sample)
        res["spark"] = {"n_items": len(sample), "accuracy": accuracy_table(sp, sample),
                        "glimmer_on_same": accuracy_table(rows, sample),
                        "agreement_correctness": {
                            v: float(np.mean([(r["code"] == "Correct") == (by[(r["word"], v)]["code"] == "Correct")
                                              for r in sp if r["version"] == v])) for v in pc.VERSIONS},
                        "rows": sp}
    res["stimuli"] = {"items": stimuli_meta()["items"]}
    out = D / "results.json"
    out.write_text(json.dumps(to_jsonable(res), indent=1))
    print({v: (round(e["accuracy"], 3), [round(x, 3) for x in e["ci95"]]) for v, e in res["glimmer_accuracy"].items()})
    print("human rho silhouette", res["human"]["silhouette"]["rho_correct"])
    print("lens", {v: (lens[v].get("first_layer_diff"), lens[v].get("first_layer_diff_ci95")) for v in pc.VERSIONS[1:]})
    print("visual", {v: (errors[v]["visual"], errors[v]["rated"]) for v in pc.VERSIONS})
    print("medium", {v: (m["medium"], m["ufo"]) for v, m in res["medium_answers"].items()},
          "spark", {v: m["medium"] for v, m in res.get("spark_medium_answers", {}).items()})


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("spark").set_defaults(fn=cmd_spark)
    p = sub.add_parser("rate")
    p.add_argument("--spark", action="store_true", help="also rate Muse Spark's errors")
    p.set_defaults(fn=cmd_rate)
    sub.add_parser("analyze").set_defaults(fn=cmd_analyze)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

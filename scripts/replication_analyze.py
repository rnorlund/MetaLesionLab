"""Analyze the n = 100 replication against the first run (n = 20), with the same code. No GPU.

Pre-registered in docs/replication_plan.md. Reads:
  - Model Lab results, runs/lesion/<set>/*.json: demo_en and demo_es (first run), core100_en and
    core100_es (replication). Every answer is re-coded here with the set's final accepted names and
    no meaning judge, so old and new are coded the same way.
  - the bilingual test's results.json: runs/bilingual (first run) and runs/bilingual_core100.
Measures (numbers as in the plan):
  1. targeted vs random-unit damage, per localizer
  2. bilingual extra drop (read from the bilingual results)
  3. falling back to English: (a) bilingual, (b) Model Lab Spanish under the naming lesion
  4. error-type profile per damage site
  5. the English pivot in the word lens (read from the bilingual results)
Writes runs/replication/results.json and prints the tables for docs/replication.md.

Usage: python scripts/replication_analyze.py [--old-runs PATH] [--runs runs] [--boot 10000]
  --old-runs is the runs/ folder holding the first run (demo sets, runs/lesion/demo_*, runs/bilingual).
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np

from metalesionlab import bilingual as B
from metalesionlab import replication as R
from metalesionlab.model_lab import answer_text, rescore_result
from metalesionlab.naming_errors import classify

FEATURED = [("naming", "mlp", 0.2973), ("visual", "mlp", 0.2548), ("language", "mlp", 0.3173),
            ("naming", "heads", 0.4042)]
LOCALIZERS = {"old": {"naming": "naming_en", "visual": "visual_en", "language": "language_en"},
              "new": {"naming": "naming_c100", "visual": "visual_c100", "language": "language_c100"}}
SITES = {"vision tower": "vision_tower", "layers 40-47": "layers:40-47", "layers 0-7": "layers:0-7"}
FEATURED_DOSE = {"vision tower": 4.223, "layers 40-47": 2.828, "layers 0-7": 3.0}
TYPES = ("meaning", "sound", "self_correction", "jargon")
PREDICTED = {"meaning": "vision tower", "sound": "layers 40-47", "self_correction": "layers 40-47",
             "jargon": "layers 0-7"}
NON_EN = ("es", "fr", "pt", "es_xen")


def slug(text: str) -> str:
    """scripts/model_lab.py's file name for a condition."""
    return re.sub(r"[^a-z0-9.]+", "-", text.lower()).strip("-")[:80]


def localizer_stem(loc: str, kind: str, frac: float, control: int | None = None) -> str:
    name = f"{loc}-{kind}-mean f{frac:.4g}" + (f" random seed{control}" if control is not None else "")
    return slug(name)


def site_stem(site: str, scale: float, seed: int = 0) -> str:
    return slug(f"{site}-noise x{scale:.4g}" + (f" seed{seed}" if seed else ""))


class LabSet:
    """A Model Lab set's results, re-coded with its manifest's accepted names and no judge."""

    def __init__(self, runs: Path, name: str):
        self.name = name
        manifest = json.loads((runs / "sets" / name / "manifest.json").read_text())
        self.items = {it["word"]: it for it in manifest["items"] if it.get("status") == "kept"}
        self.alternates = {w: tuple(it.get("alternates") or ()) for w, it in self.items.items()}
        self.results = {}
        folder = runs / "lesion" / name
        for f in sorted(folder.glob("*.json")) if folder.exists() else []:
            if f.name == "index.json" or f.name.startswith("severity_"):
                continue
            self.results[f.stem] = rescore_result(json.loads(f.read_text()), None, self.alternates)
        intact = self.results.get("intact")
        self.words = [row["word"] for row in intact["items"]] if intact else []
        self.correct_words = [row["word"] for row in intact["items"] if row["code"] == "Correct"] if intact else []
        self.lang = intact["lang"] if intact else ""

    def get(self, stems: list[str]) -> list[dict]:
        return [self.results[s] for s in stems if s in self.results]


# --- 1. targeted vs random ------------------------------------------------------------------

def targeted_vs_random(lab: LabSet, names: dict[str, str], boot: int) -> dict:
    out = {}
    words = lab.correct_words
    for contrast, kind, frac in FEATURED:
        loc = names[contrast]
        target = lab.get([localizer_stem(loc, kind, frac)])
        controls = lab.get([localizer_stem(loc, kind, frac, k) for k in range(5)])
        if not target or not controls:
            continue
        a, b = R.matrix(target, words, R.correct), R.matrix(controls, words, R.correct)
        res = R.paired_bootstrap(a, b, n_boot=boot)
        res["targeted_all_pictures"] = target[0]["accuracy"]
        res["random_all_pictures"] = round(float(np.mean([c["accuracy"] for c in controls])), 4)
        res["random_by_seed"] = [c["accuracy"] for c in controls]
        res["replicated"] = res["diff"] > 0 and res["ci95"][0] > 0
        res["errors_targeted"] = _codes(target)
        res["errors_random"] = _codes(controls)
        res["echo_or_leak_targeted"] = _echo_share(target, words)
        out[f"{contrast} {kind}"] = {"localizer": loc, "fraction": frac, **res}
    return out


def _codes(results: list[dict]) -> dict:
    total = {}
    for r in results:
        for k, v in r["counts"].items():
            total[k] = total.get(k, 0) + v
    return {k: v for k, v in total.items() if v}


def _echo_share(results: list[dict], words: list[str]) -> float:
    """Share of trials whose answer repeats the instruction or leaks the chat format."""
    m = R.matrix(results, words, lambda row: "echo" in row["flags"] or bool(B.LEAK.search(row["said"])))
    return round(float(m.mean()), 4)


# --- 3b. Model Lab Spanish: falling back to English --------------------------------------------

def spanish_fallback(lab: LabSet, names_by_word: dict[str, dict], localizer: str, boot: int) -> dict | None:
    target = lab.get([localizer_stem(localizer, "mlp", 0.2973)])
    controls = lab.get([localizer_stem(localizer, "mlp", 0.2973, k) for k in range(5)])
    if not target or not controls:
        return None
    words = [w for w in lab.correct_words if w in names_by_word]
    prompt = target[0].get("prompt", "")

    def english(row):
        return B.language_of(row["said"], "es", "en", names_by_word[row["word"]], prompt)["label"] == "en"

    def english_name(row):
        names = names_by_word[row["word"]]
        return english(row) and classify(names["en"][0], answer_text(row["said"], "en"), "en",
                                         tuple(names["en"][1:])).code == "Correct"

    out = {}
    for label, fn in (("english_answer", english), ("english_name", english_name)):
        a, b = R.matrix(controls, words, fn), R.matrix(target, words, fn)
        res = R.paired_bootstrap(a, b, n_boot=boot)  # targeted minus random
        res = {"random": res["a"], "targeted": res["b"], **{k: v for k, v in res.items() if k not in ("a", "b")}}
        res["replicated"] = res["diff"] > 0 and res["ci95"][0] > 0
        out[label] = res
    out["examples"] = [row["said"][:60] for row in target[0]["items"] if row["word"] in words and english(row)][:6]
    out["accuracy_targeted"], out["accuracy_random"] = target[0]["accuracy"], round(
        float(np.mean([c["accuracy"] for c in controls])), 4)
    return out


def spanish_names(sets: Path, prefix: str) -> dict[str, dict]:
    """Spanish test word -> the item's names in every language (for language_of)."""
    return {it.target("es"): it.names for it in B.matched_items(sets, ("en", "es"), prefix=prefix)}


# --- 4. error types per damage site ---------------------------------------------------------------

def site_runs(lab: LabSet, specs: list[dict] | None, featured_only: bool = False) -> dict[str, list[dict]]:
    out = {}
    for label, site in SITES.items():
        stems = []
        for e in specs or []:
            if e.get("site") != site or e.get("method") != "noise":
                continue
            if featured_only and abs(e["noise_scale"] - FEATURED_DOSE[label]) > 1e-6:
                continue
            stems.append(site_stem(site, e["noise_scale"], e.get("seed", 0)))
        out[label] = lab.get(stems)
    return out


def error_profiles(lab: LabSet, runs_by_site: dict[str, list[dict]], boot: int) -> dict:
    words = lab.correct_words
    groups = {}
    for label, results in runs_by_site.items():
        if not results:
            continue
        flags = {}
        for r in results:
            by = {row["word"]: row for row in r["items"]}
            for w in words:
                t = R.error_types(by[w], w, lab.alternates.get(w, ()), lab.lang)
                for k, v in t.items():
                    flags.setdefault(k, []).append(v)
        n_runs = len(results)
        groups[label] = {k: np.array(v, dtype=float).reshape(n_runs, len(words)).T for k, v in flags.items()}
    if not groups:
        return {}
    out = {"runs": {g: len(runs_by_site[g]) for g in groups},
           "accuracy": {g: round(float(1 - groups[g]["error"].mean()), 4) for g in groups}}
    for t in TYPES:
        res = R.share_bootstrap({g: (groups[g]["error"], groups[g][t]) for g in groups}, n_boot=boot)
        if len(groups) == len(SITES):
            res["predicted_site"] = PREDICTED[t]
            res["replicated"] = R.largest_with_margin(res, PREDICTED[t])
        out[t] = res
    return out


# --- 2, 3a, 5. bilingual -------------------------------------------------------------------

def bilingual_summary(path: Path) -> dict | None:
    if not path.exists():
        return None
    r = json.loads(path.read_text())
    out = {"n_pictures": r["meta"]["n_pictures"], "n_runs": r["meta"]["n_runs"],
           "missing_conditions": r["meta"]["missing_conditions"], "intact": {v: r["intact"][v]["correct"]
                                                                              for v in r["intact"]}}
    out["primary"] = {v: {k: r["primary"][v][k] for k in ("diff", "ci95", "p_sign_flip", "n_items", "acc_en",
                                                          "acc_lang", "items_worse_in_lang", "items_worse_in_en")}
                      for v in NON_EN if r["primary"].get(v)}
    sw = r["switching"]["lesioned"]
    rev = r["switching"]["reverse_on_english_trials"]["item_name_in_other_language"]
    out["switching"] = {v: {"english_answers": sw[v]["english_answers"], "english_name": sw[v]["english_name"]}
                        for v in NON_EN}
    out["reverse_name"] = rev
    for v in ("es", "fr", "pt"):
        out["switching"][v]["replicated"] = sw[v]["english_name"]["ci95"][0] > rev["ci95"][1]
    out["lens"] = {}
    for v in ("es", "fr", "pt"):
        lens = r["lens"][v]
        out["lens"][v] = {"n_items": lens["n_items"], "english_top1_before_target": lens["intact_items_english_top1_any"],
                          "share": round(lens["intact_items_english_top1_any"] / max(lens["n_items"], 1), 4),
                          "peak_layer_english": lens["intact"]["peak_layer_english"],
                          "peak_mean_p_english": lens["intact"]["peak_mean_p_english"],
                          "peak_frac_top1_english": lens["intact"]["peak_frac_top1_english"],
                          "peak_frac_top1_english_layer": lens["intact"]["peak_frac_top1_english_layer"]}
        out["lens"][v]["replicated"] = out["lens"][v]["share"] >= 0.8
    out["by_group"] = {g: {v: {k: x[k] for k in ("diff", "ci95", "acc_en", "acc_lang")} for v, x in d.items() if x}
                       for g, d in r["by_group"].items()}
    out["robustness"] = {k: {kk: v[kk] for kk in ("diff", "ci95")} for k, v in
                         r["robustness_reference_stats"]["pooled"].items()}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-runs", type=Path, default=Path("runs"))
    ap.add_argument("--runs", type=Path, default=Path("runs"))
    ap.add_argument("--boot", type=int, default=10000)
    args = ap.parse_args()
    t0 = time.time()
    specs = json.loads((Path(__file__).resolve().parent / "replication" / "components_en.json").read_text())
    old_specs = [e for e in specs if e.get("seed", 0) == 0]  # the first run had one noise seed per dose

    old_en, new_en = LabSet(args.old_runs, "demo_en"), LabSet(args.runs, "core100_en")
    old_es, new_es = LabSet(args.old_runs, "demo_es"), LabSet(args.runs, "core100_es")
    res = {"meta": {"analyzed": time.strftime("%Y-%m-%d %H:%M"), "boot": args.boot,
                    "pictures": {"demo_en": len(old_en.words), "core100_en": len(new_en.words),
                                 "demo_es": len(old_es.words), "core100_es": len(new_es.words)},
                    "intact_correct": {"demo_en": len(old_en.correct_words), "core100_en": len(new_en.correct_words),
                                       "demo_es": len(old_es.correct_words), "core100_es": len(new_es.correct_words)},
                    "intact_errors": {s.name: {row["word"]: row["said"] for row in s.results["intact"]["items"]
                                               if row["code"] != "Correct"}
                                      for s in (old_en, new_en, old_es, new_es) if "intact" in s.results}}}
    # 1
    res["targeted_vs_random"] = {"old": targeted_vs_random(old_en, LOCALIZERS["old"], args.boot),
                                 "new": targeted_vs_random(new_en, LOCALIZERS["new"], args.boot),
                                 "new_original_localizers": targeted_vs_random(new_en, LOCALIZERS["old"], args.boot)}
    # 3b
    res["spanish_fallback"] = {
        "old": spanish_fallback(old_es, spanish_names(args.old_runs / "sets", "demo"), "naming_en", args.boot),
        "new": spanish_fallback(new_es, spanish_names(args.runs / "sets", "core100"), "naming_c100", args.boot),
        "new_original_localizer": spanish_fallback(new_es, spanish_names(args.runs / "sets", "core100"), "naming_en",
                                                   args.boot)}
    # 4
    res["error_profiles"] = {"old": error_profiles(old_en, site_runs(old_en, old_specs), args.boot),
                             "new": error_profiles(new_en, site_runs(new_en, specs), args.boot),
                             "old_featured_dose": error_profiles(old_en, site_runs(old_en, old_specs, True), args.boot),
                             "new_featured_dose": error_profiles(new_en, site_runs(new_en, specs, True), args.boot)}
    # 2, 3a, 5
    res["bilingual"] = {"old": bilingual_summary(args.old_runs / "bilingual" / "results.json"),
                        "new": bilingual_summary(args.runs / "bilingual_core100" / "results.json")}
    out = args.runs / "replication" / "results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    report(res)
    print(f"\n-> {out} in {time.time() - t0:.0f}s")


def _ci(x: dict | None, key: str = "diff", pct: bool = False) -> str:
    if not x:
        return "n/a"
    f = (lambda v: f"{100 * v:.1f}") if pct else (lambda v: f"{v:+.2f}")
    return f"{f(x[key])} [{f(x['ci95'][0])}, {f(x['ci95'][1])}]"


def report(res: dict) -> None:
    print("\n1. Targeted vs random (accuracy on intact-correct pictures; diff = random - targeted)")
    tv = res["targeted_vs_random"]
    for k in tv["old"].keys() | tv["new"].keys():
        o, n, s = tv["old"].get(k), tv["new"].get(k), tv["new_original_localizers"].get(k)
        row = []
        for x in (o, n, s):
            row.append(f"{x['b']:.2f} vs {x['a']:.2f}, {_ci(x)}{' *' if x['replicated'] else ''}" if x else "n/a")
        print(f"  {k:16s} old: {row[0]:38s} new: {row[1]:38s} new, old localizer: {row[2]}")
    print("\n3b. Spanish Model Lab, English answers under the naming lesion (targeted - random)")
    for k, x in res["spanish_fallback"].items():
        if x:
            ea = x["english_answer"]
            print(f"  {k:24s} targeted {ea['targeted']:.2f} random {ea['random']:.2f} diff {_ci(ea)}"
                  f"{' *' if ea['replicated'] else ''}; English name {_ci(x['english_name'])}")
    print("\n4. Error types, share of errors per site")
    for when in ("old", "new", "old_featured_dose", "new_featured_dose"):
        p = res["error_profiles"][when]
        if not p:
            continue
        print(f"  {when}: runs {p['runs']}, accuracy {p['accuracy']}")
        for t in TYPES:
            shares = "  ".join(f"{g}: {_ci(v, 'share', True)}" for g, v in p[t]["shares"].items())
            flag = "" if "replicated" not in p[t] else (" * replicated" if p[t]["replicated"] else " (not)")
            print(f"    {t:16s} {shares}{flag}")
    for when in ("old", "new"):
        b = res["bilingual"][when]
        if not b:
            print(f"\n2/3a/5 bilingual {when}: not available")
            continue
        print(f"\n2. Bilingual {when} (n = {b['n_pictures']}, {b['n_runs']} runs)")
        for v, p in b["primary"].items():
            print(f"  {v:7s} extra drop {_ci(p)}  p={p['p_sign_flip']}  worse/better {p['items_worse_in_lang']}/"
                  f"{p['items_worse_in_en']} of {p['n_items']}")
        print(f"3a. English answers / English name; reverse name {_ci(b['reverse_name'], 'mean', True)}")
        for v, s in b["switching"].items():
            print(f"  {v:7s} {_ci(s['english_answers'], 'mean', True)}  {_ci(s['english_name'], 'mean', True)}"
                  f"{' *' if s.get('replicated') else ''}")
        print("5. Lens: English top guess before the target")
        for v, s in b["lens"].items():
            print(f"  {v}: {s['english_top1_before_target']}/{s['n_items']} peak layer {s['peak_layer_english']}")


if __name__ == "__main__":
    main()

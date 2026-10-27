"""Bilingual test for the web app: the few numbers the /lab/bilingual page shows.

runs/ is not in the repository, so a deployed site can't read runs/bilingual/results.json. This writes
metalesionlab/web/data/bilingual.json from it: per-language extra drop with its CI, switch rates and a
few real English answers, dose-response points with 95% CIs for every lesion family, and the intact word
lens (pooled curves, plus per-picture curves for up to three example pictures, read from
runs/bilingual/raw/intact__<lang>__s0.json when it exists). Nothing is re-analyzed: every number is
copied from results.json, except the CIs of doses that pool two random-unit draws, which are
bootstrapped here the same way scripts/bilingual_analyze.py does it (pictures and draws, seed 0).

Rerun after scripts/bilingual_analyze.py; it adapts to any number of pictures and conditions.

Usage: python scripts/bilingual_web_export.py [--dir runs/bilingual]   (no GPU, no API calls)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

OUT = REPO / "metalesionlab" / "web" / "data" / "bilingual.json"
MAX_BYTES = 200 * 1024
SCHEMA = 1
LANGS = ("es", "fr", "pt")  # compared with English on the page; es_xen is the instruction control
NAMES = {"en": "English", "es": "Spanish", "fr": "French", "pt": "Portuguese", "es_xen": "Spanish, English instruction"}
COLORS = {"en": "#2a78d6", "es": "#eb6834", "fr": "#1baf7a", "pt": "#eda100"}  # as scripts/bilingual_figures.py
EXAMPLE_PREF = ("pineapple", "umbrella", "whistle")  # lens examples, when they are testable in that language
N_EXAMPLES = 3
N_ANSWERS = 4
N_BOOT = 4000

FAMILY_LABELS = {  # family -> (plain label, group label, what the dose means)
    "vision_tower": ("The vision part, before language", "Noise on the part that sees", "noise"),
    "naming_en mlp mean": ("Naming neurons switched off", "Units switched off", "fraction"),
    "random mlp mean": ("Random neurons, same number (control)", "Units switched off", "fraction"),
    "naming_en heads mean": ("Naming attention heads switched off", "Units switched off", "fraction"),
    "random heads mean": ("Random heads, same number (control)", "Units switched off", "fraction"),
    "pruned": ("Whole layers removed", "Layers removed", "layers"),
}


def _r(x, nd: int = 4):
    return None if x is None else round(float(x), nd)


def family_meta(fam: str, n_layers: int) -> dict:
    if fam in FAMILY_LABELS:
        label, group, kind = FAMILY_LABELS[fam]
    elif fam.startswith("layers "):
        lo, hi = (int(x) for x in fam.split()[1].split("-"))
        where = " (first)" if lo == 0 else " (last)" if hi >= n_layers - 1 else ""
        label, group, kind = f"Layers {lo}–{hi}{where}", "Noise on 8 language layers", "noise"
    else:
        label, group, kind = fam, "Other", "other"
    return {"key": fam, "label": label, "group": group, "kind": kind}


def tick(kind: str, dose) -> str:
    if dose is None:
        return "none"
    if kind == "noise":
        return f"×{dose:g}"
    if kind == "fraction":
        return f"{round(100 * dose)}%"
    if kind == "layers":
        return f"{int(dose)} layers"
    return f"{dose:g}"


def detail(kind: str, dose) -> str:
    if dose is None:
        return "the intact model"
    if kind == "noise":
        return f"noise at {dose:g}× each unit's spread"
    if kind == "fraction":
        return f"{100 * dose:.1f}% of all units"
    if kind == "layers":
        return f"{int(dose)} layers skipped"
    return f"dose {dose:g}"


def _pooled_ci(res: dict, names: list[str], variant: str) -> list:
    """Mean and 95% CI of accuracy over several conditions at one dose (the random-unit draws), with the
    analysis's bootstrap over pictures and draws."""
    from metalesionlab import bilingual as B

    words = res["meta"]["pictures"]
    runs = [r for r in res["runs"] if r["condition"] in names and r["variant"] == variant]
    if not runs:
        return None
    m = B.correct_matrix([{**r, "seed": i} for i, r in enumerate(runs)], words)
    b = B.bootstrap_mean([m], n_boot=N_BOOT)
    return [b["mean"], b["ci95"][0], b["ci95"][1]]


def dose_families(res: dict) -> list[dict]:
    conds = [c for c in res["conditions"] if c.get("group")]
    intact = next(c for c in res["conditions"] if c["condition"] == "intact")
    variants = ("en",) + LANGS + ("es_xen",)
    n_layers = len(((res.get("lens") or {}).get(LANGS[0]) or {}).get("intact", {}).get("mean_p_other") or []) or 52

    def acc(c, v):
        b = c["by_variant"].get(v)
        return None if b is None else [_r(b["accuracy"]), _r(b["accuracy_ci95"][0]), _r(b["accuracy_ci95"][1])]

    out = []
    for fam in res["dose_response"]:
        meta = family_meta(fam, n_layers)
        doses = sorted({c["dose"] for c in conds if c["family"] == fam})
        points = [{"dose": None, "tick": "none", "detail": detail(meta["kind"], None), "n_conditions": 1,
                   "acc": {v: acc(intact, v) for v in variants if v in intact["by_variant"]}}]
        for dose in doses:
            here = [c for c in conds if c["family"] == fam and c["dose"] == dose]
            if len(here) == 1:
                a = {v: acc(here[0], v) for v in variants if v in here[0]["by_variant"]}
            else:
                a = {v: _pooled_ci(res, [c["condition"] for c in here], v) for v in variants}
                a = {v: x for v, x in a.items() if x}
            points.append({"dose": dose, "tick": tick(meta["kind"], dose), "detail": detail(meta["kind"], dose),
                           "n_conditions": len(here), "seeds": sum(len(c["seeds"]) for c in here), "acc": a})
        fam_drop = (res.get("by_family") or {}).get(fam, {})
        meta["extra_drop"] = {v: {"diff": _r(fam_drop[v]["diff"]), "ci95": [_r(x) for x in fam_drop[v]["ci95"]]}
                              for v in LANGS + ("es_xen",) if fam_drop.get(v)}
        out.append({**meta, "points": points})
    return out


def condition_tally(res: dict, v: str) -> dict:
    """Lesion conditions where the language lost more than English, as much, or less (point estimates),
    and how many of them have a CI that excludes zero."""
    t = Counter()
    for c in res["conditions"]:
        d = (c.get("by_variant", {}).get(v) or {}).get("drop_minus_en")
        if not c.get("group") or not d:
            continue
        t["worse" if d["diff"] > 1e-9 else "better" if d["diff"] < -1e-9 else "tied"] += 1
        t["reliably_worse"] += d["ci95"][0] > 0
        t["reliably_better"] += d["ci95"][1] < 0
    return {k: t[k] for k in ("worse", "tied", "better", "reliably_worse", "reliably_better")}


def summary(res: dict) -> dict:
    out = {}
    for v in LANGS + ("es_xen",):
        p = res["primary"].get(v)
        if not p:
            continue
        out[v] = {"extra_drop": _r(p["diff"]), "ci95": [_r(x) for x in p["ci95"]], "acc_en": _r(p["acc_en"]),
                  "acc_lang": _r(p["acc_lang"]), "n_items": p["n_items"], "items_worse": p["items_worse_in_lang"],
                  "items_better": p["items_worse_in_en"], "p_sign_flip": p.get("p_sign_flip"),
                  "n_conditions": p["n_conditions"], "conditions": condition_tally(res, v)}
    return out


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s).lower()) if not unicodedata.combining(c)).strip()


def _first_line(s: str) -> str:
    return " ".join(str(s or "").split("\n")[0].split())


def answers(res: dict, v: str, common: set[str]) -> dict:
    """The most frequent real English answers on this language's damaged trials: the picture's English
    name (only pictures the intact model named correctly in both languages, and not a spelling that is
    also another language's name, like cactus), and task narration."""
    main = {c["condition"] for c in res["conditions"] if c.get("group")}
    shared = {w: {_fold(n) for lang, ns in by.items() if lang not in ("en", v) for n in ns}
              for w, by in res["meta"]["names"].items()}
    names, narration = Counter(), Counter()
    for r in res["runs"]:
        if r["condition"] not in main or r["variant"] != v:
            continue
        for it in r["items"]:
            said = _first_line(it.get("said"))
            if (it.get("wrong_name") and it["en"] in common and 0 < len(said.split()) <= 3
                    and _fold(said.strip(".,!")) not in shared.get(it["en"], set())):
                names[(it["en"], it["target"], said.strip(".,!"))] += 1
            elif it.get("switch") and said.lower().startswith("the user") and '"' not in said:
                narration[said] += 1
    seen, picked = set(), []
    for (en, target, said), n in names.most_common():
        if en in seen:
            continue
        seen.add(en)
        picked.append({"picture": en, "target": target, "said": said[:40], "n": n})
        if len(picked) == N_ANSWERS:
            break
    narr = narration.most_common(1)
    return {"names": picked, "narration": (narr[0][0][:80] + "…") if narr else None}


def trial_counts(res: dict, v: str) -> dict:
    main = {c["condition"] for c in res["conditions"] if c.get("group")}
    runs = [r for r in res["runs"] if r["condition"] in main and r["variant"] == v]
    return {"trials": sum(r["n"] for r in runs), "switch": sum(r.get("switch_n") or 0 for r in runs),
            "name_in_other_language": sum(r.get("wrong_name_n") or 0 for r in runs)}


def switching(res: dict) -> dict:
    sw = res["switching"]["lesioned"]
    rev = res["switching"]["reverse_on_english_trials"]

    def mc(x):
        return {"mean": _r(x["mean"]), "ci95": [_r(y) for y in x["ci95"]]}

    out = {}
    for v in LANGS + ("es_xen",):
        if v not in sw:
            continue
        common = set(res["common_correct"].get(v, []))
        share = sw[v]["english_share_of_errors"]
        out[v] = {"english_answers": mc(sw[v]["english_answers"]), "english_name": mc(sw[v]["english_name"]),
                  "share_of_errors": _r(share["share_of_errors"]), "share_of_errors_ci95": share["ci95"],
                  "counts": trial_counts(res, v), **({"examples": answers(res, v, common)} if v in LANGS else {})}
    out["reverse"] = {"other_language_answers": mc(rev["non_english_answers"]),
                      "other_language_name": mc(rev["item_name_in_other_language"]), "counts": trial_counts(res, "en")}
    return out


def _first_majority(xs: list[float], start: int = 0):
    return next((i for i, x in enumerate(xs) if i >= start and x >= 0.5), None)


def lens(res: dict, raw_dir: Path | None) -> dict:
    out = {}
    for v in LANGS:
        L = res["lens"].get(v)
        if not L:
            continue
        it = L["intact"]
        top_en, top_l = it["frac_top1_other"], it["frac_top1_lang"]
        items = L["intact_items"]
        entry = {"n_items": L["n_items"], "items": L["items"], "n_layers": len(it["mean_p_other"]),
                 "mean_p": {"english": it["mean_p_other"], "target": it["mean_p_lang"]},
                 "top1_share": {"english": top_en, "target": top_l},
                 "peak_top1_english": _r(it["peak_frac_top1_english"]), "peak_top1_layer": it["peak_frac_top1_english_layer"],
                 "peak_mean_p_english": _r(it["peak_mean_p_english"]), "peak_mean_p_layer": it["peak_layer_english"],
                 "english_majority_layer": _first_majority(top_en),
                 "target_majority_layer": _first_majority(top_l, start=it["peak_frac_top1_english_layer"]),
                 "final_mean_p_target": _r(it["final_mean_p_lang"]),
                 "items_english_first": L.get("intact_items_english_top1_any"),
                 "lesioned_english_top1_any": _r(L["lesioned"].get("share_trials_other_top1_any_layer")),
                 "examples": []}
        # Example pictures: preferred ones first, then the longest run of English top guesses.
        order = [w for w in EXAMPLE_PREF if w in items] + sorted(
            (w for w in items if w not in EXAMPLE_PREF), key=lambda w: -len(items[w]["english_top1_layers"]))
        raw = _raw_intact(raw_dir, v)
        for w in order:
            row = raw.get(w)
            if not row or not items[w]["english_top1_layers"]:
                continue
            entry["examples"].append({
                "picture": w, "target": (res["meta"]["names"].get(w, {}).get(v) or [items[w]["said"]])[0],
                "said": items[w]["said"],
                "p_english": [_r(math.exp(x)) for x in row["lens"]["logp"]["en"]],
                "p_target": [_r(math.exp(x)) for x in row["lens"]["logp"][v]],
                "top1": [str(t)[:16] for t in items[w]["top1_by_layer"]],
                "english_top1_layers": items[w]["english_top1_layers"],
                "target_top1_layers": items[w]["target_top1_layers"]})
            if len(entry["examples"]) == N_EXAMPLES:
                break
        out[v] = entry
    rev = res["lens"].get("reverse_en_trials_es_above_en", {}).get("intact")
    if rev:
        out["english_trials"] = {"english_majority_layer": _first_majority(rev["frac_top1_lang"]),
                                 "max_share_spanish_top1": _r(max(rev["frac_top1_other"]))}
    return out


def _raw_intact(raw_dir: Path | None, v: str) -> dict:
    if raw_dir is None:
        return {}
    path = raw_dir / f"intact__{v}__s0.json"
    if not path.exists():
        return {}
    run = json.loads(path.read_text())
    return {row["en"]: row for row in run.get("items", []) if row.get("lens")}


def build(res: dict, raw_dir: Path | None = None) -> dict:
    meta = res["meta"]
    trials = trial_counts(res, "en")["trials"]
    return {
        "schema": SCHEMA,
        "source": {"model": meta["model"], "precision": meta.get("precision"), "analyzed": meta.get("analyzed"),
                   "n_pictures": meta["n_pictures"], "n_conditions": meta.get("n_main_conditions"),
                   "trials_per_language": trials, "results": "runs/bilingual/results.json",
                   "doc": "docs/bilingual.md"},
        "languages": {v: {"name": NAMES[v], "color": COLORS.get(v)} for v in ("en",) + LANGS},
        "intact": {v: {"correct": x["correct"], "n": meta["n_pictures"]} for v, x in res["intact"].items()},
        "summary": summary(res),
        "switching": switching(res),
        "dose": dose_families(res),
        "lens": lens(res, raw_dir),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=REPO / "runs" / "bilingual")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    res = json.loads((args.dir / "results.json").read_text())
    raw = args.dir / "raw"
    data = build(res, raw if raw.is_dir() else None)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
    if len(text.encode()) > MAX_BYTES:
        raise SystemExit(f"bilingual.json would be {len(text.encode()) // 1024} KB; trim it below 200 KB")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    s = data["summary"]
    print(f"wrote {args.out} ({len(text.encode()) / 1024:.0f} KB): {data['source']['n_pictures']} pictures, "
          f"{len(data['dose'])} lesion families; extra drop "
          + ", ".join(f"{v} {s[v]['extra_drop']:+.2f}" for v in LANGS if v in s)
          + "; lens examples " + ", ".join(f"{v} {len(data['lens'][v]['examples'])}" for v in LANGS if v in data["lens"]))


if __name__ == "__main__":
    main()

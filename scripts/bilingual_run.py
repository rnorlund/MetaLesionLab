"""Bilingual lesion test on the GPU box (see metalesionlab/bilingual.py).

  stats   reference statistics for mean and noise lesions: pooled over every prompt (used for
          the main conditions), and English-only and Spanish-only (robustness check)
  pilot   intact naming in every language variant, printed per picture (prompt check)
  run     every planned condition (plan()), resumable: finished runs are skipped

The plan is fixed before any lesioned Spanish result is seen. Doses come from the earlier English
runs (runs/lesion/demo_en): for each band, roughly mild, moderate and severe in English.

Raw runs go to runs/bilingual/raw/<condition>__<variant>__s<seed>.json. Codes made here use no
meaning judge (accuracy never depends on it); scripts/bilingual_analyze.py re-codes everything.

Usage: python scripts/bilingual_run.py stats|pilot|run [--sets runs/sets] [--out runs/bilingual]
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import torch

from metalesionlab import bilingual as B
from metalesionlab import glimmer
from metalesionlab.lesions import LesionSpec, UnitStats, site_dims, site_spec
from metalesionlab.localizers import Localizer, localizer_spec, random_control

VARIANTS = ("en", "es", "fr", "pt", "es_xen")
NOISE_SEEDS = [0, 1, 2]
# Decoder bands and noise scales (x the unit's sd), chosen from the earlier English severity runs.
BANDS = {
    "0-7": [0.7, 1.0, 1.4],
    "8-15": [0.7, 1.0, 1.4],
    "16-23": [1.0, 2.0, 3.0],
    "24-31": [2.0, 3.5, 5.0],
    "32-39": [1.5, 2.25, 3.0],
    "40-47": [2.181, 3.0, 4.5],  # 2.181 is the dose of the original demo_en/demo_es observation
    "48-51": [3.0, 6.0, 10.0],
}
VISION = [3.831, 4.223, 4.6]
NAMING_MLP = [0.1768, 0.2973, 0.3386]  # stored severity levels of naming_en mlp mean (demo_en)
NAMING_HEADS = [0.3667, 0.4042]        # stored severity levels of naming_en heads mean
CONTROL_SEEDS = [0, 1]
PRUNED = {"pruned 27,30,47": [27, 30, 47], "pruned 10,27,30,35,47": [10, 27, 30, 35, 47]}


def plan() -> list[B.Condition]:
    C = B.Condition
    out = [C("intact", "intact")]
    for band, scales in BANDS.items():
        for s in scales:
            out.append(C(f"layers {band} noise x{s:g}", f"layers {band}", s, NOISE_SEEDS,
                         {"site": f"layers:{band}", "method": "noise", "noise_scale": s}))
    for s in VISION:
        out.append(C(f"vision_tower noise x{s:g}", "vision_tower", s, NOISE_SEEDS,
                     {"site": "vision_tower", "method": "noise", "noise_scale": s}))
    for kind, fracs in (("mlp", NAMING_MLP), ("heads", NAMING_HEADS)):
        for f in fracs:
            rec = {"localizer": "naming_en", "kind": kind, "fraction": f, "method": "mean"}
            out.append(C(f"naming_en {kind} mean f{f:g}", f"naming_en {kind} mean", f, [0], rec))
            for k in CONTROL_SEEDS:
                out.append(C(f"naming_en {kind} mean f{f:g} random{k}", f"random {kind} mean", f, [0],
                             {**rec, "control_seed": k}))
    for name, layers in PRUNED.items():
        out.append(C(name, "pruned", float(len(layers)), [0], {}, skip=layers))
    # Robustness: the same lesions scaled by English-only or Spanish-only reference statistics.
    for stats in ("en", "es"):
        for name, rec, dose, seeds in (
                ("layers 0-7 noise x1", {"site": "layers:0-7", "method": "noise", "noise_scale": 1.0}, 1.0, NOISE_SEEDS),
                ("layers 40-47 noise x3", {"site": "layers:40-47", "method": "noise", "noise_scale": 3.0}, 3.0, NOISE_SEEDS),
                ("vision_tower noise x4.223", {"site": "vision_tower", "method": "noise", "noise_scale": 4.223}, 4.223,
                 NOISE_SEEDS),
                ("naming_en mlp mean f0.2973", {"localizer": "naming_en", "kind": "mlp", "fraction": 0.2973,
                                               "method": "mean"}, 0.2973, [0])):
            out.append(C(f"{name} [stats {stats}]", f"robustness stats {stats}", dose, seeds, rec, stats=stats,
                         variants=("en", "es")))
    return out


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9.,]+", "-", text.lower()).strip("-")[:90]


def make_spec(cond: B.Condition, seed: int, dims, runs: Path) -> LesionSpec:
    rec = cond.recipe
    if not rec:
        return LesionSpec(name=cond.name)
    if "site" in rec:
        spec = site_spec(rec["site"], rec["method"], float(rec.get("noise_scale", 1.0)), seed=seed)
    else:
        loc = Localizer.load(runs / "localizers" / f"{rec['localizer']}.pt")
        spec = localizer_spec(loc, rec["kind"], float(rec["fraction"]), rec["method"])
        if "control_seed" in rec:
            spec = random_control(spec, dims, seed=int(rec["control_seed"]))
    spec.name = cond.name
    return spec


def stats_file(out: Path, which: str) -> Path:
    return out / "cache" / f"unit_stats_{which}.pt"


def log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def cmd_stats(args, model, processor):
    for which, variants in (("pooled", ("en", "es", "fr", "pt")), ("en", ("en",)), ("es", ("es",))):
        path = stats_file(args.out, which)
        if path.exists():
            log(f"{path} exists")
            continue
        t0 = time.time()
        st = B.pooled_unit_stats(model, processor, args.sets, variants)
        st.save(path)
        log(f"stats {which}: {st.n_tokens} tokens ({st.n_image_tokens} image) in {time.time() - t0:.0f}s -> {path}")


def cmd_pilot(args, model, processor):
    items = B.matched_items(args.sets)
    tests = B.build_tests(processor, items, VARIANTS, args.batch)
    by = {it.en: it for it in items}
    for v, test in tests.items():
        r = B.run_test(model, processor, test, None, None)
        r.update(condition="pilot intact", family="pilot", seed=0)
        B.code_run(r, by)
        log(f"{v}: acc {r['accuracy']:.2f} switch {r['switch_n']} mixed {r['mixed_n']} ({r['seconds']}s)")
        for row in r["items"]:
            print(f"    {row['en']:11s} {row['target']:12s} {row['said']!r:32s} {row['code']:11s} {row['lang_label']}")
        (args.out / "pilot").mkdir(parents=True, exist_ok=True)
        (args.out / "pilot" / f"intact__{v}.json").write_text(json.dumps(r, ensure_ascii=False))


def cmd_run(args, model, processor):
    items = B.matched_items(args.sets)
    by = {it.en: it for it in items}
    tests = B.build_tests(processor, items, VARIANTS, args.batch)
    dims = site_dims(model)
    stats = {w: UnitStats.load(stats_file(args.out, w), model.device) for w in ("pooled", "en", "es")}
    conds = [c for c in plan() if not args.only or re.search(args.only, c.family)]
    raw = args.out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (args.out / "plan.json").write_text(json.dumps([c.__dict__ for c in plan()], indent=1))
    t_all = time.time()
    for ci, cond in enumerate(conds):
        for seed in cond.seeds:
            spec = make_spec(cond, seed, dims, args.runs)
            line = []
            for v in cond.variants:
                path = raw / f"{slug(cond.name)}__{v}__s{seed}.json"
                if path.exists():
                    continue
                r = B.run_test(model, processor, tests[v], spec, stats[cond.stats], cond.skip or None)
                r.update(condition=cond.name, family=cond.family, dose=cond.dose, seed=seed, stats=cond.stats,
                         skip=cond.skip, spec=spec.to_dict(units=False), units=spec.counts(dims))
                B.code_run(r, by)
                path.write_text(json.dumps(r, ensure_ascii=False, separators=(",", ":")))
                line.append(f"{v} {r['accuracy']:.2f}/sw{r['switch_n']}")
            if line:
                log(f"[{ci + 1}/{len(conds)}] {cond.name} s{seed}: " + "  ".join(line))
    log(f"done in {time.time() - t_all:.0f}s")


def cmd_ids(args):
    """First-token ids of every item's names per language (tokenizer only), for the lens analysis."""
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(glimmer.MODEL_ID)
    items = B.matched_items(args.sets)
    ids = {it.en: {lang: B.name_token_ids(tok, names) for lang, names in it.names.items()} for it in items}
    pieces = {it.en: {lang: [tok.decode([i]) for i in v] for lang, v in ids[it.en].items()} for it in items}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "name_ids.json").write_text(json.dumps({"ids": ids, "pieces": pieces}, ensure_ascii=False, indent=1))
    log(f"name ids -> {args.out / 'name_ids.json'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["stats", "pilot", "run", "ids"])
    ap.add_argument("--sets", type=Path, default=Path("runs/sets"))
    ap.add_argument("--runs", type=Path, default=Path("runs"), help="folder holding localizers/")
    ap.add_argument("--out", type=Path, default=Path("runs/bilingual"))
    ap.add_argument("--batch", type=int, default=10)
    ap.add_argument("--only", default="", help="regex on condition families")
    args = ap.parse_args()
    torch.manual_seed(0)
    if args.cmd == "ids":
        return cmd_ids(args)
    t0 = time.time()
    model, processor = glimmer.load()
    log(f"loaded in {time.time() - t0:.0f}s")
    {"stats": cmd_stats, "pilot": cmd_pilot, "run": cmd_run}[args.cmd](args, model, processor)


if __name__ == "__main__":
    main()

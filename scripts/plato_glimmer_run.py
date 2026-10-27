"""Plato's Chair inside Glimmer, GPU part (run on the L40S box).

  probe  PLATO_DIR                 shapes and timing on a few pictures (no files written)
  all    PLATO_DIR [--families ..] intact pass with hidden states -> distance matrices -> dose
                                   calibration per lesion family -> every lesion condition on
                                   every picture

Outputs go to runs/plato_glimmer/raw/:
  intact.json, <condition>.json    per-picture answers, codes and word-lens summaries
  intact_arrays.npz                answer-position residual stream (N, 52, 6656), pooled vision
                                   tower (N, 6144) and projector (N, 6656) embeddings, float16
  distances.npz                    within-concept cosine distance matrices per space (centered/raw)
  calibration.json                 the dose search for each lesion family
Reuses the lesion engine (metalesionlab/lesions.py, localizers.py, model_lab.py).
"""
import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
import torch

from metalesionlab import glimmer
from metalesionlab.lesions import LesionSpec, UnitStats, site_dims, site_spec
from metalesionlab.localizers import Localizer, localizer_spec, random_control
from metalesionlab.model_lab import SeverityCurve
from metalesionlab.plato_glimmer import (NAMED_LAYERS, Picture, Probe, collect_pictures, concept_distance_matrices,
                                         cosine_distance_matrix, save_json)

RUNS = Path("runs")
OUT = RUNS / "plato_glimmer" / "raw"

# Lesion families: how a dose becomes a spec, and the dose range searched.
FAMILIES = {
    "naming-mlp-mean": {"kind": "localizer", "localizer": "naming_en", "units": "mlp", "method": "mean",
                        "lo": 0.0, "hi": 0.5},
    "naming-heads-zero": {"kind": "localizer", "localizer": "naming_en", "units": "heads", "method": "zero",
                          "lo": 0.0, "hi": 0.5},
    "late-band-noise": {"kind": "site", "site": "layers:40-47", "method": "noise", "lo": 0.0, "hi": 16.0},
    "early-band-noise": {"kind": "site", "site": "layers:8-15", "method": "noise", "lo": 0.0, "hi": 8.0},
    "random-mlp-mean": {"kind": "random", "units": "mlp", "method": "mean", "lo": 0.0, "hi": 0.9},
}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", text.lower()).strip("-")[:80]


def random_units_spec(dims, units: str, frac: float, method: str, seed: int = 0) -> LesionSpec:
    """A random `frac` of all units of one kind, spread over every decoder layer."""
    per = dims.mlp if units == "mlp" else dims.heads
    total = dims.n_layers * per
    idx = np.random.default_rng(seed).choice(total, int(round(frac * total)), replace=False)
    chosen: dict[int, list[int]] = {}
    for flat in sorted(idx.tolist()):
        chosen.setdefault(flat // per, []).append(flat % per)
    return LesionSpec(method=method, name=f"random-{units}-{method} f{frac:.4g}",
                      recipe={"control": "random", "kind": units, "fraction": frac, "seed": seed}, **{units: chosen})


def family_spec(name: str, dose: float, dims, localizers: dict) -> LesionSpec:
    fam = FAMILIES[name]
    if fam["kind"] == "localizer":
        loc = localizers.setdefault(fam["localizer"], Localizer.load(RUNS / "localizers" / f"{fam['localizer']}.pt"))
        spec = localizer_spec(loc, fam["units"], dose, fam["method"])
        spec.name = f"{name} f{dose:.4g}"
    elif fam["kind"] == "site":
        spec = site_spec(fam["site"], fam["method"], noise_scale=dose)
        spec.name = f"{name} x{dose:.4g}"
    else:
        spec = random_units_spec(dims, fam["units"], dose, fam["method"])
        spec.name = f"{name} f{dose:.4g}"
    spec.recipe = {**spec.recipe, "family": name, "dose": dose}
    return spec


def calibration_pictures(pictures: list[Picture], per: int = 2) -> list[Picture]:
    """`per` AI and `per` human pictures per concept (the first ones), for quick dose searches."""
    return [p for p in pictures if p.index < per]


def strip_arrays(result: dict) -> dict:
    return {k: v for k, v in result.items() if k != "_arrays"}


def save_distances(pictures: list[Picture], arrays: dict, path: Path) -> None:
    """Within-concept distance matrices for the vision tower, the projector and every decoder layer,
    centered and raw, plus full centered matrices for the named layers (for between-concept checks)."""
    groups = sorted({(p.key, p.source) for p in pictures})
    spaces = {"vision_tower": arrays["vision_tower"], "projector": arrays["projector"]}
    resid = arrays["resid"]
    for layer in range(resid.shape[1]):
        spaces[f"L{layer + 1}"] = resid[:, layer]
    sizes = [sum((p.key, p.source) == g for p in pictures) for g in groups]
    out = {"groups": np.array([f"{k}|{s}" for k, s in groups]), "sizes": np.array(sizes)}
    n_max = max(sizes)
    for name, emb in spaces.items():
        for centered in (True, False):
            mats = concept_distance_matrices(emb.astype(np.float32), pictures, centered=centered)
            stack = np.full((len(groups), n_max, n_max), np.nan, dtype=np.float32)  # padded: groups have 12-16
            for i, g in enumerate(groups):
                stack[i, :sizes[i], :sizes[i]] = mats[g]
            out[f"{name}|{'centered' if centered else 'raw'}"] = stack
    for name in ["vision_tower", "projector"] + [f"L{n}" for n in NAMED_LAYERS]:
        emb = spaces[name].astype(np.float64)
        out[f"full|{name}"] = cosine_distance_matrix(emb, emb.mean(0)).astype(np.float16)
    np.savez_compressed(path, **out)


class Runner:
    def __init__(self, plato_dir: Path, per_source: int, batch: int, keys=None):
        self.pictures = collect_pictures(plato_dir, per_source, keys=keys)
        if not self.pictures:
            raise SystemExit(f"no concept in {plato_dir} has {per_source} AI and {per_source} human doodles")
        t0 = time.time()
        self.model, self.processor = glimmer.load()
        print(f"loaded in {time.time() - t0:.0f}s; {len(self.pictures)} pictures, "
              f"{len({p.key for p in self.pictures})} concepts", flush=True)
        self.dims = site_dims(self.model)
        self.batch = batch
        stats_file = RUNS / "cache" / "unit_stats_demo_en.pt"
        self.stats = UnitStats.load(stats_file, self.model.device) if stats_file.exists() else None
        self.localizers: dict = {}
        self.probe = Probe.build(self.processor, self.pictures, batch_size=batch)

    def run(self, spec: LesionSpec, probe: Probe | None = None, **kw) -> dict:
        r = (probe or self.probe).run(self.model, self.processor, spec, self.stats, **kw)
        print(f"  {r['condition']}: acc {r['accuracy']:.3f} on {r['n']} ({r['seconds']}s)", flush=True)
        return r


def cmd_probe(args):
    keys = None
    run = Runner(args.plato_dir, args.per_source, args.batch, keys=keys)
    from metalesionlab.model_lab import generate_with_lens, stop_token_ids, to_device

    small = Probe.build(run.processor, run.pictures, batch_size=args.batch)
    r = run.run(LesionSpec(name="intact"), small, capture=True, keep_tops=True, full_lens=True)
    arr = r["_arrays"]
    print({k: v.shape for k, v in arr.items()})
    print("tokens per prompt:", small.batches[0]["input_ids"].shape, "grid:", small.batches[0]["image_grid_thw"][:2])
    print("name variants of first picture:", [run.processor.tokenizer.decode(s) for s in small.variants[0]])
    for row in r["items"]:
        print(f"  {row['key']:12s} {row['source']:5s} said={row['said']!r:20} {row['code']:10s} "
              f"first={row['first_correct_layer']} stable={row['stable_correct_layer']} "
              f"p_word@39/46/52={row['p_word'][38]},{row['p_word'][45]},{row['p_word'][51]} "
              f"tops@26/39/52={row['top'][25]!r},{row['top'][38]!r},{row['top'][51]!r}")
    # the cache crop must leave decoding untouched: compare with the lesion engine's generator
    tok, stops = run.processor.tokenizer, stop_token_ids(run.model, run.processor.tokenizer)
    ref, ref_resid = [], []
    for batch in small.batches:
        t, res = generate_with_lens(run.model, to_device(batch, run.model.device), stops, 8)
        ref += [tok.decode(x, skip_special_tokens=True).strip() for x in t]
        ref_resid.append(res.float().cpu())
    same = sum(a == row["said"] for a, row in zip(ref, r["items"]))
    diff = (torch.cat(ref_resid) - torch.from_numpy(arr["resid"]).float()).abs().max().item()
    print(f"answers equal to model_lab.generate_with_lens: {same}/{len(ref)}; max |resid diff| {diff:.4f}")
    print(f"intact {r['seconds']}s for {r['n']}; peak memory {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB")
    # a lesion through the same path (last-layer lens only)
    les = run.run(family_spec("late-band-noise", 3.0, run.dims, run.localizers), small)
    print("lesion rows:", [(x["said"], x["p_word_final"]) for x in les["items"]])


def cmd_all(args):
    OUT.mkdir(parents=True, exist_ok=True)
    run = Runner(args.plato_dir, args.per_source, args.batch)
    save_json({"pictures": run.pictures, "per_source": args.per_source, "plato_dir": str(args.plato_dir.resolve())},
              OUT / "pictures.json")

    # 1. intact, with hidden states
    if not (OUT / "intact.json").exists() or args.redo_intact:
        r = run.run(LesionSpec(name="intact"), capture=True, keep_tops=True, full_lens=True)
        arrays = r.pop("_arrays")
        np.savez(OUT / "intact_arrays.npz", **arrays)
        save_json(r, OUT / "intact.json")
        save_distances(run.pictures, arrays, OUT / "distances.npz")
        print(f"intact saved; distances -> {OUT / 'distances.npz'}", flush=True)
    elif not (OUT / "distances.npz").exists():
        with np.load(OUT / "intact_arrays.npz") as f:
            save_distances(run.pictures, {k: f[k] for k in f.files}, OUT / "distances.npz")
        print(f"distances from saved arrays -> {OUT / 'distances.npz'}", flush=True)
    intact = json.loads((OUT / "intact.json").read_text())

    # 2. dose calibration on a mixed subset (2 AI + 2 human per concept)
    calib_pics = calibration_pictures(run.pictures, args.calib_per)
    calib_probe = Probe.build(run.processor, calib_pics, batch_size=args.batch)
    calib_idx = {(p.key, p.source, p.index) for p in calib_pics}
    base = np.mean([row["code"] == "Correct" for row, p in zip(intact["items"], run.pictures)
                    if (p.key, p.source, p.index) in calib_idx])
    target = args.target_ratio * base
    calib_file = OUT / "calibration.json"
    calibration = json.loads(calib_file.read_text()) if calib_file.exists() else {}
    calibration["_subset"] = {"n": len(calib_pics), "intact_accuracy": base, "target_accuracy": target,
                              "target_ratio": args.target_ratio}
    for fam in args.families:
        if fam in calibration and not args.redo_calibration:
            continue
        spec_cfg = FAMILIES[fam]
        curve = SeverityCurve(lambda dose, fam=fam: run.run(family_spec(fam, dose, run.dims, run.localizers),
                                                             calib_probe)["accuracy"])
        best = curve.bisect(target, spec_cfg["lo"], spec_cfg["hi"], steps=args.steps, tol=args.tol)
        calibration[fam] = {**best, "curve": sorted(curve.points.items())}
        save_json(calibration, calib_file)
        print(f"calibrated {fam}: dose {best['dose']:.4g} -> {best['accuracy']:.3f} (target {target:.3f})", flush=True)

    # 3. every condition on every picture
    for fam in args.families:
        dose = calibration[fam]["dose"]
        spec = family_spec(fam, dose, run.dims, run.localizers)
        specs = [(f"{fam}", spec)]
        if FAMILIES[fam]["kind"] == "localizer":
            ctrl = random_control(spec, run.dims, seed=0)
            ctrl.name = f"{fam} f{dose:.4g} random-matched seed0"
            specs.append((f"{fam}-random-matched", ctrl))
        for label, s in specs:
            path = OUT / f"{slug(label)}.json"
            if path.exists() and not args.redo_lesions:
                continue
            r = strip_arrays(run.run(s, condition=label))
            r["family"], r["dose"] = fam, dose
            save_json(r, path)
    print("done", flush=True)


def cmd_extra(args):
    """Extra conditions at explicit doses, e.g. a second severity: --family naming-mlp-mean --doses 0.2"""
    run = Runner(args.plato_dir, args.per_source, args.batch)
    for dose in args.doses:
        spec = family_spec(args.family, dose, run.dims, run.localizers)
        label = f"{args.family}@{dose:g}"
        specs = [(label, spec)]
        if args.control and FAMILIES[args.family]["kind"] == "localizer":
            ctrl = random_control(spec, run.dims, seed=0)
            ctrl.name = f"{label} random-matched seed0"
            specs.append((f"{label}-random-matched", ctrl))
        for lab, s in specs:
            path = OUT / f"{slug(lab)}.json"
            if path.exists():
                continue
            r = strip_arrays(run.run(s, condition=lab))
            r["family"], r["dose"] = args.family, dose
            save_json(r, path)
    print("done", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("extra")
    p.add_argument("plato_dir", type=Path)
    p.add_argument("--family", required=True, choices=list(FAMILIES))
    p.add_argument("--doses", type=float, nargs="+", required=True)
    p.add_argument("--control", action="store_true", help="also a random-unit control with matched counts")
    p.add_argument("--per-source", type=int, default=16)
    p.add_argument("--batch", type=int, default=16)
    p.set_defaults(fn=cmd_extra)
    for name, fn in (("probe", cmd_probe), ("all", cmd_all)):
        p = sub.add_parser(name)
        p.add_argument("plato_dir", type=Path)
        p.add_argument("--per-source", type=int, default=16)
        p.add_argument("--batch", type=int, default=16)
        p.set_defaults(fn=fn)
        if name == "all":
            p.add_argument("--families", nargs="+", default=list(FAMILIES))
            p.add_argument("--target-ratio", type=float, default=0.5,
                           help="lesion dose aims at this fraction of intact accuracy on the calibration subset")
            p.add_argument("--calib-per", type=int, default=2)
            p.add_argument("--steps", type=int, default=5)
            p.add_argument("--tol", type=float, default=0.06)
            p.add_argument("--redo-intact", action="store_true")
            p.add_argument("--redo-calibration", action="store_true")
            p.add_argument("--redo-lesions", action="store_true")
    args = ap.parse_args()
    torch.manual_seed(0)
    args.fn(args)


if __name__ == "__main__":
    main()

"""Model Lab runs on the GPU box: reference stats, naming conditions, localizers, severity.

  stats SET                 per-unit mean/sd for mean and noise lesions (held-out drawings)
  name SET [--spec JSON]    one naming condition (intact without --spec)
  agreement SET             intact naming -> runs/sets/SET/glimmer_names.json
  localize SET.. --contrast naming|visual|language
  severity SET --localizer NAME --kind mlp|heads --method zero|mean|noise   (dose = fraction of units)
  severity SET --site layers:40-47 --dose noise                            (dose = noise scale)
  components SET            vision tower, projector and decoder-band lesions

Results go to runs/lesion/<set>/<condition>.json (one file per condition) and
runs/lesion/<set>/index.json. Codes are made without the meaning judge; re-score locally with
scripts/rescore_lesions.py.
"""
import argparse
import json
import re
import time
from pathlib import Path

import torch

from metalesionlab import glimmer
from metalesionlab.lesions import LesionSpec, UnitStats, compute_unit_stats, site_dims, site_spec
from metalesionlab.localizers import (Localizer, localizer_images, localizer_spec, random_control,
                                      run_contrast)
from metalesionlab.model_lab import (NamingTest, SeverityCurve, build_batches, naming_prompt, save_result,
                                     write_index)

RUNS = Path("runs")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", text.lower()).strip("-")[:80]


def stats_path(set_name: str) -> Path:
    return RUNS / "cache" / f"unit_stats_{set_name}.pt"


class Lab:
    def __init__(self, set_dir: Path, batch_size: int):
        t0 = time.time()
        self.model, self.processor = glimmer.load()
        print(f"loaded in {time.time() - t0:.0f}s", flush=True)
        self.set_dir, self.set_name = set_dir, set_dir.name
        self.test = NamingTest.from_set(self.processor, set_dir, batch_size=batch_size)
        self.out_dir = RUNS / "lesion" / self.set_name
        self.dims = site_dims(self.model)
        self._stats = None

    @property
    def stats(self) -> UnitStats | None:
        if self._stats is None and stats_path(self.set_name).exists():
            self._stats = UnitStats.load(stats_path(self.set_name), self.model.device)
        return self._stats

    def run(self, spec: LesionSpec, condition: str = "", save: bool = True) -> dict:
        r = self.test.run(self.model, self.processor, spec, self.stats, max_new_tokens=12, condition=condition)
        if save:
            save_result(r, self.out_dir / f"{slug(r['condition'])}.json")
        print(f"  {r['condition']}: acc {r['accuracy']:.2f}  {_short(r['counts'])}  ({r['seconds']}s)", flush=True)
        return r


def _short(counts: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in counts.items() if v)


def cmd_stats(args):
    model, processor = glimmer.load()
    trials = localizer_images([args.set_dir], held_out=True) or localizer_images([args.set_dir], held_out=False)
    from PIL import Image
    batches = build_batches(processor, [(Image.open(t.image).convert("RGB"), naming_prompt(t.lang)) for t in trials],
                            args.batch)
    t0 = time.time()
    stats = compute_unit_stats(model, [{k: v.to(model.device) for k, v in b.items()} for b in batches],
                               source=f"{args.set_dir.name}: {len(trials)} held-out drawings, naming prompt")
    stats.save(stats_path(args.set_dir.name))
    print(f"unit stats from {len(trials)} pictures, {stats.n_tokens} tokens ({stats.n_image_tokens} image) "
          f"in {time.time() - t0:.0f}s -> {stats_path(args.set_dir.name)}")


def cmd_name(args):
    lab = Lab(args.set_dir, args.batch)
    spec = LesionSpec.from_dict(json.loads(Path(args.spec).read_text() if args.spec and Path(args.spec).exists()
                                           else args.spec or "{}"))
    lab.run(spec, args.condition)
    write_index(lab.out_dir)


def cmd_agreement(args):
    lab = Lab(args.set_dir, args.batch)
    r = lab.run(LesionSpec(name="intact"), "intact")
    names = {row["word"]: {"name": row["said"], "code": row["code"]} for row in r["items"]}
    (args.set_dir / "glimmer_names.json").write_text(json.dumps(names, ensure_ascii=False, indent=1))
    write_index(lab.out_dir)
    print(f"Glimmer name agreement {r['accuracy']:.2f} on {r['n']} items -> {args.set_dir / 'glimmer_names.json'}")


def cmd_localize(args):
    model, processor = glimmer.load()
    trials = localizer_images(args.set_dirs, held_out=not args.include_test) if args.contrast != "language" else None
    name = args.name or args.contrast
    t0 = time.time()
    loc = run_contrast(model, processor, args.contrast, trials, batch_size=args.batch, name=name)
    loc.meta.update({"sets": [d.name for d in args.set_dirs], "trials": loc.n_a, "seconds": round(time.time() - t0, 1),
                     "held_out": not args.include_test})
    out = RUNS / "localizers" / f"{name}.pt"
    loc.save(out)
    (RUNS / "localizers" / f"{name}.json").write_text(json.dumps(loc.summary()))
    t = loc.t["mlp"]
    print(f"{name}: {loc.n_a} vs {loc.n_b} trials in {time.time() - t0:.0f}s; mlp t max {t.max():.1f}, "
          f"units t>4: {(t > 4).sum().item()}; heads t>4: {(loc.t['heads'] > 4).sum().item()}")
    for kind in ("mlp", "heads"):
        top = loc.summary()[f"{kind}_top0.01_by_layer"]
        print(f"  {kind} top 1% by layer: {top}")


def cmd_severity(args):
    """Bisect the dose for each target accuracy. Dose is the fraction of a localizer's ranked
    units (--dose fraction) or the noise scale of a fixed lesion (--dose noise), which is either
    a localizer's top --frac units or a whole --site."""
    lab = Lab(args.set_dir, args.batch)
    loc = Localizer.load(RUNS / "localizers" / f"{args.localizer}.pt") if args.localizer else None
    noise_dose = args.dose == "noise"
    method = "noise" if noise_dose else args.method
    if args.site:
        tag = f"{args.site}-{method}"
    else:
        tag = f"{loc.name}-{args.kind}-{method}" + ("-rev" if args.direction < 0 else "")
        tag += f"-f{args.frac:g}" if noise_dose else ""

    def make(dose: float) -> LesionSpec:
        scale = dose if noise_dose else args.noise_scale
        if args.site:
            return site_spec(args.site, method, scale)
        return localizer_spec(loc, args.kind, args.frac if noise_dose else dose, method, args.direction, scale)

    def label(dose: float) -> str:
        return f"{tag} {'x' if noise_dose else 'f'}{dose:.4g}"

    results = {}

    def evaluate(dose: float) -> float:
        results[dose] = lab.run(make(dose), label(dose))
        return results[dose]["accuracy"]

    curve = SeverityCurve(evaluate)
    levels, controls = [], {}
    for target in args.targets:
        level = curve.bisect(target, args.lo, args.hi, steps=args.steps)
        dose = level["dose"]
        print(f"target {target}: dose {dose:.4g} -> accuracy {level['accuracy']:.2f}"
              + ("" if level["within_tol"] else " (not reached)"), flush=True)
        level.update(condition=results[dose]["condition"], units=results[dose]["units"])
        if level["within_tol"] and not args.site and dose not in controls:  # matched random units, once per dose
            controls[dose] = []
            for seed in range(args.controls):
                r = lab.run(random_control(make(dose), lab.dims, seed=seed), f"{label(dose)} random seed{seed}")
                controls[dose].append({"condition": r["condition"], "accuracy": r["accuracy"], "counts": r["counts"]})
        level["controls"] = controls.get(dose, [])
        levels.append(level)
    summary = {"set": lab.set_name, "localizer": loc.name if loc else None, "site": args.site, "kind": args.kind,
               "method": method, "dose": args.dose, "direction": args.direction,
               "curve": sorted(curve.points.items()), "levels": levels}
    (lab.out_dir / f"severity_{slug(tag)}.json").write_text(json.dumps(summary, indent=1))
    write_index(lab.out_dir)


def cmd_components(args):
    lab = Lab(args.set_dir, args.batch)
    if not args.no_intact:
        lab.run(LesionSpec(name="intact"), "intact")
    for comp in ("vision_tower", "projector"):
        for method in args.methods:
            scales = args.noise_scales if method == "noise" else [1.0]
            for s in scales:
                name = f"{comp} {method}" + (f" x{s:g}" if method == "noise" else "")
                lab.run(LesionSpec(method=method, components={comp: None}, noise_scale=s, name=name))
    n = lab.dims.n_layers
    for start in range(0, n, args.band):
        layers = list(range(start, min(start + args.band, n)))
        for method in args.band_methods:
            scale = args.band_noise_scale if method == "noise" else 1.0
            lab.run(LesionSpec(method=method, layers=layers, noise_scale=scale,
                               name=f"layers {layers[0]}-{layers[-1]} {method}" + (f" x{scale:g}" if method == "noise" else "")))
    write_index(lab.out_dir)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    def with_set(p):
        p.add_argument("set_dir", type=Path)
        p.add_argument("--batch", type=int, default=10)
        return p

    with_set(sub.add_parser("stats")).set_defaults(fn=cmd_stats)
    p = with_set(sub.add_parser("name"))
    p.add_argument("--spec", help="lesion spec as a JSON file or string")
    p.add_argument("--condition", default="")
    p.set_defaults(fn=cmd_name)
    with_set(sub.add_parser("agreement")).set_defaults(fn=cmd_agreement)
    p = sub.add_parser("localize")
    p.add_argument("set_dirs", type=Path, nargs="+")
    p.add_argument("--contrast", required=True, choices=["naming", "visual", "language"])
    p.add_argument("--name", default="")
    p.add_argument("--batch", type=int, default=10)
    p.add_argument("--include-test", action="store_true", help="also use the kept test pictures")
    p.set_defaults(fn=cmd_localize)
    p = with_set(sub.add_parser("severity"))
    p.add_argument("--localizer", help="rank units with this localizer")
    p.add_argument("--site", help='whole-site lesion instead: "vision_tower", "projector", "layers:40-47", "mlp:0-7"')
    p.add_argument("--dose", choices=["fraction", "noise"], default="fraction")
    p.add_argument("--frac", type=float, default=0.05, help="fraction of ranked units when the dose is noise")
    p.add_argument("--kind", choices=["mlp", "heads"], default="mlp")
    p.add_argument("--method", choices=["zero", "mean", "noise"], default="zero")
    p.add_argument("--direction", type=int, default=1)
    p.add_argument("--noise-scale", type=float, default=1.0)
    p.add_argument("--targets", type=float, nargs="+", default=[0.8, 0.6, 0.4])
    p.add_argument("--lo", type=float, default=0.0)
    p.add_argument("--hi", type=float, default=None, help="largest dose (default 0.5 fraction, 16 noise sd)")
    p.add_argument("--steps", type=int, default=5)
    p.add_argument("--controls", type=int, default=1)
    p.set_defaults(fn=cmd_severity)
    p = with_set(sub.add_parser("components"))
    p.add_argument("--methods", nargs="*", default=["zero", "mean", "noise"])
    p.add_argument("--noise-scales", type=float, nargs="+", default=[0.5, 1.0, 2.0])
    p.add_argument("--band", type=int, default=4)
    p.add_argument("--band-methods", nargs="*", default=["zero", "mean"])
    p.add_argument("--band-noise-scale", type=float, default=1.0)
    p.add_argument("--no-intact", action="store_true")
    p.set_defaults(fn=cmd_components)
    args = ap.parse_args()
    if getattr(args, "hi", 0) is None:
        args.hi = 16.0 if args.dose == "noise" else 0.5
    torch.manual_seed(0)
    args.fn(args)


if __name__ == "__main__":
    main()

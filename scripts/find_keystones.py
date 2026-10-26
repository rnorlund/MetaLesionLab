"""Find "keystone" units: the few whose lesion alone breaks naming for every picture.

Large lesions sometimes collapse all at once (the model echoes the instruction, or repeats one
word), and random controls collapse for some seeds and not others. This bisects a collapsing
unit set on a few pictures down to the units that cause it, then runs those units alone on the
whole set. Results are added to runs/localizers/keystones.json.

Usage: python scripts/find_keystones.py runs/sets/demo_en --localizer visual_en --kind mlp --frac 0.17
       [--random-seed 1] [--method zero]
"""
import argparse
import json
from pathlib import Path

from metalesionlab import glimmer
from metalesionlab.lesions import LesionSpec, site_dims
from metalesionlab.localizers import Localizer, isolate_critical, localizer_spec, random_control
from metalesionlab.model_lab import NamingTest, save_result, write_index

RUNS = Path("runs")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("set_dir", type=Path)
    ap.add_argument("--localizer", required=True)
    ap.add_argument("--kind", choices=["mlp", "heads"], default="mlp")
    ap.add_argument("--frac", type=float, required=True)
    ap.add_argument("--method", default="zero")
    ap.add_argument("--random-seed", type=int, default=None, help="bisect the matched random control instead")
    ap.add_argument("--probe-items", type=int, default=5)
    ap.add_argument("--fail-below", type=float, default=0.4)
    args = ap.parse_args()

    model, processor = glimmer.load()
    probe = NamingTest.from_set(processor, args.set_dir, batch_size=args.probe_items, limit=args.probe_items)
    full = NamingTest.from_set(processor, args.set_dir, batch_size=10)
    loc = Localizer.load(RUNS / "localizers" / f"{args.localizer}.pt")
    spec = localizer_spec(loc, args.kind, args.frac, args.method)
    if args.random_seed is not None:
        spec = random_control(spec, site_dims(model), seed=args.random_seed)
    units = getattr(spec, args.kind)

    def fails(u) -> bool:
        r = probe.run(model, processor, LesionSpec(method=args.method, **{args.kind: u}), lens=False, max_new_tokens=12)
        return r["accuracy"] < args.fail_below

    if not fails(units):
        print(f"{spec.name}: does not collapse on the probe pictures; nothing to isolate")
        return
    culprits, probes = isolate_critical(units, fails)
    n = sum(len(v) for v in culprits.values())
    print(f"{spec.name}: {n} unit(s) after {probes} probes: {culprits}")

    alone = LesionSpec(method=args.method, name=f"keystone {args.kind} {culprits} ({args.method})",
                       recipe={"keystone_of": spec.name}, **{args.kind: culprits})
    r = full.run(model, processor, alone, max_new_tokens=12)
    out_dir = RUNS / "lesion" / args.set_dir.name
    save_result(r, out_dir / f"keystone-{args.kind}-{'-'.join(f'l{k}n{v[0]}' for k, v in culprits.items())[:60]}.json")
    write_index(out_dir)
    print(f"alone on {r['n']} pictures: accuracy {r['accuracy']}; said {[x['said'][:40] for x in r['items'][:5]]}")

    path = RUNS / "localizers" / "keystones.json"
    found = json.loads(path.read_text()) if path.exists() else []
    found.append({"kind": args.kind, "method": args.method, "units": {str(k): v for k, v in culprits.items()},
                  "from": spec.name, "probes": probes, "accuracy_alone": r["accuracy"]})
    path.write_text(json.dumps(found, indent=1))


if __name__ == "__main__":
    main()

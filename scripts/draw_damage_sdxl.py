"""What damage does to an AI's chair (/draw): SDXL doodles of the 10 drawing-game things, and of the 11 ideas and
4 words of "Draw the invisible" (docs/plato_ideas_damage_plan.md), intact and with its language part or its drawing
part damaged (GPU part; run on a lab GPU, never the Mac).

  run --out DIR --conditions intact text-noise@0.5 ... [--keys chair cup] [--seeds 0 1 2 | --pick chair=3 ...]
  run --out DIR --ideas                     every idea and word with its pre-registered seeds and conditions
                                            (plato_ideas_damage.conditions / n_seeds)

Pictures: <out>/<condition>/<key>/s<i>.png (512 px). Picture i of a thing has seed seed_for(key, i) in every
condition, so it is paired across damage levels. Prompt, settings and lesion engine are the damage
experiment's (scripts/plato_damage_sdxl.py, docs/plato_damage.md): the doodle template with the phrase
Muse Image was given, 768 px, 25 steps, guidance 5, the SDXL comparison's negative prompt, and the lesion
families of plato_damage.FAMILIES with the experiment's unit statistics (unit_stats.pt), so a dose here
is the same damage as on /plato/damage. scripts/draw_damage_export.py turns the chosen pictures into the
page's thumbnails.

This is about the model only: nothing here, or on the page, is ever compared with a visitor's drawing.

SDXL: Stability AI, stabilityai/stable-diffusion-xl-base-1.0, CreativeML OpenRAIL++-M.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab import plato_ideas as I  # noqa: E402
from metalesionlab import plato_ideas_damage as ID  # noqa: E402
from metalesionlab.plato import BY_KEY as PLATO, prompt_for  # noqa: E402
from metalesionlab.plato_damage import NEGATIVE, family_spec, parse_condition  # noqa: E402
from metalesionlab.sdxl_lesions import DamageSpec, SDXLDamage  # noqa: E402

MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
# The drawing game's things (web/data/draw.json), in its order. "sailboat" is shown as "boat". Then the ideas and
# words, after the things so that the things' seeds are unchanged.
THINGS = ID.THINGS
KEYS = ID.KEYS
SEED_BASE = 20261100  # not the damage experiment's base, so these are new pictures


def seed_for(key: str, i: int) -> int:
    return SEED_BASE + 1000 * KEYS.index(key) + i


def prompt(key: str) -> str:
    """The doodle prompt Muse Image was given for this thing or idea (plato.STYLES["doodle"] either way)."""
    if key in I.ANY:
        return I.prompt_for(I.ANY[key])
    return prompt_for(PLATO[key], "doodle")


def load_pipe():
    import torch
    from diffusers import StableDiffusionXLPipeline

    pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, torch_dtype=torch.float16, variant="fp16",
                                                     use_safetensors=True).to("cuda")
    pipe.set_progress_bar_config(disable=True)
    return pipe


def spec_for(condition: str) -> DamageSpec:
    family, dose = parse_condition(condition)
    if family == "intact":
        return DamageSpec(name="intact")
    if not family.endswith("-noise") and not family.endswith("-zero"):
        raise SystemExit(f"unknown condition {condition}")
    return DamageSpec.from_dict(family_spec(family, dose))


def cmd_run(args):
    if args.ideas:  # the ideas' and words' pre-registered plan: per key, its seeds under its conditions
        keys = args.keys or ID.IDEA_KEYS + ID.WORD_KEYS
        jobs = {}
        for k in keys:
            for c in ID.conditions(k):
                jobs.setdefault(c, {})[k] = list(range(ID.n_seeds(k)))
        return run_jobs(args, jobs)
    if args.pick:  # per-thing picture indices
        picks = {}
        for p in args.pick:
            key, _, idx = p.partition("=")
            if key not in KEYS:
                raise SystemExit(f"unknown thing {key!r}")
            picks[key] = [int(i) for i in idx.split(",")]
        keys = [k for k in KEYS if k in picks]
    else:
        keys = args.keys or THINGS
        picks = {k: list(args.seeds) for k in keys}
    return run_jobs(args, {c: {k: picks[k] for k in keys} for c in args.conditions})


def run_jobs(args, jobs: dict[str, dict[str, list[int]]]):
    """jobs: condition -> key -> picture indices. Resumable: pictures already on disk are skipped."""
    import torch

    pipe = load_pipe()
    stats = torch.load(args.stats) if args.stats and args.stats.exists() else None
    engine = SDXLDamage(pipe, stats=stats)
    t0, made = time.time(), 0
    for cond, picks in jobs.items():
        keys = list(picks)
        spec = spec_for(cond)
        folder = args.out / cond
        folder.mkdir(parents=True, exist_ok=True)
        meta_path = folder / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        meta.update({"condition": cond, "spec": spec.to_dict(), "model": MODEL, "license": "CreativeML OpenRAIL++-M",
                     "steps": args.steps, "size": args.size, "guidance_scale": args.guidance, "negative": NEGATIVE})
        seeds_done = meta.setdefault("seeds", {})
        with engine.apply(spec):
            for key in keys:
                out = folder / key
                out.mkdir(parents=True, exist_ok=True)
                todo = [i for i in picks[key] if not (out / f"s{i}.png").exists()]
                for j in range(0, len(todo), args.batch):
                    idx = todo[j:j + args.batch]
                    gens = [torch.Generator("cuda").manual_seed(seed_for(key, i)) for i in idx]
                    engine.reset()
                    t1 = time.time()
                    imgs = pipe(prompt(key), negative_prompt=NEGATIVE, num_images_per_prompt=len(idx),
                                num_inference_steps=args.steps, guidance_scale=args.guidance, height=args.size,
                                width=args.size, generator=gens).images
                    for i, im in zip(idx, imgs):
                        im.thumbnail((args.save_side, args.save_side), resample=3)
                        im.save(out / f"s{i}.png")
                        seeds_done[f"{key}/s{i}.png"] = seed_for(key, i)
                    made += len(idx)
                    print(f"{cond:18s} {key:10s} {len(idx)} in {time.time() - t1:4.1f}s (total {made}, "
                          f"{time.time() - t0:5.0f}s)", flush=True)
        meta_path.write_text(json.dumps(meta, indent=1))
    print(f"done: {made} pictures in {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.set_defaults(fn=cmd_run)
    p.add_argument("--out", type=Path, default=Path("draw_damage"))
    p.add_argument("--conditions", nargs="+")
    p.add_argument("--ideas", action="store_true", help="the ideas and words with their pre-registered plan")
    p.add_argument("--keys", nargs="*", choices=KEYS)
    p.add_argument("--seeds", nargs="*", type=int, default=list(range(12)), help="picture indices for every thing")
    p.add_argument("--pick", nargs="*", help="per-thing picture indices instead, e.g. chair=3 cup=1,5")
    p.add_argument("--stats", type=Path, help="the damage experiment's unit_stats.pt (needed for noise)")
    p.add_argument("--steps", type=int, default=25)
    p.add_argument("--size", type=int, default=768)
    p.add_argument("--guidance", type=float, default=5.0)
    p.add_argument("--batch", type=int, default=4)
    p.add_argument("--save-side", type=int, default=512)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

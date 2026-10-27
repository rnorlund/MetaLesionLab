"""Plato's Chair, damage: draw with a lesioned Stable Diffusion XL (GPU part; run on a lab GPU, never the Mac).

  probe                         site sizes, one intact picture and two lesions, timing
  stats --out DIR               per-unit mean and sd over reference prompts (needed by noise lesions)
  localize --out DIR            "specific-kind" text-encoder units: subordinate > basic-level phrases
                                for held-out concepts (not chair, hat, bird or clock)
  run --out DIR --conditions intact text-zero@0.2 unet-zero@0.2 ... [--keys ...] [--n 8]
                                every picture of every prompt in every condition, resumable

Pictures: <out>/<condition>/<prompt key>/s<i>.png (512 px), seed plato_damage.seed_for(prompt, i), the
same in every condition, so picture i of a prompt is paired across damage levels. Settings are the
SDXL comparison's (768 px, 25 steps, guidance 5, its negative prompt). Each condition folder has a
meta.json with the lesion spec. Lesion families: plato_damage.FAMILIES and the targeted text-spec /
text-spec-random pair (needs localize first).

SDXL: Stability AI, stabilityai/stable-diffusion-xl-base-1.0, CreativeML OpenRAIL++-M.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab.plato import STYLES  # noqa: E402
from metalesionlab.plato_damage import (ALL_PROMPTS, BY_KEY, KIND_PROMPTS, NEGATIVE, family_spec,  # noqa: E402
                                        parse_condition, seed_for)
from metalesionlab.sdxl_lesions import (DamageSpec, SDXLDamage, collect_stats, layer_sizes, matched_random,  # noqa: E402
                                        site_layers, top_units)

MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
# Reference prompts for unit statistics: other everyday things, none of the test concepts.
REFERENCE = ["a cup", "a tree", "a car", "a key", "an umbrella", "a sailboat", "a house", "a cat", "a lamp", "a book",
             "a bicycle", "a guitar", "a fish", "a shoe", "an apple", "a spoon"]
# Held-out subordinate vs basic-level phrases for the targeted "specific kind" localizer.
SPECIFIC = [("a sports car", "a car"), ("a sailboat", "a boat"), ("a tulip", "a flower"), ("a palm tree", "a tree"),
            ("a grand piano", "a piano"), ("a teacup", "a cup"), ("a poodle", "a dog"), ("a goldfish", "a fish"),
            ("a skyscraper", "a building"), ("a castle", "a house"), ("a sneaker", "a shoe"),
            ("an electric guitar", "a guitar"), ("a canoe", "a boat"), ("a pickup truck", "a truck"),
            ("a desk lamp", "a lamp"), ("a pine tree", "a tree"), ("a kitten", "a cat"), ("a cupcake", "a cake"),
            ("a hammock", "a bed"), ("a sunflower", "a flower"), ("a bulldozer", "a vehicle"),
            ("a saxophone", "an instrument"), ("a lighthouse", "a building")]


def load_pipe():
    import torch
    from diffusers import StableDiffusionXLPipeline

    pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, torch_dtype=torch.float16, variant="fp16",
                                                     use_safetensors=True).to("cuda")
    pipe.set_progress_bar_config(disable=True)
    return pipe


def draw(pipe, engine, prompt: str, seeds: list[int], args):
    import torch

    gens = [torch.Generator("cuda").manual_seed(s) for s in seeds]
    engine.reset()
    return pipe(prompt, negative_prompt=NEGATIVE, num_images_per_prompt=len(seeds), num_inference_steps=args.steps,
                guidance_scale=args.guidance, height=args.size, width=args.size, generator=gens).images


def spec_for(condition: str, localizer: Path | None) -> DamageSpec:
    family, dose = parse_condition(condition)
    if family == "intact":
        return DamageSpec(name="intact")
    if family in ("text-spec", "text-spec-random"):
        loc = json.loads(localizer.read_text()) if localizer and localizer.exists() else None
        if loc is None:
            raise SystemExit("text-spec needs --localizer (run localize first)")
        scores = {k: np.array(v) for k, v in loc["t"].items()}
        units = top_units(scores, dose)
        if family == "text-spec-random":
            units = matched_random(units, loc["sizes"], seed=5)
        return DamageSpec(site="text", method="zero", units=units, name=condition,
                          recipe={"family": family, "dose": dose, "n_units": sum(map(len, units.values()))})
    return DamageSpec.from_dict(family_spec(family, dose))


def cmd_probe(args):
    import torch

    pipe = load_pipe()
    for site in ("text1", "text2", "unet"):
        sizes = layer_sizes(pipe, site)
        print(f"{site}: {len(sizes)} modules, {sum(sizes.values())} units; first {list(sizes.items())[:2]}", flush=True)
    engine = SDXLDamage(pipe)
    p = BY_KEY["chair__rocking_chair"]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for cond in ["intact", "text-zero@0.5", "unet-zero@0.5"]:
        t0 = time.time()
        with engine.apply(spec_for(cond, None)):
            imgs = draw(pipe, engine, p.prompt, [seed_for(p, 0), seed_for(p, 1)], args)
        for i, im in enumerate(imgs):
            im.thumbnail((512, 512))
            im.save(out / f"{cond.replace('@', '_')}_{i}.png")
        print(f"{cond}: 2 pictures in {time.time() - t0:.1f}s", flush=True)
    print(f"peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


def cmd_stats(args):
    import torch

    pipe = load_pipe()
    engine = SDXLDamage(pipe)
    prompts = [STYLES["doodle"].format(phrase=r) for r in REFERENCE[:args.n_prompts]]

    def run():
        for j, pr in enumerate(prompts):
            draw(pipe, engine, pr, [777 + j], args)

    t0 = time.time()
    stats = collect_stats(pipe, run)
    args.out.mkdir(parents=True, exist_ok=True)
    torch.save(stats, args.out / "unit_stats.pt")
    print(f"stats for {len(stats)} modules from {len(prompts)} prompts in {time.time() - t0:.0f}s -> "
          f"{args.out / 'unit_stats.pt'}", flush=True)


def cmd_localize(args):
    """Welch t of mean |activation| over the phrase's own tokens (doodle template), subordinate > basic."""
    import torch

    from metalesionlab.lesions import Moments

    pipe = load_pipe()
    mods = dict(site_layers(pipe, "text"))
    acts = {}
    hooks = []

    def grab(name):
        def hook(_m, a):
            acts[name] = a[0].float()
        return hook

    for n, m in mods.items():
        hooks.append(m.register_forward_pre_hook(grab(n)))
    groups = {"sub": {n: Moments(m.in_features, "cuda") for n, m in mods.items()},
              "basic": {n: Moments(m.in_features, "cuda") for n, m in mods.items()}}
    pairs = list(SPECIFIC)
    with torch.no_grad():
        for sub, basic in pairs:
            for label, phrase in (("sub", sub), ("basic", basic)):
                text = STYLES["doodle"].format(phrase=phrase)
                for enc_name, tok, enc in (("te1", pipe.tokenizer, pipe.text_encoder),
                                           ("te2", pipe.tokenizer_2, pipe.text_encoder_2)):
                    ids = tok(text, padding="max_length", max_length=tok.model_max_length, truncation=True,
                              return_tensors="pt").input_ids.cuda()
                    n_real = int((tok(text, return_tensors="pt").input_ids.shape[1]))
                    enc(ids, output_hidden_states=True)
                    for n in mods:
                        if n.startswith(enc_name):
                            groups[label][n].add(acts[n][0, :n_real].abs().mean(0, keepdim=True))
    for h in hooks:
        h.remove()
    t, sizes = {}, {}
    for n in mods:
        ma, va = groups["sub"][n].mean_var()
        mb, vb = groups["basic"][n].mean_var()
        na, nb = groups["sub"][n].n, groups["basic"][n].n
        t[n] = ((ma - mb) / torch.sqrt(va / na + vb / nb + 1e-12)).cpu().numpy().round(4).tolist()
        sizes[n] = mods[n].in_features
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "specific_localizer.json").write_text(json.dumps({"pairs": pairs, "t": t, "sizes": sizes}))
    allt = np.concatenate([np.array(v) for v in t.values()])
    print(f"localizer: {len(pairs)} pairs; units with t > 3: {(allt > 3).mean():.3%}", flush=True)


def cmd_run(args):
    import torch

    keys = args.keys or [p.key for p in KIND_PROMPTS]
    pipe = load_pipe()
    stats = torch.load(args.stats) if args.stats and args.stats.exists() else None
    engine = SDXLDamage(pipe, stats=stats)
    t0, made = time.time(), 0
    for cond in args.conditions:
        spec = spec_for(cond, args.localizer)
        folder = args.out / cond
        folder.mkdir(parents=True, exist_ok=True)
        meta_path = folder / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        spec_d = spec.to_dict()
        if spec_d.get("units") is not None:
            spec_d["units"] = {k: len(v) for k, v in spec_d["units"].items()}  # counts only
        meta.update({"condition": cond, "spec": spec_d, "model": MODEL, "license": "CreativeML OpenRAIL++-M",
                     "steps": args.steps, "size": args.size, "guidance_scale": args.guidance, "negative": NEGATIVE})
        seeds_done = meta.setdefault("seeds", {})
        with engine.apply(spec) as s:
            if not s.is_intact and spec.units is None:
                counts = {k: len(v) for k, v in engine.units_for(spec).items()}
                meta["units_hit"] = sum(counts.values())
            for key in keys:
                p = BY_KEY[key]
                n = args.n_plain if (p.is_plain and cond == "intact" and args.n_plain) else args.n
                out = folder / key
                out.mkdir(parents=True, exist_ok=True)
                todo = [i for i in range(n) if not (out / f"s{i}.png").exists()]
                for j in range(0, len(todo), args.batch):
                    idx = todo[j:j + args.batch]
                    t1 = time.time()
                    imgs = draw(pipe, engine, p.prompt, [seed_for(p, i) for i in idx], args)
                    for i, im in zip(idx, imgs):
                        im.thumbnail((args.save_side, args.save_side), resample=3)
                        im.save(out / f"s{i}.png")
                        seeds_done[f"{key}/s{i}.png"] = seed_for(p, i)
                    made += len(idx)
                    print(f"{cond:22s} {key:24s} {len(idx)} in {time.time() - t1:4.1f}s (total {made}, "
                          f"{time.time() - t0:5.0f}s)", flush=True)
        meta_path.write_text(json.dumps(meta, indent=1))
    print(f"done: {made} pictures in {time.time() - t0:.0f}s; peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB",
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("probe", cmd_probe), ("stats", cmd_stats), ("localize", cmd_localize), ("run", cmd_run)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--out", type=Path, default=Path("damage_out"))
        p.add_argument("--steps", type=int, default=25)
        p.add_argument("--size", type=int, default=768)
        p.add_argument("--guidance", type=float, default=5.0)
        if name == "stats":
            p.add_argument("--n-prompts", type=int, default=16)
        if name == "run":
            p.add_argument("--conditions", nargs="+", required=True)
            p.add_argument("--keys", nargs="*", help=f"prompt keys (default: all non-clock), e.g. "
                                                       f"{', '.join(x.key for x in ALL_PROMPTS[:3])}")
            p.add_argument("--n", type=int, default=8)
            p.add_argument("--n-plain", type=int, default=0, help="intact plain prompts get this many (prototype)")
            p.add_argument("--batch", type=int, default=4)
            p.add_argument("--save-side", type=int, default=512)
            p.add_argument("--stats", type=Path)
            p.add_argument("--localizer", type=Path)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

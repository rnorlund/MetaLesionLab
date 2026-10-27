"""Plato's Chair, comparison generator: the same doodle prompts drawn by Stable Diffusion XL.

Is the uniformity specific to Muse Image, or do image models generally draw one prototype? This draws
every concept with stabilityai/stable-diffusion-xl-base-1.0 (fp16, CreativeML OpenRAIL++-M), using the
SAME doodle prompt as the Muse run plus a negative prompt against shading and paper texture.

Usage (on a GPU server, never on the Mac):
  python scripts/plato_sdxl_generate.py --out ~/plato_sdxl/sdxl_doodle [--keys chair ...] [--n 16]
  python scripts/plato_sdxl_generate.py --condition any --out ~/plato_sdxl/sdxl_any
  python scripts/plato_sdxl_generate.py --condition listed --kinds-dir DIR --out ~/plato_sdxl/sdxl_listed

Every picture has its own seed (recorded in meta.json), so the pictures are independent draws.
Pictures are downscaled to 512 px like the Muse ones and saved as <out>/<key>/c<call>_<i>.png, with
4 seeds per "call", so the folder has the same layout and meta.json format as ai/doodle/ and the
core pipeline (plato_embed.py, source ai_sdxl_doodle) reads it unchanged. Copy it to
$PLATO_DIR/ai/sdxl_doodle/ afterwards. Resumable: existing pictures are kept.

Variety conditions (the "can you prompt it out?" stretch): --condition any uses Muse's doodle_any
prompt ("a chair (any kind of chair)"); --condition listed draws Muse Spark's listed kinds
(<kinds-dir>/<key>.json, i.e. $PLATO_DIR/kinds_input/kinds) as p<i>.png. Both default to the concept's
n_ai pictures (16 or 12) and reuse the default run's seeds (picture i of a concept gets the same seed
in every condition), so the conditions differ only in the prompt. Copy to $PLATO_DIR/ai/sdxl_any and
ai/sdxl_listed.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato import BY_KEY, CONCEPTS, STYLES, prompt_for  # noqa: E402

MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
NEGATIVE = "shading, photo, photorealistic, paper texture, 3d render, color, text"
SEED_BASE = 20261026


def seed_for(key: str, i: int) -> int:
    """A distinct, reproducible seed per picture: concept index * 1000 + picture index."""
    return SEED_BASE + 1000 * [c.key for c in CONCEPTS].index(key) + i


def plan(key: str, condition: str, n: int, batch: int, kinds_dir: Path | None) -> list[tuple[str, str]]:
    """(file name, prompt) for every picture of one concept in one condition."""
    c = BY_KEY[key]
    if condition == "listed":
        kinds = json.loads((kinds_dir / f"{key}.json").read_text())[:n]
        return [(f"p{i}.png", STYLES["doodle"].format(phrase=k)) for i, k in enumerate(kinds)]
    prompt = prompt_for(c, "doodle" if condition == "default" else "doodle_any")
    return [(f"c{i // batch}_{i % batch}.png", prompt) for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--condition", default="default", choices=["default", "any", "listed"])
    ap.add_argument("--kinds-dir", type=Path, help="listed: folder of <key>.json kind lists")
    ap.add_argument("--n", type=int, help="pictures per concept (default 16; any/listed: the concept's n_ai)")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--guidance", type=float, default=5.0, help="diffusers' SDXL default")
    ap.add_argument("--negative", default=NEGATIVE, help="'' for none")
    ap.add_argument("--save-side", type=int, default=512)
    args = ap.parse_args()
    if args.condition == "listed" and not args.kinds_dir:
        ap.error("--condition listed needs --kinds-dir")

    import torch
    from diffusers import StableDiffusionXLPipeline

    keys = args.keys or [c.key for c in CONCEPTS]
    t0 = time.time()
    pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, torch_dtype=torch.float16, variant="fp16",
                                                     use_safetensors=True).to("cuda")
    pipe.set_progress_bar_config(disable=True)
    print(f"loaded {MODEL} in {time.time() - t0:.0f}s; scheduler {type(pipe.scheduler).__name__}", flush=True)

    for key in keys:
        c = BY_KEY[key]
        n = args.n or (16 if args.condition == "default" else c.n_ai)
        folder = args.out / key
        folder.mkdir(parents=True, exist_ok=True)
        meta_path = folder / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        pictures = plan(key, args.condition, n, args.batch, args.kinds_dir)
        prompts = sorted({p for _, p in pictures})
        meta.update({"concept": c.label, "quickdraw": c.quickdraw, "style": "doodle", "condition": args.condition,
                     "prompt": prompts[0] if len(prompts) == 1 else None,
                     "negative_prompt": args.negative, "model": MODEL, "license": "CreativeML OpenRAIL++-M",
                     "dtype": "float16", "steps": args.steps, "size": args.size, "guidance_scale": args.guidance,
                     "scheduler": type(pipe.scheduler).__name__, "saved_side": args.save_side,
                     "batch": args.batch, "n_target": n})
        if args.condition == "listed":
            meta["prompts"] = dict(pictures)
        seeds = meta.get("seeds", {})
        todo = [i for i, (name, _) in enumerate(pictures) if not (folder / name).exists()]
        # one pipeline call per run of pictures with the same prompt (listed: one picture per call)
        groups, cur = [], []
        for i in todo:
            if cur and (len(cur) == args.batch or pictures[i][1] != pictures[cur[0]][1]):
                groups.append(cur)
                cur = []
            cur.append(i)
        groups += [cur] if cur else []
        for idx in groups:
            gens = [torch.Generator("cuda").manual_seed(seed_for(key, i)) for i in idx]
            t1 = time.time()
            imgs = pipe(pictures[idx[0]][1], negative_prompt=args.negative or None, num_images_per_prompt=len(idx),
                        num_inference_steps=args.steps, guidance_scale=args.guidance, height=args.size,
                        width=args.size, generator=gens).images
            for i, img in zip(idx, imgs):
                name = pictures[i][0]
                img.thumbnail((args.save_side, args.save_side), resample=3)  # LANCZOS
                img.save(folder / name)
                seeds[name] = seed_for(key, i)
            print(f"{key:12s} {len(idx)} pictures in {time.time() - t1:.1f}s", flush=True)
        have = sum((folder / name).exists() for name, _ in pictures)
        meta.update(seeds=dict(sorted(seeds.items(), key=lambda kv: kv[1])), n=have, complete=have >= n)
        meta_path.write_text(json.dumps(meta, indent=1))
    print(f"done in {time.time() - t0:.0f}s; peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


if __name__ == "__main__":
    main()

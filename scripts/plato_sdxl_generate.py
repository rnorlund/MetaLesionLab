"""Plato's Chair, comparison generator: the same doodle prompts drawn by Stable Diffusion XL.

Is the uniformity specific to Muse Image, or do image models generally draw one prototype? This draws
every concept with stabilityai/stable-diffusion-xl-base-1.0 (fp16, CreativeML OpenRAIL++-M), using the
SAME doodle prompt as the Muse run plus a negative prompt against shading and paper texture.

Usage (on a GPU server, never on the Mac):
  python scripts/plato_sdxl_generate.py --out ~/plato_sdxl/sdxl_doodle [--keys chair ...] [--n 16]

Every picture has its own seed (recorded in meta.json), so the pictures are independent draws.
Pictures are downscaled to 512 px like the Muse ones and saved as <out>/<key>/c<call>_<i>.png, with
4 seeds per "call", so the folder has the same layout and meta.json format as ai/doodle/ and the
core pipeline (plato_embed.py, source ai_sdxl_doodle) reads it unchanged. Copy it to
$PLATO_DIR/ai/sdxl_doodle/ afterwards. Resumable: existing pictures are kept.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato import BY_KEY, CONCEPTS, prompt_for  # noqa: E402

MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
NEGATIVE = "shading, photo, photorealistic, paper texture, 3d render, color, text"
SEED_BASE = 20261026


def seed_for(key: str, i: int) -> int:
    """A distinct, reproducible seed per picture: concept index * 1000 + picture index."""
    return SEED_BASE + 1000 * [c.key for c in CONCEPTS].index(key) + i


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--n", type=int, default=16, help="pictures per concept (all 35 get the same n)")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--guidance", type=float, default=5.0, help="diffusers' SDXL default")
    ap.add_argument("--negative", default=NEGATIVE, help="'' for none")
    ap.add_argument("--save-side", type=int, default=512)
    args = ap.parse_args()

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
        folder = args.out / key
        folder.mkdir(parents=True, exist_ok=True)
        meta_path = folder / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        prompt = prompt_for(c, "doodle")
        meta.update({"concept": c.label, "quickdraw": c.quickdraw, "style": "doodle", "prompt": prompt,
                     "negative_prompt": args.negative, "model": MODEL, "license": "CreativeML OpenRAIL++-M",
                     "dtype": "float16", "steps": args.steps, "size": args.size, "guidance_scale": args.guidance,
                     "scheduler": type(pipe.scheduler).__name__, "saved_side": args.save_side,
                     "batch": args.batch, "n_target": args.n})
        seeds = meta.get("seeds", {})
        todo = [i for i in range(args.n) if not (folder / f"c{i // args.batch}_{i % args.batch}.png").exists()]
        for s in range(0, len(todo), args.batch):
            idx = todo[s:s + args.batch]
            gens = [torch.Generator("cuda").manual_seed(seed_for(key, i)) for i in idx]
            t1 = time.time()
            imgs = pipe(prompt, negative_prompt=args.negative or None, num_images_per_prompt=len(idx),
                        num_inference_steps=args.steps, guidance_scale=args.guidance, height=args.size,
                        width=args.size, generator=gens).images
            for i, img in zip(idx, imgs):
                name = f"c{i // args.batch}_{i % args.batch}.png"
                img.thumbnail((args.save_side, args.save_side), resample=3)  # LANCZOS
                img.save(folder / name)
                seeds[name] = seed_for(key, i)
            print(f"{key:12s} {len(idx)} pictures in {time.time() - t1:.1f}s", flush=True)
        have = len(list(folder.glob("c*_*.png")))
        meta.update(seeds=dict(sorted(seeds.items(), key=lambda kv: kv[1])), n=have, complete=have >= args.n)
        meta_path.write_text(json.dumps(meta, indent=1))
    print(f"done in {time.time() - t0:.0f}s; peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


if __name__ == "__main__":
    main()

"""The Atlas of Forms: Stable Diffusion XL draws the 98 new concepts, 12 each, with the core settings.

Usage (on a GPU server, never on the Mac):
  python scripts/plato_atlas_sdxl.py --out ~/plato_atlas/sdxl_doodle [--keys ant ...] [--n 12]

Same model, prompt, negative prompt and settings as the core comparison (plato_sdxl_generate.py):
768 px, 25 steps, the default Euler scheduler, guidance 5, fp16. Seeds are pre-registered:
20261026 + 1000 * (100 + new-concept index) + picture index (the core used concept indexes 0-36).
Pictures are downscaled to 512 px and saved as <out>/<key>/c<call>_<i>.png (4 per "call") with a
meta.json, the same layout as the core. Copy the folder to $PLATO_ATLAS_DIR/ai/sdxl_doodle/ afterwards.
Resumable: existing pictures are kept.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plato_sdxl_generate import MODEL, NEGATIVE, SEED_BASE  # noqa: E402

from metalesionlab.plato_atlas import BY_KEY, N_NEW, NEW, SDXL_INDEX0, prompt_for  # noqa: E402

NEW_KEYS = [c.key for c in NEW]


def seed_for(key: str, i: int) -> int:
    return SEED_BASE + 1000 * (SDXL_INDEX0 + NEW_KEYS.index(key)) + i


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--n", type=int, default=N_NEW)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--guidance", type=float, default=5.0)
    ap.add_argument("--save-side", type=int, default=512)
    args = ap.parse_args()

    import torch
    from diffusers import StableDiffusionXLPipeline

    t0 = time.time()
    pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, torch_dtype=torch.float16, variant="fp16",
                                                     use_safetensors=True).to("cuda")
    pipe.set_progress_bar_config(disable=True)
    print(f"loaded {MODEL} in {time.time() - t0:.0f}s; scheduler {type(pipe.scheduler).__name__}", flush=True)
    for key in args.keys or NEW_KEYS:
        c = BY_KEY[key]
        folder = args.out / key
        folder.mkdir(parents=True, exist_ok=True)
        meta_path = folder / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        prompt = prompt_for(c)
        meta.update({"concept": c.label, "quickdraw": c.quickdraw, "style": "doodle", "condition": "default",
                     "prompt": prompt, "negative_prompt": NEGATIVE, "model": MODEL,
                     "license": "CreativeML OpenRAIL++-M", "dtype": "float16", "steps": args.steps,
                     "size": args.size, "guidance_scale": args.guidance,
                     "scheduler": type(pipe.scheduler).__name__, "saved_side": args.save_side,
                     "batch": args.batch, "n_target": args.n})
        seeds = meta.get("seeds", {})
        names = [f"c{i // args.batch}_{i % args.batch}.png" for i in range(args.n)]
        todo = [i for i, name in enumerate(names) if not (folder / name).exists()]
        for start in range(0, len(todo), args.batch):
            idx = todo[start:start + args.batch]
            gens = [torch.Generator("cuda").manual_seed(seed_for(key, i)) for i in idx]
            t1 = time.time()
            imgs = pipe(prompt, negative_prompt=NEGATIVE, num_images_per_prompt=len(idx),
                        num_inference_steps=args.steps, guidance_scale=args.guidance, height=args.size,
                        width=args.size, generator=gens).images
            for i, img in zip(idx, imgs):
                img.thumbnail((args.save_side, args.save_side), resample=3)  # LANCZOS
                img.save(folder / names[i])
                seeds[names[i]] = seed_for(key, i)
            print(f"{key:16s} {len(idx)} pictures in {time.time() - t1:.1f}s", flush=True)
        have = sum((folder / n).exists() for n in names)
        meta.update(seeds=dict(sorted(seeds.items(), key=lambda kv: kv[1])), n=have, complete=have >= args.n)
        meta_path.write_text(json.dumps(meta, indent=1))
    print(f"done in {time.time() - t0:.0f}s; peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


if __name__ == "__main__":
    main()

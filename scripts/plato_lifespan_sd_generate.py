"""The life of a chair, AI arm: the same doodle prompts drawn by Stable Diffusion at five training stages.

v1.1 -> v1.2 -> {v1.3, v1.4, v1.5} (see plato_lifespan.CHECKPOINTS). Every checkpoint gets the SAME prompt,
negative prompt, settings and seeds, so picture i of a thing starts from the same noise at every stage and
only the weights differ. All five repos are ungated (no token); CreativeML OpenRAIL-M.

Usage (on a GPU server, never on the Mac; diffusers may live in a private folder on PYTHONPATH):
  python scripts/plato_lifespan_sd_generate.py --out ~/plato_lifespan/sd [--keys chair ...] [--ckpts v1.1 ...]
  python scripts/plato_lifespan_sd_generate.py --out ~/plato_lifespan/sd_g4 --guidance 4   # robustness

Pictures: <out>/<ckpt>/<key>/s<i>.png (512 px) and a meta.json per folder with every seed. Resumable:
existing pictures are kept. Copy <out> to PlatosChair/lifespan/ai/sd/ afterwards.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato import BY_KEY, prompt_for  # noqa: E402
from metalesionlab.plato_lifespan import AI_KEYS, CHECKPOINTS, SD_NEGATIVE, sd_seed  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--keys", nargs="*", help="default: all 21 (tier 1 first)")
    ap.add_argument("--ckpts", nargs="*", help="default: all five, in training order")
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--guidance", type=float, default=7.5, help="the SD 1.x default")
    ap.add_argument("--negative", default=SD_NEGATIVE, help="'' for none")
    args = ap.parse_args()

    import torch
    from diffusers import EulerDiscreteScheduler, StableDiffusionPipeline

    keys = args.keys or AI_KEYS
    ckpts = [c for c in CHECKPOINTS if not args.ckpts or c[0] in args.ckpts]
    t0 = time.time()
    for name, repo, ksteps, parent in ckpts:
        todo_any = any(not (args.out / name / k / f"s{i}.png").exists() for k in keys for i in range(args.n))
        if not todo_any:
            print(f"{name}: complete", flush=True)
            continue
        t1 = time.time()
        pipe = StableDiffusionPipeline.from_pretrained(repo, torch_dtype=torch.float16, variant="fp16",
                                                       use_safetensors=True, safety_checker=None,
                                                       requires_safety_checker=False)
        pipe.scheduler = EulerDiscreteScheduler.from_config(pipe.scheduler.config)
        pipe = pipe.to("cuda")
        pipe.set_progress_bar_config(disable=True)
        pipe.vae.enable_slicing()
        print(f"loaded {name} ({repo}) in {time.time() - t1:.0f}s", flush=True)
        for key in keys:
            c = BY_KEY[key]
            prompt = prompt_for(c, "doodle")
            folder = args.out / name / key
            folder.mkdir(parents=True, exist_ok=True)
            todo = [i for i in range(args.n) if not (folder / f"s{i}.png").exists()]
            for j in range(0, len(todo), args.batch):
                idx = todo[j:j + args.batch]
                gens = [torch.Generator("cuda").manual_seed(sd_seed(key, i)) for i in idx]
                t2 = time.time()
                imgs = pipe(prompt, negative_prompt=args.negative or None, num_images_per_prompt=len(idx),
                            num_inference_steps=args.steps, guidance_scale=args.guidance, height=args.size,
                            width=args.size, generator=gens).images
                for i, img in zip(idx, imgs):
                    img.save(folder / f"s{i}.png")
                print(f"{name} {key:10s} {len(idx)} pictures in {time.time() - t2:.1f}s", flush=True)
            meta = {"checkpoint": name, "repo": repo, "cumulative_ksteps": ksteps, "parent": parent,
                    "license": "CreativeML OpenRAIL-M", "concept": c.label, "quickdraw": c.quickdraw,
                    "prompt": prompt, "negative_prompt": args.negative, "dtype": "float16", "steps": args.steps,
                    "size": args.size, "guidance_scale": args.guidance, "scheduler": type(pipe.scheduler).__name__,
                    "safety_checker": None, "seeds": {f"s{i}.png": sd_seed(key, i) for i in range(args.n)},
                    "n": sum((folder / f"s{i}.png").exists() for i in range(args.n))}
            (folder / "meta.json").write_text(json.dumps(meta, indent=1))
        del pipe
        torch.cuda.empty_cache()
    print(f"done in {time.time() - t0:.0f}s; peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


if __name__ == "__main__":
    main()

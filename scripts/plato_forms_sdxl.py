"""Plato's Forms on Stable Diffusion XL: the same clock prompts, and the bed and the table (GPU server only).

Usage (on a GPU server, from a copy of the repository):
  python scripts/plato_forms_sdxl.py clock --out ~/plato_forms
  python scripts/plato_forms_sdxl.py concepts --out ~/plato_forms --kinds-dir ~/plato_forms/kinds

Settings are the core SDXL run's (scripts/plato_sdxl_generate.py): stabilityai/stable-diffusion-xl-base-1.0,
fp16, 768 px, 25 steps, the default Euler scheduler, guidance 5, saved at 512 px. Doodles use the core
negative prompt; photos use none (the core negative prompt says "photo").
- clock: doodles for the 12 requested times (8 each) and photos with no time (16) and for the 6 photo
  times (8 each), in <out>/clock/sdxl/<style>/<any|t0120...>/c<call>_<i>.png. The no-time doodle is the
  core SDXL clock set (same prompt and settings), copied in on the Mac.
  Seed of picture i in condition k: 20261027 + 1000 k + i (k counts the doodle conditions, then the photo ones).
- concepts: bed and table, usual prompt, "any kind" and Muse Spark's named kinds (<kinds-dir>/<key>.json),
  16 each, in <out>/ai/sdxl_doodle|sdxl_any|sdxl_listed/<key>/. Seeds continue the core scheme with
  concept indexes 35 (bed) and 36 (table), the same seeds in every condition.
Copy <out>/ back into $PLATO_FORMS_DIR. Resumable; every seed is recorded in meta.json.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato import STYLES, prompt_for  # noqa: E402
from metalesionlab.plato_forms import (CLOCK_TIMES, FORMS_CONCEPTS, PER_DEFAULT, PER_TIME, PHOTO_TIMES,  # noqa: E402
                                       clock_prompt, slug)

MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
NEGATIVE = "shading, photo, photorealistic, paper texture, 3d render, color, text"  # the core doodle negative
CLOCK_SEED = 20261027
CORE_SEED, N_CORE = 20261026, 35
CLOCK_CONDS = ([("doodle", None)] + [("doodle", t) for t in CLOCK_TIMES]
               + [("photo", None)] + [("photo", t) for t in PHOTO_TIMES])


def clock_plan() -> list[dict]:
    """One entry per condition still to draw on the server (the no-time doodle is the core's)."""
    out = []
    for k, (style, t) in enumerate(CLOCK_CONDS):
        if style == "doodle" and t is None:
            continue
        n = PER_DEFAULT if t is None else PER_TIME
        out.append({"dir": f"clock/sdxl/{style}/{slug(t)}", "style": style, "time": t,
                    "negative": NEGATIVE if style == "doodle" else "",
                    "pictures": [(f"c{i // 4}_{i % 4}.png", clock_prompt(style, t), CLOCK_SEED + 1000 * k + i)
                                 for i in range(n)]})
    return out


def concept_plan(kinds_dir: Path | None) -> list[dict]:
    out = []
    for j, c in enumerate(FORMS_CONCEPTS):
        seed = lambda i: CORE_SEED + 1000 * (N_CORE + j) + i  # noqa: E731
        for cond, folder in (("default", "sdxl_doodle"), ("any", "sdxl_any"), ("listed", "sdxl_listed")):
            if cond == "listed":
                if not kinds_dir or not (kinds_dir / f"{c.key}.json").exists():
                    continue
                kinds = json.loads((kinds_dir / f"{c.key}.json").read_text())[:c.n_ai]
                pics = [(f"p{i}.png", STYLES["doodle"].format(phrase=k), seed(i)) for i, k in enumerate(kinds)]
            else:
                p = prompt_for(c, "doodle" if cond == "default" else "doodle_any")
                pics = [(f"c{i // 4}_{i % 4}.png", p, seed(i)) for i in range(c.n_ai)]
            out.append({"dir": f"ai/{folder}/{c.key}", "style": "doodle", "condition": cond, "concept": c.label,
                        "negative": NEGATIVE, "pictures": pics})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["clock", "concepts"])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--kinds-dir", type=Path)
    ap.add_argument("--steps", type=int, default=25)
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--guidance", type=float, default=5.0)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    plan = clock_plan() if args.what == "clock" else concept_plan(args.kinds_dir)
    todo = sum(not (args.out / g["dir"] / name).exists() for g in plan for name, _, _ in g["pictures"])
    print(f"{len(plan)} conditions, {todo} pictures to draw", flush=True)
    if args.dry_run or not todo:
        return

    import torch
    from diffusers import StableDiffusionXLPipeline

    t0 = time.time()
    pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, torch_dtype=torch.float16, variant="fp16",
                                                     use_safetensors=True).to("cuda")
    pipe.set_progress_bar_config(disable=True)
    print(f"loaded {MODEL} in {time.time() - t0:.0f}s; scheduler {type(pipe.scheduler).__name__}", flush=True)
    for g in plan:
        folder = args.out / g["dir"]
        folder.mkdir(parents=True, exist_ok=True)
        pics = [p for p in g["pictures"] if not (folder / p[0]).exists()]
        # one pipeline call per run of up to `batch` pictures with the same prompt
        groups, cur = [], []
        for p in pics:
            if cur and (len(cur) == args.batch or p[1] != cur[0][1]):
                groups.append(cur)
                cur = []
            cur.append(p)
        groups += [cur] if cur else []
        for grp in groups:
            gens = [torch.Generator("cuda").manual_seed(s) for _, _, s in grp]
            imgs = pipe(grp[0][1], negative_prompt=g["negative"] or None, num_images_per_prompt=len(grp),
                        num_inference_steps=args.steps, guidance_scale=args.guidance, height=args.size,
                        width=args.size, generator=gens).images
            for (name, _, _), img in zip(grp, imgs):
                img.thumbnail((512, 512), resample=3)  # LANCZOS
                img.save(folder / name)
        prompts = sorted({p for _, p, _ in g["pictures"]})
        meta = {k: v for k, v in g.items() if k not in ("pictures", "dir")}
        meta.update(model=MODEL, license="CreativeML OpenRAIL++-M", dtype="float16", steps=args.steps, size=args.size,
                    guidance_scale=args.guidance, scheduler=type(pipe.scheduler).__name__, saved_side=512,
                    negative_prompt=g["negative"], prompt=prompts[0] if len(prompts) == 1 else None,
                    prompts=None if len(prompts) == 1 else {n: p for n, p, _ in g["pictures"]},
                    seeds={n: s for n, _, s in g["pictures"]}, n_target=len(g["pictures"]),
                    n=sum((folder / n).exists() for n, _, _ in g["pictures"]))
        meta["complete"] = meta["n"] >= meta["n_target"]
        (folder / "meta.json").write_text(json.dumps(meta, indent=1))
        print(f"{g['dir']:32s} {len(pics)} new pictures ({time.time() - t0:.0f}s)", flush=True)
    print(f"done in {time.time() - t0:.0f}s; peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


if __name__ == "__main__":
    main()

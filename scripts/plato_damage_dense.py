"""Denser damage ladders for the hero rows on /damaged and /plato/damage (a display upgrade, not a new experiment).

Same pipeline, prompts, seeds and settings as the damage experiment (scripts/plato_damage_sdxl.py, docs/plato_damage.md)
and God's ideas run (scripts/draw_damage_sdxl.py): Stable Diffusion XL, 768 px, 25 steps, guidance 5, one fixed seed per
row at every level. Only the dose ladder is denser: undamaged plus 9 doses, ending at the strongest dose the hero used.

  python scripts/plato_damage_dense.py --stats unit_stats.pt --out DIR [--rows rocking throne god clock]

Writes DIR/<row>/s_<level>.png (level 0 = undamaged) and DIR/<row>/meta.json. Resumable. GPU part; no API calls.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from metalesionlab.plato_damage import BY_KEY, NEGATIVE, family_spec, seed_for  # noqa: E402
from metalesionlab.sdxl_lesions import DamageSpec, SDXLDamage  # noqa: E402

MODEL = "stabilityai/stable-diffusion-xl-base-1.0"
LADDER_TEXT = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]          # strongest = the hero's 1.0
LADDER_UNET = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10]  # strongest = the hero's 1.1


def rows():
    import draw_damage_sdxl as D  # the ideas run's prompt and seeds

    def kind(key, i):
        return BY_KEY[key].prompt, seed_for(BY_KEY[key], i)

    return {
        "rocking": ("chair__rocking_chair", *kind("chair__rocking_chair", 1), "text-noise", LADDER_TEXT),
        "throne": ("chair__throne", *kind("chair__throne", 0), "text-noise", LADDER_TEXT),
        "god": ("god", D.prompt("god"), D.seed_for("god", 13), "text-noise", LADDER_TEXT),
        "clock": ("clock__8_45", *kind("clock__8_45", 0), "unet-noise", LADDER_UNET),
    }


def main():
    import torch
    from diffusers import StableDiffusionXLPipeline

    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rows", nargs="*", default=["rocking", "throne", "god", "clock"])
    a = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "mps"
    pipe = StableDiffusionXLPipeline.from_pretrained(MODEL, torch_dtype=torch.float16, variant="fp16",
                                                     use_safetensors=True).to(device)
    pipe.set_progress_bar_config(disable=True)
    engine = SDXLDamage(pipe, stats=torch.load(a.stats))
    spec_rows, t0 = rows(), time.time()
    for name in a.rows:
        key, prompt, seed, fam, doses = spec_rows[name]
        out = a.out / name
        out.mkdir(parents=True, exist_ok=True)
        meta = {"key": key, "prompt": prompt, "seed": seed, "family": fam, "doses": [0.0] + doses, "device": device,
                "steps": 25, "size": 768, "guidance_scale": 5.0, "negative": NEGATIVE, "model": MODEL}
        (out / "meta.json").write_text(json.dumps(meta, indent=1))
        for lvl, dose in enumerate([0.0] + doses):
            f = out / f"s_{lvl}.png"
            if f.exists():
                continue
            spec = DamageSpec(name="intact") if lvl == 0 else DamageSpec.from_dict(family_spec(fam, dose))
            with engine.apply(spec):
                engine.reset()
                g = torch.Generator(device).manual_seed(seed)
                im = pipe(prompt, negative_prompt=NEGATIVE, num_inference_steps=25, guidance_scale=5.0, height=768,
                          width=768, generator=g).images[0]
            im.thumbnail((512, 512), resample=3)
            im.save(f)
            print(name, lvl, dose, f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()

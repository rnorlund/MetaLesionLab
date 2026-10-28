"""God and the other ideas, damaged: Stable Diffusion XL's drawings of the 11 ideas and the 4 words under the draw
pad's damage (docs/plato_ideas_damage_plan.md).

Muse Image is a closed API and cannot be damaged, so, as for the concrete things' strips on the draw pad, the
damaged drawer is Stable Diffusion XL (an open model). Everything about the pictures is the pad's pipeline,
unchanged (scripts/draw_damage_sdxl.py): the doodle template with the phrase Muse Image was given, 768 px, 25
steps, guidance 5, the SDXL comparison's negative prompt, saved at 512 px, and noise in every neuron of the text
encoders ("the part that handles words") or of the UNet ("the part that draws") at the strip's five doses, with
the damage experiment's unit statistics. Picture i of a key has the same seed in every condition. God also gets
the damage experiment's "neurons switched off" doses, for the /plato/ideas slider.

What is measured (pre-registered):
- severity: DINOv2-base CLS distance of the ink-cropped picture to its intact twin (as in plato_damage);
- the emblem: Muse Glimmer's multiple choice with the idea's own options (plato_ideas.options), forward and
  reversed, as in the ideas labeling; "same emblem" = the intact twin's label kept;
- yes/no questions to Glimmer (P(yes) from the answer logits): a person, a beard and a halo (God), and the
  damage experiment's "clean, simple line drawing" question (every picture);
- for God, the same three features by eye, from contact sheets, before Glimmer's answers are read.
"""
from __future__ import annotations

import numpy as np

from metalesionlab import plato_ideas as I

# The pad's things come first so their seeds are unchanged (scripts/draw_damage_sdxl.py THINGS order); the ideas
# follow in their drawing order, then the words.
THINGS = ["chair", "umbrella", "bicycle", "house", "cat", "tree", "face", "sailboat", "cup", "book"]
IDEA_KEYS = [i.key for i in I.IDEAS]
WORD_KEYS = [w.key for w in I.WORDS]
KEYS = THINGS + IDEA_KEYS + WORD_KEYS

N_SEEDS = {"god": 16}  # God: 16 seeds, as many as Muse's 16 drawings; every other idea and word: 8
N_DEFAULT = 8

# The pad strip's doses (scripts/draw_damage_export.ROWS), unchanged.
NOISE = {"text-noise": [0.25, 0.5, 0.625, 0.75, 1.0], "unet-noise": [0.75, 0.825, 0.9, 1.0, 1.1]}
# God only: the damage experiment's "neurons switched off" doses (docs/plato_damage.md), for the slider.
ZERO = {"text-zero": [0.2, 0.25, 0.27, 0.29, 0.31], "unet-zero": [0.05, 0.1, 0.15, 0.2]}
PAIRS = {"noise": ("text-noise", "unet-noise"), "zero": ("text-zero", "unet-zero")}


def n_seeds(key: str) -> int:
    return N_SEEDS.get(key, N_DEFAULT)


def cond(family: str, dose: float) -> str:
    return f"{family}@{dose:g}"


def conditions(key: str) -> list[str]:
    fams = {**NOISE, **(ZERO if key == "god" else {})}
    return ["intact"] + [cond(f, d) for f, doses in fams.items() for d in doses]


# Glimmer's yes/no questions. The person question goes to every picture (does the idea turn into people?), the
# beard and halo questions to God's. CLEAN is plato_damage_glimmer.CLEAN, word for word.
PERSON = "Does this drawing show a person or a human figure? Answer yes or no."
BEARD = "Does a person in this drawing have a beard? Answer yes or no."
HALO = "Is there a halo, or a ring or glow of light, around a person's head in this drawing? Answer yes or no."
CLEAN = ("Is this a clean, simple line drawing, with black lines on a plain white background and no color, "
         "shading or texture? Answer yes or no.")
GOD_FEATURES = ("person", "beard", "halo")


def generic_person(person: bool, beard: bool, halo: bool) -> bool:
    """A human figure with neither of God's emblems: what 'drifts toward a generic person' counts."""
    return bool(person and not beard and not halo)


def medoid(x: np.ndarray) -> int:
    """The strip's seed (pre-registered): the intact picture with the smallest mean cosine distance to the key's
    other intact pictures, i.e. SDXL's most typical intact drawing. Chosen without looking at any damage."""
    u = x / np.linalg.norm(x, axis=1, keepdims=True)
    d = 1.0 - u @ u.T
    return int(np.argmin(d.sum(1) / (len(x) - 1)))


def fails_first(rates: dict[str, list[float]], intact: dict[str, float]) -> dict[str, float | None]:
    """For each feature, the first dose index (0-based over the damaged doses) at which its rate falls below half
    its intact rate (the damage plan's H6 rule); None if it never does or was absent intact."""
    out = {}
    for f, r in rates.items():
        base = intact[f]
        hit = [i for i, v in enumerate(r) if base > 0 and v < base / 2]
        out[f] = hit[0] if hit else None
    return out

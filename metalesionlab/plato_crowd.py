"""Ask it to be a crowd: does giving Muse Image a different age for each drawing give it people's variety?

Asked 16 times for "a quick simple doodle sketch of a chair", Muse Image draws nearly the same chair (spread 0.13,
against 0.36 for 16 people's Quick, Draw! chairs). Each API call is independent, so the 16 drawings are like 16
strangers sharing one mind. Here each of the 16 calls gets one stated age, and nothing else about the person:

    "Drawn by a 34-year-old: a quick simple doodle sketch of a chair, black marker on plain white, ..."

The house prompt (plato.STYLES["doodle"]) is kept word for word after the prefix, with its first letter lowercased.
The concepts are the draw pad's 10 things and God (from the invisible Forms). The 16 ages are the same for every
concept: 20, 24, ... 80. Pre-registered in docs/plato_crowd_plan.md; results in docs/plato_crowd.md.

Data lives outside the repository, in $PLATO_CROWD_DIR (default PlatosChair/crowd, next to core/ and ideas/, which
are only read): ai/persona/<key>/pNN_ageAA.png, calls.jsonl, spend.jsonl, embeddings and results.json.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from metalesionlab import plato, plato_ideas

CROWD_DIR = Path(os.environ.get("PLATO_CROWD_DIR", str(plato.PLATO_DIR.parent / "crowd")))
IDEAS_DIR = plato_ideas.IDEAS_DIR

AGES = tuple(range(20, 81, 4))  # 16 adult ages, evenly spaced from 20 to 80; picture i of every concept is AGES[i]
THINGS = ("chair", "umbrella", "bicycle", "house", "cat", "tree", "face", "sailboat", "cup", "book")  # the draw pad's 10
IDEA = "god"
KEYS = THINGS + (IDEA,)
# The drawing order: if spending stops early, the chair and God exist first.
DRAW_ORDER = ("chair", "god", "umbrella", "bicycle", "house", "cat", "tree", "face", "sailboat", "cup", "book")
PILOT = (("chair", 80), ("god", 20))  # two pictures, one call each, to check the prompt; not analysed
MIN_PICTURES = 12  # a concept with fewer persona pictures than this is reported but left out of the tests

# Spend: the task's own cap, counted at the conservative $0.026 a picture used by the invisible Forms (the shared
# ledger books $0.01). No paid call once the shared ledger reaches SHARED_STOP.
IMAGE_USD = 0.026
BUDGET_USD = 5.0
SHARED_STOP = 72.0
MAX_ATTEMPTS = 3  # a refused call (4xx) is tried at most 3 times in all; every refusal is recorded

SEED = 20261029
B_AI, B_HUMAN, SUBSETS = 2000, 500, 200  # the house numbers (scripts/plato_analyze.py)
B_PAIRED, PERMS = 10000, 10000
# The house preparation, unchanged (scripts/plato_embed.py); a cached embedding made any other way is refused.
PREP = "flatten_paper(21, 215) + ink_crop(256, margin 0.06, threshold 200, speck 3px)"


# ---------- prompts ----------

def article(n: int) -> str:
    """'an' before an age said with a vowel sound (8, 11, 18, 80-89), else 'a'."""
    s = str(int(n))
    return "an" if s.startswith("8") or s in ("11", "18") else "a"


def persona(age: int) -> str:
    return f"Drawn by {article(age)} {int(age)}-year-old"


def base_prompt(key: str) -> str:
    """The prompt the first run used for this concept: the things' doodle prompt, or the idea's (the same template)."""
    if key in plato_ideas.BY_KEY:
        return plato_ideas.prompt_for(plato_ideas.BY_KEY[key])
    return plato.prompt_for(plato.BY_KEY[key], "doodle")


def prompt_for(key: str, age: int) -> str:
    """'Drawn by a 34-year-old: a quick simple doodle sketch of a chair, black marker on plain white, ...'"""
    base = base_prompt(key)
    return f"{persona(age)}: {base[0].lower()}{base[1:]}"


def label(key: str) -> str:
    if key in plato_ideas.BY_KEY:
        return plato_ideas.BY_KEY[key].label
    return plato.BY_KEY[key].label


def file_name(i: int, age: int) -> str:
    return f"p{i:02d}_age{int(age)}.png"


def age_of(name: str) -> int:
    """The stated age from a picture's file name (pNN_ageAA.png)."""
    return int(Path(name).stem.split("_age")[1])


def folder(key: str, root: Path | None = None) -> Path:
    return (root or CROWD_DIR) / "ai" / "persona" / key


def default_embeddings_path(key: str) -> Path:
    """The cached DINOv2 embeddings of the first-run doodles (the default prompt)."""
    if key in plato_ideas.BY_KEY:
        return IDEAS_DIR / "embeddings" / "ai_doodle" / f"{key}.npz"
    return plato.PLATO_DIR / "embeddings" / "ai_doodle" / f"{key}.npz"


def default_pictures_dir(key: str) -> Path:
    if key in plato_ideas.BY_KEY:
        return plato_ideas.folder(key)
    return plato.PLATO_DIR / "ai" / "doodle" / key


def people_embeddings_path(key: str) -> Path | None:
    """People's 200 Quick, Draw! drawings, embedded the same way; None for an idea (there are none)."""
    if key in plato_ideas.BY_KEY:
        return None
    return plato.PLATO_DIR / "embeddings" / "human" / f"{key}.npz"


# ---------- statistics ----------

def unit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def centroid(x: np.ndarray) -> np.ndarray:
    """The unit mean of a set's unit vectors (the draw pad's prototype)."""
    return unit(unit(x).mean(0))


def distance_to(x: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Cosine distance of each row of x to the vector c."""
    return 1.0 - unit(x) @ unit(c)


def loo_distances(x: np.ndarray) -> np.ndarray:
    """Each picture's cosine distance to the unit mean of the set's other pictures."""
    u = unit(x)
    others = unit((u.sum(0)[None, :] - u) / (len(u) - 1))
    return 1.0 - (others * u).sum(1)


def paired_mean_diff_boot(a_boots: list[np.ndarray], b_boots: list[np.ndarray], reps: int = B_PAIRED,
                          rng: np.random.Generator | None = None) -> np.ndarray:
    """Two-level bootstrap of the mean over items of (a - b), items paired: resample the items with replacement,
    and for each drawn item take one draw from its own picture-level bootstrap of a and one of b."""
    if len(a_boots) != len(b_boots) or not a_boots:
        raise ValueError("need the same, non-zero number of items on both sides")
    rng = rng or np.random.default_rng(SEED)
    k = len(a_boots)
    out = np.empty(reps)
    for r in range(reps):
        idx = rng.integers(0, k, k)
        out[r] = np.mean([a_boots[i][rng.integers(len(a_boots[i]))] - b_boots[i][rng.integers(len(b_boots[i]))]
                          for i in idx])
    return out


def signflip_p(diffs, reps: int = PERMS, rng: np.random.Generator | None = None, greater: bool = True) -> float:
    """One-sided sign-flip permutation p for mean(diffs) > 0 (or < 0 with greater=False), items paired."""
    rng = rng or np.random.default_rng(SEED)
    d = np.asarray(diffs, float)
    obs = d.mean()
    flips = rng.choice([-1.0, 1.0], size=(reps, len(d)))
    null = (flips * d).mean(1)
    hits = (null >= obs - 1e-12) if greater else (null <= obs + 1e-12)
    return float((hits.sum() + 1) / (reps + 1))


def age_trend(dist: dict[str, np.ndarray], ages: dict[str, np.ndarray], reps: int = PERMS,
              rng: np.random.Generator | None = None) -> dict:
    """Does the drawing change with stated age? For each concept, Spearman's rho between the persona's age and
    the picture's distance from the default centroid. The statistic is the mean rho over concepts; its p is
    two-sided, from shuffling the ages within each concept; its 95% CI comes from resampling the concepts."""
    rng = rng or np.random.default_rng(SEED)
    keys = list(dist)
    per = {k: plato.spearman(ages[k], dist[k]) for k in keys}
    obs = float(np.mean([per[k] for k in keys]))
    null = np.empty(reps)
    for r in range(reps):
        null[r] = np.mean([plato.spearman(rng.permutation(ages[k]), dist[k]) for k in keys])
    p = float(((np.abs(null) >= abs(obs) - 1e-12).sum() + 1) / (reps + 1))
    rhos = np.array([per[k] for k in keys])
    boots = np.array([rhos[rng.integers(0, len(rhos), len(rhos))].mean() for _ in range(min(reps, 5000))])
    return {"mean_rho": obs, "ci95": plato.ci(boots), "p_perm_two_sided": p, "per_concept": per, "n_concepts": len(keys)}

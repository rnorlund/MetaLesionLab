"""The Atlas of Forms: Plato's Chair scaled from 35 to 135 everyday things, as a reusable benchmark.

Concepts (pre-registered in docs/plato_atlas_plan.md, before any new picture was made):
- the 35 Plato's Chair core concepts, unchanged (metalesionlab/plato.py; data in PlatosChair/core);
- Plato's own bed and table from Plato's Forms (same prompt and protocol; data in PlatosChair/forms);
- 98 new Quick, Draw! categories: every category is either eligible, sorted into one a-priori domain, or
  excluded for a stated reason (EXCLUDED); rain, hurricane and snowman (named in the brief) are always in;
  the rest are a seeded random draw within domains (QUOTAS, SEED). select_new() reproduces the list.

Each concept also carries an a-priori "natural" flag (not made by people: animals, plants, fruit and
vegetables, body parts, landscape, sky and weather) for the exploratory natural-kind-vs-artifact test.

The same module holds the pieces the benchmark (scripts/plato_benchmark.py) shares with the analysis:
the human reference set, spread ratios with bootstrap CIs, and the pixel-average "Form" of a set.
Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from metalesionlab import plato

ATLAS_DIR = Path(os.environ.get("PLATO_ATLAS_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/atlas"))
FORMS_DIR = Path(os.environ.get("PLATO_FORMS_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/forms"))
SEED = 20261027
N_NEW = 12          # Muse Image and SDXL pictures per new concept (3 calls of n = 4)
N_HUMAN = 200       # first recognized Quick, Draw! drawings per concept
SDXL_INDEX0 = 100   # SDXL seeds: 20261026 + 1000 * (100 + new-concept index) + picture index (core used 0-36)

# ---------- the 345 Quick, Draw! categories, sorted before drawing anything ----------
FORMS_KEYS = ["bed", "table"]  # Plato's Forms (Republic X): already drawn with the core protocol

# Excluded, with the reason. Every category that is not core, forms or eligible is listed here.
EXCLUDED = {
    "abstract shape, not a thing": ["circle", "square", "triangle", "hexagon", "octagon", "line", "squiggle",
                                    "zigzag", "star", "diamond"],
    "proper noun or landmark": ["The Eiffel Tower", "The Great Wall of China", "The Mona Lisa"],
    "imaginary": ["angel", "dragon", "mermaid", "flying saucer"],
    "weapon": ["cannon", "rifle", "sword", "aircraft carrier"],
    "not an object": ["animal migration", "camouflage", "spreadsheet", "stitches"],
    "ambiguous word (two common things)": ["bat", "mouse", "nail", "pool", "fan", "compass"],
    "near-duplicate of a core or forms concept": ["coffee cup", "mug", "alarm clock", "smiley face", "palm tree",
                                                  "police car", "school bus", "pickup truck", "birthday cake",
                                                  "goatee"],
}

# Eligible, by a-priori domain. Domains are for the stratified draw and the page's filters only.
ELIGIBLE = {
    "animals": ["ant", "bear", "bee", "butterfly", "camel", "cow", "crab", "crocodile", "dolphin", "duck",
                "elephant", "flamingo", "frog", "giraffe", "hedgehog", "horse", "kangaroo", "lion", "lobster",
                "monkey", "mosquito", "octopus", "owl", "panda", "parrot", "penguin", "pig", "rabbit", "raccoon",
                "rhinoceros", "scorpion", "sea turtle", "shark", "sheep", "snake", "spider", "squirrel", "swan",
                "tiger", "whale", "zebra"],
    "food": ["asparagus", "banana", "blackberry", "blueberry", "bread", "broccoli", "cake", "cookie", "donut",
             "grapes", "hamburger", "hot dog", "ice cream", "lollipop", "mushroom", "onion", "peanut", "pear", "peas",
             "pizza", "popsicle", "potato", "sandwich", "steak", "strawberry", "string bean", "watermelon"],
    "household": ["bandage", "basket", "bathtub", "bottlecap", "broom", "bucket", "calendar", "ceiling fan",
                  "chandelier", "cooler", "couch", "dishwasher", "door", "dresser", "envelope", "fireplace", "fork",
                  "frying pan", "hot tub", "hourglass", "knife", "lantern", "light bulb", "lighter", "matches",
                  "microwave", "oven", "picture frame", "pillow", "power outlet", "sink", "sleeping bag", "stove",
                  "suitcase", "teapot", "tent", "toaster", "toilet", "toothbrush", "toothpaste", "vase",
                  "washing machine", "wine bottle", "wine glass"],
    "tools and stationery": ["anvil", "axe", "binoculars", "crayon", "drill", "eraser", "flashlight", "garden hose",
                             "hammer", "map", "marker", "paint can", "paintbrush", "paper clip", "passport", "pencil",
                             "pliers", "postcard", "rake", "screwdriver", "shovel", "stethoscope", "syringe"],
    "electronics": ["calculator", "camera", "cell phone", "computer", "headphones", "keyboard", "laptop",
                    "megaphone", "microphone", "radio", "remote control", "stereo", "telephone", "television"],
    "vehicles": ["airplane", "ambulance", "bulldozer", "bus", "canoe", "cruise ship", "firetruck", "hot air balloon",
                 "motorbike", "parachute", "speedboat", "submarine", "tractor", "train", "truck", "van", "wheel"],
    "buildings and places": ["barn", "bridge", "castle", "church", "diving board", "fence", "fire hydrant", "garden",
                             "hospital", "jail", "lighthouse", "mailbox", "roller coaster", "see saw", "skyscraper",
                             "stairs", "stop sign", "streetlight", "swing set", "traffic light", "waterslide",
                             "windmill"],
    "nature and weather": ["beach", "bush", "campfire", "cloud", "feather", "grass", "house plant", "hurricane",
                           "leaf", "lightning", "moon", "mountain", "ocean", "pond", "rain", "rainbow", "river",
                           "snowflake", "snowman", "sun", "tornado"],
    "body parts": ["arm", "beard", "brain", "ear", "elbow", "eye", "finger", "foot", "hand", "knee", "leg",
                   "moustache", "mouth", "nose", "skull", "toe", "tooth"],
    "clothing and accessories": ["backpack", "belt", "bowtie", "bracelet", "crown", "eyeglasses", "flip flops",
                                 "helmet", "jacket", "lipstick", "necklace", "pants", "purse", "shorts", "sock",
                                 "sweater", "t-shirt", "underwear", "wristwatch"],
    "instruments": ["cello", "clarinet", "drums", "piano", "saxophone", "trombone", "trumpet", "violin"],
    "sports and toys": ["baseball", "baseball bat", "basketball", "boomerang", "dumbbell", "golf club",
                        "hockey puck", "hockey stick", "rollerskates", "skateboard", "snorkel", "soccer ball",
                        "teddy-bear", "tennis racquet"],
}
QUOTAS = {"animals": 18, "food": 11, "household": 10, "tools and stationery": 8, "electronics": 5, "vehicles": 8,
          "buildings and places": 8, "nature and weather": 9, "body parts": 7, "clothing and accessories": 7,
          "instruments": 4, "sports and toys": 3}  # 98 new concepts
FORCED = ["rain", "hurricane", "snowman"]  # named in the brief; counted inside their domain's quota

# Domains of the 37 existing concepts (core + forms), for the page's filters.
EXISTING_DOMAIN = {
    "chair": "household", "sailboat": "vehicles", "face": "body parts", "house": "buildings and places",
    "cat": "animals", "cup": "household", "tree": "nature and weather", "car": "vehicles",
    "key": "tools and stationery", "umbrella": "clothing and accessories", "ladder": "tools and stationery",
    "bench": "buildings and places", "carrot": "food", "bicycle": "vehicles", "candle": "household",
    "helicopter": "vehicles", "pineapple": "food", "snail": "animals", "saw": "tools and stationery",
    "cactus": "nature and weather", "harp": "instruments", "flower": "nature and weather", "bird": "animals",
    "fish": "animals", "dog": "animals", "shoe": "clothing and accessories", "hat": "clothing and accessories",
    "clock": "household", "floor lamp": "household", "book": "tools and stationery", "guitar": "instruments",
    "apple": "food", "scissors": "tools and stationery", "spoon": "household", "yoga": "people",
    "bed": "household", "table": "household",
}

# A-priori natural kinds (not made by people). Everything else is an artifact. People (yoga) count as
# natural. Fruit, vegetables, nuts and mushrooms are natural; prepared food (bread, cake, steak) is not.
NATURAL = {
    # core
    "cat", "tree", "face", "carrot", "pineapple", "snail", "cactus", "flower", "bird", "fish", "dog", "apple", "yoga",
    # animals, all natural
    *ELIGIBLE["animals"],
    # food
    "asparagus", "banana", "blackberry", "blueberry", "broccoli", "grapes", "mushroom", "onion", "peanut", "pear",
    "peas", "potato", "strawberry", "string bean", "watermelon",
    # nature and weather (campfire and house plant are made or kept by people)
    "beach", "bush", "cloud", "feather", "grass", "hurricane", "leaf", "lightning", "moon", "mountain", "ocean",
    "pond", "rain", "rainbow", "river", "snowflake", "sun", "tornado",
    # body parts, all natural
    *ELIGIBLE["body parts"],
}

# Prompt phrases: "a <word>" unless the word is a plural, a mass noun or a one-of-a-kind thing.
PLURAL = {"binoculars", "drums", "eyeglasses", "flip flops", "grapes", "headphones", "matches", "pants", "peas",
          "pliers", "rollerskates", "shorts", "stairs"}
MASS = {"asparagus", "bread", "broccoli", "grass", "ice cream", "lightning", "rain", "toothpaste", "underwear"}
THE = {"moon", "ocean", "sun"}
LABELS = {"teddy-bear": "teddy bear", "see saw": "seesaw", "rollerskates": "roller skates"}


@dataclass(frozen=True)
class AtlasConcept:
    key: str          # folder name: the Quick, Draw! category with spaces as underscores
    label: str        # what the page calls it
    quickdraw: str    # Quick, Draw! category name
    phrase: str       # noun phrase in the doodle prompt
    domain: str
    natural: bool     # a-priori natural kind (True) or artifact (False)
    origin: str       # "core" (35), "forms" (bed, table) or "new" (98)
    n_ai: int         # Muse Image pictures in the analysis (16 or 12)


def phrase_for(qd: str) -> str:
    word = LABELS.get(qd, qd)
    if qd in plato.PHRASES:
        return plato.PHRASES[qd]
    if qd in PLURAL or qd in MASS:
        return word
    if qd in THE:
        return f"the {word}"
    return ("an " if word[0] in "aeiou" else "a ") + word


def select_new(seed: int = SEED) -> list[tuple[str, str]]:
    """The 98 new concepts as (category, domain): the forced ones, then a seeded draw within each domain."""
    rng = np.random.default_rng(seed)
    out = []
    for domain, quota in QUOTAS.items():
        pool = sorted(ELIGIBLE[domain])
        forced = [w for w in FORCED if w in pool]
        rest = [w for w in pool if w not in forced]
        drawn = list(rng.choice(rest, quota - len(forced), replace=False))
        out += [(w, domain) for w in sorted(forced + [str(x) for x in drawn])]
    return out


def _concepts() -> list[AtlasConcept]:
    out = []
    for c in plato.CONCEPTS:
        out.append(AtlasConcept(c.key, c.label, c.quickdraw, c.phrase, EXISTING_DOMAIN[c.quickdraw],
                                c.quickdraw in NATURAL, "core", c.n_ai))
    for qd in FORMS_KEYS:
        out.append(AtlasConcept(qd, qd, qd, phrase_for(qd), EXISTING_DOMAIN[qd], False, "forms", 16))
    for qd, domain in select_new():
        out.append(AtlasConcept(qd.replace(" ", "_"), LABELS.get(qd, qd), qd, phrase_for(qd), domain,
                                qd in NATURAL, "new", N_NEW))
    return out


CONCEPTS = _concepts()
BY_KEY = {c.key: c for c in CONCEPTS}
NEW = [c for c in CONCEPTS if c.origin == "new"]
DOMAINS = list(QUOTAS) + ["people"]


def prompt_for(c: AtlasConcept) -> str:
    return plato.STYLES["doodle"].format(phrase=c.phrase)


def slug(key: str) -> str:
    """A file-safe name for the web pictures."""
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")


# ---------- where each concept's pictures and embeddings live ----------

def folders(c: AtlasConcept) -> dict[str, Path]:
    """Picture folders per source (ai_doodle, ai_sdxl_doodle, human) for one concept."""
    root = {"core": plato.PLATO_DIR, "forms": FORMS_DIR, "new": ATLAS_DIR}[c.origin]
    return {"ai_doodle": root / "ai" / "doodle" / c.key, "ai_sdxl_doodle": root / "ai" / "sdxl_doodle" / c.key,
            "human": root / "human" / c.key}


def embedding_path(c: AtlasConcept, source: str) -> Path:
    root = {"core": plato.PLATO_DIR, "forms": FORMS_DIR, "new": ATLAS_DIR}[c.origin]
    return root / "embeddings" / source / f"{c.key}.npz"


# ---------- statistics shared with the benchmark ----------

def spread_ratio(a: np.ndarray, h: np.ndarray, n: int | None = None, reps_ai: int = 2000, reps_human: int = 500,
                 subsets: int = 200, rng: np.random.Generator | None = None) -> dict:
    """A set's spread against the human reference, as in plato_analyze.concept_stats: the set's own spread
    with a bootstrap CI over its pictures; people's spread as the mean over random subsets of the same n
    (default: the set's size); the ratio's CI from independent bootstraps of both. Returns the bootstrap
    draws too (keys starting with "_")."""
    rng = rng or np.random.default_rng(SEED)
    n = n or len(a)
    da, dh = plato.cosine_distances(a), plato.cosine_distances(h)
    ai = plato.spread(da)
    with np.errstate(invalid="ignore"):  # a tiny set can resample one picture n times: no pair, no spread
        ai_boot = plato.bootstrap_spread(da, reps_ai, rng)
    ai_boot = np.where(np.isfinite(ai_boot), ai_boot, 0.0) if len(a) < 8 else ai_boot
    subs = plato.subsample_spread(dh, min(n, len(h)), subsets, rng)
    hum = float(subs.mean())
    h_boot = plato.bootstrap_spread(dh, reps_human, rng)
    ratio_boot = ai_boot[:reps_human] / h_boot
    return {"n": int(len(a)), "spread": ai, "spread_ci95": plato.ci(ai_boot), "human_spread": hum,
            "human_spread_ci95": plato.ci(h_boot), "human_spread_range95_for_n": plato.ci(subs),
            "ratio": ai / hum, "ratio_ci95": plato.ci(ratio_boot),
            "share_of_human_sets_as_uniform": float((subs <= ai).mean()),
            "_ratio_boot": ratio_boot, "_ai_boot": ai_boot}


def median_ci(boots: list[np.ndarray], reps: int = 5000, rng: np.random.Generator | None = None) -> list[float]:
    """95% CI of the median ratio over concepts, two-level: resample concepts with replacement, and for each
    drawn concept take one random draw from its own picture-level bootstrap."""
    rng = rng or np.random.default_rng(SEED)
    k = len(boots)
    out = np.empty(reps)
    for r in range(reps):
        idx = rng.integers(0, k, k)
        out[r] = np.median([boots[i][rng.integers(len(boots[i]))] for i in idx])
    return plato.ci(out)


def wilson_ci(k: int, n: int, z: float = 1.959964) -> list[float]:
    """Wilson score interval for a proportion k/n."""
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    w = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [float(c - w), float(c + w)]


# ---------- pictures: the pixel-average Form and a model-free pixel spread ----------

def ink_gray(path_or_img, side: int = 256) -> np.ndarray:
    """A picture ink-cropped exactly as for the embeddings (plato.ink_crop), as a float gray array."""
    from PIL import Image

    img = path_or_img if isinstance(path_or_img, Image.Image) else Image.open(path_or_img)
    return np.asarray(plato.ink_crop(img.convert("RGB"), side=side).convert("L"), dtype=np.float32)


def form_average(grays: list[np.ndarray]) -> np.ndarray:
    """The pixel average of ink-cropped pictures, stretched so its darkest pixel is black (as for the
    clocks in Plato's Forms). One picture repeated gives back that picture; varied ones give a cloud."""
    a = np.mean(grays, axis=0)
    lo = float(a.min())
    return np.clip((a - lo) / max(255.0 - lo, 1e-6) * 255.0, 0, 255).astype(np.uint8)


def ink_map(gray: np.ndarray, threshold: int = 200, sigma: float = 8.0) -> np.ndarray:
    """Binary ink (gray < threshold) blurred with a Gaussian of sigma px, so stroke width matters little."""
    from scipy.ndimage import gaussian_filter

    return gaussian_filter((gray < threshold).astype(np.float32), sigma)


def pixel_spread(grays: list[np.ndarray]) -> float:
    """Model-free spread: mean pairwise cosine distance between the pictures' blurred ink maps."""
    maps = np.stack([ink_map(g).ravel() for g in grays])
    maps = maps[np.linalg.norm(maps, axis=1) > 0]
    if len(maps) < 2:
        return float("nan")
    return plato.spread(plato.cosine_distances(maps))

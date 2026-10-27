"""Plato's Cratylus: do names fit things by nature? "bouba" and "kiki" for an AI that never heard a word.

People everywhere match "bouba" to a round shape and "kiki" to a spiky one (Ćwiek et al. 2022, 25
languages). A text-trained model has only ever seen spellings. Does Muse Image still draw a "kiki" spiky?

Two arms:
  drawing  Muse Image draws "a shape called '<word>'" for 12 made-up words (bouba, kiki, maluma, takete and
           a 2 x 2 grid of soft vs hard consonants by rounded vs unrounded vowels), 4 neutral control words,
           a no-name baseline, and spelling variants of bouba and kiki. Roundness of every drawing is
           measured three ways: solidity (area / convex-hull area), sharp-corner count, and position on a
           human round-to-spiky axis in DINOv2 space, built from Quick, Draw! circles and clouds vs. stars,
           zigzags and lightning bolts (CC BY 4.0).
  choice   code-drawn round and spiky shapes side by side; Muse Glimmer's probability of "left" vs "right"
           for "Which one is '<word>'?", with the two sides swapped to cancel position bias; Muse Spark's
           sampled answers to the same question.

Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageDraw

from metalesionlab import plato_shapes as ps

PROMPT = "A simple black outline drawing of a shape called '{word}'. One shape only, no text."
BASELINE_PROMPT = "A simple black outline drawing of a shape. One shape only, no text."
BASELINE = "(no name)"


@dataclass(frozen=True)
class Word:
    word: str
    group: str        # classic | grid | control | baseline | spelling
    consonants: str   # soft (b, m, l) | hard (k, t, p) | neutral | mixed
    vowels: str       # rounded (o, u) | unrounded (i, e) | neutral (a) | mixed
    sound: str        # the class a person would expect: round | spiky | neutral
    n: int = 12       # pictures (separate Muse Image calls of n = 4)
    of: str = ""      # for spelling variants: the word it spells


WORDS = [
    Word("bouba", "classic", "soft", "rounded", "round"),
    Word("kiki", "classic", "hard", "unrounded", "spiky"),
    Word("maluma", "classic", "soft", "mixed", "round"),
    Word("takete", "classic", "hard", "unrounded", "spiky"),
    # the grid: soft (b, m, l) or hard (k, t, p) consonants, rounded (o, u) or unrounded (i, e) vowels
    Word("bomu", "grid", "soft", "rounded", "round"),
    Word("lobu", "grid", "soft", "rounded", "round"),
    Word("bemi", "grid", "soft", "unrounded", "mixed"),
    Word("limi", "grid", "soft", "unrounded", "mixed"),
    Word("kotu", "grid", "hard", "rounded", "mixed"),
    Word("tupo", "grid", "hard", "rounded", "mixed"),
    Word("keti", "grid", "hard", "unrounded", "spiky"),
    Word("tepi", "grid", "hard", "unrounded", "spiky"),
    # neutral controls: consonants from neither class, the open vowel a
    Word("fana", "control", "neutral", "neutral", "neutral"),
    Word("hasa", "control", "neutral", "neutral", "neutral"),
    Word("nafa", "control", "neutral", "neutral", "neutral"),
    Word("safa", "control", "neutral", "neutral", "neutral"),
    Word(BASELINE, "baseline", "neutral", "neutral", "neutral"),
    # sound vs. spelling (exploratory): the letters without the word's sound, and the sound spelled out
    Word("b-o-u-b-a", "spelling", "soft", "rounded", "round", 8, "bouba"),
    Word("k-i-k-i", "spelling", "hard", "unrounded", "spiky", 8, "kiki"),
    Word("bouba (pronounced BOO-bah)", "spelling", "soft", "rounded", "round", 8, "bouba"),
    Word("kiki (pronounced KEE-kee)", "spelling", "hard", "unrounded", "spiky", 8, "kiki"),
]
BY_WORD = {w.word: w for w in WORDS}
ROUND_CLASS = ("bouba", "maluma", "bomu", "lobu")   # soft consonants and rounded vowels
SPIKY_CLASS = ("kiki", "takete", "keti", "tepi")    # hard consonants and unrounded vowels
GRID = [w for w in WORDS if w.group == "grid"]
# choice arm only (free, Glimmer): more spellings of the two classic words
CHOICE_EXTRA = ["b o u b a", "k i k i", "BOUBA", "KIKI"]

# Human round-to-spiky axis: Quick, Draw! categories
ROUND_CATEGORIES = ("circle", "cloud")
SPIKY_CATEGORIES = ("star", "zigzag", "lightning")


def prompt_for(word: str) -> str:
    return BASELINE_PROMPT if word == BASELINE else PROMPT.format(word=word)


def slug(word: str) -> str:
    import re

    return "no_name" if word == BASELINE else re.sub(r"[^a-z0-9]+", "_", word.lower()).strip("_")


# --- code-drawn shapes for the choice arm -----------------------------------------------------

def round_shape(seed: int, side: int = 384) -> np.ndarray:
    """A smooth blob with a few rounded lobes (in the spirit of the bouba shapes of Bremner et al. 2013):
    r(theta) = R (1 + sum of low-frequency cosines), all lobes soft."""
    rng = np.random.default_rng(1000 + seed)
    theta = np.linspace(0, 2 * math.pi, 720, endpoint=False)
    k = int(rng.integers(4, 7))
    r = 1 + 0.16 * np.cos(k * theta + rng.uniform(0, 2 * math.pi))
    for f in (2, 3):
        r += rng.uniform(0.02, 0.06) * np.cos(f * theta + rng.uniform(0, 2 * math.pi))
    return _polygon_mask(theta, r, side)


def spiky_shape(seed: int, side: int = 384) -> np.ndarray:
    """An irregular star with sharp spikes of unequal length (in the spirit of the kiki shapes of
    Bremner et al. 2013)."""
    rng = np.random.default_rng(2000 + seed)
    k = int(rng.integers(7, 11))
    base = np.linspace(0, 2 * math.pi, 2 * k, endpoint=False) + rng.uniform(0, 2 * math.pi)
    base += rng.uniform(-0.12, 0.12, 2 * k) * (math.pi / k)
    r = np.where(np.arange(2 * k) % 2 == 0, rng.uniform(0.85, 1.15, 2 * k), rng.uniform(0.38, 0.5, 2 * k))
    return _polygon_mask(base, r, side)


def _polygon_mask(theta: np.ndarray, r: np.ndarray, side: int) -> np.ndarray:
    x, y = r * np.cos(theta), r * np.sin(theta)
    scale = 0.44 * side / max(np.abs(x).max(), np.abs(y).max())
    pts = [(side / 2 + scale * a, side / 2 + scale * b) for a, b in zip(x, y)]
    img = Image.new("L", (side, side), 0)
    ImageDraw.Draw(img).polygon(pts, fill=255)
    return np.asarray(img) > 127


def pair_image(left: np.ndarray, right: np.ndarray, gap: int = 0) -> Image.Image:
    """Two black shapes on white, side by side."""
    h, w = left.shape
    canvas = np.full((h, 2 * w + gap), 255, np.uint8)
    canvas[:, :w][left] = 0
    canvas[:, w + gap:][right] = 0
    return Image.fromarray(canvas).convert("RGB")


def choice_prompt(word: str) -> str:
    return (f"There are two shapes in this picture, one on the left and one on the right. "
            f"Which one is \"{word}\"? Answer with one word: left or right.")


TEXT_SHAPES = {"round": "a rounded blob with smooth, curvy lobes", "spiky": "a spiky star with sharp, jagged points"}


def text_choice_prompt(word: str, round_first: bool) -> str:
    """The choice without a picture: two described shapes labeled A and B."""
    a, b = ("round", "spiky") if round_first else ("spiky", "round")
    return (f"Imagine two shapes. A is {TEXT_SHAPES[a]}. B is {TEXT_SHAPES[b]}. Which one is called \"{word}\"? "
            f"Answer with one letter: A or B.")


def parse_side(text: str) -> str | None:
    """'left' or 'right' from a free-text answer (first one mentioned), or None."""
    import re

    m = re.search(r"\b(left|right)\b", (text or "").lower())
    return m.group(1) if m else None


# --- roundness measures of a drawing -----------------------------------------------------------

def largest_component(mask: np.ndarray) -> np.ndarray:
    from scipy import ndimage as ndi

    lab, n = ndi.label(mask)
    if n <= 1:
        return mask
    sizes = ndi.sum(mask, lab, index=np.arange(1, n + 1))
    return lab == (1 + int(np.argmax(sizes)))


@dataclass
class Roundness:
    solidity: float     # area / convex-hull area of the largest filled shape (1 = convex)
    corners: int        # sharp convex corners on its outline
    n_shapes: int       # filled shapes covering at least 5% of the largest one's area
    fill_ratio: float   # filled area / ink area (about 1 means the outline didn't close)
    closing_radius: float


def roundness(img: Image.Image) -> tuple[Roundness, np.ndarray]:
    """Fill the drawing (plato_shapes.silhouette_mask), keep the largest shape and measure it."""
    from scipy import ndimage as ndi

    ink = ps.ink_mask(ps.to_gray(img, 512), min_fraction=1e-4)
    sil = ps.silhouette_mask(ink, radii=(0, 1, 2, 3, 5, 8))
    big = largest_component(sil.mask)
    lab, n = ndi.label(sil.mask)
    sizes = ndi.sum(sil.mask, lab, index=np.arange(1, n + 1)) if n else np.array([0])
    n_shapes = int((sizes >= 0.05 * sizes.max()).sum()) if n else 0
    return Roundness(ps.solidity(big), ps.corner_count(big), n_shapes, sil.fill_ratio, sil.radius), big


# --- statistics ----------------------------------------------------------------------------

def auc(x: np.ndarray, y: np.ndarray) -> float:
    """P(a random y > a random x) + 0.5 P(tie): the probability of superiority of y over x."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    diff = y[:, None] - x[None, :]
    return float(((diff > 0).sum() + 0.5 * (diff == 0).sum()) / diff.size)


def cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    sp = math.sqrt(((len(x) - 1) * x.var(ddof=1) + (len(y) - 1) * y.var(ddof=1)) / (len(x) + len(y) - 2))
    return float((y.mean() - x.mean()) / sp) if sp > 0 else float("nan")


def bootstrap_contrast(x, y, reps: int = 4000, seed: int = 0) -> dict:
    """y - x: mean difference, Cohen's d and AUC, with percentile bootstrap CIs (resampling pictures
    within each group)."""
    rng = np.random.default_rng(seed)
    x, y = np.asarray(x, float), np.asarray(y, float)
    diffs, ds, aucs = [], [], []
    for _ in range(reps):
        bx, by = x[rng.integers(0, len(x), len(x))], y[rng.integers(0, len(y), len(y))]
        diffs.append(by.mean() - bx.mean())
        ds.append(cohens_d(bx, by))
        aucs.append(auc(bx, by))

    def ci(a):
        a = np.asarray(a, float)
        a = a[np.isfinite(a)]
        return [float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))]

    return {"diff": float(y.mean() - x.mean()), "diff_ci": ci(diffs), "d": cohens_d(x, y), "d_ci": ci(ds),
            "auc": auc(x, y), "auc_ci": ci(aucs), "n": [len(x), len(y)]}


def hierarchical_contrast(groups_x: list, groups_y: list, reps: int = 4000, seed: int = 0) -> dict:
    """y-class minus x-class mean, where each class is several words with several pictures each:
    resample words within class, then pictures within word (two-level bootstrap)."""
    rng = np.random.default_rng(seed)
    gx = [np.asarray(g, float) for g in groups_x]
    gy = [np.asarray(g, float) for g in groups_y]

    def mean_of(gs):
        return float(np.mean([g.mean() for g in gs]))

    boots = []
    for _ in range(reps):
        def draw(gs):
            pick = [gs[i] for i in rng.integers(0, len(gs), len(gs))]
            return float(np.mean([g[rng.integers(0, len(g), len(g))].mean() for g in pick]))
        boots.append(draw(gy) - draw(gx))
    boots = np.asarray(boots)
    return {"diff": mean_of(gy) - mean_of(gx), "diff_ci": [float(np.quantile(boots, 0.025)),
                                                          float(np.quantile(boots, 0.975))],
            "n_words": [len(gx), len(gy)]}

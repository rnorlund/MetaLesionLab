"""The invisible Forms: ask the painter to draw what no one has ever seen.

Plato's highest Forms were not chairs but Beauty, Justice and the Good, and in Republic X it is God who
makes the one true bed. Plato's Chair casts the image model as the painter. Here we ask Muse Image to
doodle 11 abstract ideas, 16 times each, with exactly the prompt and settings of the concrete things'
first run (plato.STYLES["doodle"], 4 calls of n = 4, 512 px), and ask two questions:

1. Does it reduce each idea to one stock emblem (a heart for love, scales for justice, a clock for time)?
   Muse Glimmer 30B names the emblem in each doodle, as multiple choice (the kinds labeling's method).
2. How spread out are its drawings of ideas, next to its drawings of everyday things (same pipeline:
   ink crop, DINOv2-base CLS, mean pairwise cosine distance)?

Pre-registered in docs/plato_ideas_plan.md. Data lives outside the repository in $PLATO_IDEAS_DIR
(default PlatosChair/ideas, next to core/ and atlas/). There are no people's drawings of these ideas in
Quick, Draw!, so every comparison here is between the AI's ideas and the AI's things.
"""
from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from metalesionlab import plato

IDEAS_DIR = Path(os.environ.get("PLATO_IDEAS_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/ideas"))
N_AI = 16          # doodles per idea, as for the tier-1 concrete things
BATCH = 4          # pictures per Muse Image call, as in the first run (plato_generate.py --batch 4)
MAX_ATTEMPTS = 3   # a refused call is tried at most 3 times in all; every refusal is recorded
# Spend: the task's own cap, counted at the price we were told (about $0.026 a picture). The shared ledger
# books what MetaAPI books ($0.01 a picture); both are reported.
IMAGE_USD = 0.026
BUDGET_USD = 5.0
SHARED_STOP = 70.0  # no new paid call once the shared ledger reaches this
SEED = 20261028

SOMETHING_ELSE = "something else (none of the options above)"
CANT_TELL = "can't tell, or no clear symbol or figure"


@dataclass(frozen=True)
class Idea:
    key: str            # folder name
    label: str          # what the page calls it ("God", "the Good")
    phrase: str         # the noun phrase in the Muse Image prompt (bare: no article)
    group: str          # "god", "plato" (Plato's own highest Forms) or "life"
    predicted: str      # the emblem we expected to dominate, named before the main run
    emblems: tuple      # ((short name, option text), ...): the labeler's choices besides SOMETHING_ELSE, CANT_TELL


# The order is the drawing order (if spending stops early, the central ideas exist). Options were fixed in
# the plan before the main run. No option names a particular religion's figures; one option per idea is
# the stock emblem we predicted.
IDEAS = [
    Idea("god", "God", "God", "god", "bearded man", (
        ("bearded man", "a man with a beard"),
        ("human figure", "a human figure without a beard"),
        ("light", "rays of light, a sun or a glow, with no figure"),
        ("clouds", "clouds or sky, with no figure"),
        ("eye", "an eye"),
        ("hands", "a hand or hands"),
        ("religious symbol", "a symbol of one particular religion"),
    )),
    Idea("love", "love", "love", "life", "heart", (
        ("heart", "a heart, or several hearts"),
        ("couple", "two people hugging, kissing or holding hands"),
        ("hands", "hands holding each other"),
        ("flower", "a flower or a rose"),
        ("arrow", "an arrow or a winged child"),
    )),
    Idea("death", "death", "death", "life", "skull", (
        ("skull", "a skull or a skeleton"),
        ("reaper", "a hooded figure with a scythe"),
        ("grave", "a gravestone, a grave or a coffin"),
        ("wilted plant", "a wilted flower or a dead tree"),
        ("candle", "a candle or a flame going out"),
        ("hourglass", "an hourglass"),
    )),
    Idea("time", "time", "time", "life", "clock", (
        ("clock", "a clock or a watch"),
        ("hourglass", "an hourglass"),
        ("calendar", "a calendar"),
        ("sun and moon", "a sun and a moon, or day and night"),
        ("ageing", "a person or thing growing old"),
        ("spiral", "a spiral or a winding path"),
    )),
    Idea("justice", "justice", "justice", "plato", "scales", (
        ("scales", "a pair of scales (a balance), with no figure"),
        ("figure with scales", "a woman holding scales or a sword (often blindfolded)"),
        ("gavel", "a judge's gavel"),
        ("sword", "a sword"),
        ("courthouse", "a courthouse or columns"),
        ("people", "people or hands"),
    )),
    Idea("beauty", "beauty", "beauty", "plato", "flower", (
        ("flower", "a flower or a rose"),
        ("woman", "a woman's face or figure"),
        ("heart", "a heart"),
        ("butterfly", "a butterfly"),
        ("eye or lips", "an eye or lips"),
        ("mirror", "a mirror"),
        ("landscape", "a landscape or a sunset"),
    )),
    Idea("the_good", "the Good", "the Good", "plato", "sun", (
        ("sun", "a sun, a light or rays"),
        ("heart", "a heart"),
        ("smiling face", "a smiling face"),
        ("helping hands", "hands or people helping each other"),
        ("thumbs-up", "a thumbs-up or a check mark"),
        ("halo or wings", "a halo or wings"),
        ("plant", "a tree, a plant or a flower"),
    )),
    Idea("the_soul", "the soul", "the soul", "life", "ghostly figure", (
        ("ghostly figure", "a ghostly or see-through figure, or a figure rising from a body"),
        ("flame", "a flame or a candle"),
        ("glow", "a glowing light, an orb or a spark"),
        ("heart", "a heart"),
        ("wings or halo", "a figure with wings or a halo"),
        ("bird or butterfly", "a bird or a butterfly"),
        ("swirl", "a spiral or a swirl"),
    )),
    Idea("freedom", "freedom", "freedom", "life", "bird", (
        ("bird", "a flying bird or birds, with no cage"),
        ("bird and cage", "a bird leaving a cage, or an open cage"),
        ("broken chains", "broken chains or shackles"),
        ("open arms", "a person with raised or outstretched arms"),
        ("flag", "a flag"),
        ("torch statue", "a statue holding up a torch"),
    )),
    Idea("happiness", "happiness", "happiness", "life", "smiling face", (
        ("smiling face", "a smiling face (a smiley)"),
        ("joyful person", "a person jumping, dancing or with raised arms"),
        ("sun", "a sun"),
        ("heart", "a heart"),
        ("balloons", "balloons"),
        ("flowers", "flowers"),
    )),
    Idea("truth", "truth", "truth", "life", "eye", (
        ("eye", "an eye"),
        ("light", "a light bulb, a candle, a lamp or a sun"),
        ("scales", "a pair of scales"),
        ("mirror", "a mirror"),
        ("book", "an open book"),
        ("key", "a key"),
        ("magnifying glass", "a magnifying glass"),
        ("face", "a face or a person"),
    )),
]
BY_KEY = {i.key: i for i in IDEAS}
GROUPS = {"god": "God, the maker of the one true bed", "plato": "Plato's own highest Forms",
          "life": "Ideas everyone lives with"}


# God's human-like share (exploratory, set beside the Lausanne "Drawings of gods" children): a human figure,
# bearded or not, or a hand. Light, clouds, an eye and religious symbols count as not human-like.
HUMAN_LIKE = {"god": ("bearded man", "human figure", "hands")}


def prompt_for(idea: Idea) -> str:
    """The concrete things' doodle prompt, word for word, with the idea's phrase."""
    return plato.STYLES["doodle"].format(phrase=idea.phrase)


def folder(idea: Idea | str, root: Path | None = None) -> Path:
    key = idea if isinstance(idea, str) else idea.key
    return (root or IDEAS_DIR) / "ai" / "doodle" / key


# ---------- the emblem labels (Muse Glimmer, multiple choice) ----------

def options(idea: Idea, reverse: bool = False) -> list[str]:
    """The labeler's choices: the idea's emblems (reversed for the second pass), then 'something else',
    then 'can't tell'. The last two always stay last."""
    texts = [t for _, t in idea.emblems]
    return (texts[::-1] if reverse else texts) + [SOMETHING_ELSE, CANT_TELL]


def short_names(idea: Idea) -> list[str]:
    """Short names in forward option order: the emblems, then 'something else', 'can't tell'."""
    return [s for s, _ in idea.emblems] + ["something else", "can't tell"]


def labeling_prompt(idea: Idea, opts: list[str]) -> str:
    lines = "\n".join(f"{plato.LETTERS[i]}. {o}" for i, o in enumerate(opts))
    return (f"Someone was asked to draw {idea.phrase}. What is the main symbol or figure this drawing uses to "
            f"show {idea.phrase}? Pick the one option that fits best. If the drawing's main symbol or figure "
            f"is not among the options, pick \"{opts[-2]}\".\n{lines}\nAnswer with the letter only.")


def naming_prompt(idea: Idea) -> str:
    """The free-text pass: what is in the picture, in a few words (used to name 'something else')."""
    return (f"Someone was asked to draw {idea.phrase}. In at most five words, what is the main symbol or figure "
            f"in this drawing? Answer with the words only.")


# How the page names an emblem in a sentence ("Yours is closest to Muse's #7: a heart").
_DISPLAY = {"reaper": "a hooded figure with a scythe", "figure with scales": "a blindfolded figure with scales",
            "scales": "a pair of scales", "woman": "a woman's face", "light": "light", "clouds": "clouds",
            "bird": "a flying bird", "bird and cage": "a bird leaving a cage", "ageing": "growing old",
            "religious symbol": "a religious symbol", "torch statue": "a statue with a torch",
            "wings or halo": "a figure with wings or a halo", "eye or lips": "an eye or lips",
            "book": "an open book", "couple": "a couple"}
_NO_ARTICLE = {"hands", "people", "broken chains", "open arms", "balloons", "flowers", "helping hands"}


def display(short: str, name: str | None = None) -> str:
    """An emblem's short name as a phrase with its article. 'something else' and 'can't tell' become Glimmer's
    own words for the picture, in quotation marks, when it gave any."""
    if short in ("something else", "can't tell"):
        words = (name or "").strip().strip(".").lower()
        return f"“{words}”" if words else "no clear symbol"
    if short in _DISPLAY:
        return _DISPLAY[short]
    if short in _NO_ARTICLE:
        return short
    return ("an " if short[0] in "aeiou" else "a ") + short


def reverse_index(n_emblems: int) -> list[int]:
    """Position j of the reversed options holds forward option back[j] (the last two stay put)."""
    return list(range(n_emblems - 1, -1, -1)) + [n_emblems, n_emblems + 1]


# ---------- statistics ----------

def concentration(labels: list[str], emblems: list[str]) -> dict:
    """Emblem concentration: the share of ALL doodles (the denominator includes 'something else' and
    'can't tell') that show the most common listed emblem. Ties: the first in sorted order.
    Also: how many listed emblems appear, and the Gini-Simpson diversity over listed emblems only."""
    n = len(labels)
    counts = Counter(x for x in labels if x in emblems)
    if not n:
        return {"n": 0, "top": None, "top_n": 0, "share": float("nan"), "distinct": 0}
    if not counts:
        return {"n": n, "top": None, "top_n": 0, "share": 0.0, "distinct": 0,
                "share_other": float(sum(x not in emblems for x in labels) / n)}
    top, top_n = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return {"n": n, "top": top, "top_n": int(top_n), "share": top_n / n, "distinct": len(counts),
            "share_other": float(sum(x not in emblems for x in labels) / n),
            "counts": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))}


def bootstrap_concentration(labels: list[str], emblems: list[str], reps: int = 2000,
                            rng: np.random.Generator | None = None) -> np.ndarray:
    """The top share of resampled doodles (with replacement). A resample can crown a different emblem."""
    rng = rng or np.random.default_rng(SEED)
    lab = np.array(labels, dtype=object)
    n = len(lab)
    out = np.empty(reps)
    for b in range(reps):
        out[b] = concentration(list(lab[rng.integers(0, n, n)]), emblems)["share"]
    return out


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Cohen's kappa for two raters' labels of the same items."""
    a, b = list(a), list(b)
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return float((po - pe) / (1 - pe)) if pe < 1 else 1.0


def median_diff_ci(a_boots: list[np.ndarray], b_boots: list[np.ndarray], reps: int = 5000,
                   rng: np.random.Generator | None = None) -> tuple[np.ndarray, list[float]]:
    """Two-level bootstrap of median(a) - median(b): resample each group's items with replacement and
    take one draw from each drawn item's own picture-level bootstrap (as plato_atlas.median_ci)."""
    rng = rng or np.random.default_rng(SEED)
    out = np.empty(reps)
    ka, kb = len(a_boots), len(b_boots)
    for r in range(reps):
        ia, ib = rng.integers(0, ka, ka), rng.integers(0, kb, kb)
        ma = np.median([a_boots[i][rng.integers(len(a_boots[i]))] for i in ia])
        mb = np.median([b_boots[i][rng.integers(len(b_boots[i]))] for i in ib])
        out[r] = ma - mb
    return out, plato.ci(out)


def perm_p_median(a: np.ndarray, b: np.ndarray, reps: int = 10000, rng: np.random.Generator | None = None,
                  greater: bool = True) -> float:
    """One-sided permutation p for median(a) - median(b) > 0 (or < 0 with greater=False)."""
    rng = rng or np.random.default_rng(SEED)
    a, b = np.asarray(a, float), np.asarray(b, float)
    obs = np.median(a) - np.median(b)
    pool = np.concatenate([a, b])
    k = len(a)
    hits = 0
    for _ in range(reps):
        p = rng.permutation(pool)
        d = np.median(p[:k]) - np.median(p[k:])
        hits += d >= obs - 1e-12 if greater else d <= obs + 1e-12
    return float((hits + 1) / (reps + 1))

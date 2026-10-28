"""Plato's Telephone: pass a picture along a chain of AI copies. What survives?

Serial reproduction (Bartlett 1932) with two Meta models taking turns. Muse Spark looks at the current
picture and describes it in a sentence or two; Muse Image draws that description as a quick doodle; Spark
describes the new doodle, and so on for 10 generations. Each chain starts from one of Muse Image's own
named-kind doodles (a rocking chair, a throne, a beanbag ...) from "Can you prompt it out of the Platonic
chair?", plus two non-chair controls (a top hat and a cuckoo clock). Three independent chains per start.

The questions: does every chain drift toward Muse's default chair (the "Form"), do chains that start far
apart end up alike, and which words of the description are lost first? The plan, with predictions, is
docs/plato_telephone_plan.md; results are in docs/plato_telephone.md.

This module holds the design constants and the pure functions (text cleanup, word tracking, cluster
bootstrap weights, pair means); scripts/plato_telephone_{run,analyze,figures}.py do the work. Data live
outside the repository, in $PLATO_TELEPHONE_DIR (default PlatosChair/telephone/).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from metalesionlab.plato import PLATO_DIR, STYLES

TELEPHONE_DIR = Path(os.environ.get("PLATO_TELEPHONE_DIR",
                                    "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/telephone"))
SEED_DIR = PLATO_DIR / "ai" / "doodle_listed"   # gen 0: the named-kind doodles (p<i>.png = kinds.json[i])

# ---------- the protocol (fixed before the run; see docs/plato_telephone_plan.md) ----------
DESCRIBE_PROMPT = "Describe this drawing so someone could redraw it. One or two sentences. Don't name an artist."
REASONING_EFFORT = "minimal"   # Muse Spark, every description and every kind label
GENERATIONS = 10               # pictures g01 ... g10 after the seed g00
CHAINS = 3                     # independent chains per seed
SPARK_SIDE = 512               # pictures are stored and shown to Spark at most 512 px on the long side
LABEL_SIDE = 448               # kind labels: ink-cropped square, as in plato_kinds_label.py
MAX_PHRASE_CHARS = 600         # a description longer than this is cut at a word boundary
BUDGET_USD = 4.00              # this experiment's own spend cap
SHARED_STOP = 70.00            # stop if the shared ledger (meta_api.spent()) passes this
BOOT_SEED = 20261028


@dataclass(frozen=True)
class Seed:
    key: str          # folder name under chains/
    label: str        # what the page calls it
    concept: str      # Plato's Chair concept key: chair, hat or clock (its default doodles are the prototype)
    file: str         # the gen-0 picture in ai/doodle_listed/<concept>/
    kind: str         # the kinds.json entry the picture was drawn from (the labeler's right answer)
    kind_word: str    # regex (case-insensitive) for the kind's name in a description
    control: bool = False


SEEDS = [
    Seed("rocking_chair", "rocking chair", "chair", "p0.png", "a rocking chair", r"rock(?:ing|er)"),
    Seed("throne", "throne", "chair", "p13.png", "a throne", r"throne"),
    Seed("beanbag", "beanbag", "chair", "p5.png", "a beanbag chair", r"bean[\s-]?bag"),
    Seed("wheelchair", "wheelchair", "chair", "p7.png", "a wheelchair", r"wheel[\s-]?chair"),
    Seed("office_chair", "office chair", "chair", "p3.png", "an office chair", r"office"),
    Seed("folding_chair", "folding chair", "chair", "p2.png", "a folding chair", r"fold"),
    Seed("high_chair", "high chair", "chair", "p6.png", "a highchair", r"high[\s-]?chair"),
    Seed("adirondack", "Adirondack chair", "chair", "p14.png", "an Adirondack chair", r"adirondack"),
    Seed("top_hat", "top hat", "hat", "p0.png", "a top hat", r"top[\s-]?hat", control=True),
    Seed("cuckoo_clock", "cuckoo clock", "clock", "p1.png", "a cuckoo clock", r"cuckoo", control=True),
]
BY_KEY = {s.key: s for s in SEEDS}
CHAIR_SEEDS = [s for s in SEEDS if not s.control]
# The category's own word. "chair" as a substring, so armchair, wheelchair and highchair count.
CATEGORY_WORD = {"chair": r"chair", "hat": r"\bhats?\b", "clock": r"clock"}


def chain_dir(seed: Seed | str, chain: int, root: Path | None = None) -> Path:
    key = seed.key if isinstance(seed, Seed) else seed
    return (root or TELEPHONE_DIR) / "chains" / key / f"c{chain}"


def pic_name(gen: int) -> str:
    return f"g{gen:02d}.png"


# ---------- text ----------

_QUOTES = "\"'“”‘’`"


def phrase(description: str, max_chars: int = MAX_PHRASE_CHARS) -> str:
    """A description as the {phrase} of the doodle prompt: whitespace collapsed, surrounding quotes and a
    trailing period dropped, a leading article ("A", "An", "The") lower-cased so it reads as a noun phrase,
    and cut at a word boundary after max_chars. Nothing else is changed."""
    s = re.sub(r"\s+", " ", description or "").strip().strip(_QUOTES).strip()
    if len(s) > max_chars:
        s = s[:max_chars].rsplit(" ", 1)[0]
    s = s.rstrip(" .;,:").strip()
    m = re.match(r"(A|An|The)\b", s)
    if m:
        s = m.group(1).lower() + s[len(m.group(1)):]
    return s


def image_prompt(description: str) -> str:
    """Muse Image's prompt: the core doodle template with the description as the phrase."""
    return STYLES["doodle"].format(phrase=phrase(description))


def has_word(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text or "", flags=re.I))


def presence(texts: list[str], pattern: str) -> list[bool]:
    return [has_word(t, pattern) for t in texts]


def first_loss(flags: list[bool]) -> int:
    """Index of the first description without the word; len(flags) if it is never lost (censored)."""
    for i, f in enumerate(flags):
        if not f:
            return i
    return len(flags)


STOPWORDS = set("""a an the and or but of with on in at to from for by as is are be been being it its this that these
those there their them they he she his her which who whom what where when while into onto over under above below
than then so such very also just only both each either neither any some all no not one two three four five six seven
eight nine ten few more most other another same own can could would should will may might must has have had having
do does did doing drawing drawn draw sketch sketched doodle simple simply quick like looks look looking shown shows
show depicts depicting depicted features featuring appears appear image picture line lines style black white marker
ink outline outlines outlined using use made make makes slightly rough roughly loose loosely hand side""".split())


def content_words(text: str) -> set[str]:
    """Lower-case words of three or more letters, minus stop words and drawing-talk words; a plural 's' is
    dropped ("legs" -> "leg") so singular and plural count as one word."""
    out = set()
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        if len(w) < 3 or w in STOPWORDS:
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
            w = w[:-1]
        if w not in STOPWORDS:
            out.add(w)
    return out


def word_runs(texts: list[str]) -> dict[str, int]:
    """For every content word of the first text: how many texts in a row, from the first, contain it."""
    sets = [content_words(t) for t in texts]
    runs = {}
    for w in sorted(sets[0]) if sets else []:
        n = 0
        while n < len(sets) and w in sets[n]:
            n += 1
        runs[w] = n
    return runs


def gained_words(texts: list[str]) -> set[str]:
    """Content words of the last text that the first text did not have."""
    return content_words(texts[-1]) - content_words(texts[0]) if texts else set()


# ---------- statistics ----------

def cluster_weights(n_seeds: int, n_chains: int, rng: np.random.Generator) -> np.ndarray:
    """One two-level bootstrap draw: seeds with replacement, then chains with replacement within each drawn
    seed. Returns weights (n_seeds, n_chains): how often each chain was drawn in all."""
    w = np.zeros((n_seeds, n_chains))
    for s in rng.integers(0, n_seeds, n_seeds):
        w[s] += np.bincount(rng.integers(0, n_chains, n_chains), minlength=n_chains)
    return w


def weighted_mean(x: np.ndarray, w: np.ndarray) -> float:
    """Mean of per-chain values x (n_seeds, n_chains) under weights w, ignoring NaN (a missing generation)."""
    ok = ~np.isnan(x)
    tot = (w * ok).sum()
    return float((np.where(ok, x, 0) * w).sum() / tot) if tot else float("nan")


def pair_mean(d: np.ndarray, w: np.ndarray, same_seed: bool) -> float:
    """Mean distance between chains' pictures at one generation.

    d: (n_seeds, n_chains, n_seeds, n_chains) distances; w: chain weights (n_seeds, n_chains), all ones
    for the point estimate. same_seed=False: pairs from different seeds (between-seed spread, how far apart
    the starts still are). same_seed=True: pairs of different chains from the same seed (within-seed
    spread, how far one start's chains have wandered from each other). A chain is never paired with itself,
    and NaN distances (missing pictures) are skipped."""
    ns, nc = w.shape
    ww = np.einsum("ab,cd->abcd", w, w)
    seed_same = np.eye(ns, dtype=bool)[:, None, :, None]
    chain_same = np.eye(nc, dtype=bool)[None, :, None, :]
    mask = (seed_same & ~chain_same) if same_seed else ~np.broadcast_to(seed_same, ww.shape)
    mask = mask & ~np.isnan(d)
    tot = (ww * mask).sum()
    return float((np.where(mask, d, 0) * ww).sum() / tot) if tot else float("nan")


def gap_closed(start: float, end: float, floor: float) -> float:
    """Share of the way from the start to the floor that has been travelled (1 = reached the floor)."""
    return (start - end) / (start - floor) if start != floor else float("nan")

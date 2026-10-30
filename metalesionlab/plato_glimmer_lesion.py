"""Damage Meta's open AI: what does it forget first? (docs/plato_glimmer_lesion_plan.md)

We switch off a random share of Muse Glimmer 30B's artificial neurons (reversible hooks, metalesionlab/lesions.py;
weights are never edited) and ask it, at each step of damage, to (1) draw a chair, a clock showing 10 past 11 and
God as SVG code, and (2) describe each in one sentence. Does it lose the word before the picture, or the picture
before the word? And is that different when the damage is in its early or its late layers?

This module holds the pure parts: the requests, the damage types and their dose ladders, the nested random choice
of neurons and heads, the description rubric (names the thing, a fixed list of parts and properties, fluency), the
retention statistics and the verdict rule, and the public file's schema. GPU work is
scripts/plato_glimmer_lesion_run.py; the analysis is scripts/plato_glimmer_lesion_analyze.py.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from metalesionlab.plato_scale import PROMPT as CHAIR_PROMPT

OUT_DIR = Path(os.environ.get("PLATO_GLIMMER_LESION_DIR",
                              "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/glimmer_lesion"))

# ---------- the requests ----------

STYLE = "black strokes only on a white background, 256 by 256 pixels"


@dataclass(frozen=True)
class Thing:
    key: str
    label: str          # what the page calls it
    draw: str           # the drawing request (SVG)
    describe: str       # the one-sentence request
    reader_label: str   # SigLIP 2's label for "read as this thing"


THINGS = [
    # word for word the scale experiment's request (docs/plato_scale.md), so intact replicates its Glimmer row
    Thing("chair", "a chair", CHAIR_PROMPT, "Describe a chair in one sentence.", "chair"),
    # the clinical clock-drawing instruction ("put in all the numbers and set the hands to 10 past 11"); "no text"
    # is dropped because the numbers are text
    Thing("clock", "a clock", "Draw a simple clock as an SVG drawing: put in all the numbers and set the hands to "
          "10 past 11. Black strokes only on a white background, 256 by 256 pixels, no colour fill. "
          "Output only the SVG code.", "Describe a clock in one sentence.", "clock"),
    Thing("god", "God", "Draw God as a simple SVG drawing: black strokes only on a white background, 256 by 256 "
          "pixels, no text, no colour fill. Output only the SVG code.", "Describe God in one sentence.", "God"),
]
BY_KEY = {t.key: t for t in THINGS}

N = 12                    # samples per thing, task and condition
TEMP = 1.0                # the scale experiment's primary temperature; pure sampling (top-p 1, no top-k)
MAX_SVG_TOKENS = 2048     # as in the scale experiment; generation also stops at the first </svg>
MAX_DESC_TOKENS = 128
SVG_SEED = 20261128       # the same torch seed in every condition (the scale experiment's seed at temperature 1)
DESC_SEED = 20261129
UNIT_SEED = 0             # which neurons and heads: one fixed random order per layer, shared by every condition

# ---------- damage ----------

N_LAYERS, N_NEURONS, N_HEADS = 52, 19968, 32
EARLY = list(range(0, 17))     # the first third of the 52 layers
LATE = list(range(35, 52))     # the last third
ALL = list(range(N_LAYERS))


@dataclass(frozen=True)
class DamageType:
    key: str
    label: str      # plain words, for the page
    site: str       # "mlp" (neurons) or "heads"
    layers: tuple
    doses: tuple    # shares switched off within each layer of the band, lightest first (set from the pilot)


# Dose ladders: fixed from the pilot (docs/plato_glimmer_lesion_plan.md, "Pilot"), before the main run.
DAMAGE = [
    DamageType("all", "neurons switched off in every layer", "mlp", tuple(ALL), (0.05, 0.10, 0.15, 0.20, 0.30)),
    DamageType("early", "neurons switched off in the first third of its layers", "mlp", tuple(EARLY),
               (0.30, 0.40, 0.50, 0.60, 0.70)),
    DamageType("late", "neurons switched off in the last third of its layers", "mlp", tuple(LATE),
               (0.20, 0.30, 0.40, 0.50, 0.60)),
    DamageType("heads", "attention heads switched off in every layer", "heads", tuple(ALL),
               (0.10, 0.15, 0.20, 0.25, 0.30)),
]
DAMAGE_BY_KEY = {d.key: d for d in DAMAGE}
PRIMARY_TYPES = ("all", "early", "late")   # the pre-registered question; heads are optional and reported apart


def condition_name(dtype: str, dose: float) -> str:
    return f"{dtype}@{dose:g}"


def parse_condition(name: str) -> tuple[str, float]:
    if name == "intact":
        return "intact", 0.0
    t, _, d = name.partition("@")
    if t not in DAMAGE_BY_KEY or not d:
        raise ValueError(f"bad condition {name!r}")
    return t, float(d)


def conditions(types=None) -> list[str]:
    """Every main-run condition: intact, then each damage type's ladder."""
    out = ["intact"]
    for d in DAMAGE:
        if types is None or d.key in types:
            out += [condition_name(d.key, x) for x in d.doses]
    return out


def unit_order(layer: int, size: int, seed: int = UNIT_SEED) -> np.ndarray:
    """One layer's fixed random order of its units (neurons or heads). A dose of f switches off the first
    round(f * size), so a heavier dose keeps every unit a lighter one switched off (nested), and the early- and
    late-layer types switch off the same units as the all-layers type at the same share."""
    return np.random.default_rng([seed, layer, size]).permutation(size)


def n_off(share: float, size: int) -> int:
    return int(round(share * size))


def damage_units(dtype: str, dose: float, n_neurons: int = N_NEURONS, n_heads: int = N_HEADS,
                 seed: int = UNIT_SEED) -> dict[int, list[int]]:
    """layer -> unit indices switched off."""
    d = DAMAGE_BY_KEY[dtype]
    size = n_neurons if d.site == "mlp" else n_heads
    k = n_off(dose, size)
    return {layer: sorted(unit_order(layer, size, seed)[:k].tolist()) for layer in d.layers}


def lesion_spec_dict(dtype: str, dose: float, **kw) -> dict:
    """A LesionSpec dict (metalesionlab.lesions.LesionSpec.from_dict) for one condition: units set to zero."""
    units = damage_units(dtype, dose, **kw)
    site = DAMAGE_BY_KEY[dtype].site
    return {"name": condition_name(dtype, dose), "method": "zero", site: {str(k): v for k, v in units.items()},
            "recipe": {"type": dtype, "dose": dose, "seed": UNIT_SEED}}


def units_off(dtype: str, dose: float) -> dict:
    """How many units a condition switches off, and their share of the whole model's neurons (or heads)."""
    d = DAMAGE_BY_KEY[dtype]
    size = N_NEURONS if d.site == "mlp" else N_HEADS
    k = n_off(dose, size) * len(d.layers)
    return {"site": d.site, "units": k, "share_of_model": k / (size * N_LAYERS), "layers": len(d.layers)}


# ---------- the description rubric (fixed before the main run) ----------

NAMES = {
    "chair": ("chair", "chairs"),
    "clock": ("clock", "clocks", "timepiece"),
    "god": ("god", "deity", "creator", "almighty", "lord", "divine being", "supreme being", "higher power"),
}
ATTRIBUTES = {
    "chair": ("sit", "sits", "sitting", "seat", "seats", "seated", "seating", "back", "backrest", "leg", "legs",
              "arm", "arms", "armrest", "armrests", "furniture", "person", "one person", "someone", "support",
              "supports", "rest"),
    "clock": ("time", "times", "hour", "hours", "minute", "minutes", "second", "seconds", "hand", "hands",
              "number", "numbers", "numeral", "numerals", "dial", "face", "tick", "ticks", "ticking", "measure",
              "measures", "tell", "tells", "display", "displays", "show", "shows", "indicate", "indicates", "keep",
              "keeps"),
    "god": ("supreme", "create", "created", "creates", "creation", "universe", "world", "all-powerful",
            "omnipotent", "omniscient", "omnipresent", "eternal", "infinite", "divine", "being", "worship",
            "worshipped", "worshiped", "faith", "religion", "religions", "religious", "belief", "beliefs",
            "believe", "believed", "spirit", "spiritual", "heaven", "almighty", "power", "powerful", "love",
            "all-knowing", "existence", "everything", "sacred", "holy"),
}
WORD_RE = re.compile(r"[a-z]+(?:[-'][a-z]+)*")


def words(text: str) -> list[str]:
    return WORD_RE.findall((text or "").lower())


def _has_any(text: str, phrases) -> list[str]:
    ws = words(text)
    joined = " " + " ".join(ws) + " "
    return sorted({p for p in phrases if (" " + p + " ") in joined})


def names_thing(text: str, key: str) -> bool:
    """The answer names the thing (or, for God, a fixed synonym)."""
    return bool(_has_any(text, NAMES[key]))


def attributes(text: str, key: str) -> list[str]:
    """The rubric's parts and properties the answer mentions."""
    return _has_any(text, ATTRIBUTES[key])


MIN_WORDS, MAX_WORDS = 4, 60


def fluency(text: str, finished: bool = True, zipf=None) -> dict:
    """A fixed, mechanical "is this a well-formed sentence?" check. Fluent when all hold:
    finished (the model stopped by itself); 4-60 words; starts with a capital letter (or a quote); ends with
    . ! or ?; no word repeated three times in a row and no three-word phrase repeated; at least 90% of the words
    are English words (wordfreq Zipf >= 1); no code (< or { or SVG)."""
    t = (text or "").strip()
    ws = words(t)
    checks = {"finished": bool(finished), "length": MIN_WORDS <= len(ws) <= MAX_WORDS,
              "capital": bool(t) and (t[0].isupper() or t[0] in "\"'“‘"),
              "ends": bool(re.search(r"[.!?][\"'”’)]*$", t)),
              "no_code": not re.search(r"[<>{}]|svg|```", t, re.I)}
    rep = any(ws[i] == ws[i + 1] == ws[i + 2] for i in range(len(ws) - 2))
    tri = [tuple(ws[i:i + 3]) for i in range(len(ws) - 2)]
    checks["no_loops"] = not rep and len(tri) == len(set(tri))
    if zipf is None:
        from wordfreq import zipf_frequency

        def zipf(w):
            return zipf_frequency(w, "en")
    real = [w for w in ws if zipf(w) >= 1.0]
    checks["real_words"] = bool(ws) and len(real) / len(ws) >= 0.9
    return {"fluent": all(checks.values()), "checks": checks, "n_words": len(ws)}


def score_description(text: str, key: str, finished: bool = True, zipf=None) -> dict:
    """The fixed rubric. correct = a short answer (it stopped by itself, at most 60 words, no code) that names the
    thing AND mentions at least one of its rubric attributes. The short-answer part was added after the pilot, before
    the main run: under heavy damage, long rambles that mention "clock" and "time" in passing were being counted."""
    named, attrs = names_thing(text, key), attributes(text, key)
    fl = fluency(text, finished, zipf)
    c = fl["checks"]
    short = c["finished"] and fl["n_words"] <= MAX_WORDS and c["no_code"]
    return {"names": named, "attributes": attrs, "short": short, "correct": named and bool(attrs) and short,
            "fluent": fl["fluent"], "fluency_checks": c, "n_words": fl["n_words"]}


# ---------- the clock's numbers (descriptive) ----------

_TEXT_EL = re.compile(r"<text\b[^>]*>(.*?)</text\s*>", re.I | re.S)


def clock_numbers(svg: str | None) -> dict:
    """Which of the numbers 1-12 the drawing's code writes as text elements (the clinical "put in all the numbers")."""
    if not svg:
        return {"numbers": [], "all_12": False}
    found = set()
    for m in _TEXT_EL.finditer(svg):
        inner = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if inner.isdigit() and 1 <= int(inner) <= 12:
            found.add(int(inner))
    return {"numbers": sorted(found), "all_12": len(found) == 12}


# ---------- statistics ----------

def first_below_half(rates: list[float], intact: float) -> int | None:
    """The first ladder step (1-based) whose rate is below half the intact rate, or None if none is (or the intact
    rate is 0, so there is nothing to lose)."""
    if not intact > 0:
        return None
    for i, r in enumerate(rates, 1):
        if r < intact / 2:
            return i
    return None


def order_verdict(step_picture: int | None, step_word: int | None) -> str:
    """Which fails first, from the first step below half intact: "picture first", "word first", "together" or
    "neither" (both survive the whole ladder)."""
    if step_picture is None and step_word is None:
        return "neither"
    if step_word is None or (step_picture is not None and step_picture < step_word):
        return "picture first"
    if step_picture is None or step_word < step_picture:
        return "word first"
    return "together"


def retention(rates: np.ndarray, intact: np.ndarray) -> np.ndarray:
    """rates (..., steps) / intact (...); NaN where intact is 0."""
    intact = np.asarray(intact, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(intact[..., None] > 0, np.asarray(rates, float) / intact[..., None], np.nan)


def gap_verdict(ci: list[float]) -> str:
    """The pre-registered rule for the word-minus-picture retention gap (averaged over the ladder): above 0 means
    the words outlast the picture ("picture first"), below 0 the reverse; a CI spanning 0 is "together"."""
    lo, hi = ci
    if lo != lo or hi != hi:
        return "not testable"
    if lo > 0:
        return "picture first"
    if hi < 0:
        return "word first"
    return "together"


def retention_curves(x: np.ndarray) -> np.ndarray:
    """x: (..., conditions = intact + ladder, things, N) of 0/1 outcomes -> (..., ladder steps): each thing's rate
    at each step over its own intact rate, averaged over the things (each thing counts the same)."""
    r = np.asarray(x, float).mean(-1)  # (..., C, T)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (r[..., 1:, :] / r[..., :1, :]).mean(-1)


def gap_of(pic: np.ndarray, word: np.ndarray) -> np.ndarray:
    """The word-minus-picture retention gap, averaged over the ladder steps (> 0: the words outlast the picture)."""
    return (retention_curves(word) - retention_curves(pic)).mean(-1)


def _resample(x: np.ndarray, reps: int, rng: np.random.Generator) -> np.ndarray:
    """Bootstrap replicates of x (..., N): the N samples resampled within every other index."""
    idx = rng.integers(0, x.shape[-1], (reps,) + x.shape)
    return np.take_along_axis(np.broadcast_to(x, (reps,) + x.shape), idx, -1)


def boot_gap(pic: np.ndarray, word: np.ndarray, reps: int = 4000, seed: int = 0) -> dict:
    """pic, word: (conditions = intact + ladder, things, N) of 0/1 outcomes. The gap (gap_of) and its 95% percentile
    bootstrap CI, resampling the N answers within each condition and thing (replicates where some thing's intact rate
    resamples to 0 are dropped and counted)."""
    rng = np.random.default_rng(seed)
    pic, word = np.asarray(pic, float), np.asarray(word, float)
    est = float(gap_of(pic, word))
    g = gap_of(_resample(pic, reps, rng), _resample(word, reps, rng))
    ok = np.isfinite(g)
    ci = [float(np.percentile(g[ok], 2.5)), float(np.percentile(g[ok], 97.5))] if ok.any() else [float("nan")] * 2
    return {"gap": est, "ci95": ci, "reps": int(ok.sum()), "dropped": int((~ok).sum()), "boot": g}


def boot_gap_difference(a: dict, b: dict) -> list[float]:
    """CI of gap(a) - gap(b) from two independent boot_gap results (each with its own replicates)."""
    ga, gb = a["boot"], b["boot"]
    ok = np.isfinite(ga) & np.isfinite(gb)
    d = ga[ok] - gb[ok]
    return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))] if len(d) else [float("nan")] * 2


def boot_rate_ci(x: np.ndarray, reps: int = 4000, seed: int = 0) -> list[float]:
    x = np.asarray(x, float).ravel()
    if not len(x):
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    b = x[rng.integers(0, len(x), (reps, len(x)))].mean(1)
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


# ---------- the public file ----------

PUBLIC_KEYS = {"about", "credits", "things", "damage", "conditions", "verdict", "cost"}

# The damaged model sometimes swears. The public file shows a swear word the comic-strip way: its first letter, then
# symbols for the rest ("F&$# you"), so a reader can tell what was said without reading the word itself.
SWEARS = re.compile(r"\b(?:(?:mother)?fuck|shit|bullshit|bitch|cunt|asshole|bastard|whore|slut)\w*", re.I)
GRAWLIX = "&$#@!%"


def grawlix(text: str) -> str:
    """The text with each strong swear word masked: "Fuck you" -> "F&$# you", "Holy shit" -> "Holy s&$#"."""
    return SWEARS.sub(lambda m: m[0][0] + "".join(GRAWLIX[i % len(GRAWLIX)] for i in range(len(m[0]) - 1)), text or "")


def validate_public(d: dict) -> list[str]:
    """Problems with web/data/plato_glimmer.json (empty = fine): derived numbers, short example sentences and the
    sprite layout only; no SVG code, no embeddings."""
    errs = []
    if missing := PUBLIC_KEYS - set(d):
        errs.append(f"missing keys: {sorted(missing)}")

    def walk(x, path="$"):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("svg", "embedding", "embeddings", "cls"):
                    errs.append(f"{path}.{k}: per-sample data is not allowed")
                walk(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
        elif isinstance(x, str) and "<svg" in x.lower():
            errs.append(f"{path}: SVG text is not allowed")
        elif isinstance(x, float) and x != x:
            errs.append(f"{path}: NaN (use null)")

    walk(d)
    return errs

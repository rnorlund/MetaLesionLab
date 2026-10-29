"""Prisoners of the cave: does a model that has seen pictures draw a better chair than its text-only twin?
(docs/plato_cave_twins_plan.md)

In Plato's cave the prisoners know only shadows. A language model trained only on text knows chairs only from
words. Its twin, built from the same base model and also trained on pictures, has "seen" chairs. Both twins get
text only (no picture goes in), the same requests and the same sampling as the model-size arm of
docs/plato_scale.md, so the difference between them is how they were trained.

This module holds the pure parts: the twins (pinned revisions), the three tasks and their prompts, the blind
coding sheets and their hash, the keyword check of the descriptions, the statistics and verdict rule, and the
public file's schema. GPU work is scripts/plato_twins_generate.py; measuring and coding is
scripts/plato_twins_measure.py; the analysis is scripts/plato_twins_analyze.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from metalesionlab import plato_scale as ps

TWINS_DIR = Path(os.environ.get("PLATO_TWINS_DIR",
                                "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/cave_twins"))

# ---------- the twins ----------


@dataclass(frozen=True)
class Twin:
    key: str            # short id, used for files
    label: str          # what the figures say
    size: str           # "7B" or "32B": which pair
    arm: str            # "text" (trained on text only) or "vision" (also trained on pictures)
    hf: str             # Hugging Face repo
    revision: str       # pinned Hub revision
    params_b: float     # the Hub's safetensors total (the vision twins include their picture encoder)
    licence: str
    fp8: bool = False   # FP8 weights to fit one 46 GB card, as in the scale experiment
    scale_key: str = ""  # the scale experiment's key whose chair answers are reused ("" = generated here)

    @property
    def vl(self) -> bool:
        return self.arm == "vision"


# Checked on the Hub on 2026-10-28: all four ungated, Apache-2.0. The text twins' revisions are the scale
# experiment's pins (metalesionlab/plato_scale.py). The other Qwen2.5-VL sizes are not Apache-2.0 (3B: Qwen
# Research licence; 72B: Qwen licence) and are not used.
MODELS = [
    Twin("qwen25_7b", "Qwen2.5 7B", "7B", "text", "Qwen/Qwen2.5-7B-Instruct",
         "a09a35458c702b33eeacc393d103063234e8bc28", 7.616, "Apache-2.0", scale_key="qwen25_7b"),
    Twin("qwen25vl_7b", "Qwen2.5-VL 7B", "7B", "vision", "Qwen/Qwen2.5-VL-7B-Instruct",
         "cc594898137f460bfe9f0759e9844b3ce807cfb5", 8.292, "Apache-2.0"),
    Twin("qwen25_32b", "Qwen2.5 32B", "32B", "text", "Qwen/Qwen2.5-32B-Instruct",
         "5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd", 32.76, "Apache-2.0", fp8=True, scale_key="qwen25_32b"),
    Twin("qwen25vl_32b", "Qwen2.5-VL 32B", "32B", "vision", "Qwen/Qwen2.5-VL-32B-Instruct",
         "7cfb30d71a1f4f49a57592323337a4a4727301da", 33.45, "Apache-2.0", fp8=True),
]
BY_KEY = {m.key: m for m in MODELS}
SIZES = ["7B", "32B"]
PAIRS = {s: (next(m for m in MODELS if m.size == s and m.arm == "text"),
             next(m for m in MODELS if m.size == s and m.arm == "vision")) for s in SIZES}
SKIPPED = [
    {"model": "Qwen/Qwen2.5-VL-3B-Instruct", "reason": "Qwen Research licence (not Apache-2.0)"},
    {"model": "Qwen/Qwen2.5-VL-72B-Instruct", "reason": "Qwen licence (not Apache-2.0); too big for one card"},
]

# ---------- the tasks ----------

CLOCK_PROMPT = ("Draw a clock showing 10 past 11 as an SVG drawing: black strokes only on a white background, "
                "256 by 256 pixels, no colour fill. Output only the SVG code.")
DESCRIBE_PROMPT = "Describe what a chair looks like in two sentences."


@dataclass(frozen=True)
class Task:
    key: str
    prompt: str
    svg: bool           # the answer is a drawing written as SVG code
    temps: tuple        # sampling temperatures (the first is primary)
    concept: str = ""   # which of the 35 Plato's Chair names a drawing should be read as


TASKS = {
    # the scale experiment's request, word for word; 0.7 is the scale experiment's check temperature
    "chair": Task("chair", ps.PROMPT, True, (1.0, 0.7), "chair"),
    # a clock may carry numbers, so "no text" is dropped; otherwise the chair request's wording
    "clock": Task("clock", CLOCK_PROMPT, True, (1.0,), "clock"),
    "describe": Task("describe", DESCRIBE_PROMPT, False, (1.0,)),
}
N = ps.N_B                    # 12 answers per model, task and temperature
PRIMARY_TEMP = 1.0
MAX_NEW_TOKENS = ps.MAX_NEW_TOKENS
BOOT_SEED = 20261029
REPS = 2000


def raw_name(key: str, task: str, temp: float) -> str:
    return f"{key}_{task}_t{temp:.1f}"


def gen_seed(temp: float) -> int:
    """The torch seed of one batch of 12 (the scale experiment's rule, the same for every model and task)."""
    return ps.gen_seed(temp)


# ---------- descriptions: the fixed rubric and its keyword check ----------

PARTS = ("seat", "legs", "back")
# The automatic check, run only after the by-eye codes are hashed. Deliberately simple: a word is enough.
KEYWORDS = {
    "seat": re.compile(r"\bseat(s|ed|ing)?\b|\bsit(s|ting)?\b", re.I),
    "legs": re.compile(r"\blegs?\b", re.I),
    "back": re.compile(r"\bback(s|rest|rests)?\b", re.I),
}


def keyword_parts(text: str) -> dict:
    """Which of the rubric's parts a description names, by keyword (0/1 each)."""
    return {p: int(bool(KEYWORDS[p].search(text or ""))) for p in PARTS}


def rubric_score(codes: dict) -> int:
    """0 to 3: how many of seat, legs and back a description mentions."""
    return int(sum(int(codes[p]) for p in PARTS))


def first_sentence(text: str, limit: int = 220) -> str:
    """The quote the page shows: the answer's first sentence (rule fixed in the plan, not chosen by eye)."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    m = re.search(r"^(.+?[.!?])(\s|$)", t)
    s = m.group(1) if m else t
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


# ---------- blind coding sheets ----------

def blind_order(items: list, salt: str) -> list:
    """A fixed shuffle of (key, task, temp, i) items, so the coder can't tell which model made which."""
    rng = np.random.default_rng([BOOT_SEED, int(hashlib.sha256(salt.encode()).hexdigest()[:8], 16)])
    return [items[k] for k in rng.permutation(len(items))]


def sheet_ids(items: list, prefix: str) -> dict:
    """Anonymous ids ("D01", ...) for items already in blind order: id -> item."""
    w = max(2, len(str(len(items))))
    return {f"{prefix}{k + 1:0{w}d}": it for k, it in enumerate(items)}


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def codes_hash(codes: dict) -> str:
    """SHA-256 of the by-eye codes in canonical JSON: recorded (and committed) before any automatic scoring."""
    return hashlib.sha256(canonical(codes)).hexdigest()


CLOCK_TIMES = ("11:10", "other", "unclear")
DESC_CODE_KEYS = set(PARTS)
CLOCK_CODE_KEYS = {"face", "hands", "time"}
CHAIR_CODE_KEYS = {"chair"}


def validate_codes(codes: dict, ids: list, keys: set, kind: str) -> list[str]:
    """Problems with a codes file (empty list = fine): every id coded once, with exactly the expected keys."""
    errs = []
    if set(codes) != set(ids):
        errs.append(f"{kind}: ids differ: missing {sorted(set(ids) - set(codes))[:5]}, extra {sorted(set(codes) - set(ids))[:5]}")
    for k, v in codes.items():
        if set(v) != keys:
            errs.append(f"{kind} {k}: keys {sorted(v)} != {sorted(keys)}")
            continue
        for f, x in v.items():
            if f == "time":
                if x not in CLOCK_TIMES:
                    errs.append(f"{kind} {k}: time {x!r}")
            elif x not in (0, 1):
                errs.append(f"{kind} {k}: {f}={x!r}")
    return errs


def cohen_kappa(a: list, b: list) -> float | None:
    """Agreement of two binary codings beyond chance; None when chance agreement is total."""
    a, b = np.asarray(a, int), np.asarray(b, int)
    po = float((a == b).mean())
    pa, pb = a.mean(), b.mean()
    pe = float(pa * pb + (1 - pa) * (1 - pb))
    return None if pe >= 1 else (po - pe) / (1 - pe)


# ---------- statistics and the verdict rule ----------

def boot_diff(a, b, reps: int = REPS, seed: int = BOOT_SEED) -> np.ndarray:
    """Bootstrap replicates of mean(b) - mean(a), resampling each model's answers independently."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    return ps.boot_mean(b, reps, rng) - ps.boot_mean(a, reps, rng)


def pct_ci(x: np.ndarray) -> list[float]:
    return [float(np.quantile(x, 0.025)), float(np.quantile(x, 0.975))]


def size_verdict(ci95: list[float]) -> str:
    """One size: 'supported' if the vision twin's advantage has a 95% CI above 0, 'contradicted' if below 0."""
    lo, hi = ci95
    if lo > 0:
        return "supported"
    if hi < 0:
        return "contradicted"
    return "unclear"


def overall_verdict(by_size: dict) -> str:
    """P1 over both sizes: supported at both; partly at one (and not contradicted at the other); contradicted if
    contradicted at either; otherwise unclear."""
    v = list(by_size.values())
    if "contradicted" in v:
        return "contradicted"
    if all(x == "supported" for x in v):
        return "supported"
    if "supported" in v:
        return "partly supported"
    return "unclear"


EQUIV_MARGIN = 0.5      # rubric points (of 3): "equally good" if the difference's 95% CI lies within ±0.5
KNOWS_WORD = 2.0        # mean rubric score at least 2 of 3: "knows the word"


def describe_verdict(mean_text: float, mean_vision: float, ci95: list[float]) -> str:
    """P2 at one size: both twins know the word and the difference is within the margin."""
    if min(mean_text, mean_vision) < KNOWS_WORD:
        return "not supported"
    lo, hi = ci95
    if -EQUIV_MARGIN < lo and hi < EQUIV_MARGIN:
        return "supported"
    return "unclear"


# ---------- the public file ----------

PUBLIC_KEYS = {"about", "credits", "models", "tasks", "rows", "pairs", "predictions", "quotes", "hashes", "skipped"}
ROW_KEYS = {"key", "task", "temp", "n", "valid", "failed", "read_as", "read_as_ci95"}


def validate_public(d: dict) -> list[str]:
    """Problems with public_data/plato_twins.json (empty list = fine): derived statistics plus one quoted sentence
    per model; no SVG code, drawings or embeddings."""
    errs = []
    missing = PUBLIC_KEYS - set(d)
    if missing:
        errs.append(f"missing keys: {sorted(missing)}")
    for row in d.get("rows", []):
        lack = ROW_KEYS - set(row)
        if lack:
            errs.append(f"row {row.get('key')}/{row.get('task')} lacks {sorted(lack)}")

    def walk(x, path="$"):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("svg", "image", "embedding", "embeddings", "cls", "drawing", "drawings", "texts", "raw"):
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

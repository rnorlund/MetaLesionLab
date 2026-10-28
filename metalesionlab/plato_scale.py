"""An AI growing up: does an AI's idea of a chair change with more data and a bigger model? (docs/plato_scale_plan.md)

Arm A trains the sketch model of docs/plato_sketch.md on nested random subsets of Quick, Draw! chairs (Google,
CC BY 4.0), from 100 to 20,000. Arm B asks language models of growing size to draw a chair as SVG code; the SVG is
rendered, ink-cropped and embedded with DINOv2 like every other Plato's Chair drawing.

This module holds the pure parts: the design (models, sizes, seeds), SVG extraction, rendering and failure
classification, nested subsets, the best-checkpoint rule, small statistics and the public file's schema.
GPU work is scripts/plato_scale_sketch.py (Arm A) and scripts/plato_scale_svg.py (Arm B); the analysis is
scripts/plato_scale_analyze.py.
"""
from __future__ import annotations

import io
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SCALE_DIR = Path(os.environ.get("PLATO_SCALE_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/scale"))

# ---------- Arm B: the prompt and the models ----------

PROMPT = ("Draw a simple chair as an SVG drawing: black strokes only on a white background, 256 by 256 pixels, "
          "no text, no colour fill. Output only the SVG code.")
TEMPS_B = [1.0, 0.7]
PRIMARY_TEMP_B = 1.0
N_B = 12
MAX_NEW_TOKENS = 2048
API_MAX_TOKENS = 2304          # 2,048 plus room for "minimal" reasoning, which bills as output
GEN_SEED = 20261028


def gen_seed(temp: float) -> int:
    """The torch seed of one model's batch of 12 at one temperature (the same for every model)."""
    return GEN_SEED + int(round(100 * temp))


@dataclass(frozen=True)
class LM:
    key: str            # short id, used for folders
    label: str          # what the figures say
    family: str         # Qwen2.5, OLMo 2, Qwen3, Muse
    hf: str             # Hugging Face repo, or the API model name
    revision: str       # pinned Hub revision ("" for API models)
    params_b: float     # parameters in billions, from the Hub's safetensors total; nan when undisclosed
    licence: str
    kind: str = "open"  # open | api
    fp8: bool = False   # weights in FP8 to fit one 46 GB card
    chat_kwargs: tuple = ()  # extra apply_chat_template arguments, e.g. (("enable_thinking", False),)


MODELS = [
    LM("qwen25_0.5b", "Qwen2.5 0.5B", "Qwen2.5", "Qwen/Qwen2.5-0.5B-Instruct", "7ae557604adf67be50417f59c2c2f167def9a775", 0.494, "Apache-2.0"),
    LM("qwen25_1.5b", "Qwen2.5 1.5B", "Qwen2.5", "Qwen/Qwen2.5-1.5B-Instruct", "989aa7980e4cf806f80c7fef2b1adb7bc71aa306", 1.544, "Apache-2.0"),
    LM("qwen25_7b", "Qwen2.5 7B", "Qwen2.5", "Qwen/Qwen2.5-7B-Instruct", "a09a35458c702b33eeacc393d103063234e8bc28", 7.616, "Apache-2.0"),
    LM("qwen25_14b", "Qwen2.5 14B", "Qwen2.5", "Qwen/Qwen2.5-14B-Instruct", "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8", 14.77, "Apache-2.0"),
    LM("qwen25_32b", "Qwen2.5 32B", "Qwen2.5", "Qwen/Qwen2.5-32B-Instruct", "5ede1c97bbab6ce5cda5812749b4c0bdf79b18dd", 32.76, "Apache-2.0", fp8=True),
    LM("olmo2_1b", "OLMo 2 1B", "OLMo 2", "allenai/OLMo-2-0425-1B-Instruct", "48d788eca847d4d7548f375ad03d3c9312f6139e", 1.485, "Apache-2.0"),
    LM("olmo2_7b", "OLMo 2 7B", "OLMo 2", "allenai/OLMo-2-1124-7B-Instruct", "470b1fba1ae01581f270116362ee4aa1b97f4c84", 7.299, "Apache-2.0"),
    LM("olmo2_13b", "OLMo 2 13B", "OLMo 2", "allenai/OLMo-2-1124-13B-Instruct", "3a5c85baefbb1896a54d56fe2e76c0395627ddf4", 13.72, "Apache-2.0"),
    LM("olmo2_32b", "OLMo 2 32B", "OLMo 2", "allenai/OLMo-2-0325-32B-Instruct", "b96024342a77a69aa0dda815c3454a671f477463", 32.23, "Apache-2.0", fp8=True),
    LM("qwen3_0.6b", "Qwen3 0.6B", "Qwen3", "Qwen/Qwen3-0.6B", "c1899de289a04d12100db370d81485cdf75e47ca", 0.752, "Apache-2.0", chat_kwargs=(("enable_thinking", False),)),
    LM("qwen3_1.7b", "Qwen3 1.7B", "Qwen3", "Qwen/Qwen3-1.7B", "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e", 2.032, "Apache-2.0", chat_kwargs=(("enable_thinking", False),)),
    LM("qwen3_4b", "Qwen3 4B", "Qwen3", "Qwen/Qwen3-4B", "1cfa9a7208912126459214e8b04321603b3df60c", 4.022, "Apache-2.0", chat_kwargs=(("enable_thinking", False),)),
    LM("qwen3_8b", "Qwen3 8B", "Qwen3", "Qwen/Qwen3-8B", "b968826d9c46dd6066d109eabc6255188de91218", 8.191, "Apache-2.0", chat_kwargs=(("enable_thinking", False),)),
    LM("qwen3_14b", "Qwen3 14B", "Qwen3", "Qwen/Qwen3-14B", "40c069824f4251a91eefaf281ebe4c544efd3e18", 14.77, "Apache-2.0", chat_kwargs=(("enable_thinking", False),)),
    LM("qwen3_32b", "Qwen3 32B", "Qwen3", "Qwen/Qwen3-32B", "9216db5781bf21249d130ec9da846c4624c16137", 32.76, "Apache-2.0", fp8=True, chat_kwargs=(("enable_thinking", False),)),
    LM("glimmer", "Muse Glimmer 30B", "Muse", "meta-models/Muse-Glimmer-30B", "cec94fcfd6512f2cfe708138c32533b346ea4f69", 29.78, "Apache-2.0", fp8=True),
    LM("spark", "Muse Spark 1.3", "Muse", "muse-spark-1.3", "", float("nan"), "Meta Model API", kind="api"),
    LM("wonder", "Muse Wonder 1.0", "Muse", "muse-wonder-1.0", "", float("nan"), "Meta Model API", kind="api"),
]
BY_KEY = {m.key: m for m in MODELS}
FAMILIES = ["Qwen2.5", "OLMo 2", "Qwen3"]
PRIMARY_FAMILY = "Qwen2.5"
# Checked on the Hub on 2026-10-28; not used. We never log in or accept a licence.
SKIPPED = [
    {"model": "Qwen/Qwen2.5-3B-Instruct", "reason": "Qwen Research licence (not Apache-2.0)", "licence": "qwen-research"},
    {"model": "Qwen/Qwen2.5-72B-Instruct", "reason": "Qwen licence (not Apache-2.0); too big for one card", "licence": "qwen"},
    {"model": "meta-llama/Llama-3.2-1B-Instruct, -3B, Llama-3.1-8B, Llama-3.3-70B", "reason": "gated (licence acceptance)", "licence": "llama3.x"},
    {"model": "google/gemma-3-1b-it (Gemma 3)", "reason": "gated (licence acceptance)", "licence": "gemma"},
]


def family_models(family: str) -> list[LM]:
    """A family's models, smallest first."""
    return sorted([m for m in MODELS if m.family == family], key=lambda m: m.params_b)


def size_band(params_b: float) -> str | None:
    """The plan's size bands for the cross-family test (E1)."""
    if params_b != params_b:  # nan: size undisclosed
        return None
    for name, lo, hi in (("<=2B", 0, 2.1), ("4-8B", 3.5, 8.5), ("13-15B", 12.5, 15.5), ("30-33B", 29, 33.5)):
        if lo <= params_b <= hi:
            return name
    return None


# ---------- SVG: extract, render, classify ----------

MAX_SVG_BYTES = 200_000
SIDE = 256
INK_LEVEL = 200          # gray below this is ink (as in plato.ink_crop)
BLANK_BELOW = 0.001      # under 0.1% ink: blank
FLOODED_ABOVE = 0.95     # over 95% ink: no drawing visible
FAILURES = ("no_svg", "render_error", "blank", "flooded")
FAILURE_LABELS = {"no_svg": "no SVG", "render_error": "didn't render", "blank": "blank", "flooded": "all ink"}

_SVG = re.compile(r"<svg\b.*?</svg\s*>", re.I | re.S)


def extract_svg(text: str | None) -> str | None:
    """The first complete <svg ...> ... </svg> in a model's answer (Markdown fences and prose around it are
    ignored), or None. Output cut off before </svg> has no complete SVG."""
    if not text:
        return None
    m = _SVG.search(text)
    return m.group(0) if m else None


def _ensure_namespace(svg: str) -> str:
    """Models often omit xmlns; browsers then still draw an inline <svg>, so the renderer gets it added."""
    head = svg[:svg.find(">") + 1]
    if "xmlns=" in head:
        return svg
    return "<svg xmlns=\"http://www.w3.org/2000/svg\"" + svg[4:]


def render_svg(svg: str, side: int = SIDE):
    """Render an SVG to a side x side grayscale PIL image on white, keeping its aspect ratio (centred).

    The SVG's own size (width/height or viewBox) is scaled so its longer side is `side`; an SVG with no size is
    drawn at side x side. cairosvg runs with unsafe=False: no external files or network, no XML entities (only
    data: URLs load). Raises on anything the renderer can't draw."""
    import cairosvg
    from PIL import Image

    data = _ensure_namespace(svg).encode("utf-8")
    if len(data) > MAX_SVG_BYTES:
        raise ValueError(f"SVG is {len(data)} bytes, over {MAX_SVG_BYTES}")
    try:
        png = cairosvg.svg2png(bytestring=data, output_width=side, unsafe=False)
        img = Image.open(io.BytesIO(png))
        if img.height > side:
            png = cairosvg.svg2png(bytestring=data, output_height=side, unsafe=False)
            img = Image.open(io.BytesIO(png))
    except ValueError as e:
        if "size is undefined" not in str(e):
            raise
        png = cairosvg.svg2png(bytestring=data, output_width=side, output_height=side, unsafe=False)
        img = Image.open(io.BytesIO(png))
    img = img.convert("RGBA")
    canvas = Image.new("RGBA", (side, side), (255, 255, 255, 255))
    canvas.alpha_composite(img, ((side - img.width) // 2, (side - img.height) // 2))
    return canvas.convert("L")


def ink_fraction(gray) -> float:
    a = np.asarray(gray)
    return float((a < INK_LEVEL).mean())


def touches_all_edges(gray, margin: int = 2) -> bool:
    """Ink within `margin` px of all four edges: a frame or a filled background (descriptive, as for SDXL)."""
    a = np.asarray(gray) < INK_LEVEL
    return bool(a[:margin].any() and a[-margin:].any() and a[:, :margin].any() and a[:, -margin:].any())


def classify(text: str | None, side: int = SIDE) -> dict:
    """One sample, from the model's raw text: {'ok', 'reason', 'svg', 'image', 'ink'}.

    reason is None when the sample is a drawing, else one of FAILURES:
    no_svg (no complete <svg>...</svg>), render_error, blank (< 0.1% ink) or flooded (> 95% ink)."""
    svg = extract_svg(text)
    if svg is None:
        return {"ok": False, "reason": "no_svg", "svg": None, "image": None, "ink": None}
    try:
        img = render_svg(svg, side)
    except Exception as e:  # noqa: BLE001  any renderer error is the model's failure to write a drawable SVG
        return {"ok": False, "reason": "render_error", "svg": svg, "image": None, "ink": None, "error": str(e)[:200]}
    ink = ink_fraction(img)
    if ink < BLANK_BELOW:
        return {"ok": False, "reason": "blank", "svg": svg, "image": img, "ink": ink}
    if ink > FLOODED_ABOVE:
        return {"ok": False, "reason": "flooded", "svg": svg, "image": img, "ink": ink}
    return {"ok": True, "reason": None, "svg": svg, "image": img, "ink": ink}


def failure_counts(reasons: list[str | None]) -> dict:
    """Counts of each failure reason (None = a drawing), the total and the failure rate."""
    n = len(reasons)
    out = {r: sum(1 for x in reasons if x == r) for r in FAILURES}
    unknown = [x for x in reasons if x is not None and x not in FAILURES]
    if unknown:
        raise ValueError(f"unknown failure reasons: {sorted(set(unknown))}")
    k = sum(out.values())
    return {**out, "n": n, "failed": k, "rendered": n - k, "rate": k / n if n else float("nan")}


def wilson(k: int, n: int, z: float = 1.959964) -> list[float]:
    """Wilson 95% interval for k successes out of n."""
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0.0, mid - half), min(1.0, mid + half)]


# ---------- Arm A: data sizes ----------

SIZES = [100, 300, 1000, 3000, 10000, 20000]
SEEDS_A = [1, 2, 3]
TEMPS_A = [1.0, 0.6]
PRIMARY_TEMP_A = 1.0
PERM_SEED = 20261028
N_HELDOUT = 1000
N_TRAIN_LOSS = 1000
N_TRAIN_REF = 1000
ANIM_INDEX = 0           # the animation's data strand: seed 1, noise index 0
WALL_A = {"seed": 1, "n": 12}


def run_name_a(size: int, seed: int) -> str:
    return f"n{size}_s{seed}"


def nested_order(seed: int, n_total: int) -> np.ndarray:
    """Seed s's shuffle of the full set; size n uses its first n (so the subsets are nested within a seed)."""
    return np.random.default_rng([PERM_SEED, seed]).permutation(n_total)


def nested_subset(seed: int, n_total: int, size: int) -> np.ndarray:
    if size > n_total:
        raise ValueError(f"size {size} > {n_total}")
    return nested_order(seed, n_total)[:size]


def best_checkpoint(heldout: dict) -> int:
    """The checkpoint with the lowest held-out loss (the earliest if tied); NaN losses never win."""
    items = [(float(v), int(k)) for k, v in heldout.items() if v == v]
    if not items:
        raise ValueError("no finite held-out loss")
    best = min(v for v, _ in items)
    return min(k for v, k in items if v == best)


# ---------- statistics ----------

def boot_mean(x, reps: int, rng: np.random.Generator) -> np.ndarray:
    """Bootstrap replicates of the mean of x (resampling its items)."""
    x = np.asarray(x, float)
    if len(x) == 0:
        return np.full(reps, np.nan)
    return x[rng.integers(0, len(x), (reps, len(x)))].mean(1)


def verdict(contrast_ci: list[float], trend_sign: float, predicted: int) -> str:
    """The plan's rule. predicted = +1 (should rise) or -1 (should fall). 'supported' if the contrast CI excludes
    0 in the predicted direction and the trend has the predicted sign; 'contradicted' if the CI excludes 0 the
    other way; otherwise 'unclear'."""
    lo, hi = contrast_ci
    if lo != lo or hi != hi:
        return "not testable"
    if predicted > 0:
        if lo > 0 and trend_sign > 0:
            return "supported"
        if hi < 0:
            return "contradicted"
    else:
        if hi < 0 and trend_sign < 0:
            return "supported"
        if lo > 0:
            return "contradicted"
    return "unclear"


# ---------- the public file ----------

PUBLIC_KEYS = {"about", "credits", "prompt", "models", "skipped", "arm_b", "arm_a", "predictions", "cost"}
ARM_B_ROW = {"key", "label", "family", "params_b", "kind", "temp", "n", "failed", "rendered", "failure_rate",
             "failure_ci95", "failures", "recog_all", "recog_rendered", "spread", "spread_ci95", "human_spread",
             "spread_ratio", "d_people", "d_muse"}
ARM_A_ROW = {"size", "checkpoint", "temp", "n_seeds", "fail", "recog", "spread", "spread_minus_train", "d_people",
             "d_muse"}


def validate_public(d: dict) -> list[str]:
    """Problems with public_data/plato_scale.json (empty list = fine). It must hold derived statistics only:
    no SVG text, no drawings, no embeddings."""
    errs = []
    missing = PUBLIC_KEYS - set(d)
    if missing:
        errs.append(f"missing keys: {sorted(missing)}")
    for row in d.get("arm_b", {}).get("rows", []):
        lack = ARM_B_ROW - set(row)
        if lack:
            errs.append(f"arm_b row {row.get('key')} lacks {sorted(lack)}")
    for row in d.get("arm_a", {}).get("rows", []):
        lack = ARM_A_ROW - set(row)
        if lack:
            errs.append(f"arm_a row {row.get('size')} lacks {sorted(lack)}")

    def walk(x, path="$"):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("svg", "image", "embedding", "embeddings", "cls", "drawing", "drawings", "strokes", "text"):
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

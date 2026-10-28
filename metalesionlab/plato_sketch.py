"""Watch an AI learn what a chair is: the sketch model across seeds and temperatures (docs/plato_sketch_plan.md).

A Sketch-RNN-style decoder (the Mac run's, scripts/plato_lifespan_sketch.py) is trained from scratch on 20,000
Quick, Draw! chairs (Google, CC BY 4.0) with 8 seeds, and on cats with 5. At 20 log-spaced checkpoints it draws
200 drawings at each of three temperatures from noise that is fixed per seed, so across checkpoints only the
weights differ. This module holds the pure parts: the design, the noise, inverse-CDF sampling, the statistics
across seeds, and helpers for the animation. Training is scripts/plato_sketch_seeds.py; the analysis is
scripts/plato_sketch_analyze.py.

Its chairs were recognizable to DINOv2 but rough to the eye, so the plan's addendum adds a stronger learner, the
one chosen for the animation: the same decoder with 2,048 units, trained on all 203,324 recognized chairs for
102,400 steps (BIG; scripts/plato_sketch_big.py), 4 seeds, the narrowing test on the 3 seeds trained after the
addendum (MODELS["big"]). Pilots it was chosen over: a pixel diffusion model (DIFF; scripts/plato_sketch_diffusion.py)
and, as a ceiling, Magenta's pretrained Sketch-RNN chair (scripts/plato_sketch_magenta.py); compared in
scripts/plato_sketch_compare.py.
"""
from __future__ import annotations

import math

import numpy as np

STEPS = [0, 25, 50, 100, 150, 200, 300, 400, 600, 800, 1200, 1600, 2400, 3200, 4800, 6400, 9600, 12800, 19200, 25600]
MAC_STEPS = [0, 50, 100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600]
TEMPS = [1.0, 0.8, 0.6]
PRIMARY_TEMP = 1.0
SEEDS = {"chair": [1, 2, 3, 4, 5, 6, 7, 8], "cat": [1, 2, 3, 4, 5]}
N_SAMPLES = 200
N_REF = 1000
REF_SEED = 20261027
BOOT_SEED = 20261027
LAST3 = [12800, 19200, 25600]
ANIM = {"seed": 1, "temp": 1.0, "n": 16}  # the animation: seed 1, temperature 1, noise indices 0-15
QUICKDRAW_CREDIT = "Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0"

# The stronger learner (scripts/plato_sketch_big.py): the small model's architecture with 2,048 units, trained on
# every recognized Quick, Draw! chair except the 200 reference chairs. Its checkpoints extend the small model's.
BIG = {"hidden": 2048, "random_scale": 0.15, "lr_decay": 0.9999, "min_lr": 1e-5,
       "n_samples": 200, "temps": [1.0, 0.8, 0.6, 0.4, 0.2],
       "steps": STEPS + [38400, 51200, 76800, 102400]}
# Pilot (b), scripts/plato_sketch_diffusion.py: a small pixel diffusion model on the same chairs, rendered as the
# site renders people's drawings and shrunk to side x side.
DIFF = {"side": 64, "base": 64, "batch": 128, "lr": 2e-4, "warmup": 200, "ema": 0.9995, "ddim_steps": 50,
        "n_samples": 200, "steps": STEPS + [38400, 51200]}

# What the pre-registered analysis (scripts/plato_sketch_analyze.py --model ...) reads for each model. The small
# model is the original plan; the larger one is the plan's addendum: seed 1 is the pilot, whose drawings and
# measures were seen before the addendum was written, so the test uses the fresh seeds 2-4 ("test_seeds").
MODELS = {
    "small": {"dir": "seeds", "run": "{concept}_s{seed}", "seeds": SEEDS, "test_seeds": SEEDS, "steps": STEPS,
              "temps": TEMPS, "primary_temp": PRIMARY_TEMP, "last3": LAST3, "anim": ANIM, "public_key": "sketch_seeds",
              "plan": "docs/plato_sketch_plan.md", "model": "LSTM 512, 20,000 chairs, 25,600 steps"},
    "big": {"dir": "big", "run": "big_s{seed}", "seeds": {"chair": [1, 2, 3, 4]}, "test_seeds": {"chair": [2, 3, 4]},
            "steps": BIG["steps"], "temps": BIG["temps"], "primary_temp": PRIMARY_TEMP, "last3": BIG["steps"][-3:],
            "anim": {"seed": 1, "temp": 0.4, "n": 16}, "public_key": "sketch_big",
            "plan": "docs/plato_sketch_plan.md (addendum: a stronger model)",
            "model": "LSTM 2,048, 203,324 chairs, 102,400 steps"},
}


def model_run_name(model: str, concept: str, seed: int) -> str:
    return MODELS[model]["run"].format(concept=concept, seed=seed)


def run_name(concept: str, seed: int) -> str:
    return f"{concept}_s{seed}"


def sample_name(step: int, temp: float) -> str:
    return f"step{step}_t{temp:.1f}"


def parse_sample_name(stem: str) -> tuple[int, float]:
    """(step, temperature) from 'step3200_t0.8'."""
    step, temp = stem.split("_t")
    return int(step.removeprefix("step")), float(temp)


# ---------- fixed noise and inverse-CDF sampling ----------

def make_noise(seed: int, n: int, max_len: int) -> dict[str, np.ndarray]:
    """The sampling noise of one seed: for drawing i at time t, a uniform number that picks the mixture
    component, one that picks the pen state, and two standard normals for the offset. It is the same at every
    checkpoint and temperature, and comes from its own generator (never the training one)."""
    rng = np.random.default_rng([seed, 5, 7])
    return {"u_mix": rng.random((n, max_len)), "u_pen": rng.random((n, max_len)),
            "e1": rng.standard_normal((n, max_len)), "e2": rng.standard_normal((n, max_len))}


def softmax(logits: np.ndarray, temp: float = 1.0) -> np.ndarray:
    z = np.asarray(logits, float) / temp
    z = z - z.max(-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(-1, keepdims=True)


def categorical_from_uniform(logits: np.ndarray, u: np.ndarray, temp: float = 1.0) -> np.ndarray:
    """Inverse-CDF draw from softmax(logits / temp), one per row, given a uniform number per row: the first
    category whose cumulative probability reaches u."""
    c = softmax(logits, temp).cumsum(-1)
    k = (c < np.asarray(u, float)[..., None]).sum(-1)
    return np.minimum(k, c.shape[-1] - 1)


def categorical_from_uniform_torch(logits, u, temp: float = 1.0):
    """The same draw on torch tensors (used by the sampler on the GPU)."""
    import torch

    c = torch.softmax(logits / temp, -1).cumsum(-1)
    return (c < u[..., None]).sum(-1).clamp(max=logits.shape[-1] - 1)


def offset_from_noise(mux, muy, sx, sy, rho, e1, e2, temp: float):
    """A correlated bivariate normal offset from two standard normals; the variances are scaled by temp."""
    s1, s2 = sx * math.sqrt(temp), sy * math.sqrt(temp)
    return mux + s1 * e1, muy + s2 * (rho * e1 + (1 - rho ** 2) ** 0.5 * e2)


# ---------- drawings ----------

def stroke_stats(drawing: list) -> tuple[int, int]:
    """(strokes, points) of a Quick, Draw! drawing ([[xs], [ys]] per stroke)."""
    return len(drawing), sum(len(s[0]) for s in drawing)


def polyline_length(xs, ys) -> float:
    return float(np.hypot(np.diff(xs), np.diff(ys)).sum()) if len(xs) > 1 else 0.0


def polyline_prefix(xs, ys, length: float) -> tuple[list[float], list[float]]:
    """The first `length` units of a polyline along its arc, ending at an interpolated point (constant pen speed)."""
    xs, ys = [float(v) for v in xs], [float(v) for v in ys]
    if length <= 0 or len(xs) < 2:
        return xs[:1], ys[:1]
    out_x, out_y, done = [xs[0]], [ys[0]], 0.0
    for i in range(1, len(xs)):
        seg = math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1])
        if done + seg >= length:
            t = (length - done) / seg if seg else 1.0
            out_x.append(xs[i - 1] + t * (xs[i] - xs[i - 1]))
            out_y.append(ys[i - 1] + t * (ys[i] - ys[i - 1]))
            return out_x, out_y
        done += seg
        out_x.append(xs[i])
        out_y.append(ys[i])
    return out_x, out_y


def pen_frames(drawing: list, speed: float, pause: int = 4) -> list[tuple[list, bool]]:
    """Frames of a drawing being drawn at a constant pen speed (units per frame): each frame is (strokes so far,
    pen down?). Between strokes the pen is lifted for `pause` frames."""
    frames, done = [], []
    for xs, ys in drawing:
        total = polyline_length(xs, ys)
        n = max(2, math.ceil(total / speed))
        for k in range(1, n + 1):
            px, py = polyline_prefix(xs, ys, total * k / n)
            frames.append((done + [[px, py]], True))
        done = done + [[list(map(float, xs)), list(map(float, ys))]]
        frames += [(done, False)] * pause
    return frames


def is_drawing(d) -> bool:
    """A sample counts if it has at least one point (to_quickdraw returns [] for a single point)."""
    return bool(d) and any(len(s[0]) for s in d)


# ---------- statistics ----------

def boot_counts(n: int, reps: int, rng: np.random.Generator) -> np.ndarray:
    """reps x n resampling counts (how often each drawing is drawn in each bootstrap replicate)."""
    idx = rng.integers(0, n, (reps, n))
    c = np.zeros((reps, n))
    np.add.at(c, (np.repeat(np.arange(reps), n), idx.ravel()), 1)
    return c


def boot_spread(d: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """Spread of each bootstrap replicate from its counts; a drawing drawn twice is never paired with itself."""
    num = ((counts @ d) * counts).sum(1)
    den = counts.sum(1) ** 2 - (counts ** 2).sum(1)
    return num / den


def t_interval(x, level: float = 0.95) -> dict:
    """Mean of per-seed values with a t-interval across seeds (df = n - 1)."""
    from scipy.stats import t

    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    m = float(x.mean()) if n else float("nan")
    if n < 2:
        return {"mean": m, "ci95": [float("nan"), float("nan")], "n": n, "sd": float("nan")}
    sd = float(x.std(ddof=1))
    half = float(t.ppf(0.5 + level / 2, n - 1)) * sd / math.sqrt(n)
    return {"mean": m, "ci95": [m - half, m + half], "n": n, "sd": sd}


def two_level_delta(seed_boots: np.ndarray, ref_boot: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Bootstrap of mean over seeds of (spread(seed) - spread(reference)).

    seed_boots: S x R, each seed's spread in R replicates that resample its drawings; ref_boot: R replicates of
    the reference's spread (resampling its drawings). Each replicate also resamples the seeds."""
    s, r = seed_boots.shape
    pick = rng.integers(0, s, (r, s))
    return seed_boots[pick, np.arange(r)[:, None]].mean(1) - ref_boot


def verdict(t_ci: list[float], boot_ci: list[float]) -> str:
    """The plan's rule: 'narrower' if both CIs lie below 0, 'wider' if both lie above, otherwise 'null'."""
    if t_ci[1] < 0 and boot_ci[1] < 0:
        return "narrower"
    if t_ci[0] > 0 and boot_ci[0] > 0:
        return "wider"
    return "null"


def log_x(step: float, offset: float = 25.0) -> float:
    """Position of a training step on the charts' log axis (step 0 is shown, offset by 25)."""
    return math.log10(step + offset)

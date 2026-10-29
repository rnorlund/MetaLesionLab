"""Watch an AI forget what a chair is: the mirror image of "Watch an AI learn" (docs/plato_sketch_forget_plan.md).

The larger Sketch-RNN of "Watch an AI learn" (plato_sketch.MODELS["big"]: LSTM 2,048, all 203,324 recognized
Quick, Draw! chairs, 102,400 steps, seeds 1-4) is damaged step by step at its last checkpoint, with reversible
forward hooks and never an edit to its weights:

- **silence** (primary): a growing share of the LSTM's 2,048 hidden units is switched off (their output h is set
  to 0 at every time step, on the way to the mixture head and back into the recurrence). The units go in a random
  order fixed per seed, so the doses are nested: every unit off at 20% is also off at 30%.
- **noise**: Gaussian noise is added to every unit's output h at every time step, scaled to that unit's standard
  deviation while it reads people's chairs; the noise draws are fixed per seed (only their size changes).
- **readout** (exploratory): the same nested units are cut off from the mixture head only; they still take part in
  the recurrence. Is the damage in the memory or in the hand?

At every dose it draws 200 drawings at temperatures 1.0 and 0.4 from the same fixed noise as the learning run
(plato_sketch.make_noise), so drawing i at every dose and at every training step starts from the same random
numbers. This module holds the pure parts: the design, the doses, the unit orders, and the measures and statistics
for the plan's three questions. The hooks, sampling and embedding are in scripts/plato_sketch_forget.py.
"""
from __future__ import annotations

import math

import numpy as np

from metalesionlab.plato_sketch import BIG, BOOT_SEED, MODELS

HIDDEN = BIG["hidden"]
STEP = MODELS["big"]["steps"][-1]  # 102,400: the fully trained model
SEEDS = [1, 2, 3, 4]
TEST_SEEDS = [2, 3, 4]     # as in the learning test: seed 1 is the display run (and was the learning pilot)
DISPLAY = {"seed": 1, "temp": 0.4, "n": 16, "arm": "silence"}  # the animation: as "Watch an AI learn"
TEMPS = [1.0, 0.4]
PRIMARY_TEMP = 1.0
N_SAMPLES = 200
# Doses. The primary grid is 0-90% switched off, in steps of 10; 95% and 100% extend it to the end of the road.
SILENCE = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
PRIMARY_DOSES = SILENCE[1:10]  # 10-90%: the doses the path tests average over
# Noise: its standard deviation as a multiple of each unit's own standard deviation (fixed before any damage was run)
NOISE = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
ARMS = {"silence": SILENCE, "noise": NOISE, "readout": SILENCE}
PRIMARY_ARM = "silence"
# Added after the planned run had shown that most of the change happens by 10% (exploratory, not in any test): finer
# silencing doses for the page's animation and curves. DISPLAY_DOSES are the animation's 16 frames.
EXTRA_SILENCE = [0.02, 0.04, 0.06, 0.08]
DISPLAY_DOSES = sorted(SILENCE + EXTRA_SILENCE)
MARGIN = 0.03  # Q1's equivalence margin, in cosine distance (about a tenth of the learning path's fall, 0.51 -> 0.20)
# Q3's two scales: ink maps of the ink-cropped 256-px render, area-averaged and blurred by 1 pixel
COARSE, FINE = 16, 64
UNIT_ORDER_KEY = 13   # np.random.default_rng([seed, 13]): the order in which units are switched off
UNIT_NOISE_KEY = 11   # torch.Generator seed seed * 1000 + 11: the noise added to the units


def path_doses(arm: str) -> list[float]:
    """The damaged doses the tests use: 10-90% for switching units off (silence, readout); every nonzero noise level."""
    return list(PRIMARY_DOSES) if arm in ("silence", "readout") else [x for x in ARMS[arm] if x > 0]


def set_name(arm: str, dose: float, temp: float) -> str:
    """'silence_d0.30_t1.0'."""
    return f"{arm}_d{dose:.2f}_t{temp:.1f}"


def parse_set_name(stem: str) -> tuple[str, float, float]:
    arm, d, t = stem.split("_")
    return arm, float(d[1:]), float(t[1:])


def run_name(seed: int) -> str:
    return f"forget_s{seed}"


# ---------- which units ----------

def unit_order(seed: int, hidden: int = HIDDEN) -> np.ndarray:
    """The order in which this seed's units are switched off (a random permutation, fixed per seed)."""
    return np.random.default_rng([seed, UNIT_ORDER_KEY]).permutation(hidden)


def n_off(dose: float, hidden: int = HIDDEN) -> int:
    return int(round(dose * hidden))


def keep_mask(order: np.ndarray, dose: float) -> np.ndarray:
    """1 for a unit that still works, 0 for one switched off: the first round(dose x hidden) units of the order."""
    m = np.ones(len(order), np.float32)
    m[order[:n_off(dose, len(order))]] = 0
    return m


# ---------- measures ----------

def ink_maps(img, coarse: int = COARSE, fine: int = FINE) -> tuple[np.ndarray, np.ndarray]:
    """A rendered drawing (PIL, white paper, black ink) as two ink maps, 1 = ink: coarse x coarse, where only the
    overall shape survives, and fine x fine, where single lines (a back's slats, a seat's edge) still show. Each is
    area-averaged from the render, then blurred by one pixel so a line a pixel off still overlaps."""
    from PIL import Image
    from scipy.ndimage import gaussian_filter

    g = img.convert("L")
    out = []
    for side in (coarse, fine):
        a = 1.0 - np.asarray(g.resize((side, side), Image.BOX), np.float32) / 255.0
        out.append(gaussian_filter(a, 1.0, mode="constant").astype(np.float32))
    return out[0], out[1]


def _centered_unit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, np.float64).reshape(len(x), -1)
    x = x - x.mean(1, keepdims=True)
    n = np.linalg.norm(x, axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, x / n, np.nan)


def nearest_person(maps: np.ndarray, ref_maps: np.ndarray) -> np.ndarray:
    """For each drawing's ink map, its correlation with the most similar of the people's chairs (ref_maps)."""
    if len(maps) == 0:
        return np.zeros(0)
    a, b = _centered_unit(maps), _centered_unit(ref_maps)
    b = b[~np.isnan(b).any(1)]
    return np.nanmax(a @ b.T, axis=1)


def kept_share(value, untrained, intact):
    """How much of what training built is still there: 1 = as the fully trained model, 0 = as the untrained one."""
    return (np.asarray(value, float) - untrained) / (intact - untrained)


def learn_interp(learn_x: np.ndarray, learn_y: np.ndarray, x) -> np.ndarray:
    """The learning path's y at recognizability x: linear interpolation over its checkpoints sorted by x (ties
    averaged); NaN outside the learning path's range, so nothing is extrapolated."""
    lx, ly = np.asarray(learn_x, float), np.asarray(learn_y, float)
    ok = ~(np.isnan(lx) | np.isnan(ly))
    lx, ly = lx[ok], ly[ok]
    ux = np.unique(lx)
    uy = np.array([ly[lx == v].mean() for v in ux])
    x = np.asarray(x, float)
    y = np.interp(x, ux, uy)
    return np.where((x < ux[0]) | (x > ux[-1]) | np.isnan(x), np.nan, y)


def path_gap(learn_r, learn_y, dam_r, dam_y) -> tuple[float, np.ndarray]:
    """Q1: at the same recognizability, how far the damaged model's measure (distance to the adult chair, or
    variety) sits from the learning path's. Returns the mean over the damage doses inside the learning path's
    range (NaN if none) and each dose's gap."""
    gaps = np.asarray(dam_y, float) - learn_interp(learn_r, learn_y, dam_r)
    return (float(np.nanmean(gaps)) if np.isfinite(gaps).any() else float("nan")), gaps


def nearest_step(learn_r, learn_d, steps, r, d) -> int:
    """The training step whose (recognizable, distance) point is nearest, each axis scaled by the learning path's
    range: 'this much damage looks like step k of learning'."""
    lr, ld = np.asarray(learn_r, float), np.asarray(learn_d, float)
    sr, sd = np.nanmax(lr) - np.nanmin(lr), np.nanmax(ld) - np.nanmin(ld)
    dist = np.hypot((lr - r) / sr, (ld - d) / sd)
    return int(steps[int(np.nanargmin(dist))])


def half_forgotten(doses, recog, intact: float, untrained: float, last: float = PRIMARY_DOSES[-1]) -> float:
    """The plan's primary dose for Q2 and Q3, chosen from recognizability alone: the smallest dose (10-90%) at which
    recognizability has fallen at least halfway from the fully trained model's to the untrained model's; 90% if
    it never does."""
    mid = (intact + untrained) / 2
    for dose, r in zip(doses, recog):
        if 0 < dose <= last and r is not None and not math.isnan(r) and r <= mid:
            return float(dose)
    return float(last)


def gap_verdict(t_ci, boot_ci, margin: float = MARGIN) -> str:
    """Q1's rule: 'retraces' if both 95% CIs lie inside +/- margin; 'further' or 'closer' if both lie on one side of
    0 and are not inside the margin; otherwise 'unclear'."""
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in (*t_ci, *boot_ci)):
        return "unclear"
    if -margin <= min(t_ci[0], boot_ci[0]) and max(t_ci[1], boot_ci[1]) <= margin:
        return "retraces"
    if t_ci[0] > 0 and boot_ci[0] > 0:
        return "further"
    if t_ci[1] < 0 and boot_ci[1] < 0:
        return "closer"
    return "unclear"


def sign_verdict(t_ci, boot_ci, up: str, down: str, none: str) -> str:
    """Both CIs above 0 -> up; both below -> down; otherwise none."""
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in (*t_ci, *boot_ci)):
        return none
    if t_ci[0] > 0 and boot_ci[0] > 0:
        return up
    if t_ci[1] < 0 and boot_ci[1] < 0:
        return down
    return none


def boot_means(values: np.ndarray, counts: np.ndarray) -> np.ndarray:
    """Bootstrap means of per-drawing values from resampling counts (reps x n)."""
    return counts @ np.asarray(values, float) / counts.sum(1)


def boot_rng() -> np.random.Generator:
    return np.random.default_rng([BOOT_SEED, 7])

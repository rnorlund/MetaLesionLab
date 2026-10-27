"""The life of a chair: do children's drawings, and an image model's training stages, converge on a prototype?

Children: Long, Fan, Huey, Chai & Frank (2024), Nature Communications 15:1191, kiddraw museum-kiosk drawings
(OSF 10.17605/OSF.IO/QYMJR; the data repository is CC BY-NC-SA 4.0). We use derived, group-level statistics
only; no child's drawing is shown or committed. Adults: Google Quick, Draw! (CC BY 4.0). AI: Stable Diffusion
v1.1 to v1.5 (CreativeML OpenRAIL-M), same prompt and seeds at every checkpoint. Plan: docs/plato_lifespan_plan.md.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np

from metalesionlab.plato import CONCEPTS

LIFESPAN_DIR = Path(os.environ.get("PLATO_LIFESPAN_DIR",
                                   "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/lifespan"))
KIDDRAW_CREDIT = ("Children's drawings: Long, Fan, Huey, Chai & Frank (2024), Parallel developmental changes in "
                  "children's production and recognition of line drawings of visual concepts, Nature Communications "
                  "15:1191, https://doi.org/10.1038/s41467-023-44529-9; data at https://osf.io/qymjr/ and "
                  "https://github.com/brialorelle/drawing_production_and_recognition (CC BY-NC-SA 4.0). Derived "
                  "group-level statistics only; no drawings are reproduced.")
SD_CREDIT = ("Stable Diffusion v1.1-v1.4 (CompVis) and v1.5 (stable-diffusion-v1-5 mirror of the RunwayML release), "
             "CreativeML OpenRAIL-M")

# kiddraw category -> our concept key (plato.CONCEPTS). Lamp (ours: floor lamp) and person (ours: yoga) are left out.
KIDDRAW_TO_KEY = {"chair": "chair", "boat": "sailboat", "face": "face", "house": "house", "cat": "cat", "cup": "cup",
                  "tree": "tree", "car": "car", "key": "key", "bike": "bicycle", "snail": "snail", "cactus": "cactus",
                  "bird": "bird", "fish": "fish", "dog": "dog", "hat": "hat", "clock": "clock", "book": "book",
                  "apple": "apple", "scissors": "scissors"}
KEY_TO_KIDDRAW = {v: k for k, v in KIDDRAW_TO_KEY.items()}
APPROXIMATE = {"sailboat"}  # children were asked for "a boat"
SHARED_KEYS = [c.key for c in CONCEPTS if c.key in KEY_TO_KIDDRAW]          # the 20 things, in priority order
TIER1_KEYS = [c.key for c in CONCEPTS if c.tier == 1]                       # the AI arm's primary 10
AI_KEYS = TIER1_KEYS + [k for k in SHARED_KEYS if k not in TIER1_KEYS]      # 21 things: primary first
CANDIDATES = SHARED_KEYS + ["umbrella"]                                     # recognizability: 21 prototypes
AGES = list(range(2, 11))

# (name, Hugging Face repo, cumulative training steps in thousands, parent); from the model cards
CHECKPOINTS = [
    ("v1.1", "CompVis/stable-diffusion-v1-1", 431, None),
    ("v1.2", "CompVis/stable-diffusion-v1-2", 946, "v1.1"),
    ("v1.3", "CompVis/stable-diffusion-v1-3", 1141, "v1.2"),
    ("v1.4", "CompVis/stable-diffusion-v1-4", 1171, "v1.2"),
    ("v1.5", "stable-diffusion-v1-5/stable-diffusion-v1-5", 1541, "v1.2"),
]
SD_NEGATIVE = "shading, photo, photorealistic, paper texture, 3d render, color, text"
SD_SEED_BASE = 20261027


def sd_seed(key: str, i: int) -> int:
    """Picture i of a thing gets the same seed (so the same starting noise) at every checkpoint."""
    return SD_SEED_BASE + 1000 * [c.key for c in CONCEPTS].index(key) + i


# ---------- children's strokes -> Quick, Draw! format ----------

_TOKEN = re.compile(r"[MmLlHhVvZz]|-?\d*\.?\d+(?:e-?\d+)?")


def parse_svg_path(d: str) -> list[tuple[float, float]]:
    """Absolute points of one stroke, from a paper.js SVG path ('M x,y l dx,dy v dy h dx ...').

    Supports M/m, L/l, H/h, V/v and Z/z (all the kiddraw strokes use only M, l, v and h); implicit repeats
    of the last command are allowed, as in 'l1,2 3,4'."""
    toks = _TOKEN.findall(d)
    pts: list[tuple[float, float]] = []
    x = y = 0.0
    cmd = None
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz" and pts:
                pts.append(pts[0])
            continue
        if cmd is None:
            raise ValueError(f"path starts with a number: {d[:40]!r}")
        if cmd in "MmLl":
            dx, dy = float(toks[i]), float(toks[i + 1])
            i += 2
            if cmd in "ml" and pts:
                x, y = x + dx, y + dy
            else:
                x, y = dx, dy
            if cmd == "M":
                cmd = "L"  # implicit repeats after a moveto are linetos
            elif cmd == "m":
                cmd = "l"
        elif cmd in "Hh":
            v = float(t)
            i += 1
            x = x + v if cmd == "h" else v
        elif cmd in "Vv":
            v = float(t)
            i += 1
            y = y + v if cmd == "v" else v
        else:
            raise ValueError(f"unsupported path command {cmd!r}")
        pts.append((x, y))
    return pts


def parse_svgs(field: str) -> list[list[tuple[float, float]]]:
    """The kiddraw 'svgs' column: a Python-2 style list of path strings ([u'M..', u'M..'])."""
    return [parse_svg_path(p) for p in re.findall(r"u?'([^']*)'", field)]


def rdp(points: np.ndarray, eps: float) -> np.ndarray:
    """Ramer-Douglas-Peucker simplification of a polyline (n x 2); keeps the end points."""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    seg = end - start
    norm = np.hypot(*seg)
    if norm == 0:
        dists = np.hypot(*(points - start).T)
    else:
        dists = np.abs(seg[0] * (points[:, 1] - start[1]) - seg[1] * (points[:, 0] - start[0])) / norm
    i = int(np.argmax(dists))
    if dists[i] > eps:
        left = rdp(points[: i + 1], eps)
        right = rdp(points[i:], eps)
        return np.vstack([left[:-1], right])
    return np.vstack([start, end])


def resample(points: np.ndarray, spacing: float = 1.0) -> np.ndarray:
    """Points every `spacing` px along a polyline (the start, the end and every vertex in between are kept
    implicitly by linear interpolation along arc length)."""
    if len(points) < 2:
        return points
    seglen = np.hypot(*np.diff(points, axis=0).T)
    s = np.concatenate([[0], np.cumsum(seglen)])
    if s[-1] == 0:
        return points[:1]
    t = np.append(np.arange(0, s[-1], spacing), s[-1])
    return np.column_stack([np.interp(t, s, points[:, 0]), np.interp(t, s, points[:, 1])])


KIDDRAW_CANVAS = 810.0  # px; the released 150 px PNGs are the canvas scaled by 1/5.40 (fitted on 4 categories)


def clip_strokes(strokes: list[list[tuple[float, float]]], lo: float = 0.0, hi: float = KIDDRAW_CANVAS,
                 spacing: float = 2.0) -> list[list[tuple[float, float]]]:
    """Keep only the parts of each stroke inside the visible canvas [lo, hi]^2, as the child saw it.

    Strokes are resampled every `spacing` px first, so a stroke that leaves and re-enters the canvas is
    split into separate pieces at the edge."""
    out = []
    for s in strokes:
        p = resample(np.asarray(s, float), spacing) if len(s) > 1 else np.asarray(s, float)
        if not len(p):
            continue
        inside = np.all((p >= lo) & (p <= hi), axis=1)
        run: list[tuple[float, float]] = []
        for pt, ok in zip(p, inside):
            if ok:
                run.append((float(pt[0]), float(pt[1])))
            elif run:
                out.append(run)
                run = []
        if run:
            out.append(run)
    return out


def to_quickdraw(strokes: list[list[tuple[float, float]]], eps: float = 2.0) -> list:
    """Quick, Draw!'s simplification: align to the top-left (min 0), scale uniformly to a maximum of 255,
    resample at 1 px, Ramer-Douglas-Peucker with epsilon 2.0. Returns [[xs], [ys]] per stroke, as integers."""
    strokes = [np.asarray(s, float) for s in strokes if len(s)]
    if not strokes:
        return []
    allp = np.vstack(strokes)
    lo = allp.min(0)
    extent = float((allp.max(0) - lo).max())
    scale = 255.0 / extent if extent > 0 else 1.0
    out = []
    for s in strokes:
        p = rdp(resample((s - lo) * scale, 1.0), eps)
        p = np.clip(np.round(p), 0, 255).astype(int)
        out.append([p[:, 0].tolist(), p[:, 1].tolist()])
    return out


def kiddraw_name(filename: str) -> tuple[str, int, str]:
    """('chair', 8, 'cdm_run_v31527960931784') from 'chair_sketch_age8_cdm_run_v3...png' (with or without a
    folder and an article: 'sketches_full_dataset/a chair_sketch_age8_...png')."""
    stem = Path(filename).name.removesuffix(".png")
    m = re.match(r"^(?:an? )?(.+)_sketch_age(\d+)_(.+)$", stem)
    if not m:
        raise ValueError(f"not a kiddraw file name: {filename!r}")
    return m.group(1), int(m.group(2)), m.group(3)


# ---------- measures ----------

def unit(x: np.ndarray) -> np.ndarray:
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def prototype(x: np.ndarray) -> np.ndarray:
    """The normalized mean of unit vectors."""
    return unit(unit(x).mean(0))


def proto_distances(x: np.ndarray, proto: np.ndarray) -> np.ndarray:
    """Cosine distance of each vector to a prototype."""
    return 1.0 - unit(x) @ unit(proto)


def loo_proto_distances(x: np.ndarray) -> np.ndarray:
    """Each vector's cosine distance to the prototype of all the others (leave-one-out)."""
    u = unit(x)
    rest = u.sum(0, keepdims=True) - u
    return 1.0 - np.sum(u * unit(rest), axis=1)


def nearest(x: np.ndarray, protos: np.ndarray) -> np.ndarray:
    """Index of the most similar prototype for each vector (cosine)."""
    return np.argmax(unit(x) @ unit(protos).T, axis=1)


def recognized(x: np.ndarray, own: int, protos: np.ndarray, loo_own: np.ndarray | None = None) -> np.ndarray:
    """Whether each vector's most similar prototype is its own (index `own`). With `loo_own` (the vectors that
    built the own prototype), the own prototype is recomputed without the vector itself (leave-one-out)."""
    sims = unit(x) @ unit(protos).T
    if loo_own is not None:
        u = unit(loo_own)
        rest = unit(u.sum(0, keepdims=True) - u)
        sims[:, own] = np.sum(unit(x) * rest, axis=1)
    return np.argmax(sims, axis=1) == own


def matched_spread(d: np.ndarray, k: int = 16, reps: int = 200, rng: np.random.Generator | None = None) -> float:
    """Mean pairwise distance, averaged over `reps` random k-subsets (all pairs if n <= k)."""
    n = len(d)
    if n <= k:
        return float(d[np.triu_indices(n, 1)].mean())
    rng = rng or np.random.default_rng(0)
    iu = np.triu_indices(k, 1)
    vals = [d[np.ix_(idx, idx)][iu].mean() for idx in (rng.choice(n, k, replace=False) for _ in range(reps))]
    return float(np.mean(vals))


def weighted_spread(d: np.ndarray, counts: np.ndarray) -> float:
    """Spread of a bootstrap resample given by per-item counts; an item drawn twice is never paired with itself."""
    w = np.outer(counts, counts).astype(float)
    np.fill_diagonal(w, 0)
    return float((w * d).sum() / w.sum()) if w.sum() else float("nan")


def ols_slope(x, y) -> float:
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = ~np.isnan(y)
    x, y = x[ok], y[ok]
    if len(x) < 2:
        return float("nan")
    xc = x - x.mean()
    return float((xc * (y - y.mean())).sum() / (xc ** 2).sum())


def quad_fit(x, y, center: float = 6.0) -> tuple[float, float, float]:
    """y = a + b (x - center) + c (x - center)^2 by least squares; returns (a, b, c)."""
    x, y = np.asarray(x, float) - center, np.asarray(y, float)
    ok = ~np.isnan(y)
    c, b, a = np.polyfit(x[ok], y[ok], 2)
    return float(a), float(b), float(c)


def quad_peak(b: float, c: float, center: float = 6.0) -> float:
    """x of the vertex of a + b u + c u^2 (u = x - center); nan if the curve is flat."""
    return float(center - b / (2 * c)) if c != 0 else float("nan")


def age_equivalent(value: float, ages, curve) -> float | str:
    """The age at which a (mostly monotone) group curve first reaches `value`, by linear interpolation between
    neighbouring ages. Below the first age's value: '<first'; above every value: '>last'. The curve is made
    monotone non-decreasing first (running maximum), so a dip doesn't create two answers."""
    ages = np.asarray(ages, float)
    c = np.maximum.accumulate(np.asarray(curve, float))
    if value < c[0]:
        return f"<{ages[0]:g}"
    if value > c[-1]:
        return f">{ages[-1]:g}"
    j = int(np.searchsorted(c, value, side="left"))
    if j == 0 or c[j] == c[j - 1]:
        return float(ages[j])
    return float(ages[j - 1] + (value - c[j - 1]) / (c[j] - c[j - 1]) * (ages[j] - ages[j - 1]))


def direction_cosines(a: dict[str, np.ndarray], b: dict[str, np.ndarray]) -> tuple[float, float]:
    """Mean cosine between paired displacement vectors (same thing in a and b), and the mean over mismatched
    pairs (different things): the null for 'they move the same way in embedding space'."""
    keys = [k for k in a if k in b]
    if len(keys) < 2:
        raise ValueError("need at least two shared things")
    A = unit(np.stack([a[k] for k in keys]))
    B = unit(np.stack([b[k] for k in keys]))
    m = A @ B.T
    off = ~np.eye(len(keys), dtype=bool)
    return float(np.diag(m).mean()), float(m[off].mean())

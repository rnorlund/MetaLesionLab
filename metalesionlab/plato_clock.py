"""The clock test (/plato/clock): Meta's Muse Image given the MoCA clock instruction, scored on the MoCA's three
clock points, beside the averages of 365 adults' clocks from the USC Aging Brain Cohort (docs/plato_clock_plan.md).

The pictures, readings and embeddings live outside the repository (CLOCK_DIR); scripts/plato_clock.py makes them and
exports the page's data (web/data/plato_clock.json) and the draw pad's clock reference (web/data/draw_clock.json).

The people's side comes only from the private analysis's public export (PUBLIC_DIR): group averages of at least 20
people and aggregate statistics. Nothing per person is read here, and validate_public refuses anything that looks
like it before it reaches the repository.
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import numpy as np

CLOCK_DIR = Path(os.environ.get("PLATO_CLOCK_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/clock"))
PUBLIC_DIR = Path(os.environ.get("ABC_CLOCK_PUBLIC",
                                 "/Users/super/Documents/Meta_Hacking_Challenge/abc_private/clock_analysis/public"))

# ---------- the prompts (fixed in the pre-registration) ----------

INSTRUCTION = "Draw a clock. Put in all the numbers and set the time to 10 past 11."  # the MoCA's words
STYLE = "Simple black pen drawing on white paper."
IMAGE_PROMPT = f"{INSTRUCTION} {STYLE}"
SVG_PROMPT = (f"{INSTRUCTION} Make it an SVG drawing: black lines and black text on a white background, 256 by 256 "
              "pixels, no colour fill. Output only the SVG code.")
N = 16
EVEN_AGES = [20 + 4 * i for i in range(N)]   # 20, 24, ..., 80: the persona ages when no decade shares are known


def persona_prompt(age: int) -> str:
    """The same prompt with one age in years in front, and no other trait."""
    return f"Drawn by a {int(age)}-year-old: {IMAGE_PROMPT}"


# ---------- money ----------

TAG = "plato_clock"     # ledger tag of every paid call in this study
BUDGET = 2.00           # USD, this study's hard cap (raised from 1.50 for the age personas)
SHARED_STOP = 70.0      # no new paid calls once the shared ledger passes this
SVG_MAX_TOKENS = 4096


def tag_spend(ledger: Path) -> float:
    """This study's spend so far: the ledger entries tagged TAG."""
    if not ledger.exists():
        return 0.0
    total = 0.0
    for line in ledger.read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            if e.get("tag") == TAG:
                total += e["usd"]
    return total


# ---------- the age personas ----------

def persona_ages(decades: list[dict] | None = None, n: int = N) -> tuple[list[int], str]:
    """The n persona ages and the rule used. With decades ([{"lo": 20, "hi": 29, "n": 41}, ...] from the export's
    stats.json), places are shared in proportion to each decade's n (largest remainder, at least one each) and spread
    evenly over each decade's range; without them, n evenly spaced ages from 20 to 80."""
    if not decades:
        return list(EVEN_AGES[:n]) if n == N else [round(20 + 60 * i / (n - 1)) for i in range(n)], "even"
    ds = [d for d in decades if d.get("n")]
    total = sum(d["n"] for d in ds)
    k = len(ds)
    if k > n:
        raise ValueError("more decades than places")
    # one place each, the rest by largest remainder of the proportional share
    extra = n - k
    raw = [extra * d["n"] / total for d in ds]
    base = [int(math.floor(r)) for r in raw]
    left = extra - sum(base)
    order = sorted(range(k), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:left]:
        base[i] += 1
    ages = []
    for d, b in zip(ds, base):
        places = b + 1
        lo, hi = int(d["lo"]), int(d["hi"])
        span = hi - lo + 1
        ages += [int(lo + math.floor((j + 0.5) * span / places)) for j in range(places)]
    return sorted(ages), "stratified"


# ---------- the MoCA's three clock points ----------

POINTS = ("contour", "numbers", "hands")
TARGET = (11, 2)    # 10 past 11: the hour hand at the 11, the minute hand at the 2
ADVERT = (10, 2)    # 10:10, the watch-advert time


def time_label(hands, hour_to, minute_to) -> str:
    """The time drawn, from where the hands point (hour numbers 1-12): '11:10', '10:10', 'swapped' (the long hand
    at 11 and the short one at 2 or 10), 'other' (another time, or more than two hands) or 'none' (fewer than two
    hands, or a hand that can't be read)."""
    try:
        hands = int(hands)
    except (TypeError, ValueError):
        hands = 0
    h, m = _num(hour_to), _num(minute_to)
    if hands < 2 or h is None or m is None:
        return "none"
    if hands > 2:
        return "other"
    if (h, m) == TARGET:
        return "11:10"
    if (h, m) == ADVERT:
        return "10:10"
    if (h, m) in ((2, 11), (2, 10)):
        return "swapped"
    return "other"


def _num(x) -> int | None:
    """An hour number 1-12 from a reader's answer (12 for 0), or None."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        m = re.search(r"\d+(\.\d+)?", str(x))
        if not m:
            return None
        v = float(m.group(0))
    if not math.isfinite(v):
        return None
    v = int(round(v)) % 12
    return v or 12


def spark_points(r: dict | None) -> dict:
    """The three points from Muse Spark's answer to plato_damage.CLOCK_RUBRIC (None: unreadable, every point 0).
    The checklist can't judge "clearly shorter" or "meeting near the centre", so its hands point only asks for exactly
    two hands with the shorter at 11 and the longer at 2."""
    if not r:
        return {"contour": False, "numbers": False, "hands": False, "total": 0, "time": "none", "read": False}
    try:
        n_num = int(r.get("numbers_count") or 0)
    except (TypeError, ValueError):
        n_num = 0
    try:
        hands = int(r.get("hands") or 0)
    except (TypeError, ValueError):
        hands = 0
    contour = bool(r.get("contour"))
    numbers = n_num == 12 and bool(r.get("numbers_in_order")) and not r.get("extra_or_wrong_numbers")
    t = time_label(hands, r.get("hour_hand_points_to"), r.get("minute_hand_points_to"))
    ok_hands = hands == 2 and t == "11:10"
    return {"contour": contour, "numbers": numbers, "hands": ok_hands,
            "total": int(contour) + int(numbers) + int(ok_hands), "time": t, "read": True}


EYE_KEYS = ("contour", "numbers", "hands", "hands_n", "hour_to", "minute_to", "note")


def eye_points(e: dict) -> dict:
    """One eye score ({contour, numbers, hands: bool, hands_n, hour_to, minute_to, note}) as points and a time."""
    for k in ("contour", "numbers", "hands"):
        if not isinstance(e.get(k), bool):
            raise ValueError(f"eye score needs a true/false {k}")
    t = time_label(e.get("hands_n"), e.get("hour_to"), e.get("minute_to"))
    if e["hands"] and t != "11:10":
        raise ValueError("the hands point needs the hands at 11 and 2")
    return {"contour": e["contour"], "numbers": e["numbers"], "hands": e["hands"],
            "total": int(e["contour"]) + int(e["numbers"]) + int(e["hands"]), "time": t}


# ---------- statistics ----------

def wilson(k: int, n: int, z: float = 1.959964) -> list[float]:
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0.0, mid - half), min(1.0, mid + half)]


def kappa(a: list[bool], b: list[bool]) -> float | None:
    """Cohen's kappa for two raters' yes/no calls; None when it is undefined (both say the same thing throughout)."""
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    n = len(a)
    if n == 0:
        return None
    po = float((a == b).mean())
    pa, pb = a.mean(), b.mean()
    pe = float(pa * pb + (1 - pa) * (1 - pb))
    if pe >= 1 - 1e-12:
        return None
    return (po - pe) / (1 - pe)


def agreement(eye: list[dict], spark: list[dict]) -> dict:
    """Per point: how many pictures the two scorers agree on, and Cohen's kappa; and on the time drawn."""
    out = {}
    for k in POINTS:
        a, b = [bool(e[k]) for e in eye], [bool(s[k]) for s in spark]
        out[k] = {"agree": int(sum(x == y for x, y in zip(a, b))), "n": len(a), "kappa": kappa(a, b)}
    out["time"] = {"agree": int(sum(e["time"] == s["time"] for e, s in zip(eye, spark))), "n": len(eye)}
    return out


def tally(scores: list[dict]) -> dict:
    """Counts of each point and of each time drawn, with Wilson CIs and the mean total."""
    n = len(scores)
    out = {"n": n}
    for k in POINTS:
        c = sum(bool(s[k]) for s in scores)
        out[k] = {"k": c, "n": n, "share": c / n if n else None, "ci95": wilson(c, n)}
    out["mean_total"] = float(np.mean([s["total"] for s in scores])) if n else None
    out["all_three"] = sum(s["total"] == 3 for s in scores)
    times: dict[str, int] = {}
    for s in scores:
        times[s["time"]] = times.get(s["time"], 0) + 1
    out["times"] = times
    return out


def fisher(k1: int, n1: int, k2: int, n2: int) -> float:
    from scipy.stats import fisher_exact

    return float(fisher_exact([[k1, n1 - k1], [k2, n2 - k2]]).pvalue)


def trend_verdict(ai: float, ai_ci: list[float], people: float) -> str:
    """How the AI's change across age compares with people's (the pre-registered rules)."""
    if ai_ci[0] <= 0 <= ai_ci[1]:
        return "no clear change"
    if people == 0 or (ai > 0) != (people > 0):
        return "contradicts"
    return "exaggerates" if abs(ai) > 2 * abs(people) else "matches"


# ---------- the people's measure: a clock centred and scaled on its face ----------
# The export's typical clock (drawing_pad_reference.json) was made from clocks prepared one way, so every picture
# compared with it is prepared the same way (face_normalise): find the ink, thin it to a 1-px skeleton, fit a circle
# to the face's outline, move and scale so the face's radius is 0.40 of a 256-px canvas, keep the ink within 1.25
# face radii, and redraw the skeleton about 3 px wide in black, anti-aliased. numpy and scipy only (the web image).

FACE_SIDE = 256
FACE_RADIUS = 0.40     # of the canvas side
FACE_KEEP = 1.25       # face radii of ink kept around the centre
FACE_WIDTH = 3.0       # px, the redrawn line
DISPLAY_SCALE = 0.3629  # the export's shared display scale for average images (bins.json): alpha = mean ink / this


def ink_mask(img, threshold: int = 200, max_side: int = 512) -> np.ndarray:
    """Dark ink as a boolean array, after flattening the paper (plato.flatten_paper); big pictures are shrunk first."""
    from PIL import Image

    from metalesionlab.plato import flatten_paper

    img = img.convert("L")
    if max(img.size) > max_side:
        k = max_side / max(img.size)
        img = img.resize((max(1, round(img.width * k)), max(1, round(img.height * k))), Image.LANCZOS)
    return np.asarray(flatten_paper(img)) < threshold


def thin(mask: np.ndarray, max_iter: int = 60) -> np.ndarray:
    """Zhang-Suen thinning: the ink as 1-px-wide lines."""
    img = np.pad(mask.astype(np.uint8), 1)
    for _ in range(max_iter):
        changed = False
        for step in (0, 1):
            p = img
            p2, p3, p4 = p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:]
            p5, p6, p7 = p[2:, 2:], p[2:, 1:-1], p[2:, :-2]
            p8, p9 = p[1:-1, :-2], p[:-2, :-2]
            nb = [p2, p3, p4, p5, p6, p7, p8, p9]
            b = sum(x.astype(np.int16) for x in nb)
            seq = nb + [p2]
            a = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.int16) for i in range(8))
            if step == 0:
                c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0)
            else:
                c = (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            kill = (p[1:-1, 1:-1] == 1) & (b >= 2) & (b <= 6) & (a == 1) & c
            if kill.any():
                img[1:-1, 1:-1][kill] = 0
                changed = True
        if not changed:
            break
    return img[1:-1, 1:-1].astype(bool)


def fit_face(skel: np.ndarray, tries: int = 1500) -> tuple[float, float, float]:
    """The clock face's circle (cx, cy, r) in pixels: the circle through three ink pixels with the most ink on it
    (RANSAC over `tries` seeded triples, radius between 0.2 and 0.62 of the drawing's size), then a least-squares fit
    to the ink near it. The face's outline is the longest circular line in a clock."""
    ys, xs = np.nonzero(skel)
    h, w = skel.shape
    if len(xs) < 20:
        return w / 2, h / 2, max(4.0, min(w, h) * 0.4)
    x, y = xs.astype(float), ys.astype(float)
    # the drawing's size from its middle 98% of ink, so a stray speck doesn't stretch the radii allowed
    span = max(np.percentile(x, 99) - np.percentile(x, 1), np.percentile(y, 99) - np.percentile(y, 1), 16.0)
    rng = np.random.default_rng(0)
    i, j, k = (rng.integers(0, len(x), tries) for _ in range(3))
    ax, ay, bx, by, qx, qy = x[i], y[i], x[j], y[j], x[k], y[k]
    den = 2 * (ax * (by - qy) + bx * (qy - ay) + qx * (ay - by))
    good = np.abs(den) > 1e-6
    den = np.where(good, den, 1.0)
    a2, b2, q2 = ax * ax + ay * ay, bx * bx + by * by, qx * qx + qy * qy
    ux = (a2 * (by - qy) + b2 * (qy - ay) + q2 * (ay - by)) / den
    uy = (a2 * (qx - bx) + b2 * (ax - qx) + q2 * (bx - ax)) / den
    ur = np.hypot(ax - ux, ay - uy)
    good &= (ur > 0.2 * span) & (ur < 0.62 * span)
    if not good.any():
        return float(np.median(x)), float(np.median(y)), float(span / 2)
    ux, uy, ur = ux[good], uy[good], ur[good]
    tol = np.maximum(2.0, 0.04 * ur)
    inliers = np.zeros(len(ux))
    for s in range(0, len(ux), 256):  # (candidates x ink) in blocks, to keep memory small
        d = np.hypot(x[None, :] - ux[s:s + 256, None], y[None, :] - uy[s:s + 256, None])
        inliers[s:s + 256] = (np.abs(d - ur[s:s + 256, None]) < tol[s:s + 256, None]).sum(1)
    cover = inliers / (2 * np.pi * ur)  # the share of the circle drawn: a long, closed line wins over a big sparse one
    b = int(np.argmax(inliers * np.sqrt(cover)))
    cx, cy, r = ux[b], uy[b], ur[b]
    d = np.hypot(xs - cx, ys - cy)
    near = np.abs(d - r) < max(3.0, 0.08 * r)
    if near.sum() >= 12:  # Kasa: x^2 + y^2 = 2a x + 2b y + c
        x, y = xs[near].astype(float), ys[near].astype(float)
        A = np.c_[2 * x, 2 * y, np.ones_like(x)]
        sol, *_ = np.linalg.lstsq(A, x * x + y * y, rcond=None)
        a, b, c = sol
        rr = float(np.sqrt(max(c + a * a + b * b, 1.0)))
        if 0.5 * r < rr < 1.5 * r:
            cx, cy, r = float(a), float(b), rr
    return float(cx), float(cy), float(r)


def face_normalise(img, side: int = FACE_SIDE, supersample: int = 4):
    """A clock picture prepared like the export's: centred on its face, the face 0.40 of the side in radius, ink kept
    within 1.25 face radii, the skeleton redrawn about 3 px wide in black. Returns an RGB PIL image."""
    from PIL import Image, ImageDraw

    skel = thin(ink_mask(img))
    cx, cy, r = fit_face(skel)
    k = FACE_RADIUS * side / r
    big = side * supersample
    out = Image.new("L", (big, big), 255)
    g = ImageDraw.Draw(out)
    keep = FACE_KEEP * r
    width = max(1, round(FACE_WIDTH * supersample))
    ys, xs = np.nonzero(skel)
    on = set(zip(ys.tolist(), xs.tolist()))

    def at(y, x):
        return ((x - cx) * k + side / 2) * supersample, ((y - cy) * k + side / 2) * supersample

    for y, x in on:
        if np.hypot(x - cx, y - cy) > keep:
            continue
        p = at(y, x)
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            q = (y + dy, x + dx)
            if q in on and np.hypot(q[1] - cx, q[0] - cy) <= keep:
                g.line((p, at(*q)), fill=0, width=width)
        rad = width / 2  # a round joint (and a lone pixel stays a dot)
        g.ellipse((p[0] - rad, p[1] - rad, p[0] + rad, p[1] + rad), fill=0)
    return out.resize((side, side), Image.LANCZOS).convert("RGB")


# ---------- the public export: nothing per person gets in ----------

# Keys that would carry a person: never allowed anywhere in what this module publishes.
PERSON_KEYS = re.compile(r"(^|_)(id|ids|pid|subject|subjects|participant|participants|dob|birth|birthday|name|names|"
                         r"date|dates|visit|mrn|record|records|vector|vectors|embedding|embeddings|per_person|"
                         r"individual|individuals|rows|people_list)($|_)", re.I)
DATE = re.compile(r"\b(19|20)\d\d[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b|"
                  r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/(19|20)?\d\d\b")
MAX_LIST = 64           # a list longer than this could be one value per person
MIN_GROUP = 20          # no group average or statistic from fewer people


def validate_public(obj, path: str = "$", allow_keys: set[str] | None = None) -> list[str]:
    """Problems with a structure meant to be public: keys that name a person or an ID, dates, long lists of numbers
    (one per person), and groups smaller than MIN_GROUP (any "n" below it). Empty when it is fine."""
    allow_keys = allow_keys or set()
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in allow_keys and PERSON_KEYS.search(str(k)):
                out.append(f"{path}.{k}: key looks per person")
            if k in ("n", "n_people") and isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < MIN_GROUP:
                out.append(f"{path}.{k}: a group of {v} (under {MIN_GROUP})")
            out += validate_public(v, f"{path}.{k}", allow_keys)
    elif isinstance(obj, list):
        if len(obj) > MAX_LIST and all(isinstance(x, (int, float)) for x in obj):
            out.append(f"{path}: a list of {len(obj)} numbers")
        for i, x in enumerate(obj):
            out += validate_public(x, f"{path}[{i}]", allow_keys)
    elif isinstance(obj, str) and DATE.search(obj):
        out.append(f"{path}: looks like a date")
    return out


def load_public(folder: Path | None = None) -> dict | None:
    """stats.json from the public export, or None if the export isn't there yet."""
    p = (folder or PUBLIC_DIR) / "stats.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text())

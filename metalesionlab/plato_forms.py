"""Plato's Forms: two follow-ups to Plato's Chair (docs/plato_forms.md, plan in docs/plato_forms_plan.md).

1. The Platonic clock. Image generators are widely reported to draw clocks at about 10:10, the time on
   watch adverts, whatever time is asked for. We ask Muse Image and Stable Diffusion XL for clocks with
   and without a time, read every clock's hands with Muse Spark (validated on clocks drawn by code with
   known times), and compare with the clocks people draw in Google Quick, Draw!.
2. Plato's own examples. Republic X uses the bed and the table, not the chair. We run the core
   Plato's Chair pipeline for both and place them among the 35 core concepts, without touching the
   core list (plato.CONCEPTS) or its results: they live in FORMS_CONCEPTS and in their own folder.

Time conventions. A reading is (hour 1-12, minute 0-59). On the dial, hands are given in hour marks
from 12 (0 <= mark < 12): the 3 is mark 3, the minute hand at 10 minutes points at mark 2. Times are
compared on the 12-hour dial, in minutes (720 per turn), as circular distances.
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

from metalesionlab.plato import STYLES, PlatoConcept

FORMS_DIR = Path(os.environ.get("PLATO_FORMS_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/forms"))
BUDGET = 5.0        # this experiment's own cap (USD), in FORMS_DIR/spend.jsonl
SHARED_STOP = 70.0  # no new paid calls once the shared ledger (MLL_LEDGER) passes this


def my_spend(log: Path | None = None) -> float:
    """This experiment's spend so far: reservations, refunds and actual chat costs in spend.jsonl."""
    log = log or FORMS_DIR / "spend.jsonl"
    if not log.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in log.read_text().splitlines() if line.strip())


def log_spend(log: Path | None = None, **entry) -> None:
    import time

    log = log or FORMS_DIR / "spend.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(json.dumps({"ts": round(time.time(), 1), **entry}) + "\n")

# ---------- the Platonic clock ----------

TEN_TEN = (10, 10)
WINDOW = 10  # minutes either side of 10:10 that count as "about 10:10"
CORRECT = 5  # a requested time counts as drawn correctly within this many minutes
# Twelve requested times: each hour 1-12 once and each five-minute mark once; none is within 25 minutes
# of 10:10, with the hands either way round (9:45 is the closest).
CLOCK_TIMES = ["1:20", "2:35", "3:00", "4:55", "5:10", "6:30", "7:50", "8:15", "9:45", "10:40", "11:05", "12:25"]
PHOTO_TIMES = ["1:20", "3:00", "4:55", "6:30", "9:45", "10:40"]  # the realistic-style subset
PER_TIME = 8          # pictures per requested time and generator
PER_DEFAULT = 16      # pictures of "a clock" with no time, per style and generator
CLOCK_STYLES = ("doodle", "photo")
DEFAULT = "any"       # folder slug of the no-time condition


def clock_prompt(style: str, time: str | None = None) -> str:
    """The image prompt. Doodle: the core doodle template ("a clock" is exactly the core prompt).
    Photo: "A photo of a wall clock showing 3:00." """
    if style == "doodle":
        return STYLES["doodle"].format(phrase="a clock" if time is None else f"a simple clock face showing {time}")
    if style == "photo":
        return "A photo of a wall clock." if time is None else f"A photo of a wall clock showing {time}."
    raise ValueError(f"unknown clock style {style!r}")


def slug(time: str | None) -> str:
    """Folder name of a condition: 'any' for no time, 't0120' for 1:20."""
    if time is None:
        return DEFAULT
    h, m = parse_time(time)
    return f"t{h:02d}{m:02d}"


def unslug(s: str) -> str | None:
    if s == DEFAULT:
        return None
    return f"{int(s[1:3])}:{s[3:5]}"


def parse_time(text) -> tuple[int, int] | None:
    """'10:10', '3:05', '12:00', '0:15' (as 12:15), '10.10' -> (hour 1-12, minute 0-59); None if not a time."""
    if text is None:
        return None
    m = re.fullmatch(r"\s*(\d{1,2})\s*[:.h]\s*(\d{1,2})\s*", str(text))
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 24 and 0 <= mi <= 59):
        return None
    h %= 12
    return (h or 12, mi)


def fmt_time(t: tuple[int, int] | None) -> str | None:
    return None if t is None else f"{t[0]}:{t[1]:02d}"


def dial_minutes(h: int, m: float) -> float:
    """Minutes past 12 on the 12-hour dial (0 <= x < 720)."""
    return ((h % 12) * 60 + m) % 720


def dial_distance(a: float, b: float, period: float = 720) -> float:
    """Circular distance between two dial positions (minutes on the 12-hour dial by default)."""
    d = abs(a - b) % period
    return min(d, period - d)


def hand_marks(h: int, m: float) -> tuple[float, float]:
    """Where the hands of h:m point, in hour marks from 12: (hour hand, minute hand)."""
    return ((h % 12) + m / 60) % 12, (m / 5) % 12


def time_from_hands(hour_mark: float, minute_mark: float) -> tuple[int, int]:
    """The time a clock shows with its hour hand at hour_mark and minute hand at minute_mark (hour marks).
    The minute comes from the minute hand; the hour is the one whose hour-hand position (hour + minute/60)
    is closest to the hour hand, so a hand drawn exactly on the 2 with the minute hand on the 10 reads 1:50."""
    m = round(5 * (minute_mark % 12)) % 60
    h = round((hour_mark % 12) - m / 60) % 12
    return (h or 12, m)


def swap_hands(h: int, m: int) -> tuple[int, int]:
    """The time read if the hour and minute hands are taken the other way round (10:10 -> 1:51)."""
    hour_mark, minute_mark = hand_marks(h, m)
    return time_from_hands(minute_mark, hour_mark)


def time_distance(read: tuple[int, int], target: tuple[int, int], either_order: bool = False) -> float:
    """Minutes between a read time and a target on the 12-hour dial; with either_order, the smaller of
    the reading and its hand-swapped twin."""
    d = dial_distance(dial_minutes(*read), dial_minutes(*target))
    if either_order:
        d = min(d, dial_distance(dial_minutes(*swap_hands(*read)), dial_minutes(*target)))
    return d


def is_ten_ten(t: tuple[int, int] | None, window: float = WINDOW) -> bool:
    """About 10:10: within `window` minutes of 10:10, with the hands either way round."""
    return t is not None and time_distance(t, TEN_TEN, either_order=True) <= window


def chance_ten_ten(window: float = WINDOW, hour_slack: bool = False) -> float:
    """Share of the 720 minute-times of the dial that count as about 10:10 (the chance level if drawn
    times were uniform on the dial); with hour_slack, the chance level of is_ten_ten_hour_slack."""
    test = is_ten_ten_hour_slack if hour_slack else is_ten_ten
    return sum(test(((x // 60) or 12, x % 60), window) for x in range(720)) / 720


# Post hoc (after the pre-registered spot check): on doodles, the reader often gives the hour one too high
# (or low) when the hour hand is drawn between two numbers, e.g. a 10:10 'V' read as 11:10. These versions
# allow the hour to be off by one and keep the minute strict. They are sensitivity checks, not the primary measure.

def with_hour(t: tuple[int, int], k: int) -> tuple[int, int]:
    """t with its hour moved by k (12-hour dial)."""
    h = (t[0] - 1 + k) % 12 + 1
    return (h, t[1])


def time_distance_hour_slack(read: tuple[int, int], target: tuple[int, int], either_order: bool = False) -> float:
    """time_distance allowing the read hour to be one off: min over hour shifts of -1, 0 and +1."""
    return min(time_distance(with_hour(read, k), target, either_order) for k in (-1, 0, 1))


def is_ten_ten_hour_slack(t: tuple[int, int] | None, window: float = WINDOW) -> bool:
    """About 10:10 if the read hour may be one off (so a 'V' read as 11:10 or 9:10 counts)."""
    return t is not None and any(is_ten_ten(with_hour(t, k), window) for k in (-1, 0, 1))


def wilson_ci(k: int, n: int, z: float = 1.959964) -> list[float]:
    """95% Wilson score interval for k successes in n."""
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0.0, mid - half), min(1.0, mid + half)]


# ---------- reading the hands (Muse Spark vision) ----------

READER_PROMPTS = {
    # v1: the time directly
    "v1": ("This picture shows a clock; it may be a rough sketch. Look only at its hands. Ignore any seconds "
           "hand. How many hands does it have, and what time do the hour hand (the shorter one) and the minute "
           "hand (the longer one) show? Read where the hands actually point, even if the time is unusual.\n"
           'Answer with JSON only: {"hands": <number of hands>, "time": "H:MM"}. Use "time": null if it has '
           "no hands or the time can't be read."),
    # v2: where each hand points first, then the time
    "v2": ("This picture shows a clock; it may be a rough sketch. Look only at its hands, not at what time a "
           "clock usually shows. Ignore any seconds hand.\n"
           "1. How many hands are there?\n"
           "2. For each hand, which number on a clock face does its tip point at? Use 1-12, with decimals for "
           "in-between directions (e.g. 2.5 is halfway between the 2 and the 3), even if the face has no numbers.\n"
           "3. Which hand is shorter (the hour hand)?\n"
           'Answer with JSON only: {"hands": <count>, "short_hand_points_to": <1-12 or null>, '
           '"long_hand_points_to": <1-12 or null>, "time": "H:MM" or null}. If the two hands look equally long, '
           "still give your best guess of which is the hour hand. Use nulls if it has no hands or they can't be read."),
}


def _json_object(text: str) -> dict | None:
    """The first {...} object in a model's answer (code fences and chatter allowed)."""
    if not text:
        return None
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I)
    for m in re.finditer(r"\{[^{}]*\}", s, flags=re.S):
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _mark(x) -> float | None:
    """A hand direction as an hour mark in [0, 12): 12 -> 0; None if missing or not a number."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not (0 <= v <= 12.99):
        return None
    return v % 12


def parse_reading(text: str) -> dict:
    """A reader answer -> {"status", "hands", "time", "time_said", "from_hands"}.

    status: "time" (a time was read), "no_hands" (fewer than two hands), "unreadable" (hands, no time),
    or "unparsed". time is (h, m): from the two hand directions when both are given (v2), else the stated
    time. time_said is the stated time; from_hands the time computed from the directions."""
    obj = _json_object(text)
    if obj is None:
        return {"status": "unparsed", "hands": None, "time": None, "time_said": None, "from_hands": None}
    hands = obj.get("hands")
    try:
        hands = int(hands) if hands is not None and not isinstance(hands, bool) else None
    except (TypeError, ValueError):
        hands = None
    said = parse_time(obj.get("time"))
    s, lng = _mark(obj.get("short_hand_points_to")), _mark(obj.get("long_hand_points_to"))
    from_hands = time_from_hands(s, lng) if s is not None and lng is not None else None
    t = from_hands or said
    if hands is not None and hands < 2 and t is None:
        status = "no_hands"
    elif t is None:
        status = "no_hands" if hands == 0 else "unreadable"
    else:
        status = "time"
    return {"status": status, "hands": hands, "time": t, "time_said": said, "from_hands": from_hands}


# ---------- validation clocks drawn by code ----------

def validation_set(seed: int = 20261027) -> list[dict]:
    """24 clocks with known times (8 in each of three styles) plus 4 with no hands.

    Times: 10:10 and its hand-swapped look-alike 1:50 (to check the reader finds a real 10:10), then 22
    distinct random five-minute times at least 30 minutes from both (to check it doesn't invent one)."""
    import random

    rng = random.Random(seed)
    pool = [(h, m) for h in range(1, 13) for m in range(0, 60, 5)
            if time_distance((h, m), TEN_TEN, either_order=True) >= 30]
    times = [(10, 10), (1, 50)] + rng.sample(pool, 22)
    rng.shuffle(times)
    styles = ["marker", "numbers", "scribble"]
    out = [{"id": f"v{i:02d}", "time": fmt_time(t), "style": styles[i % 3], "hands": 2, "seed": seed + i}
           for i, t in enumerate(times)]
    out += [{"id": f"n{i}", "time": None, "style": styles[i % 3], "hands": 0, "seed": seed + 100 + i} for i in range(4)]
    return out


def draw_test_clock(time: str | None, style: str = "marker", seed: int = 0, side: int = 512):
    """A clock face drawn by code: 'marker' (thick wobbly circle, 12 ticks), 'numbers' (circle with 12, 3,
    6, 9), 'scribble' (thin wobbly outline only, like a 20-second Quick, Draw! clock). The hour hand is
    about 55% of the minute hand's length. time None draws no hands."""
    import random

    from PIL import Image, ImageDraw, ImageFont

    rng = random.Random(seed)
    img = Image.new("RGB", (side, side), "white")
    d = ImageDraw.Draw(img)
    cx, cy = side / 2 + rng.uniform(-10, 10), side / 2 + rng.uniform(-10, 10)
    r = side * rng.uniform(0.36, 0.42)
    w = {"marker": 9, "numbers": 6, "scribble": 3}[style]
    wobble, phase = (0.035 if style != "numbers" else 0.01), rng.uniform(0, 6.3)
    pts = []
    for i in range(181):
        a = 2 * math.pi * i / 180
        rr = r * (1 + wobble * math.sin(3 * a + phase) + rng.uniform(-0.006, 0.006))
        pts.append((cx + rr * math.sin(a), cy - rr * math.cos(a) * (0.93 if style == "scribble" else 1)))
    d.line(pts, fill="black", width=w, joint="curve")
    if style == "marker":
        for k in range(12):
            a = 2 * math.pi * k / 12
            r0, r1 = r * 0.82, r * 0.93
            d.line([(cx + r0 * math.sin(a), cy - r0 * math.cos(a)), (cx + r1 * math.sin(a), cy - r1 * math.cos(a))],
                   fill="black", width=w - 3)
    if style == "numbers":
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", int(side * 0.08))
        except OSError:
            font = ImageFont.load_default()
        for k, label in ((0, "12"), (3, "3"), (6, "6"), (9, "9")):
            a = 2 * math.pi * k / 12
            d.text((cx + r * 0.78 * math.sin(a), cy - r * 0.78 * math.cos(a)), label, fill="black", font=font,
                   anchor="mm")
    if time is not None:
        h, m = parse_time(time)
        hour_mark, minute_mark = hand_marks(h, m)
        for mark, length, width in ((hour_mark, 0.48, w + 3), (minute_mark, 0.80, w)):
            a = 2 * math.pi * mark / 12 + rng.uniform(-0.02, 0.02)
            d.line([(cx, cy), (cx + r * length * math.sin(a), cy - r * length * math.cos(a))], fill="black",
                   width=width)
        d.ellipse((cx - w, cy - w, cx + w, cy + w), fill="black")
    return img


# ---------- Plato's own examples: the bed and the table ----------

REPUBLIC_X = ("Republic X (596b-597d): there is one Form of the bed, made by the god; the carpenter makes "
              "a bed by looking to it; the painter copies the carpenter's bed as it appears, a copy of a copy.")
FORMS_CONCEPTS = [
    PlatoConcept("bed", "bed", "bed", "a bed", 1, 16, "many-style artifact", "", "Plato's example, Republic X"),
    PlatoConcept("table", "table", "table", "a table", 1, 16, "many-style artifact", "",
                 "Plato's example, Republic X (beds and tables, 596b)"),
]
FORMS_BY_KEY = {c.key: c for c in FORMS_CONCEPTS}


def rank_among(value: float, others: list[float]) -> int:
    """1-based rank of value among others plus itself, 1 = smallest (ties count in value's favour)."""
    return 1 + sum(o < value for o in others)

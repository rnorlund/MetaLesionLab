"""Plato's Chair, damage: what happens to an AI's drawings when its "language part" is damaged?

Semantic dementia predicts that drawings lose their distinctive features and drift toward the
typical member of the category (Bozeat et al. 2003, "A duck with four legs"). Here the drawer is
Stable Diffusion XL: its two text encoders are the language part and its UNet is the drawing part.
Graded, reversible lesions (sdxl_lesions.py) hit one or the other, every picture keeps its seed
across damage levels, and DINOv2 measures whether a rocking chair turns back into the plain chair.

This module holds the plan (prompts, seeds, lesion families) and the pure measures; the GPU work is
scripts/plato_damage_sdxl.py and the analysis scripts/plato_damage_analyze.py. The neurology link is
an analogy about a model, not a claim about people.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

import numpy as np

from metalesionlab.plato import STYLES

NEGATIVE = "shading, photo, photorealistic, paper texture, 3d render, color, text"  # as in the SDXL comparison
SEED_BASE = 20261027

# Concept -> (plain phrase, named kinds). Chair is the main test; hat and bird check generality.
CONCEPT_KINDS = {
    "chair": ("a chair", ["a rocking chair", "an armchair", "an office chair", "a folding chair", "a high chair",
                          "a wheelchair", "a beanbag chair", "a throne"]),
    "hat": ("a hat", ["a top hat", "a baseball cap", "a cowboy hat"]),
    "bird": ("a bird", ["an owl", "a penguin", "a flamingo"]),
}
# Clock drawing: a generic instruction, not any clinical test's wording. 10:10 is the advertising
# time that image models are said to draw whatever time is asked for.
CLOCK_TIMES = ["3:00", "6:30", "8:45", "4:20", "1:55", "10:10"]


# The understanding arm uses the concepts whose named kinds intact Glimmer labeled reliably (at least
# half right) in the variety study (docs/plato.md, "Can you prompt it out of the Platonic chair?").
RELIABLE_KINDS = ["bench", "bicycle", "bird", "book", "cactus", "car", "chair", "clock", "cup", "dog", "face", "fish",
                  "floor_lamp", "flower", "guitar", "harp", "hat", "house", "saw", "shoe", "tree", "yoga"]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


@dataclass(frozen=True)
class DamagePrompt:
    key: str        # folder name, e.g. chair__rocking_chair or clock__3_00
    concept: str    # chair, hat, bird, clock
    kind: str       # the named kind ("a rocking chair"), "plain", or the clock time
    phrase: str     # what goes into the doodle template
    index: int      # position in ALL_PROMPTS; sets the seeds

    @property
    def prompt(self) -> str:
        return STYLES["doodle"].format(phrase=self.phrase)

    @property
    def is_plain(self) -> bool:
        return self.kind == "plain"


def _build() -> list[DamagePrompt]:
    out = []
    for concept, (plain, kinds) in CONCEPT_KINDS.items():
        out.append(DamagePrompt(f"{concept}__plain", concept, "plain", plain, len(out)))
        for k in kinds:
            out.append(DamagePrompt(f"{concept}__{slug(k.removeprefix('a ').removeprefix('an '))}", concept, k, k,
                                    len(out)))
    for t in CLOCK_TIMES:
        out.append(DamagePrompt(f"clock__{slug(t)}", "clock", t, clock_phrase(t), len(out)))
    return out


def clock_phrase(time: str) -> str:
    return f"a simple clock face showing {time}"


ALL_PROMPTS = _build()
BY_KEY = {p.key: p for p in ALL_PROMPTS}
KIND_PROMPTS = [p for p in ALL_PROMPTS if p.concept != "clock"]
CLOCK_PROMPTS = [p for p in ALL_PROMPTS if p.concept == "clock"]


def seed_for(prompt: DamagePrompt, i: int) -> int:
    """Seed of picture i of a prompt: the same in every damage condition (paired pictures), different
    across prompts (so two prompts never share a starting noise)."""
    return SEED_BASE + 1000 * prompt.index + i


# ---------- lesion families ----------
# Each family turns a dose into a DamageSpec dict (sdxl_lesions.DamageSpec.from_dict). The pilot set
# the dose ranges (docs/plato_damage_plan.md). Random units use one seed per family, so a higher dose
# keeps every unit a lower dose hit (cumulative damage).
FAMILIES = {
    "text-zero": {"site": "text", "method": "zero", "dose": "fraction", "seed": 1},
    "unet-zero": {"site": "unet", "method": "zero", "dose": "fraction", "seed": 2},
    "text-noise": {"site": "text", "method": "noise", "dose": "noise_scale", "seed": 3},
    "unet-noise": {"site": "unet", "method": "noise", "dose": "noise_scale", "seed": 4},
}
LANGUAGE_FAMILIES = ("text-zero", "text-noise", "text-spec", "text-spec-random")
DRAWING_FAMILIES = ("unet-zero", "unet-noise")


def family_spec(family: str, dose: float) -> dict:
    """A DamageSpec dict for one dose of a family (noise families hit every unit of the site)."""
    f = FAMILIES[family]
    d = {"site": f["site"], "method": f["method"], "seed": f["seed"], "name": condition_name(family, dose),
         "recipe": {"family": family, "dose": dose}}
    if f["dose"] == "fraction":
        d["fraction"] = float(dose)
    else:
        d["fraction"], d["noise_scale"] = 1.0, float(dose)
    return d


def condition_name(family: str, dose: float) -> str:
    return f"{family}@{dose:g}"


def parse_condition(name: str) -> tuple[str, float]:
    if name == "intact":
        return "intact", 0.0
    family, _, dose = name.partition("@")
    return family, float(dose)


# ---------- measures (embeddings are rows; cosine geometry on unit vectors) ----------

def unit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, float)
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def cos_dist(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise cosine distance between a (n, d) and b (n, d) or (d,)."""
    return 1.0 - (unit(a) * unit(b)).sum(-1)


def centroid(x: np.ndarray, leave_out: int | None = None) -> np.ndarray:
    """Mean of the unit vectors (optionally without row `leave_out`)."""
    u = unit(x)
    if leave_out is not None:
        u = np.delete(u, leave_out, axis=0)
    return u.mean(0)


def drift_measures(e: np.ndarray, e_intact: np.ndarray, kind_intact: np.ndarray, plain_intact: np.ndarray,
                   others: list[np.ndarray] | None = None) -> dict:
    """Per-picture measures for one prompt in one condition.

    e            (n, d) damaged pictures, row i = seed i
    e_intact     (n, d) the same seeds intact
    kind_intact  (n, d) intact pictures of this kind (the same rows as e_intact); its centroid leaves
                 out seed i when scoring picture i
    plain_intact (m, d) intact pictures of the plain prompt; their centroid is the prototype
    others       intact picture sets of the concept's other kinds (for the specificity check)

    Returns arrays of length n:
      d_intact   distance to the intact picture with the same seed (how much damage changed it)
      d_proto    distance to the plain prototype
      d_kind     distance to the kind's own intact centroid (leave-one-seed-out)
      drift      d_kind - d_proto: > 0 means nearer the plain prototype than its own kind
      tau        position on the line from the kind centroid (0) to the prototype (1)
      d_other    mean distance to the other kinds' centroids; drift_other = d_kind - d_other"""
    e, e_intact, kind_intact = (np.asarray(a, float) for a in (e, e_intact, kind_intact))
    n = len(e)
    proto = centroid(plain_intact)
    d_proto = cos_dist(e, proto)
    d_kind, tau = np.empty(n), np.empty(n)
    for i in range(n):
        k = centroid(kind_intact, leave_out=i if len(kind_intact) > 1 else None)
        d_kind[i] = cos_dist(e[i:i + 1], k)[0]
        axis = proto - k
        tau[i] = float((unit(e[i]) - k) @ axis / (axis @ axis)) if axis @ axis > 0 else np.nan
    out = {"d_intact": cos_dist(e, e_intact), "d_proto": d_proto, "d_kind": d_kind, "drift": d_kind - d_proto,
           "tau": tau}
    if others:
        d_other = np.mean([cos_dist(e, centroid(o)) for o in others], axis=0)
        out["d_other"], out["drift_other"] = d_other, d_kind - d_other
    return out


def boot_mean_ci(x: np.ndarray, reps: int = 4000, rng: np.random.Generator | None = None,
                 groups: np.ndarray | None = None) -> dict:
    """Mean with a percentile bootstrap CI. With `groups`, resample whole groups (e.g. a kind's seeds
    together), so pictures of one kind are not treated as independent."""
    rng = rng or np.random.default_rng(0)
    x = np.asarray(x, float)
    ok = ~np.isnan(x)
    x = x[ok]
    if not len(x):
        return {"mean": float("nan"), "ci95": [float("nan"), float("nan")], "n": 0}
    if groups is None:
        boots = np.array([x[rng.integers(0, len(x), len(x))].mean() for _ in range(reps)])
    else:
        g = np.asarray(groups)[ok]
        labels = np.unique(g)
        members = [np.flatnonzero(g == lab) for lab in labels]
        boots = np.empty(reps)
        for b in range(reps):
            pick = rng.integers(0, len(labels), len(labels))
            idx = np.concatenate([members[j] for j in pick])
            boots[b] = x[idx].mean()
    return {"mean": float(x.mean()), "ci95": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))],
            "n": int(len(x))}


def matched_doses(curves: dict[str, dict[float, float]], targets: list[float]) -> dict[str, list[float]]:
    """For each family's severity curve {dose: mean distance to intact} (monotone-ish), the dose that
    reaches each target severity, by linear interpolation on the sorted doses (clipped to the range)."""
    out = {}
    for fam, curve in curves.items():
        doses = np.array(sorted(curve))
        sev = np.maximum.accumulate(np.array([curve[d] for d in doses]))
        out[fam] = [float(np.interp(t, sev, doses)) if sev[-1] > sev[0] else float(doses[-1]) for t in targets]
    return out


def at_severity(sev, val, targets) -> np.ndarray:
    """A family's outcome at given severities: (severity, value) points per dose, with the intact
    point (0, 0) added for change scores, read off by linear interpolation along increasing severity
    (severity made monotone with a running maximum). Targets beyond the curve are clipped."""
    sev = np.maximum.accumulate(np.r_[0.0, np.asarray(sev, float)])
    val = np.r_[0.0, np.asarray(val, float)]
    return np.interp(np.asarray(targets, float), sev, val)


def matched_targets(sev_a, sev_b, quantiles=(0.25, 0.5, 0.75)) -> list[float]:
    """Severities both families reach: quantiles of [0, the smaller of the two maxima]."""
    top = min(float(np.max(sev_a)), float(np.max(sev_b)))
    return [q * top for q in quantiles]


def matched_contrast(sev_a, val_a, sev_b, val_b, targets) -> float:
    """Mean over target severities of family a's outcome minus family b's (each interpolated)."""
    return float(np.mean(at_severity(sev_a, val_a, targets) - at_severity(sev_b, val_b, targets)))


def boot_matched_contrast(d_a: np.ndarray, v_a: np.ndarray, d_b: np.ndarray, v_b: np.ndarray,
                          reps: int = 4000, rng: np.random.Generator | None = None,
                          groups: np.ndarray | None = None) -> dict:
    """Matched-severity contrast with a paired bootstrap. d_* and v_* are (units, doses) arrays of
    severity (distance to the intact twin) and outcome change for the same units (pictures) under two
    families. Units are resampled together (or whole groups of units, e.g. kinds); the target
    severities are fixed from the full sample."""
    rng = rng or np.random.default_rng(0)
    mean = lambda x, i: np.nanmean(x[i], axis=0)  # noqa: E731
    all_i = np.arange(len(d_a))
    targets = matched_targets(mean(d_a, all_i), mean(d_b, all_i))
    est = matched_contrast(mean(d_a, all_i), mean(v_a, all_i), mean(d_b, all_i), mean(v_b, all_i), targets)
    if groups is not None:
        labels = np.unique(groups)
        members = [np.flatnonzero(groups == g) for g in labels]
    boots = np.empty(reps)
    for b in range(reps):
        if groups is None:
            i = rng.integers(0, len(all_i), len(all_i))
        else:
            i = np.concatenate([members[j] for j in rng.integers(0, len(labels), len(labels))])
        boots[b] = matched_contrast(mean(d_a, i), mean(v_a, i), mean(d_b, i), mean(v_b, i), targets)
    return {"estimate": est, "ci95": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))],
            "targets": targets, "n_units": int(len(all_i))}


# ---------- drawing style (pixels of the raw picture) ----------

def style_metrics(rgb: np.ndarray) -> dict:
    """Simple pixel measures of "still a clean black-on-white doodle?" for an (h, w, 3) uint8 picture:
      colorfulness  Hasler & Suesstrunk (2003): sd and mean of the opponent channels rg and yb
                    (0 for pure grays; above ~15 is visibly colored)
      midtone       share of gray pixels (luma 60-200): shading, texture, gray paper
      ink           share of dark pixels (luma < 100)
      clean         share of pixels that are near white (> 200) or near black (< 60), i.e. 1 - midtone"""
    x = np.asarray(rgb, float)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    rg, yb = r - g, 0.5 * (r + g) - b
    colorful = float(np.hypot(rg.std(), yb.std()) + 0.3 * np.hypot(rg.mean(), yb.mean()))
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    mid = float(((luma >= 60) & (luma <= 200)).mean())
    return {"colorfulness": colorful, "midtone": mid, "ink": float((luma < 100).mean()), "clean": 1.0 - mid}


# ---------- kind labels (Glimmer) ----------

def kind_outcome(label: int, true_kind: int | None, n_kinds: int) -> str:
    """Code one labeler answer for a picture drawn as kind `true_kind` (None for the plain prompt).
    Options are the kinds (0..n_kinds-1), then plain (n_kinds), then can't tell (n_kinds + 1)."""
    if label == n_kinds + 1:
        return "cant_tell"
    if label == n_kinds:
        return "plain"
    if true_kind is None:
        return "specific"
    return "correct" if label == true_kind else "other_kind"


def outcome_shares(outcomes: list[str]) -> dict:
    n = len(outcomes)
    keys = ("correct", "plain", "other_kind", "cant_tell", "specific")
    out = {k: (sum(o == k for o in outcomes) / n if n else float("nan")) for k in keys}
    errors = [o for o in outcomes if o in ("plain", "other_kind", "cant_tell")]
    out["n"] = n
    out["plain_share_of_errors"] = (sum(o == "plain" for o in errors) / len(errors)) if errors else float("nan")
    return out


_CARRIER = re.compile(r"^(?:the\s+)?(?:object|item|thing|picture|drawing|image)(?:\s+(?:depicted|shown|drawn))?"
                      r"(?:\s+(?:in|of)\s+(?:this|the)\s+(?:picture|drawing|image))?\s+(?:is|shows|depicts)\b\s*"
                      r"(?:an?\s+|the\s+)?", re.I)


def clean_name(said: str | None) -> str:
    """A naming answer without a carrier phrase ("The object in this picture is a throne." -> "throne"),
    lowercased, punctuation stripped."""
    s = (said or "").strip()
    s = _CARRIER.sub("", s)
    s = re.sub(r"^(?:an?|the)\s+", "", s.strip(), flags=re.I)
    return re.sub(r"[^a-z0-9 -]", "", s.lower()).strip()


def code_name(said: str | None, basic: str, kind: str) -> str:
    """Code a one-word naming answer for a picture of `kind` ("a rocking chair") of concept `basic`
    ("chair"): "specific" if it uses a distinctive word of the kind (its first 5 letters), "basic" if
    it is just the concept's name, "empty" if nothing usable came out (a carrier phrase cut short),
    else "other"."""
    word = clean_name(said)
    if not word:
        return "empty"
    stop = {"a", "an", "the", basic, basic + "s"}
    distinct = [w for w in re.findall(r"[a-z]+", kind.lower()) if w not in stop and len(w) > 2]
    toks = re.findall(r"[a-z]+", word)
    if any(t[:5] == d[:5] for t in toks for d in distinct) or any(d in word.replace(" ", "") for d in distinct):
        return "specific"
    if toks and all(t in (basic, basic + "s") for t in toks):
        return "basic"
    return "other"


# Answers that name no object at all: the picture is read as a pattern, not a thing.
NO_OBJECT_WORDS = {"abstract", "pattern", "patterns", "illusion", "texture", "design", "qr", "noise", "lines", "line",
                   "scribble", "scribbles", "doodle", "sketch", "drawing", "art", "artwork", "image", "picture",
                   "optical", "mosaic", "camouflage", "static", "grayscale", "distorted", "blur", "blurry", "smudge",
                   "zigzag", "maze", "labyrinth", "fabric", "print", "geometric", "chaos", "mess", "shapes", "shape"}


def name_category(said: str | None, basic: str, kind: str) -> str:
    """What a damaged picture was named as: "kind" (the asked kind, or the concept itself for the
    plain prompt), "basic" (just the concept's name, for a named kind), "no_object" (a pattern word:
    abstract, texture, illusion ...), "other_object" (some other thing: car, bicycle, man ...), or
    "empty"."""
    code = code_name(said, basic, kind)
    if code == "empty":
        return "empty"
    if code == "specific" or (code == "basic" and kind == "plain"):
        return "kind"
    if code == "basic":
        return "basic"
    toks = set(re.findall(r"[a-z]+", clean_name(said)))
    return "no_object" if toks & NO_OBJECT_WORDS else "other_object"


# ---------- clock rubric (scored by Muse Spark vision) ----------

CLOCK_RUBRIC = (
    "This is a drawing someone made when asked to draw a simple clock face showing a given time. "
    "Score the drawing itself; do not guess what was intended. Reply with JSON only, with these keys:\n"
    '"is_clock": true if it is recognisably a clock or clock face,\n'
    '"contour": true if there is a closed outline (circle or other shape) around the face,\n'
    '"numbers_count": how many distinct hour numbers 1-12 are written on the face (0-12; count digits or '
    'Roman numerals, ignore tick marks),\n'
    '"numbers_in_order": true if the numbers that are present run clockwise in the right order and '
    'roughly the right places (12 at top, 3 right, 6 bottom, 9 left); false otherwise or if none,\n'
    '"extra_or_wrong_numbers": true if any number is repeated, larger than 12, or garbled,\n'
    '"hands": the number of clock hands drawn (0, 1, 2 or more),\n'
    '"hour_hand_points_to": the hour number (1-12) the SHORTER hand points to, or null,\n'
    '"minute_hand_points_to": the hour number (1-12) the LONGER hand points to, or null,\n'
    '"time_read": the time you read from the hands as "h:mm", or null if you cannot read one.'
)

CLOCK_KEYS = ("is_clock", "contour", "numbers_count", "numbers_in_order", "extra_or_wrong_numbers", "hands",
              "hour_hand_points_to", "minute_hand_points_to", "time_read")


def parse_clock_json(text: str) -> dict | None:
    """The rubric answer as a dict with every CLOCK_KEYS key (missing ones None), or None if there is
    no JSON object in the text."""
    m = re.search(r"\{.*\}", text or "", flags=re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    return {k: d.get(k) for k in CLOCK_KEYS}


def target_positions(time: str) -> tuple[int, int]:
    """The hour numbers the hour and minute hands should point at for 'h:mm' (hour hand to the hour
    it has passed, or the next one after 30 minutes; minute 0 -> 12)."""
    h, m = (int(x) for x in time.split(":"))
    minute_num = round(m / 5) % 12 or 12
    hour_num = h % 12 or 12
    if m > 30:
        hour_num = hour_num % 12 + 1
    return hour_num, minute_num


def _near(a, b, tol: int = 1) -> bool:
    if a is None or b is None:
        return False
    try:
        a, b = int(a), int(b)
    except (TypeError, ValueError):
        return False
    return min((a - b) % 12, (b - a) % 12) <= tol


def score_clock(r: dict | None, time: str) -> dict:
    """Binary features from one rubric answer for a clock asked to show `time`.
      clock, contour, all_numbers (12 numbers present), numbers_ok (12, in order, none extra),
      two_hands, time_ok (the short hand within one number of the target hour position and the long
      hand within one number of the target minute position), shows_1010 (hands at 10 and 2 in
      either order: the advertising pose), and total (0-5: contour + numbers_ok + two_hands + both
      hand placements; a simple sum, not a clinical scale)."""
    if r is None:
        return {k: None for k in ("clock", "contour", "all_numbers", "numbers_ok", "two_hands", "time_ok",
                                  "shows_1010", "total")}
    hour_t, min_t = target_positions(time)
    hands = r.get("hands")
    try:
        hands = int(hands)
    except (TypeError, ValueError):
        hands = 0
    try:
        n_num = int(r.get("numbers_count") or 0)
    except (TypeError, ValueError):
        n_num = 0
    hp, mp = r.get("hour_hand_points_to"), r.get("minute_hand_points_to")
    hour_ok, min_ok = _near(hp, hour_t), _near(mp, min_t)
    shows_1010 = (_near(hp, 10, 0) and _near(mp, 2, 0)) or (_near(hp, 2, 0) and _near(mp, 10, 0))
    numbers_ok = n_num == 12 and bool(r.get("numbers_in_order")) and not r.get("extra_or_wrong_numbers")
    out = {"clock": bool(r.get("is_clock")), "contour": bool(r.get("contour")), "all_numbers": n_num == 12,
           "numbers_ok": numbers_ok, "two_hands": hands == 2, "time_ok": hands == 2 and hour_ok and min_ok,
           "shows_1010": hands >= 2 and shows_1010}
    out["total"] = int(out["contour"]) + int(numbers_ok) + int(out["two_hands"]) + int(hands >= 1 and hour_ok) \
        + int(hands >= 2 and min_ok)
    return out


def plan_dict() -> dict:
    return {"prompts": [asdict(p) | {"prompt": p.prompt} for p in ALL_PROMPTS], "families": FAMILIES,
            "negative": NEGATIVE, "seed_base": SEED_BASE}

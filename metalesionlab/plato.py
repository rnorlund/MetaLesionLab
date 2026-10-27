"""Plato's Chair: how spread out is a concept in an AI's imagination, and in people's drawings?

Ask Muse Image for 16 chairs and 16 boats, embed every picture with Meta's DINOv2, and measure each
concept's spread as the mean pairwise cosine distance between its pictures. The same measure on
16 human drawings from Google Quick, Draw! (CC BY 4.0) gives the human spread for the same word.

Human drawings: Google Creative Lab, "The Quick, Draw! Dataset",
https://github.com/googlecreativelab/quickdraw-dataset, licensed CC BY 4.0.
"""
from __future__ import annotations

import io
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# All data and outputs (AI and human pictures, results, figures) live outside the repo.
PLATO_DIR = Path(os.environ.get("PLATO_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/core"))
QUICKDRAW_URL = "https://storage.googleapis.com/quickdraw_dataset/full/simplified/{category}.ndjson"
QUICKDRAW_CREDIT = ("Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0, "
                    "https://github.com/googlecreativelab/quickdraw-dataset")
DINO_MODEL = "facebook/dinov2-base"

STYLES = {
    "doodle": ("A quick simple doodle sketch of {phrase}, black marker on plain white, "
               "like a 20-second drawing, no text, no shading."),
    "photo": "A realistic photo of {phrase} on a plain background.",
}


@dataclass(frozen=True)
class PlatoConcept:
    key: str            # folder name; the Quick, Draw! category with spaces as underscores
    label: str          # what we call it in figures ("boat" for the sailboat category)
    quickdraw: str      # Quick, Draw! category name
    phrase: str         # noun phrase in the Muse Image prompt
    tier: int           # 1 = drawn first, 16 pictures; 2 = drawn next, 12 pictures
    n_ai: int           # AI pictures per concept; human drawings are subsampled to the same n
    kind: str           # a-priori type: fixed-shape artifact, many-style artifact, natural kind, person
    demo_word: str = ""  # demo_en word whose naming results we link to
    note: str = ""


DEMO_WORDS = ["cat", "umbrella", "anchor", "kettle", "ladder", "bench", "glove", "spoon", "carrot", "bicycle",
              "scissors", "candle", "helicopter", "pineapple", "snail", "saw", "cactus", "whistle", "harp", "igloo"]
# Demo words with no Quick, Draw! category, so no human drawings: left out.
DEMO_MISSING = ["anchor", "kettle", "glove", "whistle", "igloo"]
# A-priori kinds. The project's own examples: fixed-shape (key, scissors, spoon, umbrella), many-style
# (chair, house, car, hat, shoe, cup), natural kinds (tree, flower, bird, fish, cat, dog), people (face).
KINDS = {
    "fixed-shape artifact": ["key", "scissors", "spoon", "umbrella", "ladder", "saw", "candle", "bicycle", "harp",
                             "guitar", "book"],
    "many-style artifact": ["chair", "sailboat", "house", "car", "hat", "shoe", "cup", "bench", "helicopter",
                            "clock", "floor lamp"],
    "natural kind": ["tree", "flower", "bird", "fish", "cat", "dog", "carrot", "pineapple", "snail", "cactus",
                     "apple"],
    "person": ["face", "yoga"],
}
KIND_OF = {w: k for k, ws in KINDS.items() for w in ws}
LABELS = {"sailboat": "boat", "floor lamp": "lamp", "yoga": "person"}
PHRASES = {"yoga": "a person doing yoga", "scissors": "a pair of scissors"}
NOTES = {
    "sailboat": "Quick, Draw! has no 'boat'; sailboat is the closest everyday boat",
    "floor lamp": "Quick, Draw! has no 'lamp'; floor lamp is the closest",
    "face": "the person concept the project asked for first",
    "yoga": "Quick, Draw! has no 'person'; 'yoga' is its whole-body human figure category",
}
# Priority order: if drawing stops early, the key comparisons already exist.
TIER1 = ["chair", "sailboat", "face", "house", "cat", "cup", "tree", "car", "key", "umbrella"]
TIER2 = ["ladder", "bench", "carrot", "bicycle", "candle", "helicopter", "pineapple", "snail", "saw", "cactus",
         "harp", "flower", "bird", "fish", "dog", "shoe", "hat", "clock", "floor lamp", "book", "guitar", "apple",
         "scissors", "spoon", "yoga"]


def _c(qd: str, tier: int) -> PlatoConcept:
    phrase = PHRASES.get(qd) or (("an " if qd[0] in "aeiou" else "a ") + qd)
    return PlatoConcept(qd.replace(" ", "_"), LABELS.get(qd, qd), qd, phrase, tier, 16 if tier == 1 else 12,
                        KIND_OF[qd], qd if qd in DEMO_WORDS else "", NOTES.get(qd, ""))


CONCEPTS = [_c(w, 1) for w in TIER1] + [_c(w, 2) for w in TIER2]
BY_KEY = {c.key: c for c in CONCEPTS}
# Optional second style, to show how the prompt's style changes the spread (skipped in the first run).
PHOTO_KEYS = ["chair", "sailboat", "face", "yoga", "cat", "dog", "house", "tree", "shoe", "cup"]


def prompt_for(concept: PlatoConcept, style: str) -> str:
    """The Muse Image prompt. Styles: doodle, photo, and the variety prompts doodle_any and
    doodle_unusual (the doodle template with a variety phrase; see variety_phrase)."""
    if style.startswith("doodle_"):
        return STYLES["doodle"].format(phrase=variety_phrase(concept, style.removeprefix("doodle_")))
    return STYLES[style].format(phrase=concept.phrase)


# ---------- can you prompt it out of the Platonic chair? ----------
# Conditions, each a folder ai/<style>/<key>/ next to ai/doodle/ (the default prompt):
#   doodle_any      the doodle prompt with "a chair (any kind of chair)"
#   doodle_unusual  "... (any kind of chair at all; pick an unusual or different kind)", tier 1 only
#   doodle_listed   Muse Spark lists n_ai clearly different kinds; one doodle of each (p<i>.png = kinds[i])
VARIETY_STYLES = ("doodle_any", "doodle_unusual", "doodle_listed")


def variety_phrase(concept: PlatoConcept, condition: str) -> str:
    """The noun phrase for the 'any' and 'unusual' prompts. Yoga asks for any person and any pose."""
    noun = concept.quickdraw
    if concept.key == "yoga":
        return {"any": "a person doing yoga (any person, any pose)",
                "unusual": "a person doing yoga (any person, any pose at all; pick an unusual or different one)"}[condition]
    if condition == "any":
        return f"{concept.phrase} (any kind of {noun})"
    if condition == "unusual":
        return f"{concept.phrase} (any kind of {noun} at all; pick an unusual or different kind)"
    raise ValueError(f"no variety phrase for condition {condition!r}")


def listing_prompt(concept: PlatoConcept, n: int) -> str:
    """Muse Spark's request for n kinds (the pilot's wording, so its chair and umbrella lists still fit)."""
    if concept.key == "yoga":
        return (f"List {n} clearly different yoga poses that someone could draw a person doing, as short noun "
                f"phrases starting with 'a person' (e.g. 'a person in tree pose'). One per line, nothing else.")
    return (f"List {n} clearly different kinds of {concept.quickdraw} that someone could draw, as short noun phrases "
            f"starting with 'a' or 'an' (e.g. 'a rocking chair'). One per line, nothing else.")


def parse_kinds(text: str, n: int) -> list[str]:
    """Spark's list as noun phrases: bullets, numbering, bold and trailing periods removed, duplicates
    (case-insensitive) dropped, only lines that start with an article kept, at most n."""
    import re

    kinds, seen = [], set()
    for line in text.splitlines():
        s = re.sub(r"^\s*(?:[-*•]+|\d+\s*[.):-])\s*", "", line).replace("**", "").strip().rstrip(".;,").strip()
        if not re.match(r"(?i)^(a|an)\s+\S", s) or s.lower() in seen:
            continue
        seen.add(s.lower())
        kinds.append(s)
    return kinds[:n]


LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def kind_options(concept: PlatoConcept, kinds: list[str]) -> list[str]:
    """The labeler's choices for one concept: Spark's listed kinds, then the plain, ordinary one, then
    'can't tell'. The last two are always plain_option() and none_option()."""
    if len(kinds) + 2 > len(LETTERS):
        raise ValueError("too many kinds for single-letter options")
    return list(kinds) + [plain_option(concept), none_option(concept)]


def plain_option(concept: PlatoConcept) -> str:
    if concept.key == "yoga":
        return "a person in a plain, simple pose (just standing or sitting)"
    return f"a plain, ordinary {concept.quickdraw}"


def none_option(concept: PlatoConcept) -> str:
    if concept.key == "yoga":
        return "can't tell, or not a person"
    article = "an" if concept.quickdraw[0] in "aeiou" else "a"
    return f"can't tell, or not {article} {concept.quickdraw}"


def labeling_prompt(concept: PlatoConcept, options: list[str]) -> str:
    """Multiple choice with letters; the answer is read from the letter logits."""
    noun = "person doing yoga" if concept.key == "yoga" else concept.quickdraw
    lines = "\n".join(f"{LETTERS[i]}. {o}" for i, o in enumerate(options))
    return (f"Someone was asked to draw {concept.phrase}. Which kind of {noun} is in this drawing? Pick the one "
            f"option that fits best. If it is just an ordinary {noun} and not clearly one of the specific kinds, "
            f"pick \"{options[-2]}\".\n{lines}\nAnswer with the letter only.")


def parse_letter(text: str, n_options: int) -> int | None:
    """Index of the option a free-text answer names ('B', 'B.', '**B**', 'Answer: B', '(B) a sofa'),
    or None. The letter must stand alone (end of text or punctuation after it), so an answer that
    starts with the article 'A plain chair' is not read as option A."""
    import re

    m = re.match(r"^[\s*(\[]*(?:answer\s*(?:is)?\s*[:\-]?\s*)?[\s*(\[]*([A-Za-z])\s*(?:$|[.):\]*,])",
                 text.strip(), flags=re.I)
    if m and m.group(1).upper() in LETTERS[:n_options]:
        return LETTERS.index(m.group(1).upper())
    return None


def kind_diversity(labels: list[str], plain: str | None = None, none: str | None = None) -> dict:
    """How many kinds a set of pictures shows, from one hard label per picture.

    'Can't tell' labels (`none`) are not a kind: they are counted in share_none and left out of the rest.
    - distinct: number of different kinds
    - simpson: chance that two different pictures show different kinds (unbiased Gini-Simpson,
      1 - sum c(c-1) / n(n-1)); 0 = all one kind, it does not grow with n
    - entropy_bits, effective_kinds (2**entropy, the Hill number of order 1)
    - prototype: the most common kind (ties: the first in sorted order) and its share
    - share_plain: share labeled as the plain, ordinary kind"""
    from collections import Counter

    n_all = len(labels)
    kept = [x for x in labels if x != none]
    n = len(kept)
    counts = Counter(kept)
    out = {"n": n_all, "n_kind": n, "share_none": (n_all - n) / n_all if n_all else float("nan")}
    if not n:
        return {**out, "distinct": 0, "simpson": float("nan"), "entropy_bits": float("nan"),
                "effective_kinds": float("nan"), "prototype": None, "prototype_share": float("nan"),
                "share_plain": float("nan")}
    p = np.array(list(counts.values()), float) / n
    entropy = float(-(p * np.log2(p)).sum())
    c = np.array(list(counts.values()), float)
    simpson = float(1 - (c * (c - 1)).sum() / (n * (n - 1))) if n > 1 else float("nan")
    proto = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return {**out, "distinct": len(counts), "simpson": simpson, "entropy_bits": entropy,
            "effective_kinds": float(2 ** entropy), "prototype": proto[0], "prototype_share": proto[1] / n,
            "share_plain": counts.get(plain, 0) / n if plain is not None else float("nan")}


def bootstrap_simpson(labels: list[str], none: str | None = None, reps: int = 2000,
                      rng: np.random.Generator | None = None) -> np.ndarray:
    """Simpson diversity of resampled pictures; a picture drawn twice is never paired with itself
    (the same trick as bootstrap_spread), so a set of all-different kinds always gives 1."""
    rng = rng or np.random.default_rng(0)
    kept = [x for x in labels if x != none]
    n = len(kept)
    if n < 2:
        return np.full(reps, np.nan)
    _, codes = np.unique(kept, return_inverse=True)
    same = (codes[:, None] == codes[None, :]).astype(float)
    out = np.empty(reps)
    for b in range(reps):
        w = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
        ww = np.outer(w, w)
        np.fill_diagonal(ww, 0)
        out[b] = 1 - (ww * same).sum() / ww.sum() if ww.sum() else np.nan
    return out


# ---------- pictures ----------

def downscale(png: bytes, side: int = 512) -> Image.Image:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    img.thumbnail((side, side), Image.LANCZOS)
    return img


def render_strokes(drawing: list, side: int = 256, width: int = 3, pad: int = 12) -> Image.Image:
    """Quick, Draw! simplified strokes ([[xs], [ys]] per stroke, 0-255) as black ink on white."""
    scale = (side - 2 * pad) / 255.0
    xs = [x for s in drawing for x in s[0]]
    ys = [y for s in drawing for y in s[1]]
    # center the drawing (simplified data is aligned to the top-left corner)
    dx = (255 - max(xs)) / 2 if xs else 0
    dy = (255 - max(ys)) / 2 if ys else 0
    img = Image.new("L", (side, side), 255)
    draw = ImageDraw.Draw(img)
    for sx, sy in drawing:
        pts = [(pad + (x + dx) * scale, pad + (y + dy) * scale) for x, y in zip(sx, sy)]
        if len(pts) == 1:
            pts = pts * 2
        draw.line(pts, fill=0, width=width, joint="curve")
        r = width / 2
        for x, y in (pts[0], pts[-1]):
            draw.ellipse((x - r, y - r, x + r, y + r), fill=0)
    return img.convert("RGB")


def flatten_paper(gray: Image.Image, line_px: int = 21, paper: int = 215) -> Image.Image:
    """Divide out the paper: shading, texture and vignettes become white, thin ink lines stay.

    The paper is estimated by a max filter wider than any marker line, then blurred; dividing by it
    is a flat-field correction. A pure white background (the rendered human drawings) is unchanged."""
    from scipy.ndimage import gaussian_filter, maximum_filter

    a = np.asarray(gray, dtype=np.float32)
    bg = gaussian_filter(maximum_filter(a, size=line_px), sigma=line_px / 2)
    flat = np.clip(a / np.maximum(bg, 1) * 255, 0, 255)
    flat[flat > paper] = 255
    return Image.fromarray(flat.astype(np.uint8))


def ink_crop(img: Image.Image, side: int = 256, margin: float = 0.06, threshold: int = 200) -> Image.Image:
    """Flatten the paper, crop a white-background picture to its ink, pad to a square and resize.

    Quick, Draw! simplified drawings are already scaled to fill their box, so cropping the AI doodles
    the same way removes size and position differences that have nothing to do with the concept.
    Some AI doodles come on gray or textured "paper"; flattening it keeps paper from counting as
    variation (or as ink when cropping). The crop box ignores specks under 3 px (paper grain)."""
    gray = flatten_paper(img.convert("L"))
    mask = gray.filter(ImageFilter.MaxFilter(3)).point(lambda v: 255 if v < threshold else 0)
    box = mask.getbbox() or gray.point(lambda v: 255 if v < threshold else 0).getbbox()
    if box:
        gray = gray.crop(box)
    w, h = gray.size
    s = int(max(w, h) * (1 + 2 * margin)) or 1
    canvas = Image.new("L", (s, s), 255)
    canvas.paste(gray, ((s - w) // 2, (s - h) // 2))
    return canvas.resize((side, side), Image.LANCZOS).convert("RGB")


def stream_quickdraw(category: str, keep: int = 200, max_lines: int = 5000, timeout: float = 60) -> list[dict]:
    """The first `keep` recognized drawings, read line by line; stops early, never downloads the file."""
    import httpx

    url = QUICKDRAW_URL.format(category=category.replace(" ", "%20"))
    kept, seen = [], 0
    with httpx.stream("GET", url, timeout=timeout) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.strip():
                continue
            seen += 1
            rec = json.loads(line)
            if rec.get("recognized") is True and rec.get("word") == category:
                kept.append({"key_id": rec.get("key_id"), "countrycode": rec.get("countrycode"),
                             "drawing": rec["drawing"]})
            if len(kept) >= keep or seen >= max_lines:
                break
    return kept


# ---------- embeddings ----------

class Embedder:
    """DINOv2 image embeddings: the CLS token and the mean of the patch tokens."""

    def __init__(self, model: str = DINO_MODEL, device: str | None = None):
        import torch
        from transformers import AutoImageProcessor, AutoModel

        self.torch = torch
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        self.processor = AutoImageProcessor.from_pretrained(model)
        self.model = AutoModel.from_pretrained(model).to(self.device).eval()

    def __call__(self, images: list[Image.Image], batch: int = 32) -> dict[str, np.ndarray]:
        cls, mean = [], []
        with self.torch.no_grad():
            for i in range(0, len(images), batch):
                inputs = self.processor(images=images[i:i + batch], return_tensors="pt").to(self.device)
                hidden = self.model(**inputs).last_hidden_state.float()
                cls.append(hidden[:, 0].cpu().numpy())
                mean.append(hidden[:, 1:].mean(1).cpu().numpy())
        return {"cls": np.concatenate(cls), "patch_mean": np.concatenate(mean)}


# ---------- statistics ----------

def cosine_distances(x: np.ndarray, y: np.ndarray | None = None) -> np.ndarray:
    xn = x / np.linalg.norm(x, axis=1, keepdims=True)
    yn = xn if y is None else y / np.linalg.norm(y, axis=1, keepdims=True)
    return 1.0 - xn @ yn.T


def spread(d: np.ndarray, idx: np.ndarray | None = None) -> float:
    """Mean pairwise distance among distinct pictures."""
    if idx is not None:
        d = d[np.ix_(idx, idx)]
    n = len(d)
    return float(d[np.triu_indices(n, 1)].mean())


def bootstrap_spread(d: np.ndarray, reps: int = 2000, rng: np.random.Generator | None = None) -> np.ndarray:
    """Resample pictures with replacement; a picture drawn twice is never paired with itself."""
    rng = rng or np.random.default_rng(0)
    n = len(d)
    out = np.empty(reps)
    for b in range(reps):
        c = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
        w = np.outer(c, c)
        np.fill_diagonal(w, 0)
        out[b] = (w * d).sum() / w.sum()
    return out


def subsample_spread(d: np.ndarray, k: int = 16, reps: int = 200, rng: np.random.Generator | None = None) -> np.ndarray:
    """Spread of `reps` random k-picture subsets (without replacement)."""
    rng = rng or np.random.default_rng(0)
    return np.array([spread(d, rng.choice(len(d), k, replace=False)) for _ in range(reps)])


def ci(x: np.ndarray, level: float = 0.95) -> list[float]:
    a = (1 - level) / 2
    return [float(np.quantile(x, a)), float(np.quantile(x, 1 - a))]


def spearman(x, y) -> float:
    from scipy.stats import spearmanr

    return float(spearmanr(x, y).statistic)


def spearman_ci(x, y, reps: int = 5000, rng: np.random.Generator | None = None) -> dict:
    """Spearman's rho with a bootstrap CI over items and a two-sided permutation p."""
    rng = rng or np.random.default_rng(0)
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    rho = spearman(x, y)
    boots = []
    for _ in range(reps):
        i = rng.integers(0, n, n)
        if len(set(x[i])) > 1 and len(set(y[i])) > 1:
            boots.append(spearman(x[i], y[i]))
    perm = np.array([spearman(x, rng.permutation(y)) for _ in range(reps)])
    p = float((np.abs(perm) >= abs(rho) - 1e-12).mean())
    return {"rho": rho, "ci95": ci(np.array(boots)), "p_perm": p, "n": n}


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        return round(float(obj), 4)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, PlatoConcept):
        return asdict(obj)
    return obj


def grid(images: list[Image.Image], cols: int = 4, cell: int = 160, gap: int = 6, bg: str = "white") -> Image.Image:
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell + (cols - 1) * gap, rows * cell + (rows - 1) * gap), bg)
    for i, img in enumerate(images):
        tile = ImageOps.contain(img.convert("RGB"), (cell, cell))
        x = (i % cols) * (cell + gap) + (cell - tile.width) // 2
        y = (i // cols) * (cell + gap) + (cell - tile.height) // 2
        sheet.paste(tile, (x, y))
    return sheet


def load_dir(folder: Path, limit: int | None = None) -> list[Path]:
    files = sorted(folder.glob("*.png"), key=lambda p: (len(p.stem), p.stem))
    return files[:limit] if limit else files

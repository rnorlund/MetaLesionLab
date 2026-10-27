"""Plato's chair across languages and countries.

Is the "ideal chair" the same everywhere? We compare two kinds of quick doodles of the same
everyday objects:

* AI: Muse Image draws doodles from one doodle-style prompt written fully in six languages.
* People: Quick, Draw! drawings (Google, CC BY 4.0) from six countries.

Meta's DINOv2 (facebook/dinov2-base) turns every doodle into a vector. From those vectors we
measure, per concept:

* spread: the average distance between two doodles of the same group (how varied they are);
* centroid shift: the distance between two groups' average doodles, against a label-shuffling
  baseline (how much the "ideal" moves);
* group share: the share of all variation that is due to the group (language or country), an
  intraclass correlation that doesn't depend on sample size, so AI and people can be compared.

Distances are cosine distances between L2-normalized DINOv2 CLS embeddings.
"""
from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

REPO_ROOT = Path(__file__).resolve().parents[1]
# Images, human doodles, results and figures live outside the public repo.
OUT = Path(os.environ.get("PLATO_LANG_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/languages"))

# Quick, Draw! categories with clear one-word translations. Ten, to keep Muse Image at $6
# (10 concepts x 6 languages x 10 doodles = 600 images at $0.01).
CONCEPTS = ["chair", "house", "cup", "shoe", "hat", "tree", "bird", "flower", "bicycle", "umbrella"]
LANGS = {"en": "English", "es": "Spanish", "hi": "Hindi", "zh": "Mandarin Chinese", "ar": "Arabic",
         "sw": "Swahili"}
# Chosen to match the AI's languages where Quick, Draw! has enough drawings. No Swahili-speaking
# country does (Kenya and Tanzania are under 0.05% of drawings), so Russia stands in as a sixth
# region. Country is not language: many people in India played in English, for example.
COUNTRIES = {"US": "United States", "MX": "Mexico", "IN": "India", "TW": "Taiwan",
             "SA": "Saudi Arabia", "RU": "Russia"}
LANG_COUNTRY = {"en": "US", "es": "MX", "hi": "IN", "zh": "TW", "ar": "SA"}

PROMPT_EN = ("A quick doodle of {article} {word}, drawn in under 20 seconds with a black marker on a "
             "white background. Simple black lines only: no shading, no color, no text, no other objects.")
SCRIPT_NOTES = {"zh": "Simplified Chinese characters", "hi": "Devanagari script",
                "ar": "Modern Standard Arabic", "es": "neutral Latin American Spanish",
                "sw": "standard Swahili (Kiswahili sanifu)"}

QD_URL = "https://storage.googleapis.com/quickdraw_dataset/full/simplified/{category}.ndjson"
QD_CREDIT = "Human drawings: Quick, Draw! by Google (CC BY 4.0), quickdraw.withgoogle.com/data"
DINO = "facebook/dinov2-base"

CANVAS = 256  # stored and canonical image side
BOX = 200  # the drawing's longer side inside the canonical canvas


# ---------------------------------------------------------------- prompts (Muse Spark)

def english_prompt(concept: str) -> str:
    return PROMPT_EN.format(article="an" if concept[0] in "aeiou" else "a", word=concept)


def _json_from(text: str):
    match = re.search(r"[\[{].*[\]}]", text, re.S)
    return json.loads(match.group(0)) if match else None


def translate_prompts(api, langs=tuple(LANGS), concepts: list[str] = CONCEPTS) -> dict[str, dict]:
    """One Muse Spark call: the doodle prompt for every concept, written naturally in every language.

    Returns {lang: {concept: {"word", "prompt"}}}. English comes straight from the template."""
    template = PROMPT_EN.format(article="a", word="{object}")
    others = [lang for lang in langs if lang != "en"]
    listing = "\n".join(f"- {lang}: {LANGS[lang]} ({SCRIPT_NOTES[lang]})" for lang in others)
    ask = (
        "Translate this image-generation prompt into each language below, once for each object. Write "
        "it the way a native speaker would naturally phrase it, entirely in that language: no English "
        "words, no transliterations, no parentheses or notes. Use the most common everyday word for the "
        "object, with correct grammar (articles, gender, measure words). Keep every instruction in the "
        f"template.\n\nTemplate: {template}\n\nLanguages:\n{listing}\n\nObjects: {', '.join(concepts)}\n\n"
        'Return only JSON: {"<language code>": [{"concept": "<English object>", "word": "<the word you '
        'used>", "prompt": "<the full prompt>"}, ...], ...}')
    reply = api.chat([{"role": "user", "content": ask}], reasoning_effort="minimal")
    data = _json_from(reply.choices[0].message.content) or {}
    result = {"en": {c: {"word": c, "prompt": english_prompt(c)} for c in concepts}} if "en" in langs else {}
    for lang in others:
        items = {str(it.get("concept", "")).strip().lower(): {"word": it.get("word", ""), "prompt": it.get("prompt", "")}
                 for it in data.get(lang, [])}
        missing = [c for c in concepts if not items.get(c, {}).get("prompt")]
        if missing:
            raise ValueError(f"{lang}: no prompt for {missing}")
        result[lang] = {c: items[c] for c in concepts}
    return result


# ---------------------------------------------------------------- images

def save_png(image: bytes, path: Path, side: int = 512) -> None:
    img = Image.open(io.BytesIO(image)).convert("RGB")
    img.thumbnail((side, side), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", optimize=True)


def _fit(ink: Image.Image, bbox, side: int = CANVAS, box: int = BOX) -> Image.Image:
    """Crop `ink` (L mode, white background) to bbox and centre it, scaled so its longer side is `box`."""
    crop = ink.crop(bbox)
    w, h = crop.size
    scale = box / max(w, h, 1)
    crop = crop.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    canvas = Image.new("L", (side, side), 255)
    canvas.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    return canvas


def canonical_ai(path: Path) -> Image.Image:
    """An AI doodle as black ink on white, cropped to the drawing and centred like the human renders."""
    gray = ImageOps.autocontrast(Image.open(path).convert("L"), cutoff=0.5)
    ink = gray.point(lambda v: 0 if v < 150 else 255)
    arr = np.asarray(ink) < 128
    rows, cols = np.flatnonzero(arr.sum(1) >= 2), np.flatnonzero(arr.sum(0) >= 2)  # ignore lone specks
    if not len(rows) or not len(cols):
        return _fit(ink, (0, 0, *ink.size))
    return _fit(ink, (cols[0], rows[0], cols[-1] + 1, rows[-1] + 1))


def _thin(ink: np.ndarray) -> np.ndarray:
    """Zhang-Suen thinning of a boolean ink mask to one-pixel-wide lines."""
    img = np.pad(ink.astype(np.uint8), 1)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            c = img[1:-1, 1:-1]
            p2, p3, p4, p5 = img[:-2, 1:-1], img[:-2, 2:], img[1:-1, 2:], img[2:, 2:]
            p6, p7, p8, p9 = img[2:, 1:-1], img[2:, :-2], img[1:-1, :-2], img[:-2, :-2]
            ring = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            n = sum(p.astype(np.int16) for p in ring[:8])
            turns = sum(((ring[i] == 0) & (ring[i + 1] == 1)).astype(np.int16) for i in range(8))
            if step == 0:
                side = ((p2 & p4 & p6) == 0) & ((p4 & p6 & p8) == 0)
            else:
                side = ((p2 & p4 & p8) == 0) & ((p2 & p6 & p8) == 0)
            remove = (c == 1) & (n >= 2) & (n <= 6) & (turns == 1) & side
            if remove.any():
                c[remove] = 0
                changed = True
    return img[1:-1, 1:-1].astype(bool)


def uniform_lines(img: Image.Image, merge: int = 2, width: int = 1) -> Image.Image:
    """Style control: redraw a doodle's lines at one uniform width.

    Ink is merged across small gaps (so sketchy multi-stroke lines become one), thinned to a
    skeleton, then thickened to 2*width+1 px. Removes line weight and sketchiness, keeps the form."""
    from scipy.ndimage import binary_dilation
    ink = np.asarray(img.convert("L")) < 128
    if merge:
        ink = binary_dilation(ink, np.ones((3, 3), bool), iterations=merge)
    skel = _thin(ink)
    lines = binary_dilation(skel, np.ones((3, 3), bool), iterations=width)
    return Image.fromarray(np.where(lines, 0, 255).astype(np.uint8))


def render_strokes(drawing: list, side: int = CANVAS, box: int = BOX, width: float = 3.0, ss: int = 4) -> Image.Image:
    """Render Quick, Draw! simplified strokes ([[xs], [ys]] per stroke) as black lines, centred."""
    xs = [x for s in drawing for x in s[0]]
    ys = [y for s in drawing for y in s[1]]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    scale = box / max(x1 - x0, y1 - y0, 1)
    ox = (side - (x1 - x0) * scale) / 2
    oy = (side - (y1 - y0) * scale) / 2
    img = Image.new("L", (side * ss, side * ss), 255)
    draw = ImageDraw.Draw(img)
    r = width * ss / 2
    for sx, sy in (s[:2] for s in drawing):
        pts = [((x - x0) * scale * ss + ox * ss, (y - y0) * scale * ss + oy * ss) for x, y in zip(sx, sy)]
        if len(pts) > 1:
            draw.line(pts, fill=0, width=round(width * ss), joint="curve")
        for px, py in pts:  # round caps and joins
            draw.ellipse((px - r, py - r, px + r, py + r), fill=0)
    return img.resize((side, side), Image.LANCZOS)


# ---------------------------------------------------------------- Quick, Draw! streaming

def stream_quickdraw(category: str, countries, per_country: int = 200, max_bytes: int = 150_000_000):
    """Recognized drawings for each country, read line by line until every quota is met.

    Returns ({country: [record, ...]}, bytes_read, lines_read). Records keep key_id, countrycode
    and drawing. Lines are parsed as JSON data only."""
    import httpx

    out = {c: [] for c in countries}
    n_bytes = n_lines = 0
    url = QD_URL.format(category=category.replace(" ", "%20"))
    with httpx.stream("GET", url, timeout=60, follow_redirects=False) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            n_bytes += len(line) + 1
            n_lines += 1
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            c = rec.get("countrycode")
            if rec.get("recognized") is True and c in out and len(out[c]) < per_country:
                drawing = rec.get("drawing")
                if isinstance(drawing, list) and drawing:
                    out[c].append({"key_id": str(rec.get("key_id")), "countrycode": c, "drawing": drawing})
            if all(len(v) >= per_country for v in out.values()) or n_bytes >= max_bytes:
                break
    return out, n_bytes, n_lines


# ---------------------------------------------------------------- DINOv2

def pick_device() -> str:
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


class Dino:
    def __init__(self, device: str | None = None):
        import torch
        from transformers import AutoImageProcessor, AutoModel
        self.torch = torch
        self.device = device or pick_device()
        self.proc = AutoImageProcessor.from_pretrained(DINO)
        self.model = AutoModel.from_pretrained(DINO).eval().to(self.device)

    def embed(self, images: list[Image.Image], batch: int = 32) -> dict[str, np.ndarray]:
        """L2-normalized CLS and mean-patch embeddings, (N, 768) each."""
        cls, patch = [], []
        with self.torch.no_grad():
            for i in range(0, len(images), batch):
                inputs = self.proc(images=[im.convert("RGB") for im in images[i:i + batch]], return_tensors="pt")
                out = self.model(pixel_values=inputs["pixel_values"].to(self.device))
                cls.append(out.pooler_output.float().cpu().numpy())
                patch.append(out.last_hidden_state[:, 1:].mean(1).float().cpu().numpy())
        norm = lambda a: a / np.linalg.norm(a, axis=1, keepdims=True)
        return {"cls": norm(np.concatenate(cls)), "patch": norm(np.concatenate(patch))}


# ---------------------------------------------------------------- measures

def cosine_distances(emb: np.ndarray) -> np.ndarray:
    return np.clip(1.0 - emb @ emb.T, 0.0, 2.0)


def group_measures(D: np.ndarray, labels: np.ndarray, k: int, orig: np.ndarray | None = None) -> dict:
    """Spread, between-group distance and group share from a cosine-distance matrix.

    W[g]   = mean distance between two different doodles of group g (spread);
    B[g,h] = mean distance across groups minus the mean of the two spreads. For unit vectors it
             equals half the squared distance between the groups' true average doodles, with no
             small-sample bias (it can dip below 0 by chance when the groups don't differ);
    share  = between-group variance / (between + within), the part of all variation due to group.
    `orig` gives each row's original item so bootstrap duplicates aren't paired with themselves."""
    orig = np.arange(len(labels)) if orig is None else orig
    idx = [np.flatnonzero(labels == g) for g in range(k)]
    W = np.empty(k)
    for g, ii in enumerate(idx):
        sub = D[np.ix_(ii, ii)]
        mask = orig[ii][:, None] != orig[ii][None, :]
        W[g] = sub[mask].mean()
    C = np.array([[D[np.ix_(idx[g], idx[h])].mean() for h in range(k)] for g in range(k)])
    B = C - (W[:, None] + W[None, :]) / 2
    np.fill_diagonal(B, 0.0)
    # For unit vectors cosine distance is |x - y|^2 / 2, so W[g] = E|x - mu_g|^2 (the within-group
    # variance) and sum(B) / k^2 = (1/k) sum_g |mu_g - mu|^2 (the between-group variance).
    between = B.sum() / k ** 2
    within = W.mean()
    off = B[np.triu_indices(k, 1)]
    return {"W": W, "B": B, "B_mean": float(off.mean()), "share": float(between / (between + within))}


def centroid_distances(emb: np.ndarray, labels: np.ndarray, k: int) -> np.ndarray:
    """Cosine distance between each pair of group-average embeddings."""
    cents = np.stack([emb[labels == g].mean(0) for g in range(k)])
    cents /= np.linalg.norm(cents, axis=1, keepdims=True)
    return 1.0 - cents @ cents.T


def permutation_test(emb: np.ndarray, labels: np.ndarray, k: int, n_perm: int = 2000, seed: int = 0) -> dict:
    """Shuffle group labels to get the centroid distances and group share expected by chance."""
    rng = np.random.default_rng(seed)
    D = cosine_distances(emb)
    iu = np.triu_indices(k, 1)
    obs_c = centroid_distances(emb, labels, k)
    obs = {"centroid_mean": float(obs_c[iu].mean()), "share": group_measures(D, labels, k)["share"]}
    null_c, null_pair, null_share = np.empty(n_perm), np.empty((n_perm, len(iu[0]))), np.empty(n_perm)
    for p in range(n_perm):
        perm = rng.permutation(labels)
        c = centroid_distances(emb, perm, k)[iu]
        null_pair[p], null_c[p] = c, c.mean()
        null_share[p] = group_measures(D, perm, k)["share"]
    pair_p = ((null_pair >= obs_c[iu][None, :]).sum(0) + 1) / (n_perm + 1)
    return {
        "centroid": obs_c,
        "centroid_null_mean": null_pair.mean(0),  # per pair, upper-triangle order
        "centroid_pair_p": pair_p,
        "centroid_mean": obs["centroid_mean"],
        "centroid_mean_null": float(null_c.mean()),
        "centroid_mean_null_95": float(np.quantile(null_c, 0.95)),
        "centroid_mean_p": float(((null_c >= obs["centroid_mean"]).sum() + 1) / (n_perm + 1)),
        "share": obs["share"],
        "share_null_mean": float(null_share.mean()),
        "share_null_95": float(np.quantile(null_share, 0.95)),
        "share_p": float(((null_share >= obs["share"]).sum() + 1) / (n_perm + 1)),
    }


def bootstrap(emb: np.ndarray, labels: np.ndarray, k: int, n_boot: int = 2000, seed: int = 0) -> dict:
    """Resample doodles within each group; 95% percentile intervals for spreads, B and share."""
    rng = np.random.default_rng(seed)
    D = cosine_distances(emb)
    idx = [np.flatnonzero(labels == g) for g in range(k)]
    W, Bm, S = np.empty((n_boot, k)), np.empty(n_boot), np.empty(n_boot)
    for b in range(n_boot):
        pick = np.concatenate([rng.choice(ii, len(ii)) for ii in idx])
        lab = labels[pick]
        m = group_measures(D[np.ix_(pick, pick)], lab, k, orig=pick)
        W[b], Bm[b], S[b] = m["W"], m["B_mean"], m["share"]
    q = lambda a: np.quantile(a, [0.025, 0.975], axis=0)
    return {"W": W, "B_mean": Bm, "share": S, "W_ci": q(W), "B_mean_ci": q(Bm), "share_ci": q(S)}


def ci(a, lo=0.025, hi=0.975) -> list[float]:
    return [float(np.quantile(a, lo)), float(np.quantile(a, hi))]

"""Draw your chair: where does a visitor's drawing land among Muse Image's and people's drawings?

The same pipeline as the Plato's Chair experiment (scripts/plato_embed.py), so a visitor's drawing is
measured exactly like the 200 Quick, Draw! drawings it is compared with:

  canvas strokes -> Quick, Draw! normalisation (align to the corner, scale to 0-255, resample at 1 px,
  Ramer-Douglas-Peucker with epsilon 2) -> plato.render_strokes (256 px, 3 px black ink on white)
  -> plato.ink_crop -> Meta DINOv2-base CLS token -> cosine distances.

Per-concept reference data (centroids, leave-one-out distances, a small PCA) is precomputed by
scripts/draw_export.py into web/data/draw.json. The embedding model runs on CPU, through
onnxruntime when the exported model file exists (scripts/draw_model.py), else through torch.
Nothing here imports torch or onnxruntime until an embedder is built.

Drawings are processed in memory only: nothing in this module writes or logs them.
"""
from __future__ import annotations

import base64
import json
import math
import os
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from metalesionlab.plato import DINO_MODEL, ink_crop, render_strokes

REPO = Path(__file__).resolve().parents[1]
DATA_PATH = Path(__file__).resolve().parent / "web" / "data" / "draw.json"
# The exported DINOv2-base ONNX model (about 350 MB, never committed): scripts/draw_model.py writes it.
MODEL_PATH = Path(os.environ.get("DRAW_MODEL", REPO / "runs" / "models" / "dinov2-base-cls.onnx"))

MAX_STROKES = 200
MAX_POINTS = 8000
MIN_POINTS = 2
SIDE = 256       # ink_crop output, as in the experiment
CROP = 224       # DINOv2 processor: shortest edge 256, center crop 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class DrawingError(ValueError):
    """The strokes can't be turned into a drawing (empty, too big, not numbers)."""


# ---------- strokes -> picture ----------

def _rdp(pts: np.ndarray, eps: float) -> np.ndarray:
    """Ramer-Douglas-Peucker simplification of one polyline (iterative, keeps both ends)."""
    n = len(pts)
    if n < 3:
        return pts
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        seg = pts[b] - pts[a]
        rel = pts[a + 1:b] - pts[a]
        norm = math.hypot(*seg)
        if norm == 0:
            dist = np.hypot(rel[:, 0], rel[:, 1])
        else:
            dist = np.abs(seg[0] * rel[:, 1] - seg[1] * rel[:, 0]) / norm
        i = int(np.argmax(dist))
        if dist[i] > eps:
            m = a + 1 + i
            keep[m] = True
            stack += [(a, m), (m, b)]
    return pts[keep]


def _resample(pts: np.ndarray, step: float = 1.0) -> np.ndarray:
    """Points every `step` pixels along the polyline (the ends are kept)."""
    if len(pts) < 2:
        return pts
    seg = np.hypot(*np.diff(pts, axis=0).T)
    total = float(seg.sum())
    if total == 0:
        return pts[:1]
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.append(np.arange(0.0, total, step), total)
    return np.column_stack([np.interp(t, cum, pts[:, 0]), np.interp(t, cum, pts[:, 1])])


def _as_strokes(strokes) -> list[np.ndarray]:
    """Validate visitor strokes ([[xs], [ys]] per stroke, any scale) into (n, 2) float arrays."""
    if not isinstance(strokes, (list, tuple)) or not strokes:
        raise DrawingError("The drawing is empty.")
    if len(strokes) > MAX_STROKES:
        raise DrawingError(f"Too many strokes (the limit is {MAX_STROKES}).")
    out, total = [], 0
    for s in strokes:
        if not isinstance(s, (list, tuple)) or len(s) < 2:
            raise DrawingError("Each stroke needs a list of x and a list of y values.")
        xs, ys = s[0], s[1]
        if not isinstance(xs, (list, tuple)) or not isinstance(ys, (list, tuple)) or len(xs) != len(ys):
            raise DrawingError("Each stroke needs as many x values as y values.")
        if not xs:
            continue
        total += len(xs)
        if total > MAX_POINTS:
            raise DrawingError(f"Too many points (the limit is {MAX_POINTS}).")
        try:
            a = np.array([xs, ys], dtype=np.float64).T
        except (TypeError, ValueError) as e:
            raise DrawingError("Stroke coordinates must be numbers.") from e
        if not np.isfinite(a).all() or np.abs(a).max() > 1e6:
            raise DrawingError("Stroke coordinates must be finite numbers.")
        out.append(a)
    if sum(len(a) for a in out) < MIN_POINTS:
        raise DrawingError("The drawing is empty.")
    return out


def normalize_strokes(strokes) -> list[list[list[int]]]:
    """Visitor strokes in canvas pixels -> Quick, Draw! 'simplified' strokes (0-255 integers).

    The dataset's own recipe: align to the top-left corner, scale uniformly so the longer side spans
    0-255, resample every stroke at 1 px, then simplify with Ramer-Douglas-Peucker (epsilon 2.0)."""
    arrs = _as_strokes(strokes)
    allpts = np.concatenate(arrs)
    lo = allpts.min(axis=0)
    extent = float((allpts.max(axis=0) - lo).max())
    scale = 255.0 / extent if extent > 0 else 1.0
    out = []
    for a in arrs:
        p = (a - lo) * scale
        p = _rdp(_resample(p, 1.0), 2.0)
        p = np.clip(np.rint(p), 0, 255).astype(int)
        out.append([p[:, 0].tolist(), p[:, 1].tolist()])
    return out


def render(strokes) -> Image.Image:
    """Visitor strokes -> the picture DINOv2 sees: rendered like the human drawings, then ink-cropped."""
    return ink_crop(render_strokes(normalize_strokes(strokes)))


# ---------- an uploaded photo of a drawing on paper -> picture ----------

MAX_UPLOAD_BYTES = 3 * 1024 * 1024    # the browser sends a JPEG of at most 1024 px, usually 100-400 KB
MAX_UPLOAD_PIXELS = 40_000_000        # refuse decompression bombs before decoding
UPLOAD_SIDE = 512                     # Muse Image's pictures were stored at 512 px before ink_crop
NOT_A_DRAWING = ("That looks like a photo of a real object or a busy scene, not a line drawing. Draw it on plain "
                 "paper with a dark pen, then photograph just the drawing.")
NO_INK = ("We couldn't find a drawing in that photo. Draw with a dark pen or marker on plain paper and "
          "photograph it close up.")
EDGES = ("The edge of the paper (or the table) is in the photo, and it would count as part of your drawing. Take "
         "the photo closer, so the paper fills the picture, or crop it to the drawing.")
# Calibrated on synthetic pen-on-paper photos, Muse Image's doodles, children's tablet drawings and line-art
# pictures (should pass) against photos of clocks, landscapes, flowers, colour illustrations and noise (should
# not): scripts/draw_validate.py --uploads. The thresholds sit between the two groups' extremes.
MAX_COLOUR = 0.25      # share of strongly coloured pixels in the middle of the picture (a table at the edges is fine)
MAX_INK = 0.35         # share of dark pixels once the paper is flattened
MAX_MIDTONE = 0.25     # share of mid-gray pixels once the paper is flattened (shading, texture, scenery)
MIN_INK = 0.001        # less than this (at the looser ink threshold) is blank paper
MAX_DOODLE_DISTANCE = 0.78  # cosine distance from the nearest centroid of people's doodles (35 things)
MAX_SPAN = 0.95        # ink reaching across 95% of both width and height is the paper's edge or a frame
MAX_BORDER = 0.25      # share of the picture's outer edge much darker than its middle: a table around the paper


def load_upload(data: bytes) -> Image.Image:
    """Decode an uploaded picture (JPEG, PNG or WebP) to RGB on white, at most 512 px on its longer side,
    as Muse Image's pictures were stored before the experiment ink-cropped them. Raises DrawingError."""
    import io

    from PIL import ImageOps

    if not data:
        raise DrawingError("The upload is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DrawingError("That picture is too big. Please upload one under 3 MB.")
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ("JPEG", "PNG", "WEBP"):
            raise DrawingError("Please upload a JPEG, PNG or WebP picture.")
        w, h = img.size
        if w * h > MAX_UPLOAD_PIXELS:
            raise DrawingError("That picture has too many pixels. Please upload a smaller one.")
        if min(w, h) < 64:
            raise DrawingError("That picture is too small. Please upload one at least 64 pixels wide.")
        img.draft("RGB", (2 * UPLOAD_SIDE, 2 * UPLOAD_SIDE))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            img = Image.alpha_composite(white, rgba)
        img = img.convert("RGB")
    except DrawingError:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as e:
        raise DrawingError("We couldn't read that picture. Please upload a JPEG or PNG photo.") from e
    img.thumbnail((UPLOAD_SIDE, UPLOAD_SIDE), Image.LANCZOS)
    return img


def paper_stats(img: Image.Image) -> dict:
    """How much a picture looks like dark lines on plain paper.

    colour: share of strongly coloured pixels (saturation > 0.35, not dark) in the middle 60% of the picture,
    high for photos of things and colour illustrations; a wooden table around the paper doesn't count.
    ink, faint_ink and midtone: shares of dark (< 128), darkish (< 200) and mid-gray (128-215) pixels after
    the experiment's paper flattening, which turns plain paper, its texture and uneven light white;
    shading, texture and scenery are left behind as midtones and ink.
    span: how far the ink reaches across the picture (the smaller of its width and height shares), as
    ink_crop's crop box sees it; near 1 means the paper's edge or a table is in the photo."""
    from PIL import ImageFilter

    from metalesionlab.plato import flatten_paper

    hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255.0
    h, w = hsv.shape[:2]
    mid = hsv[int(h * 0.2):int(h * 0.8), int(w * 0.2):int(w * 0.8)]
    colour = float(np.mean((mid[..., 1] > 0.35) & (mid[..., 2] > 0.25)))
    gray = flatten_paper(img.convert("L"))
    flat = np.asarray(gray, dtype=np.float32)
    thick = flatten_paper(thicken(img).convert("L"))  # what ink_crop gets in prepare_upload
    box = thick.filter(ImageFilter.MaxFilter(3)).point(lambda v: 255 if v < 200 else 0).getbbox()
    span = min((box[2] - box[0]) / w, (box[3] - box[1]) / h) if box else 0.0
    return {"colour": round(colour, 4), "ink": round(float(np.mean(flat < 128)), 4),
            "faint_ink": round(float(np.mean(flat < 200)), 4),
            "midtone": round(float(np.mean((flat >= 128) & (flat < 215))), 4), "span": round(span, 4),
            "border": round(border_dark(img), 4)}


def border_dark(img: Image.Image) -> float:
    """Share of the outer 5% of the picture that is much darker (under 60%) than its middle: near 1 when
    the photo shows a table around the sheet, near 0 when the paper fills the photo (even in uneven light)."""
    g = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = g.shape
    b = max(2, int(0.05 * min(h, w)))
    middle = float(np.median(g[int(h * 0.3):int(h * 0.7), int(w * 0.3):int(w * 0.7)]))
    ring = np.concatenate([g[:b].ravel(), g[-b:].ravel(), g[:, :b].ravel(), g[:, -b:].ravel()])
    return float(np.mean(ring < 0.6 * middle))


def upload_problem(stats: dict) -> str | None:
    """A friendly reason the picture isn't a line drawing on plain paper, or None if it looks like one.
    `d_doodle`, once the picture is embedded, is its distance from the nearest kind of doodle."""
    if stats["faint_ink"] < MIN_INK:
        return NO_INK
    if stats.get("d_doodle", 0) > MAX_DOODLE_DISTANCE:
        return NOT_A_DRAWING
    if stats["colour"] > MAX_COLOUR or stats["ink"] > MAX_INK or stats["midtone"] > MAX_MIDTONE:
        return NOT_A_DRAWING
    if stats.get("span", 0) > MAX_SPAN or stats.get("border", 0) > MAX_BORDER:
        return EDGES
    return None


def thicken(img: Image.Image) -> Image.Image:
    """Widen dark lines by a pixel on each side. A pen line in a 512 px photo is often 1-2 px wide, and
    ink_crop ignores marks under 3 px (paper grain), so without this it would crop to a speck of grain."""
    from PIL import ImageFilter

    return img.filter(ImageFilter.MinFilter(3))


def prepare_upload(data: bytes) -> tuple[Image.Image, dict]:
    """Uploaded bytes -> (the picture DINOv2 sees, its paper statistics), or DrawingError with a friendly
    message. The same steps as Muse Image's pictures in the experiment (flatten the paper, crop to the
    ink), after widening thin pen lines by a pixel (thicken). The raw photo goes no further than this
    function; only the 256 px ink-cropped picture comes back."""
    img = load_upload(data)
    stats = paper_stats(img)
    problem = upload_problem(stats)
    if problem and problem != EDGES:  # a frame might still be a photo of a thing: decided once it's embedded
        raise DrawingError(problem)
    return ink_crop(thicken(img)), stats


def pixel_values(images: list[Image.Image]) -> np.ndarray:
    """The DINOv2 image processor in numpy: resize the shortest edge to 256 (bicubic), center-crop 224,
    scale to 0-1 and normalise with the ImageNet mean and std. Returns (n, 3, 224, 224) float32."""
    out = []
    for img in images:
        img = img.convert("RGB")
        w, h = img.size
        if min(w, h) != SIDE:
            r = SIDE / min(w, h)
            img = img.resize((max(SIDE, round(w * r)), max(SIDE, round(h * r))), Image.BICUBIC)
            w, h = img.size
        left, top = (w - CROP) // 2, (h - CROP) // 2
        a = np.asarray(img.crop((left, top, left + CROP, top + CROP)), dtype=np.float32) / 255.0
        out.append(((a - MEAN) / STD).transpose(2, 0, 1))
    return np.stack(out).astype(np.float32)


# ---------- embedders ----------

class OnnxEmbedder:
    """DINOv2-base CLS embeddings from the exported ONNX model, with onnxruntime on CPU."""

    backend = "onnx"

    def __init__(self, path: Path = MODEL_PATH, threads: int | None = None):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads or int(os.environ.get("DRAW_THREADS", "0"))
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0].name

    def __call__(self, images: list[Image.Image]) -> np.ndarray:
        out = self.session.run(None, {self.input: pixel_values(images)})[0]
        return out[:, 0] if out.ndim == 3 else out


class TorchEmbedder:
    """The experiment's own embedder (transformers + torch), forced onto the CPU."""

    backend = "torch"

    def __init__(self, threads: int | None = None):
        from metalesionlab.plato import Embedder

        self.embed = Embedder(DINO_MODEL, device="cpu")
        if threads:
            self.embed.torch.set_num_threads(threads)

    def __call__(self, images: list[Image.Image]) -> np.ndarray:
        return self.embed(images)["cls"]


def load_embedder(backend: str | None = None, path: Path | None = None):
    """ONNX when the model file is there (the deployed path), else torch if it is installed."""
    backend = backend or os.environ.get("DRAW_BACKEND", "auto")
    path = path or MODEL_PATH
    if backend == "onnx" or (backend == "auto" and path.exists()):
        return OnnxEmbedder(path)
    if backend in ("torch", "auto"):
        return TorchEmbedder()
    raise RuntimeError(f"Unknown DRAW_BACKEND {backend!r}")


class LazyEmbedder:
    """Builds the model on first use, once, behind a lock; later calls reuse it."""

    def __init__(self, factory=load_embedder):
        self.factory = factory
        self.model = None
        self.lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def get(self):
        with self.lock:
            if self.model is None:
                self.model = self.factory()
            return self.model


# ---------- reference data ----------

def pack(a: np.ndarray, dtype: str = "float32") -> dict:
    """An array as base64 of its little-endian bytes, with dtype and shape (compact in JSON)."""
    a = np.ascontiguousarray(a, dtype=np.dtype(dtype).newbyteorder("<"))
    return {"dtype": dtype, "shape": list(a.shape), "b64": base64.b64encode(a.tobytes()).decode()}


def pack_int8(x: np.ndarray) -> dict:
    """Rows as int8 with one float32 scale per row (unit vectors keep their nearest neighbours)."""
    x = np.asarray(x, dtype=np.float64)
    scale = np.abs(x).max(axis=1, keepdims=True) / 127.0
    scale[scale == 0] = 1.0
    out = pack(np.clip(np.rint(x / scale), -127, 127), "int8")
    out["scale"] = pack(scale[:, 0])
    return out


def unpack(d: dict) -> np.ndarray:
    raw = base64.b64decode(d["b64"])
    a = np.frombuffer(raw, dtype=np.dtype(d["dtype"]).newbyteorder("<")).reshape(d["shape"]).astype(np.float64)
    if "scale" in d:
        a = a * unpack(d["scale"])[:, None]
    return a


def unit(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def cosine_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """1 - cosine similarity between a (d,) or (n, d) and b (d,) or (m, d)."""
    return 1.0 - unit(a) @ unit(b).T


def percentile_below(value: float, reference) -> float:
    """Percent of the reference strictly below `value`, ties counted as half (0-100)."""
    ref = np.asarray(reference, dtype=np.float64)
    if ref.size == 0:
        return float("nan")
    below = np.count_nonzero(ref < value)
    ties = np.count_nonzero(ref == value)
    return float(100.0 * (below + 0.5 * ties) / ref.size)


@dataclass
class Concept:
    key: str
    label: str
    ai_centroid: np.ndarray     # mean of Muse Image's unit CLS vectors: its prototype
    human_centroid: np.ndarray  # mean of people's unit CLS vectors: the typical drawing
    pca_mean: np.ndarray        # the map: two principal axes of Muse's and people's vectors together
    pca_axes: np.ndarray        # (2, 768)
    ai: np.ndarray              # (n_ai, 768) unit vectors, for the nearest Muse doodle
    people: np.ndarray          # (n_human, 768)
    ai_loo: np.ndarray          # each Muse doodle's distance to the centroid of the other doodles
    human_loo: np.ndarray       # each person's distance to the centroid of the other people
    human_to_ai: np.ndarray     # each person's distance to Muse's centroid

    @classmethod
    def from_json(cls, entry: dict, vectors: dict) -> "Concept":
        return cls(entry["key"], entry["label"], unpack(vectors["ai_centroid"]), unpack(vectors["human_centroid"]),
                   unpack(vectors["pca_mean"]), unpack(vectors["pca_axes"]), unit(unpack(vectors["ai"])),
                   unit(unpack(vectors["people"])), np.asarray(entry["ai_loo"], float),
                   np.asarray(entry["human_loo"], float), np.asarray(entry["human_to_ai"], float))


def score(vec: np.ndarray, concept: Concept, library: tuple[list[str], np.ndarray] | None = None) -> dict:
    """Where one embedding lands among Muse's doodles and people's drawings of the same thing."""
    v = unit(np.asarray(vec, dtype=np.float64).reshape(-1))
    d_ai = float(1.0 - v @ unit(concept.ai_centroid))
    d_human = float(1.0 - v @ unit(concept.human_centroid))
    xy = (v - concept.pca_mean) @ concept.pca_axes.T
    sim_ai, sim_people = concept.ai @ v, concept.people @ v
    near_ai, near_human = int(np.argmax(sim_ai)), int(np.argmax(sim_people))
    out = {
        "concept": concept.key,
        "d_ai": round(d_ai, 4),
        "d_human": round(d_human, 4),
        # More original than X% of people: the share of people's drawings closer to the typical one than yours.
        "originality": round(percentile_below(d_human, concept.human_loo), 1),
        # The share of people's drawings that are closer to Muse's prototype than yours.
        "people_closer_to_muse": round(percentile_below(d_ai, concept.human_to_ai), 1),
        # The share of Muse's own doodles that are closer to its prototype than yours.
        "muse_closer": round(percentile_below(d_ai, concept.ai_loo), 1),
        "xy": [round(float(xy[0]), 4), round(float(xy[1]), 4)],
        "nearest_ai": near_ai,
        "nearest_human": near_human,
        "d_nearest_ai": round(float(1.0 - sim_ai[near_ai]), 4),
        "d_nearest_human": round(float(1.0 - sim_people[near_human]), 4),
    }
    if library is not None:
        keys, cents = library
        dist = 1.0 - unit(cents) @ v
        order = np.argsort(dist)
        ranked = [keys[i] for i in order]
        out["looks_like"] = ranked[:3]
        out["own_rank"] = ranked.index(concept.key) + 1 if concept.key in ranked else None
        out["d_doodle"] = round(float(dist[order[0]]), 4)  # how far from any kind of doodle at all
    return out


# ---------- abstract ideas: AI-only scoring ----------
# "Draw the invisible" (God, love, time...): Quick, Draw! has no people's drawings of these, so a drawing of an
# idea is placed among Muse Image's 16 doodles only. Nothing about people is computed or returned for them.

AI_ONLY = "ai_only"
IDEAS_PATH = DATA_PATH.parent / "draw_ideas.json"   # written by scripts/plato_ideas_web_export.py
AI_ONLY_FIELDS = {"concept", "mode", "d_ai", "muse_closer", "muse_closer_n", "muse_n", "nearest_ai", "d_nearest_ai",
                  "nearest_emblem"}


@dataclass
class IdeaConcept:
    key: str
    label: str
    ai_centroid: np.ndarray     # mean of Muse Image's unit CLS vectors: its idea of the thing
    ai: np.ndarray              # (n_ai, 768) unit vectors
    ai_loo: np.ndarray          # each Muse doodle's distance to the centroid of the other doodles
    emblems: list[str]          # each Muse doodle's emblem label (Muse Glimmer, precomputed)

    @classmethod
    def from_json(cls, entry: dict, vectors: dict) -> "IdeaConcept":
        return cls(entry["key"], entry["label"], unpack(vectors["ai_centroid"]), unit(unpack(vectors["ai"])),
                   np.asarray(entry["ai_loo"], float), list(entry["emblems"]))


def score_ai_only(vec: np.ndarray, concept: IdeaConcept) -> dict:
    """Where one embedding lands among Muse Image's doodles of an idea: its distance from Muse's prototype, how
    many of Muse's own doodles sit further from theirs (leave-one-out), and the nearest doodle with its emblem."""
    v = unit(np.asarray(vec, dtype=np.float64).reshape(-1))
    d_ai = float(1.0 - v @ unit(concept.ai_centroid))
    sim = concept.ai @ v
    near = int(np.argmax(sim))
    return {
        "concept": concept.key,
        "mode": AI_ONLY,
        "d_ai": round(d_ai, 4),
        # The share of Muse's own doodles that are closer to its prototype than yours (ties count half).
        "muse_closer": round(percentile_below(d_ai, concept.ai_loo), 1),
        # How many of Muse's own doodles sit closer to their prototype than yours does to it: "further from Muse's
        # idea of God than 14 of its 16 drawings".
        "muse_closer_n": int(np.count_nonzero(concept.ai_loo < d_ai)),
        "muse_n": int(len(concept.ai_loo)),
        "nearest_ai": near,
        "d_nearest_ai": round(float(1.0 - sim[near]), 4),
        "nearest_emblem": concept.emblems[near] if near < len(concept.emblems) else None,
    }


class Reference:
    """web/data/draw.json plus the per-concept vector files, parsed on first use and kept. The abstract ideas
    (draw_ideas.json beside it, when present) join the list with mode "ai_only"."""

    def __init__(self, index: dict, root: Path, ideas: dict | None = None):
        self.index = index
        self.root = Path(root)
        self.ideas = ideas or {}
        idea_entries = [{**c, "mode": AI_ONLY} for c in self.ideas.get("concepts", [])]
        self.entries = {c["key"]: c for c in index["concepts"] + idea_entries}
        lib = index.get("centroids") or {}
        self.library = (list(lib["keys"]), unpack(lib["vectors"])) if lib.get("keys") else None
        self.labels = lib.get("labels", {})
        self._concepts: dict[str, Concept | IdeaConcept] = {}
        self._lock = threading.Lock()

    @classmethod
    def load(cls, path: Path = DATA_PATH, ideas_path: Path | None = None) -> "Reference":
        path = Path(path)
        ideas_path = Path(ideas_path) if ideas_path else path.parent / IDEAS_PATH.name
        ideas = json.loads(ideas_path.read_text()) if ideas_path.is_file() else None
        return cls(json.loads(path.read_text()), path.parent, ideas)

    def ai_only(self, key: str) -> bool:
        return self.entries.get(key, {}).get("mode") == AI_ONLY

    def concept(self, key: str) -> Concept | IdeaConcept:
        with self._lock:
            if key not in self._concepts:
                entry = self.entries[key]
                vectors = json.loads((self.root / entry["vectors"]).read_text())
                kind = IdeaConcept if entry.get("mode") == AI_ONLY else Concept
                self._concepts[key] = kind.from_json(entry, vectors)
            return self._concepts[key]

    def score(self, key: str, vec: np.ndarray) -> dict:
        if self.ai_only(key):  # only the AI-only fields, whatever score_ai_only may grow
            return {k: v for k, v in score_ai_only(vec, self.concept(key)).items() if k in AI_ONLY_FIELDS}
        out = score(vec, self.concept(key), self.library)
        if "looks_like" in out:
            out["looks_like"] = [{"key": k, "label": self.labels.get(k, k)} for k in out["looks_like"]]
        return out

    def doodle_distance(self, vec: np.ndarray) -> float:
        """Distance from the nearest kind of doodle: people's centroids for the 35 things, and Muse's centroids
        for the ideas. Used only to refuse photos of things; never returned for an idea."""
        v = unit(np.asarray(vec, dtype=np.float64).reshape(-1))
        cents = [self.library[1]] if self.library else []
        cents += [self.concept(k).ai_centroid[None, :] for k in self.entries if self.ai_only(k)]
        if not cents:
            return 0.0
        return float((1.0 - unit(np.vstack(cents)) @ v).min())

    def public(self) -> dict:
        """What the page needs: labels, statistics, map points, distances and sprites (no 768-d vectors).
        Abstract ideas come after the things, marked mode "ai_only" and group "ideas"; the actions and qualities
        (running, something fast…) follow as group "words"."""
        out = {**{k: v for k, v in self.index.items() if k not in ("concepts", "centroids")},
               "concepts": [{k: v for k, v in c.items() if k != "vectors"} for c in self.index["concepts"]]}
        if self.ideas.get("concepts"):
            # group: "ideas" (Draw the invisible), or the entry's own ("words": an action or a quality)
            out["concepts"] += [{**{k: v for k, v in c.items() if k != "vectors"}, "mode": AI_ONLY,
                                 "group": c.get("group", "ideas")} for c in self.ideas["concepts"]]
            out["groups"] = self.ideas.get("groups", [])
            out["ideas_credits"] = self.ideas.get("credits", [])
        return out


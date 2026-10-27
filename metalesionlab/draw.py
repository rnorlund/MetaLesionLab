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
        order = np.argsort(1.0 - unit(cents) @ v)
        ranked = [keys[i] for i in order]
        out["looks_like"] = ranked[:3]
        out["own_rank"] = ranked.index(concept.key) + 1 if concept.key in ranked else None
    return out


class Reference:
    """web/data/draw.json plus the per-concept vector files, parsed on first use and kept."""

    def __init__(self, index: dict, root: Path):
        self.index = index
        self.root = Path(root)
        self.entries = {c["key"]: c for c in index["concepts"]}
        lib = index.get("centroids") or {}
        self.library = (list(lib["keys"]), unpack(lib["vectors"])) if lib.get("keys") else None
        self.labels = lib.get("labels", {})
        self._concepts: dict[str, Concept] = {}
        self._lock = threading.Lock()

    @classmethod
    def load(cls, path: Path = DATA_PATH) -> "Reference":
        path = Path(path)
        return cls(json.loads(path.read_text()), path.parent)

    def concept(self, key: str) -> Concept:
        with self._lock:
            if key not in self._concepts:
                entry = self.entries[key]
                vectors = json.loads((self.root / entry["vectors"]).read_text())
                self._concepts[key] = Concept.from_json(entry, vectors)
            return self._concepts[key]

    def score(self, key: str, vec: np.ndarray) -> dict:
        out = score(vec, self.concept(key), self.library)
        if "looks_like" in out:
            out["looks_like"] = [{"key": k, "label": self.labels.get(k, k)} for k in out["looks_like"]]
        return out

    def public(self) -> dict:
        """What the page needs: labels, statistics, map points, distances and sprites (no 768-d vectors)."""
        return {**{k: v for k, v in self.index.items() if k not in ("concepts", "centroids")},
                "concepts": [{k: v for k, v in c.items() if k != "vectors"} for c in self.index["concepts"]]}


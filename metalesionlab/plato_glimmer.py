"""Plato's Chair inside Glimmer: how spread out is each concept in Muse Glimmer's own representation,
and does that spread predict how hard the concept is to name and how easily naming breaks under damage?

The core Plato's Chair experiment (metalesionlab/plato.py, another branch) asks Muse Image for 16
doodles per concept and measures within-concept spread with DINOv2, next to human doodles from
Google Quick, Draw!. This module gives the same pictures to Muse Glimmer:

  1. Every picture is padded to a square and resized to SIDE px (so AI and human doodles cost the
     same number of image tokens) and prompted with "Name the object in this picture with exactly
     one word.", with the answer channel pre-filled (glimmer.build_inputs).
  2. One prefill pass records, at the answer position, the residual stream after every decoder
     layer (model_lab.generate_with_lens), and a hook records the vision tower's output (the input
     to vision_adapter, 6,144 channels after pixel shuffle) and the projector's output, each
     mean-pooled over the picture's image tokens. Greedy decoding then writes the answer.
  3. The answer is coded with the Philadelphia Naming Test rules (model_lab.code_answer).
  4. Word lens: after every layer, p(correct first token) and whether the correct name is the top
     guess. "First correct layer" is the first layer whose top guess is the correct name.

Spread = mean pairwise cosine distance among a concept's pictures, the same measure the core
experiment uses on DINOv2. Glimmer's hidden states share a large common direction, so vectors are
centered on the mean over every picture before the cosine ("centered"); the raw cosine is kept too.

Human drawings: Google Creative Lab, "The Quick, Draw! Dataset",
https://github.com/googlecreativelab/quickdraw-dataset, CC BY 4.0.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

QUICKDRAW_CREDIT = ("Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0, "
                    "https://github.com/googlecreativelab/quickdraw-dataset")
PROMPT = "Name the object in this picture with exactly one word."
SIDE = 448  # 32 x 32 patches of 14 px -> 256 image tokens after the 2x2 merge
# Decoder layers reported by name, 1-indexed as in the word-lens chart (layer 52 is the last).
NAMED_LAYERS = (13, 26, 39, 46, 52)
SOURCES = ("ai", "human")

# Accepted names per concept key (the core experiment's folder names). The target is the label the
# core experiment uses in its figures; alternates are the Quick, Draw! category and common names for
# the same object. Plurals, articles and modifiers are accepted by the scorer ("smiley face" -> face).
NAMES: dict[str, tuple[str, tuple[str, ...]]] = {
    "cat": ("cat", ("kitten", "kitty")), "umbrella": ("umbrella", ()), "ladder": ("ladder", ()),
    "bench": ("bench", ()), "spoon": ("spoon", ()), "carrot": ("carrot", ()),
    "bicycle": ("bicycle", ("bike",)), "scissors": ("scissors", ()), "candle": ("candle", ()),
    "helicopter": ("helicopter", ()), "pineapple": ("pineapple", ()), "snail": ("snail", ()),
    "saw": ("saw", ("handsaw",)), "cactus": ("cactus", ()), "harp": ("harp", ()),
    "chair": ("chair", ()), "sailboat": ("boat", ("sailboat", "ship", "sailing")),
    "house": ("house", ("home",)), "car": ("car", ("automobile",)), "tree": ("tree", ()),
    "flower": ("flower", ()), "dog": ("dog", ("puppy",)), "bird": ("bird", ()), "fish": ("fish", ()),
    "cup": ("cup", ("mug",)), "shoe": ("shoe", ("sneaker",)), "hat": ("hat", ()), "key": ("key", ()),
    "clock": ("clock", ()), "floor_lamp": ("lamp", ()), "book": ("book", ()), "guitar": ("guitar", ()),
    "apple": ("apple", ()), "face": ("face", ("smiley",)),
    "yoga": ("person", ("yoga", "human", "man", "woman", "figure", "stickman", "people")),
    "teapot": ("teapot", ()), "star": ("star", ()), "table": ("table", ()), "sandwich": ("sandwich", ()),
    "dragon": ("dragon", ()),
}


def names_for(key: str) -> tuple[str, tuple[str, ...]]:
    return NAMES.get(key, (key.replace("_", " "), ()))


# --- pictures ---------------------------------------------------------------------------

@dataclass
class Picture:
    key: str      # concept folder name
    source: str   # "ai" or "human"
    path: str
    index: int    # position within (key, source)

    @property
    def target(self) -> str:
        return names_for(self.key)[0]

    @property
    def alternates(self) -> tuple[str, ...]:
        return names_for(self.key)[1]


def _sorted_pngs(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.png"), key=lambda p: (len(p.stem), p.stem))


def collect_pictures(plato_dir: Path, per_source: int = 16, style: str = "doodle", keys: list[str] | None = None,
                     human_seed: int = 0, min_per_source: int = 12) -> list[Picture]:
    """Up to `per_source` AI doodles (<plato_dir>/ai/<style>/<key>/) and the same number of human
    doodles (<plato_dir>/human/<key>/, a seeded random sample of the pool) for every concept with at
    least `min_per_source` of each. The AI and human counts always match within a concept."""
    ai_root, human_root = Path(plato_dir) / "ai" / style, Path(plato_dir) / "human"
    if keys is None:
        keys = sorted(p.name for p in ai_root.iterdir() if p.is_dir()) if ai_root.exists() else []
    rng = np.random.default_rng(human_seed)
    out = []
    for key in keys:
        ai, human = _sorted_pngs(ai_root / key), _sorted_pngs(human_root / key)
        n = min(per_source, len(ai), len(human))
        if n < min_per_source:
            continue
        human = [human[i] for i in sorted(rng.choice(len(human), n, replace=False))]
        out += [Picture(key, "ai", str(p), i) for i, p in enumerate(ai[:n])]
        out += [Picture(key, "human", str(p), i) for i, p in enumerate(human)]
    return out


def square(img, side: int = SIDE):
    """Pad to a white square, then resize to side x side, so every picture has the same token count."""
    from PIL import Image

    img = img.convert("RGB")
    w, h = img.size
    s = max(w, h)
    canvas = Image.new("RGB", (s, s), "white")
    canvas.paste(img, ((s - w) // 2, (s - h) // 2))
    return canvas.resize((side, side), Image.LANCZOS)


# --- the GPU pass -----------------------------------------------------------------------

def image_token_counts(grid_thw, merge: int) -> list[int]:
    return [int(t * h * w) // (merge * merge) for t, h, w in grid_thw.tolist()]


class VisionTap:
    """Mean-pools the vision tower output (vision_adapter input) and the projector output over each
    picture's image tokens."""

    def __init__(self, model):
        self.model, self.merge = model, model.config.vision_config.merge_size
        self.counts: list[int] = []
        self.tower, self.projector = [], []
        self.hooks = []

    def _split(self, x):
        x = x.reshape(-1, x.shape[-1])
        if sum(self.counts) != x.shape[0]:
            raise RuntimeError(f"image tokens {x.shape[0]} != expected {sum(self.counts)} from image_grid_thw")
        return [chunk.float().mean(0).cpu() for chunk in x.split(self.counts)]

    def __enter__(self):
        m = self.model.model
        self.hooks = [
            m.vision_adapter.register_forward_pre_hook(lambda _m, a: self.tower.extend(self._split(a[0]))),
            m.vision_projection.register_forward_hook(lambda _m, _a, out: self.projector.extend(self._split(out))),
        ]
        return self

    def __exit__(self, *exc):
        for h in self.hooks:
            h.remove()


def name_variants(tokenizer, words: tuple[str, ...]) -> list[list[int]]:
    """Token sequences for every accepted name, lower-case and capitalized, with and without a
    leading space (the answer starts right after the pre-filled '<|message|>')."""
    seqs = []
    for w in words:
        for v in (w, w.capitalize(), " " + w, " " + w.capitalize()):
            ids = tokenizer(v, add_special_tokens=False)["input_ids"]
            if ids and ids not in seqs:
                seqs.append(ids)
    return seqs


def top_tokens(model, tokenizer, resid) -> list[list[str]]:
    """Word-lens top guess (one token) at the answer position after every layer, per row of (B, L, H)."""
    import torch

    from metalesionlab import glimmer

    norm = model.model.language_model.norm
    out = []
    for row in resid:
        ids = glimmer.output_logits(model, norm(row)).argmax(-1).tolist()
        out.append([tokenizer.decode([i]).strip() or tokenizer.decode([i]) for i in ids])
        del ids
    torch.cuda.empty_cache()
    return out


def _no_grad(fn):
    """torch.no_grad() as a decorator, importing torch lazily so the analysis side runs without it."""
    def wrapped(*a, **kw):
        import torch

        with torch.no_grad():
            return fn(*a, **kw)
    wrapped.__name__, wrapped.__doc__ = fn.__name__, fn.__doc__
    return wrapped


@_no_grad
def name_with_word_lens(model, batch: dict, stop_ids: set[int], variants: list[list[list[int]]],
                        lens_layers: list[int] | None = None, max_new_tokens: int = 8):
    """One batch: prefill, full-word lens for every accepted name, then greedy decoding.

    Word lens for a multi-token name ("S|poon"): each name is fed after the prompt through the
    prefill's KV cache (which is then cropped back), and at each lens layer l
        log p_l(name) = sum_k log softmax(lens_l(h at the position before token k))[token k]
    where lens_l is the final norm and output head applied to the residual stream after layer l.
    The name is the layer's top guess when every one of its tokens is the argmax there. Per picture
    p_l = the sum over its accepted names and spellings (distinct token sequences).

    variants[b]: token sequences of row b's accepted names. lens_layers: 0-indexed decoder layers
    to read (default all). Returns (answer tokens per row, answer-position residual stream (B, L, H),
    per-row dicts with "p_word" and "word_top" lists over lens_layers)."""
    import torch

    from metalesionlab import glimmer

    layers = glimmer.decoder_layers(model)
    lens_layers = list(range(len(layers))) if lens_layers is None else lens_layers
    norm = model.model.language_model.norm
    state = {"mode": "prefill", "h": []}

    def grab(_m, _i, out):
        if state["mode"] == "decode":
            return
        h = out[0] if isinstance(out, tuple) else out
        state["h"].append(h[:, -1].detach() if state["mode"] == "prefill" else h.detach())

    hooks = [layer.register_forward_hook(grab) for layer in layers]
    try:
        out = model(**batch, use_cache=True, logits_to_keep=1)
        resid = torch.stack(state["h"], dim=1)  # (B, L, H) at the answer position
        cache, mask, last_pos = out.past_key_values, batch["attention_mask"], batch["position_ids"][:, -1:]
        B = resid.shape[0]
        n_slots = max(len(v) for v in variants)
        logp = torch.full((B, n_slots, len(lens_layers)), float("-inf"), device=resid.device)
        is_top = torch.zeros((B, n_slots, len(lens_layers)), dtype=torch.bool, device=resid.device)
        pad = 0
        for j in range(n_slots):
            seqs = [v[j] if j < len(v) else [] for v in variants]
            T = max(len(s) for s in seqs)
            if T > 1:  # positions after the first token need their own forward pass
                ids = torch.tensor([s + [pad] * (T - len(s)) for s in seqs], device=resid.device)
                state["mode"], state["h"] = "cont", []
                model(input_ids=ids[:, :-1], attention_mask=torch.cat([mask, torch.ones_like(ids[:, :-1])], 1),
                      position_ids=last_pos + 1 + torch.arange(T - 1, device=ids.device), past_key_values=cache,
                      use_cache=True, logits_to_keep=1)
                cont = torch.stack(state["h"], dim=1)  # (B, L, T-1, H)
                cache.crop(-(T - 1))
            for b, s in enumerate(seqs):
                if not s:
                    continue
                h = resid[b, lens_layers].unsqueeze(1)  # (l, 1, H)
                if len(s) > 1:
                    h = torch.cat([h, cont[b, lens_layers, :len(s) - 1]], dim=1)  # (l, len, H)
                lp = torch.log_softmax(glimmer.output_logits(model, norm(h)), dim=-1)  # (l, len, V)
                tok = torch.tensor(s, device=lp.device)
                logp[b, j] = lp.gather(-1, tok.view(1, -1, 1).expand(lp.shape[0], -1, 1)).squeeze(-1).sum(-1)
                is_top[b, j] = (lp.argmax(-1) == tok.view(1, -1)).all(-1)
                del lp
        # greedy decoding from the (cropped) prefill cache
        state["mode"] = "decode"
        nxt = out.logits[:, -1].argmax(-1)
        tokens, pos = [nxt], last_pos
        stop = torch.tensor(sorted(stop_ids), device=nxt.device)
        done = torch.isin(nxt, stop)
        for _ in range(max_new_tokens - 1):
            if bool(done.all()):
                break
            mask = torch.cat([mask, torch.ones_like(mask[:, :1])], dim=1)
            pos = pos + 1
            o = model(input_ids=nxt[:, None], attention_mask=mask, position_ids=pos, past_key_values=cache,
                      use_cache=True)
            nxt = o.logits[:, -1].argmax(-1)
            tokens.append(nxt)
            done |= torch.isin(nxt, stop)
    finally:
        for h in hooks:
            h.remove()
    rows = torch.stack(tokens, dim=1).tolist()
    cut = [row[:next((k for k, t in enumerate(row) if t in stop_ids), len(row))] for row in rows]
    p_word = logp.exp().sum(1)  # (B, l)
    word_top = is_top.any(1)
    lens = [{"p_word": p_word[b].tolist(), "word_top": word_top[b].tolist()} for b in range(B)]
    return cut, resid, lens


def first_correct_layer(top_is_correct: list[bool], stable: bool = False) -> int | None:
    """1-indexed first layer whose top guess is the correct name (None if never). With stable, the
    first layer from which it stays the top guess to the last layer."""
    if stable:
        k = len(top_is_correct)
        while k > 0 and top_is_correct[k - 1]:
            k -= 1
        return k + 1 if k < len(top_is_correct) else None
    return next((i + 1 for i, ok in enumerate(top_is_correct) if ok), None)


@dataclass
class Probe:
    """The pictures, tokenized once in fixed-size batches; run() gives one condition."""
    pictures: list[Picture]
    batches: list[dict]
    variants: list[list[list[int]]]  # per picture: token sequences of its accepted names
    meta: dict = field(default_factory=dict)

    @classmethod
    def build(cls, processor, pictures: list[Picture], batch_size: int = 16, side: int = SIDE) -> Probe:
        from PIL import Image

        from metalesionlab.model_lab import build_batches

        examples = [(square(Image.open(p.path), side), PROMPT) for p in pictures]
        tok = processor.tokenizer
        variants = [name_variants(tok, (p.target, *p.alternates)) for p in pictures]
        return cls(pictures, build_batches(processor, examples, batch_size), variants,
                   {"side": side, "batch_size": batch_size, "prompt": PROMPT})

    def run(self, model, processor, spec=None, stats=None, capture: bool = False, max_new_tokens: int = 8,
            condition: str = "", full_lens: bool = False, keep_tops: bool = False) -> dict:
        """One condition. full_lens reads the word lens after every layer (else only the last).
        With capture, also returns the answer-position residual stream after every decoder layer
        (N, L, H) and the pooled vision tower / projector embeddings, as float16 numpy."""
        import torch

        from metalesionlab.lesions import LesionSpec, lesion, site_dims
        from metalesionlab.model_lab import code_answer, response_flags, stop_token_ids, to_device

        spec = spec if isinstance(spec, LesionSpec) else LesionSpec.from_dict(spec or {})
        tok, stops = processor.tokenizer, stop_token_ids(model, processor.tokenizer)
        n_layers = len(model.model.language_model.layers)
        lens_layers = list(range(n_layers)) if full_lens else [n_layers - 1]
        bs = self.meta["batch_size"]
        rows, hidden = [], []
        tap = VisionTap(model)
        torch.cuda.synchronize()
        t0 = time.time()
        with lesion(model, spec, stats):
            for b, batch in enumerate(self.batches):
                start, n = b * bs, batch["input_ids"].shape[0]
                tap.counts = image_token_counts(batch["image_grid_thw"], tap.merge)
                dev_batch = to_device(batch, model.device)
                variants = self.variants[start:start + n]
                if capture:
                    with tap:
                        tokens, resid, lens = name_with_word_lens(model, dev_batch, stops, variants, lens_layers,
                                                                  max_new_tokens)
                    hidden.append(resid.to(torch.float16).cpu())
                else:
                    tokens, resid, lens = name_with_word_lens(model, dev_batch, stops, variants, lens_layers,
                                                              max_new_tokens)
                tops = top_tokens(model, tok, resid) if keep_tops else None
                for k in range(n):
                    pic = self.pictures[start + k]
                    said = tok.decode(tokens[k], skip_special_tokens=True).strip()
                    c = code_answer(pic.target, said, "en", pic.alternates)
                    lk = lens[k]
                    row = {"i": start + k, "key": pic.key, "source": pic.source, "said": said, "code": c.code,
                           "head": c.head, "flags": response_flags(said, PROMPT),
                           "p_word_final": _sig(lk["p_word"][-1])}
                    if full_lens:
                        row["p_word"] = [_sig(p) for p in lk["p_word"]]
                        row["first_correct_layer"] = first_correct_layer(lk["word_top"])
                        row["stable_correct_layer"] = first_correct_layer(lk["word_top"], stable=True)
                    if tops is not None:
                        row["top"] = tops[k]
                    rows.append(row)
        torch.cuda.synchronize()
        seconds = time.time() - t0
        acc = sum(r["code"] == "Correct" for r in rows) / max(len(rows), 1)
        result = {"condition": condition or spec.name or ("intact" if spec.is_intact else "lesion"),
                  "spec": spec.to_dict(units=False), "units": spec.counts(site_dims(model)),
                  "n": len(rows), "accuracy": round(acc, 4), "seconds": round(seconds, 1), **self.meta,
                  "items": rows}
        if capture:
            result["_arrays"] = {"resid": torch.cat(hidden).numpy(),
                                 "vision_tower": torch.stack(tap.tower).to(torch.float16).numpy(),
                                 "projector": torch.stack(tap.projector).to(torch.float16).numpy()}
        return result


def _sig(x: float, digits: int = 3) -> float:
    return float(f"{x:.{digits}g}") if x and math.isfinite(x) else 0.0


# --- spread -----------------------------------------------------------------------------

def cosine_distance_matrix(x: np.ndarray, center: np.ndarray | None = None) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if center is not None:
        x = x - center
    xn = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)
    return 1.0 - xn @ xn.T


def spread(d: np.ndarray) -> float:
    """Mean pairwise distance among distinct pictures."""
    return float(d[np.triu_indices(len(d), 1)].mean())


def bootstrap_spread(d: np.ndarray, reps: int = 2000, rng: np.random.Generator | None = None) -> np.ndarray:
    """Resample pictures with replacement; a picture drawn twice is never paired with itself
    (the same estimator as the core experiment's DINOv2 spread)."""
    rng = rng or np.random.default_rng(0)
    n = len(d)
    out = np.empty(reps)
    for b in range(reps):
        c = np.bincount(rng.integers(0, n, n), minlength=n).astype(float)
        w = np.outer(c, c)
        np.fill_diagonal(w, 0)
        out[b] = (w * d).sum() / w.sum()
    return out


def concept_distance_matrices(emb: np.ndarray, pictures: list[Picture], centered: bool = True
                              ) -> dict[tuple[str, str], np.ndarray]:
    """Distance matrices per (key, source) for one embedding space (N, D)."""
    center = emb.astype(np.float64).mean(0) if centered else None
    groups: dict[tuple[str, str], list[int]] = {}
    for i, p in enumerate(pictures):
        groups.setdefault((p.key, p.source), []).append(i)
    return {g: cosine_distance_matrix(emb[idx], center) for g, idx in groups.items()}


# --- statistics -------------------------------------------------------------------------

def ci(x, level: float = 0.95) -> list[float]:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    a = (1 - level) / 2
    return [float(np.quantile(x, a)), float(np.quantile(x, 1 - a))] if len(x) else [float("nan")] * 2


def _ranks(a: np.ndarray) -> np.ndarray:
    """Average ranks along the last axis (ties share a rank)."""
    from scipy.stats import rankdata

    return rankdata(a, axis=-1)


def _center(a: np.ndarray) -> np.ndarray:
    return a - a.mean(-1, keepdims=True)


def _pearson_rows(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a, b = _center(a), _center(b)
    den = np.sqrt((a * a).sum(-1) * (b * b).sum(-1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 1e-12, (a * b).sum(-1) / np.where(den > 1e-12, den, 1.0), np.nan)


def _residualize(r: np.ndarray, z: np.ndarray) -> np.ndarray:
    r, z = _center(r), _center(z)
    zz = (z * z).sum(-1, keepdims=True)
    beta = (r * z).sum(-1, keepdims=True) / np.where(zz > 0, zz, 1.0)
    return r - beta * z


def rho_rows(x: np.ndarray, y: np.ndarray, z: np.ndarray | None = None) -> np.ndarray:
    """Spearman's rho per row of (R, n) arrays; partial on z (rank-linear) when given."""
    rx, ry = _ranks(x), _ranks(y)
    if z is not None:
        rz = _ranks(z)
        rx, ry = _residualize(rx, rz), _residualize(ry, rz)
    return _pearson_rows(rx, ry)


def spearman(x, y, z=None) -> float:
    x, y = np.asarray(x, float)[None], np.asarray(y, float)[None]
    return float(rho_rows(x, y, None if z is None else np.asarray(z, float)[None])[0])


def _finite(*cols):
    cols = [np.asarray(c, float) for c in cols]
    ok = np.all([np.isfinite(c) for c in cols], axis=0)
    return [c[ok] for c in cols]


def spearman_ci(x, y, z=None, reps: int = 4000, seed: int = 0) -> dict:
    """Spearman's rho (partial on z if given), a percentile bootstrap CI over concepts and a
    two-sided permutation p (y shuffled). Concepts with a non-finite value are dropped."""
    rng = np.random.default_rng(seed)
    cols = _finite(x, y) if z is None else _finite(x, y, z)
    n = len(cols[0])
    if n < 5:
        return {"rho": float("nan"), "ci95": [float("nan")] * 2, "p_perm": float("nan"), "n": int(n)}
    x, y = cols[0], cols[1]
    z = cols[2] if len(cols) == 3 else None
    rho = spearman(x, y, z)
    i = rng.integers(0, n, (reps, n))
    boots = rho_rows(x[i], y[i], None if z is None else z[i])
    perm_y = np.stack([rng.permutation(y) for _ in range(reps)])
    perm = rho_rows(np.broadcast_to(x, perm_y.shape), perm_y, None if z is None else np.broadcast_to(z, perm_y.shape))
    perm = perm[np.isfinite(perm)]
    p = float(((np.abs(perm) >= abs(rho) - 1e-12).sum() + 1) / (len(perm) + 1))
    return {"rho": rho, "ci95": ci(boots), "p_perm": p, "n": int(n)}


def rho_difference(x, y1, y2, reps: int = 4000, seed: int = 0) -> dict:
    """rho(x, y1) - rho(x, y2) with a paired bootstrap CI over concepts (e.g. targeted lesion vs
    random-unit control)."""
    rng = np.random.default_rng(seed)
    x, y1, y2 = _finite(x, y1, y2)
    n = len(x)
    diff = spearman(x, y1) - spearman(x, y2)
    i = rng.integers(0, n, (reps, n))
    boots = rho_rows(x[i], y1[i]) - rho_rows(x[i], y2[i])
    return {"diff": diff, "ci95": ci(boots), "n": int(n)}


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, Picture):
        return asdict(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return round(v, 4) if math.isfinite(v) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def save_json(obj, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(to_jsonable(obj), ensure_ascii=False, separators=(",", ":")))
    return path

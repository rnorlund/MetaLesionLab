"""Functional localizers: find the units that respond more in one condition than in another.

This is the LLM version of an fMRI localizer and needs forward passes only. Each trial is one
prompt; a unit's activity is read at the answer position (the last prompt token, right before
the answer is written):
  MLP neuron      |a|, the magnitude of its input to down_proj, i.e. how strongly it writes to
                  the residual stream (the sign only flips the direction it writes)
  attention head  the L2 norm of its 128-dim gated output slice (the input to o_proj)
Each unit's mean and variance are streamed per condition, Welch's t is computed for A > B, and
units are ranked by t across all layers. top_units() keeps the top fraction (positive t only).

Contrasts (A > B):
  naming    naming the picture  >  yes/no verification of the same picture
            ("Is this a cat? Answer yes or no."); the reverse ranking is a comprehension localizer
  visual    the intact picture  >  the same picture with its tiles shuffled (naming prompt for both)
  language  simple sentences  >  the same words in scrambled order (text only)

Pictures for the localizer should not be the test pictures (double dipping): localizer_images()
returns a set's candidate drawings that were not kept for the test.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import torch
from PIL import Image

from metalesionlab import glimmer
from metalesionlab.lesions import LesionSpec, Moments, SiteDims, Units, site_dims
from metalesionlab.model_lab import build_batches, naming_prompt, to_device, verify_prompt

CONTRASTS = ("naming", "visual", "language")

# Written for this project: short, plain sentences with concrete words.
SENTENCES = [
    "The cat sleeps on the warm windowsill.", "My brother rides his bike to school.",
    "She poured fresh milk into a glass.", "The old man walked his dog in the park.",
    "We ate soup and bread for dinner.", "A small bird sang outside the kitchen window.",
    "The children played soccer after lunch.", "He forgot his umbrella on the train.",
    "Rain fell softly on the green hills.", "The baker opens the shop at six.",
    "Our neighbor painted the fence bright blue.", "The teacher read a story to the class.",
    "A red boat floated near the shore.", "My sister planted carrots in the garden.",
    "The doctor listened to her heartbeat.", "They watched the sun set over the lake.",
    "The farmer fed the horses in the barn.", "I found my keys under the sofa.",
    "The train arrived late this morning.", "Grandma knitted a scarf for winter.",
    "The puppy chewed a hole in my shoe.", "We built a snowman in the yard.",
    "The pilot landed the plane safely.", "A cold wind blew through the trees.",
    "He fixed the broken chair with glue.", "The museum opens again next week.",
    "She wrote a letter to her friend.", "The kids splashed in the swimming pool.",
    "Dad cooked pancakes on Sunday morning.", "The library was quiet and warm.",
    "A spider spun a web in the corner.", "The nurse gave the boy a sticker.",
    "We climbed the hill to see the city.", "The candle burned slowly on the table.",
    "My friend sent me a funny picture.", "The cook sliced the onions very thin.",
    "Snow covered the roofs of the houses.", "The girl lost her mitten at the park.",
    "A truck delivered the new washing machine.", "The band played music until midnight.",
]


def scramble_words(sentence: str, rng: random.Random) -> str:
    """The same words in a random order that differs from the original."""
    words = sentence.rstrip(".").lower().split()
    shuffled = words[:]
    for _ in range(20):
        rng.shuffle(shuffled)
        if shuffled != words:
            break
    return " ".join(shuffled)


def scramble_tiles(image: Image.Image, grid: int = 8, side: int = 512, seed: int = 0) -> Image.Image:
    """Cut the picture into grid x grid tiles and shuffle them: local features stay, the object goes."""
    img = image.convert("RGB").resize((side, side))
    t = side // grid
    tiles = [img.crop((x * t, y * t, (x + 1) * t, (y + 1) * t)) for y in range(grid) for x in range(grid)]
    random.Random(seed).shuffle(tiles)
    out = Image.new("RGB", (t * grid, t * grid), "white")
    for k, tile in enumerate(tiles):
        out.paste(tile, ((k % grid) * t, (k // grid) * t))
    return out


@dataclass
class Trial:
    word: str
    lang: str
    image: Path


def localizer_images(set_dirs: list[Path], held_out: bool = True) -> list[Trial]:
    """Candidate drawings from Test Studio sets; with held_out, only those not kept as test items."""
    trials = []
    for set_dir in set_dirs:
        manifest = json.loads((Path(set_dir) / "manifest.json").read_text())
        for it in manifest["items"]:
            for cand in it.get("candidates", []):
                if held_out and cand["file"] == it.get("image"):
                    continue
                trials.append(Trial(it["word"], it.get("lang", manifest.get("lang", "en")), Path(set_dir) / cand["file"]))
    return trials


def contrast_examples(contrast: str, trials: list[Trial] | None = None, seed: int = 0
                      ) -> tuple[list[tuple[Image.Image | None, str]], list[tuple[Image.Image | None, str]]]:
    """(condition A, condition B) lists of (image or None, prompt)."""
    if contrast == "language":
        rng = random.Random(seed)
        return [(None, s) for s in SENTENCES], [(None, scramble_words(s, rng)) for s in SENTENCES]
    images = [(t, Image.open(t.image).convert("RGB")) for t in trials or []]
    if contrast == "naming":
        return ([(img, naming_prompt(t.lang)) for t, img in images],
                [(img, verify_prompt(t.lang, t.word)) for t, img in images])
    if contrast == "visual":
        return ([(img, naming_prompt(t.lang)) for t, img in images],
                [(scramble_tiles(img, seed=seed + k), naming_prompt(t.lang)) for k, (t, img) in enumerate(images)])
    raise ValueError(f"unknown contrast {contrast!r}; known: {CONTRASTS}")


# --- activity statistics ----------------------------------------------------------------

@torch.no_grad()
def answer_activity(model, batches: list[dict]) -> dict[str, Moments]:
    """Stream every unit's activity at the answer position over the batches."""
    dims, dev = site_dims(model), model.device
    mlp = Moments((dims.n_layers, dims.mlp), dev)
    heads = Moments((dims.n_layers, dims.heads), dev)
    cur = {}

    def on_mlp(i):
        def hook(_m, args):
            cur.setdefault("mlp", [None] * dims.n_layers)[i] = args[0][:, -1].abs()
        return hook

    def on_heads(i):
        def hook(_m, args):
            x = args[0][:, -1].float()
            cur.setdefault("heads", [None] * dims.n_layers)[i] = x.view(x.shape[0], dims.heads, dims.head_dim).norm(dim=-1)
        return hook

    hooks = []
    for i, layer in enumerate(glimmer.decoder_layers(model)):
        hooks.append(layer.mlp.down_proj.register_forward_pre_hook(on_mlp(i)))
        hooks.append(layer.self_attn.o_proj.register_forward_pre_hook(on_heads(i)))
    try:
        for batch in batches:
            cur.clear()
            model(**to_device(batch, model.device), logits_to_keep=1)
            mlp.add(torch.stack(cur["mlp"], dim=1))
            heads.add(torch.stack(cur["heads"], dim=1))
    finally:
        for h in hooks:
            h.remove()
    return {"mlp": mlp, "heads": heads}


def welch_t(a: Moments, b: Moments) -> torch.Tensor:
    """Welch's t for mean(A) > mean(B), per unit. Units silent in both conditions get t = 0."""
    (ma, va), (mb, vb) = a.mean_var(), b.mean_var()
    se = (va / max(a.n, 1) + vb / max(b.n, 1)).sqrt()
    t = (ma - mb) / se.clamp_min(1e-12)
    return torch.where(se > 0, t, torch.zeros_like(t)).float()


@dataclass
class Localizer:
    name: str  # e.g. "naming" or "naming@demo_en"
    t: dict[str, torch.Tensor]  # "mlp": (layers, neurons), "heads": (layers, heads)
    n_a: int = 0
    n_b: int = 0
    meta: dict = field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({"name": self.name, "t": {k: v.half().cpu() for k, v in self.t.items()},
                    "n_a": self.n_a, "n_b": self.n_b, "meta": self.meta}, path)

    @classmethod
    def load(cls, path: Path) -> Localizer:
        d = torch.load(path, map_location="cpu")
        return cls(d["name"], {k: v.float() for k, v in d["t"].items()}, d["n_a"], d["n_b"], d["meta"])

    def summary(self, fracs: tuple[float, ...] = (0.001, 0.01, 0.05)) -> dict:
        """Small JSON for the web UI: head t-map, and per layer how many of the top units it holds."""
        out = {"name": self.name, "n_a": self.n_a, "n_b": self.n_b, **self.meta,
               "heads_t": [[round(x, 2) for x in row] for row in self.t["heads"].tolist()],
               "mlp_max_t_by_layer": [round(x, 2) for x in self.t["mlp"].max(dim=1).values.tolist()]}
        for kind in ("mlp", "heads"):
            for f in fracs:
                units = top_units(self.t[kind], f)
                out[f"{kind}_top{f:g}_by_layer"] = [len(units.get(i, [])) for i in range(self.t[kind].shape[0])]
        return out


def run_contrast(model, processor, contrast: str, trials: list[Trial] | None = None, batch_size: int = 10,
                 seed: int = 0, name: str = "") -> Localizer:
    a_ex, b_ex = contrast_examples(contrast, trials, seed)
    a = answer_activity(model, build_batches(processor, a_ex, batch_size))
    b = answer_activity(model, build_batches(processor, b_ex, batch_size))
    t = {kind: welch_t(a[kind], b[kind]) for kind in ("mlp", "heads")}
    return Localizer(name or contrast, t, a["mlp"].n, b["mlp"].n, {"contrast": contrast, "seed": seed})


# --- picking units ----------------------------------------------------------------------

def top_units(t: torch.Tensor, frac: float, direction: int = 1) -> Units:
    """The top `frac` of all units (across layers) by t, keeping only t > 0 in `direction`."""
    flat = (t * direction).flatten()
    k = min(int(round(frac * flat.numel())), int((flat > 0).sum()))
    if k <= 0:
        return {}
    idx = flat.topk(k).indices
    layer, unit = idx // t.shape[1], idx % t.shape[1]
    out: Units = {}
    for l, u in zip(layer.tolist(), unit.tolist()):
        out.setdefault(l, []).append(u)
    return {l: sorted(v) for l, v in sorted(out.items())}


def random_like(units: Units, size: int, seed: int = 0, exclude: bool = True) -> Units:
    """Random units with the same count in each layer; with exclude, never one of `units`."""
    rng = random.Random(seed)
    out = {}
    for layer, idx in units.items():
        chosen = set(idx or [])
        pool = [u for u in range(size) if not (exclude and u in chosen)]
        n = size if idx is None else len(idx)
        out[layer] = sorted(rng.sample(pool, min(n, len(pool))))
    return out


def localizer_spec(loc: Localizer, kind: str, frac: float, method: str = "zero", direction: int = 1,
                   noise_scale: float = 1.0, seed: int = 0) -> LesionSpec:
    units = top_units(loc.t[kind], frac, direction)
    tag = loc.name if direction == 1 else f"{loc.name}-reversed"
    return LesionSpec(method=method, noise_scale=noise_scale, seed=seed,
                      name=f"{tag} top {frac:.3g} {kind} ({method})",
                      recipe={"localizer": loc.name, "kind": kind, "fraction": frac, "direction": direction},
                      **{kind: units})


def random_control(spec: LesionSpec, dims: SiteDims, seed: int = 0) -> LesionSpec:
    """Same number of units in the same layers as `spec`, chosen at random."""
    mlp = random_like(spec.mlp, dims.mlp, seed) if spec.mlp else {}
    heads = random_like(spec.heads, dims.heads, seed) if spec.heads else {}
    return LesionSpec(method=spec.method, mlp=mlp, heads=heads, noise_scale=spec.noise_scale, seed=spec.seed,
                      name=f"random control for {spec.name} (seed {seed})",
                      recipe={"control": "random", "of": spec.name, "seed": seed, **spec.recipe})


def isolate_critical(units: Units, fails: Callable[[Units], bool], max_probes: int = 60) -> tuple[Units, int]:
    """Bisect a unit set whose lesion breaks the model down to a small subset that still breaks it.
    `fails(units)` runs the lesion and says whether it broke. Halving stops when neither half
    breaks alone (the culprits interact), so the result can hold more than one unit."""
    flat = [(layer, u) for layer, idx in sorted(units.items()) for u in idx]
    probes = 0

    def as_units(pairs):
        out: Units = {}
        for layer, u in pairs:
            out.setdefault(layer, []).append(u)
        return out

    while len(flat) > 1 and probes < max_probes:
        half = len(flat) // 2
        for part in (flat[:half], flat[half:]):
            probes += 1
            if fails(as_units(part)):
                flat = part
                break
        else:
            break
    return as_units(flat), probes

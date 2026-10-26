"""Reversible lesions for Muse Glimmer, applied as forward hooks.

A lesion never edits weights (the decoder is FP8). It rewrites activations on their way through
chosen modules and is undone when the `with lesion(model, spec, stats):` block exits.

Sites (what one "unit" is):
  mlp           one channel of the input to a decoder layer's mlp.down_proj, i.e. act(gate) * up
                (52 layers x 19,968 neurons)
  heads         one query head's 128-dim slice of the input to self_attn.o_proj, taken after the
                sigmoid output gate (52 layers x 32 heads)
  vision_tower  one channel of the vision tower's output after pixel shuffle (6,144), read as the
                input to vision_adapter
  projector     one channel of vision_projection's output (6,656), before the weightless norm that
                turns it into the decoder's image embeddings
  layers        a band of whole decoder layers: every head and every neuron in them. Zeroing all
                of them removes the layer's update to the residual stream.

Methods:
  zero   set the unit to 0, the classic lesion
  mean   replace the unit with its mean over a reference set (every token position of intact
         naming trials), which removes what the unit carries but keeps activations in range
  noise  add Gaussian noise with sd = noise_scale x the unit's sd over the reference set, for
         graded damage

Specs are dataclasses that round-trip through JSON, so they are saved with results and can be
sent from the web UI.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path

import torch

METHODS = ("zero", "mean", "noise")
COMPONENTS = ("vision_tower", "projector")
Units = dict[int, list[int] | None]  # layer -> unit indices; None means every unit in the layer


@dataclass
class LesionSpec:
    method: str = "zero"
    mlp: Units = field(default_factory=dict)
    heads: Units = field(default_factory=dict)
    components: dict[str, list[int] | None] = field(default_factory=dict)
    layers: list[int] = field(default_factory=list)
    noise_scale: float = 1.0
    seed: int = 0
    name: str = ""
    recipe: dict = field(default_factory=dict)  # how the units were chosen, e.g. localizer and fraction

    def __post_init__(self):
        if self.method not in METHODS:
            raise ValueError(f"method must be one of {METHODS}, got {self.method!r}")
        if bad := set(self.components) - set(COMPONENTS):
            raise ValueError(f"unknown components {sorted(bad)}; known: {COMPONENTS}")

    @property
    def is_intact(self) -> bool:
        return not (self.mlp or self.heads or self.components or self.layers)

    def to_dict(self, units: bool = True) -> dict:
        """JSON-ready. units=False replaces index lists with counts, for small result files."""
        def pack(d: dict) -> dict:
            return {str(k): (sorted(v) if units else len(v)) if v is not None else None for k, v in d.items()}
        return {"name": self.name, "method": self.method, "noise_scale": self.noise_scale, "seed": self.seed,
                "mlp": pack(self.mlp), "heads": pack(self.heads), "components": pack(self.components),
                "layers": sorted(self.layers), "recipe": self.recipe}

    @classmethod
    def from_dict(cls, d: dict) -> LesionSpec:
        def unpack(units: dict | None) -> Units:
            out = {}
            for k, v in (units or {}).items():
                if isinstance(v, int):
                    raise ValueError("this spec was saved with counts only (units=False); it can't be re-applied")
                out[int(k)] = None if v is None else [int(i) for i in v]
            return out
        comps = {k: (None if v is None else [int(i) for i in v]) for k, v in (d.get("components") or {}).items()}
        return cls(method=d.get("method", "zero"), mlp=unpack(d.get("mlp")), heads=unpack(d.get("heads")),
                   components=comps, layers=[int(x) for x in d.get("layers") or []],
                   noise_scale=float(d.get("noise_scale", 1.0)), seed=int(d.get("seed", 0)),
                   name=d.get("name", ""), recipe=dict(d.get("recipe") or {}))

    def counts(self, dims: SiteDims) -> dict:
        """Units lesioned per site and per layer (whole-layer bands included)."""
        def per_layer(units: Units, size: int) -> dict[int, int]:
            out = {layer: (size if idx is None else len(idx)) for layer, idx in units.items()}
            for layer in self.layers:
                out[layer] = size
            return dict(sorted(out.items()))
        mlp, heads = per_layer(self.mlp, dims.mlp), per_layer(self.heads, dims.heads)
        return {"mlp": sum(mlp.values()), "heads": sum(heads.values()),
                "mlp_by_layer": mlp, "heads_by_layer": heads,
                "components": {k: (dims.component(k) if v is None else len(v)) for k, v in self.components.items()}}


@dataclass
class SiteDims:
    n_layers: int
    mlp: int  # neurons per layer
    heads: int  # query heads per layer
    head_dim: int
    vision_tower: int
    projector: int

    def component(self, name: str) -> int:
        return getattr(self, name)


def site_dims(model) -> SiteDims:
    cfg = model.config.get_text_config()
    layers = model.model.language_model.layers
    return SiteDims(n_layers=len(layers), mlp=layers[0].mlp.down_proj.in_features,
                    heads=cfg.num_attention_heads, head_dim=cfg.head_dim,
                    vision_tower=model.model.vision_adapter.fc1.in_features,
                    projector=model.model.vision_projection.out_features)


# --- reference statistics for mean and noise lesions ------------------------------------

@dataclass
class UnitStats:
    """Per-unit mean and sd over every token position of a reference set. Heads are stored per
    channel of the o_proj input (layers x heads*head_dim), so a mean-ablated head keeps its
    average 128-dim output vector."""
    mlp_mean: torch.Tensor
    mlp_std: torch.Tensor
    head_mean: torch.Tensor
    head_std: torch.Tensor
    vision_tower_mean: torch.Tensor
    vision_tower_std: torch.Tensor
    projector_mean: torch.Tensor
    projector_std: torch.Tensor
    n_tokens: int = 0
    n_image_tokens: int = 0
    source: str = ""

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({k: v.cpu() if torch.is_tensor(v) else v for k, v in self.__dict__.items()}, path)

    @classmethod
    def load(cls, path: Path, device=None) -> UnitStats:
        d = torch.load(path, map_location=device or "cpu")
        return cls(**d)

    def site(self, site: str, layer: int | None = None) -> tuple[torch.Tensor, torch.Tensor]:
        prefix = {"heads": "head"}.get(site, site)
        mean, std = getattr(self, f"{prefix}_mean"), getattr(self, f"{prefix}_std")
        return (mean, std) if layer is None else (mean[layer], std[layer])


class Moments:
    """Streaming count, sum and sum of squares per unit, in float64."""

    def __init__(self, shape, device):
        self.n = 0
        self.s = torch.zeros(shape, dtype=torch.float64, device=device)
        self.ss = torch.zeros(shape, dtype=torch.float64, device=device)

    def add(self, x: torch.Tensor) -> None:  # x: (samples, *shape)
        x = x.double()
        self.n += x.shape[0]
        self.s += x.sum(0)
        self.ss += (x * x).sum(0)

    def mean_var(self) -> tuple[torch.Tensor, torch.Tensor]:
        """Mean and unbiased variance."""
        n = max(self.n, 1)
        mean = self.s / n
        return mean, (self.ss - n * mean * mean).clamp_min(0) / max(n - 1, 1)

    def mean_std(self) -> tuple[torch.Tensor, torch.Tensor]:
        mean, var = self.mean_var()
        return mean.float(), var.sqrt().float()


@torch.no_grad()
def compute_unit_stats(model, batches, source: str = "") -> UnitStats:
    """Run intact forward passes over `batches` (model input dicts with an attention_mask) and
    collect each unit's mean and sd over every real (non-padding) token position."""
    dims, dev = site_dims(model), model.device
    layers = model.model.language_model.layers
    mlp = [Moments(dims.mlp, dev) for _ in range(dims.n_layers)]
    heads = [Moments(dims.heads * dims.head_dim, dev) for _ in range(dims.n_layers)]
    vt, pj = Moments(dims.vision_tower, dev), Moments(dims.projector, dev)
    state = {}

    def tokens(x):  # (B, T, C) -> (real tokens, C)
        return x[state["mask"]] if x.dim() == 3 else x

    hooks = []
    for i, layer in enumerate(layers):
        hooks.append(layer.mlp.down_proj.register_forward_pre_hook(lambda _m, a, i=i: mlp[i].add(tokens(a[0]))))
        hooks.append(layer.self_attn.o_proj.register_forward_pre_hook(lambda _m, a, i=i: heads[i].add(tokens(a[0]))))
    hooks.append(model.model.vision_adapter.register_forward_pre_hook(lambda _m, a: vt.add(a[0].reshape(-1, a[0].shape[-1]))))
    hooks.append(model.model.vision_projection.register_forward_hook(lambda _m, _a, out: pj.add(out.reshape(-1, out.shape[-1]))))
    try:
        for batch in batches:
            state["mask"] = batch["attention_mask"].bool()
            model(**batch, logits_to_keep=1)
    finally:
        for h in hooks:
            h.remove()
    mlp_ms, head_ms = [m.mean_std() for m in mlp], [m.mean_std() for m in heads]
    (vt_mean, vt_std), (pj_mean, pj_std) = vt.mean_std(), pj.mean_std()
    return UnitStats(
        mlp_mean=torch.stack([m for m, _ in mlp_ms]), mlp_std=torch.stack([s for _, s in mlp_ms]),
        head_mean=torch.stack([m for m, _ in head_ms]), head_std=torch.stack([s for _, s in head_ms]),
        vision_tower_mean=vt_mean, vision_tower_std=vt_std, projector_mean=pj_mean, projector_std=pj_std,
        n_tokens=mlp[0].n, n_image_tokens=pj.n, source=source)


# --- hooks ------------------------------------------------------------------------------

class _Rewrite:
    """Rewrites the masked channels (last dim) of an activation tensor."""

    def __init__(self, mask: torch.Tensor, method: str, mean: torch.Tensor | None, std: torch.Tensor | None,
                 noise_scale: float, generator: torch.Generator | None, dtype: torch.dtype):
        self.method, self.generator = method, generator
        self.keep = (~mask).to(dtype)
        if method == "mean":
            self.fill = torch.where(mask, mean.to(mask.device), 0.0).to(dtype)
        elif method == "noise":
            self.sd = torch.where(mask, std.to(mask.device) * noise_scale, 0.0).to(dtype)

    def __call__(self, x: torch.Tensor) -> torch.Tensor:
        if self.method == "zero":
            return x * self.keep
        if self.method == "mean":
            return x * self.keep + self.fill
        noise = torch.randn(x.shape, generator=self.generator, device=x.device, dtype=torch.float32)
        return x + noise.to(x.dtype) * self.sd


def _mask(size: int, idx: list[int] | None, device, group: int = 1) -> torch.Tensor:
    """Channel mask; with group > 1 each index covers `group` consecutive channels (a head)."""
    if idx is None:
        return torch.ones(size * group, dtype=torch.bool, device=device)
    m = torch.zeros(size, dtype=torch.bool, device=device)
    if idx:
        m[torch.as_tensor(idx, device=device)] = True
    return m.repeat_interleave(group)


def _pre_hook(rw: _Rewrite):
    return lambda _m, args: (rw(args[0]),) + tuple(args[1:])


def _post_hook(rw: _Rewrite):
    return lambda _m, _args, out: rw(out)


@contextlib.contextmanager
def lesion(model, spec: LesionSpec | dict | None, stats: UnitStats | None = None):
    """Apply `spec` inside the block; every hook is removed on exit, even after an error."""
    if spec is None or isinstance(spec, dict):
        spec = LesionSpec.from_dict(spec or {})
    if spec.is_intact:
        yield spec
        return
    if spec.method in ("mean", "noise") and stats is None:
        raise ValueError(f"{spec.method} lesions need UnitStats (see compute_unit_stats)")
    dims, dev = site_dims(model), model.device
    dtype = next(p for p in model.model.vision_projection.parameters()).dtype
    if dtype not in (torch.bfloat16, torch.float16, torch.float32):
        dtype = torch.bfloat16
    gen = torch.Generator(device=dev).manual_seed(spec.seed) if spec.method == "noise" else None
    layers = model.model.language_model.layers

    def rewrite(mask, site, layer=None):
        mean, std = stats.site(site, layer) if stats is not None else (None, None)
        return _Rewrite(mask, spec.method, mean, std, spec.noise_scale, gen, dtype)

    mlp = dict(spec.mlp) | {layer: None for layer in spec.layers}
    heads = dict(spec.heads) | {layer: None for layer in spec.layers}
    hooks = []
    try:
        for layer, idx in mlp.items():
            rw = rewrite(_mask(dims.mlp, idx, dev), "mlp", layer)
            hooks.append(layers[layer].mlp.down_proj.register_forward_pre_hook(_pre_hook(rw)))
        for layer, idx in heads.items():
            rw = rewrite(_mask(dims.heads, idx, dev, group=dims.head_dim), "heads", layer)
            hooks.append(layers[layer].self_attn.o_proj.register_forward_pre_hook(_pre_hook(rw)))
        if "vision_tower" in spec.components:
            rw = rewrite(_mask(dims.vision_tower, spec.components["vision_tower"], dev), "vision_tower")
            hooks.append(model.model.vision_adapter.register_forward_pre_hook(_pre_hook(rw)))
        if "projector" in spec.components:
            rw = rewrite(_mask(dims.projector, spec.components["projector"], dev), "projector")
            hooks.append(model.model.vision_projection.register_forward_hook(_post_hook(rw)))
        yield spec
    finally:
        for h in hooks:
            h.remove()

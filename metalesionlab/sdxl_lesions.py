"""Reversible lesions for Stable Diffusion XL, applied as forward hooks (the SDXL twin of lesions.py).

SDXL has a "language part" and a "drawing part":
  text   the two text encoders, CLIP ViT-L (12 layers x 3,072 MLP neurons) and OpenCLIP bigG
         (32 layers x 5,120). One unit is one channel of the input to a layer's mlp.fc2, i.e. the
         neuron after its activation function. SDXL reads the penultimate layer of both encoders
         and the pooled output of the second.
  text1, text2   one encoder only
  unet   the denoising UNet that turns the text into a picture: one unit is one channel of the
         input to the output Linear of a transformer block's feed-forward net (after GEGLU),
         70 blocks of 2,560 or 5,120 neurons.

A lesion never edits weights. It rewrites activations on their way into the chosen modules and is
undone when the `with engine.apply(spec):` block exits.

Methods:
  zero   set the chosen units to 0 (neuron loss)
  noise  add Gaussian noise with sd = noise_scale x the unit's sd over a reference set. The noise
         has shape (1, tokens, units), the same for every picture in a batch, and its generator is
         re-seeded by engine.reset() before each pipeline call, so a picture gets the same damage
         whatever else is in its batch (paired pictures across damage levels).

Which units: `fraction` of the units of every layer in the site (or in `layers`, a band of the
site's layer list), chosen at random per layer with `seed` (random_units), or an explicit
`units` dict (targeted lesions and their matched random controls, matched_random).
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

import numpy as np

SITES = ("text", "text1", "text2", "unet")
METHODS = ("zero", "noise")


@dataclass
class DamageSpec:
    site: str = "text"
    method: str = "zero"
    fraction: float = 0.0          # share of each layer's units hit
    noise_scale: float = 0.0       # noise sd in units of each unit's reference sd
    layers: list[int] | None = None  # a band of the site's layers (indices into site_layers); None = all
    units: dict[str, list[int]] | None = None  # explicit units per module name (overrides fraction)
    seed: int = 0
    name: str = ""
    recipe: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.site not in SITES:
            raise ValueError(f"site must be one of {SITES}, got {self.site!r}")
        if self.method not in METHODS:
            raise ValueError(f"method must be one of {METHODS}, got {self.method!r}")
        if not 0.0 <= self.fraction <= 1.0:
            raise ValueError("fraction must be in [0, 1]")

    @property
    def is_intact(self) -> bool:
        if self.units is not None:
            return not any(self.units.values())
        return self.fraction <= 0 or (self.method == "noise" and self.noise_scale <= 0)

    def to_dict(self) -> dict:
        return {"site": self.site, "method": self.method, "fraction": self.fraction,
                "noise_scale": self.noise_scale, "layers": self.layers,
                "units": ({k: sorted(int(i) for i in v) for k, v in self.units.items()}
                          if self.units is not None else None),
                "seed": self.seed, "name": self.name, "recipe": self.recipe}

    @classmethod
    def from_dict(cls, d: dict) -> DamageSpec:
        return cls(site=d.get("site", "text"), method=d.get("method", "zero"),
                   fraction=float(d.get("fraction", 0.0)), noise_scale=float(d.get("noise_scale", 0.0)),
                   layers=d.get("layers"), units=d.get("units"), seed=int(d.get("seed", 0)),
                   name=d.get("name", ""), recipe=dict(d.get("recipe") or {}))


def random_units(sizes: list[int], fraction: float, seed: int = 0) -> list[np.ndarray]:
    """round(fraction x size) distinct units per layer, chosen at random (sorted), independently per
    layer from one seeded generator. The same seed and fraction give nested sets: a larger fraction
    keeps every unit a smaller one hit, so doses are cumulative damage, as in progressive atrophy."""
    rng = np.random.default_rng(seed)
    out = []
    for size in sizes:
        order = rng.permutation(size)  # one fixed order per layer: dose k takes its first k units
        out.append(np.sort(order[:int(round(fraction * size))]))
    return out


def matched_random(units: dict[str, list[int]], sizes: dict[str, int], seed: int = 0,
                   exclude: bool = True) -> dict[str, list[int]]:
    """A random control for a targeted lesion: the same number of units in every layer, chosen at
    random (by default never one of the targeted units)."""
    rng = np.random.default_rng(seed)
    out = {}
    for name, idx in units.items():
        pool = np.setdiff1d(np.arange(sizes[name]), np.asarray(idx, int)) if exclude else np.arange(sizes[name])
        k = len(idx)
        if k > len(pool):
            pool = np.arange(sizes[name])
        out[name] = sorted(int(i) for i in rng.choice(pool, k, replace=False))
    return out


def top_units(scores: dict[str, np.ndarray], fraction: float) -> dict[str, list[int]]:
    """The top `fraction` of all units by score (positive scores only), pooled over layers."""
    names = list(scores)
    flat = np.concatenate([np.asarray(scores[n], float) for n in names])
    k = int(round(fraction * flat.size))
    order = np.argsort(-flat, kind="stable")[:k]
    order = order[flat[order] > 0]
    bounds = np.cumsum([0] + [len(scores[n]) for n in names])
    out = {n: [] for n in names}
    for flat_i in sorted(order.tolist()):
        layer = int(np.searchsorted(bounds, flat_i, side="right") - 1)
        out[names[layer]].append(int(flat_i - bounds[layer]))
    return out


# ---------- hooking SDXL ----------

def site_layers(pipe, site: str) -> list[tuple[str, object]]:
    """(name, module) for every unit-carrying module of a site, in depth order. The hook goes on
    the module's input."""
    import torch.nn as nn

    out = []
    if site in ("text", "text1"):
        for i, layer in enumerate(_encoder_layers(pipe.text_encoder)):
            out.append((f"te1.{i}", layer.mlp.fc2))
    if site in ("text", "text2"):
        for i, layer in enumerate(_encoder_layers(pipe.text_encoder_2)):
            out.append((f"te2.{i}", layer.mlp.fc2))
    if site == "unet":
        for name, mod in pipe.unet.named_modules():
            if type(mod).__name__ == "FeedForward" and hasattr(mod, "net"):
                linears = [m for m in mod.net if isinstance(m, nn.Linear)]
                out.append((f"unet.{name}", linears[-1]))
    return out


def _encoder_layers(encoder):
    """A CLIP text encoder's transformer layers (transformers 4 nests them under .text_model; 5 doesn't)."""
    inner = getattr(encoder, "text_model", encoder)
    return inner.encoder.layers


def layer_sizes(pipe, site: str) -> dict[str, int]:
    return {name: mod.in_features for name, mod in site_layers(pipe, site)}


class _Rewrite:
    def __init__(self, mask, method: str, sd=None, scale: float = 0.0, seed: int = 0):
        import torch

        self.method, self.seed = method, seed
        self.mask = mask
        self.keep = (~mask)
        self.idx = mask.nonzero().flatten()
        self.sd = None if sd is None else (sd.to(mask.device)[self.idx] * scale)
        self.gen = torch.Generator(device=mask.device)
        self.reset()

    def reset(self):
        self.gen.manual_seed(self.seed)

    def __call__(self, x):
        import torch

        if self.method == "zero":
            return x * self.keep.to(x.dtype)
        shape = (1,) * (x.dim() - 1) + (len(self.idx),)
        if x.dim() == 3:
            shape = (1, x.shape[1], len(self.idx))
        eps = torch.randn(shape, generator=self.gen, device=x.device, dtype=torch.float32)
        x = x.clone()
        x[..., self.idx] = x[..., self.idx] + (eps * self.sd.float()).to(x.dtype)
        return x


class SDXLDamage:
    """Applies DamageSpecs to a diffusers StableDiffusionXLPipeline."""

    def __init__(self, pipe, stats: dict | None = None):
        self.pipe = pipe
        self.stats = stats or {}  # module name -> {"mean": tensor, "sd": tensor}
        self._active: list[_Rewrite] = []

    def units_for(self, spec: DamageSpec) -> dict[str, list[int]]:
        layers = site_layers(self.pipe, spec.site)
        if spec.layers is not None:
            layers = [layers[i] for i in spec.layers]
        if spec.units is not None:
            names = {n for n, _ in layers}
            return {k: list(v) for k, v in spec.units.items() if k in names}
        chosen = random_units([m.in_features for _, m in layers], spec.fraction, spec.seed)
        return {n: c.tolist() for (n, _), c in zip(layers, chosen)}

    def reset(self) -> None:
        """Re-seed every noise generator; call before each pipeline call."""
        for rw in self._active:
            rw.reset()

    @contextlib.contextmanager
    def apply(self, spec: DamageSpec | dict | None):
        import torch

        if spec is None or isinstance(spec, dict):
            spec = DamageSpec.from_dict(spec or {"fraction": 0.0})
        if spec.is_intact:
            yield spec
            return
        modules = dict(site_layers(self.pipe, spec.site))
        if spec.units is not None:  # targeted units may span sites (e.g. text1 + text2)
            for s in ("text", "unet"):
                modules.update(dict(site_layers(self.pipe, s)))
        hooks = []
        try:
            for i, (name, idx) in enumerate(sorted(self.units_for(spec).items())):
                if not idx:
                    continue
                mod = modules[name]
                dev = next(mod.parameters()).device
                mask = torch.zeros(mod.in_features, dtype=torch.bool, device=dev)
                mask[torch.as_tensor(idx, device=dev)] = True
                sd = None
                if spec.method == "noise":
                    if name not in self.stats:
                        raise ValueError(f"noise lesions need reference stats for {name}")
                    sd = self.stats[name]["sd"]
                rw = _Rewrite(mask, spec.method, sd, spec.noise_scale, seed=spec.seed * 1000 + i)
                self._active.append(rw)
                hooks.append(mod.register_forward_pre_hook(lambda _m, args, rw=rw: (rw(args[0]),) + tuple(args[1:])))
            yield spec
        finally:
            for h in hooks:
                h.remove()
            self._active.clear()


def collect_stats(pipe, run_fn, sites=("text", "unet")) -> dict:
    """Per-unit mean and sd over every position the module sees while `run_fn()` runs the intact
    pipeline (reference prompts). Returns {module name: {"mean", "sd", "n"}} on the CPU."""
    import torch

    from metalesionlab.lesions import Moments

    mods = {}
    for s in sites:
        mods.update(dict(site_layers(pipe, s)))
    moments = {n: Moments(m.in_features, next(m.parameters()).device) for n, m in mods.items()}
    hooks = [m.register_forward_pre_hook(lambda _m, args, n=n: moments[n].add(args[0].reshape(-1, args[0].shape[-1])))
             for n, m in mods.items()]
    try:
        with torch.no_grad():
            run_fn()
    finally:
        for h in hooks:
            h.remove()
    out = {}
    for n, mo in moments.items():
        mean, sd = mo.mean_std()
        out[n] = {"mean": mean.cpu(), "sd": sd.cpu(), "n": mo.n}
    return out

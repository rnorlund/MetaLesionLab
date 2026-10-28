"""Plato's Chair: does the result depend on DINOv2? The same spread analysis with other vision models.

Every Plato's Chair result embeds the ink-cropped pictures with one model, Meta DINOv2-base (CLS token).
This module names the other open vision models we re-embed with, loads them, and holds the pure functions
that summarize a result per embedder and apply the pre-registered rules in docs/plato_robustness_plan.md.

Embedders (all openly downloadable from Hugging Face without accepting gated terms):
- dinov2_base   Meta DINOv2-base, CLS token: the reference, as in every other Plato's Chair result
- dinov2_large  Meta DINOv2-large, CLS token: same family and training, a bigger model
- pe_core_l14   Meta Perception Encoder PE-Core-L14-336 (timm port): image-text contrastive, the projected
                image embedding that is matched to text
- siglip2_so400m  Google SigLIP 2 So400m/14 at 384 px: the non-Meta control, the pooled image embedding
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from metalesionlab.plato import DINO_MODEL, Embedder


@dataclass(frozen=True)
class EmbedderSpec:
    tag: str        # folder name under $PLATO_DIR/embeddings_robust/
    name: str       # what we call it in tables
    model_id: str   # Hugging Face id (timm model name for loader "timm")
    loader: str     # dinov2 | timm | siglip
    maker: str
    license: str
    training: str
    feature: str    # which vector we use


EMBEDDERS = {
    "dinov2_base": EmbedderSpec("dinov2_base", "DINOv2-base (reference)", DINO_MODEL, "dinov2", "Meta",
                                "Apache-2.0", "self-supervised, images only", "CLS token (768-d)"),
    "dinov2_large": EmbedderSpec("dinov2_large", "DINOv2-large", "facebook/dinov2-large", "dinov2", "Meta",
                                 "Apache-2.0", "self-supervised, images only", "CLS token (1024-d)"),
    "pe_core_l14": EmbedderSpec("pe_core_l14", "PE-Core-L14-336", "vit_pe_core_large_patch14_336.fb", "timm",
                                "Meta", "Apache-2.0", "image-text contrastive (Perception Encoder)",
                                "projected image embedding (1024-d), attention-pooled"),
    "siglip2_so400m": EmbedderSpec("siglip2_so400m", "SigLIP 2 So400m/14", "google/siglip2-so400m-patch14-384",
                                   "siglip", "Google", "Apache-2.0", "image-text sigmoid contrastive",
                                   "pooled image embedding (1152-d), attention-pooled"),
}
REFERENCE = "dinov2_base"
ALTERNATIVES = ["dinov2_large", "pe_core_l14", "siglip2_so400m"]
# Checked on Hugging Face on Oct 27, 2026 and not used.
SKIPPED = {
    "facebook/dinov3-*": "gated (manual approval) under the custom DINOv3 License; the ungated timm mirror "
                         "(timm/vit_*_dinov3.lvd1689m) carries the same license, which is accepted by use, so we "
                         "skipped it too rather than accept it on the project's behalf",
}


class ImageEmbedder:
    """One embedder from EMBEDDERS: images in (already ink-cropped), one vector per image out.

    Each model uses its own standard preprocessing (resize and normalization) after the ink crop."""

    def __init__(self, spec: EmbedderSpec, device: str | None = None):
        import torch

        self.spec, self.torch = spec, torch
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")
        if spec.loader == "dinov2":
            self.dino = Embedder(spec.model_id, self.device)
        elif spec.loader == "timm":
            import timm

            self.model = timm.create_model(spec.model_id, pretrained=True).to(self.device).eval()
            cfg = timm.data.resolve_data_config({}, model=self.model)
            self.transform = timm.data.create_transform(**cfg)
        elif spec.loader == "siglip":
            from transformers import AutoImageProcessor, AutoModel

            self.processor = AutoImageProcessor.from_pretrained(spec.model_id)
            self.model = AutoModel.from_pretrained(spec.model_id).to(self.device).eval()
        else:
            raise ValueError(f"unknown loader {spec.loader!r}")

    def __call__(self, images, batch: int = 32) -> dict[str, np.ndarray]:
        """{'emb': primary vectors}; DINOv2 also returns 'patch_mean'."""
        if self.spec.loader == "dinov2":
            out = self.dino(images, batch)
            return {"emb": out["cls"], "patch_mean": out["patch_mean"]}
        torch, vecs = self.torch, []
        with torch.no_grad():
            for i in range(0, len(images), batch):
                chunk = images[i:i + batch]
                if self.spec.loader == "timm":
                    x = torch.stack([self.transform(im) for im in chunk]).to(self.device)
                    v = self.model(x)
                else:
                    inputs = self.processor(images=chunk, return_tensors="pt").to(self.device)
                    v = self.model.get_image_features(**inputs)
                    v = v if torch.is_tensor(v) else v.pooler_output
                vecs.append(v.float().cpu().numpy())
        return {"emb": np.concatenate(vecs)}


# ---------- statistics ----------

def hierarchical_median_ci(draws: np.ndarray, reps: int = 2000, level: float = 0.95,
                           rng: np.random.Generator | None = None) -> list[float]:
    """CI of the median over items of a per-item quantity, from per-item bootstrap draws (items x draws).

    Each replicate resamples the items with replacement and takes one random bootstrap draw for each
    sampled item, so the CI carries both which items were chosen and each item's own sampling noise."""
    rng = rng or np.random.default_rng(0)
    draws = np.asarray(draws, float)
    n_items, n_draws = draws.shape
    meds = np.empty(reps)
    for b in range(reps):
        items = rng.integers(0, n_items, n_items)
        meds[b] = np.median(draws[items, rng.integers(0, n_draws, n_items)])
    a = (1 - level) / 2
    return [float(np.quantile(meds, a)), float(np.quantile(meds, 1 - a))]


def nearest_centroid_share(queries: dict[str, np.ndarray], refs: dict[str, np.ndarray],
                           leave_one_out: bool = False) -> dict[str, float]:
    """Per concept: the share of query vectors that sit nearest their own concept among the reference sets.

    "Nearest" is the highest mean cosine similarity to a set's vectors (the dot product with its mean unit
    vector), as in the core recognisability check. With leave_one_out the queries are the reference sets
    themselves (same rows), and each vector is left out of its own concept's mean."""
    def unit(v):
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    keys = list(refs)
    sums = {k: unit(refs[k]).sum(0) for k in keys}
    mus = np.stack([sums[k] / len(refs[k]) for k in keys])
    out = {}
    for j, k in enumerate(keys):
        if k not in queries:
            continue
        q = unit(queries[k])
        scores = q @ mus.T
        if leave_one_out:
            scores[:, j] = (q @ sums[k] - 1.0) / (len(refs[k]) - 1)  # q . q = 1 for a unit vector
        out[k] = float(np.mean(np.argmax(scores, axis=1) == j))
    return out


# Pre-registered thresholds (docs/plato_robustness_plan.md). Do not change after results are seen.
MIN_CONCEPTS_BELOW = 28     # of 35: the AI below people (core) and Muse below SDXL
MIN_RHO = 0.6               # rank agreement of per-concept ratios with DINOv2-base
ANY_BAND = (0.8, 1.25)      # "any kind" counts as about the usual prompt if its median ratio to it is inside


def _below(ci95) -> bool:
    return ci95 is not None and ci95[1] < 1


def _above(ci95) -> bool:
    return ci95 is not None and ci95[0] > 1


def verdict(s: dict) -> dict:
    """Apply the pre-registered rules to one embedder's summary.

    `s` needs: index_median, index_median_ci95, concepts_below_1, n_concepts, chair_index_ci95,
    muse_over_sdxl_median_ci95, concepts_muse_below_sdxl, sdxl_index_median_ci95, any_vs_default_median,
    any_vs_people_median_ci95, listed_vs_people_median_ci95, listed_vs_default_median_ci95, and (not for the
    reference) rho_index_vs_reference. Returns each check and three overall labels."""
    c = {
        "core_median_below_1": s["index_median"] < 1 and _below(s["index_median_ci95"]),
        "core_most_concepts_below_1": s["concepts_below_1"] >= MIN_CONCEPTS_BELOW,
        "chair_below_1": _below(s["chair_index_ci95"]),
        "muse_below_sdxl": _below(s["muse_over_sdxl_median_ci95"])
        and s["concepts_muse_below_sdxl"] >= MIN_CONCEPTS_BELOW,
        "sdxl_not_below_people": not _below(s["sdxl_index_median_ci95"]),
        "any_about_default": ANY_BAND[0] <= s["any_vs_default_median"] <= ANY_BAND[1],
        "any_below_people": _below(s["any_vs_people_median_ci95"]),
        "listed_above_people": _above(s["listed_vs_people_median_ci95"]),
        "listed_above_default": _above(s["listed_vs_default_median_ci95"]),
    }
    rho = s.get("rho_index_vs_reference")
    c["ranks_agree"] = None if rho is None else bool(rho >= MIN_RHO)
    direction = c["core_median_below_1"] and c["core_most_concepts_below_1"] and c["muse_below_sdxl"]
    if direction and c["chair_below_1"] and c["ranks_agree"] is not False:
        core = "holds"
    elif direction:
        core = "holds in direction"  # Muse below people and below SDXL, but the chair or the concept ranking differs
    elif s["index_median"] < 1:
        core = "weaker"
    else:
        core = "does not hold"
    variety = ("holds" if all(c[k] for k in ("any_about_default", "any_below_people", "listed_above_people",
                                              "listed_above_default"))
               else "partly" if c["any_about_default"] or c["listed_above_people"] else "does not hold")
    return {"checks": {k: (None if v is None else bool(v)) for k, v in c.items()}, "core": core,
            "variety": variety, "sdxl_not_below_people": bool(c["sdxl_not_below_people"])}

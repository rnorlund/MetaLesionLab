# Plato's Chair, does it depend on DINOv2? Pre-registration

Written on Oct 27, 2026. Committed before any statistic was computed from the new embeddings. Results will go in `docs/plato_robustness.md`, and any deviation from this plan will be listed there.

**Why.** Every result in `docs/plato.md` measures spread in one embedding space: Meta DINOv2-base, CLS token. A fair question is whether "Muse draws one chair" is a fact about Muse or about DINOv2. We re-measure everything with three other open vision models and check, by rules fixed here, whether each headline survives.

**What I had seen before writing this.**
- All DINOv2-base results in `docs/plato.md`.
- For the new models, only a smoke test on the 16 Muse chair doodles: each model loads and returns finite vectors. DINOv2-base through the new code reproduces the cached core embeddings (cosine ≥ 0.99999).
- The full embedding run started before this commit. No spread, ratio, correlation or nearest-centroid share has been computed from it.

Code: `metalesionlab/plato_robust.py` (embedders, the median CI, the pass/fail rules), `scripts/plato_robust_embed.py` and `scripts/plato_robust_analyze.py`. Embeddings go to `PlatosChair/core/embeddings_robust/<embedder>/`, outside the repository. The core embeddings and results are only read, never written.

## Embedders

| Tag | Model | Maker, license | Training | Vector we use | Input after the ink crop |
|---|---|---|---|---|---|
| `dinov2_base` (reference) | `facebook/dinov2-base` | Meta, Apache-2.0 | self-supervised, images only | CLS token (768-d) | shortest side 256, center crop 224 |
| `dinov2_large` | `facebook/dinov2-large` | Meta, Apache-2.0 | same as base, bigger model | CLS token (1024-d) | as base |
| `pe_core_l14` | Perception Encoder PE-Core-L14-336 (`facebook/PE-Core-L14-336`), loaded as timm `vit_pe_core_large_patch14_336.fb` (`timm/vit_pe_core_large_patch14_336.fb`) | Meta, Apache-2.0 | image-text contrastive | projected image embedding (1024-d), the one matched to text | 336 × 336 |
| `siglip2_so400m` | `google/siglip2-so400m-patch14-384` | Google, Apache-2.0 | image-text sigmoid contrastive | pooled image embedding (1152-d) | 384 × 384 |

Each model uses its own standard resize and normalization after the shared ink crop. The vector for each model is fixed here: no switching to patch tokens or inner layers after seeing results. DINOv2-large's patch-mean vector is reported as a secondary check only, as for base.

**Why these.** They vary the two things that could matter. One is model size within the same training (DINOv2-base vs large). The other is the training objective: self-supervised on images alone, or image-text contrastive. An image-text space is arranged more by what a caption would say, a DINOv2 space more by visual form. If Muse's uniformity were a quirk of DINOv2's visual-form space, the image-text models are where it should break. SigLIP 2 is the non-Meta control.

**Checked and skipped (Hugging Face, Oct 27, 2026).**
- DINOv3 (`facebook/dinov3-*`): gated, with manual approval under the custom DINOv3 License.
  - timm mirrors (`timm/vit_*_dinov3.lvd1689m`) are not gated but carry the same license, which is accepted by use.
  - We did not accept a license on the project's behalf, so DINOv3 is left out.
- Not gated but not used:
  - PE-Core-G14-448 (a bigger model of the same family; one PE model is enough);
  - PE-Spatial;
  - OpenAI CLIP (SigLIP 2 is the non-Meta control).

**Predictions (written before any result).**
- DINOv2-large agrees closely with base: per-concept rank correlation of 0.8 or more, and every core check passes.
- In the image-text models, the core direction holds (Muse below people, Muse below SDXL), but the median ratio moves toward 1. A caption-like space may pull people's messy drawings of one object together more than Muse's clean ones.
- Concept ranks agree less with base for the image-text models (rho about 0.4–0.7).
- The variety headline holds in all three.

## Pictures and pipeline

All pictures of the core, SDXL and variety analyses, 10,020 in total:

| Source | Pictures |
|---|---|
| Muse Image, usual prompt | 460 |
| Muse Image, "any kind" | 460 |
| Muse Image, "an unusual kind" (tier 1) | 160 |
| Muse Image, named kinds | 460 |
| SDXL, usual prompt | 560 |
| SDXL, "any kind" | 460 |
| SDXL, named kinds | 460 |
| People (Quick, Draw!) | 7,000 (200 × 35) |

The steps are unchanged except the embedder:
- **Preprocessing:** the same ink crop (`plato_embed.prepare`, PREP unchanged).
- **Spread:** mean pairwise cosine distance.
- **Statistics:** exactly those of `plato_analyze.concept_stats`.
  - Muse uses its n pictures (16 for tier 1, 12 for tier 2); SDXL uses all 16.
  - The human spread is the mean of 200 random sets of the AI's n.
  - Bootstraps: 2,000 over AI pictures and 500 over human drawings. Ratio CIs come from independent bootstraps of the two sets.

**New: a CI for a median over concepts.** We use a two-level bootstrap with 2,000 replicates (`plato_robust.hierarchical_median_ci`). Each replicate resamples the concepts with replacement. For each sampled concept, it takes one of that concept's bootstrap draws of the ratio. The CI therefore reflects both which concepts were chosen and each concept's own sampling noise. It is used for every median ratio below.

**The reference row** (DINOv2-base) is recomputed by the same new script from the cached core embeddings, so all rows share code. It should match `docs/plato.md` to about two decimals; random human subsets can shift it slightly.

## Primary measures, per embedder

1. **Core.**
   - The median AI/human spread ratio (homogenization index) over the 35 concepts, with its CI.
   - The number of concepts below 1, and the number whose CI is below 1.
2. **Chair.** The chair's index with its CI.
3. **Muse vs SDXL.**
   - The median of the per-concept Muse/SDXL spread ratios, with its CI.
   - The number of concepts where Muse is more uniform.
4. **Variety.**
   - "Any kind": median ratio to the usual prompt and to people.
   - Named kinds: median ratio to people and to the usual prompt.
   - Each with its CI. Ratios to the usual prompt use independent bootstraps of the two sets, as in `plato_variety_analyze.py`.
5. **Agreement.** Spearman rho of the 35 per-concept indexes between each embedder and DINOv2-base, with a bootstrap CI over concepts (5,000 replicates) and a permutation p.

## Secondary measures (reported; no pass or fail unless stated)

- **SDXL vs people.** The median SDXL/human ratio and the number of concepts below 1 (rule S1 below).
- **Rank agreement by part.** Rank correlations with base for Muse spread and for human spread separately.
- **Does the AI's spread follow people's?** The rank correlation between Muse spread and human spread (DINOv2-base: 0.38).
- **Other prompts.**
  - "An unusual kind": median ratio to people (10 concepts).
  - SDXL "any kind": median ratio to SDXL's usual spread.
- **Relative spread.** The between-concept baseline and the median relative index (spread divided by the between-concept distance).
- **Recognisability (validity).** These show how well each space separates the 35 concepts in doodles. An embedder that can't tell the concepts apart in people's drawings measures spread in a space that says little about the concept.
  - The share of Muse doodles whose nearest human centroid is their own concept (DINOv2-base: 85%).
  - The share of human drawings whose nearest human centroid is their own concept, with the drawing left out of its own centroid.
- **Concept extremes.** The six most and the six least homogenized concepts.
- **Patch-mean check.** DINOv2-large's patch-mean index: median, and rank correlation with its CLS index.

## What counts as "holds" (fixed here)

**Core result** ("Muse draws almost every concept more uniformly than people, and more uniformly than SDXL"), per embedder:

| Check | Rule | DINOv2-base |
|---|---|---|
| C1 | Median index below 1, with its 95% CI entirely below 1 | 0.49 |
| C2 | At least 28 of 35 concepts below 1 | 34 |
| C3 | Chair index CI entirely below 1 | 0.37 [0.24, 0.55] |
| C4 | Median Muse/SDXL ratio CI entirely below 1, and Muse more uniform for at least 28 of 35 | 0.42; 34 |
| C5 | Rank correlation of per-concept indexes with DINOv2-base at least 0.6 (point estimate) | (reference) |

Labels:
- **holds:** C1–C5 all pass.
- **holds in direction:** C1, C2 and C4 pass, but C3 or C5 fails. Muse is still more uniform than people and than SDXL, but the chair or the concept ranking differs.
- **weaker:** the median index is below 1, but C1, C2 or C4 fails.
- **does not hold:** the median index is 1 or above.

**Variety headline** ("'any kind' changes nothing; named kinds lift Muse above people"), per embedder:

| Check | Rule | DINOv2-base |
|---|---|---|
| V1 | "Any kind" is about the usual prompt: median any/usual ratio between 0.8 and 1.25 | 0.96 |
| V2 | "Any kind" stays below people: median any/people CI entirely below 1 | 0.49 |
| V3 | Named kinds are above people: median named/people CI entirely above 1 | 1.30 |
| V4 | Named kinds are above the usual prompt: median named/usual CI entirely above 1 | 2.73 |

Labels: **holds** if V1–V4 all pass; **partly** if V1 or V3 passes; **does not hold** otherwise.

**Secondary rule S1** ("SDXL is no more uniform than people"): the CI of the median SDXL/human ratio is not entirely below 1. DINOv2-base: 1.22.

**Reporting.**
- A short answer comes first, then one table per embedder with CIs.
- Every failed check is named.
- We won't change settings, vectors or thresholds to rescue a failed check. Any extra analysis will be labeled exploratory.

## Outputs

- `$PLATO_DIR/results_robustness.json`: everything, per embedder and per concept.
- `public_data/plato_robustness.json`: derived statistics only, with no pictures or embeddings. It holds per-embedder summaries, the checks, and per-concept ratios with CIs.
- `docs/plato_robustness.md`: the write-up.

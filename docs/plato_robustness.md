# Plato's Chair, does it depend on DINOv2?

Every result in `docs/plato.md` measures how varied a set of pictures is in one embedding space: Meta DINOv2-base, CLS token. Is "Muse draws one chair" a fact about Muse, or about DINOv2? We re-measured everything with three other open vision models, using rules fixed in advance in `docs/plato_robustness_plan.md` (committed before any result).

**Short answer:** The main result does not depend on DINOv2.
- **Muse vs people.** In all four models, Muse Image draws almost every concept more uniformly than people: median ratio 0.29–0.49, with a CI below 1 in each. It is below people for 34 or 35 of 35 concepts.
- **Muse vs SDXL.** Muse is also more uniform than SDXL: median ratio 0.29–0.42, for 34 or 35 of 35 concepts.
- **The chair.** Its chair is flattened in all four (0.28–0.38).
- **The variety result holds everywhere.**
  - "Any kind" leaves the spread where it was: 0.95–1.00 times the usual prompt.
  - Named kinds lift Muse above people: 1.16–1.31 times people's spread.
- **What does depend on the model: which concepts are flattened most.**
  - DINOv2-large ranks the concepts like DINOv2-base (rho 0.82). The two image-text models agree only weakly: PE-Core 0.43, SigLIP 2 0.34. Both are below our pre-registered 0.6.
  - So umbrella as Muse's most uniform concept is a DINOv2 finding. Book, the least flattened, is last in all four.
  - The modest link between how variably people draw a concept and how variably Muse draws it (rho 0.38 with DINOv2-base) does not survive: 0.07–0.27 with the other models, with every CI spanning zero.

Verdicts by the pre-registered labels:
- **DINOv2-large:** the core result **holds**.
- **PE-Core and SigLIP 2:** it **holds in direction**; they fail only the concept-ranking check.
- **The variety headline:** **holds** for all three.

## What we did

| Step | What we did |
|---|---|
| Embedders | **DINOv2-large** (`facebook/dinov2-large`; Meta, Apache-2.0): the same self-supervised training as the reference, in a bigger model; CLS token. **PE-Core-L14-336** (Meta Perception Encoder, `facebook/PE-Core-L14-336`, Apache-2.0; loaded as timm `vit_pe_core_large_patch14_336.fb`): trained to match images with text; we use its projected image embedding. **SigLIP 2 So400m/14** (`google/siglip2-so400m-patch14-384`; Google, Apache-2.0): the non-Meta control, also image-text; its pooled image embedding. Reference: **DINOv2-base** (`facebook/dinov2-base`), CLS token, from the cached core embeddings. |
| Skipped | **DINOv3** (`facebook/dinov3-*`) is gated, with manual approval under the custom DINOv3 License. The ungated timm mirrors carry the same license, which is accepted by use. We left DINOv3 out rather than accept that license on the project's behalf. |
| Pictures | All 10,020 pictures of the core, SDXL and variety analyses. Muse Image: usual doodles (460), "any kind" (460), "an unusual kind" (160), named kinds (460). SDXL: usual (560), "any kind" (460), named kinds (460). People: 200 Quick, Draw! drawings for each of the 35 concepts (7,000). |
| Preprocessing | The same ink crop as the core (`plato_embed.prepare`), then each model's own standard resize and normalization: 224 px for DINOv2, 336 px for PE-Core, 384 px for SigLIP 2. |
| Statistics | Unchanged from the core (`plato_analyze.concept_stats`). Spread is the mean pairwise cosine distance. People's spread is the mean of 200 random sets of the AI's n. Ratio CIs come from independent bootstraps of both sets. New: a CI for each median over concepts, from a two-level bootstrap (resample concepts, then take one bootstrap draw per concept; 2,000 replicates). |
| Reference check | The DINOv2-base row is recomputed by the same new script. It matches `docs/plato.md` within 0.02 everywhere; random human subsets move the last digit. |
| Hardware, cost | This Mac (MPS): 40 minutes for three models and 10,020 pictures. $0. |

Code: `metalesionlab/plato_robust.py`, `scripts/plato_robust_embed.py` and `scripts/plato_robust_analyze.py`. Results: `$PLATO_DIR/results_robustness.json`. Derived statistics: `public_data/plato_robustness.json`.

## Results at a glance

Medians over 35 concepts, with 95% CIs. "Muse/people" is the homogenization index (below 1: Muse more uniform than people).

| | DINOv2-base (reference) | DINOv2-large | PE-Core-L14-336 | SigLIP 2 So400m |
|---|---|---|---|---|
| Muse/people | 0.49 [0.41, 0.56] | 0.37 [0.29, 0.42] | 0.29 [0.23, 0.37] | 0.35 [0.28, 0.39] |
| Concepts below 1 (CI below 1) | 34 (33) | 35 (33) | 35 (34) | 35 (35) |
| Chair | 0.37 [0.24, 0.54] | 0.30 [0.18, 0.48] | 0.28 [0.21, 0.39] | 0.38 [0.27, 0.50] |
| Muse/SDXL | 0.42 [0.33, 0.47] | 0.33 [0.24, 0.39] | 0.29 [0.23, 0.35] | 0.30 [0.26, 0.34] |
| Concepts with Muse below SDXL | 34 | 35 | 35 | 35 |
| Rank agreement of concepts with DINOv2-base | (reference) | 0.82 [0.65, 0.91] | **0.43** [0.11, 0.69] | **0.34** [0.02, 0.61] |
| "Any kind" / usual prompt | 0.96 [0.88, 1.07] | 0.97 [0.87, 1.12] | 0.95 [0.84, 1.07] | 1.00 [0.88, 1.13] |
| Named kinds / people | 1.31 [1.11, 1.41] | 1.20 [1.03, 1.32] | 1.26 [1.08, 1.50] | 1.16 [1.06, 1.32] |
| SDXL/people | 1.23 [1.07, 1.37] | 1.12 [1.00, 1.30] | 0.98 [0.88, 1.15] | 1.16 [1.02, 1.28] |
| **Core result** | holds | **holds** | **holds in direction** | **holds in direction** |
| **Variety headline** | holds | **holds** | **holds** | **holds** |

The image-text models put Muse *further* below people than DINOv2 does, not closer to them.

## Per embedder

The checks are those of the plan:
- C1–C5: the core result;
- V1–V4: the variety headline;
- S1: SDXL is no more uniform than people.

A check passes when the rule in the last column is met.

### DINOv2-base (reference, recomputed)

| Measure | Value [95% CI] | Check |
|---|---|---|
| Muse/people, median | 0.49 [0.41, 0.56]; below 1 for 34 of 35 (CI for 33) | C1, C2 pass |
| Chair | 0.37 [0.24, 0.54] | C3 pass |
| Muse/SDXL, median | 0.42 [0.33, 0.47]; Muse below for 34 of 35 (CI for 32) | C4 pass |
| SDXL/people, median | 1.23 [1.07, 1.37]; below 1 for 9 of 35 | S1 pass |
| "Any kind" / usual; / people | 0.96 [0.88, 1.07]; 0.49 [0.39, 0.56] | V1, V2 pass |
| Named kinds / people; / usual | 1.31 [1.11, 1.41] (above people for 27); 2.73 [2.13, 3.13] | V3, V4 pass |
| Secondary | "Unusual kind" / people 1.08 [0.84, 1.32] (10 concepts). Muse–people spread rank correlation 0.36 [0.06, 0.61]. Relative index 0.34. |  |

### DINOv2-large: holds

| Measure | Value [95% CI] | Check |
|---|---|---|
| Muse/people, median | 0.37 [0.29, 0.42]; below 1 for 35 of 35 (CI for 33) | C1, C2 pass |
| Chair | 0.30 [0.18, 0.48] | C3 pass |
| Muse/SDXL, median | 0.33 [0.24, 0.39]; Muse below for 35 of 35 (CI for 34) | C4 pass |
| Rank agreement with base | 0.82 [0.65, 0.91] | C5 pass |
| SDXL/people, median | 1.12 [1.00, 1.30]; below 1 for 12 of 35 | S1 pass |
| "Any kind" / usual; / people | 0.97 [0.87, 1.12]; 0.35 [0.25, 0.43] | V1, V2 pass |
| Named kinds / people; / usual | 1.20 [1.03, 1.32] (above people for 25); 3.15 [2.70, 3.99] | V3, V4 pass |
| Secondary | "Unusual kind" / people 0.87 [0.75, 1.24]. Muse–people spread rank correlation 0.13 [-0.22, 0.44]. Relative index 0.28. Patch-mean vector: median 0.31, below 1 for 35, rank agreement with CLS 0.70. |  |

The ranking of the 35 concepts by Muse spread agrees with base at rho 0.79; by human spread, 0.92.

### PE-Core-L14-336: holds in direction

| Measure | Value [95% CI] | Check |
|---|---|---|
| Muse/people, median | 0.29 [0.23, 0.37]; below 1 for 35 of 35 (CI for 34) | C1, C2 pass |
| Chair | 0.28 [0.21, 0.39] | C3 pass |
| Muse/SDXL, median | 0.29 [0.23, 0.35]; Muse below for 35 of 35 (CI for 35) | C4 pass |
| Rank agreement with base | 0.43 [0.11, 0.69] | **C5 fails** |
| SDXL/people, median | 0.98 [0.88, 1.15]; below 1 for 19 of 35 | S1 pass |
| "Any kind" / usual; / people | 0.95 [0.84, 1.07]; 0.27 [0.22, 0.31] | V1, V2 pass |
| Named kinds / people; / usual | 1.26 [1.08, 1.50] (above people for 28); 4.14 [3.31, 5.24] | V3, V4 pass |
| Secondary | "Unusual kind" / people 1.17 [0.92, 1.46]. Muse–people spread rank correlation 0.07 [-0.26, 0.42]. Relative index 0.22. |  |

Rank agreement with base: 0.51 by Muse spread and 0.80 by human spread.

### SigLIP 2 So400m/14 (non-Meta control): holds in direction

| Measure | Value [95% CI] | Check |
|---|---|---|
| Muse/people, median | 0.35 [0.28, 0.39]; below 1 for 35 of 35 (CI for 35) | C1, C2 pass |
| Chair | 0.38 [0.27, 0.50] | C3 pass |
| Muse/SDXL, median | 0.30 [0.26, 0.34]; Muse below for 35 of 35 (CI for 35) | C4 pass |
| Rank agreement with base | 0.34 [0.02, 0.61] | **C5 fails** |
| SDXL/people, median | 1.16 [1.02, 1.28]; below 1 for 11 of 35 | S1 pass |
| "Any kind" / usual; / people | 1.00 [0.88, 1.13]; 0.35 [0.30, 0.39] | V1, V2 pass |
| Named kinds / people; / usual | 1.16 [1.06, 1.32] (above people for 25); 3.57 [2.82, 4.16] | V3, V4 pass |
| Secondary | "Unusual kind" / people 1.12 [0.91, 1.40]. Muse–people spread rank correlation 0.27 [-0.03, 0.50]. Relative index 0.32. |  |

Rank agreement with base: 0.38 by Muse spread and 0.72 by human spread.

## Where it doesn't hold

**Which concepts are most flattened depends on the model (C5 fails for PE-Core and SigLIP 2).** The two image-text models agree with each other only moderately (rho 0.63) and with DINOv2-large at 0.53–0.54.

| Concept | Rank among 35 (1 = most flattened): DINOv2-base, large, PE-Core, SigLIP 2 |
|---|---|
| umbrella | 1, 1, 8, 24 |
| clock | 34, 34, 7, 20 |
| key | 30, 25, 5, 16 |
| face | 15, 22, 34, 34 |
| cat | 10, 13, 23, 33 |
| book | 35, 35, 35, 35 |
| bicycle | 2, 3, 16, 4 |
| chair | 9, 12, 17, 22 |

- **Stable across all four.** Pineapple, carrot, bicycle and scissors are among the most flattened (median rank 2–4). Book, floor lamp and tree are among the least.
- **People's ranks are steadier than Muse's.** People's concept ranking is fairly stable across models (rho 0.72–0.92 with base); Muse's is not (0.38–0.79). Muse's spreads are small, so the order among them rests on fine differences that each model weighs differently.
- **What changes in the image-text models.**
  - Concepts that DINOv2 sees as varied because of a few odd pictures drop: clock (one or two unusual clocks drive its wide DINOv2 CI) and key.
  - Face and cat rise toward the least flattened. Perhaps these models weigh expression and pose more than outline.
  - Treat the per-concept ranking in `docs/plato.md` (umbrella first, clock near the top) as DINOv2's view.

**Other details that change:**
- **Chair vs boat.** In three models Muse flattens chairs more than boats, as the core reports. SigLIP 2 reverses it: chair 0.38, boat 0.31. People draw chairs more variably than boats in all four, though only slightly in SigLIP 2 (0.116 vs 0.112).
- **Book.** DINOv2-base is the only model where Muse's books reach people's level (1.05). In the others book is still the least flattened concept, but below 1 (0.78–0.95); in SigLIP 2 its CI is below 1 too.
- **Does Muse's spread follow people's?** No reliable link. With DINOv2-base the rank correlation is 0.36–0.38 (p ≈ 0.03). With the other three it is 0.07–0.27, and every CI spans zero. The core doc's "only somewhat" should read "weakly at best".
- **SDXL vs people.** SDXL is no more uniform than people in all four (S1 passes). Its median ratio is above 1 in three models (1.12–1.23) but 0.98 [0.88, 1.15] in PE-Core, where it is below people for 19 of 35 concepts. "SDXL is as varied as people, or more" is safe; "SDXL is more varied than people" is not.
- **"An unusual kind"** (10 concepts, secondary): 0.87–1.17 times people's spread, with a CI that includes 1 in all four. That is about people's level, not clearly above it.

**Predictions** (from the plan, written before any result):
- Right: DINOv2-large agrees with base (rho 0.82; every check passes).
- Right: the variety headline holds in all three.
- Wrong: the image-text models were expected to move the median ratio toward 1. They moved it further down (0.29 and 0.35).
- Partly right: rank agreement for the image-text models was expected at 0.4–0.7. PE-Core is inside that range (0.43); SigLIP 2 is below it (0.34).

## Can each model tell the doodles apart?

A model that cannot separate the 35 concepts in doodles would make a poor ruler for spread. All four separate them well, and the image-text models best.

| | DINOv2-base | DINOv2-large | PE-Core | SigLIP 2 |
|---|---|---|---|---|
| People's drawings nearest their own concept (left out of its centroid), of 35 | 71% | 70% | 83% | 85% |
| Muse doodles nearest people's centroid of their concept | 85% | 80% | 93% | 90% |
| SDXL doodles nearest people's centroid of their concept | 77% | 84% | 88% | 84% |
| Mean spread: Muse, SDXL, people | 0.18, 0.44, 0.37 | 0.14, 0.44, 0.39 | 0.045, 0.15, 0.14 | 0.044, 0.14, 0.12 |
| Relative index (spread / between-concept distance), median; concepts below 1 | 0.34; 35 | 0.28; 35 | 0.22; 35 | 0.32; 35 |

Distances in the image-text spaces are a quarter to a third of DINOv2's, so absolute spreads are not comparable across models. Only ratios are.

## Deviations and additions

- **Method.** No deviations: the embedders, vectors, pictures, statistics and rules are as planned.
- **Reference row.** It differs from `docs/plato.md` by at most 0.02. Examples: named kinds / people 1.31 vs 1.30, SDXL/people 1.23 vs 1.22, the Muse–people rank correlation 0.36 vs 0.38, the chair's upper CI 0.54 vs 0.55. Random human subsets explain the differences.
- **Additions not in the plan (exploratory).**
  - Rank agreement with base for the SDXL/people ratio (0.88, 0.63, 0.65), the Muse/SDXL ratio (0.81, 0.61, 0.51) and the named kinds / people ratio (0.95, 0.82, 0.71).
  - The agreement matrix between all four models.
  - The per-concept rank table above.

## Caveats

- **None of the four models was trained on doodles.** All are general image models, trained mostly on photographs.
- **The style gap remains.** The same ink crop is used everywhere, so the style difference between Muse's clean cartoons and people's 20-second scribbles is still there (see `docs/plato.md`, Caveats). The image-text models may read part of that difference as content. A style-matched comparison is still open.
- **One vector per model,** fixed in advance. Inner layers or patch tokens might rank concepts differently. DINOv2-large's patch-mean vector gives the same direction (median 0.31) with a somewhat different ranking (rho 0.70 with its CLS vector).
- **DINOv3 untested** (gated). PE-Core-G and OpenAI CLIP were left out by choice.

Model credits: DINOv2 and Perception Encoder (Meta, Apache-2.0); SigLIP 2 (Google, Apache-2.0); timm (Ross Wightman, Apache-2.0). Human drawings: Google Quick, Draw! dataset, Google Creative Lab, CC BY 4.0 (https://github.com/googlecreativelab/quickdraw-dataset). No drawings or embeddings are committed.

# The life of a chair: pre-registered plan

Written and committed on 2026-10-27, before any children's drawing was embedded and before any Stable Diffusion picture was drawn. Only the counts below (from the dataset's metadata file) were looked at.

**Question.** Plato's *Meno* says that learning is recollecting the Forms. As children grow up, and as an image model is trained, do their drawings of a chair (and 19 other things) converge on a shared prototype? Do the two follow the same path?

## Data and licenses (checked in step 0)

| Source | What | License, access |
|---|---|---|
| Children | Long, Fan, Huey, Chai & Frank (2024), *Parallel developmental changes in children's production and recognition of line drawings of visual concepts*, Nature Communications 15:1191. 37,770 drawings of 48 categories by 8,084 children aged 2 to 10, drawn with a fingertip on a tablet at a museum kiosk (30 s per drawing), after crowd-sourced filtering ("stringent_cleaned_dataset"). Stroke data: `full_dataset_with_strokes`. OSF 10.17605/OSF.IO/QYMJR | The OSF project has no license set. The paper's data and code repository (github.com/brialorelle/drawing_production_and_recognition), which shares the drawings, is **CC BY-NC-SA 4.0**. The article is CC BY 4.0. |
| Adults | Google Quick, Draw!, the 200 cached recognized drawings per concept (`PlatosChair/core/embeddings/human/`) | CC BY 4.0 |
| Muse | Muse Image doodles from the core run (`PlatosChair/core/embeddings/ai_doodle/`) | our outputs |
| AI training stages | Stable Diffusion v1.1, v1.2, v1.3, v1.4 (`CompVis/stable-diffusion-v1-1` … `v1-4`) and v1.5 (`stable-diffusion-v1-5/stable-diffusion-v1-5` mirror). None are gated; no token or license click is needed | CreativeML OpenRAIL-M |
| Embedding | Meta DINOv2 (`facebook/dinov2-base`), CLS token | Apache-2.0 |

**Display rule.** The drawings are licensed non-commercially with share-alike, and they are children's. So this project uses **derived, group-level statistics only**. No child's drawing goes into the repository, the site or the figures. Where a figure needs a picture for an age, it shows a clearly labeled **Quick, Draw! stand-in**: the adult drawing (CC BY 4.0) nearest to that age group's centroid in DINOv2 space. Because no drawing is shown, no screening for writing is needed, and no paid model call is planned ($0).

**Other staged models (not in the primary analysis).** Stability's own SD 2.x repositories are gone from Hugging Face. Community mirrors exist (`sd2-community/stable-diffusion-2-base` → `-2` → `-2-1`, OpenRAIL++). PixArt-α has open resolution stages (`PixArt-XL-2-256x256` → `512x512` → `1024-MS`, OpenRAIL++), but it needs a T5-XXL text encoder. AuraFlow v0.1 → v0.2 → v0.3 (Apache-2.0, 6.8B) is too large to share the GPU. Any of these is exploratory, if time allows.

## Things (concepts)

The 20 kiddraw categories that have a Quick, Draw! category and a Muse prototype: **chair**, boat (Quick, Draw! and Muse: sailboat; approximate), face, house, cat, cup, tree, car, key, bicycle (kiddraw "bike"), snail, cactus, bird, fish, dog, hat, clock, book, apple, scissors.

Left out: lamp and person. Our references are a floor lamp and "a person doing yoga", which are not what the children were asked to draw. Umbrella (tier 1) has no children's drawings. The AI arm draws it and reports it on its own.

Counts (drawings per age, from the metadata): chair 43, 70, 77, 81, 69, 44, 41, 25, 47 at ages 2–10. The smallest cell of the 20 things is 23 (bicycle, age 9). **Age groups are single years, 2 to 10, without pooling**, since every cell has at least 23 drawings. Age is as entered by a parent; 10 is the oldest value.

## Preparing the pictures

- **Children (primary).** The stroke data, restricted to the drawings in `stringent_cleaned_dataset`, go through Quick, Draw!'s own simplification: align to the top-left, scale uniformly so the longest side is 255, resample at 1 px, then Ramer–Douglas–Peucker with epsilon 2.0. They are rendered by the same code as the adult drawings (`plato.render_strokes`, 256 px, 3 px lines), then `ink_crop`, then DINOv2. Children's and adults' drawings are thus rendered identically, so line width cannot vary with age.
- **Children (robustness check).** The released 150 px PNGs, composited on white, then `ink_crop`.
- **AI.** As in the core run: `ink_crop` of the 512 px picture, then DINOv2.
- A drawing with no ink after rendering is dropped and counted.

## Measures (every source; for children, per thing × age)

1. **Spread**: mean pairwise cosine distance at matched n = 16. Children and adults: mean of 200 random 16-drawing subsets. AI: its 16 pictures. 95% CI by bootstrap over drawings (pictures), never pairing a drawing with itself.
2. **Distance to the adult prototype** (primary prototype measure): mean over drawings of the cosine distance from each drawing to the adult prototype. The adult prototype is the normalized mean of the 200 Quick, Draw! unit vectors. It doesn't depend on n. The adults' own value is leave-one-out (each drawing against the prototype of the other 199).
3. **Distance to Muse's prototype**: the same, to the mean of Muse Image's doodles (16 or 12).
4. **Recognizability**: the share of drawings whose most similar adult prototype, among 21 candidates (the 20 things plus umbrella; chance 4.8%), is their own thing. Adults: leave-one-out.
5. Secondary: **centroid displacement**, the cosine distance between a group's centroid and the adult prototype at matched n = 16 (mean over subsets). It separates "where the group sits" from "how far a typical drawing is".

## Children's arm: predictions and tests

For each measure, per thing: an ordinary least squares slope on age (years, 9 points). Group effect = mean slope over the 20 things. 95% CI from a two-level bootstrap (2,000 replicates): resample things, then drawings within each thing × age cell, and recompute everything. Seed 20261027.

| # | Prediction | Supported if |
|---|---|---|
| C1 | Recognizability rises with age | mean slope > 0, CI above 0 |
| C2 | Drawings move closer to the adult prototype | mean slope of distance < 0, CI below 0 |
| C3 | Spread first rises, then falls | in a quadratic fit on (age − 6), the mean quadratic coefficient's CI is below 0 **and** the peak age's bootstrap CI lies inside 2–10. Otherwise we report the linear direction. |
| C4 (exploratory) | Drawings move closer to Muse's prototype | mean slope < 0, CI below 0 |

Also reported: the gap between 10-year-olds and adults on each measure (bootstrap CI), each thing's own slope, and the chair on its own. Robustness: the PNG rendering, and dropping the boat (an approximate match). Four primary tests, no correction for multiple tests; all are reported.

## AI arm: Stable Diffusion's training stages

| Checkpoint | Lineage (model cards) | Cumulative steps |
|---|---|---|
| v1.1 | 237k steps at 256 px on LAION-2B-en, then 194k at 512 px on LAION high-resolution | 431k |
| v1.2 | resumed from v1.1; 515k at 512 px on LAION improved-aesthetics | 946k |
| v1.3 | resumed from v1.2; 195k on improved-aesthetics, 10% text dropout | 1,141k |
| v1.4 | resumed from v1.2; 225k on LAION-aesthetics v2 5+, 10% text dropout | 1,171k |
| v1.5 | resumed from v1.2; 595k on LAION-aesthetics v2 5+, 10% text dropout | 1,541k |

v1.3, v1.4 and v1.5 are siblings that branch from v1.2, not a single chain. The x axis is cumulative training steps.

- **Prompt.** The core doodle prompt, `plato.STYLES["doodle"]`: *"A quick simple doodle sketch of {a chair}, black marker on plain white, like a 20-second drawing, no text, no shading."* The negative prompt is the SDXL run's (*"shading, photo, photorealistic, paper texture, 3d render, color, text"*).
- **Settings.** 512 px, fp16, Euler scheduler, 30 steps, guidance 7.5 (the SD 1.x default), safety checker off (black-and-white doodles of objects).
- **Seeds.** 16 per thing, seed = 20261027 + 1000 × (the thing's index in `plato.CONCEPTS`) + i. They are identical across checkpoints, so every checkpoint starts from the same noise and only the weights differ.
- **Things.** Primary: the 10 tier-1 things (chair, boat, face, house, cat, cup, tree, car, key, umbrella). Extension, same settings: the other 11 children's things, so that the AI and children can be compared on the same 20.
- **Robustness (if time allows).** Guidance 4, because v1.1 and v1.2 were trained without text dropout and so may respond differently to classifier-free guidance.

| # | Prediction | Supported if |
|---|---|---|
| A1 | Recognizability rises with training | mean slope on cumulative steps > 0 (CI) and v1.5 − v1.1 > 0 (CI) |
| A2 | Spread narrows with training | mean slope < 0 (CI) and v1.5 − v1.1 < 0 (CI) |
| A3 (two-sided) | Distance to the adult and to Muse's prototype change with training | slope CI excludes 0 |

The bootstrap resamples things, then pictures within each thing × checkpoint cell.

## Does the AI's path resemble the children's?

Computed on the things both arms share (all 20 if the extension is drawn, otherwise the 9 shared tier-1 things):

1. **Direction agreement.** For each of the four measures, does the sign of the AI's training effect (v1.5 − v1.1) match the sign of the children's age slope? Only directions whose CIs exclude zero count. "Resembles" means they agree on every measure where both are clear.
2. **Developmental age equivalent** (descriptive). For each checkpoint, the age at which the children's mean recognizability curve (over the shared things, linear interpolation between ages) reaches the checkpoint's recognizability. Outside the range it is reported as "below age 2" or "beyond age 10". Bootstrap CI.
3. **Same direction in DINOv2 space** (exploratory). Per thing, the cosine between the AI's displacement (centroid of v1.5 − centroid of v1.1) and the children's (centroid at age 10 − centroid at age 2). We report the mean over things, against a null of mismatched things (displacements paired across different things).

## Stretch (only once both arms are done)

Train a small sketch model from scratch on Quick, Draw! chairs: a Sketch-RNN-style decoder or a tiny diffusion model on 64 px renders. Track spread, recognizability and distance to the adult prototype over training steps. Question: does it end narrower than its training drawings (mode-seeking)? Exploratory, no prediction beyond that.

## Outputs

- `docs/plato_lifespan.md` (results).
- `public_data/plato_lifespan.json`: group-level statistics only, with no drawings, embeddings or per-drawing values.
- Figures in `PlatosChair/lifespan/figures/`.
- The page `/plato/lifespan`.

Raw drawings, stroke files, embeddings and AI pictures stay in `PlatosChair/lifespan/`, outside the repository.

**Caveats known in advance.**
- The drawing conditions differ: a fingertip on a kiosk tablet in 30 s, versus a mouse or finger in 20 s for Quick, Draw!, versus a generated doodle.
- The SD checkpoints differ in training data as well as in steps.
- Ages are whole years entered by a parent.
- The museum sample is not representative of all children.
- DINOv2 measures visual similarity, not knowledge.
- The "decline" end of the lifespan is an analogy, through the damaged-AI experiment (`/plato/damage`). This project makes no medical claim.

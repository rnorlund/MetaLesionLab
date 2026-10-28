# The life of a chair

Plato's *Meno* says learning is recollecting the Forms. If so, children growing up and an AI being trained should both converge on a shared prototype of a chair. Do they? And do they follow the same path?

Plan, committed before any data were measured: `docs/plato_lifespan_plan.md`. Page: `/plato/lifespan`.

## Short answer

**Children walk toward the Form.** From age 2 to 10, their drawings of 20 things become more recognizable and closer to the adults' average.
- Recognizability: 39% → 72%, +4.5 points a year [3.7, 5.3]. The slope is positive for all 20 things.
- Distance to the adult prototype: 0.29 → 0.24 (adults 0.20).
- Their variety narrows, mostly by age 6. It doesn't rise first, as we had predicted.
- At 10 they are not there yet. They are less recognizable than adults (72% vs 86%) and farther from the adult prototype.

**Stable Diffusion's training stages don't follow that path in any robust way.**
- Its first public checkpoint (v1.1, 431k steps) is already as recognizable as a 10-year-old.
- From v1.1 to v1.5 it moves the same way as children on three of four measures, over 21 things. It becomes more recognizable (+11 points [2, 21], mostly at v1.2), slightly narrower and closer to Muse's prototype.
- It never comes any closer to people's drawings (0.62 at v1.1 and at v1.5).
- For the pre-registered primary set of 10 things nothing changes clearly, and none of it survives at a lower guidance setting.

**An AI that learns only from people's chairs does grow up like a child.** We trained a small sketch model from scratch on 20,000 Quick, Draw! chairs, 8 times with different seeds (`docs/plato_sketch.md`, pre-registered in `docs/plato_sketch_plan.md`).
- It starts with scribbles (18% recognizable, distance 0.51) and passes through the range of children's chairs.
- It ends as close to the adult prototype as adults (0.20) and 87% recognizable (mean of 8 runs, temperature 1).
- It ends **less varied than the chairs it learned from**, in all 8 runs: spread 0.315 vs 0.375, difference −0.059 [−0.067, −0.052] across runs. The narrowing holds at sampling temperatures 0.8 and 0.6 too (−0.051, −0.049; 8 of 8 runs each).
- **The narrowing is not general.** The same model trained on cats (5 runs) learns them much less well (39% recognizable, against 84% for its training cats). It ends *more* varied than its training cats: +0.024 [+0.019, +0.029], 0 of 5 runs narrower.
- The first run, on this Mac, had found −0.048 [−0.076, −0.022] with one seed.

## Data and licenses

| Source | What | License |
|---|---|---|
| Children | Long, Fan, Huey, Chai & Frank (2024), *Nature Communications* 15:1191. Museum-kiosk drawings, fingertip on a tablet, 30 s each, ages 2–10, after the authors' crowd-sourced filtering ("stringent_cleaned_dataset", 37,770 drawings of 48 categories). We use the **15,820 drawings of the 20 categories that also exist in Quick, Draw! and in our Muse runs**. Each thing × age cell has 23 to 245 drawings. | The OSF project (10.17605/OSF.IO/QYMJR) sets no license. The authors' data and code repository (github.com/brialorelle/drawing_production_and_recognition), which ships the drawings, is **CC BY-NC-SA 4.0**. The article is CC BY 4.0. |
| Adults | Google Quick, Draw!: the 200 cached recognized drawings per thing (the "adult prototype"). For the sketch model, 20,000 further recognized chairs. | CC BY 4.0 |
| Muse | Muse Image 1.0 doodles from the core Plato's Chair run (16 or 12 per thing) | our outputs |
| AI stages | Stable Diffusion v1.1, v1.2, v1.3, v1.4 (`CompVis/stable-diffusion-v1-1` … `v1-4`) and v1.5 (`stable-diffusion-v1-5/stable-diffusion-v1-5`, the mirror of the RunwayML release). **None is gated**: no token or license click was needed. | CreativeML OpenRAIL-M |
| Embedding | Meta DINOv2 (`facebook/dinov2-base`), CLS token | Apache-2.0 |

- **Display rule.** The drawings are non-commercial and share-alike, and they are children's. So we show **no child's drawing anywhere**: not in the repository, on the site or in the figures. `public_data/plato_lifespan.json` holds group-level statistics only (every cell pools at least 23 drawings). The figures and the page show children's stages as an icon array of how many in 10 drawings are recognizable.
  - We tried Quick, Draw! stand-ins: the adult drawing nearest each age group's centroid, or nearest its medoid in a 3,000-drawing pool. They were all ordinary adult chairs at every age, so they would have suggested 2-year-olds draw like adults, and we dropped them.
  - Since no drawing is shown, no screening for writing was needed.
- **Other staged models we found.**
  - Stability's own SD 2.x repositories are gone from Hugging Face. Community mirrors exist (`sd2-community/stable-diffusion-2-base` → `-2` → `-2-1`, OpenRAIL++).
  - PixArt-α has open resolution stages (`PixArt-XL-2-256x256` → `512x512` → `1024-MS`), but needs a T5-XXL encoder.
  - AuraFlow v0.1 → v0.3 (Apache-2.0) is too big to share the GPU.
  - None was needed: the sketch model covers the early stages that SD's checkpoints lack.

## Method

| Step | What we did |
|---|---|
| Children's pictures | The stroke data of the stringent set, clipped to the visible 810 px canvas. That scale was fitted against the released 150 px PNGs, a factor of 5.40 in every run; without it, strokes that left the screen would appear. Then exactly Quick, Draw!'s simplification: align to the top-left, scale to 255, resample at 1 px, Ramer–Douglas–Peucker with ε = 2. Rendered by the same code as the adult drawings (`plato.render_strokes`, 3 px lines), so line width cannot vary with age. Robustness: the released PNGs. |
| SD pictures | The core doodle prompt (*"A quick simple doodle sketch of a chair, black marker on plain white, like a 20-second drawing, no text, no shading."*) and the SDXL run's negative prompt, for 21 things: the 20 and umbrella. 512 px, fp16, Euler, 30 steps, guidance 7.5, safety checker off. 16 seeds per thing, **the same at every checkpoint**, so each picture starts from the same noise and only the weights differ. 1,680 pictures in 37 min, and 800 more at guidance 4 in 18 min, on an L40S shared with Glimmer (peak 2.6 GiB). |
| Sketch model | A Sketch-RNN-style decoder (LSTM 512, 20-component Gaussian mixture, unconditional), trained from random weights. Data: 20,000 recognized Quick, Draw! chairs, the ones after the 200 used as the adult reference. 25,600 steps of batch 100. First run: this Mac (MPS, 20 min), 64 chairs at 11 log-spaced steps, at temperature 1 and 0.5. **Main runs** (`docs/plato_sketch.md`): the same model and data, **8 seeds** on an L40S, 200 drawings at each of 20 log-spaced steps and temperatures 1.0, 0.8 and 0.6, from noise fixed per seed. They are compared with 1,000 of the training chairs. Cats (5 seeds) are the generality check. Drawings that are a single point are not drawings and are dropped; none of the children's drawings is a single point. |
| Measures | Every set was rendered or cropped to its ink and embedded with DINOv2. **Recognizable**: share of drawings whose most similar adult prototype, among 21, is their own thing (chance 4.8%). **Distance to the adult Form**: mean cosine distance of each drawing to its thing's adult prototype. **Distance to Muse's Form**: the same, to Muse Image's prototype. **Spread**: mean pairwise distance at matched n = 16. Adults and Muse are compared with their own prototype leave-one-out. |
| Statistics | Children: per thing, an OLS slope on age (9 points); the group effect is the mean slope. 95% CIs from a two-level bootstrap (2,000 replicates; things, then drawings within each cell). AI: the slope on cumulative training steps and v1.5 − v1.1, with the same bootstrap over things and pictures. Seed 20261027. |

## Findings

### Children (20 things, 15,820 drawings)

| Measure | Age 2 | Age 6 | Age 10 | Adults | Slope per year [95% CI] | Things with that sign | Age 10 − adults |
|---|---|---|---|---|---|---|---|
| Recognizable | 39% [33, 45] | 59% | 72% [66, 78] | 86% | **+4.5 points** [3.7, 5.3] | 20 of 20 | −13.5 points [−19.1, −7.8] |
| Distance to the adult Form | 0.287 [0.271, 0.304] | 0.243 | 0.243 [0.230, 0.256] | 0.198 | **−0.0054** [−0.0070, −0.0036] | 18 of 20 | +0.045 [0.032, 0.061] |
| Spread | 0.428 [0.411, 0.445] | 0.388 | 0.396 [0.374, 0.416] | 0.353 | **−0.0033** [−0.0055, −0.0014] | 16 of 20 | +0.043 [0.024, 0.061] |
| Distance to Muse's Form | 0.564 | 0.514 | 0.474 | 0.495 | **−0.0119** [−0.0145, −0.0093] | 19 of 20 | −0.021 [−0.042, 0.000] |

Pre-registered predictions:
- **C1** (recognizability rises): **supported**.
- **C2** (closer to the adult prototype): **supported**. Most of the approach happens by age 6, then it plateaus 0.045 above adults.
- **C3** (spread rises, then falls): **not supported**. The quadratic is U-shaped, not an inverted U (coefficient +0.0013 [0.0005, 0.0020]). Spread falls until about age 7 (vertex 7.3 [6.5, 9.2]) and then levels off. The linear direction is down.
- **C4** (closer to Muse's prototype, exploratory): **supported**, and steadily. By 10 they are as close to Muse's chair as adults, perhaps slightly closer.

**The chair.** Recognizable 53% at 2, 80% at 6 and 89% at 10 (adults 92%). Distance to the adult Form 0.28 → 0.21 at 6, then 0.25. Spread 0.44 → 0.36 at 6, then 0.41.

**Robustness.** The children's results hold with every check: the released PNGs instead of re-rendered strokes, leaving out the boat (an approximate match), and DINOv2 patch-mean embeddings. The yearly recognizability slope is +4.5 to +4.6 points in each. All four slopes keep their sign and their CI.

### Stable Diffusion's training stages

| Things | Measure | v1.1 | v1.2 | v1.3 | v1.4 | v1.5 | v1.5 − v1.1 [95% CI] |
|---|---|---|---|---|---|---|---|
| 10 tier-1 (primary) | Recognizable | 86% | 90% | 89% | 89% | 89% | +3.1 points [−4.4, +12.5] |
| | Spread | 0.471 | 0.482 | 0.462 | 0.487 | 0.446 | −0.025 [−0.086, 0.041] |
| | Distance to the adult Form | 0.574 | 0.593 | 0.568 | 0.597 | 0.577 | +0.003 [−0.033, 0.045] |
| | Distance to Muse's Form | 0.433 | 0.434 | 0.406 | 0.442 | 0.412 | −0.021 [−0.076, 0.035] |
| All 21 (extension) | Recognizable | 75% | 84% | 85% | 86% | 86% | **+11.0 points [2.4, 20.5]** |
| | Spread | 0.511 | 0.501 | 0.489 | 0.501 | 0.466 | −0.046 [−0.095, 0.001] |
| | Distance to the adult Form | 0.616 | 0.635 | 0.613 | 0.630 | 0.619 | +0.003 [−0.023, 0.032] |
| | Distance to Muse's Form | 0.480 | 0.465 | 0.447 | 0.463 | 0.431 | **−0.049 [−0.097, −0.005]** |

Pre-registered predictions:
- **A1** (recognizability rises): not supported for the 10 primary things; supported for all 21, driven by v1.1 → v1.2 (on the 9 tier-1 things v1.1 is already 86%).
- **A2** (spread narrows): not supported (the CI touches 0). It is supported only with patch-mean embeddings, over 21 things.
- **A3** (the prototype distances change): no change in distance to the adult prototype. Distance to Muse's prototype falls over 21 things.
- **Guidance 4** (robustness, 10 things): no measure changes clearly (v1.5 − v1.1 recognizability +3.1 points [−10.6, +18.8]).

Muse Image (0.43) and SDXL (0.66) are far from people's drawings too. The AI's distance to the adult prototype is mostly drawing style: marker sketches on paper, frames and shading, against thin 3 px lines.

### Does the AI's path resemble the children's?

**Only loosely, and not robustly.**
- **Direction agreement** (pre-registered; 20 shared things, v1.5 − v1.1 against the children's age slope):
  - The AI agrees on every measure where both are clear: recognizability up (+11.9 points [3.4, 21.9]), spread down (−0.049 [−0.099, −0.001]), distance to Muse's Form down (−0.052 [−0.103, −0.011]).
  - On distance to the adult Form, children move and the AI doesn't.
  - So the criterion is met in the primary analysis, but it falls apart under robustness checks. At guidance 4 none of the AI's changes is clear. With patch-mean embeddings recognizability isn't. Without the boat spread isn't.
- **Developmental age equivalent.** Every checkpoint is "beyond age 10" on recognizability: v1.1 is 74% over the 20 things, against 72% for 10-year-olds. Stable Diffusion has no public childhood.
- **Same direction in DINOv2 space?** No. The AI's v1.1 → v1.5 displacement is no more aligned with the children's age 2 → 10 displacement for the same thing than with a different thing's (cosine 0.048 vs 0.018; difference 0.030 [−0.019, 0.079]).

### Stretch: an AI that grows up on people's chairs

The full write-up is `docs/plato_sketch.md`. It covers 8 seeds, 3 temperatures, robustness checks, the cat check and the animation.

Temperature 1, mean of 8 runs, 200 drawings per run and step (95% CIs across runs). Drawings that are a single point are not counted, so early steps have fewer drawings.

| Training step | Drawings (of 200) | Recognizable | Distance to the adult Form | Spread | Spread − training drawings |
|---|---|---|---|---|---|
| 0 (random weights) | 89 | 18% | 0.511 | 0.434 | +0.059 [+0.048, +0.070] |
| 100 | 110 | 52% | 0.363 | 0.420 | +0.045 [+0.034, +0.056] |
| 200 | 132 | 64% | 0.299 | 0.374 | −0.001 [−0.014, +0.013] |
| 800 | 160 | 68% | 0.265 | 0.344 | −0.031 [−0.042, −0.019] |
| 3,200 | 191 | 75% | 0.234 | 0.319 | −0.056 [−0.065, −0.046] |
| 12,800 | 200 | 83% | 0.208 | 0.319 | −0.056 [−0.064, −0.048] |
| 25,600 (last) | 200 | 87% | 0.201 | 0.315 | **−0.059 [−0.067, −0.052]** |
| its training drawings (1,000 of 20,000) | 1,000 | 94% | 0.211 | 0.375 | |

- Its path looks like the children's chair path: recognizability up, distance to the Form down, spread down.
  - It reaches a 2-year-old's recognizability at step 150 and a 6-year-old's at step 6,400.
  - It ends just under a 10-year-old's at temperature 1 (87% vs 89%) and above it at 0.8 and 0.6 (90%, 92%).
- **Narrower than what it learned from, in every run.** At its own temperature it ends 16% narrower.
  - The two-level bootstrap over runs and drawings gives [−0.070, −0.048]; all 8 runs are below 0.
  - It holds at temperature 0.8 (−0.051 [−0.056, −0.046]) and 0.6 (−0.049 [−0.056, −0.041]).
  - It holds for the last three checkpoints, for a reference passed through the model's stroke conversion, and for patch-mean embeddings.
- It is also pulled toward the typical chair: its final chairs sit closer to the adult prototype than its training chairs do (0.201 [0.196, 0.205] vs 0.211).
- **Cats go the other way.** The same model, trained the same way on 20,000 cats (5 runs), learns them much less well: 39% recognizable at temperature 1, against 84% for its training cats. Quick, Draw! cats have about twice the strokes and points of chairs.
  - It ends *more* varied than its training cats (+0.024 [+0.019, +0.029]; 0 of 5 runs narrower), and also at 0.8.
  - At 0.6, where its cats are 76% recognizable, there is no clear difference.
  - The narrowing seems to come with competence, not with learning from people as such.
- **The first run** (this Mac, one seed, 64 drawings, against 200 training chairs) found −0.048 [−0.076, −0.022] at temperature 1, and no narrowing at 0.5 (+0.001 [−0.035, 0.029]). The narrowing replicates. The null at 0.5 does not carry over to 0.6 (we did not test 0.5).

## Caveats

- **Different drawing conditions.** Fingertip on a museum tablet (30 s), a 20-second online game (mouse or finger), and generated pictures that look like marker sketches. Re-rendering every stroke the same way removes line width, not skill or effort.
- **Ages** are whole years entered by a parent. The paper reports that parents sometimes interfered, which may inflate the youngest children's recognizability. Children at a science museum are not a sample of all children. The kiosk asked for six different sets of eight categories over time, so different things come from partly different children.
- **Stable Diffusion's checkpoints** differ in training data (LAION-2B-en, then high-resolution, then aesthetics-filtered subsets) and in text-dropout, not only in steps. v1.3, v1.4 and v1.5 are siblings from v1.2, not a chain. The earliest public checkpoint is already far into training. One prompt; guidance 7.5, with 4 as a check.
- **DINOv2** measures how drawings look. "Recognizable" is nearest-prototype classification among 21 things, not human recognition.
- **The sketch model** learns only adults' drawings. It is 8 runs (and 5 on cats) of one small architecture, so it shows what learning from people's drawings can look like, not what children do.
- **The end of the lifespan** (losing the chair) is an analogy, through the damaged-AI experiment (`/plato/damage`), not a claim about people or about ageing. No medical claim is made.

**Deviations from the plan.**
- The strokes are clipped to the visible canvas. The released PNGs revealed that strokes can leave it, and we matched what the children saw.
- A drawing that is a single point counts as no drawing. That affects only the sketch model's early steps; no child's drawing is a single point.
- The paths figure and the "life" strip use icon arrays instead of the planned stand-ins (see the display rule).

## Cost

**$0.** No paid API calls (no Muse Spark screening was needed, because no drawing is shown).
- GPU: 55 min of SD on axon-server01 next to Glimmer, and 54 min (0.9 GPU-hours) for the sketch model's 13 runs (training, drawing and DINOv2) on the same L40S.
- Embeddings for the children and SD, the first sketch run, and all analyses ran on this Mac.

## Files

- Code:
  - `metalesionlab/plato_lifespan.py`
  - `scripts/plato_lifespan_{sd_generate,embed,analyze,figures,qd_pool,sketch}.py`
  - tests in `tests/test_plato_lifespan.py`
  - the multi-seed sketch model: `metalesionlab/plato_sketch.py` and `scripts/plato_sketch_{seeds,analyze,animate}.py`, tests in `tests/test_plato_sketch.py` (see `docs/plato_sketch.md`)
- Page:
  - `metalesionlab/web/pages/plato_lifespan.html`
  - `static/js/plato_lifespan.js`, `static/css/plato_lifespan.css`
  - pictures in `static/img/plato_lifespan/`; the time-lapse sprite and the stroke-by-stroke chair in `static/img/plato_lifespan/sketch/`
  - `metalesionlab/web/plato_lifespan_routes.py`
- Data, all outside the repo (`PlatosChair/lifespan/`): `kiddraw_raw/` (downloads), `ai/sd`, `ai/sd_g4`, `sketch/` (the first run; `sketch/seeds/` the 13 GPU runs and their `results.json`), `embeddings/`, `results.json`, and `results_robust_{png,noboat,patch,g4}.json`.
- Animations: `sketch/watch_it_learn.{mp4,gif}` and `sketch/stroke_by_stroke.{mp4,gif}`.
- Figures (`PlatosChair/lifespan/figures/`):
  - `life_of_a_chair.png`: the timeline strip. Children as icon arrays, then adults, Muse, SD v1.1–v1.5 from one seed, and a slot for the damaged AI.
  - `life_curves.{png,svg}` and `life_curves_tier1.{png,svg}`: the four measures against age and against training steps.
  - `life_paths.{png,svg}`: recognizability against distance to the adult Form.
  - `life_sketch.png`: the first sketch run's chairs at six training steps.
  - `sketch_seeds_curves.png`: the multi-seed learning path (chair and cat).
- Public statistics: `public_data/plato_lifespan.json`.

**Re-running** (all steps are cached or resumable):
```
python -I scripts/plato_lifespan_embed.py --sources kids kids_png        # Mac
# server: PYTHONPATH=~/MetaLesionLab_lifespan/pylib python scripts/plato_lifespan_sd_generate.py --out ~/plato_lifespan/sd
rsync -a axon-server01:plato_lifespan/sd axon-server01:plato_lifespan/sd_g4 PlatosChair/lifespan/ai/
python -I scripts/plato_lifespan_embed.py --sources sd sd_g4
python -I scripts/plato_lifespan_sketch.py fetch && python -I scripts/plato_lifespan_sketch.py train --data .../train_chair.ndjson --out PlatosChair/lifespan/sketch --device mps && python -I scripts/plato_lifespan_sketch.py embed
python -I scripts/plato_lifespan_analyze.py --public public_data/plato_lifespan.json
python -I scripts/plato_lifespan_figures.py --web
# the 13 sketch runs on the GPU, then: see docs/plato_sketch.md
python -I scripts/plato_sketch_analyze.py --public public_data/plato_lifespan.json && python -I scripts/plato_sketch_animate.py --web
```

Credits: children's drawings, Long, B., Fan, J. E., Huey, H., Chai, Z., & Frank, M. C. (2024), doi:10.1038/s41467-023-44529-9, data CC BY-NC-SA 4.0 (statistics only). Quick, Draw!, Google Creative Lab, CC BY 4.0. Stable Diffusion v1.x, CompVis / Stability AI / RunwayML, CreativeML OpenRAIL-M. DINOv2, Meta, Apache-2.0. Sketch-RNN design, Ha & Eck (2017).

# Watch an AI learn what a chair is

A sketch model learns what a chair is from people's drawings alone. Does it end up **narrower**, less varied, than the drawings it learned from?

There are two models, both Sketch-RNN-style decoders trained from random weights:
- **The larger model** is the one the page's animation shows: LSTM 2,048, all 203,324 recognized Quick, Draw! chairs, 102,400 steps, 4 runs.
- **The small model** came first: LSTM 512, 20,000 chairs, 25,600 steps, 8 runs, plus 5 on cats. Its chairs were recognizable to the measure but rough to a person's eye.

Each model's test was committed before its runs were trained: `docs/plato_sketch_plan.md` for the small model, and its addendum for the larger one. The addendum was written after the larger model's first (pilot) run and before its other three. Page: `/plato/lifespan#learn`. This extends the stretch result of `docs/plato_lifespan.md`, which came from one run on a Mac.

## Short answer

**The larger model, for chairs: yes, at its own temperature. At the cautious temperature the animation uses, not clearly.**
- **At temperature 1.0 it ends narrower.** Over the 3 runs trained after the addendum, its spread is 0.328 against 0.376 for the chairs it learned from: a difference of **−0.048** (13% less).
  - 95% CI across runs: [−0.062, −0.034]. Two-level bootstrap over runs and drawings: [−0.062, −0.033].
  - **3 of 3 runs** are narrower.
  - With the pilot run included: −0.045 [−0.057, −0.033], 4 of 4.
  - It holds in all three robustness checks.
- **It narrows less at lower temperatures, and the runs disagree more.**
  - At 0.8 it is still narrower: −0.035 [−0.056, −0.014].
  - At 0.6 the t-interval just reaches 0 (−0.032 [−0.067, +0.004]; the bootstrap is [−0.048, −0.011], and 3 of 3 runs are below 0). By the plan's rule that is no clear difference.
  - **At 0.4, the animation's temperature, there is no clear difference:** −0.027 [−0.112, +0.057], with 2 of 3 runs narrower (per run: −0.064, +0.004, −0.022).
  - At 0.2 there is no clear difference either.
- **So the small model's narrowing replicates in a stronger model, in its own distribution.** The size is a little smaller: 13% against 16%. The cleaner chairs the animation shows are not clearly less varied than people's.
- **Its chairs look like chairs.** At 0.4 it ends 93% recognizable, above the adults' reference chairs (92%), and about as varied as Magenta's published chair model (spread 0.351 against 0.350). At 1.0 it ends at 85%, about the small model's level (87%). The difference is mostly in how its drawings look.

**The small model, for chairs: yes, robustly; for cats: no.** In all 8 runs it ends less varied than the chairs it learned from: −0.059 [−0.067, −0.052] (16% less), at every temperature and in every robustness check. Trained on cats, it ends more varied instead. Details below, under "The small model".

## The larger model (the animation)

### Why a larger model

The small model's last chairs are recognizable to DINOv2 (87%) but rough to a person's eye. So the animation now shows a larger model. The plan's addendum (`docs/plato_sketch_plan.md`) was committed after its pilot run and before its other three runs were trained.

**A lower temperature alone doesn't fix it.** We drew the small model's last checkpoint (seed 1) at temperatures down to 0.1.
- At 0.6 and 0.4 its chairs are cleaner, but nearly all of them become the same two-stroke side-view chair.
- At 0.2 and 0.1 some collapse into tangled scribbles.
- Recognizable rises only from 87% to 91–93%.

**Pilots** (one run each, seed 1, last checkpoint, 200 drawings; measured as above, against the chairs each model learned from):

| Model | Data and training | Wall time | Recognizable | Distance to the adult prototype | Spread (learned from) |
|---|---|---|---|---|---|
| Small Sketch-RNN, temperature 1 (the original) | LSTM 512; 20,000 chairs; 25,600 steps of 100 | 4 min | 87% | 0.196 | 0.322 (0.375) |
| the same, temperature 0.4 | | | 92.5% | 0.197 | 0.337 (0.375) |
| **Larger Sketch-RNN, temperature 0.4** | LSTM 2,048; all 203,324 recognized chairs; 102,400 steps of 100; random scaling ±15% | 86 min | **93%** | 0.204 | **0.356** (0.376) |
| Larger Sketch-RNN, temperature 0.6 | | | 91.5% | 0.198 | 0.349 (0.376) |
| Larger Sketch-RNN, temperature 1 | | | 85.5% | 0.208 | 0.338 (0.376) |
| Pixel diffusion, 64 px | UNet, 18.5M parameters; the same 203,324 chairs rendered as the site renders them; 51,200 steps of 128; DDIM, 50 steps, fixed noise | 106 min | 90% | 0.207 | 0.323 (0.365, its training chairs at 64 px) |
| Magenta's pretrained chair, temperature 0.4 (ceiling reference) | LSTM 1,024; 149,600 chairs; 4.8 million steps | – | 94.5% | 0.205 | 0.350 (0.376) |

- **The larger Sketch-RNN at temperature 0.4 was chosen** from a side-by-side page of all of these (`scripts/plato_sketch_compare.py`).
  - Its chairs look like chairs to the eye: four legs, seats, round and square backs, side and front views. They are about as good as Magenta's published chair model.
  - It is the most varied model here.
  - It still goes from dots and scribbles to chairs, and it still draws stroke by stroke.
- **The diffusion model's chairs are clean too**, but it goes from TV static to chairs within its first 400 steps, and it has no strokes to draw.
- **Magenta's model** is a ceiling: it has no training path, so it can't be animated.
- **Ha & Eck's layer-normalized LSTM with recurrent dropout** was tried first and dropped: without a fused kernel it ran about 20 times slower per step in PyTorch (0.9 s against 45 ms at 2,048 units). Magenta's published chair models are plain LSTMs too.
- **The pilot's numbers were seen before the replicate runs.** So the test uses the three runs trained after the addendum.

### What we did

| | |
|---|---|
| Model | The small model's decoder (`plato_lifespan_sketch.build`) with 2,048 units instead of 512: one LSTM layer, dropout 0.1, a 20-component bivariate Gaussian mixture and 3 pen states, the same loss. 17.1 million parameters. `scripts/plato_sketch_big.py`. |
| Data | Every recognized Quick, Draw! chair after the 200 adult reference chairs: 203,326 drawings, of which 203,324 have at most 199 points and are used. |
| Training | Adam 1e-3, decayed by 0.9999 per step down to a floor of 1e-5, gradient clip 1, batch 100, **102,400 steps** (10.2 million chairs seen, about 50 passes). Ha & Eck's random scaling: each drawing's x and y offsets are multiplied by U(0.85, 1.15). **Seeds 1–4**: seed 1 is the pilot, and seeds 2–4 were trained after the addendum. |
| Checkpoints | 24: the small model's 20, plus 38,400, 51,200, 76,800 and 102,400. |
| Drawing | 200 drawings per checkpoint at temperatures **1.0, 0.8, 0.6, 0.4 and 0.2**, from noise fixed per seed (as for the small model). |
| Measures | As for the small model: rendered like people's drawings, Meta DINOv2 (CLS), recognizable among 21 adult prototypes, distance to the adult chair prototype, spread at matched n = 16. |
| "Learned from" | A fixed random 1,000 of its 203,324 training chairs (numpy seed 20261027): spread 0.376 [0.366, 0.381], 93% recognizable, distance 0.210, 4.9 strokes and 24.1 points. |
| Test (P1′) | Spread at step 102,400, temperature 1.0, minus the training chairs' spread, averaged over **seeds 2–4**. **Narrower** only if both the t-interval across seeds (2 df) and the two-level bootstrap CI (2,000 replicates) lie below 0. Also reported: the same test with the pilot included. |
| Hardware | One NVIDIA L40S per server (axon-server02 and 03), at most two at a time. |

### Does it end narrower? (P1′ and P2′: step 102,400, the 3 runs trained after the addendum)

| Temperature | Its spread | Learned from | Difference | 95% CI across runs | 95% CI, runs + drawings | Runs narrower | Verdict |
|---|---|---|---|---|---|---|---|
| **1.0** (primary) | 0.328 | 0.376 | **−0.048** (13% less) | [−0.062, −0.034] | [−0.062, −0.033] | 3 of 3 | **narrower** |
| 0.8 | 0.341 | 0.376 | −0.035 (9% less) | [−0.056, −0.014] | [−0.049, −0.017] | 3 of 3 | narrower |
| 0.6 | 0.344 | 0.376 | −0.032 (8% less) | [−0.067, +0.004] | [−0.048, −0.011] | 3 of 3 | no clear difference |
| **0.4** (the animation's) | 0.348 | 0.376 | −0.027 (7% less) | [−0.112, +0.057] | [−0.064, +0.011] | 2 of 3 | **no clear difference** |
| 0.2 | 0.353 | 0.376 | −0.023 (6% less) | [−0.161, +0.115] | [−0.078, +0.038] | 2 of 3 | no clear difference |

- Per run at temperature 1: −0.054, −0.044, −0.045 (seeds 2–4). The pilot (seed 1): −0.036.
- **With the pilot included** (seeds 1–4, 3 df):
  - 1.0: −0.045 [−0.057, −0.033], 4 of 4, narrower;
  - 0.8: −0.034 [−0.045, −0.023], narrower;
  - 0.6: −0.030 [−0.049, −0.012], narrower;
  - 0.4: −0.025 [−0.070, +0.020], 3 of 4, no clear difference;
  - 0.2: −0.032 [−0.109, +0.045], no clear difference.
- **Cautious drawing makes the runs disagree.** At 0.4 one run ends as varied as its teachers (+0.004) and another clearly narrower (−0.064). With 3 runs (2 df), that makes the interval wide. Unlike the small model, the larger model's narrowing is not the same at every temperature.

**Robustness** (temperature 1, seeds 2–4; 3 of 3 narrower in each):

| Check | Difference | 95% CI across runs | 95% CI, runs + drawings |
|---|---|---|---|
| (a) Mean of the last three checkpoints (51,200, 76,800, 102,400) | −0.042 | [−0.058, −0.027] | [−0.053, −0.030] |
| (b) Training chairs through the same stroke-5 round trip (reference spread 0.370) | −0.042 | [−0.056, −0.028] | [−0.061, −0.032] |
| (c) DINOv2 patch-mean embedding (spread 0.255 vs 0.286) | −0.031 | [−0.039, −0.022] | [−0.042, −0.023] |

### Its learning path (P3′; mean of all 4 runs)

| Step | Drawings (of 200), T 1.0 | Recognizable, T 1.0 [95% CI] | Distance, T 1.0 | Spread − learned from, T 1.0 [95% CI] | Recognizable, T 0.4 | Spread − learned from, T 0.4 |
|---|---|---|---|---|---|---|
| 0 (random weights) | 88 | 20% [14%, 25%] | 0.512 | +0.066 [+0.052, +0.081] | 18% | +0.063 |
| 100 | 124 | 57% [42%, 72%] | 0.349 | +0.019 [−0.034, +0.071] | 45% | −0.056 |
| 200 | 146 | 64% [56%, 71%] | 0.308 | +0.007 [−0.019, +0.032] | 55% | −0.091 |
| 800 | 178 | 65% [62%, 69%] | 0.259 | −0.033 [−0.043, −0.024] | 50% | −0.043 |
| 3,200 | 196 | 76% [71%, 80%] | 0.225 | −0.053 [−0.070, −0.036] | 85% | −0.050 |
| 12,800 | 200 | 83% [80%, 87%] | 0.208 | −0.052 [−0.063, −0.040] | 92% | −0.024 |
| 25,600 | 200 | 86% [84%, 87%] | 0.207 | −0.042 [−0.060, −0.024] | 92% | −0.013 |
| **102,400** | 200 | **85%** [81%, 88%] | **0.205** | **−0.045** [−0.057, −0.033] | **93%** | **−0.025** |
| the chairs it learned from (1,000) | | 93% | 0.210 | | | |
| adults' reference chairs (200, leave-one-out) | | 92% | 0.204 | | | |
| children, age 2 / 6 / 10 (chair) | | 53% / 80% / 89% | 0.280 / 0.211 / 0.247 | | | |

- **Like a child's chair, then past it.**
  - At temperature 1 it passes a 2-year-old's recognizability (53%) at step 100 and a 6-year-old's (80%) at step 6,400. It ends at 85%, under a 10-year-old's (89%), like the small model.
  - At 0.4, the animation's temperature, it passes a 10-year-old's at step 9,600 and the adults' reference chairs (92%) at step 12,800, and ends at 93%.
- **Variety.**
  - At temperature 1 it falls below its training chairs' for good from step 1,600 (the small model: step 300).
  - At 0.4 it is narrowest early in training (−0.09 at step 200). Within a run, its cautious early scribbles all look alike: staircases in one run, jagged vertical lines in another.
  - It then grows more varied again as it learns more kinds of chair, and by the end the gap is not clear.
- **Pulled toward the typical chair, a little.** It ends at distance 0.205 (temperature 1) and 0.203 (0.4) from the adult prototype, against 0.210 for its training chairs, as the small model did.
- **Not simpler at its own temperature.** At temperature 1 its final chairs have about as many points as its training chairs (24.7 vs 24.1) and slightly more strokes (5.8 vs 4.9). At 0.4 they are a little simpler (22.5 points, 3.4 strokes).

### Caveats

- **One architecture in two sizes, one data source, one thing.** The larger model was trained on chairs only, so there is no cat check for it.
- **Three runs.** The test has 2 degrees of freedom, so its intervals are wide wherever the runs disagree, as at 0.4.
- **The animation's temperature was chosen after seeing the pilot.** It was chosen by eye, for clean chairs, before the other runs. Its test is reported, and it is a null.
- **Chairs only as detailed as their teachers'.** Quick, Draw! drawings are 20-second sketches (4.9 strokes and 24 points on average), and the model learns only those. It can't draw a chair more detailed than people drew in that game.
- **Spread is measured in DINOv2**, as for the small model.

**Deviations from the addendum.**
- Seeds 3 and 4 ran side by side on one GPU. That changes only the timing, not the computation.
- Nothing else changed: same model, data, seeds, checkpoints, temperatures, tests and animation as written.

### The animation

Chosen in the addendum, after the pilot and before the other runs:
- **What it shows.** Seed 1 at temperature 0.4: the first 16 of its 200 drawings (noise indices 0–15), at all 24 checkpoints. The random starts never change; only the weights do.
- **Why 0.4.** It was chosen by eye from the pilot's drawings. At 0.4 its chairs are clean and varied; at 0.2 some collapse into dense loops; at 0.6 and above more of them are rough.
- **Overlays.** The step counter, chairs seen (step × 100), recognizability, and the "how varied" bar: seed 1's spread at that step and temperature, against its training chairs' 0.376.
- **Stroke by stroke.** At step 102,400, the first of the 16 that DINOv2 calls a chair. It is tile 1, a two-stroke side-view chair, the commonest kind people draw.
- **Its chairs are only as detailed as its teachers'.** Quick, Draw! chairs are 20-second sketches, 4.9 strokes and 24 points on average.

| File | What |
|---|---|
| `static/img/plato_lifespan/sketch/learn_sprite.webp` (488 KB) | The page's player: the 24 frames of the 4 × 4 grid, 6 across and 4 down. The step counter, chairs seen and the bar are live HTML. |
| `static/img/plato_lifespan/sketch/stroke_order.json` | The stroke-by-stroke chair, which the page draws in SVG at the pen's pace. |
| `PlatosChair/lifespan/sketch/big/watch_it_learn.mp4` (1.7 MB) and `.gif` (2.2 MB) | The time-lapse at 1280 × 720 (GIF 640 px wide). |
| `PlatosChair/lifespan/sketch/big/stroke_by_stroke.mp4` and `.gif` | The final chair drawn stroke by stroke. |
| `PlatosChair/lifespan/figures/sketch_big_curves.png` | The learning path over runs at every temperature. |

The small model's animation files are kept in `PlatosChair/lifespan/sketch/` (not in the repository). `python -I scripts/plato_sketch_animate.py --model small --web` puts its player back.

### Compute and cost

- **$0.** No paid API calls.
- **GPU** (L40S, `~/MetaLesionLab_learn`, nohup, logs in `logs/`):
  - pilots: the larger model, 86 min (server02); diffusion, 106 min (server03);
  - replicates: seed 2 alone on server02 (86 min); seeds 3 and 4 side by side on server03 (168 and 169 min). Sharing one GPU did not speed them up overall: each ran at about 105 ms per step, against 50 alone.
  - About 0.15 s per step for the diffusion model at 64 px (batch 128). Embedding: about 2 minutes per run.
- **Mac**: the small model's low-temperature check (CPU), Magenta's model (CPU, NumPy), the comparison, the analysis and the animation.

### Files

- Code:
  - `scripts/plato_sketch_big.py`: fetch all recognized chairs, benchmark, train (GPU).
  - `scripts/plato_sketch_diffusion.py`: the diffusion pilot (rasterize, train, sample, embed).
  - `scripts/plato_sketch_magenta.py`: Magenta's pretrained chair (download, decode, sample).
  - `scripts/plato_sketch_compare.py`: the side-by-side pilot page.
  - `scripts/plato_sketch_analyze.py --model big` and `scripts/plato_sketch_animate.py --model big`: the analysis and the animation, shared with the small model (`plato_sketch.MODELS`).
  - Tests: `tests/test_plato_sketch_models.py`.
- Data, outside the repo:
  - `PlatosChair/lifespan/sketch/big/`: `runs/big_s<seed>/` (samples, embeddings, `meta.json`; the checkpoints stay on the servers), `ref/` and `results.json`;
  - `sketch/diffusion/` and `sketch/magenta/`: the pilots.
- Public statistics: the `sketch_big` block of `public_data/plato_lifespan.json` (no drawings or embeddings).

**Re-running:**
```
# server (PYTHONPATH=~/MetaLesionLab_learn:~/MetaLesionLab_learn/pylib, which holds scipy)
python scripts/plato_sketch_big.py fetch --out data/train_chair_all.ndjson
python scripts/plato_sketch_big.py train --seed 2 --data data/train_chair_all.ndjson --out runs/big_s2   # seeds 1-4
python scripts/plato_sketch_seeds.py embed --run runs/big_s2
python scripts/plato_sketch_seeds.py ref --concept chair --data data/train_chair_all.ndjson --out ref_big
# Mac
rsync -a --exclude ckpt axon-server02:MetaLesionLab_learn/runs/ PlatosChair/lifespan/sketch/big/runs/   # and server03
python -I scripts/plato_sketch_analyze.py --model big --public public_data/plato_lifespan.json
python -I scripts/plato_sketch_animate.py --model big --web
```

Credits: drawings from Google Creative Lab's Quick, Draw! dataset, CC BY 4.0 (the models' own drawings are shown; they learned from these). Model design after Sketch-RNN, Ha, D. & Eck, D. (2017), *A Neural Representation of Sketch Drawings*. Magenta's pretrained chair model (comparison only, not shown on the page): Google Magenta, Apache-2.0. Similarity: Meta DINOv2, Apache-2.0.

## The small model (the original plan)

### Short answer

**For chairs, yes, and robustly. For cats, no.** We trained the Mac run's model 8 times from scratch on chairs with different seeds, and 5 times on cats.
- At its own temperature (1.0), every run ends less varied than the chairs it learned from: spread 0.315 against 0.375, a difference of **−0.059** (16% less).
  - 95% CI across runs: [−0.067, −0.052].
  - Two-level bootstrap over runs and drawings: [−0.070, −0.048].
  - **8 of 8 runs** are narrower.
- **It holds at every temperature tried.** At 0.8 the difference is −0.051 [−0.056, −0.046], at 0.6 it is −0.049 [−0.056, −0.041], and all 8 runs are narrower at each.
- **It holds in every robustness check:**
  - the mean of the last three checkpoints;
  - training drawings passed through the model's own stroke conversion;
  - a different DINOv2 embedding (patch mean).
- **Not for cats.** Trained the same way on 20,000 cats, the model learns them far less well: 39% recognizable at the end, against 84% for the cats it learned from.
  - Its cats end *more* varied than its training cats: +0.024 [+0.019, +0.029] across runs; 0 of 5 runs are narrower.
  - At temperature 0.6, where its cats are most recognizable (76%), the gap is gone (−0.004 [−0.018, +0.009]).
  - So the narrowing is not a general law of learning from people's drawings. With two things we can only suggest that it comes once the model has learned the thing well.
- The first Mac run's −0.048 [−0.076, −0.022] was not a fluke of one seed.

**Its learning path looks like a child's** (temperature 1, mean of 8 runs):
- Recognizable: from scribbles (18%) to 87%.
- Distance to the adults' average chair: from 0.51 to 0.20, about the adults' own level (0.20).
- Variety: falls below that of its training chairs by step 300 and stays below it.
- By the end its chairs sit a little *closer* to the typical adult chair than its training chairs do (0.201 [0.196, 0.205] vs 0.211). It is pulled toward the typical chair, not just made less varied.

### What we did

| | |
|---|---|
| Model | The Mac run's Sketch-RNN-style decoder (Ha & Eck 2017): LSTM with 512 units, 20-component Gaussian mixture, unconditional, trained from random weights. Model, loss and stroke conversion are imported from `scripts/plato_lifespan_sketch.py`. |
| Data | The same 20,000 recognized Quick, Draw! chairs (the ones after the 200 adult reference chairs; all 20,000 were short enough to use). For the cat check, the first 20,000 recognized cats after the cat reference's 200. |
| Training | Adam 1e-3, decay 0.9999 per step, gradient clip 1, batch 100, 25,600 steps (all as on the Mac). **Seeds 1–8** for chairs, **1–5** for cats. |
| Checkpoints | 20, roughly log-spaced: 0, 25, 50, 100, 150, 200, 300, 400, 600, 800, 1,200, 1,600, 2,400, 3,200, 4,800, 6,400, 9,600, 12,800, 19,200, 25,600 (a superset of the Mac run's 11). |
| Drawing | **200 drawings per checkpoint at temperatures 1.0, 0.8 and 0.6.** The sampling noise is fixed per seed (inverse-CDF sampling from stored uniforms and normals), so every checkpoint draws from the same random starts. A drawing that is a single point is dropped. |
| Measures | Rendered like people's drawings (`to_quickdraw` → `render_strokes` → `ink_crop`), embedded with Meta DINOv2 (CLS). **Recognizable**: nearest adult prototype among 21 is the chair's. **Distance to the adult prototype**: cosine distance to the mean of the 200 Quick, Draw! reference chairs. **Spread**: mean pairwise cosine distance at matched n = 16. |
| "Learned from" | A fixed random 1,000 of its training chairs, rendered and measured the same way: spread 0.375 [0.368, 0.382], 94% recognizable, distance 0.211. |
| Test (P1) | Spread at step 25,600 minus the training chairs' spread, averaged over seeds. **Narrower** only if both the t-interval across seeds and the two-level bootstrap CI (seeds, then drawings, and the reference's drawings; 2,000 replicates) lie below 0. |
| Hardware | One NVIDIA L40S (axon-server01). The server's DINOv2 matched the Mac's on the Mac run's 200 training chairs: mean cosine similarity 0.99999999999. |

### Results

#### Does it end narrower? (P1 and P2: step 25,600)

| Temperature | Its spread | Learned from | Difference | 95% CI across runs | 95% CI, runs + drawings | Runs narrower | Verdict |
|---|---|---|---|---|---|---|---|
| **1.0** (primary) | 0.315 | 0.375 | **−0.059** (16% less) | [−0.067, −0.052] | [−0.070, −0.048] | 8 of 8 | **narrower** |
| 0.8 | 0.324 | 0.375 | **−0.051** (14% less) | [−0.056, −0.046] | [−0.061, −0.040] | 8 of 8 | narrower |
| 0.6 | 0.326 | 0.375 | **−0.049** (13% less) | [−0.056, −0.041] | [−0.059, −0.037] | 8 of 8 | narrower |

- Per run at temperature 1: −0.056, −0.073, −0.059, −0.043, −0.064, −0.058, −0.063, −0.061 (seeds 1–8).
- **Lower temperature does not narrow it further.** At the end, temperatures 0.8 and 0.6 are slightly *more* varied than 1.0. Lower temperature makes it narrower earlier in training (for good from step 100 at 0.6 and step 150 at 0.8, against step 300 at 1.0), but at the last step the narrowing is about the same.
  - So the narrowing is not a sampling-temperature artifact: it is there in the model's own distribution.
  - The Mac run's null at 0.5 (one seed, 64 drawings, a 200-drawing reference) is not reproduced at 0.6 with 8 seeds and 200 drawings. We did not test 0.5.

**Robustness** (temperature 1, 8 runs; all 8 narrower in every check):

| Check | Difference | 95% CI across runs | 95% CI, runs + drawings |
|---|---|---|---|
| (a) Mean of the last three checkpoints (12,800, 19,200, 25,600) | −0.057 | [−0.060, −0.053] | [−0.065, −0.048] |
| (b) Training chairs through the same stroke-5 round trip (reference spread 0.372) | −0.057 | [−0.064, −0.050] | [−0.070, −0.048] |
| (c) DINOv2 patch-mean embedding (spread 0.245 vs 0.288) | −0.043 | [−0.050, −0.037] | [−0.050, −0.035] |

#### The learning path (P3; temperature 1, mean of 8 runs)

| Step | Drawings (of 200) | Recognizable [95% CI] | Distance to the adult prototype | Spread | Spread − learned from [95% CI] |
|---|---|---|---|---|---|
| 0 (random weights) | 89 | 18% [15%, 21%] | 0.511 | 0.434 | +0.059 [+0.048, +0.070] |
| 50 | 88 | 34% [30%, 39%] | 0.471 | 0.430 | +0.056 [+0.042, +0.069] |
| 100 | 110 | 52% [47%, 56%] | 0.363 | 0.420 | +0.045 [+0.034, +0.056] |
| 200 | 132 | 64% [61%, 68%] | 0.299 | 0.374 | −0.001 [−0.014, +0.013] |
| 300 | 145 | 66% [63%, 70%] | 0.282 | 0.360 | −0.015 [−0.029, −0.001] |
| 800 | 160 | 68% [64%, 71%] | 0.265 | 0.344 | −0.031 [−0.042, −0.019] |
| 3,200 | 191 | 75% [72%, 79%] | 0.234 | 0.319 | −0.056 [−0.065, −0.046] |
| 12,800 | 200 | 83% [80%, 86%] | 0.208 | 0.319 | −0.056 [−0.064, −0.048] |
| **25,600** | 200 | **87%** [85%, 89%] | **0.201** | **0.315** | **−0.059** [−0.067, −0.052] |
| the chairs it learned from (1,000) | | 94% | 0.211 | 0.375 | |
| adults' reference chairs (200, leave-one-out) | | 92% | 0.204 | 0.362 | |
| children, age 2 / 6 / 10 (chair) | | 53% / 80% / 89% | 0.280 / 0.211 / 0.247 | 0.438 / 0.360 / 0.414 | |

- **Like a child's chair, then past it:**
  - Recognizability passes a 2-year-old's (53%) at step 150 and a 6-year-old's (80%) at step 6,400. At temperature 1 it ends just under a 10-year-old's (87% vs 89%); at 0.8 and 0.6 it ends above (90%, 92%).
  - Distance to the adult prototype is below the children's at 2, 6 and 10 from step 9,600.
  - Variety drops below 2- and 10-year-olds' (0.44 and 0.41) by step 150, and below its own teachers' by step 300.
- **Not simpler drawings.** At temperature 1 its final chairs have about as many points as its training chairs (23.4 vs 23.7) and slightly more strokes (5.6 vs 4.7). They are less varied in shape, not shorter.
- At temperature 1, samples that are only a dot, or nothing, fall from 56% at step 0 to none by step 19,200.

#### Generality: cats (G1)

Same pipeline: 5 runs (seeds 1–5) on the first 20,000 recognized Quick, Draw! cats after the cat reference's 200 (all 20,000 short enough to use). They are compared with 1,000 of them: spread 0.306 [0.298, 0.312], 84% recognizable, distance 0.167.

| Temperature | Its spread | Learned from | Difference | 95% CI across runs | 95% CI, runs + drawings | Runs narrower | Verdict | Recognizable at the end |
|---|---|---|---|---|---|---|---|---|
| **1.0** | 0.330 | 0.306 | **+0.024** (8% more) | [+0.019, +0.029] | [+0.015, +0.037] | 0 of 5 | **wider** | 39% [33%, 44%] |
| 0.8 | 0.329 | 0.306 | +0.023 (7% more) | [+0.019, +0.027] | [+0.011, +0.034] | 0 of 5 | wider | 56% |
| 0.6 | 0.301 | 0.306 | −0.004 | [−0.018, +0.009] | [−0.020, +0.011] | 3 of 5 | no clear difference | 76% |

- **The narrowing does not carry over to cats.** By the plan's rule the cats are *wider* than what they learned from at 1.0 and 0.8, and show no clear difference at 0.6.
  - At temperature 1 every robustness check agrees, and 0 of 5 runs are narrower in each:
    - last three checkpoints: +0.028 [+0.024, +0.031];
    - round-trip reference: +0.019 [+0.014, +0.025];
    - patch-mean embedding: +0.035 [+0.031, +0.039].
  - Per run at temperature 1: +0.019, +0.024, +0.031, +0.023, +0.022.
- **It learns cats much less well.** Recognizability is 8% at step 3,200, 36% at 12,800 and 39% at the end, still rising. Distance to the adult cat prototype ends at 0.244, against 0.167 for its training cats.
  - Quick, Draw! cats are about twice as complex as chairs: 9.5 strokes and 58 points against 4.7 and 24.
  - The model's size and its 25,600 steps were set for chairs.
- **Like a young child's cat, in two ways.**
  - Its final recognizability (39%) matches children's cats at 2 and 6 (39% and 38%; 52% at 10).
  - Its spread falls from 0.46 at step 100 to 0.33, below children's (0.43 at 2, 0.38 at 10). It levels off above the adults' (0.30) and its training cats' (0.31) from step 3,200 on.
- **Reading.**
  - For chairs, which it learns well (87% recognizable), it ends narrower than its teachers.
  - For cats, which it learns poorly at this budget (39%), it ends wider.
  - Only at temperature 0.6, where its cats are most recognizable (76%), does the gap close.
  - This suggests the narrowing comes with competence, not with learning from people's drawings as such. Two things can't show that. A larger or longer-trained cat model would test it.

### The animation (shown on the page until 2026-10-28)

Chosen in the plan, before any run:
- **What it shows.** Seed 1 at temperature 1.0, the first 16 of its 200 drawings (noise indices 0–15), at all 20 checkpoints. The random starts never change; only the weights do.
- **Overlays.** A step counter, recognizability, and a "how varied" bar: seed 1's spread at that step against the training chairs' 0.375.
- **Stroke by stroke.** At step 25,600, the first of those 16 that DINOv2 calls a chair. It is tile 1, a two-stroke side-view chair, drawn at a constant pen speed in the order the model emitted it.

| File | What |
|---|---|
| `PlatosChair/lifespan/sketch/watch_it_learn.mp4` (0.9 MB) and `.gif` (1.2 MB) | 18 s time-lapse at 1280 × 720 (GIF 640 px wide). Each checkpoint is held, then cross-faded into the next. |
| `PlatosChair/lifespan/sketch/stroke_by_stroke.mp4` and `.gif` | The final chair drawn stroke by stroke (720 px; GIF 480 px). |
| `static/img/plato_lifespan/sketch/learn_sprite.webp` (278 KB; now the larger model's, see above) | The page's player until 2026-10-28: the 20 frames of the 4 × 4 grid, 5 across and 4 down. `plato_sketch_animate.py --model small --web` writes it again. |
| `static/img/plato_lifespan/sketch/stroke_order.json` (0.3 KB; likewise) | The final chair's strokes, which the page drew in SVG at the pen's pace. |
| `PlatosChair/lifespan/figures/sketch_seeds_curves.png` | The learning path: mean, 95% band across runs and each run, for chair and cat. |

The tiles are drawn with 5 px lines instead of the measured 3 px, so they survive being scaled down; the measurements use 3 px.

### Caveats

- **One architecture, one data source, two things.** A small unconditional LSTM decoder trained on Quick, Draw! adults' 20-second drawings, of chairs (8 runs) and cats (5 runs). The two things disagree, and with two we can't say which way a third would go. Larger models, longer training or other data might narrow less, or more. It shows what learning from people's drawings *can* look like, not what children do.
- **Training length.** 25,600 steps of batch 100 is about 128 passes over the data, as on the Mac. The narrowing is stable from step 3,200 on, but we did not train longer.
- **Spread is measured in DINOv2.** "Narrower" means less varied in how the drawings look to DINOv2, not fewer kinds of chair. It holds with both CLS and patch-mean embeddings.
- **"Learned from" is a sample.** It is 1,000 of the 20,000 training chairs; the bootstrap includes its uncertainty.
- **Temperature** here scales the mixture and pen choices and the offset variance together, as in Sketch-RNN. Other ways of sampling (only the mixture, or top-k) were not tried.

**Deviations from the plan.**
- "The drawings it learned from" are 1,000 of the drawings actually used in training. All 20,000 were short enough to use, so this is the same as sampling the 20,000.
- The animation tiles use 5 px lines for display (above); the measurements don't change.
- Nothing else changed: same seeds, checkpoints, temperatures, tests and animation choices as planned.

### Compute and cost

- **$0.** No paid API calls.
- **GPU.** One NVIDIA L40S on axon-server01, in `~/MetaLesionLab_sketch` (nohup, logs in `logs/`). **54 minutes of wall-clock GPU time (01:20–02:14 UTC), about 0.9 GPU-hours,** for all 13 training runs, all drawing, and all rendering and DINOv2 embedding. Run side by side, the runs add up to 2.7 hours.
  - One run trains in about 4 minutes alone (8.5 ms per step). Up to 5 ran side by side.
  - Rendering and DINOv2 take about 25 seconds per run.
  - No other jobs were on the GPU, and no one else's process was touched.
- **Mac.** The analysis (2,000 bootstrap replicates) and the animation.

### Files

- Code:
  - `metalesionlab/plato_sketch.py`: the design, fixed noise, inverse-CDF sampling, statistics and pen-path helpers. Tests in `tests/test_plato_sketch.py`.
  - `scripts/plato_sketch_seeds.py`: fetch, train, embed and reference, run on the GPU.
  - `scripts/plato_sketch_analyze.py`: the pre-registered analysis.
  - `scripts/plato_sketch_animate.py`: the videos, the web sprite and the figure.
- Data, outside the repo (`PlatosChair/lifespan/sketch/seeds/`):
  - `runs/<concept>_s<seed>/`: samples, embeddings and `meta.json`. The checkpoints (`ckpt/step*.pt`) stay on the server.
  - `ref/`: the 1,000-drawing references and the embedding check.
  - `results.json`: everything, including per-run rows.
- Public statistics: the `sketch_seeds` block of `public_data/plato_lifespan.json` (curves, tests, references, the animation's numbers; no drawings or embeddings).

**Re-running:**
```
# server (PYTHONPATH=~/MetaLesionLab_sketch:~/MetaLesionLab_sketch/pylib, which holds scipy)
python scripts/plato_sketch_seeds.py fetch --concept cat --out data/train_cat.ndjson
python scripts/plato_sketch_seeds.py train --concept chair --seed 1 --data data/train_chair.ndjson --out runs/chair_s1   # seeds 1-8; cat 1-5
python scripts/plato_sketch_seeds.py embed --run runs/chair_s1 ...
python scripts/plato_sketch_seeds.py ref --concept chair --data data/train_chair.ndjson --out ref                      # and cat
# Mac
rsync -a --exclude ckpt axon-server01:MetaLesionLab_sketch/{runs,ref} PlatosChair/lifespan/sketch/seeds/
python -I scripts/plato_sketch_analyze.py --public public_data/plato_lifespan.json
python -I scripts/plato_sketch_animate.py --web
```

Credits: drawings from Google Creative Lab's Quick, Draw! dataset, CC BY 4.0 (the model's own drawings are shown; it learned from these). Model design after Sketch-RNN, Ha, D. & Eck, D. (2017), *A Neural Representation of Sketch Drawings*. Similarity: Meta DINOv2, Apache-2.0.

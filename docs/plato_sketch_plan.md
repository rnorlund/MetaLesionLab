# Watch an AI learn what a chair is: pre-registered plan

Written and committed on 2026-10-27, before any of the runs below was trained. The only results looked at are those of the single Mac run, which are already public (`docs/plato_lifespan.md`, sketch-model section).

**Question.** A model that learns only from people's chairs: does it end **narrower** (less varied) than the drawings it learned from? The single Mac run (one seed, 64 drawings per step) said yes: spread 0.318 against 0.365 for its training drawings, difference −0.048 [−0.076, −0.022] at temperature 1. At temperature 0.5 it said no (+0.001 [−0.035, 0.029]). Here we test whether that holds across training seeds and sampling temperatures, and track the whole learning path.

## What stays the same as the Mac run

So the results are comparable, the model and data are the Mac run's (`scripts/plato_lifespan_sketch.py`, functions imported, not copied):

- **Model.** A Sketch-RNN-style decoder (Ha & Eck 2017), unconditional: LSTM with 512 units over stroke-5 points, dropout 0.1, a 20-component bivariate Gaussian mixture for the pen offsets and 3 pen states. Trained from random weights.
- **Data.** The same 20,000 recognized Quick, Draw! chairs (Google, CC BY 4.0), the ones after the 200 used as the adult reference (`PlatosChair/lifespan/sketch/train_chair.ndjson`). Drawings longer than 199 points are dropped; offsets are divided by the standard deviation of all offsets.
- **Training.** Adam, learning rate 1e-3, decayed by 0.9999 per step, gradient norm clipped at 1.0, batch 100 drawn at random, 25,600 steps, maximum length 200.
- **Rendering and measurement.** Each sample goes stroke-5 → Quick, Draw! format (`to_quickdraw`: align, scale to 255, resample, RDP ε = 2) → `plato.render_strokes` (256 px, 3 px lines) → `plato.ink_crop` → Meta DINOv2 (`facebook/dinov2-base`), CLS token. A sample that is a single point is not a drawing and is dropped; the count is reported.

## What changes

- **Hardware.** An NVIDIA L40S on axon-server01 (CUDA) instead of the Mac (MPS). Embedding runs on the same GPU. Check before any result is read: the server's DINOv2 embeddings of 200 training chairs must match the Mac's (mean cosine similarity ≥ 0.999); otherwise all embedding moves to the Mac.
- **Seeds.** **Chair: 8 runs, seeds 1 to 8.** The seed sets the initial weights, the order of the batches and the dropout masks. A run whose loss becomes NaN is replaced by the next unused seed (9, 10, …), and that is reported.
- **Checkpoints.** 20 steps, roughly log-spaced, including all 11 of the Mac run's: **0, 25, 50, 100, 150, 200, 300, 400, 600, 800, 1,200, 1,600, 2,400, 3,200, 4,800, 6,400, 9,600, 12,800, 19,200, 25,600.** The weights are saved at each.
- **Temperatures.** **1.0 (primary), 0.8 and 0.6.** As in the Mac run, temperature divides the mixture and pen logits and multiplies the Gaussian variances.
- **Samples.** **200 per checkpoint and temperature** (the Mac run drew 64). The sampling noise is fixed per seed: for drawing i, the uniform numbers that pick the mixture component and the pen state, and the two normal numbers for the offset, are the same at every checkpoint and every temperature. So across checkpoints only the weights differ, as in the Stable Diffusion arm. The sampler takes this noise as input (inverse-CDF sampling) and does not touch the training random-number generator.
- **"The drawings it learned from."** A fixed random 1,000 of the 20,000 training chairs (numpy seed 20261027), rendered and embedded the same way. The Mac run used 200.

## Measures (per seed × checkpoint × temperature)

As in `docs/plato_lifespan.md`:

1. **Recognizable**: share of drawings whose most similar adult prototype among the 21 candidates is the chair's (chance 4.8%).
2. **Distance to the human prototype**: mean cosine distance of each drawing to the adult chair prototype (the normalized mean of the 200 Quick, Draw! reference chairs).
3. **Spread**: mean pairwise cosine distance at matched n = 16 (mean of 200 random 16-drawing subsets).
4. **Spread − training drawings**: spread minus the spread of the 1,000 training chairs.

Also reported: drawings kept (not single points), mean number of strokes and points, against the training chairs.

## Predictions and tests

**P1 (primary).** At temperature 1.0 and the last step (25,600), the model is narrower than the drawings it learned from.
- Per seed s: Δs = spread(200 samples) − spread(1,000 training chairs).
- Effect: the mean of Δs over the 8 seeds.
- **Replicates if both** (a) the 95% t-interval of the mean across seeds (7 df) lies below 0, **and** (b) the 95% two-level bootstrap CI lies below 0. The bootstrap uses 2,000 replicates and seed 20261027. It resamples seeds, then drawings within each seed's set, and resamples the training chairs, so the reference's own uncertainty is included.
- Reported alongside: each seed's Δs, its own bootstrap CI, and how many of the 8 seeds are below 0.
- **Not replicated (null)** if either CI includes 0. **Reversed** if both lie above 0.

**P2 (temperatures).** The same test at 0.8 and at 0.6, two-sided, with no directional prediction. Lower temperature sharpens the model toward its most likely strokes, which should narrow it. But the Mac run at 0.5 was not narrower, so we don't predict it. **Robust across temperatures** only if the P1 criterion holds at all three.

**P3 (the learning path, descriptive).** At every checkpoint and temperature, the mean over seeds of each measure, with a 95% t-interval across seeds. From the Mac run we expect the following, but test none of it formally:
- recognizability rises from scribbles (about 13%) to about 80–90%;
- distance to the human prototype falls to about the adults' level (0.20);
- spread falls below the training chairs' by about step 800.

**Robustness for P1** (temperature 1.0, chair):
- (a) the mean of the last three checkpoints (12,800, 19,200, 25,600) instead of the last;
- (b) the training chairs passed through the same stroke-5 round trip as the samples (to_stroke5 → from_stroke5) before rendering;
- (c) DINOv2 patch-mean embeddings instead of the CLS token.

**G1 (generality, a second concept).** **Cat**, 5 runs (seeds 1 to 5), the same pipeline. Training data: the first 20,000 recognized Quick, Draw! cats after the 200 used as the adult reference. Same P1 criterion with the cat's references, at all three temperatures. Cat is a natural kind with many styles and has children's drawings at every age, whereas the chair is an artifact. If time runs short, cat is dropped before any chair run is cut, and that is reported.

We apply no correction for multiple tests; everything is reported, including nulls.

## The animation ("watch it learn")

Chosen now, so nothing is picked after looking:
- **Model and drawings.** Seed 1, temperature 1.0 (the primary temperature, so what you watch is what is measured). The first 16 of its 200 drawings (noise indices 0–15), at all 20 checkpoints. They have the same noise at every checkpoint, so each tile is "the same drawing" as the weights learn.
- **Overlays.** A step counter, and a "how varied" bar: seed 1's spread at that step (all 200 drawings) against the 1,000 training chairs.
- **Stroke by stroke.** At step 25,600, the first of those 16 (in index order) that DINOv2 calls a chair, drawn in the order the model emitted its points.
- **Files.**
  - MP4 and GIF in `PlatosChair/lifespan/sketch/` (outside the repository).
  - For the page, a WebP sprite of the 20 frames and a small JSON of the stroke-by-stroke drawing in `static/img/plato_lifespan/sketch/`, under 1 MB in total.

## Compute and cost

- $0: no paid API calls.
- GPU: axon-server01 (L40S), working only in `~/MetaLesionLab_sketch` under nohup with logs. We check `nvidia-smi` first and never touch other users' processes.
- Analysis and figures run on the Mac.
- Credits: Quick, Draw! (Google Creative Lab, CC BY 4.0); Sketch-RNN design (Ha & Eck 2017); DINOv2 (Meta, Apache-2.0).

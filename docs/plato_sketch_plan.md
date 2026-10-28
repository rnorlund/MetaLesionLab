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

## Addendum (2026-10-28): does the narrowing replicate in a stronger model?

Written and committed before replicate runs 2, 3 and 4 below were trained.

**Why.** The small model's last chairs are recognizable to DINOv2 (87%) but rough to a person's eye. For the animation we piloted stronger learners, one run each, and chose a larger Sketch-RNN. The 8-run result above belongs to the small model and stays true of it. This addendum asks whether it replicates in the larger model.

**What we have already seen.**
- The larger model's pilot run (seed 1): its drawings at every checkpoint and temperature, and that one run's three measures at temperatures 1.0, 0.6 and 0.4.
- At step 102,400 and temperature 1.0 it is 85.5% recognizable, with spread 0.338 against 0.376 for 1,000 of its training chairs, a difference of about −0.038. So seed 1 can't test the question, and the test uses new runs only.
- Also seen: a pixel diffusion pilot (`scripts/plato_sketch_diffusion.py`, one run) and Magenta's pretrained Sketch-RNN chair (`scripts/plato_sketch_magenta.py`), compared in `scripts/plato_sketch_compare.py`.

**The model** (`scripts/plato_sketch_big.py`, `plato_sketch.BIG`, fixed before the pilot):
- The small model's decoder (`plato_lifespan_sketch.build`), with 2,048 units instead of 512: one LSTM layer, dropout 0.1, a 20-component bivariate Gaussian mixture and 3 pen states, the same loss.
- We first tried Ha & Eck's layer-normalized LSTM with recurrent dropout. Without a fused kernel it ran about 20 times slower per step in PyTorch, so we dropped it before the pilot.
- Data: every recognized Quick, Draw! chair after the 200 adult reference chairs: 203,326 drawings, of which 203,324 have at most 199 points and are used.
- Training: Adam 1e-3, decayed by 0.9999 per step down to a floor of 1e-5, gradient norm clipped at 1, batch 100, **102,400 steps** (about 50 passes). Ha & Eck's random scaling: each drawing's x and y offsets are multiplied by U(0.85, 1.15).
- Checkpoints: the small model's 20, plus 38,400, 51,200, 76,800 and 102,400 (24 in all).
- Temperatures: **1.0, 0.8, 0.6, 0.4 and 0.2**. At every checkpoint, 200 drawings at each, from noise fixed per seed as above.
- Rendering, embedding and measures exactly as above. "The drawings it learned from": a fixed random 1,000 of the 203,324 (numpy seed 20261027), rendered and embedded the same way.

**Seeds.** **2, 3 and 4.** A run whose loss becomes NaN is replaced by the next unused seed (5, 6, …), and that is reported.

**P1′ (primary).** At temperature 1.0 and step 102,400, over seeds 2–4: Δs = spread(200 drawings) − spread(the 1,000 training chairs).
- **Narrower** only if both the 95% t-interval across seeds (2 df) and the two-level bootstrap CI (2,000 replicates, as above) lie below 0.
- **Wider** if both lie above 0. Otherwise **no clear difference**.
- Reported alongside: each seed's Δs, and the same test with the pilot included (seeds 1–4).

**P2′.** The same test at 0.8, 0.6, 0.4 and 0.2, two-sided.

**Robustness** (temperature 1.0, seeds 2–4): (a) the mean of the last three checkpoints (51,200, 76,800, 102,400); (b) the training chairs passed through the stroke-5 round trip; (c) DINOv2 patch-mean embeddings.

**P3′ (descriptive).** The learning path at every checkpoint and temperature: the mean over all four runs, with a 95% t-interval.

**The animation.**
- Seed 1 (the pilot) at temperature **0.4**: the first 16 of its 200 drawings, at all 24 checkpoints.
- The temperature was chosen by eye from the pilot's drawings. At 0.4 its chairs are clean and varied. At 0.2 some collapse into dense loops. At 0.6 and above more of them are rough.
- The measures shown with the animation are at that temperature. The test at 0.4 (P2′) is reported next to the primary one.
- Stroke by stroke: at step 102,400, the first of those 16 that DINOv2 calls a chair.

**Reading.** We report whatever comes out. If the larger model ends narrower, the narrowing replicates in a stronger model. If not, or if it ends wider, the page says so, and the 8-run result is reported as the small model's only.

**Compute.** Axon L40S GPUs on axon-server02 and axon-server03, at most two at a time, in `~/MetaLesionLab_learn`. No paid API calls.

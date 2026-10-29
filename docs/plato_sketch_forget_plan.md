# Watch an AI forget what a chair is: pre-registered plan

Written and committed on 2026-10-28, before any damaged model drew anything. What we have seen: the learning runs of "Watch an AI learn what a chair is" (`docs/plato_sketch.md`, all public), and the damage hooks working on a tiny, untrained test model (`tests/test_plato_sketch_forget.py`). No drawing, measure or picture of the damaged chair model exists yet.

**The arc.** "We can't name it, then we form the idea, then we forget it." The page already shows a sketch model learning chairs from scribbles (`/plato/lifespan#learn`). Here the same model, fully trained, is damaged step by step, like a brain losing neurons. We watch the same 16 chairs fall apart and ask three questions:

1. **Does forgetting retrace learning backwards?** Does the damaged model pass through the same states as the learning model did, judged by how recognizable its chairs are and how far they sit from people's typical chair?
2. **Does variety rise again as it forgets, or collapse?**
3. **Which goes first: the chair's details (a back's slats, a seat's edge) or its overall shape?**

## The model (unchanged)

- The larger Sketch-RNN of "Watch an AI learn" (`scripts/plato_sketch_big.py`, `plato_sketch.MODELS["big"]`): one LSTM layer of 2,048 units, a 20-component Gaussian mixture head and 3 pen states, trained from random weights on all 203,324 recognized Quick, Draw! chairs for 102,400 steps.
- **Its last checkpoint (step 102,400), for each of its 4 training seeds.** Seed 1 is the display run, as in the learning animation (it was the learning pilot). **Seeds 2–4 are the test seeds**, as in the learning test. Seed 1 is reported alongside.

## The damage: reversible hooks, never a weight edit

Each damage is a PyTorch forward hook added before drawing and removed after (`Damage` in `scripts/plato_sketch_forget.py`). The weights are never changed.

- **Switch units off ("silence"; primary).** A share of the LSTM's 2,048 hidden units is switched off: their output h is set to 0 at every time step. That cuts them off from the mixture head (the pen) and from the next time step (the recurrence), so they have no effect at all. The cell state c is not touched; with h = 0 it cannot reach anything.
  - **Doses: 0, 10, 20, 30, 40, 50, 60, 70, 80 and 90% of the units** (the primary grid), **plus 95% and 100%** to reach the end of the road.
  - **Nested and random.** The units go in a random order fixed per seed (`numpy.random.default_rng([seed, 13]).permutation(2048)`). Dose p switches off the first round(p × 2,048) of that order, so every unit off at 20% is also off at 30%.
- **Noise.** Gaussian noise is added to every unit's output h at every time step, before it reaches the head and the next step. Its standard deviation is a multiple k of the unit's own standard deviation.
  - Each unit's standard deviation is measured over all time steps while the intact model reads the 1,000 reference training chairs of "learn" (teacher forcing).
  - **Doses k: 0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2 and 3.** The noise draws are fixed per seed (`torch.Generator` seed = seed × 1000 + 11; one 200 × 2,048 draw per time step). Only their size changes, so the doses are nested in the same sense.
- **Cut the units off from the pen only ("readout"; exploratory).** The same nested units, at the same doses as "silence", are cut off from the mixture head only; they still take part in the recurrence. This separates damage to the model's memory of the drawing so far from damage to its hand.

## Drawing

- **200 drawings per seed, arm, dose and temperature, at temperatures 1.0 and 0.4**, from the learning run's fixed noise (`plato_sketch.make_noise(seed, 200, 200)`, the same inverse-CDF sampler `plato_sketch_seeds.sample_fixed`). So drawing i starts from the same random numbers at every dose and at every training step. Only the damage changes.
- 1.0 is the model's own distribution and the learning test's primary temperature. 0.4 is the learning animation's.
- **Checks, reported before any result is read:**
  - at dose 0 the drawings must be identical to the learning run's drawings at step 102,400 (same seed and temperature), drawing by drawing;
  - after all damage, with the hooks removed, the model must again draw exactly its dose-0 drawings.
  - A drawing that is only a dot is dropped, as in "learn", and the count is reported.

## Measures (the same as "learn")

Rendered like people's drawings (`to_quickdraw` → `render_strokes` → `ink_crop`), embedded with Meta DINOv2 (`facebook/dinov2-base`, CLS):
1. **Recognizable**: the share of drawings whose nearest adult prototype among the 21 candidates is the chair's.
2. **Distance**: the mean cosine distance to the adult chair prototype (the mean of the 200 Quick, Draw! reference chairs).
3. **Spread**: mean pairwise cosine distance at matched n = 16; also minus the spread of the 1,000 training chairs it learned from. A set with fewer than 16 drawings has no spread.

New, for question 3 (`plato_sketch_forget.ink_maps`, `nearest_person`): each rendered drawing becomes two ink maps.
- **Overall shape**: 16 × 16 pixels (each pixel the mean ink of a 16 × 16 block of the 256-pixel render), blurred by 1 pixel. Single lines are averaged away; the silhouette stays.
- **Details**: 64 × 64 pixels, blurred by 1 pixel. Single lines such as a back's slats or a seat's edge still show.
- At each scale, a drawing's score is its correlation with the most similar of the **1,000 people's chairs** it learned from (the "learned from" sample of "learn"), at the same scale. A set's score is the mean over its drawings.
- **Share kept**: (score − untrained score) / (intact score − untrained score), per seed and temperature. The untrained score is the same seed's step 0; the intact score is its dose 0. So 1 means "as the fully trained model" and 0 means "as before any training".

The learning runs' sets (24 checkpoints, both temperatures, seeds 1–4) are measured again with the same code, so both paths use identical measures.

## Questions and tests

All tests use **seeds 2–4**, the silence arm and **temperature 1.0** unless stated. Two CIs, as in "learn": the 95% t-interval across seeds (2 df), and a two-level bootstrap (2,000 replicates: seeds, then drawings within every set used, including the learning sets).

**The half-forgotten dose.** Questions 2 and 3 test at one dose, fixed by recognizability alone, so it can't be picked for the answer. It is the smallest dose from 10% to 90% at which mean recognizability (seeds 2–4) has fallen at least halfway from the intact model's to the untrained model's (step 0). If it never does, it is 90%. For the noise arm the same rule runs over k = 0.05–3.

**Q1. Does forgetting retrace learning?** For each seed, the learning path is its 24 checkpoints as points (recognizable, distance). At each damage dose from 10% to 90%, we take the damaged model's recognizability r and compare its distance d with the learning path's distance at the same r (linear interpolation between checkpoints sorted by recognizability; doses outside the learning path's range of r are left out, never extrapolated).
- Statistic per seed: the mean gap (d − learning d at the same r) over the doses in range. Effect: the mean over seeds 2–4.
- **Retraces** if both 95% CIs lie inside ±0.03 (about a tenth of the learning path's fall in distance, 0.51 → 0.20).
- **Off the path, further from people's chair** if both CIs lie above 0 and not inside ±0.03; **closer** if both lie below 0 and not inside ±0.03.
- Otherwise **unclear**.
- For the noise arm, the doses are k = 0.05–3.
- Also reported: the gap at each dose, and which training step each dose looks like (the nearest learning point, each axis scaled by the learning path's range).

**Q2. Does variety rise again, or collapse?**
- Primary: spread at the half-forgotten dose minus spread at dose 0. **More varied** if both CIs lie above 0, **less varied** if both lie below 0, otherwise **no clear change**.
- Reported at every dose, with the share of drawings that are only a dot.
- Secondary, the variety version of Q1: the gap in spread against the learning path at the same recognizability, averaged over the doses in range, with the same sign rule.

**Q3. Which goes first, the details or the overall shape?**
- At the half-forgotten dose: (share of overall shape kept) − (share of details kept).
- **Details go first** if both CIs lie above 0; **shape goes first** if both lie below 0; otherwise **together** (no clear order).
- Reported at every dose. Also reported, descriptively: the same two shares along the learning path (which came first in learning).

**Secondary.** The same three questions at temperature 0.4, for the noise arm, and with seed 1 included. **Exploratory:** the readout arm. No correction for multiple tests; everything is reported, including nulls.

**Predictions.** We don't predict a direction for any question. Forgetting could retrace learning ("last in, first out", as in Ribot's law of memory loss), or it could fail in its own way. Variety could rise as the chairs turn back into scribbles, or collapse into one broken drawing. Details could go first (as in semantic dementia, where drawings lose their distinguishing details before their overall shape), or the shape could.

## What the page shows (chosen now)

- **The animation.** Seed 1 at temperature 0.4, the first 16 of its 200 drawings (noise indices 0–15), at every silencing dose (0–100%, 12 frames). These are the learning animation's 16 chairs; dose 0 is its last frame. A WebP sprite in `static/img/plato_forget/`.
- **"Play the life of an AI".** The learning animation's 24 frames, then these 11 damaged frames, in one player.
- **The path chart.** Learning (blue) and forgetting (orange) on the same axes, recognizable against distance: the mean of all four runs at the chosen temperature.
- **The Damaged AI hub card** (`DAMAGED_PAGES` in `metalesionlab/web/site.py`, linking to `/plato/lifespan#forget`, with its thumbnail in the DAMAGED group of `scripts/plato_hub_thumbs.py`): the learning page's stroke-by-stroke chair (the first of the 16 that DINOv2 calls a chair at step 102,400), with 0, 30, 60 and 90% of its units switched off.

## Compute and cost

- $0: no paid API calls.
- GPU: one L40S on axon-server02, in `~/MetaLesionLab_learn/forget` under nohup with logs. We check `nvidia-smi` first and never touch other users' processes. Seeds 3 and 4's checkpoints are copied from axon-server03 (no computing there).
- Analysis, figures and pictures on the Mac. Data: `PlatosChair/sketch_forget/` (outside the repository). Public statistics: `public_data/plato_sketch_forget.json` (group-level numbers only).
- Credits: Quick, Draw! (Google Creative Lab, CC BY 4.0); Sketch-RNN design (Ha & Eck 2017); DINOv2 (Meta, Apache-2.0).

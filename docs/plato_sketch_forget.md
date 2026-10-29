# Watch an AI forget what a chair is

The mirror image of "Watch an AI learn what a chair is" (`docs/plato_sketch.md`). The larger Sketch-RNN that learned chairs from scribbles (LSTM 2,048, 203,324 Quick, Draw! chairs, 102,400 steps, 4 runs) is damaged step by step at its last checkpoint, and draws the same random starts at every level. Plan, committed before any damaged drawing existed: `docs/plato_sketch_forget_plan.md`. Page: `/plato/lifespan#forget`; card on the Damaged AI hub (`/damaged`).

## Short answer

Primary analysis: units switched off, temperature 1.0, the three runs trained after the learning addendum (seeds 2–4). Two 95% CIs: t across runs (2 df) and a two-level bootstrap (runs, then drawings; 2,000 replicates).

- **It breaks fast.** Switching off 10% of the 2,048 units takes recognizability from 85% to 72% (temperature 0.4: 93% to 73%); 30% off takes it to 30% (0.4: 13%). The plan's half-forgotten dose is **30%** (0.4: 20%).
- **Q1. Does forgetting retrace learning? Roughly, but not along the same path; by the plan's rule, unclear.**
  - Going down the doses, its drawings resemble earlier and earlier training: 10% off is nearest to step 1,600, 20% to step 300, 30% to step 50, and 100% to step 0.
  - At the same recognizability, its drawings sit *closer* to the adult chair than the learner's did: mean gap **−0.050**, t [−0.137, +0.036], bootstrap [−0.089, −0.011] → **unclear**. Per dose: −0.006 at 10%, −0.034 at 20%, then −0.06 to −0.11.
  - With seed 1 included: −0.055 [−0.103, −0.007], bootstrap [−0.086, −0.023] → closer (off the path).
  - At temperature 0.4 it goes where learning never went. With 40–80% off, only 1–6% of drawings are recognizable, below the untrained model's 18%: every drawing becomes the same diagonal staircase. Only 10–30% fall inside the learning path's range: −0.005 [−0.099, +0.089] → unclear.
- **Q2. Does variety rise again, or collapse? First it collapses, then it scatters. The primary test is null.**
  - At 30% off: −0.039, t [−0.111, +0.033], bootstrap [−0.073, −0.007] → **no clear change**.
  - With 90% or more off it is more varied than the healthy model: +0.078 [+0.037, +0.119] at 90%.
  - At temperature 0.4 the collapse is strong. From 30% to 80% off, every dose is clearly less varied: at 60%, −0.226 [−0.275, −0.176]; spread 0.12 against 0.35.
  - Against the learner at the same recognizability (secondary): less varied, −0.055, t [−0.102, −0.007], bootstrap [−0.084, −0.036].
- **Q3. Which goes first? The details.**
  - At 30% off it keeps **76%** of the overall shape that training built, but only **57%** of the details: +0.189, t [+0.101, +0.277], bootstrap [+0.127, +0.260], 3 of 3 runs.
  - The same verdict holds at every dose from 10% to 80%, and at temperature 0.4 (+0.258 [+0.137, +0.378] at 20%).
  - **Not "last in, first out" at temperature 1.** In learning, the details came about as early as the shape (at step 100: 58% of the details, 34% of the shape). At 0.4 the shape came first (49% against 31%).
- **Noise is gentler, and it retraces learning.**
  - Noise at 3× each unit's standard deviation still leaves 50% recognizable.
  - At temperature 0.4 its path stays on the learning path: +0.003, t [−0.022, +0.028], bootstrap [−0.010, +0.016] → **retraces** (within ±0.03). It passes the learning states in order: k = 0.5 is nearest step 9,600, k = 1 step 2,400, k = 3 step 150.
  - At 1.0: −0.012 [−0.043, +0.018], bootstrap [−0.029, 0.000] → unclear (the t-interval just crosses the margin).
  - Q3 with noise: together at 1.0 (+0.017 [−0.060, +0.094]); details first at 0.4 (+0.133 [+0.099, +0.168]). So the shape/detail measure does not always say "details first".
- **Readout only (exploratory).** Cutting the same units off from the mixture head, but not from the recurrence, is gentler at first (10%: 76% recognizable at 1.0, 90% at 0.4). It is off the path, closer to the adult chair: −0.091 [−0.181, −0.002], bootstrap [−0.126, −0.055].

## What we did

As planned (`docs/plato_sketch_forget_plan.md`; code `scripts/plato_sketch_forget.py`, `metalesionlab/plato_sketch_forget.py`):

- **Damage.** PyTorch forward hooks; the weights are never edited.
  - Silence: h = 0 for a nested random share of units, on the way to the head and into the recurrence.
  - Noise: h + k·σ_unit·ε, with σ measured while the intact model reads the 1,000 reference training chairs (median σ 0.04) and ε fixed per run.
  - Readout: the head's input masked.
- **Checks.**
  - At dose 0 every run drew exactly the learning run's step-102,400 drawings: 200 of 200, at both temperatures, for all 4 runs.
  - After the hooks were removed, it drew them again exactly.
- **Doses.** Silence and readout: 0–90% in steps of 10, plus 95% and 100%. Noise: k = 0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3.
- **Drawing.** 200 drawings per run, dose and temperature (1.0, 0.4), from the learning runs' fixed noise.
- **Measures.** As in "learn" (DINOv2 CLS):
  - recognizable among 21 adult prototypes;
  - distance to the adult chair prototype;
  - spread at matched n = 16.
- **Q3 measure.** Ink maps of each render at 16 × 16 (overall shape) and 64 × 64 (details). Each drawing's correlation with its nearest of the 1,000 training chairs, at each scale. Rescaled per run as the share kept between the untrained model (step 0) and the intact one.

## Deviations from the plan

- **Added after the planned run, exploratory: silencing at 2, 4, 6 and 8%.** The planned grid showed that most of the change happens before 10%. These doses are used only for the page's animation and curves (`EXTRA_SILENCE`, `DISPLAY_DOSES`), never in a test.
  - The animation therefore has 16 frames instead of the plan's 12.
  - The hub card still shows the plan's 0, 30, 60 and 90%.
- **The hub card** is defined in `damaged_routes.CARDS`, with its thumbnail in `scripts/plato_hub_thumbs.py` (`damaged-forget`), instead of the planned `web/data/damaged_extra.json`. Main's hub replaced that file before the run.
- **Some Q1 doses are outside the learning path's range for some runs** (recognizability below that run's untrained level). As planned, they are left out, not extrapolated: `doses_in_range` in the results.
- Nothing else changed.

## Caveats

- **Three test runs.** With 2 df, t-intervals are wide where runs disagree. That is why Q1 and Q2 are unclear by the rule, although the bootstrap intervals exclude 0.
- **One kind of model, one thing (chairs), one training budget.** Units are switched off at random. Targeted damage, or switching units to their mean instead of 0, might behave differently.
- **The overall shape and the details are pixel scales.** A small shift hurts the fine scale more than the coarse one. The noise arm at temperature 1 shows the measure can say "together", but this is a proxy for parts, not a part detector.
- **Analogies only.** Semantic dementia also strips distinguishing details before the overall shape, and Ribot's law says the last learned goes first. The model is not a brain, and these results only echo those ideas.

## Files and compute

- **Data** (outside the repository): `PlatosChair/sketch_forget/`
  - `runs/forget_s<seed>/`: samples, embeddings, `unit_sd.npy`, `meta.json`, `meta_extra.json`;
  - `ref_drawings.json`, `maps/` (ink-map cache), `results.json`, `logs/`, `figures/screens/` (page screenshots).
- **Public statistics:** `public_data/plato_sketch_forget.json`, served at `/api/plato/lifespan/forget`.
- **Page:** `static/js/plato_forget.js`, `static/css/plato_forget.css`, `static/img/plato_forget/forget_sprite.webp` (16 frames, 4 × 4), and the hub thumbnail `static/img/plato/hub/damaged-forget.webp`.
- **Compute.** One L40S on axon-server02 (`~/MetaLesionLab_learn/forget`, nohup):
  - about 1 minute of drawing and 5 minutes of rendering and embedding for all 4 runs;
  - 2 minutes for the extra doses.
  - Seeds 3 and 4's checkpoints were copied from axon-server03 (no computing there).
  - Analysis, pictures and the page on the Mac. **$0**: no paid API calls.

**Re-running:**
```
# server02 (env.sh: PYTHONPATH and ~/mll-env)
forget/run.sh          # refdraw, unitsd, sample and embed for seeds 1-4
forget/run_extra.sh    # the exploratory 2-8% doses
# Mac
rsync -a axon-server02:MetaLesionLab_learn/forget/{runs,ref_drawings.json,logs} PlatosChair/sketch_forget/
python -I scripts/plato_sketch_forget.py analyze --public public_data/plato_sketch_forget.json
python -I scripts/plato_sketch_forget.py web
python scripts/plato_hub_thumbs.py damaged-forget
```

Credits: Quick, Draw! (Google Creative Lab, CC BY 4.0; the models' own drawings are shown). Sketch-RNN design: Ha & Eck (2017). DINOv2: Meta, Apache-2.0.

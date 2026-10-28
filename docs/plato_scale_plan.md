# An AI growing up: does an AI's idea of a chair change with more data and a bigger model? Pre-registered plan

Written and committed on 2026-10-28, before any run below was trained or sampled. Model weights were downloaded before this commit. Two API calls were made beforehand, with the prompt "Reply with the single word: ok", to check that Muse Spark and Muse Wonder accept a temperature (they do) and several samples per call (they don't: `n` must be 1). No chair was drawn.

**Question.** Huh, Cheung, Wang & Isola (2024), "The Platonic Representation Hypothesis" (ICML 2024, arXiv:2405.07987), propose that the representations of different AI models converge as models grow. If so, do bigger models also **draw** more alike, converging on one textbook chair, a Form emerging with scale? Or do small models simply scribble broken, varied output, so that "convergence" is just competence? We ask it twice:
- **Arm A, data:** the same small sketch model trained on more and more people's chairs.
- **Arm B, model size:** language models of increasing size asked to draw a chair as SVG code.

Earlier results this builds on:
- Muse Image draws one textbook chair, at 0.37 of people's spread (`docs/plato.md`).
- A small Sketch-RNN trained on 20,000 people's chairs ends narrower than its data in 8 of 8 seeds (`docs/plato_sketch.md`).

## Shared measurement

Every drawing goes through the Plato's Chair pipeline unchanged:
- `plato.ink_crop` (flatten the paper, crop to the ink, pad to a square, 256 px);
- Meta DINOv2 (`facebook/dinov2-base`), CLS token.

| Measure | Definition |
|---|---|
| **Recognizable** | The drawing's nearest human centroid, among the 35 core Plato's Chair concepts, is the chair's (cosine; each centroid is the normalized mean of that concept's 200 cached Quick, Draw! drawings; chance 2.9%). |
| **Spread** | Mean pairwise cosine distance among a set's drawings. |
| **Distance to people's prototype** | Mean cosine distance to the normalized mean of the 200 Quick, Draw! reference chairs. |
| **Distance to Muse's prototype** | The same, to the normalized mean of Muse Image's 16 default doodle chairs (`docs/plato.md`). |
| **Failure** | Arm A: a sample that is only a dot or empty. Arm B: see "Failure" below. |

- Bootstrap CIs use 2,000 replicates with seed 20261028.
- With 4 to 6 sizes per family, every trend is **descriptive**. We give the contrast between the largest and the smallest size with its CI, and the sign of the trend, not a p-value for "scaling".

## Arm A: data size (the sketch model)

**What stays the same as `docs/plato_sketch.md`.**
- **Model:** the same Sketch-RNN-style decoder (LSTM 512, 20-component mixture, unconditional), imported from `scripts/plato_lifespan_sketch.py`.
- **Training:** the same optimizer (Adam 1e-3, decay 0.9999 per step, clip 1.0), batch 100 and 20 checkpoints (0 … 25,600).
- **Sampling:** fixed per-seed noise (inverse-CDF sampling).
- **Rendering:** `to_quickdraw` → `render_strokes` → `ink_crop`, as before.

**Data sizes.**
- **The full set is the 20,000 chairs used before.** These are the recognized Quick, Draw! chairs after the 200 reference chairs; all 20,000 are short enough to use.
- Sizes: **100, 300, 1,000, 3,000, 10,000 and 20,000**, as nested random subsets.
- For seed s, the 20,000 are shuffled once (numpy `default_rng([20261028, s])`), and size n is the first n of that order. So 100 ⊂ 300 ⊂ … ⊂ 20,000 within a seed.
- Each seed has its own order, so seed variation includes which chairs were drawn.

**Seeds.** 1, 2 and 3 at every size: 18 runs. The seed also sets the initial weights, the batch order and dropout.

**Held-out chairs.**
- 1,000 further recognized chairs (the 20,201st to 21,200th in file order) that no run trains on.
- At every checkpoint we record the mean held-out loss (negative log-likelihood, eval mode) and the loss on up to 1,000 of the run's own training chairs.

**Training-length rule (stated before any run).**
- **Primary: same compute.** Every size trains for 25,600 steps of batch 100, as in the earlier runs, and is measured at the last checkpoint.
  - This means about 25,600 passes over 100 chairs and about 128 over 20,000, so small sets can be memorized. That is part of what "less data" means here.
- **Secondary: until convergence.** Each run is also measured at its **best checkpoint**, the one of the 20 with the lowest held-out loss (the earliest if tied). It is chosen from the loss log alone, before any drawing is measured.

**Drawing.** 200 drawings per checkpoint at temperature **1.0 (primary)** and **0.6 (check)**, from the run's fixed noise.

**Measures (per run).** Failure (dot) share, recognizable, spread (matched n = 16, as in `plato_sketch.md`), distance to people's and to Muse's prototype, and spread minus the training data's spread.
- **The training data's spread:** all of the run's training chairs when n ≤ 1,000; otherwise a fixed random 1,000 of them. They are rendered and embedded the same way.
- **Copying (exploratory):** each sample's cosine distance to its nearest training chair in DINOv2, against the same distance for the 1,000 held-out chairs, both measured against that run's training subset.

**Statistics.**
- For each size: the mean over the 3 seeds, with a 95% t-interval across seeds (2 df, wide).
- **Primary CI:** a two-level bootstrap that resamples seeds, then drawings.
- **Trend:** the contrast 20,000 − 100 (same seeds, paired), with the two-level bootstrap CI, and the sign of the OLS slope on log10(n) over the 18 runs.

## Arm B: model size (language models drawing SVG)

**Prompt (fixed, one user turn, no system prompt of ours):**
> Draw a simple chair as an SVG drawing: black strokes only on a white background, 256 by 256 pixels, no text, no colour fill. Output only the SVG code.

**Samples.**
- 12 per model at temperature **1.0 (primary)**, and 12 at **0.7 (check)**.
- **Open models:** pure temperature sampling (top-p 1, no top-k, no repetition penalty), at most 2,048 new tokens, one batch of 12 per temperature, torch seed 20261028 + 100 × temperature.
- Chat templates are the models' own, including any default system prompt they add.
- **No model reasons before answering:**
  - Qwen3 runs in its non-thinking mode (`enable_thinking=False`);
  - Glimmer's reasoning channel is skipped by pre-filling the answer header, as everywhere in this project (`metalesionlab/glimmer.py`).
- **API models:** reasoning effort "minimal" (the project default), the same temperature, other settings at the API's defaults, at most 2,304 completion tokens (2,048 plus room for minimal reasoning), one call per sample.

**Models.** Only ungated weights with an Apache-2.0 licence on Hugging Face. Each was checked on the Hub on 2026-10-28 and pinned to its revision. Parameter counts are the Hub's safetensors totals.

| Family | Sizes (parameters) | Role |
|---|---|---|
| **Qwen2.5-Instruct** (Alibaba) | 0.5B (0.49), 1.5B (1.54), 7B (7.62), 14B (14.8), 32B (32.8) | primary family |
| **OLMo 2 Instruct** (AI2) | 1B (1.48), 7B (7.30), 13B (13.7), 32B (32.2) | second family (check) |
| **Qwen3** (Alibaba) | 0.6B (0.75), 1.7B (2.03), 4B (4.02), 8B (8.19), 14B (14.8), 32B (32.8) | third family (check), if time allows |
| **Muse Glimmer 30B** (Meta, open weights) | 29.8 | Meta's open model, on the size axis at its published size |
| **Muse Spark 1.3, Muse Wonder 1.0** (Meta API) | not published | at the end of the axis as **"API models, size undisclosed"**, never at a guessed size |

**Not used, and why:**
- Qwen2.5-3B-Instruct: Qwen Research licence, not Apache-2.0.
- Qwen2.5-72B-Instruct: Qwen licence, and too big for one card.
- Llama 3.x: gated (licence acceptance).
- Gemma 3: gated (licence acceptance).

We never log in or accept a licence. A model that can't be downloaded or loaded is dropped and reported, and the plan goes on.

**Precision.**
- Models up to 14B run in BF16.
- The 30–32B models (Qwen2.5-32B, OLMo 2 32B, Qwen3-32B, Glimmer) run with FP8 weights (`FineGrainedFP8Config`, as for Glimmer), to fit one 46 GB L40S.

**SVG extraction and rendering (`metalesionlab/plato_scale.py`, unit-tested).**
1. **Extract:** from the model's text, the first `<svg …>` up to its first `</svg>` (case-insensitive; Markdown fences ignored).
2. **Render:** with cairosvg at exactly 256 × 256 pixels, composited on white, converted to gray.
   - External resources are blocked (no file or network fetch).
   - An SVG over 200 KB is not rendered.
3. **Failure**, counted per sample with its reason:
   - `no_svg`: no complete `<svg>…</svg>`, including output cut off at the token limit;
   - `render_error`: the renderer raises;
   - `blank`: under 0.1% of pixels have ink (gray below 200);
   - `flooded`: over 95% have ink, so no drawing is visible.
4. **Downstream:** each rendered picture → `ink_crop` → DINOv2 → the shared measures.

**Measures (per model and temperature).**
- **Failure rate:** failures out of 12, with a Wilson 95% CI.
- **Recognizable:**
  - primary: out of all 12 samples (a failure is not a recognizable chair);
  - also: out of the rendered drawings only.
- **Spread** among rendered drawings, only if at least 4 rendered.
  - Bootstrap CI over drawings.
  - Ratio to people's spread at the same n: 200 random subsets of the 200 reference chairs.
- **Distance to people's and to Muse's prototype**, mean over rendered drawings.

## Predictions (made now)

- **P1. Recognizability rises** with data (Arm A) and with model size (Arm B).
- **P2. Spread falls with model size (convergence).** Bigger models draw chairs more alike. For data (Arm A) the analogous prediction is that spread falls as data grows.
- **P3. Failure rate falls** with model size (Arm B), and with data (Arm A: dots).

**Verdict rule.**
- **Arm B**, per family; the primary verdict is Qwen2.5 at temperature 1.0.
  - **Supported** if the contrast of the largest against the smallest size has a 95% bootstrap CI excluding 0 in the predicted direction, **and** the Spearman correlation with log parameters has the predicted sign.
  - **Contradicted** if the CI excludes 0 in the other direction.
  - **Unclear** otherwise.
  - The spread contrast uses the smallest size with at least 4 rendered drawings. If none of a family's small sizes has 4, P2 is "not testable" for that family.
  - Bootstrap: models' samples resampled independently, 2,000 replicates.
- **Arm A:** the same rule, with the 20,000 − 100 contrast, the two-level bootstrap CI, and the sign of the OLS slope on log10(n).
- Temperature 0.7 (Arm B) and 0.6 (Arm A), the best-checkpoint analysis (Arm A) and the other families (Arm B) are checks, reported in full. No correction for multiple tests.

**Exploratory (no prediction).**
- **E1. Cross-family convergence, the Platonic test.**
  - In each size band (≤ 2B, 4–8B, 13–15B, 30–33B), the mean cosine distance between drawings of two different families' models (cross-model spread).
  - Do bigger models from different makers draw more alike?
- **E2. Which Form?** Does distance to Muse's textbook chair fall with size? Is it smaller than distance to people's prototype?
- **E3. Copying** at small data (Arm A, above).
- **E4. Meta's models:** Glimmer, Spark and Wonder against the largest open models, descriptively.

## Display

- **Walls:**
  - by model size: 12 chairs per model at temperature 1.0, smallest to largest, Glimmer at its size, then Spark and Wonder at the end; failures shown as labelled empty tiles;
  - by data size: seed 1's first 12 drawings (noise indices 0–11) at the last checkpoint, temperature 1.0, for each data size.
- **Curves:** spread, recognizability and failure rate.
- **Animation ("An AI growing up"):** the real outputs only, chosen by these rules, not by eye:
  - for each model in the primary family, the first rendered sample (index order) at temperature 1.0, or the first failure's raw text if none rendered;
  - for data, seed 1's noise index 0 at each size.
- The page and figures show only model outputs (ours, from Apache-2.0 models and the Meta APIs) and statistics. No Quick, Draw! drawing is shown.

## Compute and cost

- **GPUs:**
  - axon-server02: Arm A (training, drawing, rendering and DINOv2);
  - axon-server01 and axon-server03: Arm B (open models and Glimmer).
- Everything runs in `~/MetaLesionLab_scale` under nohup, with resumable steps and logs. We check `nvidia-smi` first and never touch other users' processes.
- **Meta API:**
  - at most $3 in all;
  - Wonder bound: 24 calls × 2,304 tokens × $20/M = $1.11 worst case;
  - Spark bound: $0.24.
  - Ledger: `runs/costs.jsonl`. We stop if the shared total passes $70.
- **Mac:** SVG rendering, DINOv2 for Arm B, the analysis, figures, page and animation.
- **Credits:**
  - Quick, Draw! (Google Creative Lab, CC BY 4.0);
  - Sketch-RNN design (Ha & Eck 2017);
  - DINOv2 (Meta, Apache-2.0);
  - Qwen2.5 and Qwen3 (Alibaba, Apache-2.0);
  - OLMo 2 (AI2, Apache-2.0);
  - Muse Glimmer (Meta, Apache-2.0).

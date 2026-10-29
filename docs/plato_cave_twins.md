# Prisoners of the cave: does a model that has seen pictures draw a better chair than its text-only twin?

In Plato's cave the prisoners know only shadows. A language model trained only on text knows chairs only from words. On `/plato/scale`, text-only open models asked to "draw a simple chair as an SVG drawing" drew boxes, while Meta's Muse Spark and Muse Wonder, which have seen images, drew chairs. Those models differ in many ways, so we asked the clean version: **twins from one base model, one trained on text only and one also trained on pictures.**

- The plan was committed before the run: `docs/plato_cave_twins_plan.md` (commit 9c012db).
- The blind by-eye codes were sealed before any automatic scoring: `docs/plato_cave_twins_codes.sha256` (commit 9a72014).
- Page: the "Prisoners of the cave" section of `/plato/scale` (`#twins`), linked from `/plato/cave`.

## Short answer

**No. Seeing pictures in training didn't help these twins draw a chair in code. Both kinds of twin describe a chair equally well in words.**

- **P1 (the picture-trained twin draws chairs that are read as chairs more often) is not supported: unclear at both sizes.**
  - 7B: Google SigLIP 2 read **0 of 12** of the text-only twin's chairs as chairs and **0 of 12** of the vision twin's (difference 0 [0, 0]; Fisher one-sided p = 1).
  - 32B: **1 of 12** against **1 of 12** (0 [−0.25, +0.25]; p = 0.76).
  - The check at temperature 0.7 agrees: 0 vs 0 at 7B; 0 vs 3 at 32B (+0.25 [0, +0.50], unclear; p = 0.11).
- **P2 (both describe a chair equally well) is supported at both sizes.**
  - Rubric (seat, legs, back; by eye, blind): 2.92 vs 2.92 of 3 at 7B (difference 0 [−0.25, +0.25]); 2.92 vs 3.00 at 32B (+0.08 [0, +0.25]).
  - Each twin named all three parts in 11 or 12 of its 12 descriptions.
- **"They know the word, but can't draw the thing"** holds for both kinds of twin. Whatever the picture training gave the vision twins, it didn't reach their SVG code.

## What we did

| | |
|---|---|
| **Twins** | `Qwen/Qwen2.5-7B-Instruct` @ `a09a3545…` vs `Qwen/Qwen2.5-VL-7B-Instruct` @ `cc594898…` (BF16); `Qwen/Qwen2.5-32B-Instruct` @ `5ede1c97…` vs `Qwen/Qwen2.5-VL-32B-Instruct` @ `7cfb30d7…` (FP8 weights). All Apache-2.0, ungated, checked on the Hub on 2026-10-28. Qwen2.5-VL's language model starts from Qwen2.5's weights (Bai et al. 2025, arXiv:2502.13923). |
| **Input** | Text only. The vision twins got the same words through their processor, with no picture. |
| **Tasks** | Chair (the scale experiment's request, word for word; temperature 1.0 primary, 0.7 check); clock ("Draw a clock showing 10 past 11 as an SVG drawing: black strokes only on a white background, 256 by 256 pixels, no colour fill. Output only the SVG code."; 1.0); describe ("Describe what a chair looks like in two sentences."; 1.0). 12 answers each. |
| **Sampling** | The scale experiment's: pure temperature sampling, at most 2,048 new tokens, batch of 12, torch seed 20261028 + 100 × T. Each model's own chat template. |
| **Parity** | The text twins' chair answers are the scale experiment's (same request, sampling, seeds, revisions and precision), copied with provenance into `cave_twins/raw/`. Re-rendering and re-reading them gives the scale experiment's numbers exactly (7B: 0 failures, DINOv2 4 of 12, SigLIP 0; 32B: 0, 0, 1). |
| **Measures** | Valid drawing (scale failure classes); **read as a chair (primary)**: SigLIP 2 zero-shot among the 35 Plato's Chair names, out of 12; DINOv2 recognizable (secondary); spread (mean pairwise DINOv2 cosine distance, bootstrap CI, ratio to people's at the same n); chair by eye (secondary); clock: valid, read as a clock, and by eye face / hands / shows 11:10; description rubric by eye, plus a keyword check afterwards. |
| **Blinding** | Three shuffled sheets with anonymous ids (48 descriptions, 48 chairs, 48 clocks at T 1.0). Codes and the coder's notes on borderline items were hashed and committed before SigLIP 2, DINOv2 or the keyword check ran. The coder (Claude, for Roger) wrote the plan, so it knew the prediction, but not which twin made which item. |
| **Statistics** | Bootstrap, 2,000 replicates, seed 20261029, each model's 12 resampled independently; vision − text; 95% percentile intervals. Verdict rules as planned. |

## Results

**Chairs, temperature 1.0 (primary).**

| Model | Trained on | Valid | Read as a chair (SigLIP 2) | DINOv2 recognizable | Chair by eye | Spread [95% CI] | × people's |
|---|---|---|---|---|---|---|---|
| Qwen2.5 7B | text | 12 | **0** | 4 | 0 | 0.334 [0.227, 0.408] | 0.91 |
| Qwen2.5-VL 7B | text + pictures | 12 | **0** | 1 | 1 | 0.476 [0.393, 0.557] | 1.30 |
| Qwen2.5 32B | text | 12 | **1** | 0 | 0 | 0.493 [0.410, 0.560] | 1.35 |
| Qwen2.5-VL 32B | text + pictures | 12 | **1** | 2 | 2 | 0.478 [0.372, 0.579] | 1.30 |

**Paired differences (vision − text), temperature 1.0.**

| | 7B | 32B |
|---|---|---|
| **Read as a chair (P1)** | **0 [0, 0] unclear** | **0 [−0.25, +0.25] unclear** |
| Valid drawing | 0 [0, 0] | 0 [0, 0] |
| DINOv2 recognizable | −0.25 [−0.58, +0.08] | +0.17 [0, +0.42] |
| Chair by eye | +0.08 [0, +0.25] | +0.17 [0, +0.42] |
| Spread | **+0.142 [+0.030, +0.275]** | −0.015 [−0.143, +0.118] |
| Description score (P2) | 0 [−0.25, +0.25] | +0.08 [0, +0.25] |

- **What the chairs look like.** Both 7B twins mostly drew filled black blocks and boxes: their `<rect>`s have no `fill="none"`, so cairosvg fills them black. The 32B twins drew outlines: boxes, tables, frames, a few chair-like shapes. SigLIP 2 most often read them as books, keys, ladders, benches and hats.
- **By eye, blind:** 3 of 24 vision-twin drawings looked like a chair (one 7B lounge chair in profile; two front-view 32B chairs), against 0 of 24 text-twin drawings. Neither size's difference is clear. The coder's sealed notes flagged four more drawings as "0, borderline". Joined to the key afterwards, three of them are Qwen2.5-VL 32B's and one Qwen2.5 32B's. Counted generously, the 32B pair would be 5 against 1. So a lenient reader might see a modest 32B advantage that the pre-registered reader (SigLIP 2: 1 vs 1) does not.
- **Spread.** The 7B vision twin's drawings vary more than its text twin's (1.30× against 0.91× people's), because the text twin's black blocks look alike to DINOv2. At 32B they're equally varied. We made no prediction about spread.
- **Temperature 0.7 (check).** Read as a chair: 0 vs 0 (7B), 0 vs 3 (32B; +0.25 [0, +0.50], unclear). Spread differences as at 1.0.

**Clocks ("10 past 11", temperature 1.0; exploratory).**

| Model | Valid | Read as a clock (SigLIP 2) | Face (eye) | Two hands (eye) | Shows 11:10 (eye) |
|---|---|---|---|---|---|
| Qwen2.5 7B | 9 (2 no SVG, 1 render error) | 9 | 9 | 0 | 0 |
| Qwen2.5-VL 7B | 12 | 8 | 11 | 0 | 0 |
| Qwen2.5 32B | 12 | 12 | 12 | 11 | **1** |
| Qwen2.5-VL 32B | 11 (1 render error) | 11 | 11 | 10 | 0 |

- The 7B twins often drew solid black discs (a `<circle>` with no `fill="none"`), which hides any hands: 4 of the text twin's 9 drawings and 6 of the vision twin's 12. Neither 7B twin drew two distinct hands.
- The 32B twins drew proper dials with two hands, but at the wrong time. Most put one hand straight up at the 12 (times like 12:05 to 12:25). **One clock of 48 shows 10 past 11 (by eye), and it is the text-only 32B twin's** (its first answer; the shorter hand at about 11.5, the longer at the 2, a borderline call in the sealed notes).
- **Noticed afterwards, not planned (a lead, not a finding):** 8 of the 11 clocks from Qwen2.5-VL 32B have hour marks (dots or ticks) around the dial; none of Qwen2.5 32B's 12 do. At 7B: 1 of 9 (text) and 0 of 12 (vision). This is the one place where the picture-trained twin's drawings look more like the real thing, and it would need its own pre-registered test.

**Descriptions (by eye, blind).**

| Model | Mean score (of 3) [95% CI] | Seat | Legs | Back | All three | Mean words |
|---|---|---|---|---|---|---|
| Qwen2.5 7B | 2.92 [2.75, 3.00] | 12 | 11 | 12 | 11 | 30 |
| Qwen2.5-VL 7B | 2.92 [2.75, 3.00] | 12 | 11 | 12 | 11 | 47 |
| Qwen2.5 32B | 2.92 [2.75, 3.00] | 12 | 12 | 11 | 11 | 35 |
| Qwen2.5-VL 32B | 3.00 [3.00, 3.00] | 12 | 12 | 12 | 12 | 41 |

- The misses: one description each said "supported by a frame" or "one or more supports" instead of legs, and one said the seat curves "to fit the shape of a person's back" without naming a chair back.
- **Two of the text-only 7B twin's 12 descriptions switch into Chinese mid-sentence** (both still name seat, legs and back, in Chinese). One of the vision 7B twin's has a garbled word ("is copyrights vary widely").
- Nearly every description is one long sentence, not the two asked for.
- **Keyword check (run after the seal).** Agreement with the by-eye codes: seat 96%, legs 98% (kappa 0.79), back 96%. Kappa is uninformative for seat and back, where both coders said "yes" almost every time. The keyword check misses the two Chinese descriptions and over-counts "back" (a person's back).
- **Quoted on the page** (rule fixed in the plan: the first sentence of each model's first answer):
  - Qwen2.5 7B: "A chair typically features a seated surface supported by legs and often includes a backrest, designed to provide support while someone sits."
  - Qwen2.5-VL 7B: "A chair typically consists of a seat, a backrest, and four legs, supporting a design that provides both comfort and practicality for sitting."
  - Qwen2.5 32B: "A chair typically consists of a sturdy seat, supported by four legs, with a backrest for comfort and support."
  - Qwen2.5-VL 32B: "A chair typically consists of a sturdy seat, often padded or cushioned, supported by four legs that ensure stability."

## What it means

- The prisoners in this cave aren't helped by having once seen the sun. Both kinds of twin know what a chair is in words, equally well. Neither can write a chair as SVG code.
- So the chairs that Muse Spark and Muse Wonder draw on the rest of this page are probably not explained by "has seen images" alone. Drawing in code seems to need something these twins lack: more scale, training on code that draws, reasoning, or tuning.
- This test doesn't show that picture training adds nothing to what a model knows about how chairs look. It shows that, at these sizes and with this request, any such knowledge doesn't come out through SVG code. The hour marks on the 32B vision twin's clocks hint that some does, which is worth a planned follow-up.

## Caveats

- **12 answers per model.** Only a large difference would show. A 0-of-12 against k-of-12 difference clears the bootstrap rule only from about k = 4.
- **The twins differ in more than pictures.** Qwen2.5-VL had its own later training, including text-only and conversation data, so "trained with pictures" comes bundled with other changes. Their default system prompts also differ: "You are a helpful assistant." (VL) against "You are Qwen, created by Alibaba Cloud. You are a helpful assistant." (text). The vision twins also carry an unused picture encoder (about 0.7B parameters).
- **One request per task, default settings.** These are default behaviours, not limits.
- **Readers.** SigLIP 2 is another model's reading. It reads 86% of people's Quick, Draw! chairs as chairs. It named 9 of the 7B text twin's 9 valid clocks "clock", black discs included, so "read as a clock" says little about the time.
- **The by-eye coder** is one coder (Claude), blind to the model but not to the hypothesis. Its borderline calls went against the 32B vision twin 3 times in 4 (see above).
- **Precision.** The 32B twins ran with FP8 weights. The 32B vision twin's clock batch hit the GPU's memory limit briefly, and the allocator recovered without changing the batch.

**Deviations from the plan.** None in design or analysis. Two post-hoc additions, both labelled on the page and here: the hour-mark count, and the lenient by-eye chair count. The measure script's sealing step is called `seal` (planned as `hash`).

## Compute and cost

- **No paid API call.** $0.
- **GPU: axon-server03, one NVIDIA L40S, about 0.2 GPU-hours.**
  - Two smoke tests: VL 7B, about 2 minutes, mostly loading; VL 32B FP8, about 1 minute, 33.3 GiB.
  - The main run: 8 minutes 8 seconds for all four models.
  - The GPU was idle before and after. No one else's process was touched.
- **Download:** Qwen2.5-32B-Instruct (8.5 minutes, to the server's Hugging Face cache). The other three were already cached at the pinned revisions.
- **Mac:** rendering, SigLIP 2, DINOv2, analysis, figures, page.

## Files

- **Code:**
  - `metalesionlab/plato_twins.py`: design, rubric keywords, blind order, hash, verdicts, public schema.
  - `scripts/plato_twins_generate.py` (GPU), `scripts/plato_twins_measure.py` (`reuse`, `render`, `sheets`, `seal`, `read`, `embed`), `scripts/plato_twins_analyze.py`, `scripts/plato_twins_figures.py`.
  - Tests: `tests/test_plato_twins.py`.
- **Page:**
  - `metalesionlab/web/plato_twins_routes.py` (`/api/plato/twins`);
  - `static/js/plato_twins.js`, `static/css/plato_twins.css`, `static/img/plato_twins/` (sprites, `wall.json`);
  - a section in `pages/plato_scale.html` and a line in `pages/plato_cave.html`.
- **Data (outside the repository, `PlatosChair/cave_twins/`):**
  - `raw/`, `png/`, `render.json`, `reader.json`, `emb/`;
  - `sheets/`, `codes/` (keys, codes, notes);
  - `results.json`, `figures/wall_chairs.png`, `figures/wall_clocks.png`, `screenshots/`, `logs/`.
- **Public statistics:** `public_data/plato_twins.json`. It holds derived numbers plus the four quoted sentences: no SVG code, drawings or embeddings.

Credits: Qwen2.5 and Qwen2.5-VL (Alibaba Cloud, Qwen team), Apache-2.0. Google SigLIP 2 So400m, Apache-2.0. Meta DINOv2, Apache-2.0. Google Quick, Draw! (CC BY 4.0; statistics only).

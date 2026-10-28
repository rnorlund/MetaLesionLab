# An AI growing up: does an AI's idea of a chair change with more data and a bigger model?

Huh, Cheung, Wang & Isola (2024), "The Platonic Representation Hypothesis" (ICML 2024, arXiv:2405.07987), propose that different AI models' representations converge as the models grow. We asked a drawing version of that question. Do bigger models draw more alike, converging on one textbook chair, a Form emerging with scale? Or do small models just scribble?

- The plan was committed before any run: `docs/plato_scale_plan.md`.
- Page: `/plato/scale`.

## Short answer

**No Form emerges with scale in the open models. The one AI that drew a single textbook chair is Meta's Muse Wonder, whose size isn't published.**

- **Bigger language models (Arm B) stop breaking, but they don't converge.**
  - The smallest model of each family fails 4 to 8 times in 12: blank canvases, canvases covered in ink, malformed SVG. From 4B up they rarely fail. **P3 (failures fall) is supported** in all three families: Qwen2.5, the primary family, goes from 8 failures in 12 to 0 (−0.67 [−0.92, −0.42]).
  - Up to 33B, none of the three open families draws a recognizable chair. **P1 (recognizability rises) is unclear** (Qwen2.5 −2 of 12 [−5, 0]).
  - Their drawings don't get more alike. **P2 (spread falls, the convergence prediction) is unclear** in the primary family (−0.073 [−0.195, +0.087]) and in OLMo 2 (+0.108 [−0.042, +0.301]). Qwen3 narrows only in the temperature 0.7 check (−0.174 [−0.310, −0.028]). The 32B models are 0.93–1.60× as varied as people's chairs.
  - **Different makers' models don't converge either** (the Platonic test, E1). The gap between families' chairs at 30–33B is no smaller than at ≤ 2B (energy distance 0.118 against 0.070; change +0.047 [−0.029, +0.120]).
- **Meta's models are where the chair is.**
  - **Muse Wonder 1.0 drew the same front-view slat-back chair 12 times:** spread 0.138 [0.110, 0.172], 0.38× people's. That is exactly as narrow as Muse Image's textbook chair (0.37×, `docs/plato.md`), from a different Meta model writing code instead of pixels.
  - Muse Spark 1.3 drew plain side-view chairs as varied as people's (0.95×).
  - Muse Glimmer 30B, Meta's open model, drew chair-like tables (0.89×; 1 failure).
  - Spark and Wonder are API models of undisclosed size, so none of this is a claim about scale.
- **More data (Arm A) makes the sketch model's chairs more recognizable, not more alike.**
  - Trained for the same 25,600 steps on 100 to 20,000 people's chairs (3 seeds each), its recognizable share rises from 59% to 73%. **P1 is supported:** +14 points [+6, +22].
  - Its spread stays at about 0.31 at every size. **P2 is unclear:** −0.011 [−0.030, +0.005].
  - It never fails at the last step, so **P3 can't be tested there.**
  - At every size it is narrower than the chairs it learned from (by 0.044–0.063, every CI below 0), as the 20,000-chair runs of `docs/plato_sketch.md` found.
  - Stopped early, at its best held-out step, all three predictions hold. With 100 chairs it is still mostly scribbles: 25% recognizable, 33% only dots, spread 0.371. With 20,000 it reaches 74% and 0.309.

So the answer to "do bigger models draw more alike, a Form emerging with scale?" is **no, for open models up to 33B drawing in SVG**. What bigger models gain is competence (fewer broken drawings), not a shared chair. Convergence on one textbook chair shows up in Meta's frontier API model, as it did in Muse Image. We can't say whether that is size, training or tuning.

## What we did

| | |
|---|---|
| **Arm B: model size** | Every model got one prompt: *"Draw a simple chair as an SVG drawing: black strokes only on a white background, 256 by 256 pixels, no text, no colour fill. Output only the SVG code."* 12 samples at temperature 1.0 (primary) and 12 at 0.7 (check). |
| Open models | Three families, all ungated and Apache-2.0, pinned to their Hub revisions: **Qwen2.5-Instruct** 0.5B, 1.5B, 7B, 14B, 32B (primary); **OLMo 2 Instruct** 1B, 7B, 13B, 32B; **Qwen3** 0.6B, 1.7B, 4B, 8B, 14B, 32B (thinking off). Also **Muse Glimmer 30B** (Meta, open weights). Pure temperature sampling (top-p 1, no top-k, no repetition penalty), at most 2,048 new tokens. Up to 14B in BF16; the 30–33B models with FP8 weights to fit one 46 GB L40S. |
| Meta API models | **Muse Spark 1.3** and **Muse Wonder 1.0**: reasoning effort "minimal", the same temperatures, one call per sample. Meta doesn't publish their sizes, so they sit at the end of every axis as **"API models, size undisclosed"**. |
| Not used | Qwen2.5-3B (Qwen Research licence), Qwen2.5-72B (Qwen licence; too big for one card), Llama 3.x and Gemma 3 (gated: we never accept a licence or log in). |
| Rendering | The first complete `<svg>…</svg>` in the answer, drawn by cairosvg at 256 × 256 px on white, with external files and network blocked. **Failure**: no complete SVG, a renderer error, a blank canvas (< 0.1% ink) or one covered in ink (> 95%). |
| **Arm A: data size** | The sketch model of `docs/plato_sketch.md` (Sketch-RNN-style LSTM decoder, about 1.1 million parameters, trained from scratch), on **nested random subsets of 100, 300, 1,000, 3,000, 10,000 and 20,000** Quick, Draw! chairs. 20,000 is the full set used before. Seeds 1–3 at every size (18 runs); each seed has its own shuffle, so seed variation includes which chairs were drawn. |
| Training rule | **Same compute (primary):** 25,600 steps of batch 100 for every size, measured at the last step. **Until convergence (secondary):** each run's checkpoint with the lowest loss on 1,000 held-out chairs, chosen from the loss log before any drawing was measured. 200 drawings per checkpoint at temperature 1.0 (and 0.6). |
| Measures | Every drawing is ink-cropped and embedded with Meta DINOv2 (base, CLS). **Recognizable:** its nearest of the 35 Plato's Chair concept centroids (200 Quick, Draw! drawings each) is the chair's (chance 2.9%); a failure counts as not recognizable. **Spread:** mean pairwise cosine distance. **Distance to people's / Muse's prototype:** to the mean of the 200 Quick, Draw! reference chairs, or of Muse Image's 16 default chairs. |
| Statistics | Bootstrap CIs (2,000 replicates). Arm B: samples resampled per model; contrasts between the largest and smallest model of a family. Arm A: two-level bootstrap (seeds, then drawings); the 20,000 − 100 contrast, paired by seed. Verdict rule as planned: **supported** if the contrast CI excludes 0 in the predicted direction and the trend over sizes has the predicted sign; **contradicted** if it excludes 0 the other way; otherwise **unclear**. With 4–6 sizes per family every trend is descriptive. |

## Arm B: language models drawing a chair

**Temperature 1.0, 12 samples per model.** Spread is among the rendered drawings; "× people's" divides it by people's spread at the same n (200 random subsets of the 200 reference chairs; people's spread at n = 12 is 0.366). "Read as a chair" is the SigLIP 2 check (below).

| Model | Parameters | Failed (of 12) | Recognizable (of 12) | Read as a chair (of 12) | Spread [95% CI] | × people's | To people's chair | To Muse's chair |
|---|---|---|---|---|---|---|---|---|
| Qwen2.5 0.5B | 0.49B | **8** (5 all ink, 2 blank, 1 error) | 2 | 0 | 0.566 [0.419, 0.643] (n = 4) | 1.57 | 0.676 | 0.891 |
| Qwen2.5 1.5B | 1.54B | 1 | 0 | 0 | 0.583 [0.495, 0.666] | 1.61 | 0.623 | 0.879 |
| Qwen2.5 7B | 7.62B | 0 | 4 | 0 | 0.334 [0.219, 0.413] | 0.91 | 0.595 | 0.879 |
| Qwen2.5 14B | 14.8B | 0 | 0 | 0 | 0.395 [0.318, 0.464] | 1.08 | 0.532 | 0.835 |
| Qwen2.5 32B | 32.8B | 0 | 0 | 1 | 0.493 [0.413, 0.559] | 1.35 | 0.548 | 0.872 |
| OLMo 2 1B | 1.48B | **4** | 0 | 0 | 0.476 [0.284, 0.592] | 1.31 | 0.620 | 0.890 |
| OLMo 2 7B | 7.30B | 2 | 0 | 0 | 0.574 [0.502, 0.643] | 1.57 | 0.609 | 0.884 |
| OLMo 2 13B | 13.7B | 1 | 0 | 0 | 0.566 [0.458, 0.666] | 1.56 | 0.584 | 0.889 |
| OLMo 2 32B | 32.2B | 0 | 0 | 1 | 0.584 [0.501, 0.661] | 1.60 | 0.551 | 0.864 |
| Qwen3 0.6B | 0.75B | **6** | 0 | 0 | 0.493 [0.284, 0.720] | 1.37 | 0.643 | 0.890 |
| Qwen3 1.7B | 2.03B | 1 | 2 | 0 | 0.495 [0.362, 0.597] | 1.37 | 0.641 | 0.892 |
| Qwen3 4B | 4.02B | 0 | 0 | 0 | 0.410 [0.314, 0.491] | 1.12 | 0.521 | 0.856 |
| Qwen3 8B | 8.19B | 0 | 1 | 0 | 0.432 [0.349, 0.499] | 1.18 | 0.559 | 0.870 |
| Qwen3 14B | 14.8B | 0 | 1 | 0 | 0.268 [0.210, 0.332] | 0.73 | 0.547 | 0.845 |
| Qwen3 32B | 32.8B | 0 | 0 | 3 | 0.342 [0.255, 0.453] | 0.93 | 0.503 | 0.833 |
| **Muse Glimmer 30B** | 29.8B | 1 (error) | 2 | 2 | 0.321 [0.293, 0.348] | 0.89 | 0.440 | 0.761 |
| **Muse Spark 1.3** | undisclosed | 0 | 2 | **8** | 0.347 [0.279, 0.416] | 0.95 | 0.450 | 0.625 |
| **Muse Wonder 1.0** | undisclosed | 0 | 4 | **8** | **0.138 [0.110, 0.172]** | **0.38** | 0.417 | 0.677 |
| *people's chairs* (Quick, Draw!) | | | *88%* | *86%* | *0.366* | *1* | | |
| *Muse Image's chairs* (`docs/plato.md`) | | | *100%* | *100%* | *0.134* | *0.37* | | |

**The predictions** (primary: Qwen2.5 at temperature 1.0; contrast = largest − smallest model).

| Prediction | Qwen2.5 (primary) | OLMo 2 | Qwen3 | At temperature 0.7 |
|---|---|---|---|---|
| **P1** recognizability rises with size | **unclear**: −0.17 [−0.42, 0.00] | unclear: 0 [0, 0] | unclear: 0 [0, 0] | unclear in all three |
| **P2** spread falls with size (convergence) | **unclear**: −0.073 [−0.195, +0.087] | unclear: +0.108 [−0.042, +0.301] | unclear: −0.151 [−0.388, +0.088] | Qwen3 supported (−0.174 [−0.310, −0.028]); Qwen2.5 and OLMo 2 unclear |
| **P3** failures fall with size | **supported**: −0.67 [−0.92, −0.42] | supported: −0.33 [−0.58, −0.08] | supported: −0.50 [−0.75, −0.25] | supported in all three |

- **Small models break.** At temperature 1, the smallest model of each family fails 4 to 8 times in 12: SVGs covered in ink, blank canvases, malformed XML, or no SVG at all. From 4B up, failures are rare: 3 of 120 samples across the three families (all OLMo 2), and 1 of 12 for Glimmer.
- **Bigger open models don't draw chairs.** Even at 32B, none of the three families draws a chair a reader would recognize. They draw boxes, tables, boxy armchairs and abstract shapes. DINOv2 puts 0 to 4 of 12 nearest people's chairs, and SigLIP 2 calls at most 3 of 12 a chair (Qwen3 32B).
- **They don't converge either.** Spread doesn't fall with size in the primary family or in OLMo 2, and the 32B models are as varied as people or more (0.93–1.60× people's).
  - Qwen3 is the one family that narrows, from 1.37× to 0.73–0.93×. Its contrast is clear only at temperature 0.7, a check.
  - What spread there is among the open models is variety in *what* they draw, not in how they draw one chair.
- **Meta's models are where the chair appears.**
  - By eye, every one of Spark's and Wonder's 24 drawings is plainly a chair. SigLIP 2 reads 8 of 12 of each as chairs, and DINOv2 places most of the rest nearest people's *ladders*: a slat-back chair seen from the front looks like one.
  - **Muse Wonder draws one textbook chair:** the same front-view slat-back chair 12 times, spread 0.138 [0.110, 0.172]. That is 0.38× people's, the same as Muse Image's chairs (0.134, 0.37×), a different Meta model, drawing pixels rather than code.
  - Spark draws a side-view ladder-back chair, as varied as people (0.95×; 0.75× at temperature 0.7). Glimmer 30B, Meta's open model, draws chair-like tables and benches (0.89×; 2 of 12 read as chairs).
  - Their size isn't published, so this is not a statement about scale.
- **Which Form?** The SVG chairs sit far from Muse Image's doodle prototype (distance 0.62–0.89) and nearer people's (0.42–0.68), because they are thin line drawings, as people's are. Spark's and Wonder's are the closest to both. Among open models, distance to Muse's chair falls a little with size in Qwen3 (−0.057 [−0.082, −0.031]) and not clearly in the others.

**E1. Do different makers' models converge with size? (the Platonic test).**
- For each size band, the distance between two different families' sets of chairs, averaged over the band's cross-family pairs:
  - **energy distance:** 2·E|a − b| − E|a − a′| − E|b − b′| in DINOv2 cosine distance; 0 means the two models draw from the same distribution;
  - **plain cross-model distance:** E|a − b|.
- Glimmer is in the 30–33B band.

| Size band | Cross-family pairs | Energy distance [95% CI] | Cross-model distance [95% CI] |
|---|---|---|---|
| ≤ 2B | 8 | 0.070 [0.008, 0.139] | 0.555 [0.524, 0.585] |
| 4–8B | 5 | 0.188 [0.130, 0.254] | 0.535 [0.510, 0.560] |
| 13–15B | 3 | 0.179 [0.111, 0.253] | 0.499 [0.464, 0.537] |
| 30–33B | 6 | 0.118 [0.083, 0.154] | 0.494 [0.473, 0.516] |

- **No convergence in this test.** The 30–33B band is not closer than the ≤ 2B band (energy change +0.047 [−0.029, +0.120]; at temperature 0.7, +0.078 [−0.009, +0.158]).
- The smallest models look "alike" only because they all scribble: their sets overlap as one varied mess.
- Plain cross-model distance does fall a little with size (0.555 → 0.494). But the models' own sets tighten about as much, so different makers' chairs get no closer to each other than each model's chairs are to themselves.

**Check: a second reader (added after the plan).**
- **Why:** DINOv2's nearest-centroid recognizability is harsh on clean line art. Wonder's obvious chairs sit nearest people's ladders, Glimmer's nearest benches.
- **What:** Google SigLIP 2 (So400m/14), a model none of the families shares, read every drawing zero-shot. It picks which of the 35 concept names fits best ("a simple line drawing of a chair", …).
- **Calibration:** it reads 86% of people's 200 reference chairs and 16 of 16 Muse Image chairs as chairs.
- **The verdicts don't change.** Open models: 0–3 of 12 at every size. Spark and Wonder: 8 of 12. Glimmer: 2 of 12.

**Other observations.**
- **Frames.** Small models often frame the canvas: ink reaches all four edges in 17–63% of the drawings of models ≤ 2B, and in none at 32B.
- **The API models thought a little.** Even at reasoning effort "minimal", Spark spent about 420 reasoning tokens per answer at temperature 1 (485 at 0.7) and Wonder about 125 (90). The open models answered directly. So Spark and Wonder were not on equal terms with the open models; see the caveats.
- **Answer length.** Open models wrote 79–531 tokens on average. Only one answer hit the 2,048-token limit (a Qwen3 1.7B sample at temperature 0.7, counted as "no SVG").

## Arm A: one small model, more and more chairs

**Last step (same compute, primary), temperature 1.0.** Mean of 3 seeds with the two-level bootstrap CI (seeds, then drawings). "Its data" is the spread of the run's own training chairs (all of them up to 1,000; otherwise a fixed random 1,000). Recognizable is out of all 200 samples.

| Chairs it learned from | Recognizable | Read as a chair (SigLIP 2) | Spread | Its data | Spread − its data | To people's chair | To Muse's chair | Only a dot |
|---|---|---|---|---|---|---|---|---|
| 100 | 59% [53, 65] | 36% | 0.320 [0.310, 0.335] | 0.365 | −0.044 [−0.069, −0.015] | 0.222 | 0.681 | 0% |
| 300 | 57% [52, 62] | 34% | 0.307 [0.296, 0.318] | 0.362 | −0.056 [−0.073, −0.043] | 0.216 | 0.685 | 0% |
| 1,000 | 66% [61, 72] | 47% | 0.305 [0.296, 0.315] | 0.368 | −0.063 [−0.074, −0.052] | 0.204 | 0.668 | 0% |
| 3,000 | 71% [65, 76] | 47% | 0.309 [0.295, 0.324] | 0.371 | −0.062 [−0.077, −0.046] | 0.201 | 0.659 | 0% |
| 10,000 | 70% [64, 75] | 55% | 0.320 [0.308, 0.334] | 0.366 | −0.046 [−0.062, −0.034] | 0.205 | 0.653 | 0% |
| 20,000 | 73% [68, 78] | 56% | 0.309 [0.298, 0.320] | 0.367 | −0.058 [−0.071, −0.047] | 0.198 | 0.653 | 0% |
| *people's reference chairs* | *88%* | *86%* | *0.366* | | | *0.204* | | |

**Contrast 20,000 − 100** (paired by seed; slope on log10 n over the 18 runs for the trend's sign):

| | Last step, T 1.0 (primary) | Last step, T 0.6 | Best held-out step, T 1.0 | Best held-out step, T 0.6 |
|---|---|---|---|---|
| **P1** recognizable | **+0.138 [+0.060, +0.218] supported** | +0.205 [+0.130, +0.282] supported | +0.492 [+0.425, +0.560] supported | +0.622 [+0.555, +0.685] supported |
| **P2** spread | **−0.011 [−0.030, +0.005] unclear** | +0.018 [−0.001, +0.033] unclear | −0.062 [−0.086, −0.034] supported | +0.035 [+0.012, +0.056] contradicted |
| **P3** only a dot | **0 (no failures at any size)** | 0 | −0.328 [−0.397, −0.265] supported | −0.218 [−0.277, −0.165] supported |
| Distance to people's chair | −0.025 [−0.037, −0.013] | −0.021 [−0.036, −0.008] | −0.096 [−0.114, −0.079] | −0.055 [−0.067, −0.043] |
| Distance to Muse's chair | −0.028 [−0.041, −0.015] | −0.059 [−0.081, −0.037] | −0.107 [−0.119, −0.095] | −0.130 [−0.148, −0.112] |

- **Same compute.** With 25,600 steps every size learns to draw chairs. Small sets are badly overfitted: held-out loss ends at about 17.5 for 100 chairs, against −0.07 for 20,000. Yet their samples are still chair doodles, 59% recognizable.
  - More data makes them more recognizable and a little closer to people's (and Muse's) average chair.
  - It does not make them more alike: spread is flat, 0.305–0.320 at every size.
- **Narrower than its teachers at every size.** The model's chairs are less varied than the chairs it learned from, by 0.044 to 0.063, with every CI below 0 and all 18 runs below. So the narrowing of `docs/plato_sketch.md` doesn't need 20,000 chairs; it happens from 100. At 20,000 these runs reproduce the earlier ones: spread 0.309, against 0.315 over 8 seeds there.
- **Until convergence.** The best held-out step comes early for small sets: step 200 for all three 100-chair runs, 400–800 for 300, 2,400–3,200 for 1,000, 4,800 for 3,000, 9,600 for 10,000, and 19,200–25,600 for 20,000.
  - Stopped there, a model with little data is still learning to draw: 25% recognizable, 33% dots and spread 0.371 at 100 chairs, against 74%, 0% and 0.309 at 20,000.
  - That is the classic picture: more data, more converged. At temperature 0.6 the early small-data models are *less* varied (spread +0.035 from 100 to 20,000, contradicted), because cold sampling of an undertrained model draws the same few strokes.
- **No copying (E3).** Its drawings sit slightly *farther* from their nearest training chair than new people's chairs (the held-out 1,000) do: +0.014 to +0.022 at every size. So even with 100 chairs, each seen about 25,600 times, it doesn't reproduce its training chairs in DINOv2's eyes. The change from 100 to 20,000 is +0.004 [−0.005, +0.013].
- **SigLIP 2 agrees on the direction:** it reads 36% of the 100-chair model's drawings as chairs and 56% of the 20,000-chair model's (people's chairs 86%).

## Did the convergence prediction hold?

**No, not in the primary analysis of either arm.**

| | Model size (Qwen2.5, T 1.0) | Data size (last step, T 1.0) |
|---|---|---|
| P1 recognizability rises | unclear | **supported** |
| **P2 spread falls (convergence)** | **unclear** | **unclear** |
| P3 failures fall | **supported** | not testable (no failures) |

- **Checks.** P2 is supported in one model-size check (Qwen3 at temperature 0.7) and in the data arm's best-checkpoint analysis at temperature 1. It is contradicted in the best-checkpoint analysis at 0.6. The Platonic cross-family test (E1) finds no convergence.
- **What does change with size** is whether the model can produce a drawing at all, and, with data, whether it draws a recognizable chair.
- **Where the narrow textbook chair does appear:** Muse Wonder (0.38× people's spread) and, in `docs/plato.md`, Muse Image (0.37×).
- **How this squares with the hypothesis.** It is about representations, not drawing in code; drawing a chair in SVG is a narrow, rarely trained skill. Drawing may only show convergence once a model can draw the thing well, and among these models only Spark and Wonder could. Of those two, one converged (Wonder) and one did not (Spark).

## The animation ("An AI growing up")

A standalone mockup (one HTML file, assets embedded, 120 KB, about 28 s), built by `scripts/plato_scale_animation.py` from `scripts/plato_scale_animation_template.html` and `results.json`. It has the structure of the "A lifetime of chairs" mockup: Replay, Slow motion and Skip to end; a fluid stage (16:9, 3:5 on phones); light and dark themes; a beat sheet; checked sources.

- **The story.** An AI's brain icon grows (width on log parameters) and a pile of chair drawings grows (one sheet per about 1.7× more data). A thought bubble shows six real chairs at each stage, with a "how varied" bar against people's and Muse Image's spread.
- **Act 1, more data:** the sketch model at 100, 1,000 and 20,000 chairs, drawn stroke by stroke.
- **Act 2, a bigger brain:** Qwen2.5 0.5B → 32B, from labelled failures and ink-flooded canvases to varied boxes.
- **Act 3, Meta's models:** Glimmer, then Spark and Wonder, whose brain is drawn dashed with a question mark (size undisclosed).
- **End card:** "Bigger open models stopped breaking. They didn't converge on one chair. Muse Wonder did."
- **Chosen by rule, not by eye:**
  - act 1: seed 1's noise indices 0–5 at the last step, temperature 1;
  - acts 2 and 3: each model's first six answers at temperature 1, failures included.
- Output: `/private/tmp/claude-501/-Users-super-Documents-Meta-Hacking-Challenge/b7ed7d71-ca39-42be-891b-17ea8a11c396/scratchpad/ai_growing/index.html`, plus `preview.html` with a doctype for local viewing. Not published.

## Caveats

- **Defaults under one prompt.**
  - Every model got one wording and one setting. These are default behaviours, not limits of what any model could draw with a better prompt, examples or tools.
  - Writing a chair as SVG is a narrow skill: a model can know chairs well and still write poor SVG coordinates.
  - This is especially true of Glimmer, a vision-language model asked to write code.
- **The API models thought a little.** At reasoning effort "minimal", Spark still used about 420 reasoning tokens per answer and Wonder about 125. The open models (Qwen3 with thinking off, Glimmer with its reasoning channel skipped) answered directly. A fairer comparison would let every model reason, or none.
- **Precision.** The 30–33B models ran with FP8 weights; the smaller ones in BF16. FP8 changes outputs slightly.
- **Small samples.**
  - 12 samples per model and temperature, so a recognizability of "2 of 12" has a CI of about 0–42%.
  - With 4–6 sizes per family, every trend is descriptive.
  - The cross-family bands hold 3–8 pairs each.
- **Rendering is strict.** cairosvg rejects malformed XML and path data that a lenient browser might partly draw. There were 4 render errors in all (Qwen2.5 0.5B, Glimmer and OLMo 2 1B twice). 3 of them would partly draw in a browser: two repeated attributes (Glimmer wrote `width="256" width="256"`) and one broken path. The fourth is a malformed tag.
- **The measures see style.**
  - DINOv2 spread and recognizability compare clean SVG line art with people's 20-second Quick, Draw! doodles. DINOv2 calls a front-view slat-back chair a ladder.
  - The SigLIP 2 check (added after the plan) confirms the pattern, but it is another model's reading, not people's.
- **One sketch architecture.** Arm A is one small LSTM model on one dataset. The same-compute rule means small sets were trained for far more passes than large ones; the best-checkpoint analysis is the counterweight.
- **Sizes of Meta's API models are not published.** They are never placed on the size axis.

**Deviations from the plan.**

- **A second reader, added after the plan.** We added the SigLIP 2 zero-shot check once DINOv2 put Wonder's obvious chairs nearest people's ladders. It is reported beside the pre-registered measure, never instead of it.
- **Two descriptive columns.** "Framed" (ink at all four edges) and answer length were added.
- **Six tiles, not one, per animation stage.** The plan picked each model's first rendered sample for the animation, but one drawing can't show variety. The bubble shows the first six answers instead (failures included), and act 1 shows 3 of the 6 data sizes (100, 1,000, 20,000).
- **Glimmer in the E1 band.** The plan named families but didn't say whether Glimmer joins the 30–33B band. It does, as one more maker.
- **Where things ran.** The two FP8 32B models planned for axon-server03 (OLMo 2 32B and Qwen3-32B) failed there, offline, for want of the FP8 kernel download. They ran on axon-server01 with the Hub online instead. Nothing else changed.
- **Reasoning.** The plan said no model reasons before answering. The API models did, briefly, at "minimal" effort (see the caveats).
- **Everything else was kept:** models, sizes, prompt, temperatures, seeds, measures, tests and verdict rule.

## Compute and cost

- **Meta API: $0.22**
  - Spark: 24 calls, $0.074.
  - Wonder: 24 calls, $0.147.
  - The two parameter-check calls cost under $0.001.
  - The plan's cap was $3, with Wonder under $1.5. The shared ledger stood at $61.21 afterwards, under the $70 stop.
- **GPU (NVIDIA L40S, 46 GB): about 1.6 GPU-hours of wall time, all in `~/MetaLesionLab_scale` under nohup.** Every GPU was idle before we started, and no one else's process was touched.
  - **axon-server02 (Arm A):** 71 minutes for 18 training runs, 6 at a time (6.5 hours summed), plus drawing, rendering and DINOv2 of 21,000 reference chairs.
  - **axon-server01 and axon-server03 (Arm B):** about 18 minutes of generation for 16 open models × 24 samples, plus loading. Downloading the open weights (ungated, no token) took most of an hour of wall time.
- **Mac:** rendering the SVGs, DINOv2 and SigLIP 2 embeddings for Arm B and the reader, the analysis, figures, page and animation.

## Files

- **Code:**
  - `metalesionlab/plato_scale.py`: the design (models, revisions, sizes, seeds), SVG extraction, rendering and failure classes, nested subsets, the best-checkpoint rule, the verdict rule and the public file's schema. Tests in `tests/test_plato_scale.py`.
  - `scripts/plato_scale_sketch.py`: Arm A, run on the GPU (held-out chairs, training with held-out loss, embedding).
  - `scripts/plato_scale_svg.py`: Arm B generation (`open` on a GPU, `api` on the Mac), then `measure` (render, classify, embed).
  - `scripts/plato_scale_reader.py`: the SigLIP 2 check.
  - `scripts/plato_scale_analyze.py`: the pre-registered analysis; writes `results.json` and the public file.
  - `scripts/plato_scale_figures.py`: the walls, the curves and the page's sprites.
  - `scripts/plato_scale_animation.py` with `scripts/plato_scale_animation_template.html`: the animation.
- **Page:**
  - `metalesionlab/web/pages/plato_scale.html`, `static/js/plato_scale.js`, `static/css/plato_scale.css`;
  - `static/img/plato_scale/` (the two walls as masked WebP sprites and `wall.json`);
  - `metalesionlab/web/plato_scale_routes.py`, registered in `app.py`'s `SITE_ROUTERS["plato"]`.
- **Data, outside the repository (`PlatosChair/scale/`):**
  - `svg/raw` (every model's text), `svg/png`, `svg/emb`, `svg/measure.json`;
  - `sketch/runs/n<size>_s<seed>` (samples, embeddings, `meta.json`; checkpoints stay on axon-server02) and `sketch/ref`;
  - `reader_siglip.json` and `results.json`.
- **Figures (`PlatosChair/scale/figures/`):**
  - `wall_models.png`: 12 chairs per model, every family smallest to largest, then Glimmer and the API models;
  - `wall_models_primary.png`: Qwen2.5 and Meta's models;
  - `wall_data.png`: the sketch model by data size;
  - `curves.{png,svg}`: spread, recognizability, the SigLIP 2 check and failures, by model size and by data size.
- **Public statistics:** `public_data/plato_scale.json` (derived only: no SVG text, drawings or embeddings).

**Re-running** (each step resumes):
```
# axon-server02 (PYTHONPATH reaches the checkout and a scipy)
python scripts/plato_scale_sketch.py heldout --out data/heldout_chair.ndjson
python scripts/plato_scale_sketch.py train --size 100 --seed 1 --data data/train_chair.ndjson --heldout data/heldout_chair.ndjson --out runs/n100_s1   # 6 sizes x seeds 1-3
python scripts/plato_scale_sketch.py embed --run runs/n100_s1 ...
python scripts/plato_scale_sketch.py ref --data data/train_chair.ndjson --heldout data/heldout_chair.ndjson --out ref
# axon-server01/03 (Hub online for the FP8 kernel)
python scripts/plato_scale_svg.py open --model qwen25_0.5b ... glimmer --out svg
# Mac
MLL_LEDGER=runs/costs.jsonl python -I scripts/plato_scale_svg.py api --model spark --out $PLATO_SCALE_DIR/svg   # and wonder
python -I scripts/plato_scale_svg.py measure --out $PLATO_SCALE_DIR/svg
python -I scripts/plato_scale_reader.py
python -I scripts/plato_scale_analyze.py --public public_data/plato_scale.json
python -I scripts/plato_scale_figures.py --web
python -I scripts/plato_scale_animation.py --out <dir>/index.html --text <dir>/text.json
```

Credits: drawings Google Quick, Draw! (Google Creative Lab, CC BY 4.0; statistics only, no drawing is shown). Similarity: Meta DINOv2, Apache-2.0. Check reader: Google SigLIP 2 So400m, Apache-2.0. Sketch model design after Sketch-RNN (Ha & Eck 2017). Language models: Qwen2.5 and Qwen3 (Alibaba Cloud), OLMo 2 (Allen Institute for AI), Muse Glimmer 30B (Meta), all Apache-2.0; Muse Spark 1.3 and Muse Wonder 1.0 through the Meta Model API. Hypothesis: Huh, Cheung, Wang & Isola (2024), *The Platonic Representation Hypothesis*, ICML 2024, arXiv:2405.07987.

# Plato's Chair, damaged

What happens to an AI's idea of a chair when you damage its "language part"? We damaged the two parts of an image model, Stable Diffusion XL, step by step, and asked it for a rocking chair, a wheelchair, a throne and five other chairs, plus hats, birds and clocks. We also damaged Meta's Muse Glimmer while it read Muse Image's doodles, and, as a stretch, Janus-Pro, one model that both draws and reads. This is a study of models. The link to semantic dementia is an analogy, not a claim about people.

**Short answer.** Damaging the language part changes **what** SDXL draws, damaging the drawing part changes **how** it draws, but a damaged language part does **not** send a rocking chair back to Plato's plain chair.
- **What it is (primary, neurons switched off).** At equal amounts of picture change, language damage left fewer chairs that Glimmer still reads as the asked kind than drawing damage did: −38 vs. −25 percentage points from intact, a difference of **−12 points [95% CI −20, −4]** (kinds resampled: [−19, −7]).
- **How it is drawn.** The other half of the planned double dissociation reversed for neuron loss: language damage also cost more "clean line drawing" (−0.05 [−0.07, −0.04]), because the doodle style is in the words too. With noise lesions both halves came out as predicted on the broad measures: language noise lowers "is this a chair?" more (−0.12 [−0.16, −0.07]) and drawing noise lowers "clean line drawing" more (+0.04 [+0.02, +0.06]).
- **No way back to the Form.** Language damage moves chairs **away** from the plain chair (+0.18 [0.14, 0.22] in DINOv2 distance, averaged over doses), never toward it. The chair turns into its scene or into other things: an office, a café, a house, a man in a wheelchair, a red car. Glimmer's names for the most damaged chairs: "car", "woman", "man", "robot", "bicycle". Drawing damage: "chair", "abstract", "qr code", "maze".
- **Clocks.** Intact SDXL cannot set a clock (the asked time on 1 of 40). Drawing damage strips the numbers first (12 numbers in order: 33% to 4%) while the outline survives; language damage removes the whole clock (a portrait, a robot, a street), and the clocks it still draws keep their numbers.
- **Damage the reader instead.** When a damaged Muse Glimmer still answers steadily, a throne or a wheelchair becomes "a plain, ordinary chair", the semantic-dementia-like fallback. But random neurons do the same at the same loss of right answers (+0.7 points [−3.3, +4.4]); only damage to its seeing neurons is different (no fallback, just guesses).
- **One model that does both.** Janus-Pro-7B reads and draws with one language model; the same damage takes both, reading first. With 35% of its language neurons off it reads the right kind for 18% of doodles (intact 85%) and draws the asked kind 36% of the time (intact 78%); its wheelchair becomes a tricycle, then a car.

Plan, hypotheses and doses were pre-registered before the main runs: `docs/plato_damage_plan.md` (commit `1d24ff8`).

## Method

| Step | What we did |
|---|---|
| Drawer | Stable Diffusion XL base 1.0 (`stabilityai/stable-diffusion-xl-base-1.0`, fp16, CreativeML OpenRAIL++-M) on one lab L40S. 768 px, 25 steps, guidance 5, the SDXL comparison's negative prompt, saved at 512 px. |
| Language part | Both text encoders: CLIP ViT-L (12 layers × 3,072 MLP neurons) and OpenCLIP bigG (32 × 5,120). One unit = one neuron after the activation (the input to `mlp.fc2`). |
| Drawing part | The UNet: 70 transformer blocks; one unit = one feed-forward neuron after GEGLU (2,560 or 5,120 per block). |
| Lesions | Reversible forward hooks (`metalesionlab/sdxl_lesions.py`); weights are never edited. **Zero**: a random share of every layer's neurons switched off, nested across doses (a higher dose keeps every neuron a lower one hit). **Noise**: Gaussian noise on every neuron, sd = dose × the neuron's sd over 16 reference doodle prompts; the same noise for every picture. **Targeted** (secondary): the top share of "specific-kind" text-encoder neurons (subordinate > basic-level phrases for 23 held-out pairs such as "a sports car" vs. "a car"), with a random control of the same count per layer. |
| Doses (set by the pilot) | text-zero 0.20, 0.25, 0.27, 0.29, 0.31; unet-zero 0.05, 0.10, 0.15, 0.20; text-noise × 0.25, 0.5, 0.75, 1.0; unet-noise × 0.75, 0.9, 1.0, 1.1; targeted and its control 0.1, 0.2, 0.3. |
| Prompts | The doodle template (`plato.STYLES["doodle"]`) with "a chair" and 8 named kinds (rocking chair, armchair, office chair, folding chair, high chair, wheelchair, beanbag chair, throne); hat (top hat, baseball cap, cowboy hat) and bird (owl, penguin, flamingo) as generality checks. Clocks: "a simple clock face showing" 3:00, 6:30, 8:45, 4:20, 1:55 and 10:10 (a generic instruction, no clinical test's wording). |
| Pictures | 8 seeds per prompt and condition, the **same seed at every damage level** (paired pictures); 16 for the intact plain prompts (the prototype). 3,288 kind pictures in 24 conditions and 624 clocks in 13, $0 (lab GPU). |
| Severity | DINOv2-base CLS of the ink-cropped picture (`plato.ink_crop`, as in plato.py); d_intact = cosine distance to the intact picture with the same seed. Language and drawing damage are compared at **matched severity**: each family's mean d_intact per dose is its severity curve, and an outcome's change from intact is read off at the 25th, 50th and 75th percentiles of the range both families reach. |
| What it is | Muse Glimmer 30B's kind labeler (multiple choice: the concept's kinds + "a plain, ordinary ..." + "can't tell, or not a ...", letter logits, forward and reversed option order averaged), and its P(yes) to "Is this a drawing of a chair?". |
| How it is drawn | Glimmer's P(yes) to "Is this a clean, simple line drawing, with black lines on a plain white background and no color, shading or texture?" on the raw picture; pixel checks: colorfulness, gray (midtone) share. |
| Prototype drift | d_proto = distance to the plain prototype (centroid of the intact "a chair" pictures); d_kind = distance to the kind's intact centroid, leaving out the picture's own seed; drift index = d_kind − d_proto. |
| Clocks | Muse Spark (`muse-spark-1.3`, vision, minimal reasoning) answered our JSON rubric: is it a clock, outline, how many hour numbers, in order, extra or garbled numbers, number of hands, where each hand points, the time read. 40 random clocks were checked by eye. |
| Glimmer arm | Muse Glimmer 30B (FP8, one L40S) read Muse Image's named-kind doodles (`PlatosChair/core/ai/doodle_listed`, picture i shows kind i) for the 22 things whose kinds it labeled reliably in the variety study: 288 pictures, 221 labeled right when intact. Lesions from the lesion lab: language-, naming- and seeing-localizer neurons (`*_en` localizers), mean-ablated at the top 10, 20 and 30%, each with a random control of the same count per layer; noise on layers 9–16 and 41–48. |
| Janus stretch | Janus-Pro-7B (`deepseek-community/Janus-Pro-7B`, DeepSeek, MIT): a random share of its language model's MLP neurons switched off (0, 20, 35, 50, 65%), the same units for drawing (9 chair prompts × 4 seeds, 384 px) and reading (40 named-kind doodles of chairs, hats and birds, the same multiple choice). |
| CIs | 95% percentile bootstraps: over (kind, seed) pictures with a picture's doses kept together (4,000 resamples), and over kinds as a robustness check; over pictures for the Glimmer arm and clocks. |

Code: `metalesionlab/sdxl_lesions.py`, `metalesionlab/plato_damage.py`, `scripts/plato_damage_{sdxl,glimmer,janus,analyze,figures,web}.py`. Pictures and raw results live outside the repository in `PlatosChair/damage/`; `public_data/plato_damage.json` holds only derived statistics.

## Findings

### 1. The Form or the hand (H1, primary)

Primary test: neurons switched off, 8 chair kinds × 8 seeds, matched on how much the picture changed (DINOv2 distance to its intact twin; the matched severities are 0.16, 0.32 and 0.48). Values are changes from intact, read off each family's curve and averaged; the difference is language minus drawing.

| Measure (chairs) | Language part | Drawing part | Difference [95% CI] | By kind | Prediction |
|---|---|---|---|---|---|
| **Still read as the asked kind** (Glimmer, 48 intact-correct) | −38 pts | −25 pts | **−12 pts [−20, −4]** | [−19, −7] | below 0: **yes** |
| "Is this a drawing of a chair?" P(yes) | −0.18 | −0.11 | −0.07 [−0.12, −0.02] | [−0.14, +0.02] | below 0: yes |
| **"Clean line drawing?"** P(yes) | −0.10 | −0.04 | **−0.05 [−0.07, −0.04]** | [−0.08, −0.03] | above 0: **reversed** |
| Gray share of the picture (pixels) | +0.16 | +0.00 | +0.16 [+0.12, +0.19] | | (none) |
| Labeled "a plain, ordinary chair" | +2 pts | +6 pts | −3 pts [−8, +1] | | above 0: no |
| Labeled "can't tell, or not a chair" | +18 pts | +12 pts | +7 pts [+0, +12] | | below 0: reversed |
| Named as some other object (one word) | +15 pts | +7 pts | +8 pts [+1, +16] | | (exploratory) |

**Verdict (H1): partly supported.** Part (a) holds: language damage loses the Form, the kind, faster than drawing damage does. Part (b) reverses for neuron loss, so there is no clean double dissociation in this primary test. Switching off UNet neurons turns the paper into black-and-white texture (`figures/melt_unet-zero.png`), which neither the pixels (no gray, no colour) nor Glimmer count as "unclean" very much. Language damage brings back shading, gray paper and colour, because the words "doodle, black marker, no shading" pass through the damaged encoders too.

Secondary test, noise in the neurons, same matching:

| Measure (chairs) | Language | Drawing | Difference [95% CI] |
|---|---|---|---|
| Still read as the asked kind | −30 pts | −25 pts | −4 pts [−12, +3] |
| "Is this a drawing of a chair?" | −0.22 | −0.10 | **−0.12 [−0.16, −0.07]** |
| "Clean line drawing?" | −0.08 | −0.11 | **+0.04 [+0.02, +0.06]** |
| Gray share (pixels) | +0.10 | +0.29 | −0.19 [−0.21, −0.16] |
| Named as some other object | +14 pts | +6 pts | +8 pts [+2, +14] |

With noise, the pattern Plato would like appears on the broad measures: language noise loses "is it a chair at all" and keeps the line; drawing noise keeps the chair and loses the line (`figures/melt_text-noise.png` against `figures/melt_unet-noise.png`; `figures/dissociation.png`). The finer "which kind" measure does not separate the two kinds of noise; drawing noise blurs exactly the details (rockers, wheels) that tell kinds apart.

### 2. No way back to Plato's chair (H2)

The prediction from semantic dementia failed. Damaged language does not turn a rocking chair back into the plain chair: it moves it **away** from the plain chair.

| Chairs, 8 kinds × 8 seeds | Change in distance to the plain chair, mean over doses [95% CI] |
|---|---|
| Language, neurons off | +0.18 [0.14, 0.22] |
| Language, noise | +0.16 [0.13, 0.19] |
| Drawing, neurons off | +0.08 [0.05, 0.10] |
| Drawing, noise | +0.06 [0.02, 0.10] |

At matched severity, language minus drawing damage: +0.025 [+0.000, +0.053] for neurons off and +0.071 [+0.050, +0.092] for noise (the prediction was below zero). The drift index the brief asked for, d_kind − d_proto, rises under every kind of damage (a picture starts next to its own kind and far from the prototype, so any change raises d_kind faster); at matched severity it does not separate language from drawing damage (neurons off +0.003 [−0.024, +0.031]; noise −0.042 [−0.064, −0.018], drawing higher).

**Where the chairs go instead.** Language damage turns an object into its scene: an office chair becomes an office, a high chair a café, a beanbag chair people lounging on beanbags, a folding chair a little house, a wheelchair a man in a wheelchair, and a rocking chair a room, a red car or cartoon people (`figures/melt_text-noise.png`). The doodle style goes too (colour and shading come back), because the style words pass through the same damaged encoders. Glimmer's one-word names say the same. At the strongest language damage, 64% (neurons off) and 72% (noise) of named-kind chairs get the name of some other object, against 6% intact; the most common were "car", "woman", "man", "person", "robot", "bicycle", "table" and "room". At the strongest drawing damage, names split between "chair" (28–41%), no object at all ("abstract", "qr code", "maze": 23–31%) and other objects (22–30%). Under mild drawing damage Glimmer calls the chairs just "chair" more often (56–62% vs. 52% intact), as the details that name a kind blur.

Hats and birds (H4): the results lean the same way but are weaker (3 kinds × 8 seeds each). Neither moved toward its plain prototype under any family. With noise, hats repeat the chair pattern: language noise lowers "is this a hat?" more (−0.15 [−0.21, −0.08]) and drawing noise lowers "clean line drawing" more (+0.06 [+0.03, +0.10]); damaged hats are named as other objects more under language noise (+17 points [+8, +28]). With neurons switched off, hats lean the other way on kind (+12 points [−1, +25], CI spans 0) and birds show no difference (−4 points [−12, +5]). Birds change less at these doses (at the matched severities Glimmer still reads 88% of language-damaged and 92% of drawing-damaged birds as the asked kind), so they say little.

The targeted "specific-kind" lesion (H5) changed the pictures less than its random control at every dose (DINOv2 change 0.18 vs. 0.31, 0.42 vs. 0.61, 0.78 vs. 0.89) and did not move them toward the plain chair: at matched severity, the targeted lesion and its random control did the same to the kind (+2 points [−4, +9]), to "is it a chair" (−0.02 [−0.05, +0.02]) and to the distance to the plain chair (−0.003 [−0.023, +0.018]). Neurons that respond to specific kinds are not where SDXL keeps the kind; they just do less harm per neuron.

### 3. Clocks (H6)

**Intact SDXL cannot set a clock.** Asked for a time other than 10:10, it drew hands at the asked time on 1 of 40 clocks (2.5% [0, 7.5]) and hands at 10:10 on 5 of 40 (12.5% [2.5, 25]); asked for 10:10, it got 2 of 8. Its clocks always have an outline, 12 numbers in order on 33% (often pseudo-Roman glyphs) and two hands on 52%.

| Clocks (48 per condition) | is a clock | outline | 12 numbers in order | two hands | numbers, among clocks |
|---|---|---|---|---|---|
| intact | 100% | 100% | 33% | 52% | 33% [21, 46] |
| language off 25% / 29% / 31% | 83 / 50 / 44% | 88 / 58 / 54% | 33 / 23 / 17% | 52 / 35 / 29% | 40 / 46 / 38% |
| drawing off 10% / 15% / 20% | 73 / 60 / 52% | 85 / 73 / 60% | 4 / 6 / 2% | 46 / 42 / 31% | 6 / 10 / 4% |
| language noise × 0.5 / 0.75 / 1 | 73 / 23 / 0% | 79 / 31 / 6% | 25 / 8 / 0% | 44 / 17 / 0% | 34 / 36 / – |
| drawing noise × 0.9 / 1 / 1.1 | 81 / 52 / 6% | 81 / 54 / 8% | 6 / 2 / 0% | 50 / 33 / 4% | 8 / 4 / 0% |

- **Drawing damage strips the numbers first.** At the mildest dose the outline survives (85%) and two hands survive (46%), but 12 numbers in order fall from 33% to 4% (UNet off 10%; noise × 0.9: 6%). Among pictures that are still clocks, numbers survive on 4–10%.
- **Language damage removes the whole clock instead.** The clocks it still draws keep their numbers at the intact rate (38–46% among clocks), but more and more pictures are not clocks at all: a woman's portrait, a robot, a street, a crowd.
- The pre-registered "first to fail" rule names the asked time for language damage, but that is a floor effect: intact SDXL sets the asked time on only 6% of clocks, so it is not informative. For drawing damage the rule names the numbers, as predicted; the outline does not fail first.
- **Eye check.** For 40 random clocks, Spark's "is it a clock" matched our reading on 37; it counts SDXL's pseudo-Roman glyphs as numbers generously, so the numbers rate is an upper bound for every condition alike.

### 4. Damage the reader: Muse Glimmer (H7)

Glimmer read Muse Image's named-kind doodles (a throne, a wheelchair, a top hat, a cactus ...). We counted only answers that stay the same when the options are listed in reverse order; an answer that flips is a letter habit, not a reading.

**Short answer.** When a damaged Glimmer still answers steadily, its mistakes are "a plain, ordinary ...", almost never another specific kind and almost never "can't tell": the semantic-dementia-like fallback from the specific to the general. But the fallback is not special to the language neurons. Random neurons do the same at the same loss of right answers. Damage to the **seeing** neurons is different: no fallback, just letter guesses.

Among the 221 pictures Glimmer labeled right when intact (all answers / steady answers only):

| Lesion | Still right (all) | Still right (steady) | Steady "plain" | Steady other kind | Steady "can't tell" | Flips with option order |
|---|---|---|---|---|---|---|
| intact | 100% | 95% | 0% | 0% | 0% | 5% |
| language neurons, top 10 / 20 / 30% | 84 / 71 / 29% | 76 / 63 / 10% | 11 / 18 / 24% | 0 / 0 / 0% | 0 / 0 / 5% | 12 / 19 / 60% |
| random, same counts | 89 / 54 / 13% | 83 / 39 / 1% | 2 / 28 / 2% | 1 / 0 / 0% | 0 / 0 / 0% | 13 / 33 / 97% |
| naming neurons, 10 / 20 / 30% | 84 / 18 / 12% | 72 / 3 / 0% | 8 / 22 / 0% | 0 / 0 / 0% | 0 / 1 / 0% | 19 / 74 / 100% |
| random, same counts | 71 / 83 / 73% | 55 / 69 / 40% | 16 / 10 / 7% | 0 / 0 / 0% | 1 / 0 / 0% | 27 / 21 / 53% |
| seeing neurons, 10 / 20 / 30% | 95 / 59 / 11% | 89 / 27 / 0% | 0 / 1 / 0% | 1 / 0 / 0% | 0 / 0 / 0% | 10 / 72 / 100% |
| random, same counts | 86 / 49 / 18% | 77 / 38 / 0% | 5 / 38 / 0% | 1 / 0 / 0% | 0 / 1 / 0% | 16 / 24 / 100% |
| noise, layers 9–16, × 1 / × 2 | 52 / 5% | 22 / 0% | 1 / 0% | 0 / 0% | 0 / 0% | 76 / 100% |
| noise, layers 41–48, × 1 / × 2 | 99 / 98% | 92 / 91% | 0 / 0% | 0 / 0% | 0 / 1% | 8 / 8% |

- **The fallback is to the general kind.** Steady errors are "plain" in every damaged condition that still answers; steady "other kind" errors are 0–1% and "can't tell" 0–5%. For chairs alone (15 pictures), the strongest language lesion calls 7 of 15 specific chairs "a plain, ordinary chair" (random: 0 of 15).
- **Pre-registered test (H7), lesion vs. its random control at the same count:** language neurons +6.8 points of "plain" answers [2.7, 10.9] at 10%, −20.8 [−27.2, −14.9] at 20%, +33.9 [27.2, 40.7] at 30% (all answers; by-thing bootstrap gives the same signs). **Mixed:** the random controls break at different doses than the targeted lesions (at 30%, random neurons leave 1% steady answers), so equal counts do not mean equal damage.
- **Exploratory, matched loss of right answers** (the same idea as matched severity): language neurons minus random, steady "plain" +0.7 points [−3.3, +4.4]; naming −1.3 [−3.9, +1.3]; seeing neurons −21.1 [−25.1, −18.0], with +34.7 points [28.2, 40.6] more answers that flip with the order. So damage to language or naming neurons degrades Glimmer the way random damage does, toward the general answer; damage to the seeing neurons makes it guess.
- **"Plain" is not a letter habit.** "Plain" sits second to last in every list, but its letter depends on the thing (M for 12 kinds, Q for 16). The strongest language lesion raised it for both (47% and 34% of answers); one condition did look like a letter habit (naming neurons at 20%: 57% for 12-kind things, 0% for 16-kind things).
- **Late layers barely matter here.** Noise on layers 41–48 left kind reading intact (98–99%), while noise on layers 9–16 destroyed it.
- **One-word names.** Glimmer names 55% of the intact-correct doodles with a specific word ("rockingchair", "wheelchair", "throne") and 32% with the basic name. Under damage, the basic name does not take over: under the language lesions specific names fall from 50% to 5% and basic names from 37% to 0%, because the answers turn into carrier phrases ("The object in this picture is").

### 5. Stretch: one model that draws and reads (Janus-Pro-7B)

Janus-Pro-7B reads pictures and draws them with the same language model, so one lesion hits both. With a random share of that model's MLP neurons switched off (the same neurons for both tasks), **reading and drawing fail together, reading first**:

| Language-model neurons off | Reads the right kind (40 doodles) | Draws the asked kind (36 drawings; chance 11%) | Drawing changed (DINOv2) |
|---|---|---|---|
| none | 85% [72, 95] | 78% [64, 92] | 0 |
| 20% | 60% [45, 75] | 72% [56, 86] | 0.55 |
| 35% | 18% [8, 30] | 36% [19, 53] | 0.68 |
| 50% | 5% [0, 12] | 14% [3, 25] | 0.82 |
| 65% | 13% [3, 22] | 19% [8, 33] | 0.88 |

- "Draws the asked kind" means the drawing sits nearest its own kind's intact drawings among the 9 chair prompts (DINOv2, leave one seed out); intact drawings reach 78% on this measure.
- Janus's drawings fail the way SDXL's do: the wheelchair becomes a tricycle (20%), a trike (35%) and a car (50%); at 65% everything turns into colourful photographic texture (`figures/janus_draw.png`).
- At 35%, a third of Janus's reading answers are "a plain, ordinary ..." (33%, against 10% intact), the same fallback as damaged Glimmer; at 50% and more the answers are letter habits.
- Small n (40 reading items, 4 seeds × 9 prompts per dose) and one random lesion; a first look.

## Caveats

- **Models, not people.** The analogy to semantic dementia and to clock drawing is about the pattern of errors in a model. Nothing here says anything about any person, and nothing here is a test.
- **One drawer, one setting.** SDXL base, guidance 5, one negative prompt. Its intact doodles are not clean (shading, frames, scenes), so "clean line drawing" starts low (Glimmer's P(yes) about 0.3 intact).
- **The style words are damaged too.** "Doodle, black marker, no shading" passes through the same text encoders, so language damage also changes the style. The drawing-retention test is therefore conservative for H1(b).
- **Readers are models.** Glimmer reads the kind and the style, Spark reads the clocks, DINOv2 measures similarity. All three can be wrong; Glimmer's kind labeler names 58% of named kinds right on clean doodles.
- **Severity is DINOv2 distance.** Matching on it treats "turned into a car" and "turned into charcoal" as equal amounts of change when DINOv2 says so.
- **Doses.** Zeroing is cumulative random neuron loss; noise is the same pattern for every picture. Text-zero has a steep step between 25% and 30% of neurons off.
- **Small n where noted.** 8 seeds per prompt; hats and birds 3 kinds each; Janus 4 seeds and 40 reading items.
- **Exploratory parts.** Glimmer's one-word names, the steady-answer rule, the matched-loss comparison in the Glimmer arm, "numbers among clocks" and the Janus arm were not in the plan.

## Denser rows (display only)

The hero rows on `/damaged` and `/plato/damage` show ten pictures each: undamaged plus nine doses, left to right, from none to the strongest dose the page already used. A display upgrade: same pipeline, prompt, seed and settings (SDXL, 768 px, 25 steps, guidance 5, the same negative prompt and unit statistics); only the dose ladder is denser. Undamaged and the strongest dose reproduce the earlier pictures. No statistics change.

| Row | Damage | Seed (picture) | Doses (noise ×) |
|---|---|---|---|
| Rocking chair | words part, noise | picture 1 of the experiment's rocking chair | 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0 |
| Throne | words part, noise | picture 0 of the throne | 0.2 to 1.0, same steps |
| God | words part, noise | ideas-damage picture 13 (the page's medoid pick) | 0.2 to 1.0, same steps |
| Clock "a simple clock face showing 8:45" | drawing part, noise | picture 0 | 0.70, 0.75, ..., 1.10 |

Run with `scripts/plato_damage_dense.py` on a lab GPU (axon-server01, one L40S, 40 pictures, about 2 minutes; the device is written to each row's `meta.json`); `scripts/plato_damage_dense_web.py` makes the small WebP tiles in `static/img/plato_damage/dense/` and the hero slides. Raw pictures and contact sheets: `PlatosChair/damage_dense/out/`. The "Pictures in a row" control (5, 7, 10) shows evenly spaced steps and always keeps the first and the last. No God picture was grotesque or mocking, so the seed stayed.

## Cost

Muse Spark clock scoring: 624 calls, $1.61. SDXL, Glimmer and Janus ran on lab GPUs at $0. Total for this experiment: $1.61.

## Reproduce

```bash
# GPU (lab server with SDXL and Glimmer; ~/MetaLesionLab_damage is this repo's code)
python scripts/plato_damage_sdxl.py stats --out ~/plato_damage
python scripts/plato_damage_sdxl.py localize --out ~/plato_damage
python scripts/plato_damage_sdxl.py run --out ~/plato_damage/main --stats ~/plato_damage/unit_stats.pt \
  --localizer ~/plato_damage/specific_localizer.json --n 8 --n-plain 16 --conditions intact \
  text-zero@0.2 text-zero@0.25 text-zero@0.27 text-zero@0.29 text-zero@0.31 unet-zero@0.05 unet-zero@0.1 \
  unet-zero@0.15 unet-zero@0.2 text-noise@0.25 text-noise@0.5 text-noise@0.75 text-noise@1 unet-noise@0.75 \
  unet-noise@0.9 unet-noise@1 unet-noise@1.1 text-spec@0.1 text-spec-random@0.1 text-spec@0.2 \
  text-spec-random@0.2 text-spec@0.3 text-spec-random@0.3
python scripts/plato_damage_sdxl.py run --out ~/plato_damage/clocks --stats ~/plato_damage/unit_stats.pt --n 8 \
  --keys clock__3_00 clock__6_30 clock__8_45 clock__4_20 clock__1_55 clock__10_10 --conditions intact \
  text-zero@0.25 text-zero@0.29 text-zero@0.31 unet-zero@0.1 unet-zero@0.15 unet-zero@0.2 text-noise@0.5 \
  text-noise@0.75 text-noise@1 unet-noise@0.9 unet-noise@1 unet-noise@1.1
# Mac: copy main/ and clocks/ to PlatosChair/damage/, then
python scripts/plato_damage_analyze.py crop main          # ink-cropped copies for Glimmer -> main_crop448/
python scripts/plato_damage_analyze.py embed main && python scripts/plato_damage_analyze.py measures main
# GPU: Glimmer reads the pictures (copy main_crop448/ there first), then the damaged-Glimmer arm and Janus
python scripts/plato_damage_glimmer.py label-sdxl --naming --input ~/plato_damage/main \
  --cropped ~/plato_damage/main_crop448 --out ~/plato_damage/main_labels
python scripts/plato_damage_glimmer.py lesion --pictures ~/plato_damage/kinds_input/ai_doodle_listed \
  --out ~/plato_damage/glimmer_arm --keys bench bicycle bird book cactus car chair clock cup dog face fish \
  floor_lamp flower guitar harp hat house saw shoe tree yoga --conditions intact language-mlp-mean@0.1 ...
python scripts/plato_damage_janus.py read --pictures ~/plato_damage/kinds_input/ai_doodle_listed \
  --out ~/plato_damage/janus_read --doses 0 0.2 0.35 0.5 0.65
python scripts/plato_damage_janus.py draw --out ~/plato_damage/janus_draw --doses 0 0.2 0.35 0.5 0.65 --n 4
# Mac: copy main_labels/, glimmer_arm/, janus_read/, janus_draw/ back, then
python scripts/plato_damage_analyze.py stats main --labels main_labels
python scripts/plato_damage_analyze.py glimmer && python scripts/plato_damage_analyze.py janus
MLL_LEDGER=runs/costs.jsonl python scripts/plato_damage_analyze.py clocks clocks --side 320   # Muse Spark, ~$1.60
python scripts/plato_damage_analyze.py clockstats clocks
python scripts/plato_damage_figures.py && python scripts/plato_damage_web.py
```

Figures: `PlatosChair/damage/figures/` — `melt_{text,unet}-{zero,noise}.png` (every chair kind across the damage levels), `hero_rocking_chair_{zero,noise}.png`, `hero_wheelchair_{zero,noise}.png`, `dissociation.png`, `prototype.png`, `glimmer_arm.png`, `clocks_{text,unet}-{zero,noise}.png`, `janus_draw.png` (Janus-Pro's chairs across its doses), `series_card.webp`, and the pilot grids `pilot_grid_{zero,noise,spec}.png`.

Credits: Stable Diffusion XL (Stability AI), CreativeML OpenRAIL++-M. Janus-Pro-7B (DeepSeek), MIT. Meta Muse Image 1.0 (named-kind doodles), Muse Glimmer 30B (reader), Muse Spark 1.3 (clock reader), DINOv2 (Apache-2.0). Bozeat, S., Lambon Ralph, M. A., Graham, K. S., Patterson, K., Wilkin, H., Rowland, J., Rogers, T. T., & Hodges, J. R. (2003). A duck with four legs: Investigating the structure of conceptual knowledge using picture drawing in semantic dementia. *Cognitive Neuropsychology*, 20(1), 27–47.

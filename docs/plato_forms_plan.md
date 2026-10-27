# Plato's Forms: pre-registration

Written on Oct 27, 2026, and committed before any study picture was generated or read. Results will go in `docs/plato_forms.md`. Any deviation from this plan will be listed there as a deviation.

Two follow-ups to Plato's Chair (`docs/plato.md`):
1. **The Platonic clock.** What time does an AI draw?
2. **Plato's own examples.** In Republic X, Plato uses the bed and the table, not the chair.

Code: `metalesionlab/plato_forms.py` and `scripts/plato_forms_*.py`. Data: `PlatosChair/forms/`, outside the repository. The core data in `PlatosChair/core/` is only read, never written. The 35-concept core list and its results stay unchanged.

**What I had seen before writing this.** Before writing the plan I looked at three sets of existing core pictures as contact sheets:
- Muse's 12 core clock doodles: about 10 of 12 look like 10:10;
- SDXL's 16 core clock doodles: ornate, with mixed times;
- the first 48 of the 200 Quick, Draw! clocks: mostly L-shaped hands, some with no hands.

These informed the predictions below. I had seen no bed or table pictures.

## 1. The Platonic clock

**Question.** Image generators are widely reported to draw clocks at about 10:10, the time used in watch adverts, whatever time is asked for. Does Muse Image do this? Does SDXL? What time do people draw when simply asked to draw a clock?

### Design

| Condition | Prompt | Muse Image | SDXL | n |
|---|---|---|---|---|
| Doodle, no time | the core doodle prompt for "a clock" | the core's 12, plus 4 new | the core's 16 (same prompt and settings) | 16 each |
| Doodle, time asked | doodle template with "a simple clock face showing {time}" | 12 times × 8 | 12 times × 8 | 96 each |
| Photo, no time | "A photo of a wall clock." | 16 | 16 | 16 each |
| Photo, time asked | "A photo of a wall clock showing {time}." | 6 times × 8 | 6 times × 8 | 48 each |
| People | the first 200 recognized Quick, Draw! "clock" drawings (cached in core) | | | 200 |

The full doodle template is: *"A quick simple doodle sketch of {phrase}, black marker on plain white, like a 20-second drawing, no text, no shading."*

- **Requested times:** 1:20, 2:35, 3:00, 4:55, 5:10, 6:30, 7:50, 8:15, 9:45, 10:40, 11:05 and 12:25. Each hour from 1 to 12 appears once, and each five-minute mark appears once. None is within 25 minutes of 10:10 (with the hands either way round).
- **Photo subset:** 1:20, 3:00, 4:55, 6:30, 9:45 and 10:40.
- **Muse Image** (`muse-image-1.0`): separate calls of n = 4, so each requested time takes 2 calls. Pictures are downscaled to 512 px, as in the core run.
- **SDXL** (`stable-diffusion-xl-base-1.0`, fp16) runs on a lab GPU with the core settings: 768 px, 25 steps, the default Euler scheduler and guidance 5.
  - Doodles use the core negative prompt. Photos use none, because the core negative prompt says "photo".
  - Every picture has its own recorded seed: 20261027 + 1000 × condition index + picture index.

### Reading the time (fixed before any study picture is read)

Muse Spark (`muse-spark-1.3`, vision) reads each picture. It is asked for the number of hands and the time as JSON, or `"time": null` if there are no hands or they can't be read. The parser is `plato_forms.parse_reading`.

**Validation, done before this plan.** I tested the reader on 28 clocks drawn by code (`plato_forms.validation_set`, seeded):
- 24 had known times, 8 in each of three styles: thick marker with ticks, numbers, and a thin scribble like Quick, Draw!;
- 4 had no hands;
- the times were 10:10, its hand-swapped look-alike 1:50, and 22 random five-minute times at least 30 minutes from 10:10.

I compared three readers. The rule was: highest share within ±5 minutes, with ties going to the cheaper reader.

| Reader | Within ±5 min | Hand-less clocks found | 10:10 read on non-10:10 clocks | Cost / read |
|---|---|---|---|---|
| v1 (time directly), reasoning low | 22/24 | 4/4 | 0/22 | $0.0041 |
| **v1, reasoning minimal (chosen)** | **23/24** | **4/4** | **0/22** | **$0.0022** |
| v2 (hand directions first), minimal | 21/24 | 4/4 | 0/22 | $0.0025 |

The chosen reader's one miss read 1:50 as 2:50, the classic off-by-one hour when the hour hand is near the next number. The reader is now fixed: prompt `v1`, reasoning `minimal`.

**Spot check by eye.** I will read a random sample of 60 study pictures by eye, without seeing Spark's readings:
- 15 Muse doodles;
- 15 SDXL doodles;
- 10 photos (5 Muse and 5 SDXL);
- 20 people's drawings.

The sample is seeded. Agreement counts if both readings are within ±5 minutes, with the hands either way round, or if both say there are no hands. I will report the agreement and any disagreements.

### Measures

- **About 10:10** (`plato_forms.is_ten_ten`): the read time is within ±10 minutes of 10:10, with the hands either way round. A clock read as 2:50 or 1:50 counts.
  - **Chance level:** 41 of the 720 minute-times on the dial count as about 10:10, so the chance level is **5.7%** (`chance_ten_ten()`).
  - **Primary denominator:** all pictures. Pictures with no hands or an unreadable time count as not 10:10.
  - **Secondary denominator:** pictures with a read time.
- **Time accuracy** (time asked): the read time is within ±5 minutes of the requested time. Also reported: accuracy with the hands either way round, correct hour, and mean error in minutes.
- **Distribution of drawn times:** the directions of the hour and minute hands, shown as a clock-face heatmap per source. For people: the most common times and the share of hand-less clocks.
- **Model-free check:** the pixel average of each set of ink-cropped doodles. If most pictures are at 10:10, the average shows a sharp V.

### Statistics

- Proportions get Wilson 95% CIs.
- An exact binomial test compares each proportion with chance (5.7%).
- Fisher's exact test compares two sources.
- Time-asked measures get a CI from a cluster bootstrap over the requested times (10,000 resamples), because the 8 pictures of one time are not independent.

### Predictions

| # | Prediction | Confirmed if |
|---|---|---|
| C1 | Muse's no-time doodles are mostly 10:10 | 10:10 share ≥ 50% and above chance (binomial p < 0.05) |
| C2 | Muse often ignores the requested time | 10:10 share among time-asked doodles ≥ 25% and above chance, and time accuracy < 50% |
| C3 | SDXL draws 10:10 more than chance without a time, but less often than Muse | SDXL share above chance (p < 0.05) and below Muse's |
| C4 | SDXL rarely draws the time asked | SDXL time accuracy < 25% |
| C5 | People's clocks are rarely 10:10: mostly hand-less or other times | People's 10:10 share < 15% and below Muse's (Fisher p < 0.05) |

- **Photos are exploratory.** I expect the same direction, and probably more 10:10 than doodles, since product photos of clocks are usually set to 10:10.
- **Either way is interesting.** If Muse does draw the asked times, its "Form" of a clock is not the advert's.

## 2. Plato's own examples: the bed and the table

**Question.** Are Plato's own examples "Platonic" for Muse: drawn more uniformly than people draw them? Where do they fall among the 35 core concepts?

### Design

All steps follow the core pipeline unchanged. Bed and table are separate concepts in `plato_forms.FORMS_CONCEPTS`, outside `plato.CONCEPTS`.

| Set | n per concept |
|---|---|
| Muse doodles, usual prompt ("a bed", "a table") | 16 |
| "Any kind" ("a bed (any kind of bed)") | 16 |
| Named kinds: Muse Spark lists 16 kinds (the core listing prompt, reasoning low), and Muse Image draws each once | 16 |
| SDXL, usual prompt, core settings | 16 |
| SDXL, "any kind" and named kinds, the same seeds (extra) | 16 each |
| People: the first 200 recognized Quick, Draw! drawings in file order | 200 |

- **Muse calls:** separate calls of n = 4, as in the core run.
- **SDXL seeds:** the core scheme with concept indexes 35 (bed) and 36 (table): 20261026 + 1000 × index + picture index.

### Analysis

- **Embeddings:** ink-crop, DINOv2-base CLS embeddings, cosine distance.
- **Spread** is the mean pairwise distance. It gets a bootstrap CI over pictures (2,000 resamples).
- **People's spread:** 200 random subsets of 16 drawings, with a bootstrap CI over drawings (500 resamples).
- **Homogenization index:** Muse spread divided by people's spread, with a CI from independent bootstraps.
- **Ranks among the 35:** the core values come from the core `results.json`, read and not recomputed. I rank bed and table by:
  - the index;
  - Muse spread;
  - people's spread;
  - SDXL spread (core `results_sdxl.json`).
- **Relative spread:** the between-concept baseline is the mean distance to the 35 core concepts' centroids.
- **Recognisability:** the share of pictures nearest their own human centroid among 37 concepts (35 + bed + table).
- **Variety prompts:** for "any kind" and named kinds, the ratio to the usual prompt and to people.

### Predictions

- **B1.** For both, Muse is more uniform than people: the CI of the index lies entirely below 1.
- **B2 (a guess).** The table is in the most homogenized third of the 35 core concepts (index below the core's 12th-lowest). I make no prediction for the bed.
- **B3.** "Any kind" does not add variety: the CI of the ratio to the usual prompt includes 1. Named kinds lift the spread above people's (ratio > 1).
- **B4.** SDXL varies both more than Muse.

## Budget

My own spend is capped at $5, logged in `PlatosChair/forms/spend.jsonl`. Paid calls stop if the shared ledger passes $70. The estimates:

| Item | n | Estimate |
|---|---|---|
| Reader validation (done) | 84 reads | $0.25 |
| Muse clocks: 4 + 96 doodles, 16 + 48 photos | 164 pictures | $1.64 |
| Muse bed and table: usual, any kind, named kinds | 96 pictures | $0.96 |
| Spark kind lists | 2 calls | $0.01 |
| Spark readings (v1, minimal reasoning) | about 540 | $1.20 |
| **Total** | | **about $4.06** |

SDXL and DINOv2 cost nothing: SDXL runs on a lab GPU, DINOv2 on the Mac.

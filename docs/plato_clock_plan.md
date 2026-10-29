# The clock test: pre-registration

Written on Oct 28, 2026, and committed before any picture for this study was generated, read or scored. Results will go in `docs/plato_clock.md`. Any change to this plan will be listed there as a deviation.

**Question.** Would an AI pass the clock test? In the clock-drawing item of the Montreal Cognitive Assessment (MoCA), people are told: *"Draw a clock. Put in all the numbers and set the time to 10 past 11."* The drawing earns up to three points: contour, numbers and hands. We give Meta's image model, Muse Image, the same instruction and score its clocks the same way.

**Why it is interesting.** On `/plato/forms`, Muse Image drew the watch-advert time 10:10 on 13 of 16 clocks when no time was asked. Asked for other times, it never drew 10:10 (0 of 72), but it got the hour wrong on about half. 10 past 11 differs from 10:10 only in the hour hand, one number to the right.

Code: `metalesionlab/plato_clock.py` and `scripts/plato_clock.py`. Data: `PlatosChair/clock/`, outside the repository.

## People (not part of this run)

The people's side comes from 365 MoCA clock drawings in the USC Aging Brain Cohort (adults aged about 20 to 80), all given the instruction above. The drawings are analysed privately, under IRB approval. Only an aggregate export reaches this repository: average images of groups of at least 20 people, a typical-clock centroid with quantiles of distances, summary statistics and a README. No individual drawing, ID, date or per-person value enters the repository or the site. This study does not touch the drawings.

## Conditions

### A. Same instruction (primary)

- **Prompt, fixed:** *"Draw a clock. Put in all the numbers and set the time to 10 past 11. Simple black pen drawing on white paper."*
  - The first two sentences are the MoCA instruction, word for word. The last sentence asks for the look of a pen drawing on paper, so the picture can be compared with people's.
- **Model:** `muse-image-1.0`, through the project's client (`metalesionlab.meta_api`), so every call lands in the shared ledger.
- **n = 16**, as 4 calls of n = 4 (as on `/plato/forms`; there is no seed parameter). Pictures are downscaled to 512 px.

### B. Age personas (secondary)

Is prompting the same instruction 16 times fair, when hundreds of different people drew theirs? A second condition asks Muse Image to draw *as* 16 people of different ages.

- **Prompt:** the same prompt, prefixed with one age in years and nothing else: *"Drawn by a 34-year-old: Draw a clock. Put in all the numbers and set the time to 10 past 11. Simple black pen drawing on white paper."* No profession, health, gender or any other trait.
- **16 calls of n = 1**, one per age.
- **The 16 ages**, fixed by this rule before the run:
  - If the private export's `stats.json` exists when this condition is run, the 16 places are shared among its decades in proportion to each decade's n (largest remainder, at least one per decade). Within a decade with k places, the ages are spread evenly over the decade's age range in years.
  - Otherwise, 16 evenly spaced ages: 20, 24, 28, …, 80.
  - The results will say which rule was used.

### C. Language models drawing in code (optional, exploratory)

As `/plato/scale` did for chairs, two text models draw the clock as SVG code:

- **Prompt:** *"Draw a clock. Put in all the numbers and set the time to 10 past 11. Make it an SVG drawing: black lines and black text on a white background, 256 by 256 pixels, no colour fill. Output only the SVG code."*
- **Models:** Muse Spark 1.3 and Muse Wonder 1.0; 16 samples each, temperature 1.0, reasoning `minimal`, at most 4,096 completion tokens.
- The SVG is rendered with `plato_scale.classify` (cairosvg, no external files). A sample with no complete SVG, or one that doesn't render, scores 0 on every point and is reported as a failure.

This condition runs only if A and B leave enough of the budget.

## Scoring: the MoCA's three clock points

Each picture gets three points, 0 or 1 each, as in the MoCA instructions:

1. **Contour:** a clock face (a circle or square) is drawn; only minor distortions are allowed.
2. **Numbers:** all 12 numbers are present with no extra numbers, in the right order and roughly in the right quadrants. Roman numerals are fine, and numbers may sit outside the contour.
3. **Hands:** two hands together show 10 past 11. The hour hand points to the 11, the minute hand to the 2, the hour hand is clearly shorter, and the hands meet near the centre.

We also record **the time drawn**: the numbers the hour and minute hands point to. We classify it as 11:10 (the target), 10:10 (the advert time), hands swapped, another time, or no time (fewer than two hands).

### By eye (primary)

- I (Claude, the analyst) score every picture by eye, from enlarged contact sheets that show only file names.
- I record the three points, the hand count, where each hand points, and a short note.
- **Order:** the eye scores are written to `byeye.json` before Muse Spark reads any picture. The script refuses to run Spark on a set until every picture in it has an eye score.

### Muse Spark's checklist (secondary)

- Muse Spark 1.3 (vision, reasoning `minimal`, image at 384 px) answers the clock checklist `/plato/damage` used, word for word: `plato_damage.CLOCK_RUBRIC`.
- It answers in JSON: is it a clock, contour, how many numbers, in order, extra or wrong numbers, how many hands, where the shorter and the longer hand point, and the time read.
- The points come from its answers (`plato_clock.spark_points`):
  - contour = `contour`;
  - numbers = 12 numbers, in order, none extra or wrong;
  - hands = exactly 2 hands, the shorter one pointing to 11 and the longer one to 2.
- The checklist can't judge "clearly shorter" or "meeting near the centre", so Spark's hands point is a little more lenient than the eye's.
- **Agreement** between eye and Spark is reported per point, as the share of pictures where they agree and as Cohen's kappa, for every condition read.

## Measures and comparisons

1. **Points.** For each condition: how many pictures earn each point, and the mean total (0 to 3), with Wilson 95% CIs on the shares.
2. **Against people.** The share of people with the hands point comes from `stats.json`. It is compared with Muse's share (condition A, by eye) with Fisher's exact test. The same is done for contour and numbers where `stats.json` reports them.
3. **The time drawn.** How many of the 16 show 11:10, how many 10:10, and how many something else.
4. **Distance from the typical clock.**
   - Each picture is prepared as the draw pad prepares a picture (`plato.ink_crop`, 256 px) and embedded with Meta's DINOv2-base (CLS token), the embedder of `/draw`.
   - We take its cosine distance to the people's typical-clock centroid from the export.
   - We place it among the export's distance quantiles. This assumes the export's centroid is in the same embedding; if its README says otherwise, the deviation will be reported.
5. **Spread.** The mean pairwise cosine distance among a condition's 16 pictures, with a bootstrap 95% CI (`plato.bootstrap_spread`). It is compared with people's spread, if the export reports one on the same definition.
6. **The average clock.** The pixel average of a condition's ink-cropped pictures, made the way the export's README says the people's averages were made (else a plain mean of the 256 px greyscale crops).

## Predictions (condition A)

- **P1, hands.** Muse Image earns the hands point (by eye) on at most 7 of 16 clocks, and its most common wrong time is 10:10.
- **P2, minute hand.** The minute hand points to the 2 on at least 12 of 16 clocks, by eye.
- **P3, contour and numbers.** Contour on at least 15 of 16. Numbers on at least 12 of 16.
- **P4, against people.** Muse's share of the hands point is below people's (Fisher's exact, two-sided p < 0.05).
- **P5, agreement.** Eye and Spark agree on at least 12 of 16 clocks for each point.

## Questions and predictions (condition B, age personas)

1. **Is the personas' spread larger than the default 16's, and how does it compare with people's?**
   - Prediction: larger than condition A's spread (bootstrap 95% CI of the difference above 0).
   - Prediction: still below people's spread, where the export reports it on the same definition.
2. **Does the AI's clock change with the stated age?**
   - We compute Spearman's rho, with a bootstrap CI and a permutation p (`plato.spearman_ci`), between stated age and:
     - distance from the typical clock;
     - total points by eye;
     - total points by Spark.
   - Directional prediction: older personas get clocks further from typical (rho > 0) and with fewer points (rho < 0).
   - With n = 16 this is exploratory, and a CI that crosses 0 will be reported as "no clear change".
3. **Does that change match, exaggerate or contradict the real decade trend?**
   - The real trend: the change in people's mean distance from typical, and in mean clock points, from the youngest to the oldest decade, from `stats.json`.
   - The AI's trend: the same change across the personas, by the same decades.
   - Rules, set now:
     - **contradicts** if the two changes have opposite signs and the AI's CI excludes 0;
     - **exaggerates** if they have the same sign and the AI's change is more than twice people's;
     - **matches** if they have the same sign and the AI's change is within twice people's;
     - **no clear change** if the AI's CI includes 0.

If the AI draws older people's clocks as shakier or broken while real older adults' aren't, that is a finding about the AI's picture of aging, its stereotype, and will be reported that way. It says nothing about people.

## Condition C (exploratory)

No predictions. We report the same three points (by eye and by Spark), the time drawn, and the failures for both models.

## Budget and safety

- **Hard cap:** $2.00 for this whole study, counted by the ledger tag `plato_clock`. The script checks it before every call.
- No new paid calls once the shared ledger passes $70.
- Expected cost:
  - Muse Image, 32 pictures: $0.32;
  - Spark readings, about 64: about $0.20;
  - SVG drawings: about $0.40.
- **No visitor ever triggers a paid call.** The page replays the results. The draw pad's clock uses DINOv2 on the server only.

## What will be published

- Muse's pictures and every reading.
- The people's export, exactly as the README of its public folder allows: group averages of at least 20 people and aggregate numbers.
- The draw pad's clock reference: the people's centroid and distance quantiles, and Muse's centroid. Nothing per person.

All of it is an analogy on one measure, not a diagnosis. Nothing here is a claim about any person's health.

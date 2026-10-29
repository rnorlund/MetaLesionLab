# The clock test: results

**Would an AI pass the clock test?** Meta's Muse Image got the MoCA clock instruction, *"Draw a clock. Put in all the numbers and set the time to 10 past 11."*, plus the style sentence *"Simple black pen drawing on white paper."* It drew 16 clocks. By eye, 13 of them earn all three of the MoCA's clock points. None shows the watch-advert time 10:10.

The plan, with the prompts, scoring rules and predictions, was committed before any picture was made: `docs/plato_clock_plan.md` (commit f4dda7c). The page is `/plato/clock`, and the draw pad's clock is `/draw?thing=clock`.

## Summary

| | Muse Image (A) | Muse Image as 16 ages (B) | Muse Spark, SVG (C) | Muse Wonder, SVG (C) | People |
|---|---|---|---|---|---|
| Contour, by eye | 16 / 16 | 16 / 16 | 16 / 16 | 16 / 16 | |
| 12 numbers, by eye | 16 / 16 | 16 / 16 | 16 / 16 | 16 / 16 | |
| Hands at 10 past 11, by eye | 13 / 16 | 11 / 16 | 15 / 16 | 16 / 16 | |
| All three points, by eye | 13 / 16 (81%) | 11 / 16 | 15 / 16 | 16 / 16 | 238 / 315 (76%) |
| Time drawn, by eye | 11:10 on 13; hands swapped 2; three hands 1 | 11:10 on 16 | 11:10 on 15; 11:05 on 1 | 11:10 on 16 | |
| Hands point, by Spark's checklist | 5 / 16 | 4 / 16 | 15 / 16 | 16 / 16 | |
| Eye and Spark agree on the hands | 8 / 16 (kappa 0.19) | 9 / 16 (kappa 0.26) | 16 / 16 | 16 / 16 | |
| Spread (mean pairwise distance) | 0.10 [0.06, 0.15] | 0.08 [0.06, 0.12] | 0.07 | 0.01 | 0.21 [0.20, 0.23] |
| Distance from people's typical clock | 0.21 [0.18, 0.24] | 0.17 [0.15, 0.18] | 0.25 | 0.22 | mean 0.11; median 0.08 |

The people's figures come from the private analysis's public export: 315 analysed Baseline clocks from the USC Aging Brain Cohort, with clock points scored by the study's raters. The page shows only group averages of 20 or more clocks and aggregate numbers.

## Condition A: the instruction, 16 times

- **The time.** By eye, Muse drew 10 past 11 on 13 of 16 clocks.
  - On two, the longer hand points to the 11, so they read about 1:55.
  - One has three hands, at the 10, the 11 and the 2.
  - None shows 10:10.
  - Asked only for "a clock" on `/plato/forms`, Muse drew 10:10 on 13 of 16. Given the words, it moved the hour hand one number on.
- **Contour and numbers.** All 16 have a closed round face and the 12 numbers in order. Three also have tick marks, and one writes "10 past 11" under the clock.
- **"Clearly shorter."** Muse draws its two hands nearly the same length. Where the hands point right, the hour hand is 75 to 88% of the minute hand.
  - The MoCA gives no number for "clearly shorter", and neither did the plan.
  - We set the line at 90% when eye scoring began, before Spark read any clock.
  - Read more strictly, fewer clocks earn the hands point: 13 at 90%, 10 at 85%, 3 at 80%.
- **Muse Spark's checklist** (`plato_damage.CLOCK_RUBRIC`, word for word):
  - It agreed with the eye on the contour and the numbers for all 16.
  - It agreed on the hands for only 8 of 16 (kappa 0.19). On 10 clocks it took the longer hand to be the hour hand, reading 2:55.
  - The checklist asks which hand is shorter, and Muse's hands differ by little, so this is where it fails.
  - On the SVG clocks, whose hour hands are clearly shorter, Spark agreed with the eye on every one.

### Predictions (pre-registered)

| | Prediction | Result | Verdict |
|---|---|---|---|
| P1 | Hands point on at most 7 of 16; most common wrong time 10:10 | 13 of 16; no 10:10 | **Not supported** |
| P2 | Minute hand at the 2 on at least 12 of 16 | 14 of 16 | Supported |
| P3 | Contour on at least 15, numbers on at least 12 | 16 and 16 | Supported |
| P4 | Muse's share below people's (Fisher, p < 0.05) | All three points: Muse 13 / 16, people 238 / 315, p = 0.77 | **Not supported** (see deviation 2) |
| P5 | Eye and Spark agree on at least 12 of 16 for each point | Contour 16, numbers 16, hands 8 | **Not supported** |

## Condition B: 16 age personas

The prompt was *"Drawn by a {age}-year-old: "* plus the same words, with ages 20, 24, …, 80. No other trait was given. The persona clocks were scored by eye under shuffled code names, blind to the ages, and then matched back.

- **Every persona clock shows 10 past 11** (16 of 16).
  - 11 earn the hands point.
  - The other 5 (ages 40, 44, 52, 64 and 80) have hands 91 to 95% as long as each other.
  - Several personas wrote "10 past 11" or "11:10 ~ ten past eleven" under the clock.
- **Q1, spread.**
  - The personas' spread is 0.08, against condition A's 0.10: a difference of −0.02 [−0.07, +0.04]. **The predicted wider spread was not supported.**
  - Both are about half of people's 0.21.
- **Q2, change with the stated age.** No clear change on any measure:
  - points by eye, rho −0.22 [−0.62, +0.25];
  - points by Spark, rho −0.13 [−0.63, +0.42];
  - distance from people's typical clock, rho −0.46 [−0.83, +0.11].
  - **The directional predictions were not supported.**
- **Q3, against people's decades.**
  - From the 20–29 group to the 70+ group, people's mean clock points change by −0.11.
  - The personas' (20, 24, 28 against 72, 76, 80) change by −0.33 [−1.00, 0.00] by eye, and by 0.00 [−0.67, +0.67] by Spark.
  - Distance from typical: people +0.024, personas −0.038 [−0.082, +0.001].
  - All three verdicts are **no clear change**, because every CI includes 0.
- **The AI's picture of aging.** Told only an age, Muse drew the same clock. It did not draw older people's clocks as shakier, and the real older adults' average clocks aren't either.

## Condition C: drawing in code

Muse Spark 1.3 and Muse Wonder 1.0 wrote the clock as SVG, 16 times each. All 32 rendered.

- By eye, Spark's clocks earned all three points 15 times. The one miss put the minute hand at the 1 (11:05).
- Wonder's earned all three points 16 times.
- Spark's checklist agreed with the eye on all 32.
- Wonder's 16 are nearly identical (spread 0.01).

## People (the export)

- **All three points.** 238 of 315 clocks (76%) earned all three points, and 70 more earned two.
- **By age group.** The share with all three points was 75, 75, 85, 84, 70 and 64% in the 20–29, 30–39, 40–49, 50–59, 60–69 and 70+ groups.
- **No clear change with age:**
  - clock points against age, rho −0.016 [−0.14, +0.10];
  - distance from typical against age, rho +0.03 [−0.08, +0.14];
  - spread, +0.003 per decade [−0.006, +0.011].
- **The MoCA total** does fall with age in this group (rho −0.21 [−0.31, −0.10]).
- **Hands in the averages.** In every age group's average, the hands at 11 and 2 come through.
  - Ink toward the 11 is 5 to 16 times that of a typical direction, and toward the 2 it is 7 to 32 times.
  - Toward the 10, the 10:10 slip, it is only 1.4 to 6 times.
  - The older groups' averages look busier at the rim and in the ring of numbers.
- **The story: people keep the Form of a clock for life.**
- **The distance measure is shape only.** Among the adults, distance from the typical clock did not follow clock points: rho −0.05 [−0.16, +0.06]. Clocks with three points and with two sit equally far (0.111 and 0.111). The page never presents distance as a measure of how good a clock is.

## Damage (from `/plato/damage`)

The page shows SDXL's "simple clock face showing 8:45" under four kinds of step-by-step damage. Under each clock is Muse Spark's checklist score: contour, plus 12 numbers in order, plus the asked time, out of 3. That score falls with damage, from 1.40 for the intact clock to 0.06 for language noise × 1.

On the people's measure, every SDXL level is further from people's typical clock than any group of people, the intact clocks included (they are ornate). So the page doesn't match them to an age, and says so. The section is labelled "An analogy on one measure, not a diagnosis".

## The draw pad (`/draw?thing=clock`, and on the page)

- A new concept mode, `group` (`draw.GroupConcept`, `draw.score_group`).
- **What it ships** (`web/data/draw_clock.json`):
  - the people's typical-clock centroid (238 full-point clocks) and the quantiles of adults' distances to it, from the export;
  - Muse's centroid from condition A;
  - no per-person vector and no people's thumbnail.
- **How a drawing is prepared.** As the people's clocks were (`plato_clock.face_normalise`): thinned, centred on its face, the face 0.40 of a 256 px canvas, and redrawn 3 px wide.
- **What it returns:**
  - which average the drawing is closer to;
  - the two distances;
  - the two published percentiles its distance falls between, worded as shape similarity, with "This is not a test, and drawing on a screen isn't pen and paper."
- **Cost.** DINOv2 on the server only, so a visitor costs nothing.
- **Checks.**
  - Muse's own clocks, uploaded, land nearer the AI's average.
  - Quick, Draw! clocks land nearer people's.
  - A plain pad clock lands nearer people's.

## Deviations from the plan

1. **Persona ages.** The export's `stats.json` didn't exist when condition B ran, so the plan's fallback applied: 16 evenly spaced ages from 20 to 80.
2. **P4.** The export reports the share of clocks with all three points, not the hands point alone, so P4 compares all three points.
3. **The distance pipeline.** The export's README describes how its clocks were prepared but ships no code, so `plato_clock.face_normalise` reimplements it. Checked against the export's own distances for public sets, it reproduces them:

   | Set | Our distance | The export's |
   |---|---|---|
   | Muse's no-time doodles | 0.292 | 0.298 [0.264, 0.335] |
   | Quick, Draw! | 0.320 | 0.311 [0.304, 0.318] |
   | SDXL | 0.554 | 0.502 [0.464, 0.540] |

   The SDXL clocks are ornate, and its face fit is the least certain.
4. **The average images.** Muse's averages use the export's rendering: mean ink over the shared display scale 0.3629, blurred with sigma 1 px at 256 px.
5. **The damage row** shows Muse Spark's checklist only, not a distance, and is not mapped to an age. The export found every level beyond every group of people.
6. **The hands threshold.** "Clearly shorter" was set at 90% when eye scoring began, not in the plan; the stricter readings are reported above.

## Cost

$0.87, under the ledger tag `plato_clock`:

- Muse Image, 32 pictures: $0.32;
- Muse Spark, 64 checklist readings and 16 SVG drawings: $0.25;
- Muse Wonder, 16 SVG drawings: $0.30.

The cap was $2.00.

## Files

- **Code:** `metalesionlab/plato_clock.py` and `scripts/plato_clock.py`.
- **Eye scores:** `public_data/plato_clock_byeye.json`.
- **Page data:** `web/data/plato_clock.json`.
- **Draw pad's clock reference:** `web/data/draw_clock.json`.
- **Pictures:** `static/img/plato_clock/` (`abc/` holds the export's 13 group averages, re-encoded as WebP).
- **Data folder:** the AI pictures, Spark's readings and the embeddings are in `PlatosChair/clock/`, outside the repository.

Credits: clock averages from the USC Aging Brain Cohort (IRB-approved), 315 adults aged 20 to 80 and over, shown only as group averages of 20 or more. Meta Muse Image 1.0, Muse Spark 1.3, Muse Wonder 1.0 and DINOv2-base. Stable Diffusion XL base 1.0 (CreativeML OpenRAIL++-M).

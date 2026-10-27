# Plato's Forms: the Platonic clock, and Plato's bed and table

These are two follow-ups to Plato's Chair (`docs/plato.md`). Both were pre-registered in `docs/plato_forms_plan.md` (commit `8c74c18`), before any study picture was made. The web page is `/plato/forms`.

## Short answer

**The clock: 10:10 is Muse Image's default, not a limit.**
- **Without a time, Muse Image draws the advert's 10:10.** By eye, 13 of its 16 clock doodles show 10:10. The pre-registered automatic reader counted 8 of 16 (50%, 95% CI 28–72%, against 5.7% by chance, p = 9e-7) and read five more as 11:10. Those five are drawn as the 10:10 V with the hour hand a little past the 10.
- **People almost never draw 10:10:** 4 of 200 Quick, Draw! clocks (2%, CI 1–5%), which is below chance. Their favourite is the hands on the 12 and the 3 (64 of 200), and 17% draw no hands at all.
- **Asked for a time, Muse Image draws it.** None of its 72 time-asked doodles shows 10:10. The minute hand is right in 93% of them. With the hour hand too, 51% are right to within 5 minutes (CI 29–75%), and 88% if the hour may be one off. The hour hand often sits a number too far: 7:30 for 6:30, 10:45 for 9:45.
- **The open model SDXL does what image models are reported to do.** It ignores the time asked for: 4% right. It falls back on 10:10 for 19% of its time-asked doodles and 40% of its time-asked photos.

**The bed and the table: Plato's own examples are as "Platonic" for Muse as the chair.**
- **Table.** Muse Image's 16 tables are almost the same four-legged table in three-quarter view. They are 61% less varied than people's tables: ratio 0.39, CI 0.33–0.45. Added to the 35 core concepts, the table ranks 10th of 36 most homogenized, right after the chair (9th).
- **Bed.** The bed is the median concept: ratio 0.47, CI 0.34–0.62, 17th of 36.
- **Prompts.** As with the chair, "any kind of bed" adds no variety. When Muse Spark names 16 kinds, Muse Image's drawings become more varied than people's: 1.5 to 1.6 times their spread.

All four bed-and-table predictions held. Three of five clock predictions held. The two that failed:
- Muse Image does not ignore the time asked for.
- SDXL's plain doodles are not clearly above chance at 10:10 (3 of 16, p = 0.06), though its photos are.

## Method

| Step | What we did |
|---|---|
| Clock prompts | **Doodle, no time:** the core doodle prompt for "a clock". **Doodle, time asked:** *"A quick simple doodle sketch of a simple clock face showing 3:00, black marker on plain white, like a 20-second drawing, no text, no shading."* **Photo:** *"A photo of a wall clock."* and *"A photo of a wall clock showing 3:00."* |
| Times asked | 1:20, 2:35, 3:00, 4:55, 5:10, 6:30, 7:50, 8:15, 9:45, 10:40, 11:05 and 12:25. Each hour appears once and each five-minute mark appears once. None is within 25 minutes of 10:10. Photos used a subset of six: 1:20, 3:00, 4:55, 6:30, 9:45 and 10:40. |
| Muse Image | Separate calls of n = 4, downscaled to 512 px. **No time:** 16 doodles, of which 12 come from the core run (same prompt) and 4 are new; 16 photos. **Time asked:** 8 doodles per time and 8 photos per photo time. |
| SDXL | `stable-diffusion-xl-base-1.0` (fp16) on a lab L40S, with the core settings: 768 px, 25 steps, Euler, guidance 5. Doodles use the core negative prompt; photos use none. Each picture has its own seed. The 16 no-time doodles are the core run's. |
| People | The 200 cached Quick, Draw! "clock" drawings: the first recognized drawings in file order. |
| Reading the time | Muse Spark 1.3 (vision, minimal reasoning) answers *"…How many hands does it have, and what time do the hour hand (the shorter one) and the minute hand (the longer one) show?…"* with JSON. It was tested before the plan on 28 clocks drawn by code: 24 known times in three styles, plus 4 with no hands. Of three readers, the best got **23 of 24 within 5 minutes**, found all 4 hand-less clocks, and called none of 22 non-10:10 clocks 10:10. That reader was then fixed. |
| About 10:10 | The read time is within ±10 minutes of 10:10, with the hands either way round (`plato_forms.is_ten_ten`). By chance, 41 of the 720 dial minutes qualify: **5.7%**. All pictures are in the denominator; those with no hands or no readable time count as not 10:10. |
| Statistics | Wilson 95% CIs; exact binomial tests against chance; Fisher's exact test between sources. For time-asked measures, a cluster bootstrap over the times asked (10,000 resamples). |
| Checks | A pre-registered blind spot check: 60 random study pictures read by eye without seeing Spark's answers. Also the pixel average of each no-time set, which needs no reading at all. |
| Bed and table | The core pipeline unchanged, with its outputs in `PlatosChair/forms/`; the 35-concept core results are untouched. **Muse Image:** 16 doodles each for "a bed" and "a table", 16 for "any kind", and 16 named kinds (Muse Spark lists them, reasoning low). **SDXL:** usual prompt, any kind and named kinds, 16 each, with seeds continuing the core scheme. **People:** 200 Quick, Draw! drawings each. **Analysis:** ink crop, DINOv2-base CLS, mean pairwise cosine distance, bootstrap CIs (2,000 AI and 500 people resamples), people subsampled to n = 16. Ranks among the 35 come from the core result files, read and not recomputed. |

Code:
- `metalesionlab/plato_forms.py`: time arithmetic, the 10:10 window, the reader parse, validation clocks, and the bed and table concepts;
- `scripts/plato_forms_{generate,sdxl,read,clock,concepts,figures,export}.py`;
- `metalesionlab/web/plato_forms_routes.py` and `pages/plato_forms.html`.

Data and figures: `PlatosChair/forms/`. Derived statistics: `public_data/plato_forms.json`.

## Findings: the Platonic clock

### No time asked

| Set | n | About 10:10, reader (95% CI) | p vs 5.7% | By eye (post hoc) | Most common read times |
|---|---|---|---|---|---|
| Muse Image, doodle | 16 | 8 = 50% (28–72%) | 9e-7 | **13 of 16** | 10:10 (7), 11:10 (5) |
| Muse Image, photo | 16 | 9 = 56% (33–77%) | 5e-8 | 9–10 of 16 | 10:10 (8) |
| SDXL, doodle | 16 | 3 = 19% (7–43%) | 0.06 | 1–2 of 16 | no time twice |
| SDXL, photo | 16 | 7 = 44% (23–67%) | 1e-5 | 5–8 of 16 | 10:10 (6) |
| People (Quick, Draw!) | 200 | 4 = 2% (1–5%) | 0.02 (below chance) | 0 of 17 readable in the spot check | 3:00 (45), 12:15 (16), 4:00 (14), 2:00 (10); no hands 33 |

- **Muse vs. people:** 50% against 2%, Fisher p = 5e-8. By eye, the gap is 81% against 2%.
- **Muse vs. SDXL (no-time doodles):** not significant by the reader (p = 0.14), but clear by eye (13 against 1–2). Most SDXL "doodles" are ornate faces with three or more hand-like lines.
- **The pixel average needs no reading.** The average of Muse Image's 16 clocks is a crisp ring of ticks with two sharp hands at 10:10. People's 200 average to a soft ring with a stroke up to the 12. SDXL's average to a gray blur. See `clock_average.png`.
- **People's Form of a clock is 3:00.** 64 of 200 have the hands on the 12 and the 3: 3:00, or 12:15 with the hands swapped. The L shape is the quickest clock to draw.

### Time asked

| Set | n | Right within 5 min (cluster CI) | Hour may be one off | Minute hand right | About 10:10 |
|---|---|---|---|---|---|
| Muse Image, doodle (10 of 12 times) | 72 | 51% (29–75%) | 88% (78–96%) | 93% | **0 of 72** |
| Muse Image, photo | 48 | 69% (54–85%) | 88% (81–94%) | 92% | 1 of 48 |
| SDXL, doodle | 96 | 4% (0–10%) | 6% | 23% | 18 = 19% (cluster CI 10–28%) |
| SDXL, photo | 48 | 2% (0–6%) | 4% | 17% | 19 = 40% (cluster CI 23–56%) |

- **Muse Image.** 10:10 drops from about half (reader) or 13 of 16 (eye) without a time to 0 of 72 with one (Fisher p = 2e-7).
  - Its errors are almost all in the hour. In the spot check, its 6:30 has the hour hand halfway between the 7 and the 8, which reads 7:30.
  - 9:45 is drawn with the hour hand past the 10, which reads 10:45.
  - 12:25 mostly has the hour hand past the 1, which reads 1:25.
  - Its photos are cleaner (median error 2.5 min). They often show a thin seconds hand, sometimes on the minute asked for.
- **SDXL** draws 10:10 as often with a time asked as without one (19% and 19% for doodles). Its photos drift to 10:10 whatever time is asked: 5 of 8 for 6:30 and 5 of 8 for 9:45 read as about 10:10.

### Predictions (pre-registered)

| # | Prediction | Result |
|---|---|---|
| C1 | Muse's no-time doodles are mostly 10:10 (≥ 50%, above chance) | **Held**, just: 8 of 16 = 50% by the reader, p = 9e-7. By eye, 13 of 16. |
| C2 | Muse often ignores the time asked (10:10 ≥ 25% and accuracy < 50%) | **Failed.** 0 of 72 at 10:10; 51% exactly right, 93% with the minute hand right. |
| C3 | SDXL no-time doodles show 10:10 above chance but less than Muse | **Failed** on the first part: 3 of 16, p = 0.06. Its photos are above chance (7 of 16, p = 1e-5), and so are its time-asked doodles (18 of 96, p = 7e-6). |
| C4 | SDXL rarely draws the time asked (< 25%) | **Held:** 4% (doodles) and 2% (photos). |
| C5 | People rarely draw 10:10 (< 15%, below Muse) | **Held:** 2%, Fisher p = 5e-8 against Muse. |

### How far to trust the reader

- **Validation.** On clocks drawn by code: 23 of 24 within 5 minutes, no invented 10:10s (0 of 22, CI 0–15%), and 4 of 4 hand-less clocks found.
- **Spot check** (pre-registered, 60 pictures, blind). I could read 45 by eye; the other 15 were mostly SDXL faces with several hands or several clocks. Spark agreed with my reading on **33 of 45 (73%)**, within 5 minutes or both "no hands". They agreed on whether a clock is about 10:10 on 43 of 45. By source:

  | Source | Agreed |
  |---|---|
  | Muse doodles | 9/15 |
  | SDXL doodles | 6/7 |
  | Muse photos | 4/5 |
  | SDXL photos | 1/1 |
  | People | 13/17 |

- **The reader's hour errors.** On Muse doodles, 5 of the 6 disagreements were the hour, one off:
  - 10:10 read as 11:10;
  - 1:20 as 2:22;
  - 10:37 as 11:35;
  - 8:15 as 7:15.

  Muse draws the hour hand between numbers, and the reader rounds it. Clocks drawn by code put the hour hand exactly, which is why validation missed this.
- **Ticks read as hands.** On people's drawings, the reader read two hand-less clocks with tick marks at 12, 3, 6 and 9 as times. So people's 17% with no hands is a lower bound.
- **Post hoc response.** I read all 64 no-time AI pictures by eye (`clock/spotcheck/byeye_no_time_sets.json`). I also report a mechanical "hour may be one off" measure (`is_ten_ten_hour_slack`; chance 13.5%). On Muse's no-time doodles it gives 13 of 16, exactly the by-eye count. These are sensitivity checks; the reader's numbers are the pre-registered ones.

**A note on visual spread.** In the core Plato's Chair analysis, the clock was one of Muse Image's *least* homogenized concepts (ratio 0.80, 34th of 35). Its doodles differ in rings, ticks and arrowheads, and people's clocks are uniform circles. DINOv2 does not see where the hands point. The time on the dial is where Muse's clock is most Platonic.

## Findings: the bed and the table

| | Bed | Table | Chair (core, for reference) |
|---|---|---|---|
| Muse Image spread (95% CI) | 0.19 (0.14–0.25) | 0.16 (0.13–0.18) | 0.13 (0.09–0.20) |
| People's spread (n = 16 subsets of 200) | 0.41 | 0.40 | 0.36 |
| Ratio, Muse ÷ people (95% CI) | **0.47 (0.34–0.62)** | **0.39 (0.33–0.45)** | 0.37 (0.24–0.55) |
| Rank among the 35 core concepts (1 = most homogenized) | 17th of 36 | 10th of 36 | 9th of 35 |
| Muse spread rank; people's spread rank | 21st; 26th | 14th; 25th | |
| Relative to between-concept distance (rank) | 0.31 (16th) | 0.28 (10th) | |
| Patch-mean embeddings: ratio | 0.40 | 0.37 | |
| Random sets of 16 people's drawings as uniform as Muse's | 0 of 200 | 0 of 200 | |
| "Any kind": × usual spread (CI) | 0.72 (0.53–1.02) | 1.31 (0.85–1.84) | 0.65 (core variety run) |
| Named kinds: × people's spread (CI) | 1.49 (1.30–1.68) | 1.65 (1.47–1.83) | 1.50 |
| SDXL usual prompt: × people's spread (CI) | 0.76 (0.65–0.83) | 1.17 (1.01–1.29) | 1.17 |
| Muse ÷ SDXL spread (CI) | 0.63 (0.44–0.86) | 0.33 (0.27–0.40) | |
| Muse pictures nearest their own human centroid (of 37) | 12 of 16 (4 nearest table) | 16 of 16 | |

- **Muse's bed** is one bed: a headboard, a pillow and a rumpled blanket on four legs, in three-quarter view.
- **Muse's table** is one table: a plain four-legged rectangle in three-quarter view, drawn 16 times.
- **People** draw beds and tables mostly as side-view outlines. In DINOv2 space, people's beds sit as often near benches, tables and books as near other beds: only 38% are nearest their own centroid.
- **SDXL** draws whole bedrooms and dining rooms.
- **Named kinds:**
  - for beds, Muse Spark listed: bunk, loft, canopy, four-poster, sleigh, waterbed, murphy, trundle, daybed, crib, hammock, air mattress, platform, sofa bed, hospital bed and racecar bed;
  - for tables: dining, coffee, bedside, picnic, ping pong, pool, drafting, folding, operating, massage, laboratory, vanity, sewing, bistro, altar and console.

  Muse Image drew each one recognizably.
- **Calls.** Pictures from the same call are no more alike than pictures from different calls (bed 0.197 against 0.192; table 0.142 against 0.162).

| # | Prediction | Result |
|---|---|---|
| B1 | Muse more uniform than people for both (CI below 1) | **Held:** 0.47 (0.34–0.62) and 0.39 (0.33–0.45). |
| B2 | The table is in the most homogenized third of the 35 (below the 12th-lowest index, 0.42) | **Held:** 0.39, 10th of 36. |
| B3 | "Any kind" adds nothing; named kinds lift spread above people's | **Held:** any-kind CIs include 1; named kinds 1.49 and 1.65. |
| B4 | SDXL varies both more than Muse | **Held:** Muse ÷ SDXL 0.63 and 0.33, CIs below 1. |

**Is Plato's own example Platonic for Muse?** Yes, about as much as the chair:
- **The table** sits right after the chair among the most homogenized third.
- **The bed** sits at the median of 35 everyday things.
- **The most Platonic things are elsewhere:** the umbrella (0.14) and the bicycle (0.18).

Plato chose well. The bed and the table come out as typical Platonic Forms for Muse, not exceptions.

## Deviations from the plan

1. **Missing asked-time doodles.** Six of the 41 Muse clock calls timed out: 24 asked-time doodles, including all 8 for 4:55 and all 8 for 11:05, and 4 each for 2:35 and 10:40. They were not re-run, because the timed-out calls may have been billed and a re-run would pass the $5 cap. Muse's time-asked doodles are therefore 72 of 96 (10 of 12 times). SDXL has all 12.
2. **Post hoc checks.** The by-eye reading of the four no-time AI sets and the "hour may be one off" measures were added after the spot check exposed the reader's hour errors. They are labelled post hoc everywhere.
3. **SDXL bed and table.** I also ran "any kind" and named kinds for SDXL, as planned extras.

## Caveats

- **The reader is a model.** It reads code-drawn clocks very well, but agrees with a careful human on only 73% of real pictures. On doodles it gets the hour wrong when the hour hand sits between numbers. The headline Muse number therefore comes with two counts: 8 of 16 by the pre-registered reader and 13 of 16 by eye. The pixel average shows 10:10 with no reading at all.
- **By-eye readings were made by the analyst (Claude).** The spot check was blind to Spark's answers. The full reading of the four no-time sets was not blind: I had seen those pictures before.
- **Small n.** There are 16 pictures per no-time set and 8 per asked time, so single-set CIs are wide. The Muse vs. people contrast is not in doubt (p = 5e-8); Muse vs. SDXL for no-time doodles is (p = 0.14 by the reader).
- **One wording per style.** Other phrasings, such as "a clock showing twenty past one" or "an analog clock", are untested.
- **Muse places the hour hand imprecisely** (by eye, in the spot check). It is not always clear whether an off-by-one hour is the model's drawing or the reader's rounding. The minute-hand accuracy (93%) does not depend on that.
- **People's clocks.** These are the first 200 drawings that Quick, Draw!'s own recognizer accepted, drawn in 20 seconds. The recognizer may favour typical clocks, and 20 seconds favours the quick L shape.
- **SDXL** used one setting (guidance 5, no refiner) and one negative prompt for doodles.
- **Bed and table** share the core caveats: style mismatch between marker doodles and mouse drawings, and DINOv2 measuring how pictures look, not what they mean.
- **Fairness to Meta.** These are defaults, what a model draws when a prompt leaves the time open. Muse Image draws a requested time; in that respect it follows the prompt better than the open SDXL model.

## Cost

My spend is **$4.92** by this experiment's conservative log (`PlatosChair/forms/spend.jsonl`), under the $5 cap. Shared ledger at the end: $43.17.

| Item | Cost |
|---|---|
| Muse Image: 236 pictures received (140 clocks, 96 beds and tables) | $2.36 |
| 6 timed-out calls (24 pictures), counted as spent in case they were billed | $0.24 |
| Muse Spark: 2 kind lists | $0.01 |
| Muse Spark: 84 reader-validation reads | $0.25 |
| Muse Spark: 528 study reads (ornate SDXL clocks cost about twice as much as doodles, because the reader reasons longer) | $2.06 |

SDXL (lab GPU) and DINOv2 (Mac) cost nothing.

## Figures

All in `PlatosChair/forms/figures/`:
- `clock_wall.png`: 16 Muse Image clocks, 16 SDXL clocks and 16 people's clocks, no time asked;
- `clock_faces.{png,svg}`: every read time as hands on one dial (the clock-face heatmap), for Muse, SDXL and people, doodles and photos;
- `clock_average.png`: pixel averages;
- `clock_asked.{png,svg}`: time asked against time drawn;
- `clock_asked_strip.png`: one Muse doodle per asked time;
- `forms_bed.png`, `forms_table.png`: five rows of 16 (Muse usual, any kind, named kinds, SDXL, people);
- `forms_rank.{png,svg}`: bed and table among the 35.

Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0, https://github.com/googlecreativelab/quickdraw-dataset. The drawings are never committed; the page shows small thumbnails with credit. SDXL: Stability AI, CreativeML OpenRAIL++-M.

# Ask it to be a crowd: does a stated age give Muse Image people's variety?

Roger asked: "Is it fair to prompt the AI to draw an image 16 times, or should we tell it to draw as if 16 different people were drawing it?"

So we told it. Each of 16 calls to Meta's Muse Image got the house doodle prompt with one stated age in front, from 20 to 80: *"Drawn by a 34-year-old: a quick simple doodle sketch of a chair, …"*. We did this for the draw pad's 10 things and for God. Pre-registered in `docs/plato_crowd_plan.md` (commit `9b40904`; pilot addendum `95c4bb4`), before any picture was made. The page is the "Ask it to be a crowd" section of `/plato`.

## Short answer

**A stated age changes nothing, like "any kind of chair".** Muse Image drew the same thing whoever it was told was drawing. The sameness is not an artefact of asking one model 16 times.

- **No added variety (H1 failed).** Over the 10 things, the spread with ages minus the spread without was **+0.001** (95% CI −0.024 to +0.027; sign-flip p = 0.44). It went up for 5 things and down for 5. The median ratio, with ages ÷ without, was **1.00**.
- **Far from people's variety (H2 prediction held).** **1 of 10** things reached people's spread with ages: the book, which already did without. Nine of 10 are still clearly below people's (CI of the ratio below 1), as before. The median ratio to people's spread was 0.40 with ages and 0.41 without.
- **No age trend (H3 null).** Younger or older ages did not move the drawings away from the usual one: mean rank correlation −0.07 (CI −0.18 to +0.05; p = 0.41). There is no U shape either (p = 0.85).
- **The chair.** The same slat-back chair in three-quarter view, 16 times: spread 0.09 with ages, 0.13 without, against 0.37 for people. The ratio, 0.69 (CI 0.46–1.11), shows no clear change.
- **God.** All 16 are a bearded man with a halo, as all 16 were with no age (labelled by eye, blind to the age).
- **So:** asking 16 times is fair to Muse Image, at least where the persona is an age. Its narrow default is sticky. What does bring out its variety is naming the kinds (`docs/plato.md`, "Can you prompt it out of the Platonic chair?"): asked for a rocking chair, a beanbag, a throne, …, it draws 1.30 times people's spread.

## Results

### Pre-registered tests

| # | Question | Result | Verdict |
|---|---|---|---|
| H1 (primary) | Does a stated age add variety? | Mean paired difference +0.001 (95% CI −0.024 to +0.027), sign-flip p = 0.44. 5 of 10 things up. Mean spread 0.157 with ages, 0.155 without; people 0.336. | **Failed** (CI includes 0) |
| H2 | Does it reach people's variety? | 1 of 10 reach people's spread (book; 1 of 10 without ages). 9 of 10 clearly below, as without. Median ratio to people 0.40 (without: 0.41). | **Prediction held** (≤ 3 of 10) |
| H3 (secondary) | Does the drawing change with stated age? | Mean within-thing Spearman rho of age against distance from the default centroid: −0.07 (CI −0.18 to +0.05), two-sided permutation p = 0.41. | **No trend** |

The plan fixed the wording for this outcome: "A stated age changes nothing, like 'any kind of chair'." The page uses it.

### Each thing

Spreads with 95% CIs. People: 200 random sets of 16 from 200 Quick, Draw! drawings. "Outside default": persona pictures further from the default centroid than any default picture is from the centroid of the others (E1).

| Thing | Default spread (n) | With ages (16) | People | With ages ÷ default | With ages ÷ people | Default ÷ people | Age rho | Outside default |
|---|---|---|---|---|---|---|---|---|
| chair | 0.13 (0.09–0.20) (16) | 0.09 (0.07–0.11) | 0.37 (0.35–0.38) | 0.69 (0.46–1.11) | 0.25 (0.20–0.31) | 0.36 (0.24–0.53) | −0.36 | 0 of 16 |
| umbrella | 0.05 (0.04–0.07) (16) | 0.11 (0.06–0.17) | 0.39 (0.38–0.40) | 1.96 (1.04–3.36) | 0.27 (0.15–0.43) | 0.14 (0.11–0.17) | −0.23 | 3 of 16 |
| bicycle | 0.06 (0.05–0.08) (12) | 0.09 (0.08–0.11) | 0.34 (0.33–0.35) | 1.49 (1.14–2.06) | 0.27 (0.23–0.32) | 0.18 (0.14–0.22) | +0.32 | 7 of 16 |
| house | 0.12 (0.10–0.14) (16) | 0.12 (0.10–0.15) | 0.30 (0.28–0.31) | 0.99 (0.75–1.30) | 0.40 (0.34–0.50) | 0.41 (0.36–0.49) | −0.12 | 0 of 16 |
| cat | 0.12 (0.10–0.14) (16) | 0.14 (0.11–0.17) | 0.30 (0.29–0.32) | 1.15 (0.88–1.51) | 0.47 (0.37–0.57) | 0.41 (0.34–0.48) | −0.25 | 4 of 16 |
| tree | 0.26 (0.23–0.28) (16) | 0.28 (0.23–0.32) | 0.35 (0.33–0.37) | 1.05 (0.88–1.26) | 0.79 (0.67–0.94) | 0.75 (0.67–0.82) | −0.03 | 7 of 16 |
| face | 0.12 (0.10–0.13) (16) | 0.10 (0.09–0.13) | 0.26 (0.25–0.28) | 0.91 (0.71–1.14) | 0.40 (0.33–0.48) | 0.44 (0.37–0.52) | −0.12 | 2 of 16 |
| boat | 0.20 (0.15–0.24) (16) | 0.15 (0.13–0.17) | 0.31 (0.30–0.33) | 0.77 (0.58–1.02) | 0.48 (0.40–0.56) | 0.63 (0.48–0.78) | +0.06 | 0 of 16 |
| cup | 0.12 (0.09–0.16) (16) | 0.12 (0.05–0.24) | 0.38 (0.37–0.39) | 1.01 (0.41–2.11) | 0.32 (0.14–0.62) | 0.32 (0.23–0.41) | +0.12 | 1 of 16 |
| book | 0.36 (0.30–0.42) (12) | 0.36 (0.33–0.39) | 0.35 (0.33–0.36) | 0.99 (0.83–1.21) | 1.03 (0.93–1.13) | 1.04 (0.86–1.23) | −0.08 | 0 of 16 |
| God | 0.24 (0.20–0.28) (16) | 0.27 (0.22–0.31) | none | 1.13 (0.89–1.43) | | | −0.04 | 1 of 16 |

- **Up, clearly, for 2 of 10:** the umbrella and the bicycle, Muse's two most uniform things. Both stay far below people (0.27 of people's spread).
  - The umbrella's rise rests on one picture: the 72-year-old's bare umbrella, with no scalloped edge.
  - Several of the bicycles face the other way, which DINOv2 counts as a difference.
- **Down, not clearly:** the chair (0.69) and the boat (0.77).
- **The cup's wide interval** comes from one picture: the 40-year-old's cup with a rounded base.

### God (exploratory)

- **By eye, blind to the age:** 16 of 16 a bearded man, 16 of 16 with a halo, so 16 of 16 both. Without ages it was also 16 of 16 (`docs/plato_ideas.md`). The prediction (at least 12 of 16) held.
- **How I labelled.** The 16 pictures went on a contact sheet in shuffled order, numbered, with no ages. I labelled them with the invisible Forms' God options plus halo yes/no, and saved the labels (SHA-256 `9873fc39…2edbc`) before opening the number-to-file key. Muse Glimmer on Axon was busy, so there is no second labeller.
- **What differs:** the hair (curly in some), the halo (a ring above the head, a disc behind it, rays, dashes), and once a hooded cloak. One figure, the 36-year-old's, holds its arms out; the rest are busts.
- **Spread:** 0.27 (0.22–0.31) with ages against 0.24 (0.20–0.28) without; difference +0.03 (CI −0.03 to +0.09). No age trend: rho −0.04.

### Other exploratory measures

| # | Measure | Result |
|---|---|---|
| E1 | Persona pictures outside the default's range | 0 of 16 for chair, house, boat and book; 1–4 for cup, face, umbrella and cat; 7 for bicycle and tree. Tree's default is already loose (spread 0.26). |
| E2 | A U shape (distance against \|age − 50\|) | Mean rho −0.02 (CI −0.11 to +0.09), p = 0.85. None. |
| E3 | What changes, by eye | Nothing about which object. Every thing keeps its default kind and view: the slat-back chair, the scalloped umbrella, the side-view bicycle, the gabled house with a chimney, the sitting cartoon cat, the scribble-crowned tree, the round smiling face, the triangle-sail boat with a pennant, the mug, and open or closed books. Only the line (heavier or sketchier) and small details vary. No picture shows the drawer, a written age or any text. |
| E4 | H1 with patch-mean embeddings | +0.002 (CI −0.016 to +0.020); 6 of 10 up. The same null. |
| E5 | Pictures nearest their own people's centroid, of 35 | Unchanged: 100% for 8 things with and without ages; tree 56% (default 63%); book 94% (92%). |

## Method

| Step | What we did |
|---|---|
| Concepts | The draw pad's 10 things (chair, umbrella, bicycle, house, cat, tree, face, boat, cup, book) and God. |
| Ages | 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80: the same 16 for every concept. Picture *i* has age *i*. |
| Prompt | The first run's doodle prompt (`plato.STYLES["doodle"]`), word for word, after an age, with its first letter lowercased: *"Drawn by a 34-year-old: a quick simple doodle sketch of a chair, black marker on plain white, like a 20-second drawing, no text, no shading."* No other trait. I checked each concept's base prompt against its default set's `meta.json`. |
| Pictures | `muse-image-1.0`, one call of n = 1 per picture (16 calls per concept, 176 in all), downscaled to 512 px. The default sets are the first run's (calls of n = 4; 12 pictures for bicycle and book). Pilot: 2 pictures, not analysed. No call was refused, cut short or timed out. |
| Spread | The house pipeline: ink crop with paper flattening, DINOv2-base CLS (`facebook/dinov2-base`), mean pairwise cosine distance, 2,000 bootstrap resamples of pictures. Re-embedding four default chairs reproduced the cached vectors (cosine 1.000). People: 200 random sets of 16 from 200 Quick, Draw! drawings, with a 500-resample bootstrap CI over drawings. |
| Primary test | D = the mean over the 10 things of (persona spread − default spread), paired by thing. The CI comes from a two-level bootstrap (10,000): resample the things, and take one draw from each drawn thing's persona and default bootstraps. Also a one-sided sign-flip permutation p. |
| Age trend | Each persona picture's cosine distance from the default centroid (the unit mean of the default doodles). Spearman's rho with age within each thing; the mean over things, with a two-sided permutation p (ages shuffled within things, 10,000) and a CI from resampling things. |

Code: `metalesionlab/plato_crowd.py`; `scripts/plato_crowd_generate.py`, `plato_crowd_analyze.py`, `plato_crowd_sheets.py` and `plato_crowd_web_export.py`.

## Deviations from the plan

- **None in the measures or tests.**
- **A trial analysis on part of the data.** While the run was still going, I ran the analysis script once on the first five things to check that it worked. Nothing in the plan's measures changed afterwards. I added one line so that every run re-checks the embedder.
- **People's chair spread is 0.37 here and 0.36 on the page's first screen.** Both are means of 200 random sets of 16 from the same 200 drawings, drawn with different random seeds.

## Caveats

- **One trait, one wording.** Age only, in one phrasing. Other traits (a child, an architect, someone from another country) or "draw it as 16 different people would" are untested. Ages 20–80 are all adults, so a child's age might do more.
- **DINOv2 sees style.** Spread counts how a thing is drawn as well as which thing. Here both stayed put (E3).
- **Small n.** 16 pictures per concept and 10 things for the paired test. Single pictures move the umbrella's and the cup's numbers.
- **God is AI only.** There are no people's drawings of God to compare with, and the labels are one analyst's, made by eye.
- **The prompt is still in English and still asks for a "20-second" doodle.** The persona is the only change.

## Spend

- **This task:** 178 pictures (176 main, 2 pilot), **$4.63** at the conservative $0.026 a picture used as the cap's unit, under the $5 cap. The shared ledger books $0.01 a picture: **$1.78**.
- **The shared ledger** (`runs/costs.jsonl`) was $64.30 when I started and $66.88 when I finished. Other agents were making calls at the same time.
- DINOv2 ran on the Mac, for free. No Muse Spark or Glimmer calls.

## Files

| File | What |
|---|---|
| `docs/plato_crowd_plan.md` | the pre-registration and the pilot addendum |
| `metalesionlab/web/data/plato_crowd.json` | statistics for `/plato`, and God's result for `/plato/ideas` to show later |
| `metalesionlab/web/static/img/draw/chair_crowd_muse.webp`, `god_crowd_muse.webp` | the 16 persona doodles as sprites in the draw pad's format (112 px cells, 8 columns) |
| `PlatosChair/crowd/` (outside the repository) | pictures, `calls.jsonl`, `spend.jsonl`, embeddings, `results.json`, contact sheets, and God's labels (`labels_by_eye_blind.json`, `labels_by_eye.json`) |

AI drawings: Meta Muse Image 1.0. Similarity: Meta DINOv2. People's drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0, <https://github.com/googlecreativelab/quickdraw-dataset>. No people's drawings are committed.

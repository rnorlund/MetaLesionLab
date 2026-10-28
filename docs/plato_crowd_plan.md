# Ask it to be a crowd: pre-registration

Written on Oct 28, 2026, and committed before any picture for this experiment was made, including the pilot. Results will go in `docs/plato_crowd.md`. Any change to this plan will be listed there as a deviation.

**The question.** Roger asked: "Is it fair to prompt the AI to draw an image 16 times, or should we tell it to draw as if 16 different people were drawing it?"

Asked 16 times for "a quick simple doodle sketch of a chair", Meta's Muse Image draws nearly the same chair: spread 0.13, against 0.36 for 16 people's Quick, Draw! chairs. Every API call is independent, so the 16 drawings are like 16 strangers who share one mind. Real people differ. Here each call says who is drawing, by age only, and we ask:
1. Does a stated age give Muse Image more variety than the plain prompt?
2. Does it reach people's variety, or does the sameness survive?
3. Does the drawing change with the stated age?
4. For God: does the bearded man with a halo survive?

Code: `metalesionlab/plato_crowd.py` (this commit) and `scripts/plato_crowd_*.py`. Data: `PlatosChair/crowd/`, outside the repository. `core/` and `ideas/` are only read.

**What I had seen before writing this.**
- The core results (`docs/plato.md`): Muse's default spreads and people's spreads for the 10 pad things (table below).
- "Any kind of chair" changed nothing (0.96 times the usual spread). Named kinds gave 1.30 times people's spread.
- God (`docs/plato_ideas.md`): 16 of 16 default drawings are a bearded man with a halo; spread 0.24 (0.20–0.28).
- No persona picture. The pilot comes after this commit.

| Thing | Default spread (n) | People's spread (n = 16 subsets of 200) |
|---|---|---|
| chair | 0.13 (16) | 0.36 |
| umbrella | 0.06 (16) | 0.39 |
| bicycle | 0.06 (12) | 0.34 |
| house | 0.12 (16) | 0.30 |
| cat | 0.12 (16) | 0.30 |
| tree | 0.26 (16) | 0.35 |
| face | 0.12 (16) | 0.26 |
| boat (sailboat) | 0.20 (16) | 0.31 |
| cup | 0.12 (16) | 0.38 |
| book | 0.36 (12) | 0.35 |

By default, 1 of 10 things reaches people's spread (the book).

## Concepts: 11

- **The draw pad's 10 things:** chair, umbrella, bicycle, house, cat, tree, face, boat (Quick, Draw!'s "sailboat"), cup and book.
- **God,** from the invisible Forms. There are no people's drawings of God to compare with, so God is exploratory.

## Pictures

- **Ages.** 16 adult ages, evenly spaced from 20 to 80: **20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80**. The same 16 for every concept: picture *i* of every concept has age *i*.
- **Prompt.** The first run's prompt, word for word, after an age prefix. The first letter is lowercased after the colon. For example:
  - *"Drawn by a 34-year-old: a quick simple doodle sketch of a chair, black marker on plain white, like a 20-second drawing, no text, no shading."*
  - *"Drawn by an 80-year-old: a quick simple doodle sketch of God, black marker on plain white, ..."*
  - The noun phrase is the first run's: "a chair", "an umbrella", "a sailboat", "God" and so on (`plato.prompt_for`, `plato_ideas.prompt_for`). The test suite checks the template against `plato.STYLES["doodle"]`, and I checked it against every default set's `meta.json`.
  - No other trait: no profession, gender, health or skill.
- **Settings.** The first run's, except the batch.
  - `muse-image-1.0`, no size or seed (none exists), each picture downscaled to 512 px.
  - **One call of n = 1 per picture: 16 calls per concept.** Each picture has its own prompt, so calls of n = 4 are impossible. The core run found pictures from the same call no more alike than pictures from different calls (0.185 against 0.185), so the batch size should not matter. The named-kinds run also used n = 1.
  - Drawing order: chair, God, then umbrella, bicycle, house, cat, tree, face, boat, cup, book.
- **Refusals and failures.**
  - A refused call (a 4xx) is recorded in `calls.jsonl` and tried again, at most 3 times in all.
  - Network errors are retried with backoff and are not refusals.
  - A timed-out call keeps its reservation; it is retried only if the cap still allows.
  - A concept with at least 12 of its 16 pictures is analysed with what it has, and the missing ages are reported. With fewer than 12, it is reported and left out of the tests.
- **Pilot.** At most 2 pictures, before the main run: the chair at 80 and God at 20. It checks that the prefix does not make Muse draw the person, write the age, or refuse. The pilot pictures are kept in `pilot/` and not analysed. If the pilot shows a problem, I will say so in an addendum here before the main run.
- **Money.**
  - **Hard cap: $5** for the task, counted at the conservative $0.026 a picture used by the invisible Forms. The pilot is 2 pictures ($0.05) and the main run 176 ($4.58), $4.63 in all. The shared ledger books $0.01 a picture: $1.78.
  - Every call goes through `MetaAPI`, so the shared ledger (`runs/costs.jsonl`) records it.
  - No paid call once the shared ledger reaches $72.

## Measures

The house pipeline, unchanged.
- **Embedding.** Each picture is ink-cropped with paper flattening (`plato.ink_crop`) and embedded with the DINOv2-base CLS token (`facebook/dinov2-base`). The preparation string must match the cached embeddings' (`PREP`); before the analysis, I re-embed a few default pictures and check they match the cache.
- **Spread.** The mean pairwise cosine distance in a set. Its 95% CI comes from 2,000 bootstrap resamples of pictures (`plato.bootstrap_spread`).
- **Default spread.** From the cached embeddings of the first-run doodles: 16 per thing, 12 for bicycle and book, and God's 16. Mean pairwise distance does not depend on n.
- **People's spread.** From the cached embeddings of 200 Quick, Draw! drawings per thing: the mean spread of 200 random sets of 16, with a 500-resample bootstrap CI over drawings (`scripts/plato_analyze.py`'s `concept_stats`).
- **Ratios.** Persona ÷ default and persona ÷ people, each with a CI from independent bootstraps of the two sets.

## Hypotheses

| # | Question | Statistic | Prediction | Passes if |
|---|---|---|---|---|
| **H1** (primary) | Does a stated age add variety? | D = the mean over the 10 things of (persona spread − default spread), paired by thing. 95% CI from a two-level bootstrap (10,000 resamples): resample the 10 things, and for each drawn thing take one draw from its persona and one from its default picture-level bootstrap. Also a one-sided sign-flip permutation p over things. | D > 0, a small effect: median persona ÷ default ratio 1.1–1.6. | The CI lies entirely above 0. |
| **H2** | Does it reach people's variety? | The number of things, of 10, whose persona spread is at least people's spread (point estimates). Also: how many have a persona ÷ people CI entirely below 1, and the median persona ÷ people ratio (default: 0.41). | The sameness survives: at most 3 of 10 reach people's spread. | It is reported as a count; the prediction holds if 3 or fewer. |
| **H3** (secondary) | Does the drawing change with stated age? | Each persona picture's cosine distance from its thing's **default centroid** (the unit mean of the default doodles' unit vectors). Within each thing, Spearman's rho between age and distance (16 pictures). The statistic is the mean rho over the 10 things; two-sided permutation p from shuffling ages within each thing (10,000); 95% CI from resampling things. | No direction predicted. | p < 0.05 means the distance changes with age. |

**How the answer will be worded,** fixed now:
- **H1 passes and at least 6 of 10 things reach people's spread:** "The AI has a default, not a limit. Told to be 16 different people, it draws like 16 different people." The page and the write-up lead with this.
- **H1 passes and 5 or fewer reach people's spread:** "A stated age adds some variety, but not people's. The sameness mostly survives."
- **H1 fails:** "A stated age changes nothing, like 'any kind of chair'."

## God (exploratory)

- **Emblems, by eye.** Muse Glimmer on Axon is busy, so I label all 16 God pictures by eye. I label them from a contact sheet in shuffled order with no ages shown, so the labels are blind to the stated age. The options are the invisible Forms' God options (`plato_ideas.IDEAS`): a man with a beard; a human figure without a beard; light with no figure; clouds or sky with no figure; an eye; a hand or hands; a symbol of one particular religion; something else; can't tell. For each picture I also record whether it has a halo.
- **Compared with the default:** 16 of 16 bearded men, 16 of 16 with a halo (by eye, `docs/plato_ideas.md`).
- **Prediction:** the bearded man with a halo survives in at least 12 of 16.
- **Spread:** God's persona spread against its default spread (0.24), with the CI of the difference and the ratio. No people's number.
- **Age:** God's own Spearman rho of age against distance from its default centroid.

## Other exploratory measures (no claims of significance)

- **E1. Outside the default.** For each thing, how many persona pictures sit further from the default centroid than every default picture does from the centroid of the others (its leave-one-out distance).
- **E2. A U shape?** The H3 statistic with |age − 50| in place of age.
- **E3. What changes, by eye.** Does a persona change which object is drawn (another kind of chair) or only how (line style, detail)? Does any picture show the drawer, a written age or other text?
- **E4. Patch-mean embeddings.** H1 again with the mean patch token.
- **E5. Recognisability.** The share of persona pictures whose nearest people's centroid, of the 35 core things, is their own thing (default: 85% over the 35; reported for these 10).

## What this cannot show

- **One persona trait, one wording.** Age only, in one phrasing. A result for age says nothing yet about other traits or about "draw it as 16 different people would".
- **DINOv2 sees style.** Spread counts how a thing is drawn as well as which thing. E3 says which.
- **Small n.** 16 pictures per concept and 10 things for the paired test.
- **No people's God.** God's result is the AI against the AI.

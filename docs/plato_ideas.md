# The invisible Forms

Plato's highest Forms weren't chairs. They were Beauty, Justice and the Good. In *Republic* X, God makes the one true bed, the carpenter copies it, and the painter copies the copy. Plato's Chair (`docs/plato.md`) casts the image model as the painter. Here we ask the painter to draw what no one has ever seen.

We asked Meta's Muse Image for God and 10 other abstract ideas, 16 doodles each, with the chair's prompt and settings. Pre-registered in `docs/plato_ideas_plan.md` (commit `10395df`). The page is `/plato/ideas`; the draw pad has the ideas as a second row of things to draw, "Draw the invisible".

## Short answer

- **God.** Muse Image drew the same figure in **all 16** drawings: a bearded man with long hair, a robe and a halo.
  - Muse Glimmer and our check by eye agree on all 16.
  - No call was refused.
- **Most ideas come out as one stock emblem.**
  - **Pre-registered H1 passed.** For **10 of 11** ideas, one emblem filled at least half of the 16 drawings (we predicted at least 7). Truth is the exception.
  - **Every time** (16 of 16): love is a heart, death a hooded figure with a scythe, beauty a young woman's face with flowers in her hair. And God, above.
  - The median idea's top emblem is in 81% of its drawings (95% CI 63–100%).
- **We guessed the wrong emblems.**
  - **Pre-registered H2 failed.** The top emblem was the one we predicted for **5 of 11** ideas; we needed 6. By eye it was 6 of 11.
  - The misses: death as a hooded reaper, not a skull; beauty as a woman's face, not a flower; the Good as a thumbs-up, not a sun; justice as a blindfolded figure holding scales, rather than scales alone; truth as scales, not an eye; and (Glimmer only) freedom as broken chains, not a bird.
- **Ideas are not clearly more spread out than things.**
  - **Pre-registered H3 failed.** The median idea's spread is **0.23** (95% CI 0.19–0.31). Across the Atlas's 135 everyday things it is **0.20** (CI 0.18–0.22).
  - The difference, +0.03, has a CI of −0.01 to +0.11 (one-sided permutation p = 0.16).
  - Against the draw pad's 10 things, which are among Muse's most uniform (median 0.12), ideas are more spread out: +0.10, CI +0.02 to +0.19.
- **The range is wide.**
  - Love (0.12) is about as uniform as Muse's chair (0.13).
  - Truth (0.53) and freedom (0.43) are more spread out than any of the 135 things. Freedom only just: binoculars, the most spread-out thing, is 0.43 too.
  - Across ideas, the more one emblem dominates, the less spread out the drawings are (rank correlation −0.65, CI −0.92 to −0.05; exploratory).
- **AI only.** Google's Quick, Draw! has no category for these ideas, and we found no open collection of people's quick doodles of them. Every comparison is the AI's ideas against the AI's things.

## What we asked, and why these ideas

| Group | Ideas | Why |
|---|---|---|
| God | God | *Republic* X's maker of the one true bed. Asked for as "God", nothing more. No prompt or label names any religion or its figures. |
| Plato's own highest Forms | beauty, justice, the Good | The Forms Plato cared most about. "The Good" is written as his translators write it. |
| Ideas everyone lives with | love, time, death, the soul, freedom, happiness, truth | Common words a visitor could draw in 20 seconds, with a range of expected emblems: some look obvious (love), some don't (truth). |

**Left out.**
- *Infinity*: its stock emblem is a written sign, ∞, and the prompt says "no text".
- *"An idea"*: a light bulb is a cartoon convention for the word, not one of Plato's Forms.
- *A twelfth idea*: the $5 budget, counted at $0.026 a picture, fits 11 ideas at 16 pictures plus the pilot, with a little room for retries. It does not fit 12.

## Method

| Step | What we did |
|---|---|
| Pilot | Before the plan, one picture each of God and justice with the exact prompt. Neither was refused. It changed one emblem option: "an old man with a beard" became "a man with a beard", since the pilot's figure was bearded but not clearly old. The pilot pictures are not analysed. |
| Pictures | `muse-image-1.0`. The chair's prompt, word for word (`plato.STYLES["doodle"]`): *"A quick simple doodle sketch of God, black marker on plain white, like a 20-second drawing, no text, no shading."* The phrase is the bare idea. 16 per idea in 4 separate calls of n = 4, each picture downscaled to 512 px: the concrete things' first-run settings. |
| Refusals | A 4xx from the API is recorded in `calls.jsonl` and retried, at most 3 attempts in all. Network errors are retried and are not refusals. |
| Spread | Ink crop with paper flattening, then the DINOv2-base CLS token (`facebook/dinov2-base`), the house `PREP`. Spread is the mean pairwise cosine distance in a set; its CI comes from 2,000 bootstrap resamples of pictures. The comparison sets are Muse's first-run doodles of the Atlas's 135 things (`docs/plato_atlas.md`) and of the draw pad's 10, embedded the same way. Medians get two-level bootstrap CIs (5,000 resamples): concepts are resampled, and each drawn concept contributes one draw from its own picture-level bootstrap. The same scheme gives the CI of the difference in medians. |
| Emblems | Muse Glimmer 30B (FP8, one L40S on axon-server01, 4 minutes). Each picture is ink-cropped to 448 px and asked one multiple-choice question: the idea's 5–8 emblem options, then "something else" and "can't tell". The answer is read from the letter logits with the reasoning channel skipped. Each picture is asked twice, with the options forward and reversed; the probabilities are averaged (`scripts/plato_kinds_label.py`'s method). A second, free-text pass names the main symbol in at most five words. It is used only to name "something else" pictures. |
| Concentration | The share of all 16 pictures that show the most common listed emblem. "Something else" and "can't tell" count in the denominator but are never the top emblem. The CI comes from 2,000 bootstrap resamples of pictures. |
| Label check | Before Glimmer saw any main-run picture, I labeled all 176 by eye from numbered contact sheets, with the same options. The file's SHA-256 was committed first (`a35000f`). |

Code: `metalesionlab/plato_ideas.py`; `scripts/plato_ideas_generate.py`, `plato_ideas_label.py`, `plato_ideas_analyze.py` and `plato_ideas_web_export.py`. Data lives in `PlatosChair/ideas/`, outside the repository. Committed: statistics only (`public_data/plato_ideas.json`), the page's data, and small WebP sprites of Muse's drawings.

## Results

### Pre-registered tests

| # | Prediction | Result | Verdict |
|---|---|---|---|
| H1 | At least 7 of 11 ideas have one emblem in at least 8 of 16 drawings | **10 of 11**; median concentration 0.81 (CI 0.63–1.00). By eye: 11 of 11 | **Confirmed** |
| H2 | The top emblem is the predicted one for at least 6 of 11 | **5 of 11** (God, love, time, the soul, happiness). By eye: 6 of 11 (adds freedom) | **Failed** (on the pre-registered labels) |
| H3 | The median idea is more spread out than the median Atlas thing (CI of the difference above 0) | 0.23 vs 0.20; difference +0.03 (CI −0.01 to +0.11), p = 0.16 | **Failed** |
| H3, secondary | The same against the draw pad's 10 things | 0.23 vs 0.12; difference +0.10 (CI +0.02 to +0.19), p = 0.017 | Higher |

The guessed sizes: we expected a median concentration of 0.6–0.8 (it was 0.81) and a median idea spread of 0.25–0.35 (it was 0.23).

### Each idea

Glimmer's labels; by eye where it differs. Spread with its 95% CI.

| Idea | Top emblem (Glimmer) | Share (95% CI) | Other labels | By eye | Agree | Spread (95% CI) |
|---|---|---|---|---|---|---|
| God | a man with a beard | 16/16 (1.00) | none | same | 100% | 0.24 (0.20–0.28) |
| love | a heart | 16/16 (1.00) | none | same | 100% | 0.12 (0.10–0.14) |
| death | a hooded figure with a scythe | 16/16 (1.00) | none | same | 100% | 0.23 (0.20–0.25) |
| beauty | a woman's face | 16/16 (1.00) | none | same | 100% | 0.15 (0.13–0.18) |
| time | a clock | 15/16 (0.81–1.00) | hourglass 1 | same | 100% | 0.21 (0.16–0.26) |
| happiness | a smiling face | 13/16 (0.62–1.00) | joyful person 2, sun 1 | same | 100% | 0.20 (0.17–0.23) |
| the Good | a thumbs-up | 12/16 (0.56–0.94) | smiling face 4 | thumbs-up 12, smiling face 3, sun 1 | 94% | 0.29 (0.23–0.36) |
| freedom | broken chains | 12/16 (0.50–0.94) | bird 3, bird and cage 1 | **bird 12**, broken chains 3, bird and cage 1 | 44% | 0.43 (0.38–0.49) |
| justice | a blindfolded figure with scales | 9/16 (0.50–0.81) | scales 7 | figure 10, scales 6 | 94% | 0.21 (0.18–0.24) |
| the soul | a ghostly figure | 9/16 (0.31–0.81) | flame 1, swirl 1, something else 2, can't tell 3 | ghostly figure 14, swirl 2 | 62% | 0.29 (0.25–0.33) |
| truth | a pair of scales | 7/16 (0.31–0.69) | eye 5, light 2, magnifying glass 1, mirror 1 | scales 9, light 3, eye 2, mirror 2 | 75% | 0.53 (0.41–0.61) |

**What the drawings look like (by eye).**
- **God:** a bust of a bearded man with long hair, a robe and a halo, 16 times. Rays or sparkles sometimes surround the halo. In one picture he raises two fingers; in one he waves.
- **Love:** a big heart, alone or with small hearts, stars and flowers; an arrow through it twice.
- **Death:** a hooded figure with a skull face and a scythe, 16 times, sometimes with crossbones.
- **Beauty:** a young woman's face, eyes mostly closed, flowers in long wavy hair, 16 times.
- **Time:** a collage in all 16. A clock and an hourglass appear in every picture, often with a stopwatch, circular arrows or a spiral.
- **Justice:** scales and a blindfold in all 16. In 10 a blindfolded woman holds them; in 6 the blindfold is tied to the scales' post.
- **The Good:** a thumbs-up in all 16, often with a smiley or a halo.
- **The soul:** wispy ghost-like figures, most with a small smiling face.
- **Freedom:** a bird flying away from broken chains in all 16; one adds an open cage.
- **Happiness:** smiley faces, often among suns, hearts and flowers.
- **Truth:** the most varied. Scales (in 10 of 16 somewhere), an eye with rays (in 9), a flame, a bulb, a torch, a mirror.

**One main symbol hides company.** The multiple choice asks for one main symbol, so it undercounts emblems that always come together. By eye, beyond the main symbol:
- time shows a clock and an hourglass in 16 of 16;
- justice shows scales and a blindfold in 16 of 16;
- freedom shows a bird and broken chains in 16 of 16;
- the Good shows a thumbs-up in 16 of 16.

These counts are exploratory; the addendum to the plan recorded them before Glimmer ran.

### Refusals

**None.** 44 main-run calls (176 pictures) and 2 pilot calls: no refusal, no short call, no timeout. That includes all 4 calls for God. No picture contains written words (E5).

### The label check

- **Agreement:** Glimmer and our eye agree on **88%** of the 176 drawings (155), Cohen's kappa **0.87**.
- **Top emblem:** the same for **10 of 11** ideas.
- **Below the plan's 70% bar,** so both are reported:
  - **Freedom (44%).** Glimmer's multiple choice leaned to "broken chains" at about p = 0.5; its own free-text names said "Bird breaking chain" for most. Both are in every picture; which is "main" is a judgment call.
  - **The soul (62%).** Glimmer read several of the ghostly figures as jellyfish ("Octopus jellyfish like figure") and answered "can't tell" or "something else".
- **Other disagreements:**
  - truth's eye above scales, which we read as scales and Glimmer as the eye;
  - a mirror that Glimmer read as a magnifying glass;
  - one justice figure;
  - one collage for the Good.
- **Glimmer's answering:** its two option orders agreed on 50–100% of pictures per idea (lowest for freedom). Its letter mass was 0.83–0.95.

### Exploratory

| # | Question | Result |
|---|---|---|
| E1 | Concentration vs spread, across 11 ideas | rho **−0.65** (95% CI −0.92 to −0.05), p = 0.04 |
| E2 | God's human-like share (a human figure, bearded or not, or hands) | **16 of 16** (Glimmer and eye) |
| E3 | Refusals by idea | none for any idea |
| E4 | Model-free pixel spread | ideas' median 0.35 vs things' 0.21; 9 of 11 ideas above the things' median. Pixels say ideas vary more; DINOv2 says not clearly. Muse's ideas are collages more often than its things, and pixels count every extra symbol; DINOv2 counts style and arrangement as well. |
| E5 | Pictures with written words | 0 of 176 |

### God and how people picture God (context, not a comparison)

This experiment asks how an AI pictures God and how people have. It makes no claim about God or any faith.

**The Lausanne study.** The University of Lausanne's *Drawings of gods* project studies children's drawings of god, and we cite one chapter. Brandt, Dandarova-Robert, Dessart, Muthert & Schaap-Jonker (2023), "Integrative Model of Children's Representations of God in Drawings", in *When Children Draw Gods* (Springer, open access), ch. 2, <https://doi.org/10.1007/978-3-030-94429-2_2>. We read its full text. It reports:
- "the overall percentage of anthropomorphic figures in their Swiss sample was 87.6%", in Dessart and Brandt's study of 532 Swiss participants aged 5–17;
- a decrease, "between the ages of 6 and 16, in the proportion of god drawings depicting anthropomorphic figures", in Western and non-Western contexts, including Japan and Buryatia;
- children marking a human-based figure as more than human, for example with wings or "aura or halo", or by placing it on a cloud or in the sky. Of 390 human-based figures in the Swiss sample, "nearly 70%" used at least one such strategy, and their use increased with age.

**Muse beside it.** Muse drew a human figure in 16 of 16 drawings, and gave it a halo in 16 of 16.

**Why it is not a comparison.** Those are children's colour drawings made with time to think; these are an AI's 20-second doodle prompts. We cite their group-level findings and use none of their pictures.

## The draw pad: AI-only scoring

The ideas sit on the pad (`/draw?thing=god`) after the 10 things, under "Draw the invisible". The landing page keeps the chair and adds one line: "Or draw something no one has seen: God, love, time…".

**What a drawing of an idea gets.** DINOv2 runs on the server's CPU; there is no API call per drawing.
- **Its distance from Muse's idea:** the mean of Muse's 16 unit vectors.
- **How many of Muse's own drawings sit closer to it:** each measured by its leave-one-out distance. The page says, for example, "further from Muse's idea of God than 14 of its 16 drawings".
- **The closest of Muse's drawings,** with its emblem label, precomputed by Glimmer: "Yours is closest to Muse's #8: a bearded man."
- **The reveal strip** of Muse's 16, and the idea's emblem bars.

**No people's number.** The server returns only AI fields for an idea (`draw.AI_ONLY_FIELDS`), and the tests check it. The page hides the people's cards, the map and the Socrates link for ideas.

**Checked with real strokes.** A heart drawn for love lands 0.29 from Muse's love, and its nearest Muse drawing is a heart. A haloed stick figure drawn for God lands 0.45 away, and its nearest is a bearded man. Both sit further out than all 16 of Muse's own. As with the chair, DINOv2 also sees the style gap between a pad doodle and a marker sketch, so most pad drawings land outside Muse's 16. The page says so.

## Deviations from the plan

- **Co-occurrence.** The by-eye counts of emblems shown anywhere ("one main symbol hides company") were added after I saw the pictures, but before Glimmer ran. They are recorded in the plan's addendum and treated as exploratory.
- **Nothing else changed.** The tests, measures and options are as committed. Where agreement fell below 70% (freedom, the soul), the by-eye results are reported beside Glimmer's, as planned.

## Limitations

- **One prompt, one model, 16 drawings per idea.** These are Muse's defaults for a plain prompt. Asked for named kinds of chair, Muse drew far more varied chairs (`docs/plato.md`); we did not try that here.
- **The emblem lists were ours.** A "main symbol" is a judgment call when a drawing shows several. The co-occurrence counts and the by-eye labels are there to show how much that matters.
- **DINOv2 sees style.** Spread includes how a thing is drawn, not only which thing is drawn. The pixel spread disagrees with DINOv2 on whether ideas vary more than things.
- **Muse's things are not a matched baseline.** The comparison sets are the Atlas's 135 things and the pad's 10, drawn with the same prompt. They were not chosen to match the ideas in any way.
- **AI only.** There are no people's doodles of these ideas to compare with. The Lausanne figures are context from a different task.

## Spend

- **The cap.** This task's cap was $5, counted at $0.026 a picture. 178 pictures (176 main, 2 pilot) come to **$4.63** at that rate.
- **The shared ledger** (`runs/costs.jsonl`) books Muse Image at $0.01 a picture. It went from $61.22 to **$63.00** (+$1.78).
- **Free:** Glimmer (our own GPU) and DINOv2 (on the Mac). No Muse Spark calls.

## Files

| File | What |
|---|---|
| `docs/plato_ideas_plan.md` | the pre-registration and its addendum |
| `public_data/plato_ideas.json` | statistics only |
| `metalesionlab/web/data/plato_ideas.json`, `static/img/plato_ideas/*.webp` | the page's data and sprites of Muse's drawings |
| `metalesionlab/web/data/draw_ideas.json`, `data/draw/<idea>.json`, `static/img/draw/<idea>_muse.webp` | the pad's ideas, AI only |
| `PlatosChair/ideas/` (outside the repository) | pictures, `calls.jsonl`, `spend.jsonl`, embeddings, Glimmer labels, `labels_by_eye.json`, `results.json`, contact sheets, and `social/` (candidate pictures of God for posts) |

# The invisible Forms: pre-registration

Written on Oct 28, 2026, and committed before the main run: no picture of the ideas below exists except the two pilot pictures named here. Results will go in `docs/plato_ideas.md`. Any deviation from this plan will be listed there as a deviation.

**The question.** Plato's highest Forms weren't chairs. They were Beauty, Justice and the Good. In *Republic* X, God makes the one true Form of the bed, the carpenter copies it, and the painter copies the copy. Plato's Chair casts the image model as the painter. So we ask the painter to draw what no one has ever seen:
1. **Stock emblems.** Does Meta's Muse Image reduce each abstract idea to one stock emblem? We expect a heart for love, scales for justice, a clock for time, a skull for death, and a bearded man for God.
2. **Spread.** How does the spread of its drawings of ideas compare with the spread of its drawings of everyday things?

Code: `metalesionlab/plato_ideas.py` and `scripts/plato_ideas_*.py`. Data: `PlatosChair/ideas/`, outside the repository, next to `core/` and `atlas/`, which are only read.

**What I had seen before writing this.**
- The concrete results: `docs/plato.md` and `docs/plato_atlas.md`. Muse's median spread is 0.20 over the Atlas's 135 things (10th to 90th percentile 0.12–0.29), and 0.12 over the 10 draw-pad things.
- **The pilot: two pictures, one call of n = 1 each**, with the exact prompt below. *God:* a smiling bearded man in a robe, with a halo and rays around his head. *Justice:* a balance scale. Neither was refused. The pilot changed one thing. God's first emblem option was "an old man with a beard"; the pilot's figure is bearded but not clearly old, so it became "a man with a beard". The pilot pictures stay in `pilot/` and are not analysed.

## Ideas: 11

| Group | Ideas | Why |
|---|---|---|
| God | God | Republic X's maker of the one true bed. Asked for generically, as "God". No prompt or option names any religion's figures. |
| Plato's own highest Forms | beauty, justice, the Good | The Forms Plato cared most about. "The Good" is written as Plato's translators write it. |
| Ideas everyone lives with | love, time, death, the soul, freedom, happiness, truth | Common abstract words a visitor could draw in 20 seconds, with a range of expected emblems. Some emblems look obvious (love → heart), and some don't (truth). |

**Left out, with reasons.**
- **Infinity.** Its stock emblem is a written sign, ∞, so it tests the prompt's "no text" more than the idea.
- **"An idea."** Optional in the brief. A light bulb is a cartoon convention for the word, not one of Plato's Forms.
- **The budget.** It fits 11 ideas at 16 pictures each, plus the pilot, with a little room for retries (below). It does not fit 12 ideas.

## Pictures

- **Prompt.** The concrete things' prompt, word for word (`plato.STYLES["doodle"]`): *"A quick simple doodle sketch of {God}, black marker on plain white, like a 20-second drawing, no text, no shading."*
  - The phrase is the bare idea: God, beauty, justice, the Good, love, time, death, the soul, freedom, happiness, truth.
- **Settings.** The first run's, unchanged:
  - `muse-image-1.0`;
  - 16 pictures per idea, in 4 separate calls of n = 4 (there is no seed parameter);
  - each picture downscaled to 512 px.
  - Ideas are drawn in this order: God, love, death, time, justice, beauty, the Good, the soul, freedom, happiness, truth.
- **Refusals are data.**
  - A call the API refuses (a 4xx such as `content_policy_violation`) is recorded in `calls.jsonl` and tried again, at most 3 times in all.
  - A call that returns fewer pictures than asked is recorded too.
  - Network errors are retried with backoff and are not refusals.
  - We report refused attempts per idea.
  - An idea that ends with fewer than 16 pictures is analysed with what it has if that is at least 8. Otherwise it is reported as refused and left out of the spread and emblem statistics. Nothing is replaced.
- **Money.**
  - Hard cap $5 for the whole task, counted at $0.026 a picture. That is $0.05 for the pilot and $4.58 for the 176 main pictures.
  - Every call goes through `MetaAPI`, so the shared ledger records it.
  - No paid call is made once the shared ledger reaches $70.

## Measures

**1. Spread** (the house measure, unchanged).
- Each picture is ink-cropped with paper flattening (`plato.ink_crop`) and embedded with the DINOv2-base CLS token (`facebook/dinov2-base`).
- An idea's spread is the mean pairwise cosine distance among its pictures.
- Its 95% CI comes from 2,000 bootstrap resamples of pictures (`plato.bootstrap_spread`).

**2. Emblem labels** (Muse Glimmer 30B, self-hosted, free).
- Each idea has a fixed list of 5–8 emblem options, then "something else (none of the options above)" and "can't tell, or no clear symbol or figure". The options are in `plato_ideas.IDEAS` (this commit).
- Glimmer sees each ink-cropped picture at 448 px with the multiple-choice question in `plato_ideas.labeling_prompt`. Its answer is read from the letter logits, with the reasoning channel skipped (`glimmer.py`).
- As in the kinds labeling (`scripts/plato_kinds_label.py`), every picture is asked twice: once with the emblems in forward order and once reversed. The last two options stay last. The two probability vectors are averaged, and the label is the most probable option.
- A second, free-text pass ("In at most five words, what is the main symbol or figure in this drawing?") names the "something else" pictures. It is also the short label the draw pad shows for those pictures. It does not change any count.

**3. Emblem concentration.**
- The share of an idea's pictures that show its most common listed emblem.
- The denominator is all of the idea's pictures; "something else" and "can't tell" count in it but are never the top emblem. Ties go to the first in alphabetical order.
- The CI comes from 2,000 bootstrap resamples of the pictures; a resample can crown a different emblem.
- Also reported: how many listed emblems appear, and each idea's emblem counts.

**4. The label check.**
- Before running Glimmer, I label every main-run picture myself, by eye, with the same options, without seeing any Glimmer label. The labels go to `PlatosChair/ideas/labels_by_eye.json`, and the file's SHA-256 is committed to the repository before Glimmer runs.
- We report:
  - agreement (share of pictures with the same label, overall and per idea);
  - Cohen's kappa overall;
  - the top emblem by both raters.
- **The primary results use Glimmer's labels.** For any idea where agreement is below 70%, the results by eye are reported next to Glimmer's.
- If my look finds an unlisted emblem in 4 or more of an idea's pictures, I report it, and I give that idea's concentration both ways.

## Hypotheses (confirmatory)

| # | Prediction | Test | Passes if |
|---|---|---|---|
| H1 | **Muse draws most ideas as one stock emblem.** | Count the ideas whose top emblem is in at least 8 of 16 pictures (concentration ≥ 0.50). | At least 7 of the 11 ideas. |
| H2 | **The emblem is the one we expected.** God → a bearded man; love → a heart; death → a skull or skeleton; time → a clock or watch; justice → scales; beauty → a flower; the Good → a sun or light; the soul → a ghostly figure; freedom → a flying bird; happiness → a smiling face; truth → an eye. | Count the ideas whose top emblem (Glimmer) is the predicted one. | At least 6 of the 11. |
| H3 | **Ideas are more spread out than things.** An emblem can be drawn in many ways and with other things around it. A chair is just a chair. | The median spread over the 11 ideas minus Muse's median spread over the Atlas's 135 things. The 95% CI is a two-level bootstrap: resample items in each group, and take one draw from each item's own picture-level bootstrap (5,000 resamples). Also a one-sided permutation p over items. | The CI lies entirely above 0. |

**Secondary comparison for H3.** The same test against the 10 draw-pad things: chair, umbrella, bicycle, house, cat, tree, face, boat, cup and book. These are the things on the pad that the ideas will sit beside.

**Expected sizes** (guesses, not tests):
- median concentration across ideas 0.6–0.8;
- median idea spread 0.25–0.35, against 0.20 for things.

## Exploratory (no claims of significance)

- **E1.** Across ideas, concentration against spread (Spearman, bootstrap CI). Expected negative: one emblem, less spread.
- **E2. God's human-like share.** The share of God pictures showing a human figure, bearded or not, or a hand.
  - Set beside, not tested against, the Lausanne "Drawings of gods" children. In a Swiss sample of 532 children aged 5–17, 87.6% of god figures were anthropomorphic (Brandt et al. 2023, *When Children Draw Gods*, ch. 2, reporting Dessart & Brandt).
  - Those were colour drawings made with time to think, not 20-second doodles. So this is context, not a comparison.
- **E3.** Refusals by idea.
- **E4.** Ideas against things in pixels: the model-free pixel spread of the Atlas (`plato_atlas.pixel_spread`), the same comparison as H3.
- **E5. Text.** How many pictures contain written words despite "no text" (by eye, during the label check).

## No people's drawings

- Quick, Draw! has no category for any of these ideas, and we found no openly licensed set of people's drawings of abstract ideas.
- The Lausanne collection covers God only. It holds children's colour drawings under CC BY-NC-SA, not quick line doodles.
- So every comparison here is the AI's ideas against the AI's things. The page will say so plainly, and it will not show a "vs people" number for an idea.

## The draw pad (AI-only scoring)

On the pad, a visitor's drawing of an idea is scored only against Muse's 16:
- its cosine distance from Muse's prototype (the mean of Muse's unit vectors);
- how many of Muse's own pictures sit further from their leave-one-out prototype ("further from Muse's idea of God than 14 of its 16 drawings");
- the nearest of Muse's pictures and its emblem label.

The scoring uses DINOv2 only, with no API call per drawing. No number about people is computed or shown for an idea.

## Addendum, before Glimmer ran (Oct 28)

- **The main run is in.** 176 pictures; 44 calls, none refused, none short.
- **The label check by eye is done**, before any Glimmer label of a main-run picture: `PlatosChair/ideas/labels_by_eye.json`, SHA-256 `39043d3bd7f74e561b699c9c6ca39412e58ee1cf2a2a19198d9fd355014970ed`.
- **No picture contains written words** (E5).
- **I also counted, by eye, where the pictures show an emblem anywhere, not only as the main symbol.** This is exploratory. In *time*, every picture shows both a clock and an hourglass. In *justice*, scales and a blindfold appear in all 16. In *freedom*, a bird and broken chains appear in all 16. A single "main symbol" label cannot show this, so the write-up reports it beside the concentration.

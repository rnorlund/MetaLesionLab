# God under damage, and words beyond nouns: pre-registration

Written on Oct 28, 2026, and committed before the main runs. At this commit no picture below exists: no SDXL picture of any idea or word, and no Muse Image picture of the four words. There was no pilot. Results will go in `docs/plato_ideas_damage.md`. Any deviation from this plan will be listed there as a deviation, and any prediction that fails will be reported as failed.

This extends two finished experiments, without changing either:
- **The invisible Forms** (`docs/plato_ideas.md`, plan `docs/plato_ideas_plan.md`). Muse Image drew 11 abstract ideas 16 times each. God was a bearded man with long hair and a halo in 16 of 16; love a heart; death a hooded reaper.
- **The draw pad's damage strips** (`scripts/draw_damage_sdxl.py`, `scripts/draw_damage_export.py`; doses from `docs/plato_damage.md`). Stable Diffusion XL draws each of the pad's 10 things intact, then with noise in "the part that handles words" (its two text encoders) or "the part that draws" (its UNet), at five doses each.

## Two questions

1. **How does the idea of God change when the model is damaged?** Muse Image is a closed API and cannot be damaged. So, as for the concrete things, the damaged drawer is **Stable Diffusion XL** (SDXL), an open model. Its intact God need not be Muse's, and we will say what it draws. Every picture of damage on the site will be labelled as SDXL's, not Muse Image's.
2. **Beyond nouns.** Does Muse Image draw two verbs and two adjectives the way it draws things and ideas: one stock picture each?

## Part 1. The ideas under damage (SDXL)

### Pictures: the pad's pipeline, unchanged

| | |
|---|---|
| Drawer | `stabilityai/stable-diffusion-xl-base-1.0`, fp16, one lab L40S |
| Prompt | the doodle template with the phrase Muse Image was given (`plato_ideas.prompt_for`), e.g. *"A quick simple doodle sketch of God, black marker on plain white, like a 20-second drawing, no text, no shading."* |
| Settings | 768 px, 25 steps, guidance 5, the SDXL comparison's negative prompt, saved at 512 px |
| Keys | the 11 ideas (God, love, death, time, justice, beauty, the Good, the soul, freedom, happiness, truth) and the 4 words of Part 2 |
| Seeds | picture *i* of a key has seed 20261100 + 1000 × (the key's index) + *i*, in **every** condition. Index: the pad's 10 things (unchanged, 0–9), then the ideas in drawing order (10–20), then the words (21–24). |
| Pictures per condition | God 16 seeds; every other key 8 |
| Language damage ("noise in the neurons") | `text-noise` × 0.25, 0.5, 0.625, 0.75, 1.0: Gaussian noise on every MLP neuron of both text encoders, sd = dose × the neuron's sd (the damage experiment's unit statistics) |
| Drawing damage ("noise in the neurons") | `unet-noise` × 0.75, 0.825, 0.9, 1.0, 1.1: the same on every UNet feed-forward neuron |
| God only ("neurons switched off") | `text-zero` 20, 25, 27, 29, 31% and `unet-zero` 5, 10, 15, 20% of neurons off: the damage experiment's doses, for the /plato/ideas slider and a secondary test |

That is 1,552 pictures: 128 keyed seeds × 11 noise conditions, plus God's 16 seeds × 9 switched-off conditions. They cost nothing; they run on a lab GPU.

**The strip's seed (pre-registered rule).** Each idea's strip on the pad and God's slider show one seed: the intact picture closest on average to the key's other intact pictures (the DINOv2 medoid, `plato_ideas_damage.medoid`), so SDXL's most typical intact drawing. This rule is fixed before any damage picture exists. The concrete things' seeds were chosen by eye, for a clean intact picture and a visible change; ours are not chosen by how the damage looks.

### Measures

- **Severity.** Every picture is ink-cropped (`plato.ink_crop`) and embedded with DINOv2-base CLS. d_intact is the cosine distance to the intact picture with the same seed: the damage experiment's severity.
- **The emblem (Muse Glimmer 30B, FP8, our GPU).** The ideas labeling, unchanged: the key's own emblem options (`plato_ideas.options`), then "something else" and "can't tell". Each picture is ink-cropped to 448 px and asked twice, with the options forward and reversed; the probabilities are averaged. **Same emblem** = the picture's label equals its intact twin's label. It is counted only for pictures whose intact twin shows a listed emblem.
- **Yes/no questions (Glimmer, P(yes) from the answer logits).** All pictures:
  - *person:* "Does this drawing show a person or a human figure? Answer yes or no."
  - *clean:* the damage experiment's "Is this a clean, simple line drawing, with black lines on a plain white background and no color, shading or texture? Answer yes or no." It is asked on the raw picture, as there.

  God's pictures also get:
  - *beard:* "Does a person in this drawing have a beard? Answer yes or no."
  - *halo:* "Is there a halo, or a ring or glow of light, around a person's head in this drawing? Answer yes or no."

  A feature is **present** when P(yes) > 0.5.
- **A short name.** Glimmer's free-text pass, "In at most five words, what is the main symbol or figure in this drawing?", as in the ideas labeling. It names what the drawing turned into. It is used only for description.
- **God by eye.** Before reading any Glimmer answer for an SDXL picture, I code all 320 God pictures (16 seeds × 20 conditions) by eye from contact sheets for person, beard and halo. The file is `PlatosChair/ideas/damage/god_by_eye.json`, and its SHA-256 is committed before Glimmer runs.
  - **The primary analysis uses Glimmer's answers.**
  - The by-eye counts are reported beside them, with agreement per feature.
  - Where the two lead to different verdicts, both are reported.

### Predictions

| # | Prediction | Test | Supported if |
|---|---|---|---|
| D1 | **SDXL's intact God is also a human figure, but less uniformly Muse's figure.** SDXL learned God from many sources. Some are bearded old men on clouds; others show light, hands or a haloed figure. | Among God's 16 intact pictures: person, beard and halo counts | (a) person in ≥ 12 of 16; (b) beard in ≥ 8 of 16; (c) halo in ≤ 12 of 16, fewer than Muse's 16 |
| D2 | **Under language damage, God loses the emblem before the figure.** The features that make a figure "God" are attached to the word. "A person" is a broader, sturdier concept and should outlast them. | Language noise (`text-noise`): for each of person, beard and halo, the first dose at which its rate falls below half its intact rate (the damage plan's "fails first" rule). | Beard or halo fails at a lower dose than person, or person never fails while one of them does. A tie (same dose) is "not supported". Secondary: the same with `text-zero`. |
| D3 | **God drifts toward a generic person under language damage,** as the chair drifted toward people, rooms and cars. | "Generic person": person present, neither beard nor halo. Its rate at the language-noise dose where it peaks, minus intact. The same for drawing noise. | Language rise ≥ 0.25 (4 of 16 pictures), and larger than the drawing rise. |
| D4 | **Primary, across all 15 keys: language damage changes *what* is drawn more than drawing damage does.** This is the damage experiment's H1(a), for ideas. | Same emblem as the intact twin. Language minus drawing noise, change from intact, at matched severity: the damage experiment's `boot_matched_contrast`, mean over the 25th, 50th and 75th percentiles of the severity range both reach. Bootstrap over (key, seed) pictures, 4,000 resamples; by key as the robustness check. | Difference < 0, with the CI below 0 |
| D5 | **Drawing damage changes *how* it is drawn more.** This is H1(b); for chairs it held with noise (+0.04). | Glimmer's P(clean line drawing), same contrast | Difference > 0, with the CI above 0 |
| D6 | **People appear under language damage.** Ideas drawn as symbols turn into people more under language damage than under drawing damage. | Among pictures whose intact twin shows no person: the share with a person, same contrast | Difference > 0, with the CI above 0 |

**For God alone** (16 seeds), the D4 contrast is also reported. It uses "still a man with a beard" (Glimmer's emblem label), and its CI is a bootstrap over seeds. It is descriptive, not a test.

**Notes.**
- Matched severity uses each family's mean d_intact per dose, with the intact point at 0. As in `plato_damage`, outcomes are changes from intact.
- No picture is dropped.
- Pictures that DINOv2 or Glimmer cannot read are kept.
- A key's highest dose may destroy every picture; it stays in the analysis.

## Part 2. Beyond nouns: two verbs and two adjectives (Muse Image)

### The words, and why

| Word | Kind | Phrase in the prompt | Why |
|---|---|---|---|
| running | verb | "running" | An action with a stock picture. *Republic* X ends with the just and the unjust as runners in a race (613b–c). |
| thinking | verb | "thinking" | Plato's own activity, the soul "talking to itself" (*Theaetetus* 189e). Is it drawn as a pose, a brain or a bubble? |
| something fast | adjective | "something fast" | A quality with no object. The model must pick the thing. |
| something heavy | adjective | "something heavy" | The same, for a quality of weight, not of motion |

- **The phrasings fit the template.** "A quick simple doodle sketch of {phrase}" takes a noun phrase. A gerund ("running", "thinking") fills it like a bare idea ("love", "time"). An adjective needs a head noun, and "something" is the emptiest one: it names no category. "Runs" would not fit the template, and as a noun it means other things.
- **Not "quick".** The template already says "a quick simple doodle sketch". A drawing of "something quick" could not be told apart from the template's own word, and the prompt would read "a quick simple doodle sketch of something quick". "Fast" asks the same question without the confound.
- **Not chosen:**
  - *Small and big.* A doodle has no scale, so size is drawn only by comparison.
  - *Flying.* It overlaps with freedom's bird.
  - *Beautiful and good.* They would repeat the ideas beauty and the Good.

### Pictures: the ideas' run, unchanged

- **Model and template.** `muse-image-1.0`, with the doodle template word for word.
- **Pictures.** 16 per word, in 4 separate calls of n = 4. There is no seed parameter. Each picture is downscaled to 512 px.
- **Script.** `scripts/plato_ideas_generate.py --words`. The words are drawn in the table's order.
- **Refusals.** Refusals and short calls are recorded and retried as in the ideas' plan.
- **Money.**
  - Hard cap **$2** for this task, counted at $0.026 a picture. 64 pictures come to $1.66, which leaves room for 12 retried pictures.
  - Every call goes through `MetaAPI`, so the shared ledger records it.
  - No paid call is made once the shared ledger reaches $70.

### Measures (the ideas' measures, unchanged)

- **Spread.** DINOv2-base CLS of the ink-cropped picture; mean pairwise cosine distance; 2,000 bootstrap resamples of pictures.
- **Emblem labels.** Glimmer's multiple choice with each word's options, which are fixed in `plato_ideas.WORDS` at this commit:

  | Word | Options |
  |---|---|
  | running | one person running; two or more people running, or a race; an animal running; running shoes, feet or legs, with no whole figure; motion or speed lines, with no figure; a running track, a path or a finish line, with no figure |
  | thinking | a person with a hand on the chin or head, pondering; a head or a person with a thought bubble or cloud; a brain; a light bulb; question marks; gears or cogs |
  | something fast | a car or a race car; a rocket, a jet or a plane; a cheetah or another fast animal; a person running; a lightning bolt; a train; speed lines or a blur, with no clear object |
  | something heavy | a weight, a kettlebell, a dumbbell or a barbell; an anvil; a rock or a boulder; an elephant or another big animal; a box, a crate or a safe; a person lifting or carrying a heavy load |

  Each list ends with "something else" and "can't tell". Each picture is asked forward and reversed, and the free-text name is added.
- **Concentration.** The share of all 16 pictures that show the top listed emblem, with a 2,000-resample bootstrap CI.
- **By eye first.**
  - Before Glimmer sees any word's picture, I label all 64 by eye with the same options. The file is `PlatosChair/ideas/labels_by_eye_words.json`, and its SHA-256 is committed first.
  - I also count any written words in the pictures.
  - We report agreement and kappa. Where agreement is below 70%, the by-eye result is reported beside Glimmer's.

### Predictions

| # | Prediction | Supported if |
|---|---|---|
| W1 | **The stock picture is the one we expect:** running → one person running; thinking → a person pondering, hand on chin; something fast → a car or race car; something heavy → a weight (kettlebell, dumbbell, barbell) | The top emblem (Glimmer) is the predicted one for ≥ 3 of 4 |
| W2 | **Verbs are drawn as an agent in a stock pose,** so they are as concentrated as most ideas | Running and thinking each have concentration ≥ 0.50 |
| W3 | **"Something" leaves the object open,** so the adjectives vary more than the verbs | Each adjective's spread is above each verb's spread |
| W4 | **And the adjectives vary more than the ideas did** | Each adjective's spread is above the 11 ideas' median (0.23) |

**Exploratory.** For each word: the spread with its CI, set beside the ideas' and the Atlas things' distributions; text in pictures; refusals. With 4 words, nothing here is a test of verbs or adjectives in general.

**Under damage.** The four words join Part 1 as keys (8 seeds each), in D4–D6.

## On the site

1. **The draw pad.**
   - A damage strip for each idea and word, built by the pad's own export. The export adds the ideas' and words' strips beside the things' and keeps the things' strips unchanged.
   - The four words go on the pad in AI-only mode, like the ideas, in their own row: "Draw an action or a quality".
2. **/plato/ideas.**
   - A God-under-damage slider after the 16 Muse Gods, labelled as Stable Diffusion XL's, not Muse Image's.
   - A short "Beyond nouns" section.
3. **The gallery** gets a God damage strip, if one is striking and not open to a mocking reading.

**Wording about God.** It describes what is drawn ("a bearded man with long hair and a halo, as in Western religious art") and makes no claim about God or any faith. A damaged frame that could read as mocking a religious figure is not featured in the gallery or in posts, and the report says so.

## Not people

Nothing here is a test of a person, and nothing is compared with a visitor's drawing. The damage pictures are about the model only, as on the pad. The link to semantic dementia stays an analogy.

## Addendum 1, before Glimmer saw the words (Oct 28)

- **The words' Muse Image run is in.** 64 pictures in 16 calls, none refused, none short. Counted at $0.026 a picture this is $1.66; the shared ledger went from $63.24 to $63.88.
- **The label check by eye is done**, before Glimmer saw any word's picture: `PlatosChair/ideas/labels_by_eye_words.json`, SHA-256 `46114f0e43ab2ff1e0b58806a671078d19e21ace4d6757c1b49e5d31982f041b`. No picture contains written words.
- **Seen so far, before any Glimmer label or damage picture of the other ideas:** God's 16 intact SDXL pictures (the run's first condition), looked at once to check the run works. Nothing in the plan was changed after seeing them.

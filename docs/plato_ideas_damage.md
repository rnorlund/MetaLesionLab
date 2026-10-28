# God under damage, and words beyond nouns

Two extensions of **The invisible Forms** (`docs/plato_ideas.md`). Both were pre-registered in `docs/plato_ideas_damage_plan.md`: the plan at commit `3a60a4e`, and two addenda committed before Glimmer ran (`239e0ab`, `82d3874`).

1. **God and the other ideas under damage.**
   - Muse Image is a closed API and cannot be damaged. So, as for the concrete things on the draw pad, an open model draws them: **Stable Diffusion XL** (SDXL).
   - We damaged its words part or its drawing part step by step.
   - **Every damage picture here and on the site is SDXL's, not Muse Image's.**
2. **Beyond nouns.** Muse Image drew two verbs and two adjectives, 16 times each, exactly as it drew the ideas.

This is about models. It makes no claim about God or any faith, and the link to semantic dementia stays an analogy.

## Short answer

- **SDXL's intact God is not Muse's.**
  - SDXL draws dense, symmetric, icon-like line art, not a quick doodle: mostly a bearded man's face or bust, often crowned. A beard is in **10 of its 16** drawings (Muse Glimmer and our eye agree), and a halo in 3 (Glimmer) or 6 (by eye).
  - Muse drew a simple bearded figure with long hair and a halo 16 times out of 16.
- **Damage the words part, and God loses the emblem before the figure, then becomes an ordinary person.**
  - With noise in the text encoders, the beard falls below half its intact rate at the second step (×0.5) and the halo by the third (×0.625). A human figure never does.
  - At the most damage, **10 of 16** pictures show a person with neither beard nor halo (14 by eye), against 3 intact (4 by eye). The people are anime characters, people in rooms and stations, and crowds in comic panels.
  - The same seed's bearded, crowned face becomes a robed figure with a halo, then a man with glasses and headphones, then a crowded comic scene.
- **Damage the drawing part, and the same face dissolves into scribbles.** No ordinary person appears (+0 of 16; +3 by eye), and the figure and the beard fade together.
- **Across all 11 ideas and 4 words, words damage changes *what* is drawn more than drawing damage does.**
  - At equal amounts of picture change, words damage lost the intact emblem 9.5 points more often (95% CI 3.0 to 16.4).
  - It also put a person into 19.3 points more of the pictures that had none (CI 10.8 to 28.6).
  - Death's skulls become crowds, time's clocks become people, the Good's town becomes a motorbike.
  - **The "how" half failed:** drawing damage did not cost more "clean line drawing" (+0.00, CI −0.01 to +0.01).
- **Beyond nouns: the verbs came out as one stock figure each.**
  - Running was a stick figure mid-stride in 16 of 16.
  - Thinking was a person pondering under a thought bubble. Glimmer called the bubble the main symbol in 13 of 16; by eye, the pondering person was, in 14.
- **The adjectives made Muse pick a thing, and it picked few:** a rocket in 11 of 16 for "something fast", an anvil in 11 of 16 for "something heavy". Their spreads (0.46 and 0.44) are, as point estimates, above every one of the Atlas's 135 everyday things.
- **Our emblem guesses failed again:** 1 of 4 right (Glimmer), 2 by eye, with 3 needed.
- **Cost.** $1.66 at list price for 64 Muse Image pictures (ledger +$0.64). SDXL and Glimmer ran on our own GPU.

## Method

### Part 1: the ideas under damage (SDXL)

| Step | What we did |
|---|---|
| Drawer | `stabilityai/stable-diffusion-xl-base-1.0`, fp16, one L40S (axon-server01). The draw pad's pipeline, unchanged: `scripts/draw_damage_sdxl.py run --ideas`. |
| Prompt and settings | The doodle template with the phrase Muse Image was given, e.g. *"A quick simple doodle sketch of God, black marker on plain white, like a 20-second drawing, no text, no shading."* 768 px, 25 steps, guidance 5, the SDXL comparison's negative prompt, saved at 512 px. |
| Keys and seeds | The 11 ideas and the 4 words. Picture *i* of a key has seed 20261100 + 1000 × index + *i* in every condition. The index continues after the pad's 10 things, so the things' seeds and strips are unchanged. God has 16 seeds; every other key has 8. |
| Damage | Noise in every neuron of the text encoders, the **words part** (`text-noise` × 0.25, 0.5, 0.625, 0.75, 1), or of the UNet, the **drawing part** (`unet-noise` × 0.75, 0.825, 0.9, 1, 1.1). The noise sd is dose × the neuron's sd from the damage experiment's unit statistics. These are the pad strip's doses. God also got the damage experiment's "neurons switched off" doses: `text-zero` 20, 25, 27, 29, 31% and `unet-zero` 5, 10, 15, 20%. Reversible hooks; weights are never edited. |
| Pictures | 1,552: 128 keyed seeds × 11 noise conditions, plus God's 16 seeds × 9 switched-off conditions. About an hour on one GPU, $0. |
| Severity | DINOv2-base CLS of the ink-cropped picture. d_intact is the cosine distance to the same seed's intact picture. Across all keys, the words part's five doses give mean d_intact 0.28 to 0.70; the drawing part's give 0.46 to 0.81. |
| What Glimmer read | Muse Glimmer 30B (FP8, our GPU). **The emblem:** the ideas' multiple choice, unchanged, on the 448 px ink-cropped picture, forward and reversed. "Same emblem" means the intact twin's label is kept. **Yes/no answers**, a feature counting when P(yes) > 0.5: a person (all pictures); a beard and a halo (God); and the damage experiment's "clean, simple line drawing" (the raw picture). **A five-word name**, for description only. |
| God by eye | All 320 God pictures coded for person, beard and halo from contact sheets, before any Glimmer answer existed. `god_by_eye.json`; SHA-256 in the plan's addendum 2. |
| Matched severity | `plato_damage.boot_matched_contrast`. Each family's mean d_intact per dose is its severity curve. Outcomes, as changes from intact, are read at the 25th, 50th and 75th percentiles of the range both families reach. CIs: 4,000 bootstrap resamples of (key, seed) pictures, and 2,000 by key. |
| The strip's seed | Per key, the intact DINOv2 medoid (pre-registered). God's is seed 13: a bearded, crowned face. |

### Part 2: beyond nouns (Muse Image)

| Step | What we did |
|---|---|
| Words | running, thinking, something fast, something heavy. Not "quick": the template already says "a quick simple doodle", so a drawing of "something quick" could not be told apart from the template's own word. "Fast" asks the same question. |
| Pictures | `muse-image-1.0`, the doodle template word for word: 16 per word, in 4 calls of n = 4, at 512 px (`scripts/plato_ideas_generate.py --words`). 64 pictures from 16 calls; none was refused or short, and none has written words. |
| Emblems | Glimmer's multiple choice with each word's 6–7 options (`plato_ideas.WORDS`), forward and reversed, plus "something else" and "can't tell". Our labels by eye came first (SHA-256 in the plan's addendum 1). |
| Spread | The house measure: ink crop, DINOv2-base CLS, mean pairwise cosine distance; 2,000 bootstrap resamples of pictures. |

## Results, Part 1: God and the ideas under damage

### Pre-registered tests

| # | Prediction | Glimmer (primary) | By eye | Verdict |
|---|---|---|---|---|
| D1 | Intact SDXL God: a person in ≥ 12 of 16, a beard in ≥ 8, a halo in ≤ 12 | person 12, beard 10, halo 3 | 15, 10, 6 | **Held** |
| D2 | Words damage takes the beard or halo before the figure ("fails first": below half its intact rate) | beard at ×0.5, halo at ×0.625, person never | beard and halo at ×0.5, person never | **Held** (also with neurons switched off) |
| D3 | God drifts toward a generic person: the rise in "person, no beard, no halo" under words damage is ≥ 4 of 16 and larger than under drawing damage | +7 vs +0 of 16 | +10 vs +3 | **Held** |
| D4 | All 15 keys: words damage keeps the intact emblem less than drawing damage, at matched severity | −9.5 points (CI −16.4 to −3.0; by key −17.3 to +0.6); 78 pictures | | **Held** (the by-key CI touches 0) |
| D5 | Drawing damage costs more "clean line drawing" | +0.00 (CI −0.01 to +0.01) | | **Failed** |
| D6 | Among pictures with no person intact, words damage adds people more | +19.3 points (CI +10.8 to +28.6; by key +10.0 to +27.6); 58 pictures | | **Held** |

**God alone (descriptive).** "Still a man with a beard" (Glimmer's emblem), words minus drawing damage at matched severity:
- with noise, −12.9 points (CI −29.3 to +4.2, 16 seeds);
- with neurons switched off, 0.0 (CI −11.3 to +10.3).

Sixteen seeds are too few to separate the two parts on this measure alone.

### God, step by step

Share of SDXL's 16 drawings of God showing each feature, by Glimmer (by eye in brackets). "Generic" is a person with neither beard nor halo.

| Words part (noise) | intact | ×0.25 | ×0.5 | ×0.625 | ×0.75 | ×1 |
|---|---|---|---|---|---|---|
| person | 12 (15) | 11 (14) | 10 (11) | 7 (11) | 10 (11) | 12 (14) |
| beard | 10 (10) | 7 (7) | 3 (3) | 1 (2) | 1 (1) | 2 (0) |
| halo | 3 (6) | 2 (4) | 3 (2) | 1 (1) | 2 (1) | 0 (0) |
| generic person | 3 (4) | 5 (6) | 5 (7) | 6 (8) | 7 (9) | 10 (14) |

| Drawing part (noise) | intact | ×0.75 | ×0.825 | ×0.9 | ×1 | ×1.1 |
|---|---|---|---|---|---|---|
| person | 12 (15) | 8 (15) | 7 (12) | 8 (10) | 4 (5) | 2 (1) |
| beard | 10 (10) | 5 (7) | 5 (6) | 5 (5) | 1 (1) | 0 (0) |
| halo | 3 (6) | 4 (1) | 1 (0) | 1 (0) | 1 (0) | 2 (0) |
| generic person | 3 (4) | 2 (7) | 2 (6) | 3 (5) | 3 (4) | 2 (1) |

- **The halo goes first under drawing damage too.** SDXL's halos are ornament, and the drawing part's noise takes ornament early. So "emblem before figure" alone is not the signature of words damage.
- **The signature of words damage is what stays.** The figure stays, it loses God's emblems, and it becomes someone ordinary. Under drawing damage the figure, the beard and the lines go together, and nobody new appears.
- **With neurons switched off,** words damage does the same, less steeply. At 31% off, 9 of 16 still show a person by eye, but 3 have a beard and none a halo. Drawing damage turns the paper into black-and-white woodcut texture, and faces survive longest.
- **Agreement with our eye** over the 320 God pictures:
  - beard 94% (kappa 0.86);
  - person 81% (kappa 0.60). Glimmer counts a face alone as "a person" less often than we did.
  - halo 88% (kappa 0.43). The halo is the least certain feature: SDXL's ornament puts rings and arches near heads.

**The slider's seed** (seed 13, the medoid):
- **Words part, noise.** The bearded, crowned face becomes, step by step:
  - a bearded, crowned face (×0.25);
  - a robed, hooded figure with a halo (×0.5);
  - a cloaked figure (×0.625);
  - a man with glasses and headphones (×0.75);
  - a crowded comic-strip scene (×1).
- **Neurons switched off.** It becomes a bearded figure in flowing robes on clouds, staff in hand, in the manner of Western religious painting (25% off), then a robed figure.
- **Drawing part.** It dissolves into gray scribbles.

### What SDXL draws intact, and what words damage makes of it

The descriptions are by eye, from the contact sheets (8 seeds per idea; the middle column is the strip's seed). The counts are Glimmer's.

| Idea | SDXL intact (Glimmer's top emblem) | Most words damage (strip seed) | A person in it (intact → most words damage → most drawing damage) |
|---|---|---|---|
| love | ornate hearts (a heart, 8 of 8) | two women's faces, then anime people | 25% → 75% → 13% |
| time | clocks and pocket watches (a clock, 7 of 8) | a woman's hair and face | 0% → 62% → 0% |
| death | skulls and skeletons (a skull, 8 of 8) | comic panels, then a crowd | 0% → 88% → 0% |
| justice | robed figures, a woman holding scales (figure with scales, 6 of 8) | a caped man, then a person with a backpack | 100% → 88% → 13% |
| beauty | a young woman, mostly her face (8 of 8, as Muse) | twin faces, then anime women | 100% → 75% → 13% |
| the Good | towns, trees, faces (no listed emblem in 8 of 8) | a motorbike, then a man with a scooter | 25% → 62% → 0% |
| the soul | faces and figures, one seated in meditation (no listed emblem in 6 of 8) | people at a table | 88% → 100% → 13% |
| freedom | the Statue of Liberty's head, winged figures (statue with a torch, 4 of 8) | a rider, then a woman on a motorbike | 75% → 88% → 13% |
| happiness | mostly landscapes, trees, a village (no listed emblem in 6 of 8) | a girl, then an anime girl in a crowd | 38% → 88% → 13% |
| truth | faces staring straight out (a face, 6 of 8) | a car, then a man sitting on a floor | 62% → 50% → 13% |
| running | a person running (8 of 8, as Muse) | three runners, then a cartoon character | 100% → 38% → 13% |
| thinking | heads and faces, no thought bubble (no listed emblem in 5 of 8) | a long-haired woman looking down | 88% → 75% → 25% |
| something fast | streets, landscapes, buildings, a face (no clear object) | a bearded man in a field | 13% → 13% → 0% |
| something heavy | buildings, a bridge, a face, a dragon's head (no listed emblem in 7 of 8) | comic panels | 13% → 25% → 0% |

- **As with the chair, words damage does not send an idea back to a plainer Form.** It turns the idea into a scene with people, and the doodle style goes too: colour and shading come back.
- **Where Muse had a stock emblem, SDXL often has none:** the Good (Muse: a thumbs-up), the soul and happiness. Its truth is mostly a face, where Muse's was scales. For "something fast" and "something heavy" it draws no clear object at all.

### Glimmer's own names, and what the site shows

- For SDXL's ornate figures, Glimmer's free-text names often named a particular figure from a religion or mythology.
  - Among the 16 intact pictures: a Christian figure twice, a Maya sun god and Zeus. It also named a television character once.
  - Under damage it gave such names often, and called some of the horned figures "demonic".
- **What the site shows instead.** The site never shows these names for God's pictures. The slider shows only Glimmer's multiple-choice emblem ("a bearded man", "none of the listed emblems") and its yes/no answers.
- **Frames left out of features.** A few damaged frames of other seeds are horned or creature-like figures, or screaming faces; for example seed 1 at ×0.5–0.75, seed 5 at ×0.625, and seed 14 at ×0.5 and at 25–31% off. They appear in the data but are not featured in the gallery or in posts, because they could read as mocking a religious figure. The slider's seed 13 has none.

## Results, Part 2: beyond nouns

### Pre-registered tests

| # | Prediction | Result | Verdict |
|---|---|---|---|
| W1 | The predicted stock picture is the top emblem for ≥ 3 of 4: running → a runner; thinking → a person pondering, hand on chin; something fast → a race car; something heavy → a weight | **1 of 4** (running). By eye 2 of 4 (adds thinking) | **Failed** |
| W2 | Running and thinking each have concentration ≥ 0.50 | running 1.00, thinking 0.81 (by eye 0.88) | **Held** |
| W3 | Each adjective's spread is above each verb's | 0.46 and 0.44 vs 0.20 and 0.19 | **Held** |
| W4 | Each adjective's spread is above the 11 ideas' median (0.23) | 0.46 and 0.44 | **Held** |

### Each word

| Word | Top emblem (Glimmer) | Share (95% CI) | Other labels | By eye | Agree | Spread (95% CI) |
|---|---|---|---|---|---|---|
| running | one person running | 16/16 (1.00) | none | same | 100% | 0.20 (0.17–0.23) |
| thinking | a thought bubble | 13/16 (0.62–1.00) | pondering person 3 | **pondering person 14**, thought bubble 2 | 31% | 0.19 (0.15–0.23) |
| something fast | a rocket or a plane | 11/16 (0.50–0.88) | race car 4, speed lines 1 | rocket 11, race car 4, something else 1 | 94% | 0.46 (0.36–0.55) |
| something heavy | an anvil | 11/16 (0.50–0.88) | weight (kettlebell) 4, something else 1 | same | 100% | 0.44 (0.29–0.57) |

**What the drawings look like (by eye).**
- **Running:** a stick-like figure mid-stride with motion lines, 16 times.
- **Thinking:** a person with a hand at the chin (14) under an outlined thought bubble (15), with question marks (12) and a light bulb (5).
- **Something fast:** 11 rockets, 4 cars (3 with a driver) and a sneaker, all with speed lines.
- **Something heavy:** 11 anvils, 4 kettlebells and an anchor. No weight is labelled "1 TON".

**The label check.**
- Glimmer and our eye agree on 52 of 64 drawings (81%), kappa 0.78.
- **Thinking falls below the plan's 70% bar (31%).** Every drawing shows both a pondering person and a bubble, and the raters picked different ones as "main". So both are reported. Glimmer's two option orders agreed on 14 of 16 pictures of thinking.

**Where the words sit.**
- The verbs are about as uniform as Muse's median everyday thing: running sits above 51% of the 135 Atlas things, thinking above 44%. They are more uniform than 9 of the 11 ideas.
- The adjectives' point estimates are above every one of the 135 things (the most spread out thing is 0.43) and above 10 of the 11 ideas. Only truth (0.53) is higher. Their CIs are wide.
- Pixel spread does not agree for "something fast" (0.24, near the things' median of 0.21), perhaps because rockets and cars share the same diagonal speed-line composition, which pixels count and DINOv2 looks past.

**Spend:** 64 Muse Image pictures, $1.66 counted at $0.026 a picture, within the $2 cap. The shared ledger went from $63.24 to $63.88. Glimmer and SDXL ran on our own GPU.

## Deviations from the plan

- **The SDXL run moved to axon-server01.** Servers 02 and 03 were in use. It loaded the same diffusers version as the pad's run (0.42.0) from a private path, and one missing VAE file was downloaded first. Settings, seeds and unit statistics are unchanged. Recorded in addendum 2.
- **The site shows no Glimmer free-text names for God's pictures** (see above). The plan did not say either way; the names stay in the data and in this write-up.
- **The seed rule differs from the things' strips by design.** The concrete things' seeds were chosen by eye; the ideas' seeds by the pre-registered medoid rule.
- **The page's damage pictures** live in `static/img/plato_ideas/dmg/`, apart from the pad's `static/img/draw_damage/`. The pad's folder budget rose from 1.5 to 2.5 MB, so the WebP quality, and with it every thing's existing picture, is unchanged (byte-identical).

## Limitations

- **SDXL is not Muse Image.** Damage to SDXL says how one open model's ideas come apart, not Muse's. SDXL's intact God already differs from Muse's.
- **Small n.** God has 16 seeds, the other keys 8. The per-idea numbers are descriptions. The pooled tests (D4–D6) use 58–128 pictures, and the by-key CI for D4 touches 0.
- **Readers are models.** Glimmer reads person, beard, halo and emblem; DINOv2 measures change. Our eye agreed with Glimmer on the beard, less well on the person and the halo.
- **The style words are damaged too.** "Doodle, black marker, no shading" passes through the damaged text encoders, so words damage brings back colour and shading. That is one reason D5 failed.
- **Four words are not "verbs" and "adjectives" in general.** W1–W4 describe these four.

## Files

| File | What |
|---|---|
| `docs/plato_ideas_damage_plan.md` | the pre-registration and its two addenda |
| `metalesionlab/plato_ideas.py` (`WORDS`), `metalesionlab/plato_ideas_damage.py` | the words, their options, the damage plan's constants |
| `scripts/draw_damage_sdxl.py run --ideas`, `scripts/plato_ideas_damage.py`, `scripts/plato_ideas_damage_glimmer.py` | SDXL pictures, the Mac's analysis, Glimmer's reading |
| `scripts/plato_ideas_generate.py --words`, `scripts/plato_ideas_label.py`, `scripts/plato_ideas_analyze.py words` | the words' Muse pictures, labels and statistics |
| `scripts/draw_damage_export.py`, `scripts/plato_ideas_web_export.py`, `scripts/plato_gallery_export.py` | the pad's strips, the page's data and pictures, the gallery's God strip |
| `public_data/plato_ideas.json` (`words`, `damage`) | statistics only |
| `PlatosChair/ideas/damage/` (outside the repository) | SDXL pictures, crops, embeddings, Glimmer labels, `god_by_eye.json`, `picks.json`, `results.json`, sheets |
| `PlatosChair/ideas/social/sdxl_god_*` | social candidates: three God-damage frames of seed 13 and its two-row strip |

Credits: Stable Diffusion XL base 1.0 (Stability AI), CreativeML OpenRAIL++-M. Meta Muse Image 1.0 (drawings), Muse Glimmer 30B (labels), DINOv2 (Apache-2.0).

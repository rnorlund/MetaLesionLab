# The Atlas of Forms: pre-registration

Written on Oct 27, 2026, and committed before any new picture was generated, downloaded or embedded. Results will go in `docs/plato_atlas.md`. Any deviation from this plan will be listed there as a deviation.

**The question.** Plato's Chair (`docs/plato.md`) found, for 35 everyday things, that Meta's Muse Image draws them far more uniformly than people do. Its spread is about half of people's (median ratio 0.49), and it is narrower for 34 of 35 things. Does that hold for everyday things in general, or only for the 35 we happened to pick? The Atlas scales the study to 135 things and turns it into a benchmark that anyone can run on their own image model.

Code: `metalesionlab/plato_atlas.py` and `scripts/plato_atlas_*.py`; the benchmark is `scripts/plato_benchmark.py`. Data: `PlatosChair/atlas/`, outside the repository. The core (`PlatosChair/core/`) and Plato's Forms (`PlatosChair/forms/`) folders are only read, never written.

**What I had seen before writing this.** The core results and figures (`docs/plato.md`), and the bed and table results from Plato's Forms (`docs/plato_forms.md`). I have seen no picture, by any model or person, of the 98 new concepts. The new concepts were drawn by code (below) before any picture existed.

## Concepts: 135

| Group | n | Pictures |
|---|---|---|
| Core (Plato's Chair), unchanged | 35 | Existing: Muse 16 (tier 1) or 12 (tier 2), SDXL 16, people 200 |
| Plato's own bed and table (Plato's Forms) | 2 | Existing, same prompt and protocol: Muse 16, SDXL 16, people 200 |
| New | 98 | New: Muse 12, SDXL 12, people 200 |

### Selection rule for the 98 new concepts

Quick, Draw! has 345 categories. Each one was sorted, by hand and before drawing, into exactly one of four groups. The lists are in `metalesionlab/plato_atlas.py`.
- **Already studied (37):** the 35 core concepts and the bed and table.
- **Excluded (41)**, with these reasons:
  - abstract shapes, not things (10): circle, square, triangle, hexagon, octagon, line, squiggle, zigzag, star, diamond;
  - proper nouns or landmarks (3): The Eiffel Tower, The Great Wall of China, The Mona Lisa;
  - imaginary things (4): angel, dragon, mermaid, flying saucer;
  - weapons (4): cannon, rifle, sword, aircraft carrier;
  - not an object (4): animal migration, camouflage, spreadsheet, stitches;
  - ambiguous words, each naming two common things (6): bat, mouse, nail, pool, fan, compass;
  - near-duplicates of a studied concept (10): coffee cup, mug, alarm clock, smiley face, palm tree, police car, school bus, pickup truck, birthday cake, goatee.
- **Eligible (267)**: drawable, everyday things, each sorted into one of 12 domains.
- **Drawn (98):** a stratified random draw from the eligible list.
  - Each domain has a fixed quota (`QUOTAS`).
  - Rain, hurricane and snowman were named in the brief, so they are always in. They count inside their domain's quota.
  - The rest of each domain is a seeded random draw, `numpy.random.default_rng(20261027)`, over the domain's alphabetical list (`plato_atlas.select_new()`).

The draw gave these 98:

| Domain | Quota | Drawn |
|---|---|---|
| Animals | 18 | ant, camel, cow, dolphin, flamingo, frog, giraffe, hedgehog, kangaroo, lion, owl, parrot, penguin, rabbit, rhinoceros, sea turtle, tiger, whale |
| Food | 11 | asparagus, blackberry, blueberry, cake, cookie, grapes, ice cream, lollipop, peanut, peas, popsicle |
| Household | 10 | bandage, bathtub, couch, dishwasher, envelope, hourglass, lantern, lighter, sink, tent |
| Tools and stationery | 8 | anvil, binoculars, crayon, garden hose, marker, pencil, rake, syringe |
| Electronics | 5 | calculator, cell phone, computer, headphones, remote control |
| Vehicles | 8 | airplane, ambulance, cruise ship, firetruck, hot air balloon, parachute, submarine, wheel |
| Buildings and places | 8 | barn, fence, hospital, mailbox, roller coaster, see saw, swing set, windmill |
| Nature and weather | 9 | bush, feather, house plant, hurricane, moon, mountain, rain, snowflake, snowman |
| Body parts | 7 | arm, beard, elbow, eye, finger, skull, tooth |
| Clothing and accessories | 7 | backpack, bracelet, flip flops, lipstick, pants, purse, t-shirt |
| Instruments | 4 | clarinet, drums, trombone, violin |
| Sports and toys | 3 | baseball bat, rollerskates, teddy-bear |

The names above are Quick, Draw! category names. The page shows "seesaw", "roller skates" and "teddy bear".

### Natural kind or artifact (a-priori coding, for the exploratory test)

**Natural** means not made by people: animals, fruit, vegetables, nuts and mushrooms, body parts and people, plants, landscape, sky and weather.
- **Natural, among the 37 existing concepts (13):** cat, tree, face, carrot, pineapple, snail, cactus, flower, bird, fish, dog, apple and person (yoga).
- **Natural, among the 98 new concepts (38):**
  - all 18 animals;
  - asparagus, blackberry, blueberry, grapes, peanut and peas;
  - all 7 body parts;
  - bush, feather, hurricane, moon, mountain, rain and snowflake.
- **Artifacts:** everything else. That includes prepared food (cake, cookie, ice cream, lollipop, popsicle), the house plant (kept by people) and the snowman (made by people).
- **Totals:** 51 natural and 84 artifacts.

## Pictures

- **Muse Image** (`muse-image-1.0`) gets the core doodle prompt, unchanged: *"A quick simple doodle sketch of {phrase}, black marker on plain white, like a 20-second drawing, no text, no shading."*
  - **Phrase:** "a"/"an" + the name. Plurals and mass nouns go bare ("grapes", "rain", "ice cream"); "the moon" takes "the" (`plato_atlas.phrase_for`).
  - **Calls:** 12 pictures per new concept, in 3 separate calls of n = 4 (there is no seed parameter). Pictures are downscaled to 512 px.
  - **Cost and stop:** about 1,176 images, about $11.76.
    - The run's own spend is reserved before each call in `atlas/spend.jsonl` and capped at $14.
    - Paid calls stop if the shared ledger (`runs/costs.jsonl`) passes $70.
- **Stable Diffusion XL** (`stabilityai/stable-diffusion-xl-base-1.0`, fp16) runs on a lab GPU with the core settings: the same prompt, the core negative prompt, 768 px, 25 steps, Euler, guidance 5.
  - 12 pictures per new concept, downscaled to 512 px.
  - Seeds: 20261026 + 1000 × (100 + new-concept index) + picture index. The core used concept indexes 0 to 36, so seeds never repeat.
  - Core and forms concepts keep their existing 16 SDXL pictures.
- **People.** The first 200 drawings with `recognized=true`, in file order, from each Quick, Draw! simplified file (streamed, never downloaded whole). They are rendered at 256 px, as in the core. If the first 5,000 lines hold fewer than 200, the reader goes on up to 20,000 lines.

## Measures (all as in the core, unchanged)

- **Preparation:** ink crop with paper flattening (`plato.ink_crop`, the core's `PREP`).
- **Embedding:** DINOv2-base (`facebook/dinov2-base`), CLS token. The mean patch token is a robustness check.
- **Spread:** mean pairwise cosine distance within a set.
- **Ratio** (the homogenization index): Muse spread ÷ people's spread.
  - People's spread is the mean over 200 random subsets of the same n as Muse's set.
  - CI from independent bootstraps of both: 2,000 Muse resamples and 500 resamples of people (`plato_atlas.spread_ratio`).
  - **Below 1 means Muse is more uniform than people.** "Most Platonic" means the lowest ratio.
- **The analysis set:** each concept's Muse pictures as listed above (16 or 12). Expected spread does not depend on n; only CI widths do.
- **Seeded RNG:** 20261027.

## Hypotheses

### Confirmatory: the core result generalizes (the 98 new concepts only, out of sample)

| # | Prediction | Confirmed if |
|---|---|---|
| H1 | Muse's median ratio is below 1 | The 95% CI of the median lies entirely below 1 |
| H2 | Most concepts are below 1 | The share of new concepts with a ratio below 1 has a Wilson 95% CI whose lower bound is above 50% |

- **The CI of the median** is two-level (`plato_atlas.median_ci`, 5,000 resamples). Concepts are resampled with replacement, and each drawn concept contributes one draw from its own picture-level bootstrap.
- **Expected size (a guess, not a test):** from the core, I expect a median of 0.40 to 0.60 and at least 85% of new concepts below 1.

### Secondary

- **S1 SDXL.** I expect SDXL not to be more uniform than people: its median SDXL/human ratio's CI includes 1 or lies above it. I also expect Muse to be more uniform than SDXL for at least 85% of new concepts (core: 34 of 35).
- **S2 The atlas, all 135 concepts.**
  - Ranked from most Platonic (lowest ratio) to least.
  - Median with the two-level CI.
  - Count below 1, and count whose CI is entirely below 1.
- **S3 Robustness.**
  - The same median and count with patch-mean embeddings.
  - **A model-free pixel spread** (`plato_atlas.pixel_spread`). Each ink-cropped picture is binarized at 200 and blurred with a Gaussian of σ = 8 px at 256 px; the spread is the mean pairwise cosine distance between these ink maps. People use all 200 drawings, since mean pairwise distance is unbiased at any n. I expect the median pixel ratio to be below 1 too.
- **S4 Recognizability.** The share of each concept's Muse doodles that sit nearest their own concept's human centroid, among all 135. Reported only; no concept is excluded for it.

### Exploratory: what makes a thing "Platonic"?

These are exploratory, across all 135 concepts. Each gets a bootstrap 95% CI over concepts (5,000 resamples) and a permutation p. No correction for multiple tests; I will report CIs and not call anything significant.

| # | Predictor | Test | Expectation |
|---|---|---|---|
| P1 | **People's spread** | Spearman of Muse spread with people's spread (core: rho 0.38). Also Spearman of the ratio with people's spread. That one is partly mechanical, because people's spread is the ratio's denominator, so it is reported but not interpreted on its own. | Positive but modest for Muse spread |
| P2 | **Word frequency** | `wordfreq.zipf_frequency(name, "en")`, where the name is the Quick, Draw! name with "-" and "_" as spaces ("teddy bear", "see saw"). Spearman with the ratio. | No directional prediction (two-sided) |
| P3 | **Natural kind vs artifact** | Difference in mean log ratio (natural minus artifact), with a bootstrap CI and a permutation p | No difference (core: kinds did not differ) |
| P4 | **All three together** | OLS of log(Muse spread) on log(people's spread), Zipf frequency and natural (0/1), with bootstrap CIs for each coefficient. A coefficient of 1 on log(people's spread) would mean Muse follows people's spread in proportion. | — |

Domains are shown descriptively (mean and median ratio per domain), without tests.

## The Forms (pictures for the page)

For each concept I make two pixel averages: Muse's Form and people's Form.
- **Method:** the ink-cropped pictures, prepared exactly as for the embeddings, are averaged pixel by pixel. The darkest pixel is stretched to black, as for the clocks in Plato's Forms (`plato_atlas.form_average`).
- **Equal n:** both averages use 12 pictures. Muse's are its first 12 (calls 0 to 2). People's are a seeded random 12 of the 200.
- **On the page:** the same 24 pictures appear as thumbnails when a card is opened.

The averages are illustrations, not a measure. The pixel spread above is the model-free measure.

## Exclusions and stopping

- **Short Muse sets.** If a new concept ends with fewer than 12 Muse pictures after retries (refusals or errors), it is analyzed with what it has if that is at least 8, and dropped otherwise. Dropped concepts are reported, not replaced.
- **No result-based exclusions.** Recognizability is reported, never used to drop a concept.
- **Budget.** Generation stops if the run's own spend reaches $14 or the shared ledger passes $70. The confirmatory tests then run on whatever concepts are complete, and that is reported.

## The benchmark

`scripts/plato_benchmark.py` measures any image model the same way.
- **Input:** a folder with one subfolder per concept, named by the Quick, Draw! category; any concepts of the 135, any number of pictures (at least 4 per concept).
- **Steps:** it embeds the pictures (same ink crop, same DINOv2), and builds or reuses a cached human reference: the same 200 drawings per concept, streamed from Quick, Draw! and embedded locally.
- **Output:** each concept's spread, ratio and CI, and the model's median ratio with its two-level CI. The output also lists Muse Image's and SDXL's numbers from `public_data/plato_atlas.json` alongside.

## Fairness

These are defaults: one prompt, no style or variety instructions. Plato's Chair showed that Muse can draw as varied as people when asked for named kinds. The Atlas measures what Muse draws by default, not what it can draw.

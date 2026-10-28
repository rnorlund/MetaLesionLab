# The Atlas of Forms

Plato's Chair (`docs/plato.md`) found that Meta's Muse Image draws 35 everyday things far more uniformly than people do. The Atlas scales that to 135 things and turns it into a benchmark any image model can be run on. It was pre-registered in `docs/plato_atlas_plan.md` (commit `376195c`) before any new picture was made. The web page is `/plato/atlas`.

## Short answer

- **The core result generalizes.** Muse Image draws **131 of 135** everyday things more alike than people do.
  - Its median spread is **0.53** of people's (95% CI 0.49–0.58).
  - The CI is entirely below 1 for 126 things.
- **Both pre-registered tests pass on the 98 new things**, which were drawn at random before any picture existed:
  - **H1:** median ratio **0.57** (95% CI 0.51–0.60), entirely below 1;
  - **H2:** **95 of 98** below 1 (97%, Wilson CI 91–99%), well above half.
  - The guessed size held too: a median between 0.40 and 0.60, and at least 85% below 1.
- **The most Platonic things:**
  - **Violin** is first: 0.11 (CI 0.08–0.14), the same violin 12 times;
  - then umbrella 0.14, bicycle 0.18, dolphin 0.22, hourglass 0.25, snowman 0.29, shoe 0.29, flamingo 0.30, hurricane 0.31 and pants 0.31.
- **The least Platonic things:**
  - **Lighter** is last, 1.19 (CI 1.03–1.36). It is the only thing Muse varies clearly more than people do.
  - Then binoculars 1.09, book 1.06, crayon 1.04, lipstick 0.92 and marker 0.86.
  - Most of these are small, long objects. Muse draws them at different angles: upright, lying flat, diagonal. DINOv2 counts that as variety (a post hoc observation, made by eye).
- **It is Muse's default, not every image model's.** Given the same prompt, Stable Diffusion XL is more varied than people: median ratio 1.17 (CI 1.07–1.25). It is below 1 for only 48 of 135 things. It is more varied than Muse for 129 of 135.
- **What makes a thing Platonic is mostly unexplained.** We tested three candidates, all exploratory.
  - **People's variety:** Muse's spread tracks people's only loosely (rho 0.26, CI 0.08–0.42).
  - **Word frequency:** no link (rho 0.03, CI −0.15 to 0.20).
  - **Natural vs artifact:** no clear difference. Natural things' median is 0.52, artifacts' 0.59; the difference in mean log ratio has a CI of −15% to +8%.
  - **Together** the three explain 7% of the variation in Muse's spread.
- **The pixels agree.** A model-free pixel spread puts Muse below people for 133 of 135 things (median ratio 0.39). Averaging Muse's 12 drawings pixel by pixel gives a crisp Form; averaging people's 12 gives a cloud.
- **These are defaults.** One plain prompt, no request for variety. Plato's Chair showed that Muse draws as varied as people when asked for named kinds.

## Method

| Step | What we did |
|---|---|
| Things | 135. The 35 Plato's Chair concepts, unchanged. Plato's bed and table from Plato's Forms, drawn with the same prompt and protocol. And **98 new Quick, Draw! categories**. All 345 categories were sorted by hand before any drawing: studied (37), excluded with a reason (41), or eligible in one of 12 domains (267). Excluded were shapes, landmarks, imaginary things, weapons, non-objects, ambiguous words and near-duplicates. Rain, hurricane and snowman (named in the brief) were always in. The rest is a seeded random draw within domain quotas (`plato_atlas.select_new()`, seed 20261027). |
| Muse Image | `muse-image-1.0`. Prompt: *"A quick simple doodle sketch of {a violin}, black marker on plain white, like a 20-second drawing, no text, no shading."* Plurals and mass nouns go bare ("grapes", "rain"); "the moon" takes "the". 12 pictures per new thing, in 3 separate calls of n = 4 (there is no seed parameter), downscaled to 512 px. 1,176 pictures, no failures. Core and forms things keep their existing 16 (tier 1, bed, table) or 12 pictures. |
| SDXL | `stabilityai/stable-diffusion-xl-base-1.0`, fp16, on a lab L40S. The same prompt and the core negative prompt; 768 px, 25 steps, Euler, guidance 5. 12 per new thing; seeds 20261026 + 1000 × (100 + index) + picture. Core and forms things keep their 16. |
| People | The first 200 drawings with `recognized=true`, in file order, from each Quick, Draw! simplified file, rendered at 256 px. Every new thing had 200 within the first 5,000 lines. |
| Embedding | Ink crop with paper flattening, then DINOv2-base (`facebook/dinov2-base`) CLS token on a Mac (MPS). This is the core `PREP`, unchanged. |
| Spread and ratio | Spread is the mean pairwise cosine distance in a set. People's spread is the mean over 200 random subsets of the same n as Muse's set. The ratio (Muse ÷ people) gets a CI from independent bootstraps: 2,000 resamples of Muse's pictures, 500 of people's. **"Most Platonic" means the lowest ratio.** |
| Summaries | The median ratio's CI is two-level (5,000 resamples). Concepts are resampled, and each contributes one draw from its own picture-level bootstrap. Shares get Wilson CIs. |
| Forms | The pixel average of 12 ink-cropped pictures, darkest pixel set to black (as for the clocks in Plato's Forms): Muse's first 12, and a seeded random 12 of people's 200. A model-free **pixel spread** is the mean pairwise cosine distance between blurred ink maps (binarized at 200, Gaussian σ = 8 px at 256 px), for Muse's set and all 200 people. |
| Predictors | Zipf word frequency (`wordfreq`, English) of the category name. The a-priori natural/artifact coding is in the plan. Spearman correlations with bootstrap CIs and permutation p. The natural minus artifact difference in mean log ratio. OLS of log Muse spread on log people's spread, Zipf and natural, with bootstrap CIs. All exploratory. |

Code:
- `metalesionlab/plato_atlas.py`: concept list, selection, statistics, Forms;
- `scripts/plato_atlas_generate.py` (Muse), `plato_atlas_sdxl.py` (GPU), `plato_atlas_data.py` (people, embeddings), `plato_atlas_analyze.py` (pixels, stats), `plato_atlas_web_export.py` (page data, pictures, figures);
- `scripts/plato_benchmark.py`: the benchmark.

Data and figures live in `PlatosChair/atlas/`, outside the repository. Only derived statistics are committed: `public_data/plato_atlas.json`, and the page's data and small pictures.

## Findings

### Pre-registered tests (the 98 new things)

| # | Prediction | Result | Verdict |
|---|---|---|---|
| H1 | Median Muse/people ratio below 1 | 0.57, 95% CI 0.51–0.60 | **Confirmed** |
| H2 | More than half below 1 | 95 of 98 (97%), Wilson CI 91–99% | **Confirmed** |
| (size) | Median 0.40–0.60; at least 85% below 1 | 0.57; 97% | As expected |
| S1 | SDXL not more uniform than people; Muse more uniform than SDXL for at least 85% | SDXL median 1.18 (CI 1.03–1.26) on the new things; Muse more uniform for 93 of 98 (95%) | As expected |
| S3 | The pixel spread agrees | Median pixel ratio 0.39; below 1 for 96 of 98 new things | As expected |

- **CIs.** The ratio's CI lies entirely below 1 for 91 of the 98 new things, and entirely above 1 for one, the lighter.
- **The new things are a little less Platonic than the core 35.** Their median is 0.57; the core's is 0.49 (CI 0.42–0.57). They still fall clearly below 1.

### The atlas: all 135 things

| | Result |
|---|---|
| Below people | 131 of 135 (97%, CI 93–99%); CI entirely below 1 for 126 |
| Median ratio | **0.53** (95% CI 0.49–0.58); mean 0.55 |
| Mean spread | Muse 0.20, people 0.38, SDXL 0.42 |
| Reaching people's level | Only 4: crayon 1.04, book 1.06, binoculars 1.09, lighter 1.19. Only the lighter's CI lies above 1. |
| Core 35, recomputed | Median 0.49, 34 of 35 below 1, CI below 1 for 33: as in `docs/plato.md` |

**Most Platonic (lowest ratio).**

| Rank | Thing | Muse ÷ people (95% CI) | SDXL ÷ people | Set |
|---|---|---|---|---|
| 1 | violin | 0.11 (0.08–0.14) | 0.58 | new |
| 2 | umbrella | 0.14 (0.11–0.18) | 1.11 | core |
| 3 | bicycle | 0.18 (0.14–0.22) | 0.84 | core |
| 4 | dolphin | 0.22 (0.17–0.28) | 0.75 | new |
| 5 | hourglass | 0.25 (0.15–0.36) | 0.21 | new |
| 6 | snowman | 0.29 (0.22–0.36) | 1.10 | new |
| 7 | shoe | 0.29 (0.23–0.37) | 1.01 | core |
| 8 | flamingo | 0.30 (0.23–0.39) | 0.80 | new |
| 9 | hurricane | 0.31 (0.24–0.39) | 0.77 | new |
| 10 | pants | 0.31 (0.25–0.38) | 1.34 | new |

**Least Platonic (highest ratio).**

| Rank | Thing | Muse ÷ people (95% CI) | SDXL ÷ people | Set |
|---|---|---|---|---|
| 126 | clock | 0.80 (0.40–1.22) | 1.92 | core |
| 127 | elbow | 0.80 (0.64–0.99) | 1.52 | new |
| 128 | bandage | 0.81 (0.65–0.97) | 1.74 | new |
| 129 | bush | 0.82 (0.67–0.97) | 1.51 | new |
| 130 | marker | 0.86 (0.53–1.16) | 1.64 | new |
| 131 | lipstick | 0.92 (0.69–1.14) | 1.59 | new |
| 132 | crayon | 1.04 (0.86–1.21) | 1.46 | new |
| 133 | book | 1.06 (0.86–1.22) | 1.64 | core |
| 134 | binoculars | 1.09 (0.86–1.32) | 0.98 | new |
| 135 | lighter | 1.19 (1.03–1.36) | 2.04 | new |

**What the ends look like (by eye).**
- **The most Platonic things are one object, drawn identically.** The same violin and the same three-ball snowman with a top hat, 12 times each. The hurricane is the same satellite-view spiral; people draw a funnel instead.
- **The least Platonic are mostly the same object at different angles.** The crayon, marker, pencil and lipstick are one object, upright, flat or diagonal. The lighter is a Bic, upright 7 times and lying down 5.
  - The ink crop removes size and position, not orientation, so DINOv2 counts the angle as variety.
  - People turn these objects too, but less.
  - This is a post hoc observation, not a pre-registered test.
- **The clock** is still the advert's 10:10 (`docs/plato_forms.md`). Its ratio is high only because people's clocks are uniform too.

**Plato's own examples.**
- **Chair:** 0.37 (CI 0.23–0.55), rank 23.
- **Table:** 0.39 (CI 0.33–0.45), rank 27.
- **Bed:** 0.47 (CI 0.35–0.64), rank 49.
- All three are in the more Platonic half.

**By domain** (descriptive, no tests):

| Domain | n | Median ratio | Below 1 | Most / least Platonic |
|---|---|---|---|---|
| Instruments | 6 | 0.37 | 6 | violin / drums |
| Electronics | 5 | 0.44 | 5 | calculator / cell phone |
| Sports and toys | 3 | 0.44 | 3 | teddy bear / baseball bat |
| Vehicles | 12 | 0.48 | 12 | bicycle / boat |
| Animals | 23 | 0.49 | 23 | dolphin / ant |
| Food | 14 | 0.55 | 14 | carrot / cake |
| Buildings and places | 10 | 0.56 | 10 | house / swing set |
| Body parts | 8 | 0.57 | 8 | eye / elbow |
| Nature and weather | 12 | 0.60 | 12 | snowman / bush |
| Tools and stationery | 13 | 0.61 | 10 | scissors / binoculars |
| Household | 18 | 0.65 | 17 | hourglass / lighter |
| Clothing and accessories | 10 | 0.65 | 10 | umbrella / lipstick |
| People (yoga) | 1 | 0.52 | 1 | — |

### Is it just Muse? (SDXL)

| Question | Result |
|---|---|
| Is SDXL more uniform than people? | **No.** Median SDXL/people ratio 1.17 (CI 1.07–1.25), below 1 for 48 of 135. Its CI lies entirely below 1 for 24 and entirely above for 55. Most uniform: hourglass 0.21, windmill 0.28, rhinoceros 0.34, helicopter 0.49. |
| Is Muse more uniform than SDXL? | **Yes, for 129 of 135.** The CI of the difference excludes zero for 116. Median Muse/SDXL spread ratio 0.45. The exceptions are helicopter, rhinoceros, hourglass, binoculars, windmill and backpack. |
| Do the two models find the same things easy? | **Moderately.** Muse's and SDXL's spreads correlate at rho 0.45 (CI 0.29–0.58); with 35 concepts the core found 0.30. SDXL's spread does not track people's (rho 0.05, CI −0.11 to 0.22). |

### Robustness

- **Patch-mean embeddings.** Median ratio 0.44; below 1 for 134 of 135. The ranking matches the CLS ranking closely (rho 0.91, CI 0.86–0.93).
- **Pixel spread (model-free).** Median ratio 0.39; below 1 for 133 of 135 (pencil 1.01 and lighter 1.02 are the exceptions). It ranks things only partly like DINOv2 does (rho 0.37, CI 0.20–0.53): pixels and embeddings agree on the direction far more than on the order.
- **Recognizability.** On average, 70% of each thing's Muse doodles sit nearest people's centroid for that same thing, among all 135. For 15 things it is 0%:
  - dog, hat, person, frog, lion, tiger, blackberry, blueberry, lantern, garden hose, marker, hurricane, snowman, finger and violin.
  - These are mostly style gaps: shaded cartoon animals against stick figures, or a satellite-view hurricane against a funnel.
  - As pre-registered, no thing was dropped for this.

### What makes a thing Platonic? (exploratory)

| # | Predictor | Result |
|---|---|---|
| P1 | People's spread | Muse spread vs people's spread: rho **0.26** (CI 0.08–0.42), p = 0.002. Things people draw in more ways are somewhat more likely to be ones Muse varies, but loosely. The ratio vs people's spread is −0.09 (CI −0.26 to 0.08); that one is partly mechanical. |
| P2 | Word frequency (Zipf) | Ratio vs Zipf: rho **0.03** (CI −0.15 to 0.20). No link. Muse's spread vs Zipf: −0.03. People draw common things a little more uniformly: people's spread vs Zipf, −0.19 (CI −0.35 to −0.03). |
| P3 | Natural vs artifact | Median ratio: natural 0.52 (51 things), artifacts 0.59 (84). Natural minus artifact in mean log ratio: −0.04 (CI −0.16 to 0.07), p = 0.51, i.e. natural things about 4% lower (CI −15% to +8%). No clear difference, as in the core. |
| P4 | All three (OLS of log Muse spread) | log people's spread **0.77** (CI 0.28–1.20); Zipf 0.01 (−0.07 to 0.09); natural −0.04 (−0.16 to 0.08); **R² 0.07** |

- **P4.** The slope on people's spread is below 1 but its CI includes 1. On average, Muse's spread rises with people's, in rough proportion, with a lot of scatter. Most of what makes a thing Platonic for Muse is not in these three.
- **A guess, not tested.** Whether a thing has one canonical product shape, like the violin, the Bic lighter or the snowman, and whether it is long and easy to turn, look like better candidates for a future pre-registration.

## Run it on your model

`scripts/plato_benchmark.py` measures any image model exactly as the Atlas measures Muse.

1. **Draw.** Make pictures of any of the 135 things with your model: at least 4 per thing, 12 or more is better. Use the Atlas prompt for comparability: *"A quick simple doodle sketch of {a chair}, black marker on plain white, like a 20-second drawing, no text, no shading."*
2. **Arrange.** One subfolder per thing, named by its Quick, Draw! category. Spaces, `_` and `-` all work, and "boat", "lamp" and "person" mean sailboat, floor lamp and yoga. Pictures can be PNG, JPEG or WebP, any size.
   ```
   my_model/
     chair/        0.png … 11.png
     teddy bear/   …
     sea_turtle/   …
   ```
3. **Run.**
   ```
   pip install -e ".[experiments]"          # numpy, scipy, pillow, httpx, torch, transformers
   python scripts/plato_benchmark.py my_model --name "My model" --out my_model_atlas.json
   python scripts/plato_benchmark.py --list  # the 135 names
   ```

**What it does:**
- **Embeds your pictures** with the Atlas pipeline: ink crop, then DINOv2-base CLS. It runs on CUDA, MPS or the CPU (`--device`).
- **Builds the human reference once per thing**, then caches it in `~/.cache/plato_atlas/human/` (`--cache`). That is the same 200 drawings, streamed from Google's public Quick, Draw! bucket, rendered and embedded the same way.
  - The cache stores embeddings and drawing IDs only.
  - A few seconds per thing the first time; four things, model loading included, took under 30 seconds on a Mac.
- **Reports:**
  - for each thing: your spread, people's spread at your n, the ratio with a 95% CI, and Muse's and SDXL's ratios for that thing from `public_data/plato_atlas.json`;
  - overall: your median ratio with the two-level CI, how many things fall below 1, and Muse's and SDXL's medians on the same things.
- **Checks itself.** It warns if its human reference differs from the Atlas's.

**Checked.**
- **Muse's own folders.** Run on four of Muse's folders (chair, lighter, teddy bear, violin), the benchmark rebuilt the human reference from Quick, Draw!. Its people's spreads matched the Atlas's exactly (difference 0.0000), and its ratios were within 0.01 of the Atlas's: 0.37, 1.20, 0.38 and 0.11 (the Atlas has 0.37, 1.19, 0.38 and 0.11).
- **A fixture test.** A tiny fixture (fake embeddings, no network) is in `tests/test_plato_atlas.py`.

**Reading the number.**
- **Below 1:** your model draws that thing more alike than 20-second human doodles do.
- **Your style counts.** DINOv2 sees style as well as content, so shading, frames or photographic rendering count as spread. Use the doodle prompt and compare like with like.

## Deviations from the plan

1. **Core numbers are recomputed, not copied.** People's spread is a mean over random subsets, so recomputing in one run shifts some core ratios by up to about 0.02 from `docs/plato.md`; book is 1.06 here and 1.04 there. The core's medians and counts are unchanged.
2. **Post hoc additions, labelled as such.** The by-eye notes on the ends of the ranking (orientation of long objects), the domain table, and Muse vs SDXL spread correlation and the people's-spread-vs-frequency correlation (reported beside the planned P1 and P2).

## Caveats

- **Spread is DINOv2's view.** DINOv2 sees style, line quality and orientation as well as which object it is. Muse's marker doodles and people's mouse drawings differ in style, which is why only 70% of Muse's doodles sit nearest their own thing among people's drawings. The pixel spread gives the same direction without any model.
- **People are Quick, Draw! players**, drawing in 20 seconds with a mouse or finger. Their drawings are the first 200 the game's recognizer accepted, which may favour typical drawings and so make people look *more* uniform, not less.
- **Twelve pictures per thing** make single ranks noisy. The CIs often overlap across 30 or more ranks, so read the ends of the ranking, not the exact order.
- **One prompt, one style.** Other wordings or styles may give other spreads. **These are defaults.** Asked for named kinds, Muse Image draws about as varied as people (`docs/plato.md`).
- **The Forms are illustrations.** A pixel average depends on alignment: the ink crop centres and scales each picture but does not rotate it.
- **Exploratory predictors** are not corrected for multiple tests, and Zipf frequency measures the word, not how often the thing is pictured.

## Cost

| Item | Cost |
|---|---|
| Muse Image: 1,176 pictures (294 calls of 4), no failures or timeouts | **$11.76** |
| SDXL: 1,176 pictures on a lab L40S (52 minutes, shared with another job) | $0 |
| DINOv2 on the Mac: 21,952 pictures | $0 |
| Quick, Draw!: 19,600 drawings streamed | $0 |

- **This run's own log:** `PlatosChair/atlas/spend.jsonl`, $11.76 of the $14 cap.
- **The shared ledger:** $44.94 at the start and $60.83 at the end, including other agents' spend. The $70 stop was never reached.

## Figures and files

- `PlatosChair/atlas/figures/atlas_forms.png`: the Forms of the 8 most and 8 least Platonic things, Muse above people.
- `PlatosChair/atlas/figures/atlas_rank.png`: all 135 ratios with SDXL's.
- `PlatosChair/atlas/results.json`: every statistic. `pixels.json`: the pixel spreads and which 12 people each Form uses.
- `public_data/plato_atlas.json`: the derived statistics (no pictures or embeddings); also the benchmark's reference.
- Page: `/plato/atlas` (`metalesionlab/web/pages/plato_atlas.html`, `static/js/plato_atlas.js`, `static/css/plato_atlas.css`, `plato_atlas_routes.py`). It holds 675 small WebP pictures, 3.3 MB in all, lazy-loaded; the thumbnails load only when a card is opened.

**Credits.**
- **Human drawings:** Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0, https://github.com/googlecreativelab/quickdraw-dataset. The drawings are never committed; the page shows small averages and thumbnails with credit.
- **AI drawings:** Muse Image (Meta) and Stable Diffusion XL base 1.0 (Stability AI, CreativeML OpenRAIL++-M).
- **Embeddings:** DINOv2 (Meta, Apache-2.0).

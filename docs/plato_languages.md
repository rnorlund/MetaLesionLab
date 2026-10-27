# Plato's chair in six languages

**Question.** Is the "ideal chair" the same in every language and culture? We asked Meta's Muse Image for quick doodles of 10 everyday objects using the same prompt written in six languages. We then compared those doodles with drawings people made of the same objects in six countries in Google's Quick, Draw!

**Short answer.**
- **The chair itself barely changes with language.** Muse Image draws the same slatted wooden chair whether you ask in English, Spanish, Hindi, Mandarin, Arabic or Swahili.
- **Some words do change the picture.** In Hindi, Mandarin, Arabic and Swahili a "hat" is a baseball cap. In Spanish, *sombrero* gives a brimmed hat, sometimes a Mexican sombrero.
- **People's drawings shift a little by country, and reliably so.** Country explains about 1.6% of the variation in people's drawings. Chairs are the most country-dependent concept for people (3.3%).
- **The AI's language effect is larger than people's country effect.** That is partly an artifact: the AI's drawings are about half as varied as people's, so a small shift counts for more. Some of the shift is also drawing style rather than form.

## Method

| Step | What we did |
|---|---|
| Concepts | chair, house, cup, shoe, hat, tree, bird, flower, bicycle, umbrella (all are Quick, Draw! categories) |
| Prompt | *"A quick doodle of a {object}, drawn in under 20 seconds with a black marker on a white background. Simple black lines only: no shading, no color, no text, no other objects."* |
| Translation | One Muse Spark 1.3 call (minimal reasoning) wrote the whole prompt, with the everyday word for each object, in Spanish, Hindi, Mandarin (Simplified), Arabic (MSA) and Swahili. Reviewed by hand; all 60 prompts are in `results.json`. |
| AI drawings | Muse Image 1.0 with default settings: **10 doodles × 10 concepts × 6 languages = 600**, stored at 512 px. |
| Human drawings | Quick, Draw! simplified ndjson, streamed line by line until each country had **200 recognized drawings per concept** (12,000 in all). Streaming stopped there: 21–33 MB per category, 257 MB in total, never a whole file. Drawings were rendered at 256 px with 3 px lines. |
| Countries | United States, Mexico, India, Taiwan, Saudi Arabia, Russia. The first five match five of the prompt languages (English, Spanish, Hindi, Mandarin, Arabic). No Swahili-speaking country has enough drawings (Kenya and Tanzania are under 0.05% of the data), so Russia is the sixth region. |
| Framing | Every drawing is cropped to its ink and centred, with its longer side at 200 px on a 256 px white canvas. AI drawings are also binarized, which removes grey paper. |
| Embedding | Meta's DINOv2 (`facebook/dinov2-base`, Apache-2.0) on MPS: the L2-normalized CLS token. Distance is cosine distance. |
| Measures | **Spread:** average distance between two drawings from the same group (language or country). **Between:** distance between two groups' average drawings, minus what sampling noise alone produces; 0 means no difference, and the estimate doesn't depend on sample size. **Group share:** between-group variance as a share of all variance, i.e. how much of the variation the language or country explains. |
| Statistics | 95% bootstrap CIs, resampling drawings within each group: 2,000 resamples for AI, 1,000 for people. Permutation p-values from shuffling group labels: 2,000 shuffles for AI, 1,000 for people. Human measures are also recomputed on random subsamples of 10 per country, to match the AI's n. |
| Style control | DINOv2 sees style as well as form: line weight, sketchy repeated strokes, paper texture. As a control, every drawing (AI and human) was binarized, nearby strokes merged, thinned to a skeleton and redrawn with one 3 px line, then re-embedded. |
| Checks | (1) Validity: is each AI doodle closest to the human centroid of its own concept? (2) Robustness: the same analysis on mean-patch embeddings. |

Code: `metalesionlab/plato_lang.py` and `scripts/plato_lang_{prompts,generate,humans,analyze,figures,public}.py`. Data and figures live outside the repo, in `$PLATO_LANG_DIR` (default `PlatosChair/languages/`).

## Findings

Shares are percentages of variation explained by group, given as [95% CI]. Distances are ×10⁻³.

### 1. Does the AI's "ideal chair" change with the language of the prompt?

No, not in any way that matters.
- All 60 AI chairs are the same slatted wooden dining chair in three-quarter view (`average_chair.png`).
- Raw images:
  - Language explains **5.0% [0.4, 10.1]** of the variation in AI chairs (p = 0.003).
  - With style removed it explains **0.7% [−3.0, 5.4]** (p = 0.24), indistinguishable from zero.
- Comparison with people, style removed:
  - The AI's average chair moves **1.1 [−4.3, 7.6]** between languages.
  - People's average chair moves **11.8 [8.5, 15.2]** between countries, about ten times more.
- Plato would be pleased: in Muse Image there is one chair.

The prompt language does change some objects:
- **Hat** is the clearest case: 20.2% [13.8, 28.6] raw and 18.1% [12.2, 24.9] with style removed (p = 0.001).
  - Baseball caps: 10 of 10 in Hindi (*टोपी*), Mandarin (*帽子*), Arabic (*قبعة*) and Swahili (*kofia*); 7 of 10 in English; 1 of 10 in Spanish.
  - Spanish (*sombrero*) gave 6 brimmed hats and 3 Mexican sombreros.
  - People in all six countries draw a brimmed hat (`average_hat.png`).
- **Cup**: 9.6% [3.4, 15.8] raw and 9.9% [2.4, 17.4] with style removed (p = 0.002). Every cup is a handled mug; what changes is the proportions.
- **Ambiguous words.** Swahili *ndege* means both "bird" and "airplane", and 1 of 10 Swahili "birds" is an airplane.
- **Which languages differ** (style removed, `heatmap_centroids_uniform_lines.png`):
  - Spanish is the outlier (16–26 from every other language), mostly because of *sombrero*.
  - English and Mandarin prompts give practically identical drawings (0.1), as do Arabic and Swahili (1.0).
  - The other pairs fall between 4 and 9.

### 2. Do people's chairs change by country?

Yes, a little, and reliably.
- Country explains **3.3% [2.4, 4.2]** of the variation in people's chairs (p = 0.001). That is the highest of the 10 concepts, and it is 3.1% with style removed.
- Across all concepts, country explains **1.6% [1.5, 1.8]**. Every concept is significant at n = 200 per country.
- Most country-dependent for people: chair (3.3%), cup (2.2%), flower (1.8%), house (1.7%).
- Most universal: bicycle (0.4%) and bird (0.9%).
- The most distinct country is Taiwan: its average drawings are 11.5 from the US and 9.9 from Saudi Arabia. The closest pair is the US and Mexico (2.7).
- Within any one country, people's chairs vary enormously: spread 0.34, against 0.09 for the AI.

### 3. Is the AI's cross-language variation bigger or smaller than people's cross-country variation?

Bigger, but by less than the raw numbers suggest.

| | AI, by language (n = 10) | People, by country (n = 200) |
|---|---|---|
| Group share, raw | **10.3% [8.5, 12.3]** | **1.6% [1.5, 1.8]** |
| Group share, style removed | **5.6% [3.9, 7.0]** | **1.75% [1.6, 1.9]** |
| Between-group distance, raw | 22.3 [18.5, 27.0] | 6.3 [5.7, 6.9] |
| Between-group distance, style removed | 10.2 [7.2, 13.3] | 6.4 [5.8, 7.0] |
| Within-group spread | 0.142 [0.136, 0.148] | 0.315 [0.314, 0.317] |

- **Raw:** the AI's share is larger for all 10 concepts. The difference is 8.6 points [6.8, 10.7].
- **Style removed:** larger for 8 of 10 concepts, with a difference of 3.8 points [2.2, 5.3].
- **Two things inflate the raw contrast:**
  1. Muse Image draws each concept much more uniformly than people do; its spread is less than half of theirs. The same shift is therefore a bigger share of its variation.
  2. About half of the raw language effect is drawing style. For example, Arabic and Swahili prompts give thin, light, pencil-like lines, while Spanish prompts give heavy, sketchy marker lines (see the 60 chairs).
- **Absolute shift, style removed:** the AI's average drawing moves only about 1.6× as far between languages as people's does between countries. Most of that is hats and cups.
- **Equal sample sizes.** Human shares computed on 10 drawings per country average 1.65%, with 95% ranges reaching 3–9% depending on the concept. With raw images, the AI's language share falls above that range for 8 of 10 concepts; the exceptions are chair and umbrella.
- **Robustness:** mean-patch embeddings give the same picture (AI 11.2% [9.3, 13.0] vs people 1.7% [1.5, 1.9]).

### 4. Which concepts are most culture-dependent, and which are most universal?

They are **different concepts for the AI and for people.**

| | Most dependent on group | Most universal |
|---|---|---|
| Muse Image, by language (style removed) | hat 18.1%, cup 9.9%, bicycle 5.7%, umbrella 5.7% | chair 0.7%, house 1.0%, shoe 2.0% |
| People, by country | chair 3.3%, cup 2.2%, flower 1.8%, house 1.7% | bicycle 0.4%, bird 0.9% |

- The two rankings don't agree: Spearman ρ = −0.41 (p = 0.25) raw, −0.19 (p = 0.61) with style removed.
- **Cups are the only concept near the top of both lists.**
- **The AI's language drift doesn't point toward the matching country's drawings.**
  - Test: we took each language's AI average minus the AI mean, and each country's human average minus the human mean. Then we checked whether, for example, the Hindi direction matches the India direction (pairs en–US, es–MX, hi–IN, zh–TW, ar–SA).
  - Result: the cosine is −0.007, against a chance range up to 0.029 (p = 0.64, 720 possible assignments).
  - Prompting in Hindi doesn't make Muse Image draw the way people in India draw; it changes its drawings in its own way.

### Validity check

96% of AI doodles are closest to the human-drawing centroid of their own concept (93–99% per language). 22 of the 24 misses are AI trees (many drawn with blossoms), which sit closer to people's flowers.

## Figures (`PlatosChair/languages/figures/`)

| File | What it shows |
|---|---|
| `grid_ai_house.png`, `grid_ai_chair.png`, `grid_ai_hat.png` (all 10 concepts) | One concept, six prompt languages, 4 random doodles each, with the word in its own script |
| `grid_human_<concept>.png` | The matching grid for people, 4 random drawings per country (Quick, Draw! credited) |
| `average_<concept>.png` | Pixel average of all centred doodles: AI by language (10 each) above people by country (200 each) |
| `heatmap_centroids.png` | Chance-corrected distance between group averages, AI languages vs countries, mean over concepts, on a shared scale |
| `heatmap_centroids_uniform_lines.png` | The same with style removed |
| `share_by_concept.png` | Group share per concept with 95% CIs: AI raw, AI with style removed, people |

## Caveats

- **Translation is part of the treatment.**
  - We used one natural translation per language, reviewed by hand and not by native speakers of every language.
  - The hat result comes from the word: *sombrero* vs *gorra* would likely give different hats. The same goes for the Swahili *ndege* airplane.
  - The effect is "language plus everyday word choice", not language alone.
- **Style vs form.** Raw DINOv2 distances mix what is drawn with how it is drawn. The uniform-line control removes line weight and sketchiness, but it adds artifacts to heavily sketched drawings (scribbled caps and tree crowns). We report both, and for most concepts the conclusions depend on which you trust.
- **Small n for the AI.** With 10 doodles per language (budget: $6 of Muse Image), single-concept CIs are wide, about ±5–7 points on the share. The overall means are much tighter.
- **Country is not language.**
  - Quick, Draw! prompts were shown in the local language, but many players in India, for example, used English.
  - Taiwan writes Traditional Chinese, not Simplified.
  - Russia stands in for Swahili.
  - Country codes come from players' IP addresses.
- **Who played Quick, Draw!** Online players around 2016–2017, drawing with a mouse or finger against a 20-second clock. We kept only drawings the game's classifier recognized, which favours canonical shapes, and we took the first 200 per country in file order (the file isn't sorted by time).
- **Two kinds of drawing.** AI doodles look like marker sketches; people's are mouse strokes. Absolute distances between AI and human drawings aren't comparable, so every comparison here is within a domain (a share, or a chance-corrected distance), set side by side.
- **One model call setting.** Muse Image ran with its defaults, including its own prompt reasoning. It may translate prompts internally, and that is part of what we measure.
- **Ten concepts** make the rank comparisons coarse.

## Cost

| Item | Cost |
|---|---|
| Muse Image: 600 doodles at $0.01 | $6.00 |
| Muse Spark: one translation call | $0.02 |
| DINOv2 on the Mac, Quick, Draw! streaming | $0 |
| **Total** | **$6.02** |

Some calls failed with connection errors during a network outage and were retried with backoff. Meta bills only for images that are returned.

## Attribution

- Human drawings: [Quick, Draw! dataset](https://quickdraw.withgoogle.com/data) by Google, licensed CC BY 4.0. Drawings are never committed to this repository; only group-level statistics are in `public_data/plato_languages.json`.
- AI drawings: Muse Image 1.0 (Meta). Translation: Muse Spark 1.3 (Meta). Embeddings: DINOv2 (Meta, Apache-2.0).

## Reproduce

```bash
export PLATO_LANG_DIR=/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/languages
python scripts/plato_lang_prompts.py          # 1 Muse Spark call
python scripts/plato_lang_generate.py         # 600 Muse Image doodles, $6
python -I scripts/plato_lang_humans.py        # stream Quick, Draw! (free)
python scripts/plato_lang_analyze.py          # DINOv2 embeddings + statistics -> results.json
python scripts/plato_lang_figures.py          # figures/
python scripts/plato_lang_public.py           # public_data/plato_languages.json
```

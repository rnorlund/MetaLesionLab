# Plato's Chair

Plato thought there is one ideal chair. If you ask an AI to draw 16 chairs and 16 boats, are its chairs all alike while its boats vary? How spread out is each concept in the AI's imagination, and does that match how varied people's drawings of the same thing are?

**Short answer:** Muse Image draws almost every concept far more uniformly than people do. Its spread is about half of people's (median ratio 0.49), and 34 of 35 concepts fall below the human level. The concepts that people draw most variably are only somewhat more likely to be the ones the AI varies (rank correlation 0.38). Its chair is close to a Platonic one: the same slat-back dining chair, in the same three-quarter view, 16 times.

## Method

| Step | What we did |
|---|---|
| Concepts | 35 Quick, Draw! categories, drawn in priority order. Tier 1 (16 AI pictures each): chair, boat, face, house, cat, cup, tree, car, key, umbrella. Tier 2 (12 each): the 13 other demo-set words that exist in Quick, Draw!, plus flower, bird, fish, dog, shoe, hat, clock, lamp, book, guitar, apple and person. |
| Substitutes | Quick, Draw! has no "boat", "lamp" or "person". We used **sailboat**, **floor lamp** and **yoga** (its whole-body human figure; the AI prompt is "a person doing yoga"). Five demo words have no category at all and are left out: anchor, kettle, glove, whistle, igloo. |
| AI drawings | Muse Image 1.0 (`muse-image-1.0`), prompt: *"A quick simple doodle sketch of {a chair}, black marker on plain white, like a 20-second drawing, no text, no shading."* There is no seed parameter, so we made separate calls of n=4: 4 calls for tier 1 and 3 calls for tier 2. Pictures are downscaled to 512 px. |
| Human drawings | Google Quick, Draw! simplified strokes, streamed line by line from the public bucket. We kept the first 200 drawings per category with `recognized=true` and rendered them at 256 px, black on white. |
| Normalising | Both sources are cropped to their ink, padded to a square and resized (Quick, Draw! drawings are already scaled to fill their box). AI "paper" (gray, textured or vignetted backgrounds) is flattened to white first. |
| Embedding | Meta DINOv2 (`facebook/dinov2-base`, Apache-2.0), run locally on a Mac (MPS). We use the CLS token; the mean patch token is a robustness check. |
| Spread | Mean pairwise cosine distance among a concept's pictures. |
| Equal n | The AI side is the concept's n pictures (16 or 12), with a 2,000-sample bootstrap CI over pictures. For the human side we drew 200 random subsets of the same n from the 200 drawings. The human spread is the mean of those subsets, with a bootstrap CI over drawings. |
| Homogenization index | AI spread divided by human spread, with a CI from independent bootstraps of both. Below 1 means the AI is more uniform than people. |
| Between-concept baseline | Mean distance from a concept's pictures to every other concept's pictures in the same source. Relative spread is within-concept spread divided by this baseline. |

Code: `metalesionlab/plato.py` and `scripts/plato_{generate,human,embed,analyze,figures}.py`. Data, results and figures live outside the repo, in `$PLATO_DIR` (default `PlatosChair/core/`). `public_data/plato_concept_spread.json` holds only derived statistics.

## Findings (35 concepts)

| | Result |
|---|---|
| Overall | The AI is more uniform than people for 34 of 35 concepts. The CI is entirely below 1 for 33 of them. Median homogenization index: **0.49**. Mean spread: AI 0.18, people 0.37. For 33 concepts, the AI's set is more uniform than every one of 200 random sets of human drawings of the same size. |
| Relative to how distinct concepts are | The AI's concepts are also farther apart from each other (between-concept distance 0.75, against 0.52 for people). Relative to that baseline, the AI is about 3 times tighter: median relative spread 0.22 against 0.73 for people (median relative index 0.34). |
| Does the AI's spread follow people's? | Only modestly. Spearman rho = **0.38** [95% CI 0.08, 0.62], permutation p = 0.025. On relative spread: 0.30 [-0.01, 0.56]. With patch-mean embeddings: 0.33 [0.00, 0.60]. The ranking of the index barely changes between the two embeddings (rho 0.86). |
| Most uniform AI concepts | umbrella (0.055), bicycle (0.062), shoe, ladder, face, cat |
| Most varied AI concepts | book (0.36), key (0.31), spoon, hat, tree, cactus |
| Most homogenized (index) | umbrella **0.14** [0.11, 0.18], bicycle 0.18 [0.14, 0.22], shoe 0.29, scissors 0.32, cup 0.32, carrot 0.33 |
| Least homogenized | book **1.04** [0.87, 1.21] (the only concept the AI varies as much as people: open, closed, stacked, at an angle), clock 0.80 [0.38, 1.20] (people draw clocks very uniformly too), candle 0.76, tree 0.75, hat 0.72, key 0.71 |
| Kinds of concept | No difference. Mean index: fixed-shape artifacts 0.49, many-style artifacts 0.52, natural kinds 0.51, person 0.48 (2 items). |

**Chair vs. boat (the lead's example).**
- People draw chairs more variably than boats: 0.36 vs. 0.31.
- The AI does the reverse. Its chairs (0.13 [0.09, 0.19]) are, if anything, more alike than its sailboats (0.20 [0.15, 0.24]). The difference has a CI of [-0.01, 0.13], so this is a trend, not a sure thing.
- So the AI flattens chairs the most: index 0.37 [0.24, 0.55] for chairs against 0.63 [0.49, 0.77] for boats.
- Most of the 16 people drew a chair in side view. The AI drew one slat-back dining chair in three-quarter view, over and over.

**Person.**
- **Face.** People draw faces very uniformly: a circle with a smile is among the lowest human spreads, 34th of 35. The AI is even more uniform: 0.12 against 0.26, index 0.44 [0.37, 0.51].
- **Whole person (yoga).** People's drawings are among the most varied (0.43, 7th of 35). The AI's are about half as varied: 0.22 [0.15, 0.29], index 0.52 [0.35, 0.66]. Almost all of them show tree pose or lotus, in the same cartoon style.
- So the lead's suspicion holds: people picture a person far more variously than the AI does. But "person" is not special: the AI compresses it about as much as the median concept.

**Sampling check.** Pictures from the same API call are no more alike than pictures from different calls (distance 0.185 vs. 0.185). The n=4 batches therefore behave like independent draws.

**Recognisability check.** In DINOv2 space, 85% of the AI doodles sit closest to the human centroid of their own concept, out of 35. The exceptions are concepts where style differs most:
- person 0% (the AI draws cartoon people, people draw stick figures)
- dog 8%
- bench 17%
- hat 25%

## Link to naming (exploratory, n = 15)

For the 15 demo words that exist in Quick, Draw!, we recorded:
- Muse Spark name agreement on the demo pictures
- Muse Glimmer's intact naming (glimmer_names.json)
- per-item accuracy across 229 Glimmer lesion conditions (`runs/lesion/demo_en/`), overall and by localizer (language, naming, visual)
- accuracy across 18 Spanish conditions (`demo_es`, matched by gloss)

**This is exploratory and underpowered.**
- Spark and intact Glimmer are at ceiling (all correct), so they can't correlate with anything.
- No spread measure tracks lesion robustness. Every |rho| is 0.35 or less, and every CI spans zero. Examples:
  - AI spread vs. overall lesion accuracy: rho 0.09 [-0.44, 0.56]
  - human spread vs. accuracy under language-localizer lesions: -0.32 [-0.75, 0.23]

Per-concept values are in `results.json` under `naming`.

## Caveats

- **Style mismatch.** The AI's "20-second doodle" is a clean, sketchy marker cartoon. Quick, Draw! drawings are real 20-second mouse or finger drawings, often unfinished, by players worldwide.
  - Part of the human spread is skill and noise, not a different idea of the object. That is why the absolute index (about 0.5) matters less than the ranking across concepts and the relative (between-concept) version.
  - Style differs more for some concepts (person, dog) than others.
- **Prompt sensitivity.** One prompt template, one style. A different wording ("a chair, any kind", "a children's drawing") would move the AI's spread. We have not measured how much. The realistic-photo style was skipped to save budget.
- **The image model's sampling.** There is no seed or temperature control, and separate calls are the only source of variety. Muse Image returned mostly 3:2 pictures (309 of 460) and some square ones; cropping to the ink removes that difference.
- **Small n.**
  - Tier 2 concepts have only 12 AI pictures, so some CIs are wide: clock [0.09, 0.28] and harp [0.08, 0.28], each driven by one or two unusual drawings.
  - The cross-concept correlation rests on 35 concepts, and the naming link on 15.
- **Category substitutes.** Boat is sailboat, lamp is floor lamp, and person is yoga. Humans saw only the word "yoga"; the AI got "a person doing yoga".
- **One embedding model.** DINOv2 is a vision model. "Spread" is visual spread, not conceptual spread.
- **Human sample.** We used the first 200 recognized drawings in file order, not a random sample of all drawings.

## Next steps

1. **Second generator.** A self-hosted SDXL run would test whether low diversity is specific to Muse Image or common to image models.
2. **Prompt sweep.** Vary the prompt on a few concepts (chair, boat, person, book) to measure prompt sensitivity, and add the realistic-photo style for 10 concepts (about $1.60).
3. **Style-matched comparison.** Thin both sources to single-pixel strokes before embedding, or prompt for "one continuous thin line".
4. **Spread inside Muse Glimmer.** Measure each concept's spread inside the model's layers (PlatosChair/inside_glimmer). Then test the lead's hypothesis on more items, with graded lesion severities rather than one accuracy score: diffuse concepts are harder to name and lost first under damage.
5. **Web panel and video moment** (see the final report).

Human drawings: Google Quick, Draw! dataset, Google Creative Lab, CC BY 4.0 (https://github.com/googlecreativelab/quickdraw-dataset). The drawings are never committed to this repository.

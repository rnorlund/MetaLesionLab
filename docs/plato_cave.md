# Plato's Cave: name the shadow

Plato's prisoners see only shadows on the cave wall and take them for the things themselves. How much of an everyday object survives as a bare shadow, and does an AI lose the same objects people do?

**Short answer:** Most of an object survives as a shadow.
- **How much survives.** Meta's open model Muse Glimmer 30B named 100 of 100 line drawings, 86% of their outlines, 90% of their filled silhouettes and 67% of soft shadows cast on a wall.
- **Names the medium.** When it failed on a cast shadow, its most common answer was simply "Shadow" (10 times), then "UFO" (7). Plato's prisoners take the shadow for the thing; the model often names the shadow instead of the thing.
- **Same objects as people, mostly.** The objects people find hard to identify as silhouettes are harder for Glimmer too (rank correlation 0.32 [0.07, 0.51] with whether it named them; 0.43 [0.23, 0.61] with its confidence in the right name). But Glimmer named many silhouettes that people miss.
- **Second model.** Muse Spark behaved the same way on a 50-picture sample.

Pre-registered in `docs/plato_cave_plan.md` (committed before any model saw a picture). Not every prediction held; see "Predictions".

## Method

| Step | What we did |
|---|---|
| Pictures | The project's 100 checked line drawings (`runs/sets/core100_en`, each with an accepted name and alternates). |
| Four versions | All made by code (`metalesionlab/plato_cave.py`, `metalesionlab/plato_shapes.py`, `scripts/plato_cave_stimuli.py`). They share one square crop around the object, at 512 px. **Original:** the drawing. **Outline:** only the silhouette's outer contour, as thick as the drawing's own strokes. **Silhouette:** the drawing filled black; the background is flooded from the picture's edge, and whatever it can't reach is the object. Holes are filled, as in the main silhouettes of Wagemans et al. (2008). **Shadow:** the silhouette sheared, squashed a little and blurred, as a gray shadow on a lit, faintly textured gray wall. |
| Gaps | Outlines with small gaps were closed first, using the smallest closing radius after which the filled area stops jumping. 94 pictures needed none, 3 a radius of 2 px, 1 of 8 px and 2 of 12 px (at 1024 px). Feather was set by hand to 12 px after the QC sheet showed its barbs leaking. |
| Open drawings | A foot cut off at the ankle, an ear and a nose are drawn as open curves. Each was closed across its biggest opening: the convex-hull edge whose closure encloses the most area. SAM 3.1 was tried first on these three (4 calls, $0.01). Its foot mask was patchy, its nose mask covered a small patch, and it found no ear in two tries. |
| Naming | **Muse Glimmer 30B** (FP8, one L40S): "Name the object in this picture with exactly one word." The answer channel is pre-filled, decoding is greedy (8 tokens), and pictures are resized to 448 px. The full word lens is read after all 52 decoder layers (`plato_glimmer.name_with_word_lens`, reused from Plato's Chair). **Muse Spark** (`muse-spark-1.3`, minimal reasoning) named a seeded random 50 of the 100 pictures in all four versions, with the Test Studio prompt. |
| Coding | The project's PNT-style coder (`model_lab.code_answer`), with WordNet and the cached Muse Spark meaning judge. Every incorrect real-word answer also went to Muse Spark as second rater (`scorer.second_rater`) with the picture the model saw. Its "Visual" code means a word for something that looks like the picture but is unrelated in meaning. |
| People | Wagemans, De Winter, Op de Beeck, Ploeger, Beckers & Vanroose (2008), *Perception* 37:207–244, Table 2: "% correct concept" for silhouettes and outlines of the 260 Snodgrass & Vanderwart (1980) pictures. 356 first-year psychology students at the University of Leuven wrote a name for each picture (5 s each), scored in Flemish/Dutch. 78 of our 100 concepts map onto an SV item; boat counts as sailboat, and SV's heart is the valentine shape. |
| Statistics | Accuracy with a 2,000-sample bootstrap 95% CI over pictures. Each version is compared with the original as a paired difference with a paired bootstrap CI and an exact McNemar p. The human comparison uses Spearman's rho with a bootstrap CI over concepts and a permutation p. The word-lens comparison is a paired difference over pictures named correctly in both versions. |

## Findings

### Accuracy by version

| Version | Muse Glimmer (100) | vs. original | McNemar p | Muse Spark (50) | Glimmer on Spark's 50 |
|---|---|---|---|---|---|
| Original | **100%** [100, 100] | | | 100% [100, 100] | 100% |
| Outline | **86%** [79, 92] | −14 points [−21, −8] | 0.0001 | 90% [82, 98] | 88% |
| Silhouette | **90%** [83, 95] | −10 [−16, −4] | 0.002 | 90% [82, 98] | 90% |
| Cast shadow | **67%** [57, 76] | −33 [−42, −24] | < 0.0001 | 76% [64, 88] | 66% |

- **Detail costs little; the shadow costs a third.** Losing the inside detail (outline, silhouette) cost 10–14 points. The soft, sheared cast shadow cost 33.
- **Outline vs. silhouette.** A filled silhouette was named slightly more often than a bare outline (90% vs. 86%). People show the same small order: 64.7% vs. 61.9% on the 260 SV pictures.
- **Spark.** Spark and Glimmer agreed on whether a picture was named correctly for 100%, 98%, 100% and 86% of the 50 pictures (original, outline, silhouette, shadow).

### Which objects survive

- **All four versions:** 66 objects, among them the anchor, bicycle, scissors, key, umbrella, giraffe, cactus, helicopter, ladder and sled.
- **Lost in every reduced version:** 9 objects. A book (a rectangle), a clock and a watermelon (circles), a sun (a starburst), and an ear, a feather, a shell, a tambourine and a whistle (read as a submarine).
- **Lost only as a cast shadow** (named as outline and as silhouette): 19. They are the rabbit, penguin, hedgehog, airplane, axe, saw, rake, egg, boat ("canoe"), bone, leaf, nest, guitar, flute, sock ("boot"), scarf, belt and igloo ("Umbrella"), plus the eye ("UFO").
- **Lost in some versions:** 6 more fall in between.
  - Lost as outline and as shadow: the glove ("hand" both times), the bench ("sofa", "couch"), the bread ("bun", "UFO") and the artichoke.
  - Lost as silhouette and as shadow: the hat ("bowler", "UFO").
  - Lost only as outline: the tree ("Ginkgo").
- **Most robust** (mean final-layer p(name) over the three reduced versions): car, anchor, tooth, owl, trumpet, bicycle, acorn, snail, cherry, volcano.
- **Least robust:** clock, book, whistle, tambourine, shell, watermelon, feather, sun, ear, glove.

### What it says instead (error types)

| Version | Errors | Semantic | Formal | Mixed | Unrelated | Description | "Visual" (second rater) |
|---|---|---|---|---|---|---|---|
| Outline | 14 | 5 | 1 | 3 | 3 | 2 | 4 of 12 real-word errors |
| Silhouette | 10 | 1 | 3 | 1 | 3 | 2 | 6 of 8 |
| Cast shadow | 33 | 6 | 4 | 1 | 19 | 3 | 17 of 30 |

- **It names the medium.** For cast shadows, 10 answers were just "Shadow": airplane, clock, ear, egg, feather, guitar, leaf, penguin, rabbit and sun. Three more began "The object is a shadow of …".
- **"UFO."** Seven answers were "UFO", mostly for soft ovals: belt, bread, eye, flute, hat, nest and saw.
- **Silhouettes never.** It never answered "Shadow" for a sharp black silhouette.
- **Spark too.** Muse Spark answered "shadow" for 5 of its 50 cast shadows (cat, ear, egg, feather, rabbit).
- *This "medium" analysis was not pre-registered;* we added it after seeing the answers.
- **Shape errors.** The shape-based "visual" share rises from outlines to shadows. The rater was not consistent about "Shadow" answers, coding them Unrelated, Semantic or Visual.

### Inside the model (word lens)

- **When the name appears.** In every version, the correct name first becomes the lens's top guess in the last dozen layers: around layer 43 of 52 for originals.
- **Shadows: a little later.** For cast shadows the first correct layer is +0.57 layers later [0.10, 1.07] than for the same drawings (67 objects named in both). The stable correct layer is +1.19 later [0.17, 2.23].
- **Silhouettes: no delay.** For silhouettes there is no delay (−0.01 [−0.34, 0.31]); the stable layer is in fact slightly earlier (−0.45 [−0.90, −0.05]).
- **Outlines: unclear.** For outlines, +0.21 [−0.03, 0.47].
- **Final confidence.** Mean final-layer p(correct name) is 0.79 for originals, 0.72 silhouettes, 0.69 outlines and 0.51 cast shadows.

### People (Wagemans et al. 2008), 78 shared concepts

| | Silhouette | Outline |
|---|---|---|
| Spearman rho, people's rate vs. Glimmer correct (0/1) | **0.32** [0.07, 0.51], p = 0.003 | 0.39 [0.16, 0.57], p = 0.0002 |
| rho, people's rate vs. Glimmer's p(correct name) | 0.43 [0.23, 0.61], p = 0.0002 | 0.36 [0.13, 0.56], p = 0.002 |
| Mean, people vs. Glimmer | 75% vs. 91% | 73% vs. 87% |
| Glimmer where < 50% of people named it | 67% [44, 89] of 18 concepts | 56% [33, 78] of 18 |
| Glimmer where > 90% of people named it | 98% [94, 100] of 50 | 98% [94, 100] of 48 |

- **Lost by both (silhouettes):** watermelon, clock, book, ear, sun, whistle.
- **People lost, Glimmer named:** ladder, bread, artichoke, broom, sled, eye, nose, drum, flute, accordion, belt, house.
  - Some of this is the drawings. Filled-in SV silhouettes of a front-view ladder or a sled are black slabs. Wagemans et al. report that without filled holes, ladder and sled rise to 98.8%.
- **Glimmer lost, people named:** hat. Glimmer said "bowler", and the coder doesn't accept that as "hat".
- **Published human means** (all 260 SV items): 64.7% silhouettes, 61.85% outlines (correct concept).

## Predictions (pre-registered)

| Prediction | Result |
|---|---|
| P1. Original > outline ≈ silhouette > shadow; silhouette at least 15 points below the original | **Partly.** The order held (100 > 86, 90 > 67). But the silhouette was only 10 points below [−16, −4], not 15. |
| P2. Outline and silhouette within 10 points | **Yes** (86% vs. 90%). |
| P3. The AI finds the same shadows hard (rho > 0) | **Yes:** 0.32 [0.07, 0.51] for silhouettes; 0.39 for outlines. |
| P4. More shape-based errors for silhouettes and shadows than for originals | **Yes, trivially.** Originals had no errors at all. Among real-word errors, the "visual" share was 33% (outlines), 75% (silhouettes) and 57% (shadows). |
| P5. The name emerges later for silhouettes | **No.** Silhouettes show no delay. The delay is for cast shadows (+0.57 layers [0.10, 1.07]). |

## Caveats

- **Different drawings.** People saw the 1980 SV drawings; the AI saw our Muse Image drawings. The human comparison is by concept, and a concept's difficulty depends on the drawing's view (front-view ladder vs. our angled one).
  - People also named in Flemish, under a "correct concept" rule with synonyms. Our coder accepts the target, its alternates, plurals and modifiers, so "bowler" for hat or "bunny" (accepted) for rabbit depend on the alternates list.
- **Ceiling.** Glimmer named every original. So "how much is lost" is measured from 100%, and the human-hard concepts are where the variance is.
- **One shadow.** One way of casting the shadow (one shear, one blur, one wall). A sharper or straight-on shadow would score higher; the 23-point gap between silhouette and cast shadow is part shape, part blur and contrast.
- **Short answers.** Answers are capped at 8 tokens, so a few descriptions are cut off ("The object is a shadow of a hed").
- **Second rater.** The rater's "Visual" code is one model's judgment, and it was inconsistent for "Shadow" answers.
- **Human data licence.** No licence is stated for the human item-level data. We quote published means only. The item-level table stays outside the repository, as does a scatter of human vs. AI per concept (`people_vs_ai.png`).
- **No repeats.** One run, greedy decoding, so there is no sampling variability. The CIs are over pictures.

## Cost

| Item | Cost |
|---|---|
| Spark naming (200 calls), second rater (57) and meaning judge | about $0.43 (tagged `plato_cave` in the ledger, plus about 72 untagged naming calls before tagging) |
| SAM 3.1 (4 calls) | $0.01 |
| Glimmer | lab GPU, $0 (2.5 minutes for 400 pictures with the full word lens) |

## Files

- **Code:** `metalesionlab/plato_shapes.py`, `metalesionlab/plato_cave.py`, `scripts/plato_cave_{stimuli,glimmer,analyze,figures,web_export}.py`.
- **Derived statistics:** `public_data/plato_cave.json`.
- **Data** (stimuli, raw answers, the human norms CSV, `results.json`) live outside the repository, in `PlatosChair/cave/`.
- **Figures** in `PlatosChair/cave/figures/`:
  - `cave_wall.png` (the hero: 12 shadows on a firelit wall with Glimmer's answer under each)
  - `versions_strip.png`
  - `accuracy_by_version.{png,svg}`
  - `word_lens.{png,svg}`
  - `people_vs_ai.{png,svg}` (outside the repository only)
- **Page:** `/plato/cave` (the "Name the shadow" game runs in the browser and stores nothing).

**Credits.** Wagemans, J., De Winter, J., Op de Beeck, H., Ploeger, A., Beckers, T., & Vanroose, P. (2008). Identification of everyday objects on the basis of silhouette and outline versions. *Perception*, 37(2), 207–244, doi:10.1068/p5825. Snodgrass, J. G., & Vanderwart, M. (1980). *Journal of Experimental Psychology: Human Learning and Memory*, 6, 174–215. For context on shape in AI vision: Geirhos et al. (2019, ICLR), ImageNet-trained CNNs rely on texture over shape; Baker et al. (2018, *PLoS Comput Biol*), CNNs recognise few silhouettes. Models: Meta Muse Glimmer 30B, Muse Spark 1.3, Muse Image 1.0 (the drawings) and SAM 3.1 (tried).

# Plato's Cave: pre-registered plan

Written and committed on Oct 27, 2026, after the stimuli were made and checked by eye but before any model named any of them.

## Question

Plato's prisoners see only shadows and take them for the things themselves. How much of an everyday object survives as a bare shadow? And do the AI and people lose the same objects?

## Stimuli (made by code, already built)

- **Pictures.** The 100 checked pictures of the core naming set (`runs/sets/core100_en`). Each has an accepted name and alternates.
- **Four versions** of each picture (`metalesionlab/plato_cave.py`, `scripts/plato_cave_stimuli.py`), all in one square crop around the object, at 512 px:
  - **original:** the line drawing.
  - **outline:** only the silhouette's outer contour, drawn as a line about as thick as the drawing's own strokes. No inner detail.
  - **silhouette:** the drawing filled black. The background is flooded from the picture's edge; whatever it can't reach is the object. Holes are filled, as in the main silhouettes of Wagemans et al. (2008).
  - **shadow:** the silhouette as a soft, sheared shadow cast on a lit gray wall.
- **Gaps.** Outlines with small gaps are closed first. The smallest closing radius that seals them is chosen by a fixed rule; feather was set by hand (radius 12 px at 1024 px), after checking by eye.
- **Open drawings.** Three drawings are open curves that flooding can't fill: a foot cut off at the ankle, an ear and a nose. Each is closed across its biggest opening, the convex-hull edge whose closure encloses the most area.
  - SAM 3.1 was tried on these three first, for 4 calls ($0.01). Its foot mask was patchy, its nose mask covered a small patch, and it found no ear in two tries. So SAM is not used.

## Models and prompts

- **Muse Glimmer 30B** (FP8, one L40S) names all 400 pictures with the project's naming prompt: *"Name the object in this picture with exactly one word."* As in the other experiments:
  - The answer channel is pre-filled and decoding is greedy, up to 8 tokens.
  - Pictures are padded to a square and resized to 448 px.
  - The full word lens is read after every one of the 52 decoder layers (`plato_glimmer.name_with_word_lens`).
- **Muse Spark** (`muse-spark-1.3`, minimal reasoning) names a random sample of **50 of the 100 pictures**, in all four versions (200 calls). The sample is drawn with seed 0. The prompt is the Test Studio naming prompt: *"Name the object in this picture with exactly one word in English. Reply with the word only."*

## Coding

- **Naming codes.** Every answer is coded with the project's PNT-style coder (`model_lab.code_answer` → `naming_errors.classify`), using the item's accepted name and alternates.
  - "Correct" never depends on a judge.
  - Semantic vs. unrelated uses WordNet plus the cached Muse Spark meaning judge.
- **Shape-based ("visual") errors.** Every incorrect answer that names a real word gets a second code from Muse Spark (`scorer.second_rater`), with the stimulus the model saw attached. The rater's "Visual" category means a real word for something that looks like the picture but is unrelated in meaning.

## Measures and analyses

1. **Accuracy by version.** The share of pictures named correctly, with a 2,000-sample bootstrap 95% CI over pictures. Each version is compared with the original as a paired difference, with a paired bootstrap CI and an exact McNemar p.
2. **Which objects survive.** We list:
   - the objects named correctly in all four versions;
   - the objects lost as silhouettes or shadows;
   - per object, the lowest version still named.
3. **Human comparison.**
   - Source: Wagemans et al. (2008), Table 2. It gives identification rates ("% correct concept") for silhouettes and outlines of the 260 Snodgrass & Vanderwart pictures, from Flemish students.
   - Overlap: 78 of our 100 concepts map onto an SV item (sailboat counts as boat; heart is the valentine shape in SV).
   - Primary test: Spearman's rho between the human silhouette rate and Glimmer's silhouette correctness (0/1), with a bootstrap CI over concepts and a permutation p.
   - Secondary tests:
     - the same with Glimmer's final-layer p(name) for the silhouette;
     - outline vs. human outline rate;
     - Glimmer's accuracy on the concepts people find hard (human rate below 50%) vs. easy (above 90%).
   - These are different drawings of the same concepts, so this is a concept-level comparison.
   - No licence is stated for the human data. We quote published numbers only and keep the table out of the repository.
4. **Error types.**
   - The distribution of codes by version.
   - The share of errors that are shape-based (Spark "Visual"), by version.
5. **Word lens.**
   - The first layer whose top guess is the correct name.
   - Compared between each version and the original, on pictures named correctly in both: the paired mean difference, with a bootstrap CI.
   - Also the mean p(name) by layer and version.
6. **Second model.** Spark accuracy by version on its 50-picture sample, with CIs, and its agreement with Glimmer on the same pictures.

## Predictions

- **P1.** Accuracy falls from the original to the shadow. We expect original > outline ≈ silhouette > shadow. Silhouette accuracy should be at least 15 points below the original.
- **P2.** Outline and silhouette are within 10 points of each other. For people the two were close: 64.7% vs. 61.9% in Wagemans et al.
- **P3.** The AI finds the same shadows hard: rho between human silhouette rates and Glimmer's silhouette correctness is above 0.
- **P4.** Errors on silhouettes and shadows are more often shape-based ("Visual") than errors on the originals.
- **P5.** For silhouettes, the correct name emerges later in the word lens than for originals: the first correct layer is higher.

## Not pre-registered

The visitor game ("Name the shadow") and any figure choices.

## Budget

- Spark naming: 200 calls.
- Visual-error rater: one call per incorrect real-word answer.
- Semantic judge: cached pairs only.
- In all, under $1.20. Glimmer is free (lab GPU).

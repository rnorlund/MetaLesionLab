# Plato's Chair inside Glimmer

**Status: exploratory.** 35 concepts, about 920 pictures, one model. There are many comparisons and none of them was pre-registered. The 95% CIs are percentile bootstraps over concepts (for a single concept's spread, over its pictures), and the p values come from permutations. Treat any single p < .05 as a lead, not a finding.

## Question

The core Plato's Chair experiment measures how spread out each concept is in pictures. Muse Image draws 12–16 doodles per concept, Google Quick, Draw! provides human doodles, and DINOv2 measures within-concept spread.

Here we give the same pictures to **Muse Glimmer 30B** and ask three things:

1. **How spread out is each concept inside Glimmer?** We look at the vision tower, the projector and every decoder layer.
2. **Are more spread-out (less prototypical) concepts harder to name?** We measure accuracy, confidence, and the layer where the name first appears.
3. **Are they lost first when Glimmer is damaged?**

The idea comes from typicality effects in people: atypical category members are named more slowly and less accurately, and are thought to be more fragile after brain damage.

## Method

**Pictures.** The core experiment's folders (`PlatosChair/core/`) hold 35 concepts. The five "fill" concepts were not generated. For each concept we use every AI doodle (16 for 10 concepts, 12 for 25) and the same number of human doodles, drawn at random (seed 0) from the 200-drawing Quick, Draw! pool. That is 920 pictures in total.

Every picture is padded to a white square and resized to 448 px. AI and human doodles therefore cost the same 256 image tokens. Human doodles are rendered at 256 px and upsampled.

**Naming.** Prompt: "Name the object in this picture with exactly one word." The answer channel is pre-filled (`glimmer.build_inputs`), decoding is greedy, and at most 8 new tokens are generated.

Answers are coded with the Philadelphia Naming Test rules (`model_lab.code_answer`). The accepted names are the core experiment's label plus a fixed list of alternates (`plato_glimmer.NAMES`). Examples:
- boat: sailboat, ship
- person: yoga, man, woman, figure, stick figure
- lamp; cup: mug

**Hidden states.** One prefill pass records:
- the residual stream at the answer position after every decoder layer (52 layers, 6,656-d);
- the vision tower output (the `vision_adapter` input, 6,144-d), mean-pooled over the picture's image tokens;
- the projector output (6,656-d), pooled the same way.

**Spread.** Spread is the mean pairwise cosine distance among a concept's pictures, computed separately for AI and human doodles. This is the core experiment's measure. Glimmer's spaces are centered on the mean over all 920 pictures first, because the residual stream has a large shared direction; raw cosine is kept as a check.

Two DINOv2 spreads are used:
- our own, from DINOv2-base CLS embeddings of the exact pictures Glimmer saw;
- the core experiment's (`core/results.json`), whose human spread uses the whole 200-drawing pool.

**Word lens (full word).** Many names split into several tokens with ambiguous first tokens ("S|poon", "C|andle", "H|arp"), so a first-token lens is unreliable. After the prefill, each accepted spelling of the name is fed through the cached prompt. At each layer l:

> log p_l(name) = Σ_k log softmax(final norm + output head applied to layer l's residual at the position before token k)[token k]

This is summed over accepted names and spellings. The **first correct layer** is the first layer where every token of an accepted name is the lens's top guess.

A check on 16 pictures showed that the answers after cropping the cache matched the lesion engine's generator 16/16, with identical hidden states.

**Lesions.** We use the lesion engine (`metalesionlab/lesions.py`) with reversible forward hooks. Mean-ablation statistics come from `unit_stats_demo_en`, and naming-localizer rankings from `localizers/naming_en`.

Doses were calibrated on 140 pictures (2 AI + 2 human per concept) with the aim of about half of intact accuracy. The table shows accuracy on all 920 pictures (intact: 80.6%).

| Condition | Dose | Accuracy | Correct names lost |
|---|---|---|---|
| Naming-localizer neurons, mean-ablated | top 22.9% of neurons | 27.9% | 66% |
| Naming-localizer neurons, mean-ablated (milder) | top 20% | 47.8% | 42% |
| Naming-localizer heads, zeroed | top 6.25% of heads (104) | 54.8% | 33% |
| Noise on layers 9–16 (all heads and neurons) | sd × 1.0 | 49.9% | 40% |
| Noise on layers 41–48 | sd × 3.36 | 49.6% | 41% |
| Random-unit controls, same count per layer: neurons 22.9% / neurons 20% / heads | | 78.1% / 69.9% / 79.3% | 7% / 16% / 5% |
| Random neurons, matched damage | 41.3% / 36% of all neurons | 32.6% / 52.9% | 61% / 37% |

The matched-count controls say whether *which* units are hit matters, at equal count. The matched-damage controls say whether *any* damage of the same severity produces the same pattern.

**Vulnerability measures.**
- **Concept level:** the "lost rate" is the share of a concept's pictures named correctly when intact that the lesioned model misses. Absolute accuracy drop is also reported, but it is confounded with baseline: concepts that start low have less room to fall.
- **Item level:** within each concept and source, a picture's atypicality is its mean distance to the other pictures of its concept. A stratified AUC asks whether atypical pictures are the ones misnamed (intact) or lost (lesions, among intact-correct pictures). The CI is a bootstrap over concepts; the p value comes from shuffling labels within groups.

## Findings

### 1. Glimmer names AI doodles almost perfectly and human doodles much less well

Accuracy is 95.1% on AI doodles and 66.2% on human doodles. By concept, human accuracy runs from 17% (bench, often called "Table") to 100% (helicopter). The word lens settles on the name late: the median first correct layer is 42 of 52 for both sources, and ranges from layer 39 (lamp, scissors) to 51 (harp).

### 2. Inside Glimmer, AI doodles are less spread out than human doodles, and the gap explodes in the late layers

Human doodles are more spread out in every space. The gap (human minus AI spread, mean over concepts) is:

| Space | AI | Human | Gap [95% CI] | Concepts with wider human spread |
|---|---|---|---|---|
| DINOv2 | 0.22 | 0.33 | +0.11 [0.08, 0.14] | 31/35 |
| Projector | 0.22 | 0.43 | +0.21 [0.17, 0.25] | 33/35 |
| Layer 26 | 0.61 | 0.70 | +0.08 [0.05, 0.11] | 27/35 |
| Layer 52 | 0.09 | 0.54 | +0.45 [0.40, 0.50] | 35/35 |

By the naming layers, Glimmer has filed all of a concept's AI doodles in essentially one place, while people's doodles stay spread out (`figures/spread_by_layer.png`).

Glimmer's projector spread agrees with the core experiment's DINOv2 spread for human doodles: rho = 0.72 [0.47, 0.87]. The vision tower agrees less well: 0.37 [0.01, 0.65].

**Concept identity reaches the answer position late** (`figures/rho_by_layer_accuracy.png`, top panel). We measure it as how often a picture's nearest neighbour is the same concept (leave-one-out, within source).

- For human doodles it is 73% at the projector. It falls to 29–31% at layers 26–30, rises from layer 31, and plateaus at about 82% from layer 39.
- For AI doodles it is 99% at the projector, 62–63% at layers 26–28, and 100% from layer 36.

So the answer position at layers 13–26 carries little concept identity, and spread measured there is mostly not about the concept.

### 3. Spread-out concepts are harder to name, but only when spread is measured on the picture side

Human doodles, spread vs. Glimmer's naming accuracy over 35 concepts (`figures/spread_vs_naming_human.png`):

| Spread measured in | rho [95% CI] | p |
|---|---|---|
| DINOv2, core (200-drawing pool) | −0.50 [−0.70, −0.23] | .003 |
| DINOv2, the exact pictures | −0.36 [−0.59, −0.07] | .034 |
| Glimmer projector | −0.35 [−0.60, −0.04] | .042 (log p(name): −0.50 [−0.68, −0.24]) |
| Glimmer vision tower | −0.21 [−0.50, +0.15] | |
| Decoder layer 13 | +0.06 [−0.30, +0.44] | |
| Decoder layer 26 | +0.19 [−0.15, +0.51] | |
| Decoder layers 46 and 52 | −0.60 and −0.72 | circular, see below |

Late-layer spread at the answer position partly *is* the answer: concepts whose pictures get different answers are spread out there by construction. Those correlations are reported but not interpreted.

AI doodles are at ceiling on accuracy, so we use log p(name) instead (`figures/spread_vs_naming_ai_logp.png`): DINOv2 core −0.37 [−0.62, −0.05], projector −0.23 [−0.50, +0.09].

Robustness checks for the DINOv2 and projector results:
- **Without hat and yoga** (name-agreement problems, see caveats): DINOv2 core −0.56 [−0.75, −0.28]; projector −0.40 [−0.65, −0.08].
- **Relative spread** (within / between concept distance): projector −0.36 [−0.61, −0.06].

**Spread does not predict *when* the name appears.** Spread vs. the first correct layer: every |rho| ≤ 0.29 and every CI includes 0 (e.g. DINOv2 core, human doodles: −0.20 [−0.53, +0.17]).

**Item level, intact.** Within a concept, the atypical doodles are the ones Glimmer misnames (`figures/typicality_items.png`). AUC (174 misnamed out of 920 pictures):

| Space | AUC [95% CI] | p |
|---|---|---|
| DINOv2 | 0.61 [0.56, 0.65] | .002 |
| Vision tower | 0.65 [0.60, 0.70] | < .001 |
| Projector | 0.66 [0.61, 0.71] | < .001 |
| Layer 26 | 0.45 [0.37, 0.52] | |

This is the clearest typicality effect in the data.

### 4. Spread does not predict which concepts lose their names first under damage

Concept spread vs. lost rate (`figures/spread_vs_lesion_dinov2_core.png`, `figures/spread_vs_lesion_projector.png`). For each targeted lesion, every rho with DINOv2-core or projector spread lies between −0.25 and +0.09, and every CI includes 0:

| Lesion | DINOv2 core | Projector |
|---|---|---|
| Naming neurons at 48% | +0.09 [−0.26, +0.41] | +0.08 [−0.26, +0.40] |
| Naming heads | −0.06 [−0.41, +0.31] | +0.08 [−0.28, +0.43] |
| Late-band noise | −0.13 [−0.48, +0.24] | −0.25 [−0.54, +0.08] |

The random-unit controls look the same, between −0.05 and +0.16. Targeted minus random rho differences all have CIs spanning 0. Example: naming neurons at 48% vs. its matched-count control, DINOv2 core +0.01 [−0.38, +0.40].

Controlling for intact log p(name) changes nothing. Absolute accuracy drop even leans the other way (diffuse concepts start lower and have less to lose): projector vs. drop under late-band noise −0.39 [−0.64, −0.07].

The only nominal hits are at decoder layer 26, in the opposite direction to the hypothesis: concepts with more layer-26 spread lose *fewer* names under the naming-neuron lesions (−0.36 [−0.63, −0.03] and −0.33 [−0.60, +0.01]). They are not specific, since random neurons at matched damage give −0.24. Layer 26 also carries little concept identity, so we read these as noise.

### 5. Item level: moderate targeted damage takes atypical doodles first; random damage does not

Among pictures named correctly when intact, the AUC for "atypical pictures are lost" is:

| Lesion | Accuracy | Projector AUC [95% CI] | p | DINOv2 AUC [95% CI] |
|---|---|---|---|---|
| Naming neurons | 48% | 0.62 [0.55, 0.69] | .003 | 0.57 [0.48, 0.68] |
| Late-band noise | 50% | 0.57 [0.52, 0.62] | .015 | |
| Naming heads | 55% | 0.56 [0.50, 0.61] | .058 | |
| Random neurons (matched damage) | 53% | 0.50 [0.45, 0.56] | | |
| Random neurons (matched damage) | 33% | 0.47 [0.43, 0.52] | | |
| Early-band noise | 50% | 0.48 [0.43, 0.53] | | |
| Naming neurons (severe) | 28% | 0.51 [0.46, 0.56] | | |

Paired over concepts at matched damage (naming neurons 48% vs. random neurons 53%), the AUC difference is:
- projector: **+0.12 [0.03, 0.20]**
- DINOv2: +0.10 [0.00, 0.20]
- vision tower: +0.00 [−0.09, +0.10]

Against the matched-count controls, which do far less damage, the differences are not reliable (projector +0.06 [−0.05, +0.18]).

This pattern is suggestive, not established. It is one of 40 item-level lesion tests, and it holds for one targeted lesion at moderate severity but not at the severe dose.

## Summary

- Inside Glimmer, people's doodles of a concept stay spread out while Muse Image's collapse to one point by the naming layers.
  - **Collapse layer**, a summary measure used by Ask Socrates (`public_data/plato_glimmer_inside.json`, from `scripts/plato_glimmer_inside_export.py`): the first decoder layer from which Muse Image's doodles stay less than 0.5 times as spread out as people's, through layer 52. Median layer 36 (range 30–44) across 35 things; "person" never collapses. The 0.5 threshold is a convention chosen after seeing the data, not a pre-registered test.
- Concepts whose pictures vary more are harder for Glimmer to name: rho about −0.35 to −0.50 when spread is measured on the picture side (DINOv2, projector).
- Within a concept, the atypical doodles are the ones it misnames (AUC 0.61–0.66).
- That spread does not tell us which concepts break first under damage, nor how late the name appears.
- There is a hint that a moderate naming-neuron lesion takes atypical doodles first, more than random damage of the same severity does.

## Caveats

- **Few concepts, many tests.** n = 35 concepts, several hundred correlations and AUCs, no multiplicity correction. 25 concepts have 12 pictures per source rather than 16.
- **AI doodles are at ceiling** (95%), so AI-side analyses lean on log p(name).
- **Name agreement is not recognition.** Muse Image's "hat" is a baseball cap, and Glimmer calls 11 of 12 "cap". "Yoga" pictures get pose names ("Tree pose", "Meditation"). Strict scoring is primary; a sensitivity analysis drops both concepts.
- **The accepted-name lists are ours** and change accuracy. p(name) uses the same lists.
- **Truncated answers.** Answers are cut at 8 new tokens, so a name after a long carrier phrase would be missed. 13 answers were coded "Description".
- **Circular late layers.** Late-layer spread encodes the answer itself, so its correlations with naming are partly circular.
- **The mid-layer null depends on centering.** With raw (uncentered) cosine, layer-13 spread does correlate with human naming accuracy: −0.49 [−0.71, −0.15].
- **The word lens is a logit lens.** Early layers are not calibrated for the output head, so "first correct layer" reflects when the name becomes decodable, not when the concept is first represented.
- **Calibration overlaps the test.** Dose calibration used a subset of the test pictures (for severity only), and the naming-neuron search stopped at 26% rather than the 40% target. That is why a milder dose was added.
- **Reference sets.** Noise lesions are one random draw. Mean-ablation statistics come from the clean demo line drawings, not doodles.
- **Model setup.** FP8 decoder on one L40S. Results are for this model, this prompt and this picture size.
- **Data.** All AI steps use Meta models: Muse Glimmer, Muse Image (core experiment), DINOv2. Human doodles come only from Quick, Draw!; no research-participant data was used.

## Reproduce

```bash
# GPU box (one L40S): intact pass, distances, dose calibration, lesions (~1.5 h)
python scripts/plato_glimmer_run.py all data/core
python scripts/plato_glimmer_run.py extra data/core --family naming-mlp-mean --doses 0.2 --control
python scripts/plato_glimmer_run.py extra data/core --family random-mlp-mean --doses 0.36
# local: copy runs/plato_glimmer/raw/ to PlatosChair/inside_glimmer/raw/, then
python scripts/plato_glimmer_analyze.py
python scripts/plato_inside_web_export.py   # /plato/inside: per-layer maps, spreads and thumbnails
```

Outputs: `PlatosChair/inside_glimmer/results.json` and `PlatosChair/inside_glimmer/figures/`.

Human drawings: Google Creative Lab, "The Quick, Draw! Dataset", https://github.com/googlecreativelab/quickdraw-dataset, licensed CC BY 4.0. The human doodles stay out of this repository.

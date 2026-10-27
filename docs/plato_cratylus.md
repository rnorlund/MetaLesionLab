# Plato's Cratylus: bouba and kiki

In the *Cratylus*, Socrates asks whether names fit things by nature. People all over the world match "bouba" to a round blob and "kiki" to a spiky star (Ćwiek et al. 2022: 72% of 917 people in 25 languages matched both). A text-trained model has never heard a word. Does it still draw a "kiki" spiky?

**Short answer: yes for the famous words, no for new ones.**
- **The famous words.** Muse Image drew all 12 "kiki"s as stars and all 12 "bouba"s as soft blobs: every kiki is spikier than every bouba (probability of superiority 1.00 on solidity and on people's round-to-spiky scale). Takete vs. maluma came out the same.
- **New words.** But eight new words built from the same sounds were all drawn as rounded blobs, including "keti" and "tepi", which have kiki's hard consonants and unrounded vowels. With no name at all, "a shape" came out as stars and polygons; any made-up name except kiki and takete turned it into a blob. The image model learned the famous words, not the sounds.
- **Choosing between shapes.** Muse Spark matched bouba and kiki every time (people: 72%). For the new words it followed the consonants, as people do: soft-consonant words got the round shape 24 of 24 times, hard-consonant words 7 of 24.
- **Glimmer.** Meta's open model Muse Glimmer leaned toward the round shape for nearly every word (p ≈ 0.55). It barely separated bouba (0.70) from kiki (0.51).

Pre-registered in `docs/plato_cratylus_plan.md`, committed before any picture was drawn.

## Method

| Step | What we did |
|---|---|
| Words | **Classic:** bouba, kiki, maluma, takete. **Grid:** soft consonants (b, m, l) or hard ones (k, t, p) crossed with rounded vowels (o, u) or unrounded ones (i, e), two words per cell: bomu, lobu / bemi, limi / kotu, tupo / keti, tepi. **Neutral controls:** fana, hasa, nafa, safa. **No name:** "a shape". **Spellings:** b-o-u-b-a, k-i-k-i, "bouba (pronounced BOO-bah)" and "kiki (pronounced KEE-kee)". The grid and control words have a Zipf frequency below 2 in English (wordfreq). Round class: bouba, maluma, bomu, lobu. Spiky class: kiki, takete, keti, tepi. |
| Drawings | Muse Image 1.0: *"A simple black outline drawing of a shape called '<word>'. One shape only, no text."* (the no-name prompt drops "called '<word>'"). Separate calls of n = 4: 12 pictures per word, 8 per spelling variant, 236 in all. All 236 were checked by eye on a contact sheet. None showed letters, so none were excluded. Four "tupo"s were pins, much like the Andean *tupu* shawl pin. |
| Roundness | (a) **Solidity**: area divided by convex-hull area of the largest filled shape. The drawing is filled by flooding the background from the edge (`plato_shapes.silhouette_mask`); every picture closed, so no SAM call was needed. (b) **Corners**: sharp convex corners, where the outline turns by at least 60° within 2% of the perimeter on each side. (c) **Human axis**: the projection of the DINOv2 CLS embedding (ink-cropped, as in Plato's Chair) onto the line from people's round drawings to their spiky ones. That is 400 Quick, Draw! "circle" and "cloud" drawings and 600 "star", "zigzag" and "lightning" drawings, scaled so round = 0 and spiky = 1. On this scale people's categories sit at circle −0.03, cloud 0.03, star 1.13, zigzag 0.99 and lightning 0.88. |
| Choice arm | 8 code-drawn pairs: a smooth blob with 4–6 soft lobes and an irregular star with 7–10 spikes, after Bremner et al. (2013). Each pair is shown both ways (round left, round right). **Glimmer** (FP8, one L40S): *"There are two shapes in this picture, one on the left and one on the right. Which one is "<word>"? Answer with one word: left or right."* p(left) vs. p(right) comes from the first answer token, summed over case and spacing variants, and is averaged over the two placements. Also a **no-picture version**: the two shapes are described in words as A and B, in both orders. **Spark** (minimal reasoning, default sampling): the picture question for the 16 test and control words, 3 pairs × 2 placements. |
| People | Published numbers only, from Ćwiek et al. (2022), *Phil. Trans. R. Soc. B* 377: 20200390 (CC BY 4.0). Their OSF data carry no licence, so nothing here is computed from them. 917 people in 25 languages heard "bouba" and "kiki" spoken and picked one of two shapes. **Both trials matched:** 72% (95% CrI 56–82%). **English:** about 0.84 [0.71, 0.93] posterior, 0.88 descriptive, n = 41, read from their Fig. 4. **First trials:** bouba → round about 0.82 [0.68, 0.90] and kiki → spiky about 0.68 [0.53, 0.78], read from Fig. 6. |
| Statistics | **Pairwise contrasts:** mean difference, Cohen's d and probability of superiority (AUC), with 4,000-sample bootstrap CIs over pictures. **Class and grid effects:** a two-level bootstrap (words, then pictures within words). Positive always means "the expected way" (spikier for spiky-sounding words; more round choices for soft or rounded words). |

## Findings: drawings

| Word | Solidity (1 = blob) | Sharp corners | Round→spiky axis |
|---|---|---|---|
| bouba | 0.92 [0.88, 0.95] | 0.6 | 0.12 [0.07, 0.17] |
| **kiki** | **0.55** [0.54, 0.57] | **9.3** | **0.80** [0.75, 0.85] |
| maluma | 0.94 [0.92, 0.95] | 0.5 | 0.17 |
| **takete** | **0.55** [0.54, 0.57] | **8.7** | **0.83** |
| bomu / lobu (soft, rounded) | 0.93 / 0.90 | 0 / 0 | 0.15 / 0.19 |
| bemi / limi (soft, unrounded) | 0.94 / 0.96 | 0 / 0 | 0.18 / 0.14 |
| kotu / tupo (hard, rounded) | 0.95 / 0.85 | 0 / 1.3 (pins) | 0.21 / 0.32 |
| **keti / tepi** (hard, unrounded) | **0.96 / 0.98** | **0 / 0** | 0.25 / 0.19 |
| fana, hasa, nafa, safa | 0.93–0.96 | 0–0.4 | 0.20–0.27 |
| no name ("a shape") | 0.75 [0.65, 0.86] | 3.7 | 0.75 [0.57, 0.92] |
| b-o-u-b-a / "bouba (pronounced BOO-bah)" | 0.89 / 0.92 | 0 / 0 | 0.23 / 0.13 |
| k-i-k-i / "kiki (pronounced KEE-kee)" | 0.57 / 0.55 | 10.4 / 9.9 | 0.71 / 0.79 |

| Contrast | Solidity | Corners | Axis |
|---|---|---|---|
| kiki vs. bouba: difference | 0.37 [0.32, 0.40] | 8.8 [7.3, 9.9] | 0.69 [0.61, 0.76] |
| kiki vs. bouba: AUC | **1.00** [1.00, 1.00] | 0.997 [0.98, 1.00] | **1.00** [1.00, 1.00] |
| kiki vs. bouba: Cohen's d | 7.1 | 5.1 | 7.3 |
| takete vs. maluma: difference (AUC) | 0.39 [0.36, 0.41] (1.00) | 8.2 [7.3, 9.0] (1.00) | 0.65 [0.58, 0.72] (1.00) |
| spiky vs. round class (4 words each, two-level) | 0.16 [−0.05, 0.37] | 4.2 [−0.3, 8.9] | 0.36 [0.06, 0.67] |
| grid: consonant effect (hard − soft) | 0.00 [−0.05, 0.06] | 0.3 [0.0, 1.2] | 0.08 [0.01, 0.16] |
| grid: vowel effect (unrounded − rounded) | **−0.05** [−0.10, −0.01] | −0.3 [−1.2, 0.0] | −0.02 [−0.12, 0.06] |

- **Famous words, total separation.** The kiki and takete pictures are stars with about nine points, and the bouba and maluma pictures are clouds, quatrefoils and (for maluma) pears.
- **New words, no separation.** Hard consonants made no difference to solidity, and the vowel effect points the wrong way: unrounded-vowel words were drawn a little *rounder*. The small consonant effect on the human axis comes from tupo's pins, not from spikes.
  - The class contrast exists only because kiki and takete are in the spiky class. Its CI includes zero on solidity and corners.
- **A name rounds the shape.** With no name, "a shape" came out as five-pointed stars, pentagons and hexagons (solidity 0.75, axis 0.75). Every made-up name except kiki and takete (neutral fana and safa included) gave a soft blob (solidity 0.93–0.98).
- **Spelling and sound hints change nothing.** Spelling the word out (k-i-k-i) or adding how to say it kept kiki a star and bouba a blob. Whatever links the word to the shape survives letter-by-letter spelling.

## Findings: choices

| Word | Glimmer, picture: p(round) | Glimmer, words only | Spark, picture (round of 6) |
|---|---|---|---|
| bouba | 0.70 [0.68, 0.72] | 0.73 | 6 |
| kiki | 0.51 [0.47, 0.54] | 0.38 | 0 |
| maluma | 0.65 | 0.81 | 6 |
| takete | 0.50 | 0.36 | 0 |
| bomu, lobu, bemi, limi (soft) | 0.55–0.61 | 0.53–0.81 | 6, 6, 6, 6 |
| kotu, tupo, keti, tepi (hard) | 0.54–0.56 | 0.44–0.62 | 2, 4, 0, 1 |
| fana, hasa, nafa, safa | 0.53–0.56 | 0.51–0.55 | 6, 6, 6, 6 |

| Match rate | Value | People (Ćwiek et al. 2022) |
|---|---|---|
| Both bouba and kiki matched | **Spark 100%** (6 of 6 paired trials); **Glimmer 35%** [31, 39] (chance that two independent answers both match) | 72% [56, 82]; English about 84% |
| Mean of p(round \| bouba) and p(spiky \| kiki) | Glimmer picture 0.60, words 0.68; Spark 1.00 | first trials: (0.82 + 0.68) / 2 = 0.75 |
| Grid: consonant effect on choosing round | **Spark +71 points** [42, 96]; Glimmer +2 [0.1, 5]; Glimmer, words +8 [−8, 26] | consonants matter more than vowels (Fort, Martin & Peperkamp 2015) |
| Grid: vowel effect on choosing round | Spark +21 [−33, 75]; Glimmer +1 [−1, 4]; Glimmer, words +9 [−8, 25] | |

- **Glimmer's position bias.** Glimmer's normalized p(left) averaged 0.52, and averaging over placements cancels it. Its top first token was always "left" or "right" (238 and 162 of 400), but those two carried only 0.46–0.85 of the first-token probability (mean 0.64).
- **Spark's neutral words.** Spark gave the round shape to all four neutral words. Its "default" is round unless a word has hard consonants.

## Predictions (pre-registered)

| Prediction | Result |
|---|---|
| P1. Kiki spikier than bouba on all three measures, with the AUC CI above 0.5 for at least two | **Yes**, all three (AUC 1.00, 0.997, 1.00). |
| P2. Takete spikier than maluma | **Yes** (AUC 1.00 on all three). |
| P3. Spiky class spikier than round class on solidity, with the CI excluding 0 | **No:** 0.16 [−0.05, 0.37]. It is carried by kiki and takete alone; keti and tepi were drawn round. |
| P4. Consonant and vowel effects both point the spiky way, consonant ≥ vowel | **No** for drawings: consonant 0.00, vowel −0.05 (the wrong way). **Yes** for Spark's choices: consonant +71 points, vowel +21 (n.s.). |
| P5. Controls and baseline fall between the classes on solidity | **No.** The neutral words were as round as the round class (0.94 vs. 0.92). The no-name baseline was as spiky as the spiky-class mean (0.75 vs. 0.76): stars and polygons. |
| P6. Glimmer p(round \| bouba) > 0.5 and p(round \| kiki) < 0.5, match ≥ 72%; Spark the same | **Spark yes** (100%). **Glimmer no:** bouba 0.70, kiki 0.51; it matches both only 35% of the time. Without a picture it does better (kiki 0.38). |

## Caveats

- **Contamination.** Bouba/kiki and maluma/takete appear in thousands of documents about this very effect. The drawing result says Muse Image *knows* these words, not that it hears sounds. That is exactly why the grid words matter, and the grid says the sounds alone do nothing for the image model.
- **Letters, not sounds.** People heard spoken words; the models see only spellings. The spelling variants keep the letters, so they can't separate "knows the word kiki" from "k and i look angular". Hyphenated spelling still worked, which is consistent with knowing the word.
- **Small n.** 12 pictures per word and 6 Spark answers per word. Spark's 100% rests on 6 paired trials. The grid has two words per cell.
- **Corner count.** It also counts tight rounded lobes (one bouba "flower" scored 7). Solidity and the human axis don't have this problem, and they agree.
- **Glimmer's format.** Its "left/right" mass averaged 0.64, so some probability went to other first tokens. The text-only version suggests the picture-reading step is part of its weakness.
- **People's numbers.** The English figures are read from published figures, so they are approximate. People's both-trial match counts a person only if both trials match; for Glimmer we report the probability that two independent answers both match.

## Cost

| Item | Cost |
|---|---|
| Muse Image: 236 pictures | $2.36 |
| Muse Spark choice arm: 96 calls | $0.11 (ledger tag `plato_cratylus`) |
| SAM | not needed ($0) |
| Glimmer (lab GPU, about 1 minute) and DINOv2 (laptop) | $0 |

## Files

- **Code:** `metalesionlab/plato_cratylus.py`, `metalesionlab/plato_shapes.py`, `scripts/plato_cratylus_{generate,analyze,figures,web_export}.py`, and `scripts/plato_cave_glimmer.py choice` (the GPU part).
- **Derived statistics:** `public_data/plato_cratylus.json`.
- **Data** (pictures, Quick, Draw! renderings, embeddings, `results.json`) live outside the repository, in `PlatosChair/cratylus/`.
- **Figures** in `PlatosChair/cratylus/figures/`:
  - `bouba_kiki_wall.png` (12 boubas beside people's circles, 12 kikis beside people's stars, and 12 ketis and tepis)
  - `roundness_by_word.{png,svg}`
  - `choice.{png,svg}`
  - `all_words.png`
- **Page:** `/plato/cratylus`.

**Credits.**
- **People's shape choices:** Ćwiek, A., Fuchs, S., Draxler, C., et al. (2022). The bouba/kiki effect is robust across cultures and writing systems. *Phil. Trans. R. Soc. B*, 377, 20200390.
- **Classic findings:** Köhler (1929/1947); Ramachandran & Hubbard (2001); Bremner et al. (2013), the shapes; Fort, Martin & Peperkamp (2015), consonants vs. vowels.
- **Earlier work on AI models:** Alper & Averbuch-Elor (2023, NeurIPS) found a bouba/kiki effect in Stable Diffusion and CLIP; Verhoef et al. (2024) found it inconclusive in VLMs; Loakman, Li & Lin (2024).
- **Human drawings:** Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0.
- **Models:** Meta Muse Image 1.0, Muse Glimmer 30B, Muse Spark 1.3 and DINOv2.

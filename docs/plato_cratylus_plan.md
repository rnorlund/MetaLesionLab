# Plato's Cratylus: pre-registered plan

Written and committed on Oct 27, 2026, before any picture was drawn and before any model saw a choice.

## Question

In the *Cratylus*, Socrates asks whether names fit things by nature. People around the world match "bouba" to a round shape and "kiki" to a spiky one: 72% of 917 people in 25 languages matched both (Ćwiek et al. 2022). A text-trained model never hears a word, only spellings.

1. Does Muse Image still draw a "kiki" spiky and a "bouba" round?
2. Do the AIs pick the round shape for "bouba", and the spiky one for "kiki", as often as people do?

## Words

Code: `metalesionlab/plato_cratylus.py`.

| Group | Words | Pictures each |
|---|---|---|
| Classic | bouba, kiki, maluma, takete | 12 |
| Grid: soft consonants (b, m, l) × rounded vowels (o, u) | bomu, lobu | 12 |
| Grid: soft × unrounded vowels (i, e) | bemi, limi | 12 |
| Grid: hard consonants (k, t, p) × rounded | kotu, tupo | 12 |
| Grid: hard × unrounded | keti, tepi | 12 |
| Neutral controls (consonants from neither class, vowel a) | fana, hasa, nafa, safa | 12 |
| No-name baseline | "a shape" | 12 |
| Sound vs. spelling (exploratory) | b-o-u-b-a, k-i-k-i, "bouba (pronounced BOO-bah)", "kiki (pronounced KEE-kee)" | 8 |

- **Picking the grid words.** They are made-up words with a Zipf frequency below 2 in English and in five other Latin-script languages (wordfreq). "Kiki" is also a name and "Maluma" a singer. Those two are kept because they are the classic stimuli.
- **Round class:** bouba, maluma, bomu, lobu.
- **Spiky class:** kiki, takete, keti, tepi.

## Drawing arm

- **Prompt.** Muse Image (`muse-image-1.0`): *"A simple black outline drawing of a shape called '<word>'. One shape only, no text."* The baseline drops "called '<word>'".
- **Calls.** Each word gets separate calls of n = 4 (3 calls for 12 pictures, 2 for 8). That makes 236 pictures, about $2.36.
- **Filter.** Every picture is checked by eye on a contact sheet. Pictures that show any letters or text are excluded and counted. Nothing else is excluded.
- **Roundness**, measured three ways:
  - **(a) Solidity:** the area divided by the convex-hull area of the largest filled shape (1 = convex; a star is about 0.5). The drawing is filled by code, flooding the background from the edge after closing small gaps (`plato_shapes.silhouette_mask`). If code fails on a picture (the outline doesn't close), SAM 3.1 may supply the mask, at $0.0025 a call; otherwise the picture's solidity is reported as missing.
  - **(b) Corners:** the number of sharp convex corners on the outer contour, where the outline turns by at least 60° within 2% of the perimeter on each side. A blob scores 0 and a 5-pointed star 5.
  - **(c) Human axis:** position on a round-to-spiky axis in DINOv2 space (`facebook/dinov2-base`, CLS token, after the core experiment's ink crop).
    - The axis runs from the centroid of 400 Quick, Draw! round drawings (200 "circle", 200 "cloud") to the centroid of 600 spiky ones (200 each of "star", "zigzag" and "lightning"). Drawings are the first recognized ones, streamed with `plato.stream_quickdraw`, CC BY 4.0.
    - Each picture's embedding is projected onto the axis and scaled so the round centroid is 0 and the spiky centroid is 1.
- **Spikiness direction.** Lower solidity, more corners and a higher axis score all mean spikier.

## Choice arm

- **Shapes.** 8 code-drawn pairs: a smooth blob with 4–6 soft lobes and an irregular star with 7–10 sharp spikes, in the spirit of Bremner et al. (2013), the shapes Ćwiek et al. used. Each pair is shown side by side in black on white, twice: round on the left, then round on the right.
- **Muse Glimmer 30B.** *"There are two shapes in this picture, one on the left and one on the right. Which one is "<word>"? Answer with one word: left or right."*
  - The answer channel is pre-filled. We read p(left) and p(right) from the first answer token, summed over spelling and capitalization variants and normalized over the two.
  - p(round) is the probability of the round shape's side, averaged over the two placements, which cancels position bias. It is then averaged over the 8 pairs.
  - Words: all 21 words and spellings above, plus "b o u b a", "k i k i", BOUBA and KIKI.
- **Glimmer without a picture.** The two shapes are described in words and labeled A and B, in both orders; we read p(A) vs. p(B).
- **Muse Spark** (`muse-spark-1.3`, minimal reasoning, default sampling). The same picture question for the 12 test words and the 4 neutral controls, with 3 pairs × 2 placements per word (96 calls, about $0.25). Its answer is parsed for left/right.

## Measures and analyses

1. **Bouba vs. kiki** (12 vs. 12 pictures), for each roundness measure:
   - the mean difference (kiki − bouba, signed so that positive = kiki spikier);
   - Cohen's d;
   - the probability of superiority (AUC: the chance a random kiki picture is spikier than a random bouba picture);
   - each with a 4,000-sample bootstrap 95% CI over pictures.
2. **Takete vs. maluma:** the same.
3. **Spiky class vs. round class** (4 words each): mean difference with a two-level bootstrap CI (words, then pictures within words).
4. **Grid effects** (8 words, 2 per cell):
   - consonant effect = mean(hard cells) − mean(soft cells);
   - vowel effect = mean(unrounded cells) − mean(rounded cells);
   - each with a two-level bootstrap CI.
5. **Controls.** The neutral words and the no-name baseline, placed on the same scales.
6. **Choice.**
   - Per word: Glimmer's p(round) and Spark's share of round answers.
   - Match rate = the mean of p(round | bouba) and p(spiky | kiki); likewise for the classes.
   - Bootstrap CIs over pairs (Glimmer) or answers (Spark).
7. **Human comparison.** Published numbers only; the OSF data carry no licence. From Ćwiek et al. (2022):
   - 72% both-trial match overall (95% CrI 56–82%);
   - English about 0.84 [0.71, 0.93] (posterior, read from Fig. 4; descriptive about 0.88);
   - bouba → round about 0.82 and kiki → spiky about 0.68 (first trials, read from Fig. 6).

## Predictions

- **P1.** Kiki pictures are spikier than bouba pictures on all three measures: lower solidity, more corners, higher axis score. The AUC is above 0.5, with the CI excluding 0.5 for at least two of the three measures.
- **P2.** Takete is spikier than maluma, the same way.
- **P3.** The spiky class (kiki, takete, keti, tepi) is spikier than the round class (bouba, maluma, bomu, lobu) on solidity, and the CI excludes 0. This matters because the classic words are famous in the training text, so the made-up grid words test whether the effect generalizes.
- **P4.** Both the consonant and the vowel effect point the spiky way. Following human work (consonants matter more than vowels; Fort et al. 2015), we expect the consonant effect to be at least as large as the vowel effect. This is the weakest prediction.
- **P5.** Neutral controls and the baseline fall between the two classes on solidity.
- **P6.** In the choice arm, Glimmer gives p(round | bouba) > 0.5 and p(round | kiki) < 0.5, and its match rate is at or above people's 72%. Spark's answers do the same.

## Caveats known in advance

- The classic words appear in thousands of papers and web pages about this effect. So a "correct" answer from a model can come from reading about the effect, not from the sound. The grid words partly address this.
- A model may also draw letters' shapes: k and t are angular, o and b round. The spelling variants are a first, exploratory look at sound vs. spelling, not a clean test.

## Budget

- Muse Image: 236 pictures, $2.36.
- Spark: about 96 calls, about $0.25.
- SAM: only if code fails.
- In all, under $3. Glimmer and DINOv2 are free.

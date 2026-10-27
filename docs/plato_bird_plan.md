# Plato's Bird: pre-registered plan

Written and committed on 2026-10-27, before any AI answers were collected. Results go in `docs/plato_bird.md`.

## Question

Plato's Chair found that Muse Image *draws* the textbook chair. Does the AI also *think* in textbook examples? Asked to "name a bird", is it far more stuck on one answer than people are?

Wittgenstein argued that categories such as "game" have no definition, only family resemblances. Rosch showed that they still have best examples (prototypes). People's first answer in a category production task is a direct measure of that prototype pull, so we can compare the AI's pull with people's.

## Human data

- **Source.** Banks, B., & Connell, L. (2023). Category production norms for 117 concrete and abstract categories. *Behavior Research Methods*, 55(3), 1292–1313. https://doi.org/10.3758/s13428-021-01787-z.
- **Access and license.** Data from https://osf.io/jgcu6/. The OSF project and its Data component are licensed CC BY 4.0, checked on the OSF page on 2026-10-27.
- **Sample.** 117 categories (67 concrete, 50 abstract). 20 UK adults per category (13–20 first responses after the authors' exclusions). Participants named aloud as many members as they could in 60 s.
- **Files used.** Kept outside the repository, in `PlatosChair/bird/human_raw/`.
  - Trial-level data: each participant's first response (rank 1).
  - The referential item-level file:
    - production frequency (how many of the 20 named a member at all);
    - first-rank frequency;
    - typicality ratings (1–5, from separate raters).

**Human first-named distribution.**
- **Primary.** The rank-1 responses from the trial-level file, passed through **the same normalizer as the AI answers**.
- **Robustness.** The authors' referential first-rank frequencies, in which they merged same-referent names.

## AI data

**Prompt.** One user message, the same for both models:

> Name one member of the category {category}. Answer with one word or a short name only.

- Category names are written as in the norms, including UK spelling ("colour", "jewellery").
- There is one extra AI-only category, **game** (Wittgenstein's example), which the norms lack.

**Muse Spark (`muse-spark-1.3`).**
- Separate API calls with default sampling (no temperature set) and reasoning effort `minimal`, the project default for one-word answers.
- **Sample-size rule, fixed now.** We run a pilot of 1 call for each of 10 categories, and the pilot answers count toward the samples.
  - If the mean cost per call times 118 × 50 is at most $3.50, we take **50 samples per category**.
  - Otherwise we take **30**.
- Paid calls stop if the shared ledger passes $70, or if this experiment's own spend passes $5.

**Muse Glimmer 30B (FP8, self-hosted, free).**
- The reasoning channel is skipped by pre-filling the answer header, as in `metalesionlab/glimmer.py`.
- **(a) Logit distribution.** The next-token distribution at the first answer position is read from the logits. We expand the top first tokens (up to 64, or until 99% of the mass is covered), and each one is continued greedily to a full answer. Each answer's probability is its first token's probability. The covered mass is reported.
- **(b) Samples.** 50 samples per category at temperature 1.0, with top-k and top-p off.
- **Temperature sensitivity.** 50 samples each at T = 0.7 and T = 1.5, plus the logit distribution re-weighted to T = 0.5–2.0.

## Normalization

The function is `metalesionlab/plato_bird.py: normalize`, and the same function is applied to human and AI answers.

1. Keep the first line and the first item, and remove markdown, quotes, parentheticals and the leading articles (a, an, the).
2. Lowercase.
3. Singularize the head noun with a rule-based singularizer that has exception lists (glasses, scissors, gymnastics, ...).
4. Apply a small **synonym map**. It only merges names for the same referent:
   - spelling and US/UK variants: eggplant → aubergine, wrench → spanner, soccer → football;
   - number words → digits.

   The map is built by looking at the answer lists, reviewed by hand, and listed in full in the results document. It never merges different members into one.
5. Empty or refused answers are excluded and their rate is reported.

## Measures

These are computed per category, for people (first responses), Spark samples, Glimmer samples and the Glimmer logit distribution.

**Primary.** Compared at **equal n**: the AI's samples are subsampled without replacement to the category's human n, over 1,000 draws, and the results are averaged. Glimmer's logit distribution is sampled n times.
- **Dominance:** the share of the most common answer.
- **Entropy:** plug-in Shannon entropy, in bits.

**Secondary.**
- Distinct answers at equal n.
- **Match probability:** the unbiased chance that two answers agree, Σc(c−1)/n(n−1). It does not depend on n, so it uses all samples.
- **Prototype agreement:** whether the AI's top answer is among people's top first answers.
  - The human production frequency (% of 20) of the AI's top answer.
  - The human typicality rating of the AI's top answer.
- **Spearman correlations,** within each category over the members people produced:
  - the AI's answer probability against human production frequency;
  - the AI's answer probability against typicality.
  - Glimmer's logit distribution is the primary AI side here, since it gives every member a probability. Spark's sample shares are secondary.
  - We report the median rho over categories, with a bootstrap CI.
- **Coverage:** the share of AI answers that any of the 20 people produced at any rank.

## Statistics

- The unit is the category (117 with human data).
- AI minus human is reported as the mean difference over categories, with a 95% bootstrap CI (10,000 resamples of categories). We also report the number of categories where AI > human, and a Wilcoxon signed-rank p.
- Concrete vs. abstract: the difference in the mean AI − human gap, with a bootstrap CI that resamples within each domain.

## Predictions

1. **P1.** The AI's top answer takes a larger share than people's, and its entropy is lower. Mean AI − human dominance > 0 and entropy < 0, with CIs excluding 0. This holds for Spark and for Glimmer at T = 1.
2. **P2.** The gap is larger for abstract categories than for concrete ones.
3. **P3, the possible twist (as with the chairs).** For concrete categories with a strong prototype (fruit → apple, tool → hammer), people may be nearly as concentrated as the AI. That would make the gap mostly an abstract-category effect.
4. **P4, pictures.** For most of the 12 drawn categories, the member Muse Image draws most often is the member Spark names most often.

Each prediction is reported either way.

## Pictures

**Generation.**
- Muse Image (`muse-image-1.0`) draws a fruit, a bird, a vegetable, a vehicle, a musical instrument, a game, a sport, a tool, a flower, a dog, a fish and a piece of furniture.
- The prompt is the Plato's Chair doodle prompt (`plato.STYLES["doodle"]`).
- Each category gets 12 pictures, from 3 separate calls of n = 4: 144 pictures, $1.44.

**Labels.** Each picture is labeled with the member it shows:
- Glimmer (free text, greedy, free) answers *"Someone was asked to draw {a fruit}. Which {fruit} is in this drawing? ... Answer with one word or a short name only."*
- Muse Spark (vision, minimal reasoning) answers the same question as a second opinion.
- Labels go through the same normalizer.

**Comparison.** The drawn top member against:
- Spark's named top member;
- Glimmer's named top member;
- people's top first answer.

"a dog" is compared with the norms category "breed of dog", and "a piece of furniture" with "furniture". "a game" has no human norm.

## Deliverables and limits

- Derived statistics only go into the repo (`public_data/plato_bird.json`), with the CC BY 4.0 attribution.
- Raw human rows, AI answers and pictures stay in `PlatosChair/bird/`.
- This experiment's spend is capped at $5.

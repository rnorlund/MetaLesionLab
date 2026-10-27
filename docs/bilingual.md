# Does damage hurt Spanish more than English? A controlled test

- **First measured** on **Oct 26, 2026**, on 20 pictures.
- **Rerun on Oct 27** on **100 new pictures**, with the same plan, as a pre-registered replication:
  [`replication_plan.md`](replication_plan.md), results in [`replication.md`](replication.md).
- **Setup:** Muse Glimmer 30B (decoder in FP8), one NVIDIA L40S per run.

The numbers below are from the **n = 100 rerun** (`runs/bilingual_core100/results.json`, figures
in `runs/bilingual_core100/figures/`). The first run's numbers are kept in
[First run (n = 20)](#first-run-n--20) at the end. Both runs were coded with the same, current
coder. The generated files are not in the repository; the commands to rebuild them are at the end.

## Verdict

**The test supports the effect, it is large, and it replicated on 100 new pictures.**

- **The setup.** The same pictures and the same damage were used in each language, with a matched
  one-word instruction.
- **The result.** Damage cost Spanish naming 28 more percentage points than English naming, on
  average.
  - The 95% confidence interval runs from 26 to 30 points. The first run, on 20 pictures, gave 28
    [23, 32].
  - All 96 testable pictures fared worse in Spanish than in English, and none fared better.
- **Other languages.** French (+32) and Portuguese (+33) show the same pattern, slightly stronger.
- **Switching.** When the damaged model failed in another language, it often answered in English.
  - The picture's English name came out on 11% of damaged Spanish trials.
  - The reverse, another language's name on an English trial, happened on 0.16%.
- **The intact model.** Its "word lens" suggests why. On Spanish, French and Portuguese trials, the
  English name comes up first in the middle-to-late layers, on 84–86% of the pictures that can be
  tested. The asked-for word takes over only in the last few layers.

The pattern echoes a common clinical observation in bilingual aphasia: the less dominant language
is often more affected, and speakers may slip into the stronger one. That is an analogy, not
evidence about brains. The caveats are at the end. The biggest ones:

- it is one model, with one style of picture;
- the explanation from the word lens is consistent with the data but not proven.

## Why a new test

Earlier runs hinted at the effect, but they could not show it:

- **Noise on decoder layers 40–47 (×2.18):** English stayed at 16/20 but Spanish fell to 3/19
  (`runs/lesion/demo_en`, `demo_es`).
- **"What can I cut?":** Spanish broke first, and cut models answered Spanish prompts in English
  ("Umbrella" for *paraguas*).
- **With its naming units ablated:** the model answered "The object is a cat" for *gato*.

Those runs differed in more than language:

- Each language had **different drawings**.
- The prompts were **worded differently**: the English one did not name a language, and the
  Spanish one was longer and stricter.
- The noise was **scaled by each set's own reference statistics**.

Any of these could make Spanish look more fragile.

## Design

### What was held constant

| | Earlier runs | This test |
|---|---|---|
| Pictures | different drawings per language | the same drawings in every language: the 100 kept pictures of `core100_en` (first run: the 20 of `demo_en`) |
| Instruction | worded differently per language | one structure, written natively in each language: it names the language and asks for a single word with no article |
| Damage | noise scaled by each set's own statistics | **one lesion spec per condition**, applied fresh for each language. Mean and noise values come from reference statistics pooled over all four prompts. Noise restarts from the same seed in every language. |
| Scoring | Model Lab rules | the same rules (`naming_errors.classify`, first attempt, carrier phrase removed), with accepted names chosen to be equally lenient in every language |

| Variant | Instruction |
|---|---|
| English | Say the name of the object in a single word in English. Just the word, no article. |
| Spanish | Di el nombre del objeto con una sola palabra en español. Solo la palabra, sin artículo. (the Model Lab's tested wording) |
| French | Dis le nom de l'objet en un seul mot en français. Seulement le mot, sans article. |
| Brazilian Portuguese | Diga o nome do objeto com uma só palavra em português. Só a palavra, sem artigo. |
| Spanish, English instruction (control) | Say the name of the object in a single word in Spanish. Just the word, no article. |

The control variant asks for Spanish in English. It separates two questions: is the problem
understanding a Spanish instruction, or producing a Spanish word?

### Pictures and names

- **Pictures.** `scripts/wordlists/core100.json` holds 100 concrete nouns in nine categories,
  including the 20 demo words.
  - Muse Image drew them as line drawings, checked by SAM 3.1 and Muse Spark and then by eye.
  - The Spanish, French and Portuguese sets reuse the English pictures
    (`scripts/language_sets.py`).
- **Names.** Each language's target and accepted alternates come from the word table, chosen on the
  same principle in every language: synonyms, regional names, short forms, spellings.
  - Three pictures got the drawn subtype's name in every language after the intact pilot and
    before any lesion: sneaker for the shoe, molar for the tooth, crescent for the moon.
  - The demo pictures' alternates (`EXTRA_NAMES` in `metalesionlab/bilingual.py`) still apply. For
    example, the kettle drawing also reads as a teapot, so *teapot*, *tetera*, *théière* and *bule*
    are all accepted.
- **English spellings are not accepted in other languages.** An alternate spelled like an English
  name counts as an English answer: Spanish and Portuguese *molar*, Portuguese "cactus". Otherwise
  an English answer would score as correct in one language and not in another.
- **Names identical in two languages are kept as targets.** *cactus* is the same word in Spanish,
  French and English, and *igloo* in French and English. These answers can't be told apart by
  language.

### Lesions

The plan was fixed before any lesioned non-English result was seen, and reused unchanged for the
rerun. Doses come from the earlier English severity runs: mild, moderate and severe in English.

| Family | Conditions | Seeds |
|---|---|---|
| Gaussian noise on every head and neuron of a band of 8 decoder layers | 7 bands: 0–7, 8–15, 16–23, 24–31, 32–39, 40–47, 48–51; 3 doses each, from ×0.7 to ×10 the unit's sd | 3 |
| Noise on the vision tower's output | ×3.83, ×4.22, ×4.6 | 3 |
| Naming-localizer mean ablation (`naming_en`, from English held-out drawings) | MLP neurons at the stored fractions 0.177, 0.297 and 0.339; attention heads at 0.367 and 0.404 | deterministic |
| Matched random-unit controls for each localizer lesion | same count of units in the same layers | 2 control seeds |
| Pruned models from "What can I cut?" (layers skipped, which matches real removal) | layers 27, 30, 47; the 5-layer cut 10, 27, 30, 35, 47 | deterministic |
| Robustness: noise and mean values from English-only or Spanish-only statistics | 4 of the conditions above, in English and Spanish | 3 |

- **Size:** 41 main lesion conditions; with their seeds, 89 lesioned runs per language.
- **Trials:** each run names 100 pictures, so each language has 8,900 lesioned trials.
- **Compute:** the test made 490 runs in all, split over axon-server01 (2.3 h) and axon-server03
  (2.6 h), with identical reference statistics.
- **Reference statistics:** pooled over the 100 held-out drawings × 4 prompts (400 trials).

### Measures

- **Accuracy:** the first attempt, coded by `classify` with no meaning judge. "Correct" never
  depends on the judge.
- **Language of the answer.** Each word of the first attempt is assigned to a language:
  - the picture's names in each language decide first;
  - otherwise wordfreq decides: a word leans to a language when it is common there and at least 10
    times more frequent there than in the other;
  - a short non-word that starts only one language's name also leans to that language (e.g. "Umb").

  Format labels ("Answer:"), words from the trial's own instruction (echoes) and chat-format leaks
  don't count as language.
- **English answer:** a first attempt whose words lean only to English, on a non-English trial.
- **English name:** an English answer that is the picture's English name ("Umbrella" for
  *paraguas*). The mirror measure on English trials is the picture's name in another language
  ("pina").
- **Word lens:** after every decoder layer, the probability of the first token of each language's
  name, plus the lens's top guess.
  - Pictures whose English and target names share a first token are dropped (cactus, helicopter and
    the like).
  - That leaves 86 pictures for Spanish, 81 for French and 84 for Portuguese.

### Pre-specified primary measure

The primary measure was written into `scripts/bilingual_analyze.py` before any lesioned non-English
result was seen.

- **The extra drop.** For each language, take the accuracy drop from intact in that language, minus
  the drop in English, on the same pictures. Average it over all 41 lesion conditions and their
  seeds.
- **Which pictures.** Only pictures named correctly by the intact model in both languages: 96 for
  Spanish, 100 for French, 97 for Portuguese.
- **The 95% CI** comes from a bootstrap over pictures (the same resample for every condition) and
  over seeds within each condition: 10,000 resamples.
- **The p-value** is a sign-flip permutation test over pictures.

Some measures were added or changed after the first run's data were seen. They describe the result;
they were not used to choose it.
- **The two narrower switch measures** (the picture's own name in the wrong language, and the wrong
  language after the first attempt) were added to separate real switches from garbled text.
- **The word-lens measures** (top guess, p ≥ 0.05) replaced a planned "English above target at any
  probability" share. In layers 0–37 both probabilities are about 10⁻⁸, so that share was coin-flip
  noise.

All of them were then fixed for the rerun.

## Results (n = 100)

### 1. The intact model is near ceiling in every language

| | English | Spanish | French | Portuguese | Spanish, English instruction |
|---|---|---|---|---|---|
| Correct of 100 | 100 | 96 | 100 | 97 | 97 |
| The misses | none | tooth → "Molar", shell → "caracol", drum → "Batería", igloo → "Igloo" | none | acorn → "Boleado", shell → "Caracol", drum → "Bumbo? Não, snare. Tambor" | shell → "caracol", drum → "bombo", igloo → "igloo" |
| Mean p(target's first token), last layer | 0.94 | 0.92 | 0.91 | 0.89 | 0.96 |

Two of the intact Spanish misses are English-identical answers: "Igloo" for *iglú*, and "Molar",
which is also a Spanish word.

### 2. Primary result: damage costs other languages more than English

| Language | English accuracy, lesioned | Language accuracy, lesioned | Extra drop vs English [95% CI] | Pictures worse / better than English | p |
|---|---|---|---|---|---|
| Spanish | 0.71 | 0.42 | **+0.28** [+0.26, +0.30] | 96 / 0 (n = 96) | < 0.0001 |
| French | 0.70 | 0.38 | **+0.32** [+0.30, +0.35] | 100 / 0 (n = 100) | < 0.0001 |
| Portuguese | 0.71 | 0.38 | **+0.33** [+0.31, +0.35] | 97 / 0 (n = 97) | < 0.0001 |
| Spanish, English instruction | 0.71 | 0.40 | **+0.31** [+0.29, +0.33] | 97 / 0 (n = 97) | < 0.0001 |

- **All 100 pictures, intact misses included:** Spanish +0.25 [+0.21, +0.28], with 96 pictures
  worse and 4 better.
- **Condition by condition:**
  - Spanish was worse than English in **39 of 41** conditions, tied in 1 and better in 1.
  - The exception was noise at layers 0–7 ×1.0: −0.10 [−0.22, +0.02], a CI that includes zero.
  - In 33 conditions the CI excludes zero, and every one of them is Spanish worse.
- **French:** 40 worse, 0 better, 37 reliable.
- **Portuguese:** 40 worse, 1 better (the same ×1.0 band), 37 reliable.

![Accuracy, English vs other languages](figures/bilingual/accuracy_en_vs_lang.png)

`runs/bilingual_core100/figures/accuracy_en_vs_lang.png`: each point is one lesion condition.
Points below the diagonal mean the other language did worse than English under the same damage.

### 3. By lesion type

Each cell shows English vs the other language's accuracy, then the extra drop with its 95% CI.
Pictures are those correct intact in both languages.

| Lesion family | Spanish | French | Portuguese | Spanish, English instruction |
|---|---|---|---|---|
| Noise, layers 0–7 | 0.78 / 0.63, +0.15 [+0.10, +0.20] | 0.77 / 0.57, +0.21 [+0.15, +0.27] | 0.77 / 0.62, +0.15 [+0.10, +0.21] | 0.78 / 0.65, +0.13 [+0.08, +0.18] |
| Noise, layers 8–15 | 0.78 / 0.59, +0.19 [+0.14, +0.23] | 0.78 / 0.55, +0.22 [+0.18, +0.27] | 0.78 / 0.59, +0.19 [+0.15, +0.23] | 0.78 / 0.52, +0.26 [+0.22, +0.30] |
| Noise, layers 16–23 | 0.55 / 0.25, +0.30 [+0.24, +0.36] | 0.54 / 0.20, +0.34 [+0.28, +0.40] | 0.54 / 0.27, +0.27 [+0.21, +0.33] | 0.55 / 0.03, +0.52 [+0.47, +0.57] |
| Noise, layers 24–31 | 0.63 / 0.12, +0.51 [+0.44, +0.57] | 0.62 / 0.10, +0.52 [+0.45, +0.58] | 0.63 / 0.18, +0.45 [+0.39, +0.50] | 0.63 / 0.03, +0.59 [+0.53, +0.65] |
| Noise, layers 32–39 | 0.53 / 0.08, +0.45 [+0.38, +0.51] | 0.52 / 0.08, +0.44 [+0.37, +0.51] | 0.52 / 0.06, +0.46 [+0.40, +0.53] | 0.52 / 0.08, +0.45 [+0.37, +0.52] |
| Noise, layers 40–47 | 0.48 / 0.06, +0.41 [+0.34, +0.48] | 0.48 / 0.05, +0.43 [+0.36, +0.49] | 0.48 / 0.04, +0.44 [+0.38, +0.50] | 0.48 / 0.06, +0.42 [+0.35, +0.48] |
| Noise, layers 48–51 | 0.82 / 0.58, +0.23 [+0.16, +0.31] | 0.81 / 0.53, +0.28 [+0.21, +0.35] | 0.82 / 0.51, +0.32 [+0.25, +0.39] | 0.82 / 0.60, +0.22 [+0.16, +0.29] |
| Noise, vision tower | 0.61 / 0.44, +0.17 [+0.10, +0.24] | 0.61 / 0.40, +0.21 [+0.14, +0.28] | 0.62 / 0.45, +0.16 [+0.09, +0.23] | 0.62 / 0.55, +0.07 [−0.00, +0.14] |
| Naming localizer, MLP mean | 0.76 / 0.17, +0.59 [+0.52, +0.65] | 0.75 / 0.09, +0.66 [+0.60, +0.71] | 0.76 / 0.11, +0.64 [+0.58, +0.70] | 0.76 / 0.13, +0.63 [+0.56, +0.69] |
| Random MLP units, matched | 0.90 / 0.66, +0.23 [+0.18, +0.28] | 0.89 / 0.60, +0.29 [+0.24, +0.35] | 0.90 / 0.56, +0.33 [+0.28, +0.38] | 0.90 / 0.64, +0.26 [+0.21, +0.31] |
| Naming localizer, heads mean | 0.38 / 0.00, +0.38 [+0.30, +0.45] | 0.38 / 0.00, +0.38 [+0.30, +0.46] | 0.38 / 0.00, +0.38 [+0.31, +0.45] | 0.38 / 0.01, +0.37 [+0.30, +0.45] |
| Random heads, matched | 0.79 / 0.71, +0.08 [+0.02, +0.15] | 0.78 / 0.61, +0.17 [+0.10, +0.23] | 0.79 / 0.48, +0.31 [+0.25, +0.38] | 0.79 / 0.67, +0.12 [+0.06, +0.18] |
| Pruned (2 cuts) | 0.99 / 0.90, +0.09 [+0.04, +0.14] | 0.98 / 0.89, +0.10 [+0.04, +0.16] | 0.98 / 0.85, +0.13 [+0.08, +0.20] | 0.99 / 0.88, +0.11 [+0.06, +0.16] |

**Where the gap is largest.** Noise on the middle and late decoder (layers 24–47) leaves English at
about half its pictures and the other languages at almost nothing.

**Where it is smallest:**
- the pruned models, about one picture in ten;
- noise on the vision tower, which damages the input before any language processing.

With 100 pictures, every family's gap now excludes zero, except the vision tower when Spanish is
asked in English: +0.07 [−0.00, +0.14].

**The naming localizer.** It was built from English trials and spares English at its mildest dose:
- **MLP fraction 0.177:** English stays at 99/100, but Spanish falls to 40/100, French to 22/100
  and Portuguese to 27/100.
- **Matched random units:** Spanish keeps 86/100 and 77/100.
- **The heads localizer:** every non-English answer turns into English narration ("The user asks:
  ...") and scores 0, while English keeps 56% and 20% at the two doses.

**The original observation.** The condition from the original observation (noise on layers 40–47,
×2.18) replicates under the controlled design:
- English 0.69 [0.61, 0.77] vs Spanish 0.12 [0.07, 0.18], averaged over 3 seeds;
- French 0.10 and Portuguese 0.08.

### 4. Dose-response

![Dose-response](figures/bilingual/dose_response.png)

**Mild doses.** At the mildest doses (bands 0–7 and 8–15 at ×0.7), every language stays at or near
ceiling (0.94–0.99).

**×1.0.** At the next step the gap is small or reversed:
- layers 0–7: English 0.67, Spanish 0.76, Portuguese 0.75. This is the one reversal, seen in both
  runs.
- layers 8–15: English 0.89, Spanish 0.78, French 0.68, Portuguese 0.70.

**Stronger doses.** One step further (×1.4), the other languages collapse while English degrades
gradually:
- layers 0–7: English 0.66, Spanish 0.11;
- layers 8–15: English 0.46, Spanish 0.03.

**Bands 24–47.** Even the mildest dose tested leaves English at 0.69–0.74 but drops the other
languages to 0.08–0.39.

So the other languages don't degrade in proportion to English. Once the damage is past a threshold,
they fall off a cliff that English doesn't reach.

### 5. Switching into English

![Language switching](figures/bilingual/switch_rate.png)

Pooled over all lesions, 8,900 trials per language:

| | Spanish | French | Portuguese | Spanish, English instruction | Reverse: English trials |
|---|---|---|---|---|---|
| First attempt in English (other language on English trials) | 23.6% [22.5, 24.8] | 17.9% [16.8, 19.1] | 20.4% [19.5, 21.5] | 36.3% [35.0, 37.6] | 1.2% [0.8, 1.6]* |
| The picture's own name in the wrong language | 10.7% [9.6, 11.9] | 8.2% [7.1, 9.3] | 7.2% [6.3, 8.1] | 22.2% [20.9, 23.5] | **0.16%** [0.03, 0.39] (14 of 8,900)† |
| Share of errors that are English answers | 34% [33, 36] | 26% [25, 28] | 27% [26, 28] | 55% [53, 56] | not applicable |
| Mixed answers (words of both languages) | 1.8% | 2.0% | 1.8% | 2.5% | 0.5% |
| The wrong language after the first attempt (e.g. "anclaría … Wait object is anchor") | 20.2% | 14.9% | 16.2% | 20.7% | 0.07% |

- \* **The detector's noise floor.** On English trials, most detector hits are garbled letter
  strings, where single letters happen to lean to French or Portuguese.
- † **An upper bound.** The 14 include near-misses of the English word that the sound rules file
  under another language: "giraf…? Actually giraffe", "artichoe".
- **The clean comparison** is the picture's own name in the wrong language: 11% one way, 0.16% the
  other.

**Two kinds of English answer:**
- **The picture's English name**, sometimes in an English carrier phrase. Examples are "Umbrella"
  for *paraguas* and "The object is a cat" for *gato*. This is the earlier observation, and the
  model clearly recognized the object.
- **English narration of the task**, such as "The user asks for the name of the object in
  Spanish…". This is the voice of Glimmer's reasoning channel leaking into the answer. When the
  damaged model narrates, it almost always does so in English, whatever was asked:

  | Trials | Narration in English | Narration in the asked-for language |
  |---|---|---|
  | Spanish | 743 | 32 |
  | French | 564 | 18 |
  | Portuguese | 506 | 11 |

Under late-layer noise, the first attempt is often a garbled target-language word ("anclaría",
"cuperón"), followed by a self-correction in English: "Wait object is spoon".

### 6. Asking for Spanish in English

With the instruction in English, Spanish accuracy under damage is about the same as with the
Spanish instruction: 0.40 vs 0.42. Its extra drop is +0.31 [+0.29, +0.33].

So the deficit is in producing the Spanish word, not in reading a Spanish instruction. With the
English instruction the model falls back to English even more often: the picture's English name
appears on 22.2% of trials, against 10.7%.

### 7. Error types

Pooled over all lesions, % of 8,900 trials.
- **Without the meaning judge,** Semantic and Unrelated are merged: Spanish, French and Portuguese
  meaning relations are only judged by Muse Spark, which was not used here.
- **English meaning relations** come from WordNet.

| Code | English | Spanish | French | Portuguese | Spanish, English instruction |
|---|---|---|---|---|---|
| Correct | 67.0 | 37.3 | 34.2 | 34.9 | 34.3 |
| English name (switch) | not applicable | 10.0 | 8.3 | 7.3 | 22.0 |
| Other English (narration, English words) | not applicable | 11.7 | 9.1 | 10.2 | 13.9 |
| Mixed language | not applicable | 1.3 | 1.9 | 1.5 | 1.1 |
| Real word, Semantic or Unrelated | 4.7 | 5.6 | 7.7 | 8.8 | 5.6 |
| Formal | 3.9 | 5.6 | 4.2 | 5.4 | 5.3 |
| Mixed (meaning + sound) | 0.9 | 0 | 0 | 0 | 0 |
| Nonword | 5.1 | 8.4 | 6.9 | 7.4 | 8.3 |
| Neologism | 1.6 | 3.5 | 4.5 | 5.2 | 3.2 |
| Description (incl. narration and echoes in the same language) | 14.7 | 15.6 | 22.1 | 18.3 | 5.3 |
| No response | 2.2 | 1.1 | 1.2 | 0.9 | 1.1 |

The plain PNT codes hide the switches. An English answer on a Spanish trial gets coded as Formal,
Nonword or Neologism, because wordfreq lists many English words in Spanish too: "Umbrella" for
*paraguas* comes out as Formal. The table above codes switches first.

French gives more Descriptions because, under the MLP localizer lesion, it echoes its own
instruction ("Dis le nom de l'objet…") instead of switching.

### 8. Word lens: English comes first

![English pivot in the word lens](figures/bilingual/english_pivot.png)

**In the intact model, on Spanish trials** (86 testable pictures):

- **Up to about layer 37**, neither name has any probability.
- **From layer 38**, the English name rises:
  - its mean probability is about 0.3 from layer 40 to 44, peaking at 0.31 at layer 43;
  - it is the lens's top guess on 67% of trials at layer 40.
- **The Spanish name** becomes the top guess on most pictures only from layer 47, and ends at
  p = 0.92.
- **72 of the 86 testable pictures (84%)** have the English name as the lens's top guess at some
  layer before the Spanish name takes over. Two examples:
  - *pineapple* leads from layer 36 to 47, then *piña* takes over at 48;
  - *harp* leads from layer 40 to 47, then *arpa* takes over at 49.
- **French and Portuguese** look the same:
  - 69 of 81 and 72 of 84 pictures;
  - the share of trials with the English name on top peaks at 67–71% at layers 39–40;
  - the target leads from layer 47.

**On English trials**, the English name becomes the top guess on most pictures from layer 39, eight
layers earlier than the other languages' names. The Spanish name is the top guess at some layer on
only 2 of 86 intact English trials (2.3%), and 2.1% of lesioned ones.

**So the asked-for word appears later.** Answering in a language other than English takes a late
extra step: the model reaches the English name around layer 38–40 and only then turns it into the
asked-for word. That leaves Spanish, French and Portuguese answers only the last five layers as the
top guess. This matches the "latent English" finding of Wendler et al. (2024) for Llama 2.

**Under damage** (pooled over all lesions, Spanish trials):

| | Intact | Damaged |
|---|---|---|
| English name is the top guess at any layer | 84% of trials | 44% |
| Spanish name is the top guess at the last layer | 97% | 32% |
| Mean final p, Spanish name | 0.92 | 0.24 |
| Mean final p, English name | 0.02 | 0.06 |

For comparison, under the same damage the English name finishes on top on 50% of English trials.

**The lens barely predicts which pictures switch.** How strongly the intact lens favors English at a
picture (its peak English probability) hardly predicts that picture's switch rate under damage.
The Spearman correlations over 81–86 pictures are:

- Spanish 0.24 (p = 0.03, uncorrected, one of four tests);
- French 0.12 (p = 0.31);
- Portuguese 0.06 (p = 0.57);
- Spanish with the English instruction 0.14 (p = 0.18).

The English pivot is a property of most non-English trials, and it fits the fragility, but this test
doesn't show that a stronger pivot means more switching.

### 9. Robustness to the reference statistics

The same four conditions were run in English and Spanish with three sets of reference statistics.
The four conditions were noise at 0–7 ×1, noise at 40–47 ×3, the vision tower at ×4.22, and the
MLP localizer at 0.297.

| Reference statistics | Spanish extra drop [95% CI] |
|---|---|
| Pooled over all prompts (main analysis) | +0.30 [+0.24, +0.36] |
| English prompt only | +0.29 [+0.24, +0.35] |
| Spanish prompt only | +0.31 [+0.26, +0.36] |

The effect does not depend on which language the lesion was calibrated in.

## What this means

**In plain language:**
- **Same damage, worse outcome.** On the same pictures, a given amount of damage costs Glimmer far
  more in Spanish, French and Portuguese than in English. It held on 100 new pictures with the same
  size as on the first 20.
- **How it fails.** When the other language fails, the model often answers in English, either with
  the right name in English or by narrating the task in English. A damaged English answer almost
  never comes out in another language.
- **Why it might be so.** The intact model appears to reach the English name first, on most
  pictures, and translate it at the end. That makes a non-English answer depend on a late extra
  step, and when damage disrupts that step, English comes out.

**For aphasia research, this is an analogy to bilingual aphasia, not evidence about it.** Glimmer
behaves like a speaker whose dominant language is English. Its training data are presumably
English-heavy, as for most large models, but that wasn't checked here.

In bilingual aphasia:
- Outcomes vary, and parallel impairment of both languages is common.
- When the languages are affected differently, the language with higher pre-stroke proficiency and
  use tends to be better preserved (Kuzmina et al., 2019, meta-analysis).
- Pathological switching and mixing into another language is reported (Fabbro, 2001).

The model reproduces both the asymmetry and the direction of switching. It also gives a concrete,
inspectable mechanism, which brains do not: an English intermediate in the late layers.

## Caveats

- **100 pictures, one style.** The pictures are all Muse Image line drawings of concrete nouns.
  - The intervals account for which pictures happened to be chosen and for noise seeds.
  - They do not treat the 41 conditions as a sample of all possible lesions: the conditions are a
    fixed, hand-chosen set.
  - Per-family intervals are exploratory and not corrected for multiple comparisons.
- **One model, one precision.** Muse Glimmer 30B has its decoder in FP8. Other models, or BF16,
  could differ.
- **Prompt wording.** Each language has one instruction.
  - The prompts are matched in structure and intact accuracy is 96–100 of 100 everywhere, but
    wording effects under damage were not tested beyond the English-instruction control.
  - The English prompt names "English", unlike the Model Lab's English prompt.
- **Doses were chosen from earlier English runs.** They span mild to severe for English. A plan
  calibrated to Spanish would put more conditions where English is at ceiling. That would likely
  widen the gap, not close it.
- **No meaning judge.**
  - Accuracy, the switch measures and the extra-drop statistics don't depend on a judge.
  - Semantic vs Unrelated does, so those codes are merged here. Spanish, French and Portuguese
    meaning relations would need the Muse Spark judge.
  - The rerun's GPU runs made no Meta API calls.
- **The switch detector is rule-based** (word lists and frequencies).
  - It ignores format labels, instruction echoes and chat-format leaks.
  - On garbled letter strings it has a noise floor of about 1% (the reverse direction).
  - The picture-name measure is the cleaner one: 11% one way, 0.16% the other.
- **The word lens reads only first tokens.**
  - 14 to 19 pictures per language were dropped because their names share a first token with
    English.
  - Single-letter tokens such as "G" or "C" add some noise to the probabilities.
  - The lens shows where a name is decodable, not that the model uses it causally. The pivot was
    not ablated.
- **Pruning was done by skipping layers.** That matches real deletion exactly (checked in "What can
  I cut?"). The pruned models are only mildly impaired, so they say little either way.
- **Answers are typed, not spoken.** Scoring is the Model Lab's written-answer path, capped at 12
  new tokens.
- **No participant data was used.** Every picture was made by Muse Image for this project.

## First run (n = 20)

The first run (Oct 26) used the same plan on the 20 demo pictures. It is re-coded here with the
current coder, which gives the same numbers as first reported. Results:
`runs/bilingual_n20/results.json`; figures: `docs/figures/bilingual/n20/`.

| | First run (n = 20) | Rerun (n = 100) |
|---|---|---|
| Intact correct: English / Spanish / French / Portuguese / Spanish, English instruction | 20 / 19 / 20 / 19 / 19 of 20 | 100 / 96 / 100 / 97 / 97 of 100 |
| Extra drop, Spanish | +0.28 [+0.23, +0.32], 19 / 0 pictures | +0.28 [+0.26, +0.30], 96 / 0 |
| Extra drop, French | +0.33 [+0.28, +0.38], 20 / 0 | +0.32 [+0.30, +0.35], 100 / 0 |
| Extra drop, Portuguese | +0.35 [+0.30, +0.39], 19 / 0 | +0.33 [+0.31, +0.35], 97 / 0 |
| Extra drop, Spanish with English instruction | +0.30 [+0.25, +0.35], 19 / 0 | +0.31 [+0.29, +0.33], 97 / 0 |
| Spanish worse in how many of 41 conditions (CI excludes 0) | 35 (25) | 39 (33) |
| First attempt in English, Spanish trials | 23.8% [20.6, 27.6] | 23.6% [22.5, 24.8] |
| The picture's English name, Spanish / French / Portuguese | 11.0% / 7.6% / 9.0% | 10.7% / 8.2% / 7.2% |
| Reverse: another language's name on English trials | 0.1% (1 of 1,780: "pina") | 0.16% (14 of 8,900) |
| Lens: English name on top before the target, Spanish / French / Portuguese | 15/15, 14/15, 14/15 | 72/86, 69/81, 72/84 |
| Lens: peak share of trials with the English name on top | 87–93% (layers 39–40) | 67–71% (layers 39–40) |
| Original observation, layers 40–47 ×2.18: English vs Spanish | 0.70 vs 0.13 | 0.69 vs 0.12 |
| Robustness, Spanish extra drop with English-only / Spanish-only statistics | +0.29 / +0.26 | +0.29 / +0.31 |
| Lens vs switch rate, Spearman (Spanish / French / Portuguese) | 0.29 / −0.37 / 0.63 | 0.24 / 0.12 / 0.06 |
| Runs, time | 490 runs, 58 min on axon-server02 | 490 runs, 4.9 GPU-hours on two L40S |

## Reproduce

```bash
# GPU box: needs runs/sets/core100_{en,es,fr,pt} (or demo_*) and runs/localizers/naming_en.pt;
# NLTK_DATA with WordNet
export HF_HOME=$HOME/.cache/huggingface PYTHONPATH=$PWD
B="--prefix core100 --out runs/bilingual_core100"        # first run: no options (demo sets, runs/bilingual)
python scripts/bilingual_run.py stats $B   # reference statistics: pooled, English-only, Spanish-only
python scripts/bilingual_run.py pilot $B   # intact naming per language, printed per picture (prompt check)
python scripts/bilingual_run.py ids $B     # first-token ids of every name (tokenizer only)
python scripts/bilingual_run.py run $B     # the fixed plan, ~5 h on one L40S (split it with --only REGEX)

# Locally, after copying runs/bilingual_core100 back
python scripts/bilingual_analyze.py --prefix core100 --dir runs/bilingual_core100 --boot 10000
python scripts/bilingual_figures.py --dir runs/bilingual_core100
pytest tests/test_bilingual.py
```

Code: `metalesionlab/bilingual.py` (items, prompts, response language, word-lens readout,
statistics), `scripts/bilingual_run.py`, `scripts/bilingual_analyze.py`,
`scripts/bilingual_figures.py`.

## References

- Fabbro, F. (2001). The bilingual brain: Bilingual aphasia. *Brain and Language*, 79(2), 201–210.
- Kuzmina, E., Goral, M., Norvik, M., & Weekes, B. S. (2019). What influences language impairment in
  bilingual aphasia? A meta-analytic review. *Frontiers in Psychology*, 10, 445.
- Wendler, C., Veselovsky, V., Monea, G., & West, R. (2024). Do Llamas work in English? On the latent
  language of multilingual transformers. *ACL 2024*. arXiv:2402.10588.

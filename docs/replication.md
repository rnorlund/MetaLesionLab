# Replication at n = 100

The plan, conditions and criteria were fixed in advance in [`replication_plan.md`](replication_plan.md),
committed before any lesion ran on the new pictures. This page reports what happened, including
what did not replicate.

> **Status: in progress.** The progress notes below are updated as each step finishes.

## Progress notes

### Oct 27: pictures

- **Word list:** `scripts/wordlists/core100.json`, 100 words, including the 20 demo words.
- **English set** `core100_en`:
  - Built by Test Studio: 2 drawings per word, SAM 3.1 and Muse Spark checks.
  - The automatic checks kept 93 of 100.
  - In review were lemon, watermelon, comb, ear and nose: SAM found no object box, though the
    drawings are clear.
  - Kettle was also in review: both drawings are teapots, as in the first run.
  - Whistle was in review because neither drawing reads as a whistle.
- **Visual review** (`scripts/replication/core100_review.json`, applied by
  `scripts/review_set.py`). Every picture was checked by eye on the contact sheet, before any GPU
  run.
  - **Kept by eye:** lemon, watermelon, comb, ear and nose. SAM missed them; each drawing is one
    clear object, and Muse Spark named it correctly.
  - **Kettle kept:** teapot is an accepted name in every language, as in the first run.
  - **Flute:** switched to the drawing with keys. The automatic pick reads as a recorder.
  - **Redrawn:** whistle (one drawing read as a fishing lure, the other as a tube) and tie (both read
    as a ribbon or scarf). Redraw set `core100_fix`.
  - **Dropped: none.** All **100 pictures kept**.
- **Spanish, French and Portuguese sets:** the same 100 pictures, named from the word table
  (`scripts/language_sets.py`).
  - Muse Spark named them in each language and agreed with the table on 99 (Spanish), 98 (French)
    and 99 (Portuguese).
  - The disagreements were *caracol* for the spiral shell, and two more specific names for the
    drawn object: *bottine* (ankle boot) and *tênis* (sneaker).
- **Cost:**
  - English set: $3.19.
  - Redraws: $0.09.
  - Muse Spark name check: $0.25.
  - **Total: $3.53** of Meta API credit.

### Oct 27: intact naming, reference statistics, localizers

These ran on axon-server02 and axon-server01. None of them are lesions.

- **Intact Model Lab:**
  - English (`core100_en`): 99 of 100. Moon → "Crescent".
  - Spanish (`core100_es`, Spanish prompt): 95 of 100. Misses: *diente* → "Molar", *concha* →
    "caracol", *tambor* → "Batería", *zapato* → "zapatilla", *iglú* → "Igloo".
- **Intact bilingual pilot** (matched prompts, as coded on the GPU box):
  - English: 100. Spanish: 95. French: 99. Portuguese: 96. Spanish with the English instruction: 96.
- **Accepted names frozen** after these intact runs, **before any lesion run**.
  - Three additions, each made in every language, on one principle: the name of the drawn subtype.
    - **Shoe:** the drawing is a sneaker. Added sneaker and trainer; *zapatilla* and *tenis*;
      *basket* and *tennis*; *tênis*.
    - **Tooth:** the drawing is a molar. Added molar, *molar*, *molaire* and *molar*.
    - **Moon:** the drawing is a crescent. Added crescent, *creciente*, *croissant* and *crescente*.
  - **Not accepted:**
    - *caracol* for the shell (it is the snail item's name);
    - *Batería* or *bombo* for the snare drum (other drums);
    - "Boleado" (not a word).
  - As in the first run, the bilingual test drops an alternate spelled like an English name.
    Spanish and Portuguese *molar* therefore count as English-identical there, and the tooth stays
    an intact miss in the bilingual Spanish test. The Model Lab's Spanish test accepts *molar*.
  - **Intact after the freeze:**
    - Model Lab: English 100, Spanish 97.
    - Bilingual: English 100, Spanish 96, French 100, Portuguese 97, Spanish with the English
      instruction 97.
- **Reference statistics:**
  - Model Lab: from the 100 held-out drawings (`unit_stats_core100_en.pt`, `unit_stats_core100_es.pt`).
  - Bilingual test: pooled over the 4 prompts (400 trials), plus English-only and Spanish-only.
- **Localizers:** `naming_c100`, `visual_c100` and `language_c100`. The naming and visual ones come
  from the 100 held-out drawings; the language one is from 40 sentences.

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

### Oct 27: intact naming (GPU, axon-server02)

- **Spanish Model Lab test** (`core100_es`, Spanish prompt): 95 of 100.
  - Misses: *diente* → "Molar", *concha* → "caracol", *tambor* → "Batería", *zapato* →
    "zapatilla", *iglú* → "Igloo".
- **English:** pending. The first attempt failed because WordNet was missing on the server; it is
  being rerun.

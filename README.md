# Tippa Lingua

**Language tests for people and AI, in any language.** Build picture-based language tests in minutes, give them by voice, and score them automatically. Then run the same tests on Meta's open-weight model and see where language breaks.

Tippa Lingua has three tools that share one pipeline:

1. **Test Studio:** turns a word list into a picture test in your language.
   - **Muse Image** draws each item.
   - **SAM 3.1** checks that each picture shows exactly one clear object.
   - **Muse Spark** and **Muse Glimmer** check that the picture gets the intended name.
   - You can export printable cards, slides and a norms table.

   Standard picture tests are copyrighted and mostly English, and building a checked set by hand takes weeks.
2. **Scorer:** the test is given by voice, and every response is transcribed and coded.
   - **Muse Voice Transcribe** transcribes the responses.
   - Naming errors are coded with the standard categories (semantic, formal, mixed, nonword, neologism, unrelated, description, no response), and **Muse Spark** acts as an independent second rater.
   - A person reviews the codes, then exports.

   Tasks: picture naming, picture description and category fluency.
3. **Model Lab:** the same tests are given to **Muse Glimmer**, Meta's open-weight model.
   - You damage chosen parts of the model on purpose and watch aphasia-like errors appear.
   - A word lens shows the model's best guess at every layer.
   - A **Muse Spark** agent designs and runs the experiments and compares the results with published profiles from people with aphasia.
   - **What can I cut?** removes whole layers from the model, with your tests as the guardrail, and measures the real savings.

> Research and teaching use only. Tippa Lingua doesn't diagnose, and it doesn't give medical or treatment advice.

## Built during the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026)

Everything in this repository was written during the hackathon, starting at the kickoff on Oct 26, 2026. The commit history is the record.

| Date | Built |
|---|---|
| Oct 26 | Repo, data guard, Meta Model API client with spend ledger and budget cap |
| Oct 26 | Muse Glimmer in FP8 on a single L40S (32 GiB). Picture naming with the reasoning channel skipped. Word lens (logit lens) that matches the model's own output at the last layer |
| Oct 26 | Naming-error classifier (English and Spanish), with WordNet plus a Muse Spark judge for meaning. It passes 34 unit tests and agreed with the expected code on 19 of 20 live cases; the one miss was a mistake in the expected answer. |
| Oct 26 | Web app (FastAPI, plain HTML and JS): landing page, Test Studio with live build progress, review and exports (cards PDF, norms CSV, ZIP), Scorer with voice recording per picture and reviewer override, Model Lab with the word-lens chart and published human profiles. Per-visitor limits on every paid call. |
| Oct 26 | "What can I cut?": every Glimmer decoder layer skipped alone, a greedy removal path guarded by picture naming (English and Spanish) and perplexity on Muse Spark-written text, and real deletion of the chosen layers with measured size, memory and speed |

### Prior research context (not part of this submission)

The research question comes from the author's earlier work on simulating aphasia by lesioning a different vision-language model: Yang et al. (2026), "Lesioned multimodal language models reproduce aphasic picture-naming patterns", arXiv:2607.11621 (preprint). No code, data or results from that project are included here.

Built new during the hackathon:
- everything on Meta's models (Muse Glimmer, Muse Spark, Muse Image, SAM 3.1, Muse Voice Transcribe),
- the test-building and scoring tools for people,
- the word lens,
- the agent,
- any-language support.

## How scoring works

The decision order follows the Philadelphia Naming Test scheme (Roach et al., 1996):

1. No response.
2. Correct, allowing articles, plurals, modifiers and accepted alternate names.
3. Description: three or more words that don't name the target.
4. For a real word, check meaning and sound:
   - meaning only → **semantic**
   - sound only → **formal**
   - both → **mixed**
   - neither → **unrelated**
5. For a non-word: sounds like the target → **nonword**; otherwise → **neologism**.

| Check | English | Spanish |
|---|---|---|
| Real word? | Common in wordfreq and listed in the CMU Pronouncing Dictionary | Common in wordfreq |
| Sound | The PNT rule: shared first or last sound, shared stressed vowel, or two shared sounds anywhere. Sounds come from the CMU dictionary, or from spelling rules for non-words. | Same rule, adapted because nouns end in a gender vowel: a shared final vowel doesn't count |
| Meaning | WordNet first. Muse Spark judges associations (milk for cat). | Muse Spark judges every pair |

See `metalesionlab/naming_errors.py`. French, Brazilian Portuguese, Hindi and Mandarin Chinese have their own rules and measured results in [docs/languages.md](docs/languages.md).

## What can I cut?

Which parts of a model can go while the abilities you care about stay? The tests you build become the guardrail. `metalesionlab/compress.py` removes whole decoder layers from Muse Glimmer:

1. Each of the 52 layers is skipped alone. The result is scored by picture naming on the English and Spanish demo sets (39 pictures) and by perplexity on 150 plain sentences written by Muse Spark (`public_data/general_text_guard.json`).
2. A greedy path removes one layer at a time. A cut passes if naming stays at or above 95% of intact and perplexity rises by 10% or less. The other Muse Image picture of each word is held out to check each cut.
3. The chosen layers are deleted for real: the stock model code loads the smaller model from its own config. The outputs match the skip version exactly, and a saved copy reloads with identical logits.

Measured on one L40S with the FP8 decoder (`python scripts/what_can_i_cut.py scan|greedy|prune|reload|export`):

| Cut | Layers | Params | GPU memory | ms per picture | Tokens/s | Naming (39) | Held-out (38) | Perplexity |
|---|---|---|---|---|---|---|---|---|
| Intact | 52 | 29.78B | 32.04 GiB | 563 | 10.1 | 37 | 37 | 48.6 |
| Confirmed: 27, 30 | 50 | 28.81B (−3.3%) | 31.15 GiB (−2.8%) | 545 (−3.2%) | 10.5 (+3.9%) | 37 | 36 | 48.0 |
| Both guards: 27, 30, 47 | 49 | 28.32B (−4.9%) | 30.70 GiB (−4.2%) | 536 (−4.7%) | 10.7 (+6.1%) | 37 | 34 | 48.2 |
| Perplexity guard only (5 layers) | 47 | 27.36B (−8.1%) | 29.80 GiB (−7.0%) | 519 (−7.7%) | 11.2 (+10.5%) | 34 | 29 | 51.8 |
| 10 layers, no guard | 42 | 24.94B (−16.3%) | 27.54 GiB (−14.0%) | 472 (−16.1%) | 12.3 (+22.1%) | 24 | 24 | 67.6 |

The honest answer for this model is "not much". Two layers can go with no measurable loss, a saving of about 3%. Naming, not perplexity, was the binding guard: a perplexity check alone would allow five layers but lose three guard pictures and eight held-out ones, mostly in Spanish. The cut models often answered a Spanish prompt in English ("Umbrella" for *paraguas*), so language control broke before object recognition did. Full-attention layers mattered no more than sliding-window ones. Block influence, a cheap no-skip score, ranked layers poorly here. With about 20 pictures per language, one picture is about 5 points, so treat small differences as noise. Full results, including per-layer scores and the whole greedy path, are in `runs/compress/glimmer.json`.

## Meta models used

| Model | Role |
|---|---|
| Muse Glimmer 30B (open weights, self-hosted) | Test-taker in Model Lab, with lesions and the word lens; name-agreement check |
| Muse Image 1.0 | Draws test pictures |
| SAM 3.1 | Picture quality check |
| Muse Spark 1.3 | Name agreement, meaning judge, second rater, experiment agent |
| Muse Voice Transcribe 1.0 | Transcribes spoken responses |
| DINOv2 (`facebook/dinov2-base`, open weights, run locally) | Picture embeddings for the Plato's Chair experiment |

Every AI step uses a Meta model. The other resources are non-AI: WordNet, the CMU Pronouncing Dictionary and wordfreq.

## Experiment: Plato's Chair

Ask Muse Image to draw 16 chairs: are they all the same chair? We compared how spread out 35 concepts are in Muse Image's doodles and in people's drawings of the same words, using DINOv2 embeddings. The AI was more uniform than people for 34 of the 35 concepts, with a median spread ratio of 0.49. Method, results and caveats are in [`docs/plato.md`](docs/plato.md), and the code is in `scripts/plato_*.py`.

Human drawings come from the [Google Quick, Draw! dataset](https://github.com/googlecreativelab/quickdraw-dataset) (Google Creative Lab, CC BY 4.0). They are streamed at run time and never committed; `public_data/plato_concept_spread.json` holds only derived statistics.

## Data policy

- No data from real research participants is stored in, or processed by, this repository. Comparisons with people with aphasia use published group-level numbers, cited where they are used.
- A pre-commit hook blocks data files and large binaries outside `public_data/`. Enable it once per clone:

  ```bash
  git config core.hooksPath .githooks
  ```

- Audio sent to the Scorer goes to the Meta Model API. Use speaker codes, never names, and don't upload identifiable patient recordings unless your institution has approved that.

## Setup

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"          # Test Studio and Scorer
pip install -e ".[gpu]"          # Model Lab (needs a GPU with ~40 GB, e.g. one L40S)
export MODEL_API_KEY=...         # from dev.meta.ai
python scripts/smoke_meta_api.py # checks every Meta API we use
```

Every Meta API call is logged to `runs/costs.jsonl`, and new calls are refused once spending reaches `MLL_BUDGET_USD` (default $120).

## Web app

```bash
pip install -e ".[web]"
python -m metalesionlab.web --port 8000   # then open http://127.0.0.1:8000
```

Pages: `/` (home), `/challenge` (You vs. the AI), `/lab` (Model Lab), `/scorer` (Scorer), `/studio` (Test Studio). Every page has a guided Demo tour. The JSON API is documented at `/api/docs`. Voice scoring needs `ffmpeg` on `PATH` to read browser recordings.

- Data lives in `TOT_DATA_DIR` (default `runs/`): picture sets in `sets/`, description scenes in `scenes/`, precomputed lesion conditions in `lesion/`. The Model Lab shows a small, clearly labeled sample until `lesion/` has results.
- Every route that spends Meta API credit has a per-visitor daily limit: 3 set builds, 3 scenes and 60 scored responses by default (`TOT_LIMIT_BUILD`, `TOT_LIMIT_SCENE`, `TOT_LIMIT_SCORE`). The overall budget cap still applies; once it's reached, the app says so and browsing, review and exports keep working.
- For a public deployment, set `TOT_PUBLIC=1` so visitors can edit only the sets and scenes they built, `TOT_TRUST_PROXY=1` behind a reverse proxy, and `TOT_ALLOW_BUILDS=0` to turn off image generation.
- Scorer results stay in the browser until exported. The server doesn't store audio.

## License

Apache 2.0

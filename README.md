# Tippa Lingua

**Language tests for people and AI, in any language.** Build picture-based language tests in minutes, give them by voice, and score them automatically. Then run the same tests on Meta's open-weight model and see where language breaks.

Tippa Lingua has four tools that share one pipeline:

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
3. **Naming Assessment:** a timed, computerized picture-naming test for clinicians and researchers, and a short public version anyone can take.
   - It measures accuracy (first complete response), error types and naming latency, and tracks change across sessions.
   - Tests can be our sets, a test you are licensed to use (pictures plus a CSV, or a PowerPoint), or a personal test made from a photo of the person's own things (**Muse Spark**, **SAM 3.1**, **Muse Image**).

   It measures and reports, beside published reference values. It doesn't diagnose or predict; a qualified person interprets.
4. **Model Lab:** the same tests are given to **Muse Glimmer**, Meta's open-weight model.
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
| Oct 26 | Naming Assessment: speech-onset latency (max error 5.6 ms on synthesized speech), first-complete-response coding, review and override, PDF report, tracking across sessions, parallel forms, bring-your-own test (ZIP, folder or PowerPoint), personal tests from a photo, and a public naming test with an opt-in reference range |
| Oct 26 | "What can I cut?": every Glimmer decoder layer skipped alone, a greedy removal path guarded by picture naming (English and Spanish) and perplexity on Muse Spark-written text, and real deletion of the chosen layers with measured size, memory and speed |
| Oct 26 | Web pages for both experiments: `/plato` (16 chairs from Muse Image vs. 16 people, 35 things, six languages, inside Glimmer, the second-model comparison) and `/lab/cut` (set your own guardrail on the greedy path, a 52-layer map, the real-deletion table). Both replay shipped statistics, with no API calls |

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

## Naming Assessment

`/assess` is for clinicians and researchers; `/take` is a 3-minute public version. Both use the same engine (`metalesionlab/assessment.py`, `metalesionlab/web/assess_routes.py`, `static/js/assess-engine.js`).

**For use by clinicians and researchers. Measurements only; no diagnosis or prognosis.** Every page and report says so. The public test reports numbers only, beside the range of adults who took the same test, and says it isn't a medical test.

### What a session measures

- **Accuracy** on the first complete response, as in the PNT. "Dog, no, cat" is coded *dog*; fragments ("c-, cat"), comments ("let me think"), refusals followed by an answer and frames ("it's a", "es un") are set aside. A description stays whole.
- **Error types**, with the Scorer's coder and optionally Muse Spark as second rater. The reviewer can change any code or latency, or correct a transcript to re-code it; the reviewer's entries are final.
- **Naming latency**: picture onset to speech onset. Median and interquartile range for correct responses, latency per item, and items that reached the time limit (default 20 s, as in the PNT; reaching it counts as no response).
- A **reference panel** of published Philadelphia Naming Test group results (controls; pooled aphasia groups), labeled as group references on a different test, not norms for the person.
- Exports: a one-page PDF report with an item appendix, and an item-level CSV.

### How latency is measured

The browser captures the microphone continuously (AudioWorklet) and places each picture's onset on the audio clock, at the frame the picture is painted. Each clip starts 300 ms before the picture and is sent as 16 kHz WAV with the onset's position. On the server, `audio.detect_speech` finds speech with a documented energy detector: RMS in 10 ms windows every 5 ms; noise floor = median of the first 150 ms; threshold 12 dB above it (at least −55 dBFS); speech = at least 60 ms above threshold, bridging dips under 30 ms; the onset is walked back to where energy first rose 6 dB above the floor. Device audio and display delays the browser doesn't report (typically 10–50 ms) are not corrected, so compare sessions on the same device.

`python scripts/validate_latency.py` builds clips the way a session records them: 300 ms lead-in, then 200, 500, 1000 or 2000 ms of silence, then a word spoken by macOS `say` (8 English and 4 Spanish words). The true onset is the known silence plus the word's first sample above −50 dBFS.

| Condition | Clips | Mean error | Mean absolute error | Largest error |
|---|---|---|---|---|
| Clean | 48 | −2.5 ms | 2.5 ms | 5.6 ms |
| White noise at −60 dBFS | 48 | +1.2 ms | 2.5 ms | 14.4 ms |
| White noise at −50 dBFS | 48 | +11.0 ms | 11.2 ms | 54.4 ms |

The only errors over 50 ms were the soft /f/ of "fan" in the noisier condition, which was detected at the vowel. Through the running server, with real transcription, 8 clips in English and Spanish were within 3 ms.

### Two modes

- **Clinician or researcher (`/assess`):** choose a test, a speaker code (never a name), the time limit and, optionally, practice items, a parallel form and the second rater. The administration screen shows only the picture; Space, → or a tap on **Next** moves on. Sessions are kept per speaker code in the browser, with a chart of accuracy and median latency across sessions (points only: no trend line or prediction), and export, import and delete.
- **Public (`/take`):** about 20 pictures in a verified language (English, Spanish, French or Portuguese demo set). The result is accuracy, median naming speed and a plain-language breakdown, beside the range of adults who took the same test once at least 10 have contributed ("being collected (n = k)" until then), plus the PNT control accuracy labeled as a different test.

### Reference range for the public test

Adults who report no neurological or language condition, and fluency in the test language, can add their result after a consent line. Only a summary is stored, in `TOT_DATA_DIR/norms/<set>.jsonl`: language, set and set version, accuracy, median latency on correct answers, optional age band and the date. No audio, transcripts, names or IP addresses. The server recomputes the summary from signed per-answer receipts, so it can't be typed in by hand, and limits each visitor to 3 a day. `python scripts/aggregate_norms.py` writes `public_data/naming_norms_<set>.json` (n, mean, SD, 5th–95th percentiles) only for sets with at least 10 contributors.

### Privacy

- Each answer's audio goes to the Meta Model API for transcription; the server processes it in memory and stores nothing about the person. Get your institution's approval before using this with patients.
- Session results stay in the browser (IndexedDB) until exported or deleted. Audio clips are kept in memory for playback during review only.
- Private sets (imported tests and photo tests) stay in the browser. Their pictures are never uploaded; during a session only the audio, the target word and its accepted alternates are sent.
- A photo for a personal test goes to the Meta Model API, re-encoded without its metadata, and isn't saved; the finished pictures go back to the browser.

### Bring your own test

Import a ZIP or a folder of pictures with a CSV:

```csv
file,target,alternates,practice
p1.png,house,home,yes
01.png,cat,kitty;puss,
```

For a test that comes as a PowerPoint, such as the Philadelphia Naming Test obtained from its publisher, make the ZIP with:

```bash
pip install -e ".[pptx]"
python scripts/import_pptx_test.py test.pptx targets.txt -o ~/my_test.zip --practice 2
```

It takes the largest picture on each slide, skips slides without one, pairs them in order with the target list (`cat: kitty; puss` per line, or a CSV), and refuses to write inside this repository. We don't distribute PNT pictures; use only tests you are licensed to use.

### Personal tests and parallel forms

- **From a word list:** Test Studio.
- **From a photo** of the person's home or belongings (no people): Muse Spark lists the clearly visible, nameable objects in the test's language, SAM 3.1 finds each one, and Muse Image redraws it as a line drawing in our style, two candidates as in Test Studio (or it is cropped from the photo). The Test Studio checks then run. On a synthetic kitchen photo, 4 of 7 drawings and 5 of 7 Spanish crops passed both checks; the rest were flagged for review.
- **Parallel forms:** a set splits into two halves matched on word frequency (Zipf) and length in phonemes, for re-testing without repeating pictures. The English demo set splits into halves with mean Zipf 3.87 and 3.87, and 5.0 and 4.9 phonemes.

## Does damage hurt the second language first?

We showed the same 20 pictures to Muse Glimmer with matched one-word instructions in English, Spanish, French and Portuguese, and applied identical damage in each language (41 lesion conditions, 490 runs).
- **Bigger drop outside English.** Damage cost Spanish naming **28 percentage points more than English** (95% CI 23–32). French lost 33 more and Portuguese 35 more. Every picture fared worse in the non-English language.
- **Falls back to English.** Damaged non-English trials often come out in English: 24% of damaged Spanish trials. The reverse happened in 2 of 1,780 English trials.
- **An English pivot.** Even intact, the word lens shows the English name as the top guess around layer 40, with the asked-for language taking over only at layer 47.

It echoes the observation that in bilingual aphasia the non-dominant language can be hit harder. That is an analogy, not evidence about brains. Method, caveats (20 pictures, one model) and figures: [docs/bilingual.md](docs/bilingual.md).

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

The honest answer for this model is "not much". Two layers can go with no measurable loss, a saving of about 3%. Naming, not perplexity, was the binding guard: a perplexity check alone would allow five layers but lose three guard pictures and eight held-out ones, mostly in Spanish. The cut models often answered a Spanish prompt in English ("Umbrella" for *paraguas*), so language control broke before object recognition did. Full-attention layers mattered no more than sliding-window ones. Block influence, a cheap no-skip score, ranked layers poorly here. With about 20 pictures per language, one picture is about 5 points, so treat small differences as noise. Full results, including per-layer scores and the whole greedy path, are in `runs/compress/glimmer.json`. In the app, **Model Lab → What can I cut?** (`/lab/cut`) replays them: set how much naming and perplexity you'll give up, and the deepest passing cut moves with your limits. `runs/` isn't in the repository, so the app ships a compact copy (`metalesionlab/web/data/cut_glimmer.json`, written by `python scripts/cut_web_export.py`) and prefers `TOT_DATA_DIR/compress/glimmer.json` when it exists.

## Ask the Lab

`/ask` takes a question in plain language, such as "Which kind of damage makes sound errors like 'Caraloon'?" or "Does damage hurt Spanish more than English?". A **Muse Spark** agent then works through it in three steps:

1. It plans and calls up to six read-only tools, using Muse Spark's native tool calling.
2. The tools read results the lab has already computed, through the same loaders as the pages:
   - lesion conditions, error profiles by damage site, a search over the model's answers and the word lens;
   - layer removal, the bilingual test and Plato's Chair;
   - the published group profiles of people with aphasia, and language support.
3. It answers with numbers, a `[tool: id]` citation for each one, and links into `/lab`, `/plato` and `/lab/cut`.

Each step streams to the page as it happens (JSON lines), so you watch the trace live. The code is in `metalesionlab/lab_agent.py` and `metalesionlab/web/agent_routes.py`.

- **Checked numbers.** Before the answer is shown, every number in it is matched against the tool results; a difference or ratio of two numbers that match also passes. One repair call fixes any misses, and whatever is still unmatched is flagged on the page.
- **No medical advice.** Questions about a particular person's health, test result, recovery or treatment are declined before any model call. The agent's instructions decline the subtler ones. Text inside the data (the model's own answers) is treated as data, never as instructions.
- **Cost.** A typical answer costs $0.01–0.03 in Muse Spark calls; the page shows each answer's cost. Settings:
  - `TIPPA_AGENT_DAILY_USD` (default $1): the agent's daily cap, read from ledger entries tagged `ask`;
  - `TIPPA_AGENT_SESSION_QUESTIONS` (default 10): questions per browser per day;
  - `TIPPA_AGENT_IP_QUESTIONS` (default 30): questions per address per day.

## Meta models used

| Model | Role |
|---|---|
| Muse Glimmer 30B (open weights, self-hosted) | Test-taker in Model Lab, with lesions and the word lens; name-agreement check |
| Muse Image 1.0 | Draws test pictures |
| SAM 3.1 | Picture quality check |
| Muse Spark 1.3 | Name agreement, meaning judge, second rater, experiment agent, Ask the Lab agent (tool calling) |
| Muse Voice Transcribe 1.0 | Transcribes spoken responses |
| DINOv2 (`facebook/dinov2-base`, open weights, run locally) | Picture embeddings for the Plato's Chair experiment |

Every AI step uses a Meta model. The other resources are non-AI: WordNet, the CMU Pronouncing Dictionary and wordfreq.

## Experiment: Plato's Chair

Ask Muse Image to draw 16 chairs: are they all the same chair? We compared how spread out 35 concepts are in Muse Image's doodles and in people's drawings of the same words, using DINOv2 embeddings. The AI was more uniform than people for 34 of the 35 concepts, with a median spread ratio of 0.49. Method, results and caveats are in [`docs/plato.md`](docs/plato.md), and the code is in `scripts/plato_*.py`.

Human drawings come from the [Google Quick, Draw! dataset](https://github.com/googlecreativelab/quickdraw-dataset) (Google Creative Lab, CC BY 4.0). They are streamed at run time and never committed; `public_data/plato_concept_spread.json` holds only derived statistics.

The `/plato` page tells the story for everyone: a toggle between Muse Image's 16 chairs and 16 people's, all 35 things, six languages, what Muse Glimmer does with the doodles, and the comparison with Stable Diffusion XL (the uniformity is Muse Image's, not every image model's). It reads statistics in `metalesionlab/web/data/plato.json` and 14 small figures in `static/img/plato/`, written by `python scripts/plato_web_export.py`; figures with people's drawings keep their Quick, Draw! credit. The full data folder (pictures, embeddings, raw results) lives outside the repository.

## Data policy

- No data from real research participants is stored in, or processed by, this repository. Comparisons with people with aphasia use published group-level numbers, cited where they are used.
- A pre-commit hook blocks data files and large binaries outside `public_data/`. Enable it once per clone:

  ```bash
  git config core.hooksPath .githooks
  ```

- Audio sent to the Scorer and the Naming Assessment goes to the Meta Model API. Use speaker codes, never names, and don't upload identifiable patient recordings unless your institution has approved that.
- Assessment sessions and private test sets stay in the user's browser. The only thing the server keeps is the summary a volunteer chooses to add to the public test's reference range (see Naming Assessment).

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

Pages: `/` (home), `/challenge` (You vs. the AI), `/plato` (Plato's Chair), `/lab` (Model Lab), `/lab/cut` (What can I cut?), `/ask` (Ask the Lab), `/scorer` (Scorer), `/studio` (Test Studio), `/assess` (Naming Assessment) and `/take` (public naming test). Every page except the two assessment pages has a guided Demo tour. The JSON API is documented at `/api/docs`. Voice scoring needs `ffmpeg` on `PATH` to read browser recordings; the assessment pages send WAV and don't.

- Data lives in `TOT_DATA_DIR` (default `runs/`): picture sets in `sets/`, description scenes in `scenes/`, precomputed lesion conditions in `lesion/`. The Model Lab shows a small, clearly labeled sample until `lesion/` has results.
- Every route that spends Meta API credit has a per-visitor daily limit: 3 set builds, 3 scenes and 60 scored responses by default (`TOT_LIMIT_BUILD`, `TOT_LIMIT_SCENE`, `TOT_LIMIT_SCORE`). The overall budget cap still applies; once it's reached, the app says so and browsing, review and exports keep working.
- For a public deployment, set `TOT_PUBLIC=1` so visitors can edit only the sets and scenes they built, `TOT_TRUST_PROXY=1` behind a reverse proxy, and `TOT_ALLOW_BUILDS=0` to turn off image generation.
- Scorer results stay in the browser until exported. The server doesn't store audio.
- A full PNT-length session is 175 scored responses; on a local install raise `TOT_LIMIT_SCORE`. Set `TOT_RECEIPT_KEY` to keep public-test receipts valid across restarts.

## License

Apache 2.0

# Tip of the Tongue

**Language tests for people and AI, in any language.** Build picture-based language tests in minutes, give them by voice, and score them automatically. Then run the same tests on Meta's open-weight model and see where language breaks.

Tip of the Tongue has three tools that share one pipeline:

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

> Research and teaching use only. Tip of the Tongue doesn't diagnose, and it doesn't give medical or treatment advice.

## Built during the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026)

Everything in this repository was written during the hackathon, starting at the kickoff on Oct 26, 2026. The commit history is the record.

| Date | Built |
|---|---|
| Oct 26 | Repo, data guard, Meta Model API client with spend ledger and budget cap |
| Oct 26 | Muse Glimmer in FP8 on a single L40S (32 GiB). Picture naming with the reasoning channel skipped. Word lens (logit lens) that matches the model's own output at the last layer |
| Oct 26 | Naming-error classifier (English and Spanish), with WordNet plus a Muse Spark judge for meaning. It passes 34 unit tests and agreed with the expected code on 19 of 20 live cases; the one miss was a mistake in the expected answer. |

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

See `metalesionlab/naming_errors.py`.

## Meta models used

| Model | Role |
|---|---|
| Muse Glimmer 30B (open weights, self-hosted) | Test-taker in Model Lab, with lesions and the word lens; name-agreement check |
| Muse Image 1.0 | Draws test pictures |
| SAM 3.1 | Picture quality check |
| Muse Spark 1.3 | Name agreement, meaning judge, second rater, experiment agent |
| Muse Voice Transcribe 1.0 | Transcribes spoken responses |

Every AI step uses a Meta model. The other resources are non-AI: WordNet, the CMU Pronouncing Dictionary and wordfreq.

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

## License

Apache 2.0

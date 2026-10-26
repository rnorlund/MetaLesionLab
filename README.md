# MetaLesionLab

A toolkit for picture-naming research, built on Meta's models. It does three things:

1. **Stimulus Studio:** make a normed, rights-free picture-naming set in minutes. You give it words. **Muse Image** draws each object, **SAM 3.1** checks that each picture shows exactly one clear object, and **Muse Spark** plus **Muse Glimmer** check that each picture gets the intended name. You get printable cards, a slide deck and a norms table. Classic naming tests are copyrighted, and building your own set by hand takes weeks.
2. **Naming Scorer:** someone names the pictures out loud. **Muse Voice Transcribe** transcribes each answer, and every answer is coded with the standard error categories: semantic, formal, mixed, nonword, neologism, unrelated or no response. A person reviews and corrects the codes, then exports them. Scoring a naming test by hand takes hours.
3. **Lesion Lab:** damage specific parts of **Muse Glimmer**, Meta's open-weight model, and watch it make aphasia-like naming errors. A word lens shows the model's best guess at every layer. A **Muse Spark** agent designs and runs the experiments, then compares the model's error profiles with published profiles from people with aphasia.

> Research and teaching use only. MetaLesionLab doesn't diagnose, and it doesn't give medical or treatment advice.

## Built during the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026)

Everything in this repository was written during the hackathon, starting at the kickoff on Oct 26, 2026. The commit history is the record.

| Date | Built |
|---|---|
| Oct 26 | Repo, data guard, Meta Model API client with spend ledger and budget cap |
| Oct 26 | Muse Glimmer in FP8 on a single L40S (32 GiB); picture naming with the reasoning channel skipped; word lens (logit lens) that matches the model's own output at the last layer |

### Prior research context (not part of this submission)

The research question comes from earlier work by the author on simulating aphasia by perturbing the weights of a different vision-language model (LLaVA). No code, data or results from that project are included here. MetaLesionLab is a new implementation built on Meta's models.

## Meta models used

| Model | Role |
|---|---|
| Muse Glimmer 30B (open weights, self-hosted) | The model that gets lesioned; names, repeats and verifies pictures; word lens |
| Muse Image 1.0 | Draws the naming stimuli |
| SAM 3.1 | Stimulus quality check: exactly one clear target object |
| Muse Spark 1.3 | Name agreement, independent second rater for error codes, experiment agent |
| Muse Voice Transcribe 1.0 | Transcribes spoken naming answers |

## Data policy

- No data from real research participants is stored in, or processed by, this repository. Comparisons with people with aphasia use published group-level numbers, cited where they are used.
- A pre-commit hook blocks data files and large binaries outside `public_data/`. Enable it once per clone:

  ```bash
  git config core.hooksPath .githooks
  ```

- Audio sent to the Naming Scorer goes to the Meta Model API. Don't use it with identifiable patient recordings unless your institution has approved that.

## Setup

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"          # API tools (Stimulus Studio, Naming Scorer)
pip install -e ".[gpu]"          # Lesion Lab (needs a GPU with ~40 GB, e.g. one L40S)
export MODEL_API_KEY=...         # from dev.meta.ai
python scripts/smoke_meta_api.py # checks every Meta API we use
```

Every Meta API call is logged to `runs/costs.jsonl`, and new calls are refused once spending reaches `MLL_BUDGET_USD` (default $120).

## License

Apache 2.0

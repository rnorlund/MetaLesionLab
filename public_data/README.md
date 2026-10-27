# public_data

The only folder where data files may be committed. Everything here must be public and licensed for redistribution, with its source and license listed below.

No data from real research participants goes anywhere in this repository. Comparisons with people with aphasia use published, group-level numbers, cited in the code that uses them.

| File | Source | License |
|---|---|---|
| `general_text_guard.json` | 150 short everyday sentences (100 English, 50 Spanish) written by Muse Spark (`muse-spark-1.3`) for this project with `scripts/make_guard_text.py`; the general-language guard in "What can I cut?" (`metalesionlab/compress.py`). Model-generated, not from any person or corpus | Apache 2.0, with the repository |
| `language_support.json` | Our own measurements (Oct 26, 2026): picture sets built with Meta's models and naming checks on speech synthesized with macOS voices. No recordings of people. Method in `docs/languages.md` | Apache 2.0, like the code |
| `human_naming_profiles.json` | Published group-level numbers from Schwartz et al. 2012, Walker et al. 2018, Yang et al. 2026 (C-STAR group means, with permission), Dell et al. 2007, Roach et al. 1996 and Walker et al. 2011 (citations, DOIs and tables inside the file) | Facts quoted from published papers, with citation |
| `naming_norms_<set>.json` (once written) | Reference range for the public naming test, aggregated by `scripts/aggregate_norms.py` from opt-in summaries of adult volunteers (no audio, words, names or IP addresses); written only from 10 contributors | Collected for this project; summary statistics only |

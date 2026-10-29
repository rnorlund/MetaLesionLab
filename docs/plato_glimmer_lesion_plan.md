# Damage Meta's open AI: what does it forget first? Pre-registration

Written on Oct 28–29, 2026, and committed before the main run. At this commit only the pilot exists (4 answers per thing at 20 settings, `PlatosChair/glimmer_lesion/pilot/`). Results will go in `docs/plato_glimmer_lesion.md`; any deviation from this plan will be listed there, and any prediction that fails will be reported as failed.

## The question

Every damage result on the site so far damaged Stable Diffusion XL, which draws pictures. Here we damage **Meta's own open-weight model, Muse Glimmer 30B**, and ask it to do two things with the same idea:

1. **draw it**, by writing the drawing as SVG code, as in the scale experiment (`docs/plato_scale.md`), and
2. **describe it** in one sentence.

The things are **a chair**, **a clock set to 10 past 11** (the clinical clock-drawing instruction) and **God**.

**Main question.** As more of the model is switched off, does "draws a recognisable X" fail **before**, **together with**, or **after** "describes X correctly"? Is that different when the damage is in the **early** layers or in the **late** layers? This is the aphasia researcher's question (does a patient lose the word before the picture, or the picture before the word?) asked of a model. It is an analogy, not a claim about people.

## Model and requests

| | |
|---|---|
| Model | `meta-models/Muse-Glimmer-30B` (revision as in the scale experiment), FP8 decoder weights with the vision tower and lm_head in BF16 (`metalesionlab/glimmer.py`), one L40S (axon-server01). Reasoning channel skipped by pre-filling the answer prefix, as in the scale experiment. |
| Draw a chair | *"Draw a simple chair as an SVG drawing: black strokes only on a white background, 256 by 256 pixels, no text, no colour fill. Output only the SVG code."* (the scale experiment's request, word for word) |
| Draw a clock | *"Draw a simple clock as an SVG drawing: put in all the numbers and set the hands to 10 past 11. Black strokes only on a white background, 256 by 256 pixels, no colour fill. Output only the SVG code."* "No text" is dropped because the numbers are text. |
| Draw God | *"Draw God as a simple SVG drawing: black strokes only on a white background, 256 by 256 pixels, no text, no colour fill. Output only the SVG code."* |
| Describe | *"Describe a chair in one sentence."*, *"Describe a clock in one sentence."*, *"Describe God in one sentence."* |
| Sampling | 12 answers per request and condition, temperature 1.0 (the scale experiment's primary), top-p 1, no top-k, no repetition penalty. Drawings: at most 2,048 new tokens, stopping at the first `</svg>` (only the first complete SVG is ever used) or the end of turn. Descriptions: at most 128 new tokens. |
| Seeds | The same torch seed in every condition: 20261128 for the 36 drawings (3 requests × 12, one left-padded batch), 20261129 for the 36 descriptions. Answer *i* of a request is "the same random starting point" at every step. |
| Batching check | Greedy answers alone and in a left-padded batch: the three drawing requests are identical; the three descriptions differ by a word or two (numerical noise of a padded batch, same meaning). The main run batches the descriptions separately, where the prompts differ by a token or two. |

## Damage

Reversible forward hooks (`metalesionlab.lesions`, method `zero`); the weights are never edited. Glimmer has 52 decoder layers, each with 19,968 MLP neurons (the input channels of `mlp.down_proj`) and 32 attention heads.

| Type | What is switched off | Where |
|---|---|---|
| **all** | a share *f* of the MLP neurons in each layer | all 52 layers |
| **early** | the same share in each layer | layers 0–16 (the first third) |
| **late** | the same share in each layer | layers 35–51 (the last third) |
| **heads** (optional, reported apart) | a share *f* of the attention heads in each layer (the head's 128 channels of the `o_proj` input) | all 52 layers |

**Which units.** Each layer has one fixed random order of its neurons (and of its heads): `numpy.random.default_rng([0, layer, size]).permutation(size)`. A share *f* switches off the first round(*f* × size). So a heavier step keeps every unit a lighter step switched off, and early and late switch off exactly the units that "all" switches off in those layers at the same share. One random draw of units (seed 0) is used throughout.

**Dose ladders** (five steps each, set from the pilot below; see "Pilot"):

| Type | Steps (share switched off in each damaged layer) |
|---|---|
| all | 5%, 10%, 15%, 20%, 30% |
| early | 30%, 40%, 50%, 60%, 70% |
| late | 20%, 30%, 40%, 50%, 60% |
| heads | 10%, 15%, 20%, 25%, 30% |

That is 1 + 4 × 5 = 21 conditions, 756 drawings and 756 descriptions.

## Measures

### Drawings

- **Drew something** (secondary): the first `<svg>…</svg>` in the answer, put inline in a blank page and drawn by headless Chromium (JavaScript off, every network request refused) on a 256 × 256 white box at its own size (`scripts/plato_glimmer_lesion_browser.py`); not blank (< 0.1% ink) and not covered in ink (> 95%). A browser forgives typos that the strict renderer rejects. In the pilot, damage made such typos common (a misspelt namespace address, `width` written twice) while the drawing itself was fine.
- **Valid code** (secondary): the house's strict renderer and failure codes (`plato_scale.classify`, cairosvg): renders, not blank, not all ink.
- **Named right (primary picture measure): the thing is among Google SigLIP 2's three best guesses**, out of 36 names, for the browser's drawing, ink-cropped (`plato.ink_crop`). SigLIP 2 So400m/14-384, zero-shot, *"a simple line drawing of {name}"*, with the 35 Plato's Chair concept names (as in the scale experiment's reader) plus **"a god"**. A drawing that didn't come out counts as not named.
  - *Why top three, not the best guess.* In the pilot, undamaged Glimmer's chairs were read as benches first (chair second or third), and its God drawings (a figure with a halo) as a person or a face first. With the best guess only, two of three things start near zero and their loss can't be measured. "Among the three best of 36" has a chance rate of 8%. The best guess alone ("named first") is reported as a secondary measure, comparable with the scale experiment.
  - *Why "a god".* With the name "God", SigLIP 2 pulled 16% of people's Quick, Draw! drawings of the 35 other things (20 each) to God, including scribbles. We checked phrasings before the main run on drawings that are not Glimmer's: "a god" reads 2% of people's drawings of other things as a god, and 16 of 16 of Muse Image's God doodles and 16 of 16 of Stable Diffusion XL's undamaged God pictures as a god. "God" read 12 and 13 of 16. The choice was made on those sets alone.
- **Like its undamaged drawings** (secondary): DINOv2-base CLS of the ink-cropped drawing, cosine similarity to the mean of the thing's undamaged drawings (an undamaged drawing is compared with the others, itself left out).
- **The clock's numbers** (descriptive): whether the code writes all of 1–12 as text.

### Descriptions

- **Correct (primary word measure), a fixed keyword rubric** (`plato_glimmer_lesion.score_description`): the answer
  - names the thing: chair → chair(s); clock → clock(s), timepiece; God → god, deity, creator, almighty, lord, divine being, supreme being, higher power;
  - mentions at least one rubric attribute (the fixed lists in `plato_glimmer_lesion.ATTRIBUTES`: for the chair sit, seat, back, legs, arms, furniture, person, support …; the clock time, hours, minutes, hands, numbers, face, measures, tells, shows …; God supreme, creator, universe, all-powerful, eternal, divine, being, worship, faith …);
  - **and is a short answer**: it stopped by itself, has at most 60 words and contains no code.

  The short-answer condition was added after the pilot and before the main run. Under heavy damage the pilot's answers rambled for 100 words and mentioned "clock" and "time" in passing ("In a clock, you have the current… etc. The user asked for…"), which the bare keyword rule counted as correct.
- **Names the thing** (secondary): the first condition alone.
- **Fluent (a proper sentence, right or wrong; secondary)**: all of: it stopped by itself; 4–60 words; starts with a capital (or a quote mark); ends with . ! or ?; no word three times in a row and no three-word phrase repeated; at least 90% of words are English words (wordfreq Zipf ≥ 1); no code.
- **By eye (the check).** Before any automatic scoring of the main run, I read all 756 descriptions in a shuffled sheet that shows only an id and which thing was asked, never the condition (`byeye/sheet.json`; the key in `byeye/key.json` is not opened while coding). For each I record **correct** (it says what the thing is, correctly and typically, in a sentence a reader would accept as a description, even if clumsy) and **fluent** (a well-formed sentence or two, whatever it says). The codes are saved as `byeye/codes.json` and its SHA-256 is added to this plan, in a commit, before `score` runs; the scoring script refuses to run otherwise.

## Analysis

**Things in the test.** A thing enters the primary test if, undamaged (the main run's intact condition), at least 4 of its 12 drawings are named right **and** at least 4 of its 12 descriptions are correct. Things below that floor are reported but left out of the verdict: there is too little to lose.

**Retention.** For each damage type and each thing in the test, a measure's rate at each step divided by its undamaged rate; the curve is the mean over the things in the test (each counts the same).

**Primary statistic: the gap.** For each damage type: mean over the five steps of (word retention − picture retention), with a 95% percentile bootstrap CI (4,000 resamples of the 12 answers within each condition and thing; a replicate in which some thing's undamaged rate resamples to 0 is dropped and the count reported).

**Verdict rule** (per damage type):
- CI entirely above 0 → **picture first** (the words outlast the drawing);
- CI entirely below 0 → **word first**;
- otherwise → **together** (too close to call).

**Descriptive order.** The first step at which each mean retention curve falls below 0.5 (half its undamaged level; the house's "fails first" rule from `docs/plato_ideas_damage_plan.md`): picture first, word first, together (same step) or neither. Reported beside the gap; where they disagree, the gap decides and both are reported.

**Early against late.** gap(early) − gap(late), CI from the two independent bootstraps; **different** if the CI excludes 0, otherwise too close to call.

### Predictions

| # | Prediction | Supported if |
|---|---|---|
| P1 | **Damage everywhere takes the drawing before the words.** Writing a drawing as code is a long, exact, rarely trained skill; a one-sentence definition is short and overlearned. The pilot hinted at this. | type **all**: the gap's CI is above 0 |
| P2 | **Early and late damage differ** in which goes first (no direction predicted). | the early − late CI excludes 0 |
| P3 | **Fluent but wrong.** Under damage everywhere, sentences stay well formed after they stop being correct (like fluent aphasia). | type **all**: mean over the steps of (fluent retention − correct retention), pooled over the three things with the same bootstrap, has a CI above 0 |

Heads are an extra, exploratory arm: the same statistics, no prediction.

### Secondary analyses (all reported)

- the gap with other measures of each side: drew something vs correct; named right vs names the thing; named right vs fluent; named right vs **by-eye correct**;
- per thing, the same gap and order;
- every measure's raw rate (out of 12) per thing and condition; DINOv2 similarity; the clock's numbers; named first (best guess);
- agreement between the rubric and my by-eye codes (percent agreement, per measure).

**Where the rubric and the by-eye codes disagree on a verdict**, both are reported and the verdict is called not robust.

### What the page will show

The slider follows one answer per thing through every step: the thing's **undamaged DINOv2 medoid** (the undamaged drawing nearest on average to the other undamaged drawings; ties: the lower index), fixed by this rule before any damaged drawing is seen. The same index is used for the sentence beside it.

## Pilot

4 answers per thing at 25 settings (about 0.5 GPU-hour). Per setting, drawings that came out / named right (SigLIP top 3) of 4, summed over the three things:

| Type | Share off | Drew | Named | What happened |
|---|---|---|---|---|
| all | 10% | 10/12 | 6/12 | words mostly fine, drawing code gets typos |
| all | 20% | 4/12 | 4/12 | drawings failing, sentences start to ramble |
| all | 30% | 1/12 | 1/12 | gibberish |
| early | 40% | 10/12 | 9/12 | near intact |
| early | 50% | 10/12 | 10/12 | still drawing, some code failures |
| early | 60% | 0/12 | 2/12 | cliff: nothing drawn |
| late | 20% | 12/12 | 12/12 | intact |
| late | 40% | 4/12 | 10/12 | drawings fail, answers still named |
| late | 60% | 0/12 | 6/12 | nothing drawn |
| heads | 10% | 12/12 | 12/12 | intact |
| heads | 20% | 10/12 | 9/12 | mixed |
| heads | 30% | 0/12 | 4/12 | broken |

Ladders were set so each step is a visible change: the heaviest step breaks most drawings, the lightest is mild. Early damage has a cliff between 50% and 60%, so its ladder is dense there. The "named" counts in the pilot were rough (the reader's rule was fixed at "top three" as above after seeing pilot drawings, on the pilot only; the main run's undamaged drawings were not seen).

## Cost

No paid API calls. Glimmer runs on our own GPU (axon-server01). SigLIP 2, DINOv2 and Chromium run on the Mac.

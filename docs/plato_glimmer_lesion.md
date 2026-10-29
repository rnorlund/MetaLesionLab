# Damage Meta's open AI: what does it forget first?

Pre-registered in `docs/plato_glimmer_lesion_plan.md` (plan commit 6819c7c, pilot table corrected in 110376c, the sampling deviation and the by-eye hash committed before scoring). Page: `/plato/glimmer`. Data, drawings and raw answers: `PlatosChair/glimmer_lesion/`. Code: `metalesionlab/plato_glimmer_lesion.py`, `scripts/plato_glimmer_lesion_{run,browser,analyze}.py`.

We switched off random neurons (or attention heads) of Meta's open-weight Muse Glimmer 30B, step by step, and asked it for a chair, a clock set to 10 past 11 and God, each drawn as SVG code and each described in one sentence. 12 answers per thing per setting, temperature 1; 21 settings, 756 drawings and 756 descriptions. An analogy to aphasia research, not a claim about people.

## Short answer

**The drawing goes first.** With neurons switched off in all 52 layers, "drawn so a reader AI can name it" fell below half at step 2 of 5 and "described correctly" at step 5. The word-minus-picture retention gap is +20 points [+4, +30] (verdict rule: CI above 0, "picture first"). The same holds with damage only in the first third of layers (+15 [+6, +22]) and only in the last third (+21 [+8, +30]). Early against late: difference −6.5 points [−19, +8], too close to call. Attention heads (extra): +17 [+11, +23].

- **Fluent but wrong (P3, supported for damage everywhere):** well-formed sentences outlast correct ones: fluent minus correct retention +11 points [+2, +20]. Early damage +21 [+14, +29]; late damage +4 [−3, +13] (together).
- **Caveat that matters.** Whether any drawing came out at all fell together with correct descriptions in 3 of 4 damage types (all, early, heads; late: picture first). So much of the "picture first" result is drawings becoming unrecognisable (a chair that reads as nothing) before they stop existing. The strict "valid code" count is lower still, because damage breaks the SVG's boilerplate (the browser forgives it; cairosvg doesn't).
- **Predictions:** P1 (damage everywhere takes the drawing first) supported. P2 (early and late differ) not supported: too close to call. P3 supported for damage everywhere.

## Doses

Share of neurons (or heads) switched off in each damaged layer, set from the pilot: all 5, 10, 15, 20, 30%; early (layers 0-16) 30, 40, 50, 60, 70%; late (layers 35-51) 20, 30, 40, 50, 60%; heads 10, 15, 20, 25, 30%. Early damage has a cliff between 50% and 60%, so its last two steps are already dead (a dose-ladder mistake: it should have been denser at 40-60%).

## Undamaged (replicates the scale experiment)

Chair: 12 of 12 came out, 7 of 12 named a chair among the reader's top three (1 of 12 as its first guess; the scale experiment found 2 of 12). Clock: 12 of 12 read as a clock; all twelve numbers drawn in 2 of 12. God: 11 of 12 read as a god. Descriptions: 12 of 12 correct for each thing.

## Method notes and deviations

- **Browser drawing.** The house strict renderer (cairosvg) rejected many damaged drawings for boilerplate typos. Drawings are drawn by headless Chromium (JS off, network refused); the strict count is a secondary measure. One strict render hung on a pathological SVG; renders now have a 20 s limit.
- **Reader.** SigLIP 2 zero-shot, 36 names; "a god" as God's name (fixed before the main run from non-Glimmer drawings, because "God" attracted 16% of people's drawings of other things). Primary picture measure: the thing is among the three best of 36.
- **Descriptions: the keyword rubric is primary on all 756 (dated deviation, cost).** I coded a stratified random sample of 150 by eye, blind (seed 20261029, round-robin over the 63 thing x setting strata), hash committed before scoring. Rubric against eye: **88% agreement on "correct"** (rubric 44% yes, eye 48%), **75% on "fluent"** (rubric 59%, eye 71%: the rubric is stricter on fluency). The "named vs by-eye correct" analysis was dropped.
- **Short-answer condition** added to the rubric after the pilot, before the main run (rambles that mention "clock" in passing).
- **Not done / limits.** One random draw of neurons; 12 answers per cell; heads were optional and not predicted; the reader AI and keyword list are imperfect; early ladder poorly placed (see Doses).

## Cost

No paid API calls. GPU: about 1.7 hours on one L40S (axon-server01): main run 99.7 minutes, pilot about 0.5 hour (plus load and batch checks).

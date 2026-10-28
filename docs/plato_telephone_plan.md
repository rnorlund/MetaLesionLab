# Plato's Telephone: pre-registered plan

Written and committed on 2026-10-27, before any chain was run. No description or picture from this experiment exists yet. The seed pictures were looked at only to choose the two controls.

**Question.** If an AI passes a picture along a chain (describe it, draw the description, describe that drawing, and so on), what survives? Does every chain collapse toward the same textbook chair, Muse's "Form", whatever chair it started from?

## Why ask

- **People.** Bartlett (1932), *Remembering* (Cambridge University Press), passed drawings along chains of people, each redrawing the previous drawing (serial reproduction). In his "Portrait d'homme" series, an ambiguous drawing became more face-like, "simplified" and "conventional" over the chain (p. 185, as quoted by Carbon & Albrecht, 2012). Carbon and Albrecht (2012, *Quarterly Journal of Experimental Psychology* 65(11), 2258–2270, doi:10.1080/17470218.2012.696121) could not replicate it. In five experiments, none showed a systematic drift toward Bartlett's described case, and one serial-reproduction experiment showed the opposite.
- **Iterated learning.** Kirby, Cornish and Smith (2008, *PNAS* 105(31), 10681–10686, doi:10.1073/pnas.0707835105) passed an artificial language along chains of learners. The languages became easier to learn and more structured. Griffiths and Kalish (2007, *Cognitive Science* 31(3), 441–480) showed that for Bayesian learners who sample from their posterior, iterated learning converges to the learners' prior. Xu and Griffiths (2010, *Cognitive Psychology* 60(2), 107–126) gave a Bayesian analysis of serial reproduction and tested it with people. On this view, a chain is a way to read out the prior: where it ends up is what the reproducer expects.
- **AI.** Shumailov et al. (2024, "AI models collapse when trained on recursively generated data", *Nature* 631, 755–759, doi:10.1038/s41586-024-07566-y) showed "model collapse": models trained on earlier models' output lose the rare parts of the data, "in which tails of the original content distribution disappear". Our chain does no training. It asks a related question about inference only: when two models copy each other, are the unusual chairs the "tails" that disappear?
- **Plato.** Republic X: the painter copies the carpenter's bed, which is itself a copy of the Form. A telephone chain is a copy of a copy of a copy.

## Seeds (generation 0)

Muse Image's own named-kind doodles from "Can you prompt it out of the Platonic chair?" (`PlatosChair/core/ai/doodle_listed/<concept>/p<i>.png`, kind i of that concept's `kinds.json`):

| Seed | File | Kind (labeler's right answer) | Kind word in a description (regex, case-insensitive) |
|---|---|---|---|
| rocking chair | chair/p0 | a rocking chair | `rock(ing\|er)` |
| throne | chair/p13 | a throne | `throne` |
| beanbag | chair/p5 | a beanbag chair | `bean[\s-]?bag` |
| wheelchair | chair/p7 | a wheelchair | `wheel[\s-]?chair` |
| office chair | chair/p3 | an office chair | `office` |
| folding chair | chair/p2 | a folding chair | `fold` |
| high chair | chair/p6 | a highchair | `high[\s-]?chair` |
| Adirondack | chair/p14 | an Adirondack chair | `adirondack` |
| *control:* top hat | hat/p0 | a top hat | `top[\s-]?hat` |
| *control:* cuckoo clock | clock/p1 | a cuckoo clock | `cuckoo` |

The controls ask whether a non-chair also drifts toward its own default (Muse's default hat is a baseball cap; its default clock is in the core run). The cuckoo clock was chosen over the sundial, hourglass and water clock because it is still clearly a clock.

Category words: `chair` anywhere in a word (so armchair, wheelchair and highchair count), `\bhats?\b`, `clock`.

**Not run:** the optional two Quick, Draw! starting chairs. The lab GPUs (for the free Glimmer labeler) are not used in this run, so kind labels come from Muse Spark and use the margin of the $4 budget.

## Protocol

Each chain, for k = 0 … 10:
1. **Describe.** Muse Spark (`muse-spark-1.3`, reasoning effort **minimal**, fixed) gets picture g(k) and the text: *"Describe this drawing so someone could redraw it. One or two sentences. Don't name an artist."* One call; an empty answer is asked again (up to twice).
2. **Draw** (k < 10). Muse Image (`muse-image-1.0`, n = 1, default size) gets the core doodle template with the description as the phrase: *"A quick simple doodle sketch of {description}, black marker on plain white, like a 20-second drawing, no text, no shading."* The description is cleaned only at its edges (`plato_telephone.phrase`: whitespace collapsed, surrounding quotes and a final period dropped, a leading "A/An/The" lower-cased, cut at a word boundary after 600 characters).
3. Every picture, including g00, is stored at 512 px on its long side and shown to Spark at that size.

So a chain has 11 pictures (g00 to g10) and 11 descriptions; picture g10's description is never drawn. **Three independent chains per seed** (they share g00 and nothing else; Spark describes g00 separately in each chain). 10 seeds × 3 chains × 10 steps = **300 pictures and 330 descriptions**.

Failures: network errors (DNS drops on this Mac, timeouts, 5xx, rate limits) are retried with backoff. A refused or failed picture is tried 3 times; a chain that still fails stops there and is reported with the generations it has. No step is ever redone because of what it produced.

**Budget.** About 300 × $0.01 (pictures) + 330 × ~$0.0016 (descriptions) ≈ $3.5, plus labels (below). This experiment's own cap is **$4.00** (its spend log `PlatosChair/telephone/spend.jsonl`); everything also stops if the shared ledger (`runs/costs.jsonl`) passes $70.

**Pilot.** The first two steps of the first chains are checked by eye (that the description and the picture make sense) before the run continues. They are part of the data; the protocol does not change after them unless something is broken, which would be reported.

## Measures

Embedding as in Plato's Chair: `plato.ink_crop` (256 px), DINOv2 (`facebook/dinov2-base`) CLS token, cosine distance.

1. **Distance to the Form** (per picture): cosine distance to the **prototype** of the seed's concept, the normalized mean of Muse Image's default doodles in the core run (16 for chair, 12 for hat and clock; `PlatosChair/core/embeddings/ai_doodle/`). Reference levels: the default doodles' own leave-one-out distance to their prototype (the **floor**: where a chain would sit if it had fully become the default), and the gen-0 value.
2. **Distance to its own start**: cosine distance from g(k) to the chain's g00.
3. **Between-seed spread** at generation k: the mean distance between pictures of chains from **different** chair seeds (all 8 × 3 chains). At k = 0 this is the spread of the 8 seed doodles. Reference: the spread of Muse's 16 default chairs (core run).
4. **Within-seed spread** at generation k: the mean distance between the 3 chains of the **same** seed (0 at k = 0).
5. **Words.** For each description: whether it contains the seed's kind word and the category word. Per chain, the first description (0–10) that lacks each word (11 = never lost, censored), and the share of the 11 descriptions that contain it. Exploratory: content words (`plato_telephone.content_words`) of a chain's first description and how many descriptions in a row keep each; words that the last description has and the first did not.
6. **Kind labels.** Muse Spark (vision, reasoning minimal) answers Plato's Chair's multiple-choice kind question for each picture: the concept's 16 (chair) or 12 (hat, clock) listed kinds, then "a plain, ordinary …", then "can't tell, or not a …" (`plato.labeling_prompt`, `plato.kind_options`, forward order, parsed with `plato.parse_letter`), on the picture ink-cropped to 448 px. g00 is labeled once per seed. **Kind retained** = the seed's own kind; **still the category** = any answer except "can't tell, or not a …"; **plain** = "a plain, ordinary …". Labels are bought after the run: every picture if the remaining budget allows (about $0.40 for 310 pictures); otherwise only generations 0, 2, 4, 6, 8 and 10. The choice depends only on the money left, not on any result.

## Predictions and tests (chair seeds; 24 chains)

CIs: 95%, from a two-level cluster bootstrap (2,000 replicates, seed 20261028): resample the 8 seeds with replacement, then the 3 chains within each drawn seed. The same draws are used for both ends of a difference. Spreads use the same chain weights and never pair a chain with itself.

| # | Prediction | Primary test | Supported if |
|---|---|---|---|
| P1 | Chains drift toward the default chair | mean change in distance to the chair prototype from g00 to g10 | CI entirely below 0 |
| P2 | Different starting chairs converge | change in between-seed spread from g00 to g10 | CI entirely below 0 |
| P3 | Distinctive features drop out first | per chain, (first description without the kind word) − (first description without "chair"); mean over chains | CI entirely below 0 |

Also reported, not tests: the slope of each measure over generations; the share of the gap to the floor that chains close by g10; when the kind label is lost compared with "still a chair" (P3's picture-side check); within- vs between-seed spread at g10 (does the start still matter?); each seed on its own.

**Specificity check (P1).** If pictures simply became plainer, they might move toward every prototype at once. So the same change is computed for distance to the hat and clock prototypes and to the mean of all 35 core concepts' prototypes. P1 is called chair-specific only if the drop toward the chair prototype is larger than the drop toward the mean of all prototypes (CI of the difference below 0).

**Controls.** For the top hat and cuckoo clock, the same measures against their own prototypes, 3 chains each. With one seed apiece, these are descriptive (CIs over 3 chains only).

Three primary tests, no correction for multiple tests; all reported whatever they show.

## What is published

Pictures stay in `PlatosChair/telephone/` (outside the repository). The site shows WebP filmstrips of the chains (our own Muse Image pictures). `public_data/plato_telephone.json` holds derived statistics, per-chain distance curves and Muse Spark's descriptions (model-generated text), with no embeddings. Write-up: `docs/plato_telephone.md`.

## Caveats known in advance

- Spark's description is the bottleneck: anything it doesn't say cannot survive. The drift measures the pair (describer plus drawer), not Muse Image alone.
- One describing prompt, one drawing template, one reasoning effort.
- Turning pictures into words loses a lot; a chain that kept everything is not expected.
- A seed's three chains share g00, so they are not independent at the start; the bootstrap resamples seeds first for that reason.
- This is one default behaviour under one protocol, not a property of Meta's models in general.

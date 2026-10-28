# Plato's Telephone

If an AI passes a picture along a chain (describe it, draw the description, describe that drawing, and so on), what survives? Does every chain collapse toward Muse's textbook chair, whatever chair it started from?

**Short answer: no.** When Muse Spark describes and Muse Image draws, ten times over, chairs are not pulled into the textbook chair.
- **No pull toward the Form.** On average the 8 named-kind chairs ended slightly *farther* from Muse's default chair than they started: distance 0.51 → 0.58, change +0.07 (95% CI −0.03 to 0.18). 14 of 24 chains ended farther away.
- **The chairs drift apart.** Chains from different starting chairs ended *more* different from each other, not less: 0.61 → 0.73, change +0.12 [0.03, 0.24]. Even the three chains of one chair, which start as the same picture, ended 0.37 apart, nearly three times the spread of Muse's 16 default chairs (0.13).
- **Names go first** (as predicted). Spark's descriptions dropped the kind's name (rocking, beanbag, folding …) at description 6.6 on average, and the word "chair" at 10.0 (11 = never): difference −3.3 [−6.0, −0.8]. No first description called the throne a throne (Spark saw "an armchair with … crown-like points"); later ones said "throne-like" only 4 times in 30.
- **One chair did fall into the Form: the high chair.** In 2 of its 3 chains, the tray Spark described didn't make it into the first redraw. From then on Spark described a simple chair, and within a few copies every picture was Muse's slat-back textbook chair, where it stayed (distance 0.07 and 0.09 at the end; Muse's own default chairs sit at 0.07).
- **Without their names, the others wandered rather than reverting.** A beanbag became a croissant and then a fan-shaped window; a folding chair became a scribbled diamond; the throne's crown ended on a pole above a black oval. Rocking chairs, wheelchairs and office chairs kept their names in all 33 descriptions each.
- **Controls.** The top hat stayed a top hat and the cuckoo clock a cuckoo clock in all 6 chains. Neither came near Muse's default hat (a baseball cap) or default clock: they ended at 0.59 and 0.64 from them, against 0.17 and 0.11 for Muse's own defaults.

So in this loop the textbook chair works like a trap door, not a slope: a chain fell in only when the one detail that set it apart was dropped in a single step, and then it stayed. Chains that kept their distinguishing detail never slid toward it. This is one protocol with one prompt, and the bottleneck is the description (see Caveats).

## Why ask

- **People.** Bartlett (1932, *Remembering*) passed drawings along chains of people, each redrawing the previous one. In his best-known chain, the "Portrait d'homme" series, an ambiguous drawing became more face-like and, in his words, more "simplified" and "conventional" (p. 185, as quoted by Carbon & Albrecht, 2012). Carbon and Albrecht (2012) tested this in five experiments and found no systematic drift toward the face; one serial-reproduction experiment showed the opposite.
- **Iterated learning.** Made-up languages passed along chains of learners became easier to learn and more structured (Kirby, Cornish & Smith, 2008). For Bayesian learners who sample from their posterior, iterated learning converges to the learners' prior (Griffiths & Kalish, 2007), and serial reproduction has been analysed and tested the same way (Xu & Griffiths, 2010). Where a chain ends up then shows what the copier expects.
- **AI.** Shumailov et al. (2024) showed "model collapse": models trained on earlier models' output lose the tails of the original distribution. Our chain involves no training. It asks a smaller, inference-only question: when two models copy each other, are the unusual chairs the tails that disappear?
- **Plato.** *Republic* X ranks the Form, the carpenter's bed and the painter's picture of it, a copy of a copy. In the *Parmenides*, the likeness between a thing and its Form seems to need a further Form, and so on without end. Each picture here is a copy of a description of a copy.

## Method

Pre-registered in [`docs/plato_telephone_plan.md`](plato_telephone_plan.md), committed before any chain was run. Nothing was changed after the pilot (the first two steps of two chains), which is part of the data.

| Step | What we did |
|---|---|
| Starts (generation 0) | Muse Image's own named-kind doodles from "Can you prompt it out of the Platonic chair?" (`docs/plato.md`): rocking chair, throne, beanbag, wheelchair, office chair, folding chair, high chair, Adirondack chair. Controls: a top hat and a cuckoo clock from the same run. |
| Describe | Muse Spark (`muse-spark-1.3`, reasoning effort minimal) gets the picture (512 px) and *"Describe this drawing so someone could redraw it. One or two sentences. Don't name an artist."* |
| Draw | Muse Image (`muse-image-1.0`, n = 1) gets Plato's Chair's doodle prompt with the description as the object: *"A quick simple doodle sketch of {description}, black marker on plain white, like a 20-second drawing, no text, no shading."* Only the description's edges are cleaned (a leading article lower-cased, a final period dropped). |
| Size | 10 starts × 3 independent chains × 10 generations: 300 pictures and 330 descriptions (the last picture of each chain is described too). Every chain completed; no step failed or was redone. |
| Distance to the Form | DINOv2 (`facebook/dinov2-base`) CLS embeddings after `plato.ink_crop`, cosine distance to the normalized mean of Muse's default doodles of the same thing in the core run (16 chairs; 12 hats, 12 clocks). Reference: the default doodles' own leave-one-out distance to that mean (chair 0.074, hat 0.166, clock 0.109). |
| Convergence | At each generation: the mean distance between chains from different starting chairs (between) and between the 3 chains of the same chair (within). Reference: the spread of the 16 default chairs, 0.134. |
| Words | Whether each description contains the start's kind name (regexes in the plan, e.g. `rock(ing\|er)`, `bean[\s-]?bag`) and the category word (`chair` inside any word). Per chain, the first description without the word (11 = never). |
| Kind labels | Muse Spark (vision, minimal reasoning) answered Plato's Chair's multiple-choice kind question for every picture: the 16 listed kinds of chair (12 of hat or clock), "a plain, ordinary …" or "can't tell, or not a …". |
| CIs | 95%, two-level cluster bootstrap (2,000 replicates): resample the 8 starting chairs, then the 3 chains within each. Spreads never pair a chain with itself. Primary tests use the 24 chair chains; the controls are descriptive. |

Code: `metalesionlab/plato_telephone.py` (protocol, text and bootstrap helpers, tested in `tests/test_plato_telephone.py`) and `scripts/plato_telephone_{run,analyze,figures}.py`. Data, figures and results live outside the repository in `PlatosChair/telephone/`. `public_data/plato_telephone.json` holds the derived statistics and Spark's descriptions.

## Findings

| # | Prediction | Result | Verdict |
|---|---|---|---|
| P1 | Chains drift toward Muse's default chair | Distance 0.513 → 0.579; change **+0.066 [−0.026, 0.180]**; slope +0.004 per generation [−0.004, 0.014]; share of the gap to the default closed −0.15 [−0.48, 0.06] | **Not supported.** If anything, away. |
| P1 check | The drop toward the chair is larger than toward the average of all 35 things | Change toward the 35-thing average −0.025 [−0.088, 0.034]; difference +0.090 [−0.028, 0.225] | **Not supported** (there is no drop to compare) |
| P2 | Different starting chairs converge | Spread between starts 0.606 → 0.729; change **+0.124 [0.029, 0.242]** | **Not supported: the opposite.** They diverge. |
| P3 | The kind's name is lost before "chair" | First lost at description 6.63 [3.67, 9.46] vs 9.96 [8.46, 11.0]; difference **−3.33 [−6.04, −0.79]** | **Supported** |

Other measures (not tests):
- **Each chain wanders.** Distance from a chain's own start grows steadily: 0.15 after one copy, 0.27 after five, 0.38 after ten.
- **The start still matters at the end.** At generation 10, chains from different chairs are 0.36 [0.13, 0.56] farther apart than chains from the same chair.
- **Other references.** Toward the hat prototype: +0.002 [−0.038, 0.046]. Toward the clock prototype: −0.040 [−0.081, −0.005], a small move. Toward people's chairs (the Quick, Draw! average): +0.034 [−0.025, 0.090].

**By start** (mean of 3 chains; distance to Muse's default of the same thing; "kind word" = the descriptions that name it):

| Start | Start → generation 10 | Distance from its own start at 10 | Kind word first missing (chains 1, 2, 3) |
|---|---|---|---|
| rocking chair | 0.49 → 0.43 | 0.18 | kept, kept, kept |
| throne | 0.26 → 0.68 | 0.59 | never said in any chain |
| beanbag | 0.70 → 0.86 | 0.69 | 1, 10, 9 |
| wheelchair | 0.67 → 0.76 | 0.29 | kept, kept, kept |
| office chair | 0.56 → 0.60 | 0.51 | kept, kept, kept |
| folding chair | 0.59 → 0.60 | 0.32 | 9, 1, 6 |
| high chair | 0.25 → 0.17 (0.07, 0.35, 0.09) | 0.36 | 1, 6, 1 |
| Adirondack chair | 0.58 → 0.53 | 0.11 | 3, 2, kept |
| *top hat* | 0.62 → 0.59 (default: baseball cap, 0.17) | 0.23 | kept, kept, kept |
| *cuckoo clock* | 0.57 → 0.64 (default clock 0.11) | 0.19 | kept, kept, kept |

**Words** (exploratory; 24 chair chains):
- Descriptions do not shrink. They stay about 220 characters and 19–20 content words from the first description to the last.
- **What lasts.** Of the words in a chain's first description, "leg" lasts 9.9 descriptions in a row on average, "armrest" 9.3, "seat" 9.0 and "chair" 8.5. "View" lasts 1.1, "cushioned" 1.3, "wooden" 3.0, "slat" and "back" 3.7.
- **What rises.** Words of heavy ink rise despite the prompt's "no shading": "heavily" 0% → 21% of chains, "hatching" 0% → 21%, "filled" 0% → 17%. Shape words rise too: "vertical" 17% → 46%, "oval" 0% → 21%.
- **What falls.** "Back" 79% → 42%, "curved" 46% → 17%, "chair" 75% → 50%, "cushioned" 25% → 0%.

**Kind labels** (Spark shown each picture with the list of 16 kinds of chair; picture side of P3):
- Spark named the right kind for all 10 starting pictures.
- At generation 10 it still picked the starting kind for **79% [50%, 100%]** of the chair chains' pictures, and "still a chair" for 96% [83%, 100%]. So the kind drops more than the category in the pictures too, but much less than in the words (46% of last descriptions name the kind).
- The pictures keep their kind's look longer than the descriptions keep its name. The throne is the clearest case: no first description said "throne", yet Spark picked "a throne" for all 31 of its pictures, crown on a pole included.
- Where it changed: the high chair became "a dining chair" (2 chains) and "an Adirondack chair" (1). The beanbag that turned into a croissant became "can't tell, or not a chair" from generation 2 on. One Adirondack chain ended as "an armchair".
- The choice is forced and lenient. The folding chair that ended as a scribbled diamond was still "a folding chair", and Spark never picked "a plain, ordinary chair" for any picture. Plato's Chair found Spark prefers specific kinds over "plain" too.

**The most striking chains** (the rules were fixed in the analysis script before the wall was drawn):
- Farthest from its start: **beanbag, chain 1**. From the first copy on, Spark described something else: it turned into "a plump croissant", then "a fan-shaped half-ring", and ended as "a semicircular fanlight window" (`figures/rows/beanbag_c0.png`).
- Most drift toward the Form: **high chair, chain 1**. The tray was gone after one copy, and the picture stayed the textbook chair for nine generations (0.25 → 0.09 → 0.07) (`figures/rows/high_chair_c0.png`).
- Most faithful: **Adirondack chair, chain 1** (0.11 from its start after ten copies).

## What it means

- **The textbook chair is a trap door, not a slope.** Plato's Chair found that Muse Image draws one slat-back chair when asked for "a chair". In this loop, that chair took over only where the defining detail was lost in one step (the high chair's tray), and then it held. Chains that kept their name kept their kind, and chains that lost it wandered somewhere new rather than back to the default.
- **Why no collapse?** Spark's descriptions are long and specific (about 220 characters, every generation), so each step passes on a lot. In iterated-learning terms, the data dominate the prior. A shorter description, a lossier describer or a vaguer drawer might collapse more. We didn't test that.
- **What gets lost is the name, and what grows is style.** The kind's name goes about three descriptions before "chair", and the drawings get darker and more hatched over the chain, though every prompt says "no shading".
- **Fair to Meta.** This is the default behaviour of two Muse models under one protocol. It is a good-news result for variety: in this loop the models keep distinct chairs distinct, and the drift into the conventional that Bartlett described shows up only for the high chair.

## Caveats

- **The description is the bottleneck.** Anything Spark doesn't say can't survive, and anything it stresses gets drawn bigger. This measures the pair (describer and drawer), not Muse Image alone. The high chair shows the drawer can also drop what was said.
- **One prompt.** One describing prompt, one drawing template, minimal reasoning. "One or two sentences" let Spark write long, detailed sentences.
- **Vision to text is lossy.** Pictures were never expected to stay identical. Distance from the start grows partly because every step adds noise, not only because of any pull.
- **Small n.** 8 chairs × 3 chains; the controls are one picture each. A seed's three chains share their start, which is why the bootstrap resamples starts first.
- **DINOv2 measures looks.** It counts heavier hatching as difference too, and some of the drift away from the default is style, not a different chair.
- **Spark labels its own pictures' kinds.** The labeler is one of the two models in the loop.
- **Not run:** the optional Quick, Draw! starting chairs, to keep within budget (see the plan).

## Cost

- **Total: $3.66** of this experiment's $4.00 cap (its own spend log, `PlatosChair/telephone/spend.jsonl`).
- 300 Muse Image pictures: $3.00.
- 330 Muse Spark descriptions: $0.38 (about $0.0011 each at minimal reasoning).
- 310 Spark kind labels: $0.28.
- DINOv2 ran on this Mac, at $0.

## Figures

In `PlatosChair/telephone/figures/`:
- `telephone_wall.png`: all 30 chains, one row each, generations 0–10, with Muse's default picture of the same thing at the right
- `rows/<start>_c<k>.png`: one chain per file
- `convergence.{png,svg}`: distance to the default chair, spread between and within starts, and words and labels kept, with 95% CIs
- `last_words.png`: chain 1 of each chair at descriptions 0, 1, 5 and 10, with the kind's name marked

Page: `/plato/telephone` (filmstrips of every chain with a generation slider and Spark's description underneath).

## References

- Bartlett, F. C. (1932). *Remembering: A Study in Experimental and Social Psychology.* Cambridge University Press.
- Carbon, C.-C., & Albrecht, S. (2012). Bartlett's schema theory: The unreplicated "portrait d'homme" series from 1932. *Quarterly Journal of Experimental Psychology*, 65(11), 2258–2270. doi:10.1080/17470218.2012.696121
- Griffiths, T. L., & Kalish, M. L. (2007). Language evolution by iterated learning with Bayesian agents. *Cognitive Science*, 31(3), 441–480.
- Kirby, S., Cornish, H., & Smith, K. (2008). Cumulative cultural evolution in the laboratory: An experimental approach to the origins of structure in human language. *PNAS*, 105(31), 10681–10686. doi:10.1073/pnas.0707835105
- Shumailov, I., Shumaylov, Z., Zhao, Y., Papernot, N., Anderson, R., & Gal, Y. (2024). AI models collapse when trained on recursively generated data. *Nature*, 631, 755–759. doi:10.1038/s41586-024-07566-y
- Xu, J., & Griffiths, T. L. (2010). A rational analysis of the effects of memory biases on serial reproduction. *Cognitive Psychology*, 60(2), 107–126.
- Plato, *Republic* X (596a–598b), in Benjamin Jowett's translation (public domain); the passages quoted on the page come from `public_data/plato_passages.json`.

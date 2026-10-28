# Plato's Chair

Plato thought there is one ideal chair. If you ask an AI to draw 16 chairs and 16 boats, are its chairs all alike while its boats vary? How spread out is each concept in the AI's imagination, and does that match how varied people's drawings of the same thing are?

**Short answer:** Muse Image draws almost every concept far more uniformly than people do. Its spread is about half of people's (median ratio 0.49), and 34 of 35 concepts fall below the human level. Whether the concepts people draw most variably are the ones the AI varies is unclear: the rank correlation is 0.38 with DINOv2, but 0.07–0.27 with three other vision models, every CI including zero (see "Does it depend on DINOv2?"). Its chair is close to a Platonic one: the same slat-back dining chair, in the same three-quarter view, 16 times. **This is specific to Muse, not to image models in general.** Given the same prompt, Stable Diffusion XL varies far more than Muse: more for 34 of 35 concepts, at about 2.4 times the spread. On the same measure it is no more uniform than people, though much of its extra variety is drawing style, not different objects (see "Is it just Muse?"). **Muse knows the variety:** "any kind of chair" still gives the textbook chair, but asked for named kinds it draws as varied as people. And people mostly draw the textbook chair too: their extra spread is in how they draw it, not which chair (see "Can you prompt it out of the Platonic chair?").

> **Does it depend on DINOv2?** Not for the main result. We re-measured everything with Meta's DINOv2-large and Perception Encoder (PE-Core), and with Google's SigLIP 2 as a non-Meta control, under rules fixed in advance.
> - **What holds in all four models:**
>   - Muse is more uniform than people (median ratio 0.29–0.49; 34 or 35 of 35 concepts) and more uniform than SDXL.
>   - Its chair is flattened.
>   - "Any kind" changes nothing, and named kinds lift it above people.
> - **What depends on the model:** which concepts are flattened most. Umbrella first is a DINOv2 finding; book last holds in all four.
> - **What doesn't hold:** the weak link between people's spread and Muse's (0.38).
>
> Details: [plato_robustness.md](plato_robustness.md).

## Method

| Step | What we did |
|---|---|
| Concepts | 35 Quick, Draw! categories, drawn in priority order. Tier 1 (16 AI pictures each): chair, boat, face, house, cat, cup, tree, car, key, umbrella. Tier 2 (12 each): the 13 other demo-set words that exist in Quick, Draw!, plus flower, bird, fish, dog, shoe, hat, clock, lamp, book, guitar, apple and person. |
| Substitutes | Quick, Draw! has no "boat", "lamp" or "person". We used **sailboat**, **floor lamp** and **yoga** (its whole-body human figure; the AI prompt is "a person doing yoga"). Five demo words have no category at all and are left out: anchor, kettle, glove, whistle, igloo. |
| AI drawings | Muse Image 1.0 (`muse-image-1.0`), prompt: *"A quick simple doodle sketch of {a chair}, black marker on plain white, like a 20-second drawing, no text, no shading."* There is no seed parameter, so we made separate calls of n=4: 4 calls for tier 1 and 3 calls for tier 2. Pictures are downscaled to 512 px. |
| Human drawings | Google Quick, Draw! simplified strokes, streamed line by line from the public bucket. We kept the first 200 drawings per category with `recognized=true` and rendered them at 256 px, black on white. |
| Normalising | Both sources are cropped to their ink, padded to a square and resized (Quick, Draw! drawings are already scaled to fill their box). AI "paper" (gray, textured or vignetted backgrounds) is flattened to white first. |
| Embedding | Meta DINOv2 (`facebook/dinov2-base`, Apache-2.0), run locally on a Mac (MPS). We use the CLS token; the mean patch token is a robustness check. |
| Spread | Mean pairwise cosine distance among a concept's pictures. |
| Equal n | The AI side is the concept's n pictures (16 or 12), with a 2,000-sample bootstrap CI over pictures. For the human side we drew 200 random subsets of the same n from the 200 drawings. The human spread is the mean of those subsets, with a bootstrap CI over drawings. |
| Homogenization index | AI spread divided by human spread, with a CI from independent bootstraps of both. Below 1 means the AI is more uniform than people. |
| Between-concept baseline | Mean distance from a concept's pictures to every other concept's pictures in the same source. Relative spread is within-concept spread divided by this baseline. |

Code: `metalesionlab/plato.py` and `scripts/plato_{generate,human,embed,analyze,figures}.py`; the SDXL comparison is `scripts/plato_sdxl_{generate,analyze,figures}.py`. Data, results and figures live outside the repo, in `$PLATO_DIR` (default `PlatosChair/core/`). `public_data/plato_concept_spread.json` holds only derived statistics.

## Findings (35 concepts)

| | Result |
|---|---|
| Overall | The AI is more uniform than people for 34 of 35 concepts. The CI is entirely below 1 for 33 of them. Median homogenization index: **0.49**. Mean spread: AI 0.18, people 0.37. For 33 concepts, the AI's set is more uniform than every one of 200 random sets of human drawings of the same size. |
| Relative to how distinct concepts are | The AI's concepts are also farther apart from each other (between-concept distance 0.75, against 0.52 for people). Relative to that baseline, the AI is about 3 times tighter: median relative spread 0.22 against 0.73 for people (median relative index 0.34). |
| Does the AI's spread follow people's? | Only modestly. Spearman rho = **0.38** [95% CI 0.08, 0.62], permutation p = 0.025. On relative spread: 0.30 [-0.01, 0.56]. With patch-mean embeddings: 0.33 [0.00, 0.60]. The ranking of the index barely changes between the two embeddings (rho 0.86). |
| Most uniform AI concepts | umbrella (0.055), bicycle (0.062), shoe, ladder, face, cat |
| Most varied AI concepts | book (0.36), key (0.31), spoon, hat, tree, cactus |
| Most homogenized (index) | umbrella **0.14** [0.11, 0.18], bicycle 0.18 [0.14, 0.22], shoe 0.29, scissors 0.32, cup 0.32, carrot 0.33 |
| Least homogenized | book **1.04** [0.87, 1.21] (the only concept the AI varies as much as people: open, closed, stacked, at an angle), clock 0.80 [0.38, 1.20] (people draw clocks very uniformly too), candle 0.76, tree 0.75, hat 0.72, key 0.71 |
| Kinds of concept | No difference. Mean index: fixed-shape artifacts 0.49, many-style artifacts 0.52, natural kinds 0.51, person 0.48 (2 items). |

**Chair vs. boat (the lead's example).**
- People draw chairs more variably than boats: 0.36 vs. 0.31.
- The AI does the reverse. Its chairs (0.13 [0.09, 0.19]) are, if anything, more alike than its sailboats (0.20 [0.15, 0.24]). The difference has a CI of [-0.01, 0.13], so this is a trend, not a sure thing.
- So the AI flattens chairs the most: index 0.37 [0.24, 0.55] for chairs against 0.63 [0.49, 0.77] for boats.
- Most of the 16 people drew a chair in side view. The AI drew one slat-back dining chair in three-quarter view, over and over.

**Person.**
- **Face.** People draw faces very uniformly: a circle with a smile is among the lowest human spreads, 34th of 35. The AI is even more uniform: 0.12 against 0.26, index 0.44 [0.37, 0.51].
- **Whole person (yoga).** People's drawings are among the most varied (0.43, 7th of 35). The AI's are about half as varied: 0.22 [0.15, 0.29], index 0.52 [0.35, 0.66]. Almost all of them show tree pose or lotus, in the same cartoon style.
- So the lead's suspicion holds: people picture a person far more variously than the AI does. But "person" is not special: the AI compresses it about as much as the median concept.

**Sampling check.** Pictures from the same API call are no more alike than pictures from different calls (distance 0.185 vs. 0.185). The n=4 batches therefore behave like independent draws.

**Recognisability check.** In DINOv2 space, 85% of the AI doodles sit closest to the human centroid of their own concept, out of 35. The exceptions are concepts where style differs most:
- person 0% (the AI draws cartoon people, people draw stick figures)
- dog 8%
- bench 17%
- hat 25%

## Is it just Muse? (a second generator)

Do AI image models in general picture one prototype, or is it Muse? We drew the same 35 concepts with an open model, Stable Diffusion XL, and measured them the same way.

**Short answer:** It is mostly Muse.
- **SDXL vs. Muse.** SDXL's pictures vary far more than Muse's: more for 34 of 35 concepts, and about 2.4 times the spread.
- **SDXL vs. people.** On the core measure SDXL is not more uniform than people: its spread is above people's for 26 of 35 concepts.
- **What varies.** Much of SDXL's variety is in how it draws, not in what it draws. It adds frames, scenes, hatching and gray backgrounds despite "no shading" and a negative prompt. For bicycle, helicopter and umbrella it draws one classic object every time, in different settings.

| Step | What we did |
|---|---|
| Generator | Stable Diffusion XL base 1.0 (`stabilityai/stable-diffusion-xl-base-1.0`, fp16, CreativeML OpenRAIL++-M), self-hosted on a lab GPU (L40S). 560 pictures in 21 minutes, $0. |
| Prompt | The same doodle prompt as Muse. Negative prompt: *"shading, photo, photorealistic, paper texture, 3d render, color, text"*. Settings: 768 px, 25 steps, Euler scheduler, guidance 5 (the diffusers default). |
| Pictures | 16 per concept for all 35 concepts, downscaled to 512 px. Each picture has its own seed, recorded in `meta.json`: 20261026 + 1000 × concept index + picture index. Muse has only 12 pictures for tier 2 concepts. That is fine: mean pairwise distance doesn't depend on n, and SDXL's first 12 pictures rank the concepts like all 16 (rho 0.98). |
| Analysis | Unchanged: the same ink crop, DINOv2 CLS embeddings, cached human embeddings and bootstraps. For Muse vs. SDXL, the difference and ratio of spreads get CIs from independent bootstraps of both picture sets. |

| Question | Result |
|---|---|
| Is SDXL more uniform than people? | **No, on the core measure.** Median SDXL/human ratio 1.22 (Muse: 0.49). SDXL is below people for 9 of 35 concepts; the CI is entirely below 1 for only 2: helicopter 0.49 [0.41, 0.58] and guitar 0.72 [0.59, 0.86]. It is entirely above 1 for 16, including saw 1.97 [1.75, 2.17], clock 1.89 and book 1.65. With patch-mean embeddings, SDXL is below people for only 2 concepts. |
| ... relative to how distinct its concepts are? | **Mildly yes.** SDXL's concepts are far apart (between-concept distance 0.85; Muse 0.75, people 0.52). Relative to that, its median spread is 0.52, against 0.73 for people and 0.22 for Muse. The relative index is below 1 for 31 of 35 concepts (median 0.75; Muse 0.34). |
| Is Muse more uniform than SDXL? | **Yes, for 34 of 35 concepts.** The CI of the difference excludes zero for 32 of them. Median Muse/SDXL spread ratio 0.42; mean spread Muse 0.18, SDXL 0.44, people 0.37. The one exception is helicopter, SDXL's most uniform concept (Muse/SDXL 1.22 [0.94, 1.56]). |
| Do the two AIs flatten the same concepts? | **Only weakly.** Rank correlation of Muse and SDXL spread: rho 0.30 [-0.05, 0.60], p = 0.07. Holding people's spread constant: 0.27 [-0.09, 0.57]. SDXL's spread does not track people's either: 0.15 [-0.19, 0.45], against 0.38 for Muse. |

| Concept | Muse spread | SDXL spread | People | Muse/human | SDXL/human | Rank, 1 = most uniform of 35 (Muse, SDXL) |
|---|---|---|---|---|---|---|
| umbrella | 0.05 [0.04, 0.07] | 0.43 [0.30, 0.56] | 0.39 | 0.14 | 1.11 [0.77, 1.46] | 1, 16 |
| bicycle | 0.06 [0.05, 0.08] | 0.29 [0.22, 0.35] | 0.34 | 0.18 | 0.85 [0.64, 1.05] | 2, 3 |
| chair | 0.13 [0.09, 0.20] | 0.43 [0.36, 0.49] | 0.36 | 0.37 | 1.17 [0.98, 1.37] | 10, 15 |
| book | 0.36 [0.30, 0.42] | 0.57 [0.53, 0.63] | 0.35 | 1.04 | 1.65 [1.49, 1.81] | 35, 30 |
| boat | 0.20 [0.15, 0.24] | 0.28 [0.22, 0.34] | 0.31 | 0.63 | 0.91 [0.71, 1.10] | 21, 2 |
| face | 0.12 [0.10, 0.13] | 0.35 [0.27, 0.44] | 0.26 | 0.44 | 1.34 [1.05, 1.67] | 5, 8 |
| person (yoga) | 0.22 [0.15, 0.28] | 0.42 [0.37, 0.47] | 0.43 | 0.52 | 0.97 [0.86, 1.08] | 26, 14 |

How the two AIs compare on the lead's concepts:
- **Bicycle: both flatten it.** It is the 2nd most uniform concept for Muse and the 3rd for SDXL. SDXL draws the same side-view bicycle every time.
- **Book: both vary it.** It is the 35th of 35 for Muse and the 30th for SDXL.
- **Umbrella: they disagree.** It is Muse's most uniform concept but only 16th for SDXL. SDXL's umbrellas are one classic shape, but seen from above, from below or as a beach parasol, in rain scenes, and once as a sheet of many umbrellas. DINOv2 counts that as variety.
- **Chair: middling for both** (10th and 15th). Still, SDXL's chairs are different chairs: armchairs, an office chair, a dining chair, a folding chair. Muse draws one slat-back chair.

**Style differences.** SDXL ignored "no shading" and most of the negative prompt.
- **Frames and scenes.** 54% of its pictures have ink reaching all four edges (a frame, a scene or a background). Muse and people: 0%.
- **Ink and gray.** Ink covers 27% of the cropped picture, against 10% for Muse and 4% for people. 18% of the raw picture is mid-gray, against 2% for Muse.
- **Color.** 16 of its 560 pictures are partly in color.
- **Stronger negative prompt.** A spot check with a longer negative prompt (adding hatching, background, scenery, frame, border, sketchbook) changed little: the same seeds gave the same compositions.

So SDXL's spread includes style variation, and DINOv2 sees style. Partial controls:
- **Dropping framed and scene pictures.** 26 concepts keep at least 6 pictures. Their SDXL spread comes close to people's (median ratio 1.07, below 1 for 11 of 26) and is still far above Muse's (24 of 26).
- **Style lifts every concept rather than reordering them.** A concept's SDXL spread barely tracks its share of framed or scene pictures (rho 0.23 [-0.09, 0.53]).

**Failures.** For "a saw", SDXL rarely drew a hand saw. It drew assorted tools, gears and a circular saw.
- Only 6% of those pictures sit nearest the human saw centroid, so saw's top SDXL spread reflects confusion, not imagination.
- Person (6%) and clock (25%) also match people's drawings poorly. SDXL draws detailed figures and ornate clocks, while people draw stick figures and circles.
- Overall, 77% of SDXL pictures sit nearest their own concept's human centroid (Muse 85%).

**Caveats.** One SDXL setting: base model without the refiner, guidance 5, one negative prompt. Higher guidance would probably reduce its variety. There is no style-matched measure, so "SDXL is as varied as people" is an upper bound on its variety in object ideas. The firm result is the Muse vs. SDXL contrast, which the grids confirm by eye.

Results: `results_sdxl.json`. Figures:
- `grid3_chair.png`, `grid3_umbrella.png`, `grid3_book.png` (16 Muse, 16 SDXL and 16 people, ink-cropped)
- `index_ranked_two_ai.{png,svg}`
- `scatter_muse_vs_sdxl.{png,svg}`

SDXL: Stability AI, CreativeML OpenRAIL++-M. Its pictures are kept outside the repository, like the others.

## Can you prompt it out of the Platonic chair?

Muse Spark can name 16 kinds of chair, and Muse Image draws every one of them when asked. So why does it draw one chair by default? And do people vary in **which** chair they draw, or only in **how** they draw it? We asked Muse Image for each thing in three more ways. Besides visual spread, we labeled which kind of object every picture shows.

**Short answer:** Muse draws the textbook version by default, but it knows the variety and draws it when asked by name. People mostly draw the textbook version too.
- **"Any kind" changes nothing.** "A chair (any kind of chair)" still gives the same slat-back dining chair 16 times. Across 35 things the spread stays at half of people's (median ratio 0.49; 0.96 times the usual prompt). SDXL ignores the phrase too (0.98 times its usual spread).
- **Naming the kinds works.** When Muse Spark lists kinds and Muse Image draws one of each, the spread rises to 1.30 times people's: 2.7 times the usual prompt, and above people's for 27 of 35 things. Asking for "an unusual or different kind" gives 1.07 times people's (10 things).
- **Variety has a price.** The new pictures look less like people's drawings of the thing: 66–67% sit nearest their own concept's human centroid, against 85% with the usual prompt. Glimmer answered "can't tell, or not a chair" for half of the "unusual" chairs, and "... not a car" for 14 of 16 "unusual" cars. Some of Spark's kinds come from other senses of the word: a piano key, a map legend key, a clock face, a bra cup.
- **People mostly draw one kind too.** Of people's recognisable drawings, 83% are the plain, ordinary kind, the same share as Muse's usual prompt (83%). For 30 of 35 things, people's most common kind is also Muse's. People do draw somewhat more kinds: kind diversity 0.21 against 0.12, higher for 24 of 35 things and never lower. But that is far below what Muse draws when the kinds are named (0.81).
- **People's spread is mostly "how", not "which".** People's drawings of their single most common kind are almost as spread out as all their drawings: a median of 96% of the full spread. A concept's human spread barely tracks how many kinds people draw (rho 0.30 [-0.08, 0.61]).

**The chair.** 
- Usual prompt: spread 0.13 (0.37 of people's). "Any kind": 0.09 (0.24), the same chair again.
- "An unusual kind": 0.59 (1.62): spring chairs, egg chairs, a snail-shell chair. Glimmer calls half of them "not a chair", and only 3 of 16 sit nearest people's chairs in DINOv2 space.
- Named kinds: 0.55 (1.50). Sixteen different chairs (rocking chair, beanbag, wheelchair, throne ...), each recognised as its kind; 13 of 16 sit nearest people's chairs.
- People: spread 0.36. Of their recognisable chairs, 84% are a plain, ordinary chair, mostly the same simple side view. Those plain chairs alone carry 98% of people's spread.

**The umbrella.** 
- Muse: usual prompt 0.055 (0.14 of people's), "any kind" 0.065 (0.17), "an unusual kind" 0.40 (1.03), named kinds 0.33 (0.84).
- Many of the named umbrellas (golf, stick, beach, patio, LED, studio) are drawn as the classic umbrella, and Glimmer labels 11 of 16 of them plain.
- People: 98% of recognisable umbrellas are the plain one (kind diversity 0.04). So people and Muse both draw one umbrella. People's large visual spread (0.39) is how they draw it, not which umbrella.

**Where people do vary the kind:** hats (kind diversity 0.80: brimmed hats, caps, top hats, party hats; Muse drew a baseball cap 11 of 12 times), yoga poses (0.76 against 0.53), and faces (0.45 against 0.13).

| Step | What we did |
|---|---|
| Prompts | Four ways to ask for the same thing, all inside the core doodle template. **Usual**: the core prompt ("a chair"). **Any kind**: "a chair (any kind of chair)"; for yoga, "a person doing yoga (any person, any pose)". **An unusual kind**: "a chair (any kind of chair at all; pick an unusual or different kind)", tier 1 only (10 things). **Named kinds**: Muse Spark (`muse-spark-1.3`, reasoning effort low) was asked to "List 16 clearly different kinds of chair that someone could draw, as short noun phrases"; for yoga, 12 poses. Muse Image then drew each kind once. |
| Pictures | n per thing as in the core run (16 for tier 1, 12 for tier 2): 460 "any kind" and 160 "unusual" (separate calls of n=4), 460 "named kinds" (one call each). Chair and umbrella reuse a pilot run with the same prompts. Spark's lists are kept as written. |
| Visual spread | Unchanged: ink crop, DINOv2 CLS embeddings, mean pairwise cosine distance, bootstrap CIs, human drawings subsampled to the same n. Two ratios: to people's spread, and to the usual prompt's spread (CI from independent bootstraps of the two sets). |
| Recognisability | Share of pictures whose nearest human centroid (of 35) is their own concept, as in the core run. |
| Kind labels | Muse Glimmer 30B (FP8, self-hosted on one L40S) answered one multiple-choice question per picture: *"Someone was asked to draw a chair. Which kind of chair is in this drawing? Pick the one option that fits best. If it is just an ordinary chair and not clearly one of the specific kinds, pick 'a plain, ordinary chair'."* The options were Spark's kinds, then "a plain, ordinary chair", then "can't tell, or not a chair". We read the answer from the option letters' logits, not from generated text. Every picture was asked twice, with the kinds in forward and reversed order, and the two answers averaged. In total, 10,020 pictures: all 7 AI sets and the 200 cached human drawings per thing. |
| Validation | For "named kinds" pictures the right answer is known: picture i shows kind i. We measured accuracy, accuracy counting "plain" as a near miss, and confusions. A thing's kind labels count as **reliable** if Glimmer names at least half of its listed pictures correctly. |
| Kind diversity | Per set: **Simpson diversity**, the chance that two different pictures show different kinds (0 = all one kind; it does not grow with n; CI by bootstrap over pictures). Also: number of distinct kinds, entropy, share "plain", and the most common kind (the prototype). "Can't tell" is reported separately and left out of the kind measures. People: all 200 drawings, with distinct kinds counted in random sets of the AI's n. |
| How or which | For people: spread of their drawings of the prototype kind only, against all their drawings, both subsampled to the AI's n. |
| Second opinion | Muse Spark (vision, minimal reasoning) answered the same question for a random sample: 140 named-kind pictures, 156 human drawings and 70 usual-prompt doodles ($0.48). |
| SDXL (stretch) | Stable Diffusion XL drew "any kind" and "named kinds" with the settings of its usual-prompt run and the same seeds (picture i of a thing has the same seed in every condition), on a lab GPU, $0. |

| Question | Result |
|---|---|
| Does "any kind" add variety? | **No.** Median ratio to people 0.49, as with the usual prompt. "Any kind" is 0.96 times the usual spread, above it (CI) for 1 of 35 things. Kind diversity 0.13 against 0.12. SDXL: 0.98 times its usual spread. |
| Does "an unusual kind" add variety? (10 things) | **Yes, with drift.** Ratio to people 1.07, above people's for 7 of 10 (CI for 4). 2.35 times the usual spread (CI for 9 of 10). Only 66% sit nearest their own human centroid (usual 96% for these 10). Glimmer says "can't tell, or not a ..." for 31%: car 88%, cup 75%, house 69%, chair 50%. |
| Do named kinds add variety? | **Yes.** Ratio to people 1.30, above people's for 27 of 35 (CI for 17; below for 3). 2.73 times the usual spread (CI above for 32 of 35). 8.7 distinct kinds per set of 12–16 and kind diversity 0.81. Recognisability falls to 67%, lowest for kinds from other senses of the word (key 25%, clock 8%). |
| Is the gap Muse-specific? | **Mostly.** SDXL named kinds: 1.69 times people's, but only 1.38 times SDXL's own usual spread (Muse 2.73). SDXL's usual prompt already shows several kinds (diversity 0.44, against 0.12 for Muse): its chairs are mostly armchairs. Muse's narrow default is a default, not a gap in what it knows. |
| How good is the kind labeler? | Glimmer names the right kind for 58% of the 460 named-kind pictures (chance 7%), 88% counting "plain" as a near miss. Errors: "plain" 30%, another kind 8%, "can't tell" 4%. It is reliable (≥ 50%) for 22 of 35 things: hat, yoga 100%, chair, face 94%, umbrella 25%, cat 25%, apple 0%. Breeds, varieties and similar-looking kinds are often drawn and read as the plain one. Confident answers (probability ≥ 0.6) that name a specific kind are right 91% of the time (269 answers), unsure ones 65%. On SDXL's named kinds: 43% (67%). |
| Do people draw more kinds than Muse's usual prompt? | **A few more.** Kind diversity 0.21 against 0.12 (reliable things: 0.30 against 0.17). People's diversity is higher for 24 of 35 things (CI for 13) and lower for none. Distinct kinds in a set of the AI's size: 1.65 against 1.49. Treating Glimmer's unsure specific answers as plain: 0.14 against 0.10. |
| Same prototype? | **Yes, mostly.** For 30 of 35 things, people's most common kind is Muse's. It is "a plain, ordinary ..." for 33 things for people and 30 for Muse. The exceptions: hat (people plain, Muse baseball cap), shoe (plain vs sneaker), saw (plain vs hand saw), yoga (standing figure vs tree pose), harp. |
| Is people's spread kinds or drawing? | **Drawing.** Of people's recognisable drawings, 83% are the plain kind (Glimmer). Their drawings of the prototype kind alone are 96% as spread as all their drawings (median over 34 things). Human spread and human kind diversity are only weakly related across things: rho 0.30 [-0.08, 0.61]. |
| Second opinion (Muse Spark) | Spark is the better labeler on named-kind pictures: 66% against Glimmer's 55% on the same 140. It picks specific kinds more often everywhere. On its sample, kind diversity is 0.26 for Muse's usual prompt, 0.54 for people and 0.90 for named kinds; Glimmer on the same pictures: 0.11, 0.16 and 0.80. The two agree on only 44% of people's drawings. Glimmer says "can't tell" for 35% of them, Spark for 6%. So the order (Muse usual < people << named kinds) holds for both labelers, but how much more varied people are depends on the labeler. |

**Caveats.**
- **The labels are a model's reading.** Glimmer misses kinds that look ordinary in a doodle, and rough 20-second drawings make it worse: it says "can't tell" for 33% of people's drawings (harp 95%, scissors 77%, bicycle 74%). Spark sees more kinds in the same drawings. We report Glimmer for all pictures and Spark as a check. We trust the ordering of conditions more than any absolute level.
- **The kind lists are Spark's.** Breeds and varieties (cat, apple, carrot, snail) cannot be told apart in a black-and-white doodle, so those things fall outside the reliable set. Lists that stray into other senses of the word (key, face, cup) inflate the named-kinds spread and lower recognisability. A list written for line drawings would be a fairer test of "kinds".
- **Plain or specific?** A slat-back dining chair is both a dining chair and an ordinary chair. Glimmer labeled Muse's usual chair "plain" 15 of 16 times and "dining chair" once. The prototype comparison treats these as different kinds.
- **One wording per condition.** "Any kind" and "unusual" are single phrasings. Other wordings, such as "a different chair each time", might do better. Each call of n=4 is independent, so Muse never sees its earlier pictures.
- **Small n.** 12–16 pictures per set and 10 things for "unusual". Chair and umbrella reuse the pilot's "unusual" and "named kinds" pictures, made with the same prompts.

Cost: 1,080 new Muse Image pictures, 35 Spark lists and the Spark sample: $11.51 including the pilot. Glimmer and SDXL ran on lab GPUs at $0.

Code: `scripts/plato_generate.py --style doodle_any|doodle_unusual|doodle_listed`, `scripts/plato_kinds_label.py` (prepare, label on a GPU, spark), `scripts/plato_variety_analyze.py` and `scripts/plato_variety_figures.py`. SDXL: `scripts/plato_sdxl_generate.py --condition any|listed`. Results: `results_variety.json`; derived statistics: `public_data/plato_variety.json`. Figures:
- `variety_<thing>.png` for the 10 tier-1 things: five rows of 16 (usual, any kind, an unusual kind, named kinds, people) with each row's spread and number of kinds
- `variety_spread.{png,svg}`: spread compared with people's, by prompt, for Muse and SDXL
- `variety_kinds.{png,svg}`: kind diversity by prompt and for people

## Link to naming (exploratory, n = 15)

For the 15 demo words that exist in Quick, Draw!, we recorded:
- Muse Spark name agreement on the demo pictures
- Muse Glimmer's intact naming (glimmer_names.json)
- per-item accuracy across 229 Glimmer lesion conditions (`runs/lesion/demo_en/`), overall and by localizer (language, naming, visual)
- accuracy across 18 Spanish conditions (`demo_es`, matched by gloss)

**This is exploratory and underpowered.**
- Spark and intact Glimmer are at ceiling (all correct), so they can't correlate with anything.
- No spread measure tracks lesion robustness. Every |rho| is 0.35 or less, and every CI spans zero. Examples:
  - AI spread vs. overall lesion accuracy: rho 0.09 [-0.44, 0.56]
  - human spread vs. accuracy under language-localizer lesions: -0.32 [-0.75, 0.23]

Per-concept values are in `results.json` under `naming`.

## Caveats

- **Style mismatch.** The AI's "20-second doodle" is a clean, sketchy marker cartoon. Quick, Draw! drawings are real 20-second mouse or finger drawings, often unfinished, by players worldwide.
  - Part of the human spread is skill and noise, not a different idea of the object. That is why the absolute index (about 0.5) matters less than the ranking across concepts and the relative (between-concept) version.
  - Style differs more for some concepts (person, dog) than others.
- **Prompt sensitivity.** One prompt template, one style. "Any kind" leaves the spread unchanged, while naming the kinds or asking for an unusual one lifts it above people's (see "Can you prompt it out of the Platonic chair?"). Other wordings, such as "a children's drawing", are untested. The realistic-photo style was skipped to save budget.
- **The image model's sampling.** There is no seed or temperature control, and separate calls are the only source of variety. Muse Image returned mostly 3:2 pictures (309 of 460) and some square ones; cropping to the ink removes that difference.
- **Small n.**
  - Tier 2 concepts have only 12 AI pictures, so some CIs are wide: clock [0.09, 0.28] and harp [0.08, 0.28], each driven by one or two unusual drawings.
  - The cross-concept correlation rests on 35 concepts, and the naming link on 15.
- **Category substitutes.** Boat is sailboat, lamp is floor lamp, and person is yoga. Humans saw only the word "yoga"; the AI got "a person doing yoga".
- **One embedding model.** DINOv2 is a vision model. "Spread" is visual spread, not conceptual spread. The kind labels in "Can you prompt it out of the Platonic chair?" are a first measure of conceptual variety. Three other vision models give the same direction, but they rank the concepts differently (see `docs/plato_robustness.md`).
- **Human sample.** We used the first 200 recognized drawings in file order, not a random sample of all drawings.

## Next steps

1. **Second generator.** Done with SDXL (see "Is it just Muse?"). An SDXL guidance sweep would show how much one model's settings move its spread, since higher guidance usually means less variety.
2. **Prompt sweep.** Done for variety prompts (see "Can you prompt it out of the Platonic chair?"). Still open: other wordings ("a different chair each time"), kind lists written for line drawings, and the realistic-photo style for 10 concepts (about $1.60).
3. **Style-matched comparison.** Thin both sources to single-pixel strokes before embedding, or prompt for "one continuous thin line".
4. **Spread inside Muse Glimmer.** Measure each concept's spread inside the model's layers (PlatosChair/inside_glimmer). Then test the lead's hypothesis on more items, with graded lesion severities rather than one accuracy score: diffuse concepts are harder to name and lost first under damage.
5. **Web panel and video moment** (see the final report).

Human drawings: Google Quick, Draw! dataset, Google Creative Lab, CC BY 4.0 (https://github.com/googlecreativelab/quickdraw-dataset). The drawings are never committed to this repository.

**Robustness:** the core and variety results hold with DINOv2-large, Meta PE-Core and Google SigLIP 2 (Muse/people 0.29–0.49, 34 or 35 of 35 concepts below people; Muse below SDXL; named kinds above people); only the per-concept ranking and the 0.38 link to people's spread depend on DINOv2 (`docs/plato_robustness.md`).

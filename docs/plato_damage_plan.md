# Plato's Chair, damaged: pre-registered plan

Written **Oct 27, 2026**, after a small pilot and before the main runs. The commit is the
timestamp. Results go in `docs/plato_damage.md`. **The pilot set the dose ranges and showed one
problem with a measure** (see "Pilot" at the end). No pilot picture enters the main analysis.

## Question

If you damage the "language part" of an AI that draws, what happens to the chairs it draws, and to
how it recognises chairs?

In semantic dementia, drawings lose distinctive features and drift toward the typical member of the
category (Bozeat et al. 2003, "A duck with four legs"), and specific things get general names. Our
analogy: as damage to an image model's language part grows, a rocking chair might turn back into
the plain, Platonic chair, while damage to its drawing machinery should degrade the lines but keep
the kind. This is a model. The neurology link is an analogy, not a claim about people.

## Arms

1. **SDXL draws (main arm).** Stable Diffusion XL base 1.0 (Stability AI, CreativeML OpenRAIL++-M),
   fp16, on one lab L40S. Language part: its two text encoders (CLIP ViT-L, 12 layers × 3,072 MLP
   neurons; OpenCLIP bigG, 32 × 5,120). Drawing part: the UNet (70 transformer blocks; one unit is
   one feed-forward neuron after GEGLU, 2,560 or 5,120 per block). Lesions are reversible forward
   hooks (`metalesionlab/sdxl_lesions.py`); no weight is edited.
2. **Clocks.** The same lesions on "a simple clock face showing <time>" (a generic instruction, not
   any clinical test's wording), scored by Muse Spark with our own rubric.
3. **Glimmer understands.** Muse Glimmer 30B, damaged with the lesion lab's tools, looks at Muse
   Image's named-kind doodles and says which kind of thing each one shows.
4. **Stretch: Janus-Pro-7B** (DeepSeek, MIT), one model that both draws and understands, damaged
   once in its shared language model, only if arms 1–3 are done.

## Pictures and prompts (SDXL)

- **Template:** `plato.STYLES["doodle"]` ("A quick simple doodle sketch of {phrase}, black marker on
  plain white, like a 20-second drawing, no text, no shading."), the SDXL comparison's negative
  prompt, 768 px, 25 steps, guidance 5, saved at 512 px.
- **Chair:** "a chair" (the plain prompt) and 8 named kinds: rocking chair, armchair, office chair,
  folding chair, high chair, wheelchair, beanbag chair, throne.
- **Generality check:** hat ("a hat"; top hat, baseball cap, cowboy hat) and bird ("a bird"; owl,
  penguin, flamingo).
- **Clocks:** 3:00, 6:30, 8:45, 4:20, 1:55 and 10:10 (10:10 is the "advertising" time image models are
  said to draw whatever is asked).
- **Seeds:** picture i of a prompt has seed 20261027 + 1000 × prompt index + i in **every** damage
  condition, so pictures are paired across damage levels; no two prompts share a seed.
- **n:** 8 seeds per prompt per condition (chair: 8 kinds × 8 = 64 paired pictures per condition);
  the intact plain prompts get 16 (the prototype). Clocks: 8 seeds per time.

## Lesion families and doses (SDXL)

| Family | Site | What is done | Doses |
|---|---|---|---|
| text-zero | both text encoders | zero a random share of every layer's MLP neurons | 0.2, 0.25, 0.27, 0.29, 0.31 |
| unet-zero | UNet | zero a random share of every block's feed-forward neurons | 0.05, 0.1, 0.15, 0.2 |
| text-noise | both text encoders | Gaussian noise on every MLP neuron, sd = dose × the unit's sd | 0.25, 0.5, 0.75, 1.0 |
| unet-noise | UNet | the same on every feed-forward neuron | 0.75, 0.9, 1.0, 1.1 |
| text-spec | both text encoders | zero the top share of "specific-kind" neurons (below) | 0.1, 0.2, 0.3 |
| text-spec-random | both text encoders | the same number of random neurons in the same layers | 0.1, 0.2, 0.3 |

- Random units use one fixed seed per family, so a higher dose keeps every unit a lower dose hit
  (cumulative damage, as in progressive atrophy).
- Noise is the same for every picture (it does not depend on what else is in the batch); unit sds
  come from 16 reference doodle prompts of other things (cup, tree, car ...).
- **Specific-kind localizer** (targeted family): mean |activation| over the phrase's tokens for 23
  held-out subordinate vs. basic-level phrases ("a sports car" vs. "a car", "a tulip" vs. "a flower",
  ...; no chair, hat, bird or clock), Welch t, top share of all text-encoder neurons. The random
  control has the same count per layer and excludes the targeted units. Its main job is the
  random-unit control for the language site.
- **Clocks** use intact plus the four main families at three doses each: text-zero 0.25, 0.29,
  0.31; unet-zero 0.1, 0.15, 0.2; text-noise 0.5, 0.75, 1.0; unet-noise 0.9, 1.0, 1.1.

## Measures

**Severity (the common axis).** All pictures are ink-cropped and embedded with DINOv2-base CLS
(`plato.ink_crop`, as in plato.py). d_intact = cosine distance between a damaged picture and the
intact picture with the same seed. Families are compared at **matched severity**: each family's
mean d_intact per dose gives its severity curve; an outcome's change from intact is interpolated at
the 25th, 50th and 75th percentiles of the severity range both families reach, and averaged. CIs:
bootstrap over (kind, seed) pictures, a picture's doses kept together (4,000 resamples); a
bootstrap over kinds is the robustness check.

**Concept retention (what it is).** The Glimmer kind labeler (`scripts/plato_kinds_label.py` method:
multiple choice of the concept's kinds + "a plain, ordinary chair" + "can't tell, or not a chair",
letter logits, forward and reversed order averaged) on the ink-cropped picture: correct kind / plain
/ other kind / can't tell, among pictures whose intact twin was labeled correctly. Plus Glimmer's
P(yes) to "Is this a drawing of a chair? Answer yes or no." (yes/no logits).

**Drawing retention (how it is drawn).** Glimmer's P(yes) to "Is this a clean, simple line drawing,
with black lines on a plain white background and no color, shading or texture?" on the raw
(uncropped) picture. Pixel checks on the raw picture: colorfulness (Hasler & Süsstrunk), midtone
share (luma 60–200: shading, texture) and ink share.

**Prototype drift.** d_proto = distance to the plain prototype (centroid of the 16 intact plain
pictures); d_kind = distance to the kind's intact centroid, leaving out the picture's own seed.
Drift index = d_kind − d_proto (> 0: nearer the plain chair than its own kind). Also Δd_proto
alone (a picture that turns into the plain chair gets closer to it; generic damage moves it away),
τ (position on the line from kind centroid 0 to prototype 1) and drift toward the concept's other
kinds.

**Clocks.** Muse Spark (vision, minimal reasoning) answers a JSON rubric we wrote: is it a clock,
contour, how many hour numbers, in order, extra or garbled numbers, number of hands, where each
hand points, the time read. Features: contour, all 12 numbers in order, two hands, hands at the
asked time (each hand within one number), and **shows 10:10** (hands at 10 and 2). A 0–5 sum is
reported as a summary only. At least 40 clocks are checked by eye against Spark's reading.

## Hypotheses and what counts as support

**H1, double dissociation (primary).** At matched severity:
- (a) concept retention is **lower** under language damage than under drawing damage
  (text-zero − unet-zero < 0 in the change in "correct kind", CI below 0);
- (b) drawing retention is **higher** under language damage than under drawing damage
  (text-zero − unet-zero > 0 in the change in Glimmer's P(clean line drawing), CI above 0).
- Supported: both. Partly: one. Not supported: neither, or a reversal. The same two tests for
  text-noise vs. unet-noise are secondary. "Is this a chair?" and the pixel checks are secondary
  measures of the same two sides.

**H2, prototype drift (pre-specified, expected to be null after the pilot).** Under language
damage, named-kind chairs move toward the plain prototype: Δd_proto < 0, and text-zero − unet-zero
< 0 in Δd_proto at matched severity (CIs below 0). The drift index requested in the brief
(d_kind − d_proto) is reported with the same matched contrast (prediction > 0), but its absolute
value is not a test: the pilot showed it rises under any damage (see "Pilot").

**H3, kinds collapse to "plain".** Among errors on named-kind chairs, the plain share is higher
under text-zero than under unet-zero at matched severity; drawing damage is expected to produce
mostly "can't tell".

**H4, generality.** H1(a), H1(b) and H2 for hats and birds (secondary; CIs, no separate criterion).

**H5, targeted vs. random (secondary).** Zeroing the "specific-kind" neurons changes concept
retention and Δd_proto more than the same number of random neurons (paired by picture).

**H6, clocks (exploratory, directional).** Intact SDXL's 10:10 bias is measured first (share of
non-10:10 clocks whose hands read 10:10). Prediction: under language damage the asked time fails
first while the contour survives; under drawing damage the layout (contour, numbers in order) fails
first. "Fails first" = the feature whose rate falls below half its intact rate at the lowest dose.

**H7, Glimmer understanding.** A damaged Glimmer reads Muse Image's named-kind doodles
(`PlatosChair/core/ai/doodle_listed`, picture i shows kind i), for the 22 concepts whose kinds Glimmer
labeled reliably when intact (≥ 50% in the variety study; 288 pictures). Families: language-
localizer neurons (sentences > scrambled words), naming-localizer neurons and visual-localizer
neurons (lesion lab localizers `*_en`), each mean-ablated at the top 10%, 20% and 30%, each with a
random control of the same count per layer; and noise on layers 9–16 and 41–48 at sd × 1 and × 2.
Among intact-correct pictures, the semantic-dementia signature is a rise in **"plain" answers** (a
specific kind called just "a plain ..."): language-localizer damage − its random control > 0
(paired over pictures, CI above 0), and plain > can't tell under language damage. Visual-localizer
damage is expected to produce more "can't tell" than "plain". Secondary: the one-word name ("Name
the object in this picture with exactly one word"), coded specific (uses a word of the kind's
name), basic (just the concept's name) or other.

## Analysis rules

- Every CI is a 95% percentile bootstrap unless said otherwise. Many tests are run; H1 is the
  primary test, H2 and H7 are the pre-specified secondary tests, the rest are leads.
- No picture is dropped. Pictures that DINOv2 or Glimmer cannot read are kept and counted.
- A family's highest dose may destroy every picture (pure texture); it is still analysed, and the
  matched-severity comparison only uses the range both families reach.

## Pilot (before this plan)

Oct 27, 2026, server03. Two chair kinds (rocking chair, wheelchair) + the plain chair × 4 seeds,
intact and 4 doses per family; then the targeted family at 0.02–0.2 with its random control.
Grids: `PlatosChair/damage/figures/pilot_grid_{zero,noise,spec}.png`.

- **Dose range.** Zeroing 50% of either site destroys the pictures; text-zero changes little up to
  0.2 and jumps between 0.25 and 0.3 (DINOv2 change 0.17 → 0.68); unet-zero 0.1–0.25 spans 0.21–0.61;
  text-noise 0.5–1.0 spans 0.26–0.69; unet-noise 0.75–1.25 spans 0.14–0.90. The main doses above fill
  these ranges. The targeted "specific-kind" lesion changed less than its random control at every
  dose (0.2: 0.23 vs. 0.48).
- **What the pictures did.** Drawing damage kept the kind and degraded the drawing (rocking chairs
  stay rocking chairs, then dissolve into charcoal or black-and-white texture). Language damage
  changed what was drawn: a wheelchair became a bicycle, a shopping cart, cars, a man in a
  wheelchair; a rocking chair became a room, a red car, cartoon people; colour and shading came back
  (the style words are damaged too).
- **Prototype drift looked absent.** No family brought named kinds closer to the plain prototype
  (Δd_proto from −0.03 to +0.36). The drift index d_kind − d_proto rose under every family (up to
  +0.43), because a picture starts next to its own kind's centroid and far from the prototype, so
  any change raises d_kind faster. That is why H2 uses Δd_proto and matched contrasts, and why the
  primary test became the double dissociation (H1), suggested by the project lead after the pilot.
- **Pixel checks.** Zeroing UNet neurons gives black-and-white texture, which the midtone and colour
  measures miss (it has no gray and no colour); noise in the UNet gives gray charcoal (midtone up).
  So the primary drawing measure is Glimmer's judgement, and the pixel checks are secondary.

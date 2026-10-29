# Plain-language style for Plato's Chair

Everything a visitor can read on the Plato's Chair site follows these rules: sentences, labels, captions, headings, buttons, tooltips, alt text and share text. The site is public, and most readers are not scientists.

Roger's brief: *"Every point needs to be self-explanatory without knowing everything about everything in this project, and written in layman's terms for everything, since this is all public facing."*

## The rules

1. **Each page stands alone.** Someone who lands on a page with no other context should understand it. Don't write "as above" or "like 'any kind of chair'", or point at another experiment without saying what it found. Define every short name on the page.
2. **Say who and what.** Name a model or source in full on its first mention on each page (see *Who's who* below). Short names are fine after that.
3. **Keep jargon out of the main text.** The words in *Words to avoid* stay out of headings, ledes, findings and captions. If an idea is needed, explain it in the same sentence: "how different the drawings are from one another (we call this spread)".
4. **Numbers come with meaning.** Lead with what the number means: "People's chairs differed from one another nearly 3 times as much as the AI's." Keep the exact figure, but as a secondary detail: in brackets, a tooltip, a smaller line or a table.
5. **Say what happened, then what it means.** "We asked Meta's AI for 'any kind of chair' 16 times. It still drew the same chair. When we named specific kinds (a rocking chair, a throne), its chairs became more varied than people's."
6. **Use short, active, everyday words.** Aim for 25 words or fewer per sentence. Headings are complete thoughts, not slogans or labels: "Asking for 'any kind of chair' doesn't help", not "Ask for variety".
7. **Stay honest.** Keep failed and partial predictions, in plain words: "We expected X. That didn't happen." Keep the caveats too. Never change a number, a verdict or how strong a claim is. Technical detail can live in "Method and caveats" sections and in docs/, but no main point may depend on it.
8. **Translate, don't delete.** If a finding leaves the main text, it must still appear somewhere on the same page (a "details" box, a tooltip, the method notes).

### Quick checks before you commit

- Read the page top to bottom as a curious non-scientist who has seen nothing else on the site. Stop at every word you'd have to look up.
- Does each finding make sense without the sentence before it? Card texts, hub answers and gallery captions are often read alone.
- Is every number paired with words that say what it means?
- Are Plato's quotations untouched? They are verbatim (Jowett's translation) and must not change.

## Who's who: first mention on a page, then the short name

| Short name | First mention on a page |
|---|---|
| Muse Image | Meta's image AI, Muse Image |
| Muse Spark | Meta's chat AI, Muse Spark |
| Muse Glimmer | Meta's open AI model, Muse Glimmer (one anyone can download and look inside) |
| Muse Wonder | Meta's Muse Wonder, an AI that writes drawing code |
| DINOv2 | a Meta AI that compares pictures (DINOv2) |
| People / Quick, Draw! | people playing Google's Quick, Draw! game, 20 seconds per drawing |
| SDXL | Stable Diffusion XL, an open image AI from Stability AI. Never write "SDXL" alone in the main text. |
| Janus-Pro | Janus-Pro, an open AI from DeepSeek that both reads and draws pictures |
| Socrates (the chat) | an AI (Meta's Muse Spark) playing Socrates |

## Glossary: the plain phrasings we use

Use these wordings so every page says the same thing the same way.

| Technical term | What we write |
|---|---|
| spread | "how different the drawings are from one another". If the number is shown, add "(we call this spread)" once. 0 would mean 16 identical copies. |
| spread 0.13 vs 0.36 | "People's chairs differed from one another nearly 3 times as much as the AI's (spread 0.36 against 0.13)." |
| ratio / index (AI spread ÷ people's) | "about half as varied as people's (0.49)"; "63% less varied than people's"; "1.3 times as varied as people's". |
| "more alike", "flattened", "uniform" | "drawn more alike than people draw them"; "drawn the same way nearly every time". |
| textbook / slat-back / prototype chair | "the same plain wooden chair with a slatted back" (first time), then "the textbook chair". |
| Platonic / the Form | "Plato's Form: the one perfect, ideal version of a thing, which every real one copies". |
| default / usual prompt | "what it draws when you ask for nothing special"; "our plain request". |
| prompt | "request" or "the words we typed": "the same request every time: 'a quick simple doodle sketch of a chair'". |
| named kinds | "when Meta's chat AI listed 16 kinds of chair (a rocking chair, a beanbag, a throne…) and Muse Image drew one of each". |
| "any kind" prompt | "asking for 'a chair (any kind of chair)'". Always say what was asked. Never use "any kind" as a bare label. |
| persona / crowd | "we told it the age of the person drawing (20 to 80), a different age each time". |
| embedding | "a list of numbers that describes how the picture looks". |
| cosine distance / distance | "how different two pictures look to DINOv2 (0 = identical)". |
| centroid / prototype / average | "the average of its drawings"; "its typical chair (the average of its 16)". |
| layer | "stage": "the model reads a picture in 52 stages (layers), one after another". After that, "by stage 36 of 52". |
| collapse to one point | "it files them all in the same place: to the model they are one drawing". |
| CI / 95% interval | main text: "probably between 0.46 and 1.11" or "too close to call". The exact CI goes in brackets or tooltips. |
| rho / rank correlation | "a moderate link (−0.50 on a scale from −1 to 1)"; "they agree only weakly on which things...". |
| p, n | Don't use them. Say "out of 35 things", "16 drawings". |
| seed | "the same random starting point". |
| temperature | "the randomness setting". |
| checkpoint / training stage | "a saved snapshot from partway through training". |
| lesion / ablate / damage | first time: "we damaged the AI on purpose: we added random noise to its artificial neurons" or "we switched off some of its artificial neurons". After that, "damage". |
| text encoder / language part | "the part that reads the words (its text encoder)", then "the words part". |
| UNet / drawing part | "the part that paints the picture", then "the drawing part". |
| dose / level | "how much damage: step 1 of 5 (lightest) to step 5 of 5 (heaviest)". |
| recognizable | "drawings an AI could name correctly". |
| pre-registered | "we wrote down our predictions before we made any pictures". |
| null result | "We expected X. That didn't happen." |
| upper bound | "at most this much, probably less". |
| kappa | "how often two labelers agree, beyond what chance would give". |
| emblem | "the main symbol in a drawing (a heart for love, a reaper for death)". |
| originality (draw pad) | "how far your drawing is from the typical person's drawing of it". |
| "Plato's painter" | "Plato's painter, who copies how a thing looks instead of what it is". |

## Where technical detail may stay

- "Method and caveats" sections, "See the numbers" tables and "How it works" lists may use exact terms, once they have been defined in plain words.
- Tooltips may carry the exact figures (spread, ratio, likely range).
- docs/*.md are the full write-ups and may stay technical.
- Code comments and test names are not visible, so they don't need to change.

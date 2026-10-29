# Seven meanings: pre-registration

Written on Oct 28, 2026, and committed before the main run. No clip has been transcribed except the two pilot clips named here, Spark has seen only the two pilot transcripts, and the prosody reader has not been run on any test clip. Results will go in `docs/plato_phaedrus.md`. Any deviation from this plan will be listed there as a deviation.

**The question.** In the *Phaedrus* (276a), Socrates and Phaedrus agree that the written word is "properly no more than an image" of the living word. A model that learns only from text lives with the image. The sentence "I never said she stole my money" has seven meanings, one for each word a speaker can stress. Written down, the seven are one string.
1. **The shadow.** Does Meta's Voice Transcribe write the seven spoken versions down identically? Any difference in punctuation or casing would be writing keeping a trace of the stress (a leak).
2. **Text only.** Given the transcript, can Muse Spark tell which of the seven meanings the speaker intended? And given writing that keeps the stress (the stressed word in CAPITALS or *italics*)?
3. **The living word.** Can a plain prosody reader, using only pitch, loudness and duration per word, find the stressed word in the sound?

Code: `metalesionlab/plato_phaedrus.py` (the sentence, the meanings, the prompt, the reader) and `scripts/plato_phaedrus_*.py`. Data: `PlatosChair/phaedrus/`, outside the repository.

**What I had seen before writing this.**
- **macOS emphasis.** `say`'s emphasis command, `[[emph +]]`, is ignored on this Mac (macOS 26): for 19 English voices the audio with the command is bit-identical to the audio without it (Tessa and Rishi vary a little from run to run, with or without it). AVSpeechSynthesizer's SSML `<emphasis>` gave the same number of samples as plain text for Samantha. The voices do follow their pitch, volume and rate commands (`[[pbas]]`, `[[volm]]`, `[[rate]]`).
- **Kokoro's stress marks.** Raising a word's stress in Kokoro's phonemes (misaki's `[word](+2)`) barely changed pitch, loudness or duration (two voices tried). So Kokoro's focus is added with a vocoder (below).
- **Tool checks, not outcomes.**
  - The pitch tracker against WORLD's Harvest on 12 Kokoro clips: median difference 0.09 semitones, 1.6% of frames off by more than 2 semitones.
  - The word aligner on the 32 Kokoro test clips, each aligned to the other voices' templates: median boundary error 5 ms (90th percentile 12 ms). It hasn't been checked against true boundaries for the other families (they have none); spectrograms of 9 say and eSpeak clips with their boundaries looked right by eye.
  - The manipulation check (each stressed word against the same word in the same voice's neutral reading, aligned): Kokoro's stressed words are 2.5–6.3 semitones higher, 0–4 dB louder and 30% longer; say's 1.6–4.4 semitones higher, about 10 dB louder and 4–20% longer; eSpeak's emphasis makes the word 3–9 dB louder and 14–150% longer but not higher (−2.6 to +1.7 semitones).
  - Two speech-span and octave bugs found by these checks were fixed before this was written.
- **The pilot.** Two Kokoro clips (af_heart, "she" and "stole" stressed) were transcribed: both came back "I never said she stole my money." Spark guessed "I" and "never" (both wrong). Spark spent about $0.003 a call, more than the $0.001 we had assumed. The pilot stays in `pilot/` and is not analysed.

## Stimuli: 13 voices × 7 stressed versions, and a neutral reading each

Written down, the sentence is "I never said she stole my money." Each voice reads it neutrally and with each of the seven words stressed. `scripts/plato_phaedrus_stimuli.py` (this commit) makes them all; nothing is chosen by ear after the fact.

| Family | Voices | How the word is stressed | Ships? |
|---|---|---|---|
| Kokoro-82M (Apache-2.0) | af_heart, am_michael, bf_emma, bm_george | Added with the WORLD vocoder, the way English marks contrastive focus (Xu & Xu 2005): a pitch accent on the word (+5 semitones at its peak), 4 dB louder and 30% longer; after it, 2 semitones lower, with the pitch range halved and 2 dB softer. The neutral reading goes through the vocoder untouched. | Yes: these are the page's clips |
| macOS `say` | Samantha, Daniel, Karen, Moira, Tessa, Rishi | The voice's own commands: pitch +6, volume 0.55 → 1.0 and rate −60 on the word; pitch 2 lower after it | No: Apple's licence doesn't allow publishing them |
| eSpeak NG (GPL-3.0) | en-us, en-gb, en-us+f3 | Its own SSML `<emphasis level="strong">`: none of our numbers | No |

Five more Kokoro voices (af_bella, af_nicole, am_adam, bf_isabella, bm_lewis) read the sentence neutrally as extra alignment templates only. Every clip is 16 kHz mono 16-bit PCM. No recording of a person is used anywhere.

In two of the three families we set the stress ourselves, from pitch, loudness and duration, the very cues the reader measures. eSpeak's emphasis is the one family whose stress we didn't design.

## Measures

**1. The shadow.** Every clip (91 stressed, 13 neutral) is transcribed once by Voice Transcribe (`muse-voice-transcribe-1.0`, through `MetaAPI.transcribe`), with 0.5 s of silence added before and after and the language hint English.
- Per voice: are the 8 transcripts identical? Are they the same words once casing and punctuation are set aside (lower case, letters and apostrophes only)?
- Every difference in casing or punctuation between a voice's transcripts is reported as a leak, with the clips it came from.

**2. Text only** (Muse Spark, `muse-spark-1.3`, reasoning effort "minimal", one call per trial).
- The prompt is fixed (`plato_phaedrus.PROMPT`): "Someone said one sentence out loud and stressed one word to give it a particular meaning. Here is the sentence, written down: … Which meaning did the speaker intend? … Answer with the letter only."
- The seven options (`plato_phaedrus.MEANINGS`, this commit) say what the speaker means without naming the stressed word. Their order is shuffled for every trial from a fixed seed (20261028).
- **Transcript condition:** 91 trials, each stressed clip's transcript exactly as returned.
- **Control condition:** the sentence with the stressed word in CAPITALS ("I never said SHE stole my money.") and, separately, in markdown italics ("I never said *she* stole my money."). 7 words × 5 shuffles = 35 trials each.
- A reply is read as its first standalone letter A–G. A reply without one counts as wrong.

**3. The living word** (the prosody reader, `plato_phaedrus.read_stress`; numpy only, no learned weights).
- *Speech span:* frames within 40 dB of the loudest, and 10 dB above the quietest tenth or 25 dB under the loudest, whichever is lower.
- *Word timing:* dynamic time warping of the clip's MFCCs (12 coefficients, cepstral mean removed) onto each neutral Kokoro template. Each template's word boundaries are carried through the warping path, and the median across templates is taken. A Kokoro test clip is never aligned to its own voice's template.
- *Cues per word:* pitch peak (90th percentile of voiced F0, in semitones re the clip's median F0), loudness peak (90th percentile of frame level, re the clip's median speech level), and duration (the word's share of the speech span over its share in the templates, log ratio).
- *Prominence:* each cue is z-scored across the seven words (SD floored at a quarter of its typical spread: 2 semitones, 3 dB, 0.2). The templates' mean z-profile is subtracted from pitch and loudness, so the sentence's ordinary falling melody isn't read as stress. Prominence is pitch + loudness + duration, with equal weights. The most prominent word is the guess.
- These settings are fixed by this commit. Nothing is tuned on the test clips.

## Predictions and tests

Chance is 1/7 (14.3%). Accuracies get exact (Clopper–Pearson) 95% CIs. A second CI resamples whole voices (10,000 bootstrap draws), since a voice's clips share a voice and, often, a transcript. Tests against chance are one-sided exact binomial tests unless stated.

| | Prediction | Passes if |
|---|---|---|
| **H1 The shadow** | Writing drops the stress. | At least 12 of the 13 voices give 8 transcripts with the same words. Casing and punctuation leaks are reported however many there are. |
| **H2 Text only** | From transcripts, Spark is at chance. | The exact 95% CI of its accuracy over the 91 trials includes 1/7. It fails if the CI lies wholly above 1/7 (a leak, or a reading we didn't expect). |
| **H3 Writing that keeps the stress** | With CAPITALS or *italics*, Spark understands the stress. | Accuracy is at least 80% in each style (35 trials each), with the CI's lower bound above 1/7. |
| **H4 The living word** | The prosody reader finds the stressed word in the sound. | Over all 91 stressed clips, accuracy is at least 60% and p < 0.001. By family: at least 70% for Kokoro and for say, where we built the stress from the reader's own cues (a manipulation check more than a test); above chance (p < 0.05) for eSpeak. |

**Secondary, reported without a pass mark:**
- Each family on its own, and each stressed word.
- The 7 × 7 confusion tables for Spark and for the reader.
- The reader with Kokoro's true word boundaries instead of the aligner's.
- The reader without the neutral profile subtracted.
- Each cue alone (pitch, loudness, duration).
- Spark's answers to the 7 stressed versions of each voice: when their transcripts are identical, any spread in its answers comes only from the shuffled order of the options.

**Optional: an audio model.** Qwen2-Audio-7B-Instruct (Apache-2.0), on the Axon GPU servers, would hear each clip and answer the same multiple-choice question. Axon isn't reachable today (no VPN), so this isn't part of the plan. If it is run later, it will be reported as a deviation.

## Money

- The task's hard cap is $3, summed in `spend.jsonl`. No paid call is made once the shared ledger reaches $70. It stood at $63.89 after the pilot.
- Estimate: transcription, 104 clips of about 3.5 s, about $0.02; Spark, 161 trials at about $0.003, about $0.50.
- The web page's "Try it yourself" costs about $0.003 a try (one transcription, one Spark call). It runs under the site's spend guard.

## What this can't show

- The voices are synthetic. For two families we set the stress ourselves. People stress words in more ways, and less cleanly.
- One sentence, seven meanings, our wording of them. Another sentence could be harder or easier.
- The reader's success on clips whose stress we built from its own cues shows only that the cue survives in the audio and a simple measure can find it. It doesn't show that the reader hears stress as people do. eSpeak's clips, and visitors' own voices on the page, are the fairer tests.
- Spark at chance from a transcript says nothing about what Spark knows. The transcript holds nothing to know.

## Addendum, Oct 28, 2026, after the run: the Kokoro clips remade (v2)

Not part of the plan above, and not pre-registered. Listening with his eyes closed, one of us couldn't tell which word the Kokoro clips stressed. So the four Kokoro voices' 32 clips were remade with much stronger stress, chosen in a blind listening test, then transcribed and read again. Nothing else changed: the prompt, the option orders, the reader, its templates and the statistics are the same. The pre-registered verdicts stay the first run's. The v2 numbers are reported beside them in `docs/plato_phaedrus.md` (Deviation 6, and "The Kokoro clips remade (v2)").

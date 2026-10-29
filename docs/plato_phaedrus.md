# Seven meanings

In the *Phaedrus* (276a), Phaedrus calls the written word "properly no more than an image" of "the living word of knowledge which has a soul", and Socrates agrees. A model that learns only from text lives with the image. "I never said she stole my money" means seven things, one for each word a speaker can stress. Written down, the seven are one string.

We spoke the sentence with each word stressed, in 13 synthetic voices. Meta's Voice Transcribe wrote each clip down. Muse Spark guessed the intended meaning from the transcript, and from writing that keeps the stress (CAPITALS, *italics*). A plain prosody reader guessed from the sound. Pre-registered in `docs/plato_phaedrus_plan.md` (commit `120fb20`). The page is `/plato/phaedrus`.

A listener couldn't hear the stress in the four Kokoro voices, so after the run we remade their clips with much stronger stress, chosen in a blind listening test, and measured them again. This is v2, a revision that wasn't pre-registered. It is reported in "The Kokoro clips remade (v2)" and listed as Deviation 6. The page plays the v2 clips and shows the v2 numbers; its macOS and eSpeak numbers are from the first run. Everything else below is the first run, v1, as pre-registered.

## Short answer

- **Writing drops the stress.** Voice Transcribe wrote 81 of the 104 clips as exactly the sentence's words. The rest were slips: a doubled word ("I never never said…", "II never said…"), a lower-case "i", a missing full stop.
  - The slips came with every stressed word and with the neutral readings too. Transcribed a second time, the same clips slipped in different places, so they're the transcriber's noise, not the stress.
  - No transcript ever wrote a stressed word in capitals.
  - **Pre-registered H1 failed as written.** We predicted that at least 12 of 13 voices would give 8 transcripts with the same words. Only 1 did, because of the stray words.
- **From the transcript, Muse Spark is at chance.** It picked the intended meaning **9 times in 91 (10%**, exact 95% CI 5–18%; chance is 14%). **H2 passed.**
  - It answered "never" (59 times) or "I" (21) whatever was stressed.
- **Writing that keeps the stress, Spark gets.** With the stressed word in *italics*: **35 of 35** (CI 90–100%). In CAPITALS: **30 of 35** (CI 70–95%). **H3 passed.**
  - All 5 CAPITALS misses were "I". "I" is always a capital, so CAPITALS can't mark it.
- **The stress is still in the sound.** The prosody reader (pitch, loudness and length per word, no AI) found the stressed word in **80 of 91** clips (**88%**, CI 79–94%, p < 10⁻⁵⁰). **H4 passed.**
  - The voice families: Kokoro **26 of 28**, macOS **37 of 42**, eSpeak **17 of 21**.
  - In two of the three families we built the stress from those same cues, so there the result mostly shows that the cue survives in the audio. eSpeak, whose emphasis we didn't design, is the fairer test: 81% (CI 58–95%).
  - Hardest word: "never" (5 of 13), often heard as "I".
  - As pre-registered the reader scored 79 of 91. A pitch-tracker bug was fixed after the main run (Deviations).
- **v2: the Kokoro clips remade with stronger stress** (after the run; not pre-registered).
  - Against the rest of the sentence, the stressed word is now **+13.5 semitones, +12.6 dB and 1.62 times as long** (medians). In v1 it was +5.1 semitones, +4.0 dB and ×1.22.
  - The reader finds it in **28 of 28** Kokoro clips (v1: 26). Pooled with the first run's macOS and eSpeak clips, that is **82 of 91** (90%).
  - From the new transcripts, Spark is still at chance: **5 of 28** (v1: 4); pooled, **10 of 91** (11%, CI 5–19%).

## Stimuli

| Family | Voices | How the word was stressed | Clips |
|---|---|---|---|
| Kokoro-82M (Apache-2.0) | af_heart, am_michael, bf_emma, bm_george | v1: added with the WORLD vocoder, as English marks contrastive focus (Xu & Xu 2005). The word gets a pitch accent of +5 semitones at its peak, is 4 dB louder and 30% longer. The words after it are 2 semitones lower, with half the pitch range, and 2 dB softer. v2 (after the run): much stronger, edited inside Kokoro; see "The Kokoro clips remade (v2)". | 32; the page ships v2 |
| macOS `say` | Samantha, Daniel, Karen, Moira, Tessa, Rishi | The voices' pitch, volume and rate commands: `[[pbas +6]]`, volume 0.55 → 1.0, `[[rate -60]]` on the word, pitch 2 lower after it | 48, not shipped (Apple's licence) |
| eSpeak NG | en-us, en-gb, en-us+f3 | Its own SSML `<emphasis level="strong">` | 24, not shipped |

Each voice read the sentence neutrally and with each word stressed. No recording of a person was used.

**macOS emphasis does nothing.** On this Mac (macOS 26), `say`'s `[[emph +]]` command left the audio bit-identical for 19 English voices. AVSpeechSynthesizer's SSML `<emphasis>` changed nothing either for Samantha (same number of samples). The pitch, volume and rate commands work, so the stress was built from them.

**Kokoro's stress marks barely move the voice.** In a pilot with two voices, misaki's `[word](+2)` changed pitch, loudness and length very little. So Kokoro's focus was added with the vocoder; the neutral clip goes through the same vocoder untouched.

**Was the stress audible and measurable?** Each stressed word was measured against the same word in the same voice's neutral reading:

| Family | Pitch | Loudness | Length |
|---|---|---|---|
| Kokoro | +2.5 to +5.9 semitones (one word, am_michael's "she", +0.0) | 0 to +4 dB | +30% |
| macOS | +3.3 to +4.4 semitones | about +10 dB | 0 to +20% |
| eSpeak | −2.6 to +1.6 semitones | +3 to +9 dB | +14 to +150% |

(Measured with the final pitch tracker; the plan's figures came from the version before the fix in Deviations.)

So eSpeak's emphasis is loudness and length, not pitch. For the first run nobody listened to the clips: the analysis ran with no one at the speakers. Every clip was checked by these measurements and by its pitch track and spectrogram. When someone did listen, v1's Kokoro stress was too weak to hear, which led to v2 (below).

## The Kokoro clips remade (v2)

**Why.** Listening with his eyes closed, one of us couldn't tell which word the Kokoro clips stressed. The prosody reader had found it in 26 of 28, but a person couldn't hear it. So after the run we remade the four Kokoro voices' 32 clips with stronger stress and measured them again. This is a revision after listener feedback, **not pre-registered** (Deviation 6). Everything above is the first run (v1), as pre-registered. The macOS and eSpeak clips, the CAPITALS and italics control and the reader's templates are unchanged.

**Why v1 was hard to hear.** It was small for contrastive focus: +5 semitones, +4 dB and 30% longer. It was also partly misplaced:
- v1's edits were placed with Kokoro's own word timestamps. Those start each word three duration frames early, so they run 75–110 ms ahead of the sound. Kokoro's decoder follows its frame alignment to within 10 ms (the pitch it renders against the pitch track it's given, four voices).
- So part of v1's lengthening and loudness fell on the end of the word before.
- Measured on the frame-aligned spans, the v1 word was the loudest in the sentence in only 13 of 28 clips, and the highest in 17. Measured on the timestamps it was placed with, it was the loudest and the highest in 18.
- v2 places every edit on the frame alignment.

**What we tried, and how we chose.** One listener, blind, scored in aggregate. A page played clips at random, the listener picked the stressed word, and the page then showed the answer and the method. Two voices (af_heart, bm_george).

| | Method | Round 1 | Round 2 (with notes) |
|---|---|---|---|
| A | v1 | 5 / 7 | 3 / 3 |
| B | Strong WORLD: +12 semitone rise-fall accent, +9 dB, vowels ×2, 150 ms pause, words after it lower, flatter, softer and faster | 8 / 8 | 3 / 3 |
| C | Kokoro's own stress marks only: primary stress on the word, every other mark removed | 4 / 7 | 0 / 3 |
| D | B's targets, but edited inside Kokoro: its predicted phoneme lengths and pitch track changed before it renders the voice | 11 / 12 | 3 / 3 |
| E | C's marks plus a gentler D | 9 / 9 | 3 / 3 |

- **C is too weak.** Kokoro's stress marks moved the word by +0.9 semitones and −0.3 dB against the rest of the sentence (medians). CAPITALS only add the same mark, and "MY" in capitals is read as the letters M-Y.
- **B, D and E were clear, but had a hiccup.** The listener heard "a weird hiccup right at the start of the emphasised word" in B, D and E, on every word but the first. It was the 150 ms pause, cut in as silence: entering the word, the level rose 20–23 dB per 5 ms more than the neutral reading's did at the same spot (medians).
- **Smooth versions (B2, D2, E2).**
  - No silence is cut in.
  - The gain rises over 90 ms (a raised cosine) ending at the word's onset, and falls over 80 ms after the word.
  - The pitch starts gliding up 120 ms before the word, in an L+H* shape, and every pitch edit is smoothed over 40 ms.
  - The stressed vowel takes the lengthening; the onset consonant is stretched only ×1.1.
  - "she" and "stole" are a little longer.
  - In D2 and E2, the only gap is Kokoro's own: the space before the word is held 50 ms longer. Kokoro renders that as a slower transition, and as silence only where the neutral reading already has a closure.
- **Round 3:** the smooth versions got 9 of 9 right (3 each), with no complaint about the onsets. We ship **D2**: Kokoro renders the stressed voice itself, so there is no vocoder resynthesis.

**v2, as shipped (D2).**
- **Inside Kokoro, before it renders:**
  - the word's vowels ×2.2 (with a further ×1.25 for "she" and ×1.3 for "stole"), its onset consonant ×1.1 and other consonants ×1.35;
  - the space before the word held 50 ms longer;
  - a rise-fall pitch accent peaking 12 semitones up on the stressed vowel, starting 120 ms before the word and ending 2 semitones under the old track;
  - Kokoro's energy track +1 on the word;
  - after the word: 3 semitones lower, a third of the pitch range, 10% faster;
  - before it: pitch range at 70%.
- **Then on the waveform:** the word 9 dB louder and everything after it 3.5 dB softer, with the ramps above. Every clip is peak-normalised to −1 dBFS.
- **The neutral reading** is Kokoro's plain rendering.
- Made by `scripts/plato_phaedrus_stimuli.py --kokoro-version v2`. Each clip's seed and its word spans are in its `meta.json`.

**Manipulation check (v2).** Each stressed word is measured against the same word in its voice's neutral reading, with the reader's own pitch tracker and level meter, on the frame-aligned spans. "Against the rest" takes away the median change of the other six words (for length, divides by it). Because every clip is peak-normalised, the rest of a stressed sentence ends up quieter than the neutral one, so the comparison against the rest is the one a listener makes. Medians over the four voices:

| Stressed word | Pitch, against the rest | Loudness, against the rest | Length, against the rest | Against its own neutral reading | Longer gap before it |
|---|---|---|---|---|---|
| I | +15.2 st | +13.3 dB | ×1.48 | +11.1 st, −0.8 dB, ×1.40 | (first word) |
| never | +13.9 st | +13.4 dB | ×1.66 | +10.2 st, +2.2 dB, ×1.58 | 50 ms |
| said | +12.6 st | +14.0 dB | ×1.37 | +9.3 st, +3.1 dB, ×1.37 | 50 ms |
| she | +13.4 st | +12.8 dB | ×2.00 | +11.1 st, +8.8 dB, ×2.00 | 50 ms |
| stole | +12.0 st | +10.3 dB | ×1.56 | +10.5 st, +2.3 dB, ×1.56 | 50 ms |
| my | +14.3 st | +11.0 dB | ×1.45 | +13.1 st, +5.8 dB, ×1.45 | 50 ms |
| money | +10.8 st | +9.4 dB | ×1.89 | +10.6 st, +3.6 dB, ×1.89 | 50 ms |
| **All 28** | **+13.5 st** (+8.6 to +16.6) | **+12.6 dB** (+8.1 to +18.6) | **×1.62** (1.25 to 2.00) | | |

- **The rule of thumb holds.** In all 28 clips, the stressed word is the highest, the loudest and the most lengthened word of its sentence.
- **v1, measured the same way:** +5.1 semitones, +4.0 dB and ×1.22 against the rest.

**Onset check.** Abrupt entries into the word were measured as two numbers: the largest spectral flux, and the largest rise of the frame level. Both are taken from 60 ms before the onset to 40 ms after it, and set against the neutral reading at the same spot. Words 2–7, so 24 clips for v2:

| | Spectral flux, ratio to neutral | Extra level rise, dB per 5 ms |
|---|---|---|
| D in round 2 (pause cut in; 2 voices) | 1.43 (max 4.82) | +20.6 (max +35.8) |
| B in round 2 | 1.59 (max 5.06) | +23.1 (max +32.8) |
| E in round 2 | 1.44 (max 5.23) | +19.8 (max +30.9) |
| **v2 as shipped (D2; 4 voices)** | **1.20** (max 1.72) | **+0.4** (max +9.3) |

The remaining maximum is af_heart's "stole". It enters on an /s/ after a closure, and that onset already rises 13 dB per 5 ms in the neutral reading.

**Results with v2.** The same prompt, and the same option order for every clip as in v1, so only the transcript differs. Spark's calls are in `PlatosChair/phaedrus/v2/` with their ledger entries.

| | v1 (pre-registered) | v2 |
|---|---|---|
| Kokoro transcripts with exactly the sentence's words | 22 of 32 | 26 of 32 |
| Spark from the Kokoro transcripts | 4 of 28 (CI 4–33%) | 5 of 28 (CI 6–37%; p = 0.37 against chance) |
| The reader on the Kokoro clips | 26 of 28 (CI 77–99%) | **28 of 28** (CI 88–100%) |
| The reader, Kokoro, with the true word boundaries | 24 of 28 | 28 of 28 |
| The reader, Kokoro, one cue at a time (pitch, loudness, length) | 24, 21, 21 of 28 | 27, 23, 28 of 28 |
| Spark from all 91 transcripts (macOS and eSpeak from the first run) | 9 of 91 (10%, CI 5–18%) | 10 of 91 (11%, CI 5–19%) |
| The reader, all 91 clips (macOS and eSpeak from the first run) | 80 of 91 (88%, CI 79–94%) | **82 of 91** (90%, CI 82–95%) |

- **Writing still drops the stress.** Spark answered "never" 20 times and "I" 4 times. Four of its five right answers were the "never"-stressed clips. One reply was "Cannot determine without knowing which word was stressed." (counted wrong, as the plan says).
- **One possible trace in the writing.** For bm_george with "said" stressed, Voice Transcribe wrote "I never said, she stole my money.": a comma just after the stressed word, where Kokoro had held the gap. It's one transcript in 28, and Spark still picked "never" for it.
- **The other slips are the transcriber's usual noise.** Doubled words ("I never never said…", "i neverI never said…") came with stressed and neutral clips alike, as in v1.
- **Pooled, the pre-registered tests come out the same.** H2 passes (at chance) and H4 passes (82 of 91, by voice CI 85–96%).
- **H1 still fails.** Now 0 of 13 voices give 8 transcripts with the same words; in v1, 1 did. af_heart's neutral clip came back "i neverI never said…".

The reader's 28 of 28 shows that the stress is now unmistakable in the sound. We designed it from the reader's own cues, so this is a manipulation check more than a test. eSpeak's own emphasis, at 17 of 21, is still the fairer test.

## Method

- **Transcription.** Each clip was sent once to `muse-voice-transcribe-1.0`, with 0.5 s of silence added before and after and the language hint English.
- **Text only.** Muse Spark (`muse-spark-1.3`, reasoning effort "minimal") got a fixed prompt (`plato_phaedrus.PROMPT`): "Someone said one sentence out loud and stressed one word to give it a particular meaning. Here is the sentence, written down: … Which meaning did the speaker intend?"
  - The seven options, in an order shuffled for every trial from a fixed seed, say what the speaker means. None says which word was stressed.
  - It saw each stressed clip's transcript exactly as returned (91 trials).
  - The control: the sentence with the stressed word in CAPITALS or markdown *italics*, each word 5 times (35 trials each).
- **The prosody reader** (`plato_phaedrus.read_stress`, numpy only).
  - *Finding the words:* DTW of the clip's MFCCs onto neutral Kokoro readings whose word times are known (9 voices). A Kokoro test clip is never aligned to its own voice. On Kokoro clips the median boundary error is 5 ms.
  - *Cues per word:* pitch peak in semitones, loudness peak in dB, and duration share, each z-scored across the seven words. The neutral readings' profile is subtracted, so the sentence's falling melody isn't read as stress.
  - *Guess:* the word with the highest sum. The settings were fixed before the main run.
- **Statistics.** Exact (Clopper–Pearson) 95% CIs; one-sided exact binomial tests against 1/7; a second CI that resamples whole voices (10,000 draws).

## Results

### H1. The shadow: failed as written

| | First pass | Second pass (exploratory) |
|---|---|---|
| Transcripts exactly "I never said she stole my money." | 66 of 104 | – |
| Exactly its words (casing and punctuation set aside) | 81 of 104 | 82 of 104 |
| Identical to the first pass | – | 37 of 104 |
| Same words as the first pass | – | 71 of 104 |
| A word added or doubled | 23 | 22 (7 on the same clips as the first pass) |
| A lower-case "i" at the start | 18 | 33 (7 on the same clips) |
| A stressed word in capitals | 0 | 0 |

- **Voices.** Only af_heart's 8 transcripts had the same words. Every other voice had at least one stray word, so H1 (at least 12 of 13 voices) failed.
- **Where the slips came.** They came with neutral readings (2 of 13 in the first pass) as well as with each stressed word (1 to 6 of 13).
- **Odd punctuation.** A trailing comma (bf_emma, "money" stressed), "money.." (Karen, "said"), "money.!" (Moira, neutral), and "money dot" (eSpeak en-us+f3, "money").
- **A pattern that didn't replicate.** In the first pass, a lower-case "i" never appeared on neutral or "I"-stressed clips (0 of 26) and appeared on 18 of the other 78 (Fisher p = 0.005, exploratory). The second pass found it on neutral and "I"-stressed clips too: 6 of 26 against 27 of 78 (p = 0.34). We read it as noise.

### H2. Text only: passed

| | Right | 95% CI (exact) | CI by voice | p (above chance) |
|---|---|---|---|---|
| All transcripts | 9 / 91 (10%) | 5–18% | 7–13% | 0.92 |
| Kokoro | 4 / 28 | | | |
| macOS | 3 / 42 | | | |
| eSpeak | 2 / 21 | | | |

- **What Spark picked.** "never" 59 times, "I" 21, "she" 7, "said" 3, "money" 1.
- **Same words, different answers.** When a voice's transcripts were identical, Spark's answers still varied with the shuffled order of the options.
- **The stray words didn't help.** Transcripts with exactly the sentence's words: 6 of 70 right. With a stray word: 3 of 21. A doubled "never" seems to pull Spark toward "never", which was right only when "never" happened to be the stressed word.

### H3. Writing that keeps the stress: passed

| | Right | 95% CI | Misses |
|---|---|---|---|
| CAPITALS | 30 / 35 (86%) | 70–95% | All 5 on "I": "never" 3, "she" 2 |
| *italics* | 35 / 35 (100%) | 90–100% | none |

"I never said she stole my money." with "I" in capitals is the plain sentence. Writing can't show that "I" was stressed, and Spark guessed.

### H4. The living word: passed

| | Right | 95% CI | p |
|---|---|---|---|
| All 91 clips | 80 (88%) | 79–94% (by voice 82–93%) | 2 × 10⁻⁵⁵ |
| Kokoro | 26 / 28 (93%) | 77–99% | 3 × 10⁻²⁰ |
| macOS | 37 / 42 (88%) | 74–96% | 2 × 10⁻²⁶ |
| eSpeak | 17 / 21 (81%) | 58–95% | 1 × 10⁻¹¹ |

**By stressed word:** I 13/13, never 5/13, said 12/13, she 13/13, stole 11/13, my 13/13, money 13/13. Stressed "never" was heard as "I" 4 times. The sentence's first two words share the high start of the melody, which the neutral profile only partly removes.

**Secondary analyses:**
- **Kokoro with its true word boundaries:** 24 of 28. That is no better than with the aligner's (26 of 28), so the aligner isn't what limits the reader.
- **Without the neutral profile subtracted:** 81 of 91.
- **Each cue alone:**

| Cue | All 91 | Kokoro | macOS | eSpeak |
|---|---|---|---|---|
| Pitch | 59 | 24 / 28 | 32 / 42 | 3 / 21 |
| Loudness | 79 | 21 / 28 | 39 / 42 | 19 / 21 |
| Duration | 50 | 21 / 28 | 12 / 42 | 17 / 21 |

  eSpeak's emphasis carries no pitch, and the reader finds it through loudness and length. Combining the cues beats any single one.

**Optional audio model.** Qwen2-Audio-7B-Instruct on the Axon servers wasn't run: Axon was unreachable all day (no VPN). The plan made it optional.

## The page

- **First screen.** The seven Kokoro recordings (v2), with four voices to choose from. Beside each recording is what Voice Transcribe wrote for it, exactly as returned, with stray words marked.
- **Charts.** After a clip is played, Spark's guess and the reader's guess for it appear. Below: the four accuracies with their CIs, the two 7 × 7 confusion tables, and the reader's pitch and loudness contour for the last clip played.
- **v2 numbers, labelled.** The accuracies and tables use the v2 Kokoro clips together with the first run's macOS and eSpeak clips. The caption names each family's source; the text gives the first run's numbers and says the verdicts are the first run's.
- **Try it with your voice.** The browser records the visitor, resamples to a 16 kHz WAV and sends it twice:
  - to `/api/phaedrus/listen`, the reader. It runs on our server, costs nothing and is listed as free in the spend guard;
  - to `/api/phaedrus/read`, Voice Transcribe and then Spark, with the experiment's prompt. It is paid, about $0.003 a try, and goes through the guard's daily cap and per-visitor limits, and `limits.py`'s.
- **Privacy.** The recording is read in memory and never written or logged. The visitor's answer to "which word did you stress?" stays in the browser.
- **When things fail.** At the daily cap, or without an API key, the transcript and Spark's guess say they're paused. The reader still answers.
- **Checked end to end.** Chromium recorded a generated macOS clip ("she" stressed) through a fake microphone. Voice Transcribe wrote "I never said she stole my money.", Spark guessed "never", and the reader said "she".

## Deviations from the plan

1. **Pitch tracker fix.** After the main run, a unit test found that the pitch tracker could report a steady 260 Hz tone an octave low: with the window divided out, the peak at twice the period could edge out the true one. It now takes the shortest-lag peak within 10% of the best. The fix changed one guess (macOS Daniel, "money"): **79 of 91 as pre-registered, 80 after.** Every number above uses the fixed reader. Against WORLD's Harvest the tracker's median error stayed at 0.10 semitones.
2. **Second transcription pass.** Every clip was transcribed a second time (exploratory), to see whether the stray words recur. They mostly didn't.
3. **The lower-case "i" test** is exploratory, and didn't replicate.
4. **A hung call.** One Spark call hung for ten minutes. The run was stopped, a 90 s timeout added and the run resumed. The hung call left no answer and no ledger entry.
5. **Capitals check.** The route's "a stressed word in capitals" check ignores "II", a doubled "I", which the first version counted. This changes no result above: no transcript had a stressed word in capitals.
6. **The Kokoro clips remade (v2), after listener feedback.** One listener couldn't hear the first run's Kokoro stress, so the 32 Kokoro clips were remade, transcribed again (32 calls) and read again by Spark (28 calls, transcripts only; the CAPITALS and italics control doesn't depend on the clips) and by the reader. Nothing about the method was chosen in advance. Five candidates and three smooth versions were compared by ear in a blind test, and the strengths were set by measurement and by that listener. The reader's templates, prompt, option orders and statistics are unchanged. The pre-registered verdicts are the first run's; the v2 numbers are reported beside them, not instead of them. See "The Kokoro clips remade (v2)".

## Limitations

- **Synthetic voices.** In two families we set the stress ourselves, from pitch, loudness and length, the cues the reader measures. People stress words in more ways, and less cleanly. eSpeak's emphasis and visitors' own voices on the page are fairer tests.
- **One sentence, seven meanings, our wording of them.** Another sentence could be harder or easier.
- **Spark is not to blame.** Spark at chance from a transcript says nothing about what Spark knows: the transcript holds nothing to know. The CAPITALS and italics controls show that it reads stress well when writing keeps it.
- **The reader is crude.** It assumes the sentence and seven words, aligns to Kokoro voices, and has no notion of a pitch accent beyond "higher, louder, longer". On visitors' voices it will be less accurate than here, and we haven't measured how much.

## Spend

- **v2 (the remade Kokoro clips): $0.11.** Voice Transcribe $0.006 for 32 clips; Spark $0.10 for 28 calls. The ledger went from $66.95 to $67.05. That task's cap was $1.50.
- **The first run: about $0.41.**
  - Muse Spark, 166 calls, about $0.38 (about $0.0023 a call: even at "minimal" effort Spark spent about 540 reasoning tokens a call). That is 161 trials, 2 pilot calls and 3 live checks of the page.
  - Voice Transcribe, about $0.04: 104 clips twice, the pilot's 2 and 3 live checks.
- **The shared ledger** (`runs/costs.jsonl`) stood at $64.29 at the end of this task. The task's own cap was $3.

## Files

- `metalesionlab/plato_phaedrus.py`: the sentence, the meanings, the prompt, transcript checks, the prosody reader and aligner, statistics.
- `scripts/plato_phaedrus_stimuli.py`, `plato_phaedrus_run.py` and `plato_phaedrus_analyze.py`: stimuli, paid calls and analysis.
- `public_data/plato_phaedrus.json`: every transcript, Spark answer and reader guess, and the tests.
- `public_data/plato_phaedrus_audio/`: the 32 Kokoro clips (Apache-2.0).
- `metalesionlab/web/plato_phaedrus_routes.py`, `pages/plato_phaedrus.html`, `static/js/plato_phaedrus.js` and `static/css/plato_phaedrus.css`: the page and the voice test.
- `metalesionlab/web/data/plato_phaedrus.json` and `phaedrus_templates.json`: the page's data and the reader's templates.
- Data outside the repository: `PlatosChair/phaedrus/` (stimuli, transcripts, Spark answers, spend), with v2 in `PlatosChair/phaedrus/v2/`.
- `public_data/plato_phaedrus.json` has the v2 results at the top level, the first run's under `v1`, both focus settings under `focus`, and v2's manipulation and onset checks under `manipulation_v2`.

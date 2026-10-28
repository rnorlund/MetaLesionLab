# Seven meanings

In the *Phaedrus* (276a), Phaedrus calls the written word "properly no more than an image" of "the living word of knowledge which has a soul", and Socrates agrees. A model that learns only from text lives with the image. "I never said she stole my money" means seven things, one for each word a speaker can stress. Written down, the seven are one string.

We spoke the sentence with each word stressed, in 13 synthetic voices. Meta's Voice Transcribe wrote each clip down. Muse Spark guessed the intended meaning from the transcript, and from writing that keeps the stress (CAPITALS, *italics*). A plain prosody reader guessed from the sound. Pre-registered in `docs/plato_phaedrus_plan.md` (commit `120fb20`). The page is `/plato/phaedrus`.

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

## Stimuli

| Family | Voices | How the word was stressed | Clips |
|---|---|---|---|
| Kokoro-82M (Apache-2.0) | af_heart, am_michael, bf_emma, bm_george | Added with the WORLD vocoder, as English marks contrastive focus (Xu & Xu 2005). The word gets a pitch accent of +5 semitones at its peak, is 4 dB louder and 30% longer. The words after it are 2 semitones lower, with half the pitch range, and 2 dB softer. | 32, shipped with the page |
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

So eSpeak's emphasis is loudness and length, not pitch. We couldn't listen to the clips ourselves (the analysis ran without anyone at the speakers). Every clip was checked by these measurements and by its pitch track and spectrogram.

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

- **First screen.** The seven Kokoro recordings, with four voices to choose from. Beside each recording is what Voice Transcribe wrote for it, exactly as returned, with stray words marked.
- **Charts.** After a clip is played, Spark's guess and the reader's guess for it appear. Below: the four accuracies with their CIs, the two 7 × 7 confusion tables, and the reader's pitch and loudness contour for the last clip played.
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

## Limitations

- **Synthetic voices.** In two families we set the stress ourselves, from pitch, loudness and length, the cues the reader measures. People stress words in more ways, and less cleanly. eSpeak's emphasis and visitors' own voices on the page are fairer tests.
- **One sentence, seven meanings, our wording of them.** Another sentence could be harder or easier.
- **Spark is not to blame.** Spark at chance from a transcript says nothing about what Spark knows: the transcript holds nothing to know. The CAPITALS and italics controls show that it reads stress well when writing keeps it.
- **The reader is crude.** It assumes the sentence and seven words, aligns to Kokoro voices, and has no notion of a pitch accent beyond "higher, louder, longer". On visitors' voices it will be less accurate than here, and we haven't measured how much.

## Spend

- **This task: about $0.41.**
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
- Data outside the repository: `PlatosChair/phaedrus/` (stimuli, transcripts, Spark answers, spend).

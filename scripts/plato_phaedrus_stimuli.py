"""Seven meanings, step 1: speak "I never said she stole my money." eight ways (neutral, and each word stressed)
in several synthetic voices. No Meta API calls.

Three families of voice, each stressing the word its own way:

- kokoro: Kokoro-82M (hexgrad, Apache-2.0), an open neural voice. Kokoro has no emphasis control (its stress
  marks barely moved pitch in a pilot), so the stress is added afterwards with the WORLD vocoder (pyworld, MIT),
  the way English marks contrastive focus (Xu & Xu 2005): a pitch accent on the word (+5 semitones at its peak),
  4 dB louder and 30% longer, and the words after it lower (-2 semitones) and flatter (pitch range halved) and
  2 dB softer. The neutral reading goes through the same vocoder untouched. Kokoro reports word times, so these
  clips have exact word boundaries; they are the templates of the word aligner and the clips the web page plays
  (openly licensed, so they may ship).
  v2 (added after the run, when a listener couldn't hear v1's stress; not pre-registered): the four tested voices
  again, with focus as large as speakers make it, made inside Kokoro (see "kokoro v2" below). Written to DIR/v2;
  v1's clips stay where they were, and v1's neutral readings stay the aligner's templates.
- say: macOS voices. Their emphasis command, [[emph +]], is ignored on this Mac (the audio is bit-identical with
  and without it), so the word is marked with the voices' pitch, volume and rate commands instead: [[pbas +6]],
  [[volm]] from 0.55 to 1.0 and [[rate -60]] on the word, [[pbas -2]] after it. Apple's licence doesn't allow
  publishing these voices' output, so these clips never leave this computer.
- espeak: eSpeak NG (GPL-3.0) with SSML <emphasis level="strong">: the synthesizer's own emphasis, set by none
  of our numbers.

Usage (Kokoro needs kokoro, pyworld and soundfile, which the web app doesn't; use a separate environment):
  python scripts/plato_phaedrus_stimuli.py --family kokoro say espeak [--out DIR]
  python scripts/plato_phaedrus_stimuli.py --family kokoro --kokoro-version v2 [--candidate D]

Writes DIR/stimuli/<family>/<voice>/{neutral,0_i,1_never,...}.wav (16 kHz mono 16-bit, what Voice Transcribe
takes) and DIR/stimuli/<family>/<voice>/meta.json; Kokoro also writes 24 kHz MP3s for the page to
DIR/ship/<voice>/. DIR is $PLATO_PHAEDRUS_DIR (outside the repository).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato_phaedrus import PHAEDRUS_DIR, SENTENCE, WORDS  # noqa: E402

FFMPEG = shutil.which("ffmpeg") or "/usr/local/fsl/bin/ffmpeg"
KOKORO_TEST = ["af_heart", "am_michael", "bf_emma", "bm_george"]          # the clips tested and shipped
KOKORO_TEMPLATES = ["af_bella", "af_nicole", "am_adam", "bf_isabella", "bm_lewis"]  # extra neutral readings
SAY_VOICES = ["Samantha", "Daniel", "Karen", "Moira", "Tessa", "Rishi"]
ESPEAK_VOICES = ["en-us", "en-gb", "en-us+f3"]
# The focus added to Kokoro's reading (see the docstring).
FOCUS = {"accent_st": 5.0, "gain_db": 4.0, "stretch": 1.3, "post_st": -2.0, "post_range": 0.5, "post_db": -2.0}
# Where the pitch peak falls within the word: early for never and money (stress on the first syllable).
PEAK_AT = {"never": 0.3, "money": 0.3}


def to_wav16k(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", "-map_metadata", "-1", "-fflags", "+bitexact", str(dst)], check=True)


def write_float_wav(x: np.ndarray, sr: int, path: Path) -> None:
    y = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((y * 32767).astype("<i2").tobytes())


def variants() -> list[tuple[str, int | None]]:
    return [("neutral", None)] + [(f"{i}_{w.lower()}", i) for i, w in enumerate(WORDS)]


# --- kokoro + WORLD ----------------------------------------------------------------------------------------------

def kokoro_pipelines():
    import misaki.espeak

    class _NoFallback:  # every word of the sentence is in Kokoro's lexicon; its espeak fallback needs a data path
        def __init__(self, *a, **k):
            pass

        def __call__(self, token):
            return (None, None)
    misaki.espeak.EspeakFallback = _NoFallback
    from kokoro import KPipeline
    return {"a": KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M"),
            "b": KPipeline(lang_code="b", repo_id="hexgrad/Kokoro-82M")}


def kokoro_say(pipes, voice: str) -> tuple[np.ndarray, list[tuple[float, float]]]:
    audio, times = [], []
    for r in pipes[voice[0]](SENTENCE, voice=voice):
        audio.append(r.audio.numpy())
        for t in r.tokens:
            if t.text.strip(".") and t.start_ts is not None:
                times.append((float(t.start_ts), float(t.end_ts)))
    if len(times) != len(WORDS):
        raise RuntimeError(f"{voice}: expected {len(WORDS)} word times, got {len(times)}")
    return np.concatenate(audio).astype(np.float64), times


def ramp(t: np.ndarray, a: float, b: float, edge: float = 0.02) -> np.ndarray:
    """1 inside [a, b], 0 outside, with linear ramps of `edge` seconds."""
    up = np.clip((t - (a - edge)) / edge, 0, 1)
    down = np.clip(((b + edge) - t) / edge, 0, 1)
    return np.minimum(up, down)


def add_focus(x: np.ndarray, sr: int, times: list[tuple[float, float]], k: int | None, p: dict = FOCUS):
    """WORLD analysis and resynthesis; with k, focus on word k (see the docstring). Returns audio and word times."""
    import pyworld as pw
    fp = 5.0
    f0, t = pw.harvest(x, sr, frame_period=fp)
    sp = pw.cheaptrick(x, f0, t, sr)
    ap = pw.d4c(x, f0, t, sr)
    if k is None:
        return pw.synthesize(f0, sp, ap, sr, fp), list(times)
    a, b = times[k]
    voiced = f0 > 0
    # the pitch accent: a rise to the peak and a fall after it, spanning the word and 30 ms either side
    peak = a + PEAK_AT.get(WORDS[k], 0.5) * (b - a)
    lo, hi = a - 0.03, b + 0.03
    bump = np.where(t <= peak, 0.5 * (1 - np.cos(np.pi * np.clip((t - lo) / (peak - lo), 0, 1))),
                    0.5 * (1 + np.cos(np.pi * np.clip((t - peak) / (hi - peak), 0, 1))))
    st = p["accent_st"] * bump
    # after the focus: lower and flatter, easing in over 60 ms
    post = np.clip((t - b) / 0.06, 0, 1)
    after = voiced & (t > b)
    ref = float(np.median(f0[after])) if after.any() else 1.0
    f0_new = f0.copy()
    f0_new[voiced] = f0[voiced] * 2 ** (st[voiced] / 12)
    if after.any():
        comp = ref * (f0[after] / ref) ** p["post_range"] * 2 ** (p["post_st"] / 12)
        w = post[after]
        f0_new[after] = (1 - w) * f0_new[after] + w * comp
    gain = 10 ** ((p["gain_db"] * ramp(t, a, b) + p["post_db"] * post) / 10)  # sp is a power spectrum
    sp_new = sp * gain[:, None]
    # longer: the word's frames are read out at 1/stretch speed
    fa, fb = int(round(a * 1000 / fp)), int(round(b * 1000 / fp))
    idx = np.concatenate([np.arange(fa), np.arange(fa, fb, 1 / p["stretch"]), np.arange(fb, len(t))])
    near = np.clip(np.round(idx).astype(int), 0, len(t) - 1)
    lo_i = np.clip(np.floor(idx).astype(int), 0, len(t) - 1)
    hi_i = np.clip(lo_i + 1, 0, len(t) - 1)
    frac = (idx - lo_i)[:, None]
    sp_out = (1 - frac) * sp_new[lo_i] + frac * sp_new[hi_i]
    ap_out = (1 - frac) * ap[lo_i] + frac * ap[hi_i]
    f0_out = np.where((f0_new[lo_i] > 0) & (f0_new[hi_i] > 0),
                      (1 - frac[:, 0]) * f0_new[lo_i] + frac[:, 0] * f0_new[hi_i], f0_new[near])
    y = pw.synthesize(np.ascontiguousarray(f0_out), np.ascontiguousarray(sp_out), np.ascontiguousarray(ap_out), sr, fp)
    extra = (p["stretch"] - 1) * (b - a)
    new_times = [(s, e) if e <= a + 1e-9 else ((s, a + p["stretch"] * (b - a)) if j == k else (s + extra, e + extra))
                 for j, (s, e) in enumerate(times)]
    return y, new_times


def make_kokoro(out: Path, voices: list[str], ship: bool) -> None:
    import soundfile as sf
    pipes = kokoro_pipelines()
    for voice in voices:
        x, times = kokoro_say(pipes, voice)
        sr = 24000
        folder = out / "stimuli" / "kokoro" / voice
        folder.mkdir(parents=True, exist_ok=True)
        meta = {"family": "kokoro", "voice": voice, "model": "hexgrad/Kokoro-82M", "focus": FOCUS, "peak_at": PEAK_AT,
                "clips": {}}
        for name, k in variants():
            y, t = add_focus(x, sr, times, k)
            y = y / max(1e-6, np.abs(y).max()) * 0.89  # -1 dBFS peak
            with tempfile.TemporaryDirectory() as tmp:
                hi = Path(tmp) / "hi.wav"
                sf.write(hi, y, sr, subtype="PCM_16")
                to_wav16k(hi, folder / f"{name}.wav")
                if ship:
                    dst = out / "ship" / voice / f"{name}.mp3"
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y", "-i", str(hi), "-ac", "1",
                                    "-c:a", "libmp3lame", "-b:a", "48k", "-map_metadata", "-1", str(dst)], check=True)
            meta["clips"][name] = {"stressed": k, "word_times": [[round(s, 4), round(e, 4)] for s, e in t]}
        (folder / "meta.json").write_text(json.dumps(meta, indent=1))
        print(f"kokoro {voice}: {len(meta['clips'])} clips")


# --- macOS say -----------------------------------------------------------------------------------------------------

SAY_ON = "[[pbas +6]][[volm 1.0]][[rate -60]]"
SAY_OFF = "[[rate +60]][[volm 0.55]][[pbas -8]]"  # back to the old rate and volume, 2 below the old pitch


def say_text(k: int | None) -> str:
    words = SENTENCE.rstrip(".").split()
    if k is None:
        return "[[volm 0.55]]" + " ".join(words) + "."
    words[k] = SAY_ON + words[k] + SAY_OFF
    return "[[volm 0.55]]" + " ".join(words) + "."


def make_say(out: Path, voices: list[str]) -> None:
    for voice in voices:
        folder = out / "stimuli" / "say" / voice
        folder.mkdir(parents=True, exist_ok=True)
        meta = {"family": "say", "voice": voice, "on": SAY_ON, "off": SAY_OFF, "clips": {}}
        for name, k in variants():
            text = say_text(k)
            with tempfile.TemporaryDirectory() as tmp:
                aiff = Path(tmp) / "x.aiff"
                subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
                to_wav16k(aiff, folder / f"{name}.wav")
            meta["clips"][name] = {"stressed": k, "text": text}
        (folder / "meta.json").write_text(json.dumps(meta, indent=1))
        print(f"say {voice}: {len(meta['clips'])} clips")


# --- eSpeak NG -----------------------------------------------------------------------------------------------------

def espeak_ssml(k: int | None) -> str:
    words = SENTENCE.rstrip(".").split()
    if k is not None:
        words[k] = f'<emphasis level="strong">{words[k]}</emphasis>'
    return "<speak>" + " ".join(words) + ".</speak>"


def make_espeak(out: Path, voices: list[str]) -> None:
    exe = shutil.which("espeak-ng")
    if not exe:
        raise SystemExit("espeak-ng isn't installed (brew install espeak-ng)")
    for voice in voices:
        folder = out / "stimuli" / "espeak" / voice
        folder.mkdir(parents=True, exist_ok=True)
        meta = {"family": "espeak", "voice": voice, "clips": {}}
        for name, k in variants():
            ssml = espeak_ssml(k)
            with tempfile.TemporaryDirectory() as tmp:
                raw = Path(tmp) / "x.wav"
                subprocess.run([exe, "-v", voice, "-m", "-w", str(raw), ssml], check=True)
                to_wav16k(raw, folder / f"{name}.wav")
            meta["clips"][name] = {"stressed": k, "ssml": ssml}
        (folder / "meta.json").write_text(json.dumps(meta, indent=1))
        print(f"espeak {voice}: {len(meta['clips'])} clips")


# --- kokoro v2: the stress made unmistakable (a revision after the run, not pre-registered) ------------------------
#
# Listening with his eyes closed, one of us couldn't tell which word v1 stressed. v2 makes English contrastive focus
# as large as speakers make it. Kokoro predicts each phoneme's length and a pitch track, then renders the voice from
# them; v2 (candidate D2, chosen by ear) edits those predictions before it renders (no vocoder resynthesis) and then
# raises the word's level:
# - the word: vowels 2.2 times as long ("she" and "stole" a little more), its onset consonant 10% longer and its other
#   consonants 35%; a rise-fall pitch accent that starts 120 ms before the word, peaks 12 semitones up on its stressed
#   vowel and ends 2 semitones under the old track, the whole pitch edit smoothed over 40 ms; Kokoro's energy track +1;
#   9 dB louder, rising over the 90 ms before the word and falling over 80 ms after it;
# - the space before it held 50 ms longer by Kokoro (a slower transition, silent only where the neutral has a closure);
# - after it: 3 semitones lower, a third of the pitch range, 3.5 dB softer and 10% faster;
# - before it: pitch range at 70%.
# The neutral reading is Kokoro's plain rendering. v1's edits were placed with Kokoro's own word timestamps, which
# run 75-110 ms ahead of the sound (they start each word 3 duration frames early); v2 places its edits on Kokoro's
# frame alignment, which its decoder follows to within 10 ms. meta.json keeps word_times in v1's convention (Kokoro's
# timestamps, what the aligner's templates use) and word_spans_audio, the frame-aligned spans.
# Candidates tried, and chosen by ear in a blind listening test, are listed in docs/plato_phaedrus.md.

V2_SUBDIR = "v2"
# The candidates of the listening test (B, D and E; A was v1, C Kokoro's stress marks alone). method "inside" edits
# Kokoro's predictions before it renders; "world" edits Kokoro's plain rendering with the WORLD vocoder; marks puts
# Kokoro's primary-stress mark on the word and removes every other stress mark.
_STRONG = {"accent_st": 12.0, "fall_to": -2.0, "gain_db": 9.0, "vowel_stretch": 2.0, "cons_stretch": 1.35,
           "pause_s": 0.15, "post_st": -3.0, "post_range": 0.35, "post_db": -3.5, "post_rate": 0.9, "pre_range": 0.7}
V2_CANDIDATES = {
    "B": {"method": "world", "marks": False, "energy": 0.0, **_STRONG},
    "D": {"method": "inside", "marks": False, "energy": 1.0, **_STRONG},
    "E": {"method": "inside", "marks": True, "energy": 0.5, "accent_st": 8.0, "fall_to": -1.5, "gain_db": 6.0,
          "vowel_stretch": 1.6, "cons_stretch": 1.2, "pause_s": 0.12, "post_st": -2.5, "post_range": 0.5,
          "post_db": -3.0, "post_rate": 0.93, "pre_range": 0.8},
}
# Round 2 of the listening test: B, D and E were clear, but each had "a weird hiccup right at the start of the
# emphasised word". The inserted silence made the level jump about 20 dB in 5 ms more than the neutral reading at the
# same spot. The smooth versions drop it; the gap before the word, if any, is Kokoro's own (the space before the word
# held longer); the gain rises over 90 ms before the word and falls over 80 ms after it; the pitch starts rising
# 120 ms before the word (an L+H* glide) and every pitch edit is smoothed over 40 ms; the stressed vowel takes most
# of the lengthening, the onset consonant little; "she" and "stole" a little longer.
_SMOOTH = {"pause_s": 0.0, "gap_frames": 2, "gain_ramp_s": 0.09, "gain_release_s": 0.08, "rise_lead_s": 0.12,
           "smooth_s": 0.04, "post_ease_s": 0.10, "pre_fade": True, "onset_stretch": 1.1,
           "longer": {"she": 1.25, "stole": 1.3}}
# the vowels a little longer than in B and D, since the onset consonants are now stretched less; E's "she" is already
# very long (Kokoro lengthens a stressed "she" a lot by itself)
V2_CANDIDATES["D2"] = {**V2_CANDIDATES["D"], **_SMOOTH, "vowel_stretch": 2.2}
V2_CANDIDATES["E2"] = {**V2_CANDIDATES["E"], **_SMOOTH, "vowel_stretch": 1.7, "longer": {"stole": 1.3}}
V2_CANDIDATES["B2"] = {**V2_CANDIDATES["B"], **_SMOOTH, "vowel_stretch": 2.2, "gap_frames": 0}
V2_PICK = "D2"  # chosen by ear: round 3 of the blind listening test (docs/plato_phaedrus.md)
FOCUS_V2 = V2_CANDIDATES[V2_PICK]
KOKORO_SR = 24000
KOKORO_FRAME = 600 / KOKORO_SR   # one unit of Kokoro's predicted durations: 25 ms
VOWELS = set("AIOWYQaeiouæɑɐɒɔəɛɜɪʊʌᵻɚɝːɘɵ")  # misaki's vowels and diphthongs (A = eɪ, I = aɪ, O = oʊ, Q = əʊ, ...)
STRESS_MARKS = set("ˈˌ")


def raised(t: np.ndarray, a: float, b: float) -> np.ndarray:
    """0 before a, 1 after b, a raised-cosine step between."""
    return 0.5 * (1 - np.cos(np.pi * np.clip((t - a) / max(b - a, 1e-6), 0, 1)))


def focus_f0(t: np.ndarray, f0: np.ndarray, spans: list[tuple[float, float]], k: int, peak_t: float,
             p: dict = FOCUS_V2) -> np.ndarray:
    """Contrastive focus on a pitch track (Hz per frame at times t, in s; <= 30 Hz counts as unvoiced and is left
    alone): a rise-fall accent on word k peaking p["accent_st"] semitones up at peak_t and ending p["fall_to"] at the
    word's end; the words after it p["post_st"] lower with p["post_range"] of their range; the words before it with
    p["pre_range"] of theirs."""
    voiced = f0 > 30
    if voiced.sum() < 5:
        return f0.copy()
    med = float(np.median(f0[voiced]))
    st = np.where(voiced, 12 * np.log2(np.maximum(f0, 1e-6) / med), 0.0)
    out = st.copy()
    a, b = spans[k]
    lo = a - p.get("rise_lead_s", 0.04)
    pre = voiced & (t < a)
    if pre.any():
        ref = np.median(st[pre])
        flat = ref + p["pre_range"] * (st[pre] - ref)
        # smooth versions: the flattening hands over to the accent's rise instead of stopping at the word's onset
        w = 1 - raised(t[pre], lo, a) if p.get("pre_fade") else 1.0
        out[pre] = w * flat + (1 - w) * st[pre]
    bump = np.where(t <= peak_t, p["accent_st"] * raised(t, lo, peak_t),
                    p["accent_st"] * (1 - raised(t, peak_t, b)) + p["fall_to"] * raised(t, peak_t, b))
    inword = (t >= lo) & (t <= b)
    out[inword] += bump[inword]
    after = voiced & (t > b)
    if after.any():
        ref = np.median(st[after])
        comp = ref + p["post_range"] * (st[after] - ref) + p["post_st"]
        ease = p.get("post_ease_s", 0.06)  # from the accent's tail into the compressed track
        w = raised(t[after], b, b + ease) if p.get("pre_fade") else np.clip((t[after] - b) / ease, 0, 1)
        out[after] = (1 - w) * (st[after] + p["fall_to"]) + w * comp
    sm = p.get("smooth_s", 0.0)
    if sm:
        # the edit (not the voice's own pitch) smoothed over sm seconds, through the unvoiced gaps, so no step is left
        delta = np.interp(t, t[voiced], (out - st)[voiced])
        n = max(3, int(round(sm / max(float(np.median(np.diff(t))), 1e-6))) | 1)
        win = np.hanning(n + 2)[1:-1]
        delta = np.convolve(np.pad(delta, n // 2, mode="edge"), win / win.sum(), mode="valid")
        out = st + delta
    return np.where(voiced, med * 2 ** (out / 12), f0)


def word_gain(y: np.ndarray, sr: int, spans: list[tuple[float, float]], k: int, p: dict = FOCUS_V2) -> np.ndarray:
    """Word k p["gain_db"] louder (20 ms ramps), everything after it p["post_db"] (a 50 ms ramp)."""
    return y * 10 ** (gain_db_at(np.arange(len(y)) / sr, spans, k, p) / 20)


def gain_db_at(t: np.ndarray, spans: list[tuple[float, float]], k: int, p: dict = FOCUS_V2) -> np.ndarray:
    """The level change (dB) at times t: word k p["gain_db"] up, everything after it p["post_db"]. With
    p["gain_ramp_s"], a raised-cosine rise that ends at the word's onset (none inside its first consonant) and a
    raised-cosine release of p["gain_release_s"] at its end; otherwise 20 ms linear ramps."""
    a, b = spans[k]
    if p.get("gain_ramp_s"):
        up = raised(t, a - p["gain_ramp_s"], a)
        rel = raised(t, b - 0.02, b - 0.02 + p["gain_release_s"])
        return p["gain_db"] * up * (1 - rel) + p["post_db"] * rel
    db = p["gain_db"] * np.minimum(np.clip((t - (a - 0.02)) / 0.02, 0, 1), np.clip(((b + 0.02) - t) / 0.02, 0, 1))
    return db + p["post_db"] * np.clip((t - b) / 0.05, 0, 1)


def insert_pause(y: np.ndarray, sr: int, at: float, pause_s: float, fade_s: float = 0.008) -> tuple[np.ndarray, float]:
    """pause_s of silence, cut in at the quietest 10 ms from 40 ms before to 15 ms after `at`, with 8 ms fades.
    Returns the audio and the time of the cut (s)."""
    win, step = int(0.010 * sr), int(0.0025 * sr)
    cands = np.arange(int((at - 0.04) * sr), int((at + 0.015) * sr), step)
    cands = cands[(cands - win // 2 >= 0) & (cands + win // 2 < len(y))]
    i = int(round(at * sr))
    if len(cands):
        i = int(cands[int(np.argmin([np.sqrt(np.mean(y[c - win // 2:c + win // 2] ** 2)) for c in cands]))])
    nf = int(fade_s * sr)
    left, right = y[:i].copy(), y[i:].copy()
    left[-nf:] *= np.linspace(1, 0, nf)
    right[:nf] *= np.linspace(0, 1, nf)
    return np.concatenate([left, np.zeros(int(round(pause_s * sr))), right]), i / sr


def sentence_phonemes(tokens, k_marks: int | None = None) -> tuple[str, list[int]]:
    """The phoneme string Kokoro reads (as KPipeline.tokens_to_ps) and each character's word (-1 punctuation, -2 a
    space). With k_marks, the stress marks of every word are removed and word k_marks gets a primary stress; the
    tokens' phonemes are changed to match (so KPipeline.join_timestamps still lines up)."""
    ps, cmap, k = "", [], 0
    for t in tokens:
        ph = t.phonemes or ""
        word = t.text.strip(".,!?").lower()
        idx = -1
        if word and k < len(WORDS) and word == WORDS[k].lower():
            idx, k = k, k + 1
            if k_marks is not None:
                if idx == k_marks and "ˈ" in ph:
                    ph = ph.replace("ˌ", "")
                else:
                    ph = "".join(c for c in ph if c not in STRESS_MARKS)
                    if idx == k_marks:
                        v = next(i for i, c in enumerate(ph) if c in VOWELS)
                        ph = ph[:v] + "ˈ" + ph[v:]
                t.phonemes = ph
        ps += ph
        cmap += [idx] * len(ph)
        if t.whitespace:
            ps += " "
            cmap.append(-2)
    while ps.endswith(" "):
        ps, cmap = ps[:-1], cmap[:-1]
    if k != len(WORDS):
        raise RuntimeError(f"found {k} of {len(WORDS)} words in {[t.text for t in tokens]}")
    return ps, cmap


class KokoroV2:
    """Kokoro-82M with its predicted durations, pitch and energy edited before its decoder renders the voice
    (candidate B instead edits its plain rendering with the WORLD vocoder)."""

    def __init__(self):
        import torch
        self.torch = torch
        self.pipes = kokoro_pipelines()
        self.model = self.pipes["a"].model
        self.pipes["b"].model = self.model

    def render(self, voice: str, k: int | None, p: dict = FOCUS_V2, seed: int = 0) -> dict:
        """Word k focused (None: the plain reading). Returns the audio (24 kHz), the frame-aligned word spans and
        Kokoro-convention word times (both in s, after any pause), the phonemes and the pause."""
        from kokoro import KPipeline
        torch, m = self.torch, self.model
        torch.manual_seed(seed)  # the decoder's harmonic source has random phases
        _, toks = self.pipes[voice[0]].g2p(SENTENCE)
        ps, cmap = sentence_phonemes(toks, k if (k is not None and p.get("marks")) else None)
        if any(c not in m.vocab for c in ps):
            raise RuntimeError(f"{voice}: phonemes outside Kokoro's vocabulary in {ps!r}")
        inside = k is not None and p["method"] == "inside"
        ref_s = self.pipes[voice[0]].load_voice(voice)[len(ps) - 1]
        ids = torch.LongTensor([[0, *[m.vocab[c] for c in ps], 0]])
        T = ids.shape[1]
        lengths = torch.full((1,), T, dtype=torch.long)
        mask = torch.zeros((1, T), dtype=torch.bool)
        cm = np.array([-3] + cmap + [-3])
        chars = [""] + list(ps) + [""]
        with torch.no_grad():  # KModel.forward_with_tokens, with the edits in between
            d_en = m.bert_encoder(m.bert(ids, attention_mask=(~mask).int())).transpose(-1, -2)
            s = ref_s[:, 128:]
            d = m.predictor.text_encoder(d_en, s, lengths, mask)
            x, _ = m.predictor.lstm(d)
            dur = torch.sigmoid(m.predictor.duration_proj(x)).sum(axis=-1).squeeze()
            if inside:
                pos_k = np.flatnonzero(cm == k)
                first_v = next(i for i in pos_k if chars[i] in VOWELS)
                more = p.get("longer", {}).get(WORDS[k], 1.0)
                for i in range(T):
                    if cm[i] == k:
                        if chars[i] in VOWELS:
                            dur[i] *= p["vowel_stretch"] * more
                        elif i < first_v and "onset_stretch" in p:  # the onset consonant (and stress mark): little
                            dur[i] *= p["onset_stretch"]
                        else:
                            dur[i] *= p["cons_stretch"]
                    elif cm[i] > k:
                        dur[i] *= p["post_rate"]
                if p.get("gap_frames") and k > 0 and cm[pos_k[0] - 1] == -2:
                    dur[pos_k[0] - 1] += p["gap_frames"]  # Kokoro's own gap: the space before the word held longer
            pred = torch.round(dur).clamp(min=1).long()
            idx = torch.repeat_interleave(torch.arange(T), pred)
            aln = torch.zeros((T, idx.shape[0]))
            aln[idx, torch.arange(idx.shape[0])] = 1
            aln = aln.unsqueeze(0)
            F0, Nn = m.predictor.F0Ntrain(d.transpose(-1, -2) @ aln, s)
            cum = np.concatenate([[0], np.cumsum(pred.numpy())])
            spans = []
            for w in range(len(WORDS)):
                pos = np.flatnonzero(cm == w)
                spans.append((float(cum[pos[0]] * KOKORO_FRAME), float(cum[pos[-1] + 1] * KOKORO_FRAME)))
            if k is not None:
                pos = np.flatnonzero(cm == k)
                seq = [chars[i] for i in pos]
                vi = None
                if "ˈ" in seq:  # the vowel after the primary-stress mark, else the word's first vowel
                    vi = next((pos[j] for j in range(seq.index("ˈ"), len(seq)) if seq[j] in VOWELS), None)
                if vi is None:
                    vi = next(i for i in pos if chars[i] in VOWELS)
                vj = vi
                while cm[vj + 1] == k and chars[vj + 1] in VOWELS:
                    vj += 1
                peak_t = float((cum[vi] + 0.6 * (cum[vj + 1] - cum[vi])) * KOKORO_FRAME)
            if inside:
                tf = (np.arange(F0.shape[-1]) + 0.5) * KOKORO_FRAME / 2  # the pitch track runs at twice the frame rate
                f0 = focus_f0(tf, F0[0].numpy().astype(np.float64), spans, k, peak_t, p)
                F0 = torch.from_numpy(f0[None].astype(np.float32))
                a, b = spans[k]
                if p.get("gain_ramp_s"):
                    env = raised(tf, a - p["gain_ramp_s"], a) * (1 - raised(tf, b - 0.02, b - 0.02 + p["gain_release_s"]))
                else:
                    env = np.minimum(np.clip((tf - (a - 0.03)) / 0.03, 0, 1), np.clip(((b + 0.03) - tf) / 0.03, 0, 1))
                Nn = Nn + torch.from_numpy((p["energy"] * env)[None].astype(np.float32))
            y = m.decoder(m.text_encoder(ids, lengths, mask) @ aln, F0, Nn, ref_s[:, :128])
            y = y.squeeze().numpy().astype(np.float64)
        # Kokoro's own word timestamps from the same durations: v1's convention, which the aligner's templates use
        KPipeline.join_timestamps(toks, pred)
        times = [(float(t.start_ts), float(t.end_ts)) for t in toks if t.text.strip(".") and t.start_ts is not None]
        if len(times) != len(WORDS):
            raise RuntimeError(f"{voice}: {len(times)} word times")
        if p["method"] == "world":  # the WORLD vocoder on the plain rendering; its neutral reading goes through it too
            phones = [[(float(cum[i] * KOKORO_FRAME), float(cum[i + 1] * KOKORO_FRAME), chars[i] in VOWELS)
                       for i in np.flatnonzero(cm == w) if chars[i] not in STRESS_MARKS] for w in range(len(WORDS))]
            y, warp = world_focus_v2(y, KOKORO_SR, spans, phones, k, peak_t if k is not None else 0.0, p)
            spans = [(warp(a), warp(b)) for a, b in spans]
            times = [(warp(a), warp(b)) for a, b in times]
        pause = 0.0
        if k is not None:
            if inside:
                y = word_gain(y, KOKORO_SR, spans, k, p)
            if k > 0 and p["pause_s"] > 0:
                y, cut = insert_pause(y, KOKORO_SR, spans[k][0], p["pause_s"])
                pause = p["pause_s"]
                spans = [sp if j < k else (sp[0] + pause, sp[1] + pause) for j, sp in enumerate(spans)]
                spans[k - 1] = (spans[k - 1][0], min(spans[k - 1][1], cut))
                times = [tt if j < k else (tt[0] + pause, tt[1] + pause) for j, tt in enumerate(times)]
        return {"audio": y, "spans": spans, "times": times, "phonemes": ps, "pause_s": pause}


def world_focus_v2(x: np.ndarray, sr: int, spans: list[tuple[float, float]], phones: list[list[tuple[float, float, bool]]],
                   k: int | None, peak_t: float, p: dict):
    """Candidate B: the focus with the WORLD vocoder on Kokoro's plain rendering. phones: per word, each phoneme's
    (start, end, is a vowel). Returns the audio and a function mapping old times to new."""
    import pyworld as pw
    fp = 5.0
    f0, t = pw.harvest(x, sr, frame_period=fp)
    sp = pw.cheaptrick(x, f0, t, sr)
    ap = pw.d4c(x, f0, t, sr)
    if k is None:
        return pw.synthesize(f0, sp, ap, sr, fp), (lambda s: s)
    a, b = spans[k]
    f0n = focus_f0(t, f0, spans, k, peak_t, p)
    sp = sp * (10 ** (gain_db_at(t, spans, k, p) / 10))[:, None]  # a power spectrum
    rate = np.ones_like(t)  # input frames advanced per output frame
    more = p.get("longer", {}).get(WORDS[k], 1.0)
    seen_vowel = False
    for s0, e0, vowel in phones[k]:
        seen_vowel = seen_vowel or vowel
        stretch = (p["vowel_stretch"] * more if vowel else
                   p["onset_stretch"] if (not seen_vowel and "onset_stretch" in p) else p["cons_stretch"])
        rate[(t >= s0) & (t < e0)] = 1 / stretch
    rate[t >= b] = 1 / p["post_rate"]
    idx, pos = [], 0.0
    while pos < len(t) - 1:
        idx.append(pos)
        pos += rate[int(pos)]
    idx = np.array(idx)
    lo = np.clip(np.floor(idx).astype(int), 0, len(t) - 1)
    hi = np.clip(lo + 1, 0, len(t) - 1)
    near = np.clip(np.round(idx).astype(int), 0, len(t) - 1)
    frac = (idx - lo)[:, None]
    f0o = np.where((f0n[lo] > 0) & (f0n[hi] > 0), (1 - frac[:, 0]) * f0n[lo] + frac[:, 0] * f0n[hi], f0n[near])
    y = pw.synthesize(np.ascontiguousarray(f0o), np.ascontiguousarray((1 - frac) * sp[lo] + frac * sp[hi]),
                      np.ascontiguousarray((1 - frac) * ap[lo] + frac * ap[hi]), sr, fp)
    t_out = np.arange(len(idx)) * fp / 1000
    return y, (lambda s: float(np.interp(s * 1000 / fp, idx, t_out)))


def make_kokoro_v2(out: Path, voices: list[str], p: dict = FOCUS_V2) -> None:
    """DIR/v2/stimuli/kokoro/<voice>/*.wav (16 kHz) with meta.json, and DIR/v2/ship/<voice>/*.mp3 (24 kHz)."""
    import soundfile as sf
    kv = KokoroV2()
    for vi, voice in enumerate(voices):
        folder = out / "stimuli" / "kokoro" / voice
        folder.mkdir(parents=True, exist_ok=True)
        how = {"inside": "Kokoro's predicted durations, pitch and energy edited before its decoder renders; then the "
                         "word's level raised",
               "world": "Kokoro's plain rendering edited with the WORLD vocoder"}
        meta = {"family": "kokoro", "voice": voice, "model": "hexgrad/Kokoro-82M", "version": "v2",
                "candidate": next((c for c, q in V2_CANDIDATES.items() if q == p), None),
                "method": how[p["method"]] + (", with Kokoro's primary-stress mark on the word only" if p["marks"] else "")
                + ("; a pause cut in before the word" if p["pause_s"] else "")
                + ("; the space before the word held longer by Kokoro" if p.get("gap_frames") else ""),
                "focus": p, "clips": {}}
        for ci, (name, k) in enumerate(variants()):
            r = kv.render(voice, k, p, seed=1000 * vi + ci)
            y = r["audio"] / max(1e-6, np.abs(r["audio"]).max()) * 0.89  # -1 dBFS peak
            with tempfile.TemporaryDirectory() as tmp:
                hi = Path(tmp) / "hi.wav"
                sf.write(hi, y, KOKORO_SR, subtype="PCM_16")
                to_wav16k(hi, folder / f"{name}.wav")
                dst = out / "ship" / voice / f"{name}.mp3"
                dst.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y", "-i", str(hi), "-ac", "1",
                                "-c:a", "libmp3lame", "-b:a", "48k", "-map_metadata", "-1", str(dst)], check=True)
            meta["clips"][name] = {"stressed": k, "phonemes": r["phonemes"], "pause_s": r["pause_s"], "seed": 1000 * vi + ci,
                                   "word_times": [[round(s, 4), round(e, 4)] for s, e in r["times"]],
                                   "word_spans_audio": [[round(s, 4), round(e, 4)] for s, e in r["spans"]]}
        (folder / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
        print(f"kokoro v2 {voice}: {len(meta['clips'])} clips")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--family", nargs="+", default=["kokoro", "say", "espeak"])
    ap.add_argument("--out", type=Path, default=PHAEDRUS_DIR)
    ap.add_argument("--kokoro-version", choices=["v1", "v2"], default="v1",
                    help="v2: the stronger focus, written to DIR/v2 (the four tested voices only)")
    ap.add_argument("--candidate", choices=sorted(V2_CANDIDATES), default=V2_PICK,
                    help=f"with --kokoro-version v2: which listening-test candidate (default {V2_PICK}, the one chosen)")
    args = ap.parse_args()
    if "kokoro" in args.family and args.kokoro_version == "v2":
        make_kokoro_v2(args.out / V2_SUBDIR, KOKORO_TEST, V2_CANDIDATES[args.candidate])
    elif "kokoro" in args.family:
        make_kokoro(args.out, KOKORO_TEST, ship=True)
        make_kokoro(args.out, KOKORO_TEMPLATES, ship=False)
    if "say" in args.family:
        make_say(args.out, SAY_VOICES)
    if "espeak" in args.family:
        make_espeak(args.out, ESPEAK_VOICES)


if __name__ == "__main__":
    main()

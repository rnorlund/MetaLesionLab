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
- say: macOS voices. Their emphasis command, [[emph +]], is ignored on this Mac (the audio is bit-identical with
  and without it), so the word is marked with the voices' pitch, volume and rate commands instead: [[pbas +6]],
  [[volm]] from 0.55 to 1.0 and [[rate -60]] on the word, [[pbas -2]] after it. Apple's licence doesn't allow
  publishing these voices' output, so these clips never leave this computer.
- espeak: eSpeak NG (GPL-3.0) with SSML <emphasis level="strong">: the synthesizer's own emphasis, set by none
  of our numbers.

Usage (Kokoro needs kokoro, pyworld and soundfile, which the web app doesn't; use a separate environment):
  python scripts/plato_phaedrus_stimuli.py --family kokoro say espeak [--out DIR]

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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--family", nargs="+", default=["kokoro", "say", "espeak"])
    ap.add_argument("--out", type=Path, default=PHAEDRUS_DIR)
    args = ap.parse_args()
    if "kokoro" in args.family:
        make_kokoro(args.out, KOKORO_TEST, ship=True)
        make_kokoro(args.out, KOKORO_TEMPLATES, ship=False)
    if "say" in args.family:
        make_say(args.out, SAY_VOICES)
    if "espeak" in args.family:
        make_espeak(args.out, ESPEAK_VOICES)


if __name__ == "__main__":
    main()

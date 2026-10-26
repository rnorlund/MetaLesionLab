"""Check the naming-latency detector (audio.detect_speech) on synthesized speech with known timing.

Each clip is built the way the Naming Assessment records one: a 300 ms lead-in before the picture
appears, then a known silence (200, 500, 1000 or 2000 ms), then one word spoken by macOS `say`.
The true onset is the known silence plus the word's own acoustic onset, taken as the first sample
of the synthesized word above -50 dBFS. Clips are tested clean and with white noise added at
-60 and -50 dBFS (a quiet and a noisier room). Prints the latency error per condition.

Needs macOS (`say`) and ffmpeg on PATH. Writes nothing to the repository.

    python scripts/validate_latency.py [--json results.json]
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from metalesionlab import audio

LEAD_IN_S = 0.3
SILENCES_MS = (200, 500, 1000, 2000)
NOISE_DBFS = (None, -60.0, -50.0)
TRUTH_DBFS = -50.0
WORDS = [("Samantha", w) for w in ("cat", "umbrella", "scissors", "helicopter", "fan", "house", "whistle", "pineapple")] + \
        [("Paulina", w) for w in ("gato", "silla", "zanahoria", "helicóptero")]


def synth(voice: str, word: str, tmp: Path) -> np.ndarray:
    aiff = tmp / "w.aiff"
    subprocess.run(["say", "-v", voice, "-o", str(aiff), word], check=True)
    wav = audio.to_wav16k(aiff.read_bytes(), ".aiff")
    x, rate = audio.samples(wav)
    assert rate == audio.SAMPLE_RATE
    return x


def to_wav(x: np.ndarray) -> bytes:
    return audio.pcm16_wav((np.clip(x, -1, 1) * 32767).round().astype("<i2").tobytes())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", type=Path, help="also write every trial to this JSON file")
    args = ap.parse_args()
    rate = audio.SAMPLE_RATE
    rng = np.random.default_rng(1)
    trials = []
    with tempfile.TemporaryDirectory() as tmp:
        for voice, word in WORDS:
            x = synth(voice, word, Path(tmp))
            own = int(np.flatnonzero(np.abs(x) >= 10 ** (TRUTH_DBFS / 20))[0])
            for silence_ms in SILENCES_MS:
                for noise in NOISE_DBFS:
                    clip = np.concatenate([np.zeros(int((LEAD_IN_S + silence_ms / 1000) * rate)), x, np.zeros(rate // 2)])
                    if noise is not None:
                        clip = clip + 10 ** (noise / 20) * rng.standard_normal(len(clip))
                    t = audio.detect_speech(to_wav(clip), search_from_s=LEAD_IN_S)
                    truth_ms = silence_ms + own / rate * 1000
                    got_ms = None if t.onset_s is None else (t.onset_s - LEAD_IN_S) * 1000
                    trials.append({"voice": voice, "word": word, "silence_ms": silence_ms,
                                   "noise_dbfs": noise, "truth_ms": round(truth_ms, 1),
                                   "latency_ms": None if got_ms is None else round(got_ms, 1),
                                   "error_ms": None if got_ms is None else round(got_ms - truth_ms, 1),
                                   "duration_ms": None if t.onset_s is None else round((t.offset_s - t.onset_s) * 1000)})

    print(f"{len(WORDS)} words x {len(SILENCES_MS)} silences x {len(NOISE_DBFS)} noise levels = {len(trials)} clips")
    print(f"{'condition':<14}{'n':>4}{'missed':>8}{'mean err':>10}{'mean |err|':>12}{'max |err|':>11}")
    worst = 0.0
    for noise in NOISE_DBFS:
        rows = [t for t in trials if t["noise_dbfs"] == noise]
        errs = [t["error_ms"] for t in rows if t["error_ms"] is not None]
        missed = len(rows) - len(errs)
        label = "clean" if noise is None else f"noise {noise:g} dBFS"
        print(f"{label:<14}{len(rows):>4}{missed:>8}{statistics.mean(errs):>9.1f} {statistics.mean(map(abs, errs)):>11.1f}"
              f"{max(map(abs, errs)):>11.1f}")
        if noise is None:
            worst = max(map(abs, errs))
    bad = [t for t in trials if t["error_ms"] is None or abs(t["error_ms"]) >= 50]
    for t in bad:
        print("  over 50 ms:", t)
    if args.json:
        args.json.write_text(json.dumps(trials, ensure_ascii=False, indent=1))
    print(f"clean speech: max |error| {worst:.1f} ms (target < 50 ms)")
    return 0 if worst < 50 else 1


if __name__ == "__main__":
    sys.exit(main())

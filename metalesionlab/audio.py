"""Audio for the Scorer: turn a browser recording into the WAV Muse Voice Transcribe accepts.

Browsers record webm/Opus (Chrome, Firefox) or mp4/AAC (Safari); the transcribe endpoint takes
only a RIFF/WAVE file holding mono 16-bit PCM at 16 or 24 kHz. ffmpeg does the conversion and
must be on PATH. A WAV that is already 16 kHz mono 16-bit passes through untouched.

Clips with no silence before the first word sometimes come back empty (synthesized French
"chat" and "ancre", Oct 26); pad_silence adds a lead-in for such clips.

detect_speech finds when speech starts and ends in a clip, for naming latency. It is a plain
energy-based voice-activity detector, documented next to its settings below.
"""
from __future__ import annotations

import re
import shutil
import struct
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000


class FFmpegMissing(RuntimeError):
    pass


def _parse_wav(wav: bytes) -> tuple[int, int, int, int, int, int]:
    """(format tag, channels, sample rate, bits per sample, data offset, data bytes)."""
    if len(wav) < 12 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    fmt, pos = None, 12
    while pos + 8 <= len(wav):
        cid, size = wav[pos:pos + 4], struct.unpack("<I", wav[pos + 4:pos + 8])[0]
        body = pos + 8
        if cid == b"fmt ":
            tag, channels, rate = struct.unpack("<HHI", wav[body:body + 8])
            bits = struct.unpack("<H", wav[body + 14:body + 16])[0]
            if tag == 0xFFFE and size >= 26:  # WAVE_FORMAT_EXTENSIBLE: the real tag opens the subformat GUID
                tag = struct.unpack("<H", wav[body + 24:body + 26])[0]
            fmt = (tag, channels, rate, bits)
        elif cid == b"data":
            if fmt is None:
                raise ValueError("WAV data chunk before fmt chunk")
            # A streamed WAV may carry a placeholder size; trust the bytes actually present.
            return (*fmt, body, min(size, len(wav) - body))
        pos = body + size + (size & 1)
    raise ValueError("WAV has no data chunk")


def wav_format(wav: bytes) -> tuple[int, int, int, int, int]:
    """(format tag, channels, sample rate, bits per sample, data bytes) from a RIFF/WAVE header."""
    tag, channels, rate, bits, _, n = _parse_wav(wav)
    return tag, channels, rate, bits, n


def duration_s(wav: bytes) -> float:
    _, channels, rate, bits, n = wav_format(wav)
    return n / (rate * channels * bits / 8)


def _is_transcribe_ready(data: bytes) -> bool:
    try:
        tag, channels, rate, bits, _ = wav_format(data)
    except (ValueError, struct.error):
        return False
    return (tag, channels, rate, bits) == (1, 1, SAMPLE_RATE, 16)


def to_wav16k(data: bytes, suffix: str) -> bytes:
    """Convert a recording (webm, ogg, m4a, mp4, wav...) to 16 kHz mono 16-bit PCM WAV.

    `suffix` is the file extension (".webm", "webm") or a MIME type ("audio/webm;codecs=opus");
    ffmpeg identifies the format from the content, so it only names the temporary file."""
    if _is_transcribe_ready(data):
        return data
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FFmpegMissing("ffmpeg is not on PATH; install it (brew install ffmpeg, apt install ffmpeg) "
                            "to convert browser recordings")
    ext = re.sub(r"[^a-z0-9]", "", suffix.lower().split(";")[0].rsplit("/", 1)[-1].rsplit(".", 1)[-1]) or "bin"
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / f"input.{ext}", Path(tmp) / "output.wav"
        src.write_bytes(data)
        result = subprocess.run(
            [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vn",
             "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", "-map_metadata", "-1",
             "-fflags", "+bitexact", str(dst)],
            capture_output=True, timeout=120)
        if result.returncode or not dst.exists():
            raise ValueError(f"ffmpeg could not convert the {ext} recording: "
                             f"{result.stderr.decode(errors='replace').strip()[-300:]}")
        return dst.read_bytes()


def pcm16_wav(samples: bytes, rate: int = SAMPLE_RATE, channels: int = 1) -> bytes:
    """Wrap raw 16-bit little-endian PCM in a minimal WAV header."""
    block = channels * 2
    header = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(samples), b"WAVE", b"fmt ", 16, 1, channels,
                         rate, rate * block, block, 16, b"data", len(samples))
    return header + samples


def pad_silence(wav: bytes, seconds: float = 0.5) -> bytes:
    """Add `seconds` of silence before and after a 16-bit PCM WAV."""
    tag, channels, rate, bits, start, n = _parse_wav(wav)
    if (tag, bits) != (1, 16):
        raise ValueError("pad_silence needs 16-bit PCM; run to_wav16k first")
    pad = b"\x00" * (int(rate * seconds) * channels * 2)
    return pcm16_wav(pad + wav[start:start + n] + pad, rate, channels)


def trim(wav: bytes, start_s: float = 0.0, end_s: float | None = None) -> bytes:
    """The part of a 16-bit PCM WAV between start_s and end_s (seconds from the start)."""
    tag, channels, rate, bits, start, n = _parse_wav(wav)
    if (tag, bits) != (1, 16):
        raise ValueError("trim needs 16-bit PCM; run to_wav16k first")
    block = channels * 2
    total = n // block
    a = min(total, max(0, int(round(start_s * rate))))
    b = total if end_s is None else min(total, max(a, int(round(end_s * rate))))
    return pcm16_wav(wav[start + a * block:start + b * block], rate, channels)


def samples(wav: bytes) -> tuple[np.ndarray, int]:
    """Mono float samples in [-1, 1] and the sample rate of a 16-bit PCM WAV."""
    tag, channels, rate, bits, start, n = _parse_wav(wav)
    if (tag, bits) != (1, 16):
        raise ValueError("samples needs 16-bit PCM; run to_wav16k first")
    n -= n % (channels * 2)
    x = np.frombuffer(wav[start:start + n], dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        x = x.reshape(-1, channels).mean(axis=1)
    return x, rate


# --- speech onset for naming latency ------------------------------------------------------
#
# The clip starts a little before the picture appears (the lead-in), so its first 150 ms hold
# only the room's background sound. Steps:
#   1. Energy: RMS in 10 ms windows every 5 ms, in dB relative to full scale (dBFS).
#   2. Noise floor: the median window energy in the first 150 ms. If that is more than 10 dB
#      above the quietest 5% of the clip (someone was talking during the lead-in), the quiet
#      windows set the floor instead and lead_in_noisy is set.
#   3. Threshold: 12 dB above the noise floor, and never below -55 dBFS, so a digitally silent
#      lead-in doesn't turn breath or hiss into speech.
#   4. Speech: the first stretch after picture onset that stays above the threshold for at
#      least 60 ms in total, bridging dips shorter than 30 ms. Shorter bursts (a click, a tap on
#      the keyboard) are ignored.
#   5. Onset: from the start of that stretch, step back while the energy is still 6 dB above
#      the noise floor, to catch soft starts such as /f/ or /h/. A window is timed at its centre.
#   6. Offset: the end of the last stretch above the threshold; response duration = offset - onset.
# On synthesized speech with known leading silence the onset is within a few ms (tests and
# scripts/validate_latency.py). Device input and display delays are not corrected here.

VAD_WINDOW_S = 0.010
VAD_HOP_S = 0.005
VAD_NOISE_S = 0.150
VAD_RISE_DB = 12.0
VAD_MIN_DBFS = -55.0
VAD_MIN_SPEECH_S = 0.060
VAD_MAX_GAP_S = 0.030
VAD_ONSET_RISE_DB = 6.0
VAD_LEAD_IN_EXCESS_DB = 10.0


@dataclass
class SpeechTiming:
    onset_s: float | None  # first speech at or after search_from_s, seconds from the clip start
    offset_s: float | None  # end of the last speech
    noise_dbfs: float
    threshold_dbfs: float
    peak_dbfs: float
    speech_at_start: bool  # already speaking when the search began (latency is then unreliable)
    lead_in_noisy: bool = False  # the lead-in was much louder than the quietest part of the clip

    def as_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def _frame_db(x: np.ndarray, rate: int) -> tuple[np.ndarray, int, int]:
    win, hop = max(1, int(round(VAD_WINDOW_S * rate))), max(1, int(round(VAD_HOP_S * rate)))
    if len(x) < win:
        return np.full(1, -120.0), win, hop
    n = 1 + (len(x) - win) // hop
    sq = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    starts = np.arange(n) * hop
    rms = np.sqrt(np.maximum(sq[starts + win] - sq[starts], 0) / win)
    return 20 * np.log10(rms + 1e-6), win, hop


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """[start, end) index pairs of the True stretches in a boolean array."""
    edges = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def detect_speech(wav: bytes, search_from_s: float = 0.0, noise_s: float = VAD_NOISE_S) -> SpeechTiming:
    """When speech starts and ends in a 16-bit PCM WAV (see the notes above for the method).

    search_from_s is where to start looking (the picture onset); the noise floor comes from the
    first noise_s seconds, or from the quietest tenth of the clip if the lead-in is shorter."""
    x, rate = samples(wav)
    db, win, hop = _frame_db(x, rate)
    centre = (np.arange(len(db)) * hop + win / 2) / rate
    lead = db[centre + VAD_WINDOW_S / 2 <= min(noise_s, max(search_from_s, 0.0)) + 1e-9]
    quiet = float(np.percentile(db, 5))
    noise = float(np.median(lead)) if len(lead) >= 3 else quiet
    noisy = noise > quiet + VAD_LEAD_IN_EXCESS_DB
    if noisy:
        noise = quiet
    threshold = max(noise + VAD_RISE_DB, VAD_MIN_DBFS)
    peak = float(db.max()) if len(db) else -120.0
    first = int(np.searchsorted(centre, search_from_s))

    above = db >= threshold
    above[:first] = False
    # Bridge short dips, then keep stretches long enough to be speech.
    runs = _runs(above)
    merged: list[list[int]] = []
    max_gap = int(round(VAD_MAX_GAP_S / VAD_HOP_S))
    for a, b in runs:
        if merged and a - merged[-1][1] <= max_gap:
            merged[-1][1] = b
            merged[-1][2] += b - a
        else:
            merged.append([a, b, b - a])
    min_frames = int(round(VAD_MIN_SPEECH_S / VAD_HOP_S))
    speech = [(a, b) for a, b, count in merged if count >= min_frames]
    if not speech:
        return SpeechTiming(None, None, noise, threshold, peak, False, noisy)

    a = speech[0][0]
    soft = max(noise + VAD_ONSET_RISE_DB, VAD_MIN_DBFS - VAD_ONSET_RISE_DB)
    while a > first and db[a - 1] >= soft:
        a -= 1
    at_start = a <= first and first < len(db) and db[first] >= soft and search_from_s > 0
    onset = float(centre[a])
    offset = float(centre[speech[-1][1] - 1])
    return SpeechTiming(onset, offset, noise, threshold, peak, bool(at_start), noisy)

"""Audio for the Scorer: turn a browser recording into the WAV Muse Voice Transcribe accepts.

Browsers record webm/Opus (Chrome, Firefox) or mp4/AAC (Safari); the transcribe endpoint takes
only a RIFF/WAVE file holding mono 16-bit PCM at 16 or 24 kHz. ffmpeg does the conversion and
must be on PATH. A WAV that is already 16 kHz mono 16-bit passes through untouched.

Clips with no silence before the first word sometimes come back empty (synthesized French
"chat" and "ancre", Oct 26); pad_silence adds a lead-in for such clips.
"""
from __future__ import annotations

import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

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

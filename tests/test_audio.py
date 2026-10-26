import shutil
import struct
import subprocess

import numpy as np
import pytest

from metalesionlab.audio import duration_s, pad_silence, pcm16_wav, to_wav16k, wav_format

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not on PATH")


def tone(seconds: float, rate: int, channels: int = 1) -> bytes:
    t = np.arange(int(seconds * rate)) / rate
    wave = (0.3 * 32767 * np.sin(2 * np.pi * 440 * t)).astype("<i2")
    return pcm16_wav(np.repeat(wave, channels).tobytes(), rate, channels)


def test_duration_and_format_of_a_plain_wav():
    wav = tone(1.5, 16000)
    assert wav_format(wav) == (1, 1, 16000, 16, 48000)
    assert duration_s(wav) == pytest.approx(1.5)


def test_streamed_wav_with_placeholder_size_uses_bytes_present():
    wav = bytearray(tone(1.0, 16000))
    wav[40:44] = struct.pack("<I", 0xFFFFFFFF)
    assert duration_s(bytes(wav)) == pytest.approx(1.0)


def test_ready_wav_passes_through_without_ffmpeg():
    wav = tone(0.5, 16000)
    assert to_wav16k(wav, ".wav") is wav


def test_pad_silence_adds_both_ends():
    wav = pad_silence(tone(1.0, 16000), 0.5)
    assert duration_s(wav) == pytest.approx(2.0)


def test_not_a_wav_raises():
    with pytest.raises(ValueError):
        duration_s(b"not audio at all")


@needs_ffmpeg
def test_stereo_44k_wav_is_converted():
    out = to_wav16k(tone(1.0, 44100, channels=2), "wav")
    assert wav_format(out)[:4] == (1, 1, 16000, 16)
    assert duration_s(out) == pytest.approx(1.0, abs=0.01)


@needs_ffmpeg
@pytest.mark.parametrize("ext,codec", [("webm", "libopus"), ("ogg", "libopus"), ("m4a", "aac")])
def test_browser_formats_are_converted(tmp_path, ext, codec):
    src, dst = tmp_path / "in.wav", tmp_path / f"rec.{ext}"
    src.write_bytes(tone(2.0, 48000))
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(src), "-c:a", codec, str(dst)], check=True)
    out = to_wav16k(dst.read_bytes(), f"audio/{ext};codecs=x")
    assert wav_format(out)[:4] == (1, 1, 16000, 16)
    assert duration_s(out) == pytest.approx(2.0, abs=0.1)


@needs_ffmpeg
def test_garbage_input_reports_ffmpeg_error():
    with pytest.raises(ValueError, match="ffmpeg could not convert"):
        to_wav16k(b"\x00" * 1000, ".webm")

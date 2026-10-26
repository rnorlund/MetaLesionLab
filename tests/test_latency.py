"""Speech onset (naming latency) on generated tones, noise and silence."""
import numpy as np
import pytest

from metalesionlab import audio

R = audio.SAMPLE_RATE


def wav(x):
    return audio.pcm16_wav((np.clip(x, -1, 1) * 32767).round().astype("<i2").tobytes())


def tone(seconds, freq=220.0, amp=0.3, attack=0.0):
    t = np.arange(int(seconds * R)) / R
    y = amp * np.sin(2 * np.pi * freq * t)
    return y * np.minimum(1.0, t / attack) if attack else y


def silence(seconds):
    return np.zeros(int(round(seconds * R)))


@pytest.mark.parametrize("latency", [0.2, 0.5, 1.0, 2.0])
@pytest.mark.parametrize("noise", [0.0, 0.001, 0.003])
def test_onset_within_10_ms(latency, noise):
    x = np.concatenate([silence(0.3 + latency), tone(0.6), silence(0.4)])
    x = x + noise * np.random.default_rng(0).standard_normal(len(x))
    t = audio.detect_speech(wav(x), search_from_s=0.3)
    assert t.onset_s - 0.3 == pytest.approx(latency, abs=0.010)
    assert t.offset_s - t.onset_s == pytest.approx(0.6, abs=0.015)
    assert not t.speech_at_start


def test_soft_attack_is_caught_early():
    x = np.concatenate([silence(1.3), tone(0.6, attack=0.08), silence(0.3)])
    t = audio.detect_speech(wav(x), search_from_s=0.3)
    assert 1.3 <= t.onset_s <= 1.3 + 0.03


def test_noise_floor_comes_from_the_lead_in():
    rng = np.random.default_rng(1)
    x = np.concatenate([silence(1.0), tone(0.5), silence(0.3)]) + 0.01 * rng.standard_normal(int(1.8 * R))
    t = audio.detect_speech(wav(x), search_from_s=0.3)
    assert t.noise_dbfs == pytest.approx(-40, abs=1.5) and t.threshold_dbfs == pytest.approx(t.noise_dbfs + 12)
    assert t.onset_s == pytest.approx(1.0, abs=0.01)


def test_clicks_and_silence_are_not_speech():
    x = silence(2.0)
    x[int(1.0 * R):int(1.02 * R)] = 0.5  # a 20 ms click, e.g. a key press
    t = audio.detect_speech(wav(x), search_from_s=0.3)
    assert t.onset_s is None and t.offset_s is None
    assert audio.detect_speech(wav(silence(1.0)), 0.3).onset_s is None


def test_a_short_dip_does_not_split_a_word_but_a_pause_ends_it():
    x = np.concatenate([silence(0.5), tone(0.2), silence(0.02), tone(0.2), silence(0.6), tone(0.3), silence(0.2)])
    t = audio.detect_speech(wav(x), search_from_s=0.3)
    assert t.onset_s == pytest.approx(0.5, abs=0.01)
    assert t.offset_s == pytest.approx(0.5 + 0.42 + 0.6 + 0.3, abs=0.015)  # the last stretch ends the response


def test_speech_before_the_picture_is_ignored_and_ongoing_speech_is_flagged():
    early = np.concatenate([tone(0.1, amp=0.2), silence(0.5), tone(0.4), silence(0.2)])
    t = audio.detect_speech(wav(early), search_from_s=0.3)
    assert t.onset_s == pytest.approx(0.6, abs=0.01) and not t.speech_at_start
    ongoing = np.concatenate([silence(0.15), tone(1.0), silence(0.3)])
    assert audio.detect_speech(wav(ongoing), search_from_s=0.3).speech_at_start


def test_trim_and_samples_round_trip():
    x = np.concatenate([silence(0.5), tone(0.5)])
    clip = audio.trim(wav(x), 0.25, 0.75)
    assert audio.duration_s(clip) == pytest.approx(0.5, abs=1e-3)
    y, rate = audio.samples(clip)
    assert rate == R and np.abs(y[:R // 5]).max() == 0 and np.abs(y[-R // 5:]).max() > 0.2
    assert audio.duration_s(audio.trim(wav(x), 0.9, None)) == pytest.approx(0.1, abs=1e-3)

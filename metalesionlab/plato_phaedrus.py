"""Seven meanings: what writing keeps of a spoken sentence, and what it loses.

In the Phaedrus (276a) the written word is "properly no more than an image" of the living word. A model that
learns only from text lives with the image. "I never said she stole my money" has seven meanings, one for each
word a speaker can stress; written down, the seven are one string.

The experiment (pre-registered in docs/plato_phaedrus_plan.md) speaks the sentence with each word stressed, in
several synthetic voices, and asks:

1. The shadow. Does Meta's Voice Transcribe write the seven versions down the same way?
2. Text only. From the transcript, can Muse Spark tell which of the seven meanings was meant? And from the
   sentence with the stressed word in CAPITALS or *italics*, writing that keeps the stress?
3. The living word. Can a plain prosody reader (pitch, loudness and duration per word) find the stressed word
   in the sound?

This module holds what the experiment, its scripts and the web page share: the sentence and its seven meanings,
Spark's fixed prompt, transcript checks, the prosody reader and its word aligner. It needs numpy only, so the
web app (no torch) can run the reader on a visitor's recording. Data lives outside the repository in
$PLATO_PHAEDRUS_DIR.
"""
from __future__ import annotations

import os
import random
import re
import string
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PHAEDRUS_DIR = Path(os.environ.get("PLATO_PHAEDRUS_DIR",
                                   "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/phaedrus"))
BUDGET_USD = 3.0     # this task's own cap
SHARED_STOP = 70.0   # no new paid call once the shared ledger reaches this
SEED = 20261028

SENTENCE = "I never said she stole my money."
WORDS = ("I", "never", "said", "she", "stole", "my", "money")
N = len(WORDS)
CHANCE = 1 / N


@dataclass(frozen=True)
class Meaning:
    word: str      # the stressed word
    gloss: str     # what the stress adds, as the page says it
    option: str    # the same meaning as a multiple-choice option for Spark (doesn't say which word is stressed)


# Written before any model saw them. Each option says what the speaker means without naming which word carries
# the stress, so Spark can only pick one from what the text tells it.
MEANINGS = (
    Meaning("I", "Someone else said it, not me.",
            "Someone else said she stole the money; the speaker didn't."),
    Meaning("never", "I didn't say it at all.",
            "The speaker flatly denies ever having said it."),
    Meaning("said", "I implied it, but I didn't say it.",
            "The speaker may have hinted it, but didn't say it in words."),
    Meaning("she", "Someone else stole it, not her.",
            "Someone stole the money, but it wasn't her."),
    Meaning("stole", "She took it, but she didn't steal it; she borrowed it.",
            "She took the money, but didn't steal it (she borrowed it, say)."),
    Meaning("my", "She stole someone else's money, not mine.",
            "She stole money, but someone else's, not the speaker's."),
    Meaning("money", "She stole something of mine, but not money.",
            "She stole something of the speaker's, but not money."),
)
LETTERS = "ABCDEFG"

PROMPT = """Someone said one sentence out loud and stressed one word to give it a particular meaning. Here is the sentence, written down:

{text}

Which meaning did the speaker intend?
{options}

Answer with the letter only."""


def stressed_text(i: int, style: str) -> str:
    """The sentence with word i marked the way writing can mark stress: "caps" (SHE) or "italics" (*she*)."""
    words = list(SENTENCE.rstrip(".").split())
    w = words[i]
    words[i] = w.upper() if style == "caps" else f"*{w}*"
    return " ".join(words) + "."


def option_order(rng: random.Random) -> list[int]:
    """A shuffled order of the seven meanings (indices into MEANINGS)."""
    order = list(range(N))
    rng.shuffle(order)
    return order


def build_prompt(text: str, order: list[int]) -> str:
    opts = "\n".join(f"{LETTERS[k]}. {MEANINGS[m].option}" for k, m in enumerate(order))
    return PROMPT.format(text=text, options=opts)


def parse_choice(answer: str, order: list[int]) -> int | None:
    """The meaning (index into MEANINGS) a reply picks: its first standalone letter A-G, else None."""
    m = re.search(r"\b([A-G])\b", (answer or "").strip().upper())
    return order[LETTERS.index(m.group(1))] if m else None


# --- the shadow: what the transcript keeps -------------------------------------------------------------------

def words_of(transcript: str) -> list[str]:
    """Lower-case words without punctuation: what's left when casing and punctuation are set aside."""
    t = (transcript or "").lower().replace("’", "'")
    return re.findall(r"[a-z']+", t)


def is_the_sentence(transcript: str, min_match: int = 5) -> bool:
    """Whether a transcript is (close to) the sentence: at least min_match of its seven words, in order."""
    got = words_of(transcript)
    want = [w.lower() for w in WORDS]
    # longest common subsequence, tiny
    table = [[0] * (len(want) + 1) for _ in range(len(got) + 1)]
    for a in range(len(got)):
        for b in range(len(want)):
            table[a + 1][b + 1] = table[a][b] + 1 if got[a] == want[b] else max(table[a][b + 1], table[a + 1][b])
    return table[-1][-1] >= min_match and len(got) <= N + 3


def leaks(transcripts: list[str]) -> dict:
    """How a set of transcripts of the same sentence differ: in words, or only in casing and punctuation (a leak:
    writing that kept a trace of the stress)."""
    exact = set(transcripts)
    by_words = {" ".join(words_of(t)) for t in transcripts}
    marks = {t: "".join(c for c in t if c in string.punctuation or c in "…—–“”‘’") for t in transcripts}
    # a word of the sentence written in capitals (SHE, NEVER); "I" is always a capital, and "II" is a doubled "I"
    stressable = {w.lower() for w in WORDS if w != "I"}
    caps = {t: [w for w in re.findall(r"[A-Za-z']+", t) if w.isupper() and w.lower() in stressable] for t in transcripts}
    return {"identical": len(exact) == 1, "same_words": len(by_words) == 1, "n_distinct": len(exact),
            "n_distinct_words": len(by_words), "punctuation": sorted(set(marks.values())),
            "capitalised_words": sorted({w for v in caps.values() for w in v})}


# --- the living word: a plain prosody reader -------------------------------------------------------------------
#
# Steps, all fixed before the main run:
#   1. Speech span: frames within 40 dB of the loudest and 10 dB above the quietest tenth (or 25 dB under the
#      loudest, whichever is lower); the span runs from the first to the last such frame.
#   2. Word timing: dynamic time warping of the clip's MFCCs (12 coefficients, cepstral mean removed) onto
#      template recordings of the neutral sentence whose word boundaries are known; each template's boundaries
#      are carried through its warping path and the median across templates is taken.
#   3. Per word: pitch peak (90th percentile of voiced F0, in semitones re the clip's median F0), loudness peak
#      (90th percentile of frame level in dB, re the clip's median speech level) and duration (the word's share of
#      the speech span, divided by its share in the templates, as a log ratio).
#   4. Each cue is z-scored across the seven words; the expected z-profile of a neutral reading (the templates')
#      is subtracted from pitch and loudness, so the sentence's own declining melody isn't read as stress.
#      Prominence = pitch + loudness + duration, equal weights. The most prominent word is the reader's guess.

SR = 16000
HOP_S = 0.010
F0_MIN, F0_MAX = 60.0, 500.0
VOICING = 0.45          # normalized autocorrelation peak a frame needs to count as voiced
SPAN_RANGE_DB = 40.0
SPAN_FLOOR_DB = 10.0
SD_FLOOR = 0.25         # a cue whose seven values barely differ adds little: z uses max(SD, this x its scale)
CUES = ("pitch", "loud", "dur")


def frame_signal(x: np.ndarray, win: int, hop: int) -> np.ndarray:
    if len(x) < win:
        x = np.pad(x, (0, win - len(x)))
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    return x[idx]


def level_db(x: np.ndarray, sr: int = SR, win_s: float = 0.030, hop_s: float = HOP_S) -> np.ndarray:
    """Frame level in dBFS (RMS of a 30 ms window every 10 ms; frame k is centred at k * hop + win / 2)."""
    f = frame_signal(x.astype(np.float64), int(win_s * sr), int(hop_s * sr))
    return 20 * np.log10(np.sqrt(np.mean(f ** 2, axis=1)) + 1e-6)


def pitch_track(x: np.ndarray, sr: int = SR, hop_s: float = HOP_S, win_s: float = 0.045) -> np.ndarray:
    """F0 in Hz per frame (NaN when unvoiced), by normalized autocorrelation with the window's own autocorrelation
    divided out (Boersma 1993), then octave jumps folded back toward the clip's median and a 5-frame median
    filter. Frames are aligned with level_db's (same hop, centred)."""
    win, hop = int(win_s * sr), int(hop_s * sr)
    pad = (win - int(0.030 * sr)) // 2
    xp = np.pad(x.astype(np.float64), (pad, pad))
    f = frame_signal(xp, win, hop)
    f = f - f.mean(axis=1, keepdims=True)
    w = np.hanning(win)
    nfft = 1 << int(np.ceil(np.log2(2 * win)))
    spec = np.fft.rfft(f * w, nfft)
    ac = np.fft.irfft(np.abs(spec) ** 2, nfft)[:, :win]
    wac = np.fft.irfft(np.abs(np.fft.rfft(w, nfft)) ** 2, nfft)[:win]
    ac = ac / (ac[:, :1] + 1e-12) / (wac / wac[0] + 1e-12)
    lo, hi = int(sr / F0_MAX), min(int(sr / F0_MIN), win // 2)
    seg = ac[:, lo:hi]
    # the shortest lag whose peak is within 10% of the best: a periodic sound peaks at every multiple of its period,
    # and with the window divided out the peak at twice the period can edge out the true one (an octave too low)
    best = seg.max(axis=1, keepdims=True)
    peaks = np.zeros_like(seg, dtype=bool)
    peaks[:, 1:-1] = (seg[:, 1:-1] > seg[:, :-2]) & (seg[:, 1:-1] >= seg[:, 2:])
    ok = peaks & (seg >= 0.9 * best)
    k = np.where(ok.any(axis=1), np.argmax(ok, axis=1), np.argmax(seg, axis=1))
    peak = seg[np.arange(len(seg)), k]
    # parabolic interpolation around the peak
    kk = np.clip(k, 1, seg.shape[1] - 2)
    a, b, c = seg[np.arange(len(seg)), kk - 1], seg[np.arange(len(seg)), kk], seg[np.arange(len(seg)), kk + 1]
    denom = a - 2 * b + c
    safe = np.where(np.abs(denom) > 1e-9, denom, 1.0)
    shift = np.where(np.abs(denom) > 1e-9, 0.5 * (a - c) / safe, 0.0)
    lag = lo + kk + np.clip(shift, -1, 1)
    f0 = sr / lag
    db = level_db(x, sr, 0.030, hop_s)
    n = min(len(f0), len(db))
    f0, peak, db = f0[:n], peak[:n], db[:n]
    loud_enough = db > max(np.percentile(db, 95) - 35.0, -60.0)
    f0 = np.where((peak > VOICING) & loud_enough, f0, np.nan)
    voiced = ~np.isnan(f0)
    if voiced.sum() >= 5:
        # octave jumps: a frame an octave away from the voiced frames within 70 ms of it is folded back. A stressed
        # word's pitch rises smoothly, so its neighbours rise with it and it isn't folded.
        idx = np.flatnonzero(voiced)
        local = np.array([np.median(f0[idx[(idx >= i - 7) & (idx <= i + 7)]]) for i in idx])
        r = f0[idx] / local
        f0[idx] = np.where(r > 1.7, f0[idx] / 2, np.where(r < 0.59, f0[idx] * 2, f0[idx]))
        out = f0.copy()
        for i in idx:  # median of the voiced frames among the 5 around each voiced frame
            out[i] = np.nanmedian(f0[max(0, i - 2):i + 3])
        f0 = out
    return f0


def speech_span(db: np.ndarray) -> tuple[int, int]:
    """[first, last + 1) frames of speech (see step 1 above)."""
    if not len(db):
        return 0, 0
    floor = np.percentile(db, 10)
    # 10 dB over the quiet tenth, but never more than 25 dB under the peak (a clip that is nearly all speech has
    # no quiet tenth), and never less than 40 dB under it
    thr = max(db.max() - SPAN_RANGE_DB, min(floor + SPAN_FLOOR_DB, db.max() - 25.0))
    on = np.flatnonzero(db >= thr)
    if not len(on):
        return 0, len(db)
    return int(on[0]), int(on[-1]) + 1


_MEL_CACHE: dict = {}


def mfcc(x: np.ndarray, sr: int = SR, hop_s: float = HOP_S, n_mels: int = 26, n_ceps: int = 12) -> np.ndarray:
    """MFCCs 1-12 per frame (25 ms Hamming windows, 10 ms hop, pre-emphasis 0.97), cepstral mean removed later."""
    y = np.append(x[0], x[1:] - 0.97 * x[:-1]).astype(np.float64)
    win, hop = int(0.025 * sr), int(hop_s * sr)
    pad = (int(0.030 * sr) - win) // 2
    f = frame_signal(np.pad(y, (pad, pad)), win, hop) * np.hamming(win)
    nfft = 512
    power = np.abs(np.fft.rfft(f, nfft)) ** 2 / nfft
    key = (sr, nfft, n_mels, n_ceps)
    if key not in _MEL_CACHE:
        mel = lambda hz: 2595 * np.log10(1 + hz / 700)  # noqa: E731
        hz = lambda m: 700 * (10 ** (m / 2595) - 1)  # noqa: E731
        pts = hz(np.linspace(mel(60), mel(sr / 2 - 200), n_mels + 2))
        bins = np.floor((nfft + 1) * pts / sr).astype(int)
        fb = np.zeros((n_mels, nfft // 2 + 1))
        for m in range(1, n_mels + 1):
            l, c, r = bins[m - 1], bins[m], bins[m + 1]
            if c > l:
                fb[m - 1, l:c] = (np.arange(l, c) - l) / (c - l)
            if r > c:
                fb[m - 1, c:r] = (r - np.arange(c, r)) / (r - c)
        k = np.arange(n_mels)
        dct = np.cos(np.pi / n_mels * (k[None, :] + 0.5) * np.arange(1, n_ceps + 1)[:, None])
        _MEL_CACHE[key] = (fb, dct)
    fb, dct = _MEL_CACHE[key]
    logmel = np.log(power @ fb.T + 1e-10)
    return logmel @ dct.T


def dtw_path(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """The minimum-cost warping path between feature sequences a (n x d) and b (m x d), as (i, j) pairs,
    with steps (1,0), (0,1) and (1,1); both ends are tied."""
    n, m = len(a), len(b)
    cost = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(axis=2))
    acc = np.full((n + 1, m + 1), np.inf)
    acc[0, 0] = 0.0
    for i in range(1, n + 1):
        row = cost[i - 1]
        prev = acc[i - 1]
        best = np.minimum(prev[1:], prev[:-1])  # entering column j from above or from the diagonal
        # then moving right within the row: cur[j] = min over k <= j of best[k-1] + row[k-1] + ... + row[j-1],
        # which is a running minimum over prefix sums
        s = np.concatenate([[0.0], np.cumsum(row)])
        acc[i, 1:] = s[1:] + np.minimum.accumulate(best - s[:-1])
    i, j, path = n, m, []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        steps = (acc[i - 1, j - 1], acc[i - 1, j], acc[i, j - 1])
        s = int(np.argmin(steps))
        if s == 0:
            i, j = i - 1, j - 1
        elif s == 1:
            i -= 1
        else:
            j -= 1
    return np.array(path[::-1])


@dataclass
class Template:
    """A neutral reading of the sentence with known word boundaries (seconds from its speech onset)."""
    name: str
    feats: np.ndarray            # MFCC frames of the speech span, cepstral mean removed
    bounds: np.ndarray           # 8 boundaries, in frames from the span start (word k is bounds[k]..bounds[k+1])
    z_pitch: np.ndarray | None = None
    z_loud: np.ndarray | None = None

    def to_json(self) -> dict:
        return {"name": self.name, "feats": np.round(self.feats, 3).tolist(), "bounds": self.bounds.tolist(),
                "z_pitch": None if self.z_pitch is None else np.round(self.z_pitch, 4).tolist(),
                "z_loud": None if self.z_loud is None else np.round(self.z_loud, 4).tolist()}

    @classmethod
    def from_json(cls, d: dict) -> "Template":
        return cls(d["name"], np.asarray(d["feats"], dtype=np.float64), np.asarray(d["bounds"], dtype=np.float64),
                   None if d.get("z_pitch") is None else np.asarray(d["z_pitch"]),
                   None if d.get("z_loud") is None else np.asarray(d["z_loud"]))


def _span_feats(x: np.ndarray, sr: int = SR) -> tuple[np.ndarray, int, int, np.ndarray]:
    db = level_db(x, sr)
    a, b = speech_span(db)
    c = mfcc(x, sr)
    n = min(len(c), len(db))
    c = c[:n]
    feats = c[a:b] - c[a:b].mean(axis=0, keepdims=True)
    return feats, a, b, db


def make_template(name: str, x: np.ndarray, word_times: list[tuple[float, float]], sr: int = SR) -> Template:
    """A template from a neutral reading and its known word times (seconds from the clip start)."""
    feats, a, b, _ = _span_feats(x, sr)
    edges = [word_times[0][0]] + [(word_times[k][1] + word_times[k + 1][0]) / 2 for k in range(N - 1)] + [word_times[-1][1]]
    bounds = np.clip(np.array(edges) / HOP_S - a, 0, b - a)
    t = Template(name, feats, bounds)
    feat = word_features(x, bounds_s=[(e + a) * HOP_S for e in bounds], sr=sr)
    t.z_pitch, t.z_loud = _z(feat["pitch"]), _z(feat["loud"])
    return t


def align(x: np.ndarray, templates: list[Template], sr: int = SR, exclude: str | None = None) -> list[float]:
    """The 8 word boundaries of a reading of the sentence (seconds from the clip start), by DTW onto each template
    and the median across templates."""
    feats, a, b, _ = _span_feats(x, sr)
    if len(feats) < 2 * N:
        raise ValueError("too short to be the sentence")
    found = []
    for t in templates:
        if exclude and t.name.startswith(exclude):
            continue
        path = dtw_path(feats, t.feats)
        mapped = []
        for edge in t.bounds:
            j = int(round(min(edge, len(t.feats) - 1)))
            hits = path[path[:, 1] == j, 0]
            mapped.append(float(np.median(hits)) if len(hits) else float(edge))
        found.append(mapped)
    if not found:
        raise ValueError("no templates")
    edges = np.median(np.array(found), axis=0)
    edges = np.maximum.accumulate(edges)
    return [float((e + a) * HOP_S) for e in edges]


def word_features(x: np.ndarray, bounds_s: list[float], sr: int = SR, f0: np.ndarray | None = None,
                  db: np.ndarray | None = None) -> dict:
    """Per word: pitch peak (semitones re the clip's median F0), loudness peak (dB re the median speech level),
    duration (s), with the pitch and level tracks."""
    f0 = pitch_track(x, sr) if f0 is None else f0
    db = level_db(x, sr) if db is None else db
    n = min(len(f0), len(db))
    f0, db = f0[:n], db[:n]
    a, b = speech_span(db)
    voiced = ~np.isnan(f0)
    med_f0 = float(np.median(f0[voiced])) if voiced.any() else float("nan")
    med_db = float(np.median(db[a:b])) if b > a else float(np.median(db))
    pitch, loud, dur = [], [], []
    for k in range(N):
        i0 = int(np.floor(bounds_s[k] / HOP_S))
        i1 = max(i0 + 1, int(np.ceil(bounds_s[k + 1] / HOP_S)))
        seg_f0 = f0[i0:i1]
        seg_f0 = seg_f0[~np.isnan(seg_f0)]
        pitch.append(12 * np.log2(np.percentile(seg_f0, 90) / med_f0) if len(seg_f0) and med_f0 > 0 else np.nan)
        seg_db = db[i0:i1]
        loud.append(float(np.percentile(seg_db, 90) - med_db) if len(seg_db) else np.nan)
        dur.append(max(bounds_s[k + 1] - bounds_s[k], HOP_S))
    pitch = np.array(pitch, dtype=float)
    if np.isnan(pitch).all():
        pitch = np.zeros(N)
    else:
        pitch = np.where(np.isnan(pitch), np.nanmin(pitch), pitch)
    loud = np.nan_to_num(np.array(loud, dtype=float), nan=float(np.nanmin(loud)) if not np.isnan(loud).all() else 0.0)
    return {"pitch": pitch, "loud": loud, "dur": np.array(dur), "f0": f0, "db": db, "span": (a, b),
            "median_f0": med_f0, "median_db": med_db}


def _z(v: np.ndarray, scale: float = 1.0) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    sd = max(float(v.std()), SD_FLOOR * scale)
    return (v - v.mean()) / sd


# Typical spread of each cue across the seven words of a neutral reading, for the SD floor: semitones, dB, log ratio.
CUE_SCALE = {"pitch": 2.0, "loud": 3.0, "dur": 0.2}


def prominence(feat: dict, templates: list[Template], baseline: bool = True) -> dict:
    """Each word's z-scored cues and their sum (see step 4 above)."""
    share_t = np.mean([np.diff(t.bounds) / (t.bounds[-1] - t.bounds[0]) for t in templates], axis=0)
    share = feat["dur"] / feat["dur"].sum()
    cues = {"pitch": _z(feat["pitch"], CUE_SCALE["pitch"]), "loud": _z(feat["loud"], CUE_SCALE["loud"]),
            "dur": _z(np.log(share / share_t), CUE_SCALE["dur"])}
    if baseline:
        zp = np.mean([t.z_pitch for t in templates if t.z_pitch is not None], axis=0)
        zl = np.mean([t.z_loud for t in templates if t.z_loud is not None], axis=0)
        cues["pitch"] = cues["pitch"] - zp
        cues["loud"] = cues["loud"] - zl
    total = cues["pitch"] + cues["loud"] + cues["dur"]
    return {**cues, "total": total, "guess": int(np.argmax(total))}


def read_stress(x: np.ndarray, templates: list[Template], sr: int = SR, bounds_s: list[float] | None = None,
                exclude: str | None = None) -> dict:
    """The prosody reader on one clip: word boundaries (aligned unless given), cues, prominence and its guess."""
    if sr != SR:
        raise ValueError("resample to 16 kHz first")
    bounds = bounds_s if bounds_s is not None else align(x, templates, sr, exclude=exclude)
    feat = word_features(x, bounds, sr)
    prom = prominence(feat, templates)
    raw = prominence(feat, templates, baseline=False)
    return {"bounds": bounds, "features": feat, "prominence": prom, "raw": raw, "guess": prom["guess"]}


def contour(result: dict, max_points: int = 240) -> dict:
    """What the page draws: pitch (semitones re median, None when unvoiced) and level (dB re median) over the
    speech span, decimated, with word boundaries in the same time base and each word's prominence."""
    feat = result["features"]
    a, b = feat["span"]
    a = max(0, min(a, int(result["bounds"][0] / HOP_S)) - 5)
    b = min(len(feat["db"]), max(b, int(np.ceil(result["bounds"][-1] / HOP_S))) + 5)
    step = max(1, int(np.ceil((b - a) / max_points)))
    idx = np.arange(a, b, step)
    f0 = feat["f0"][idx]
    st = np.where(np.isnan(f0), np.nan, 12 * np.log2(np.where(np.isnan(f0), 1, f0) / feat["median_f0"]))
    prom = result["prominence"]
    return {"t": [round(float(i * HOP_S), 3) for i in idx],
            "pitch": [None if np.isnan(v) else round(float(v), 2) for v in st],
            "level": [round(float(v), 1) for v in feat["db"][idx] - feat["median_db"]],
            "bounds": [round(float(t), 3) for t in result["bounds"]],
            "words": [{"word": WORDS[k], "pitch": round(float(prom["pitch"][k]), 2), "loud": round(float(prom["loud"][k]), 2),
                       "dur": round(float(prom["dur"][k]), 2), "total": round(float(prom["total"][k]), 2)}
                      for k in range(N)],
            "guess": int(result["guess"])}


# --- statistics ------------------------------------------------------------------------------------------------

def exact_ci(k: int, n: int, level: float = 0.95) -> list[float]:
    """Clopper-Pearson interval for k successes in n."""
    from scipy.stats import beta
    a = (1 - level) / 2
    lo = 0.0 if k == 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - a, k + 1, n - k))
    return [lo, hi]


def binom_p_greater(k: int, n: int, p: float = CHANCE) -> float:
    """One-sided exact binomial p-value for at least k of n at chance p."""
    from scipy.stats import binom
    return float(binom.sf(k - 1, n, p))


def binom_p_two_sided(k: int, n: int, p: float = CHANCE) -> float:
    from scipy.stats import binomtest
    return float(binomtest(k, n, p).pvalue)


def cluster_bootstrap(correct: np.ndarray, clusters: list[str], reps: int = 10000, seed: int = SEED) -> list[float]:
    """95% interval of accuracy, resampling whole voices (items within a voice share a transcript or a voice)."""
    correct = np.asarray(correct, dtype=float)
    keys = sorted(set(clusters))
    groups = [correct[[c == k for c in clusters]] for k in keys]
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for r in range(reps):
        pick = rng.integers(0, len(groups), len(groups))
        allv = np.concatenate([groups[i] for i in pick])
        out[r] = allv.mean()
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]

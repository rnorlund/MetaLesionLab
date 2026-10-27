"""Naming Assessment: timed picture naming with latency, for clinicians, researchers and the public.

This module holds the parts that don't need the web app:

first_complete_response
  The PNT scores a person's first complete attempt (Roach et al., 1996). A transcript such as
  "dog, no, cat" or "c-, cat" is split into attempts, and the first one that is complete is
  coded. Splitting happens only when there is a sign of a new attempt: a correction word ("no",
  "I mean", "digo", "je veux dire") or a run of short pieces ("tat, cat"). English, Spanish, French
  and Portuguese only; other languages are coded whole. A description such as "it's round, you
  eat it" stays whole. Comments ("let me think"), refusals ("I don't know"), frames ("it's a",
  "es un") and fragments (a lone non-word that starts the next attempt, or of one or two letters)
  are not attempts.

summarize
  Session measures: accuracy on scored (non-practice) items, counts by error type, median and
  interquartile range of naming latency for correct responses, and items that reached the time
  limit. Percentiles use linear interpolation (numpy's default), the same as the browser.

parallel_forms
  Splits a set into two halves matched on word frequency (Zipf) and length in phonemes: items are
  sorted on both measures and dealt out in pairs so each pair goes the way that keeps the halves'
  totals closest, then single items are swapped between halves while that brings the halves'
  means (and, at half weight, their spreads) closer.

norms_summary / receipts
  The public test's reference range. A scored response comes back with a signed receipt; a
  volunteer who opts in sends the receipts, and the server recomputes accuracy and median latency
  from them, so a summary can't be typed in by hand. Only the summary is kept.

Everything here measures and reports. None of it diagnoses, predicts or advises.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import unicodedata
from collections import Counter

import numpy as np
from wordfreq import zipf_frequency

from metalesionlab.naming_errors import REFUSAL_KEYS, _strip_accents, is_word, phonemes, tokens

CODES = ("Correct", "Semantic", "Formal", "Mixed", "Nonword", "Neologism", "Unrelated", "Description",
         "Visual", "NoResponse")
DEFAULT_TIME_LIMIT_S = 20.0  # per item, as in the PNT
NORMS_MIN_N = 10  # a reference range is shown only from this many contributors

# --- first complete response ------------------------------------------------------------

CORRECTIONS = {
    "en": ("i mean", "no wait", "sorry", "wait", "actually", "not that", "oops", "no"),
    "es": ("quiero decir", "mejor dicho", "o sea", "perdón", "perdon", "espera", "digo", "no"),
    "fr": ("je veux dire", "pardon", "plutôt", "plutot", "attends", "non"),
    "pt": ("quero dizer", "quer dizer", "desculpa", "espera", "digo", "não", "nao"),
}
SPLIT_LANGS = {"en", "es", "fr", "pt"}  # space-separated words and checked correction words; others stay whole
COMMENTS = {
    "en": {"let me think", "i know this", "i know it", "i know", "what is it", "what is that", "whats it called",
           "what do you call it", "what is it called", "hmm", "oh", "okay", "ok", "well", "yes", "yeah", "hold on"},
    "es": {"dejame pensar", "a ver", "lo se", "ya se", "como se llama", "que es", "que es eso", "pues", "bueno",
           "si", "vale", "espera"},
    "fr": {"voyons", "je sais", "alors", "bon", "oui", "attends", "c est quoi", "cest quoi"},
    "pt": {"deixa eu pensar", "deixa ver", "eu sei", "sei", "bom", "entao", "sim", "espera"},
}
FRAMES = {
    "en": re.compile(r"^(?:i think |i guess |maybe )?(?:it'?s|it is|that'?s|that is|this is|this'?s|looks like|"
                     r"it looks like)(?: an?| the)?\b\s*"),
    "es": re.compile(r"^(?:creo que |pues )?(?:es|eso es|esto es|parece)(?: una?| el| la| unos| unas)?\b\s*"),
    "fr": re.compile(r"^(?:je pense que |je crois que )?(?:c'est|c est|ce sont|voilà|voila)(?: une?| le| la| les| des)?\b\s*"),
    "pt": re.compile(r"^(?:acho que )?(?:é|isso é|isto é|parece)(?: uma?| o| a)?\b\s*"),
}
_SPLIT = re.compile(r"[.,;:!?¿¡…]+|\s[-–—]+\s|\.\.\.")


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").lower().replace("’", "'")


def _plain(words: list[str]) -> str:
    return _strip_accents(" ".join(words)).replace("'", "")


def _attempt_words(piece: str, lang: str) -> list[str]:
    text = " ".join(tokens(piece))  # fillers out first, so "um, it's a cat" loses its frame too
    frame = FRAMES.get(lang)
    return tokens(frame.sub("", text, count=1)) if frame else tokens(text)


def first_complete_response(response: str, lang: str, target: str = "") -> dict:
    """{"scored": text to code, "attempts": [each attempt], "split": bool}. See the module notes."""
    if lang not in SPLIT_LANGS:  # e.g. Chinese (no spaces) and Hindi: coded whole, as the Scorer does
        return {"scored": (response or "").strip(), "attempts": [(response or "").strip()] if (response or "").strip() else [],
                "split": False}
    text = _norm(response)
    markers = CORRECTIONS.get(lang, ())
    marker_re = re.compile(r"\b(?:" + "|".join(re.escape(m) for m in markers) + r")\b") if markers else None
    comments = COMMENTS.get(lang, set())
    attempts: list[list[str]] = []
    corrected = False
    for piece in _SPLIT.split(text):
        words = tokens(piece)
        if not words or _plain(words) in REFUSAL_KEYS or _plain(words) in comments:
            continue
        parts = [piece]
        if marker_re and marker_re.search(piece):
            parts = marker_re.split(piece)
            corrected = True
        for part in parts:
            words = _attempt_words(part, lang)
            if words and _plain(words) not in REFUSAL_KEYS and _plain(words) not in comments:
                attempts.append(words)
    whole = [w for a in attempts for w in a]
    if not attempts:
        return {"scored": "" if corrected or not tokens(text) else " ".join(tokens(text)), "attempts": [], "split": False}
    if not corrected and (len(attempts) == 1 or any(len(a) >= 3 for a in attempts)):
        return {"scored": " ".join(whole), "attempts": [" ".join(whole)], "split": False}
    complete = [a for k, a in enumerate(attempts) if not _is_fragment(a, attempts[k + 1:], target, lang)]
    chosen = complete[0] if complete else attempts[-1]
    return {"scored": " ".join(chosen), "attempts": [" ".join(a) for a in attempts], "split": len(attempts) > 1}


def _is_fragment(attempt: list[str], later: list[list[str]], target: str, lang: str) -> bool:
    if len(attempt) != 1:
        return False
    w = attempt[0]
    if is_word(w, lang) and len(w) > 2:
        return False
    nxt = later[0][0] if later else ""
    return len(w) <= 2 or (bool(nxt) and nxt.startswith(w) and nxt != w) or (bool(target) and target.lower().startswith(w))


# --- session summary ----------------------------------------------------------------------

def percentile(values: list[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if values else None


def final_code(item: dict) -> str | None:
    return item.get("reviewer") or item.get("code")


def final_latency(item: dict) -> float | None:
    v = item.get("reviewer_latency_ms")
    return item.get("latency_ms") if v is None or v == "" else float(v)


def summarize(items: list[dict]) -> dict:
    """Measures for one session; items carry code/reviewer, latency_ms, timeout and practice."""
    scored = [it for it in items if not it.get("practice") and final_code(it)]
    codes = Counter(final_code(it) for it in scored)
    n = len(scored)
    correct = codes.get("Correct", 0)
    lat = [final_latency(it) for it in scored if final_code(it) == "Correct" and final_latency(it) is not None]
    return {
        "n": n, "correct": correct, "accuracy_pct": round(100 * correct / n, 1) if n else None,
        "counts": {c: codes[c] for c in CODES if codes.get(c)},
        "latency_n": len(lat),
        "latency_median_ms": _round(percentile(lat, 50)), "latency_q1_ms": _round(percentile(lat, 25)),
        "latency_q3_ms": _round(percentile(lat, 75)),
        "timeouts": [it.get("target") for it in scored if it.get("timeout")],
        "flagged": [it.get("target") for it in scored if it.get("flags")],
    }


def _round(v):
    return None if v is None else round(v)


# --- parallel forms -----------------------------------------------------------------------

def item_measures(word: str, lang: str) -> dict:
    ph, _ = phonemes(word.lower(), lang)
    return {"word": word, "zipf": round(zipf_frequency(word.lower(), lang), 2), "phonemes": len(ph),
            "letters": len(word)}


def _imbalance(form_a: list[int], form_b: list[int], z: np.ndarray) -> float:
    """Difference between the halves in mean, plus half the difference in spread, summed over
    both measures (in SD units of the whole set)."""
    if not form_a or not form_b:
        return float("inf")
    means = np.abs(z[form_a].mean(axis=0) - z[form_b].mean(axis=0)).sum()
    spreads = np.abs(z[form_a].std(axis=0) - z[form_b].std(axis=0)).sum()
    return float(means + 0.5 * spreads)


def parallel_forms(words: list[str], lang: str) -> dict:
    """Two halves of `words` matched on Zipf frequency and length in phonemes (indices into words)."""
    measures = [item_measures(w, lang) for w in words]
    n = len(words)
    if n < 4:
        raise ValueError("Parallel forms need at least 4 items.")
    raw = np.array([[m["zipf"], m["phonemes"]] for m in measures], dtype=float)
    sd = raw.std(axis=0)
    z = (raw - raw.mean(axis=0)) / np.where(sd > 0, sd, 1)
    order = sorted(range(n), key=lambda i: (z[i].sum(), z[i][0]))
    a: list[int] = []
    b: list[int] = []
    for k in range(0, n - 1, 2):
        p, q = order[k], order[k + 1]
        sum_a, sum_b = z[a].sum(axis=0) if a else np.zeros(2), z[b].sum(axis=0) if b else np.zeros(2)
        keep = np.abs(sum_a + z[p] - sum_b - z[q]).sum()
        swap = np.abs(sum_a + z[q] - sum_b - z[p]).sum()
        (a.append(p), b.append(q)) if keep <= swap else (a.append(q), b.append(p))
    if n % 2:
        last = order[-1]
        (a if _imbalance(a + [last], b, z) <= _imbalance(a, b + [last], z) else b).append(last)
    improved = True
    while improved:  # swap single items between halves while it improves the match
        improved = False
        best = _imbalance(a, b, z)
        for i in range(len(a)):
            for j in range(len(b)):
                a2, b2 = a.copy(), b.copy()
                a2[i], b2[j] = b[j], a[i]
                score = _imbalance(a2, b2, z)
                if score < best - 1e-9:
                    a, b, best, improved = a2, b2, score, True
    a.sort()
    b.sort()

    def stats(idx):
        cols = {k: [measures[i][k] for i in idx] for k in ("zipf", "phonemes", "letters")}
        return {"n": len(idx), **{f"{k}_mean": round(float(np.mean(v)), 2) for k, v in cols.items()},
                **{f"{k}_sd": round(float(np.std(v, ddof=1)), 2) if len(v) > 1 else 0.0 for k, v in cols.items()}}

    return {"A": a, "B": b, "measures": measures, "stats": {"A": stats(a), "B": stats(b)}}


# --- reference range for the public test -------------------------------------------------

AGE_BANDS = ("18-29", "30-44", "45-59", "60-74", "75+")


def _describe(values: list[float]) -> dict:
    v = np.asarray(values, dtype=float)
    return {"mean": round(float(v.mean()), 1), "sd": round(float(v.std(ddof=1)), 1) if len(v) > 1 else 0.0,
            "p5": round(float(np.percentile(v, 5)), 1), "p50": round(float(np.percentile(v, 50)), 1),
            "p95": round(float(np.percentile(v, 95)), 1), "min": round(float(v.min()), 1),
            "max": round(float(v.max()), 1)}


def norms_summary(records: list[dict], min_n: int = NORMS_MIN_N) -> dict:
    """n, and once n >= min_n the mean, SD and 5th/50th/95th percentiles of accuracy (items correct
    and percent) and of each person's median latency on correct items."""
    out = {"n": len(records), "min_n": min_n, "ready": len(records) >= min_n}
    if not out["ready"]:
        return out
    n_items = Counter(r["n_items"] for r in records).most_common(1)[0][0]
    lat = [r["median_latency_ms"] for r in records if r.get("median_latency_ms") is not None]
    out.update(n_items=n_items, correct=_describe([r["correct"] for r in records]),
               accuracy_pct=_describe([r["accuracy_pct"] for r in records]),
               median_latency_ms=_describe(lat) if len(lat) >= min_n else None,
               age_bands=dict(Counter(r.get("age_band") or "not given" for r in records)))
    return out


def sign_receipt(payload: dict, key: bytes) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode()
    return body + "." + hmac.new(key, body.encode(), hashlib.sha256).hexdigest()[:32]


def read_receipt(token: str, key: bytes) -> dict | None:
    body, _, sig = str(token).partition(".")
    good = hmac.new(key, body.encode(), hashlib.sha256).hexdigest()[:32]
    if not sig or not hmac.compare_digest(sig, good):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(body.encode()))
    except ValueError:
        return None


def summary_from_receipts(receipts: list[dict]) -> dict:
    """Accuracy and median latency (correct items) from one session's verified receipts."""
    correct = [r for r in receipts if r["code"] == "Correct"]
    lat = [r["latency_ms"] for r in correct if r.get("latency_ms") is not None]
    n = len(receipts)
    return {"n_items": n, "correct": len(correct), "accuracy_pct": round(100 * len(correct) / n, 1),
            "median_latency_ms": _round(percentile(lat, 50))}

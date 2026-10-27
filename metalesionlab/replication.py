"""Measures for the n = 100 replication (docs/replication_plan.md). No GPU.

Everything is paired by picture: the same pictures are resampled for both sides of a comparison
(percentile bootstrap, 95% CI), and where a condition has several seeds, seeds are resampled
within it. Model Lab results (scripts/model_lab.py) are lists of rows {"word", "said", "code"}.

Error types (pre-registered):
  meaning          Semantic or Mixed (WordNet relation, no judge)
  sound            Nonword or Formal
  self_correction  the first attempt is wrong but a later sentence names the target
                   ("Caraloon? Wait object is carrot.")
  jargon           Neologism, or a first attempt in which letters are under half of the
                   non-space characters ("5-01-26-01-01-01-")
"""
from __future__ import annotations

import re

import numpy as np

from metalesionlab.naming_errors import classify

MEANING = ("Semantic", "Mixed")
SOUND = ("Nonword", "Formal")


# --- per-trial measures -----------------------------------------------------------------

def _sentences(said: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s|\n", said.replace("*", "").strip()) if s.strip()]


def self_correction(said: str, code: str, target: str, alternates: tuple[str, ...] = (), lang: str = "en") -> bool:
    """A wrong first attempt followed, later in the answer, by a sentence that names the target."""
    if code == "Correct":
        return False
    return any(classify(target, s, lang, alternates).code == "Correct" for s in _sentences(said)[1:])


def is_jargon(said: str, code: str) -> bool:
    """Neologism, or a first attempt that is mostly not letters (digits, dashes, symbols)."""
    if code == "Neologism":
        return True
    if code == "Correct":
        return False
    first = (_sentences(said) or [""])[0]
    chars = [c for c in first if not c.isspace()]
    return bool(chars) and sum(c.isalpha() for c in chars) < 0.5 * len(chars)


def error_types(row: dict, target: str, alternates: tuple[str, ...] = (), lang: str = "en") -> dict[str, bool]:
    code, said = row["code"], row["said"]
    return {"error": code != "Correct", "meaning": code in MEANING, "sound": code in SOUND,
            "self_correction": self_correction(said, code, target, alternates, lang),
            "jargon": is_jargon(said, code)}


# --- matrices -----------------------------------------------------------------------------

def matrix(results: list[dict], words: list[str], value) -> np.ndarray:
    """(pictures, runs) matrix of value(row) for each result (one column per seed or run)."""
    cols = []
    for r in results:
        by = {row["word"]: row for row in r["items"]}
        cols.append([float(value(by[w])) for w in words])
    return np.array(cols, dtype=float).T if cols else np.zeros((len(words), 0))


def correct(row: dict) -> bool:
    return row["code"] == "Correct"


# --- bootstraps over pictures ------------------------------------------------------------------

def paired_bootstrap(a: np.ndarray, b: np.ndarray, n_boot: int = 10000, seed: int = 0) -> dict:
    """mean(b) - mean(a) for (pictures, seeds) matrices on the same pictures. Pictures are
    resampled once per replicate for both; seeds are resampled within each. Also a two-sided
    sign-flip p over the per-picture differences."""
    from metalesionlab.bilingual import sign_flip_test

    rng = np.random.default_rng(seed)
    n = a.shape[0]
    diff = float(b.mean() - a.mean())
    boots = np.empty(n_boot)
    for k in range(n_boot):
        idx = rng.integers(0, n, n)
        sa = a[idx][:, rng.integers(0, a.shape[1], a.shape[1])]
        sb = b[idx][:, rng.integers(0, b.shape[1], b.shape[1])]
        boots[k] = sb.mean() - sa.mean()
    lo, hi = np.percentile(boots, [2.5, 97.5])
    per_picture = b.mean(1) - a.mean(1)
    return {"a": round(float(a.mean()), 4), "b": round(float(b.mean()), 4), "diff": round(diff, 4),
            "ci95": [round(float(lo), 4), round(float(hi), 4)], "p_sign_flip": round(sign_flip_test(per_picture), 5),
            "n_pictures": int(n), "seeds": [int(a.shape[1]), int(b.shape[1])], "n_boot": n_boot}


def mean_ci(m: np.ndarray, n_boot: int = 10000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    n = m.shape[0]
    boots = np.array([m[rng.integers(0, n, n)][:, rng.integers(0, m.shape[1], m.shape[1])].mean()
                      for _ in range(n_boot)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"mean": round(float(m.mean()), 4), "ci95": [round(float(lo), 4), round(float(hi), 4)], "n_pictures": int(n)}


def share_bootstrap(groups: dict[str, tuple[np.ndarray, np.ndarray]], n_boot: int = 10000, seed: int = 0) -> dict:
    """Share of error trials with some type, per group, pooled over runs: sum(hits) / sum(errors).
    groups: name -> (errors, hits), each (pictures, runs) 0/1 on the same pictures. Pictures are
    resampled jointly for every group, so the pairwise differences are paired by picture."""
    rng = np.random.default_rng(seed)
    names = list(groups)
    n = next(iter(groups.values()))[0].shape[0]
    per_pic = {g: (e.sum(1), h.sum(1)) for g, (e, h) in groups.items()}

    def share(e, h):
        return float(h.sum() / e.sum()) if e.sum() else float("nan")

    point = {g: share(*per_pic[g]) for g in names}
    boots = {g: np.empty(n_boot) for g in names}
    for k in range(n_boot):
        idx = rng.integers(0, n, n)
        for g in names:
            e, h = per_pic[g]
            boots[g][k] = share(e[idx], h[idx])
    out = {"shares": {}, "differences": {}}
    for g in names:
        lo, hi = np.nanpercentile(boots[g], [2.5, 97.5])
        out["shares"][g] = {"share": round(point[g], 4), "ci95": [round(float(lo), 4), round(float(hi), 4)],
                            "errors": int(per_pic[g][0].sum()), "hits": int(per_pic[g][1].sum())}
    for i, g in enumerate(names):
        for h in names[i + 1:]:
            d = boots[g] - boots[h]
            lo, hi = np.nanpercentile(d, [2.5, 97.5])
            out["differences"][f"{g} - {h}"] = {"diff": round(point[g] - point[h], 4),
                                                "ci95": [round(float(lo), 4), round(float(hi), 4)]}
    return out


def largest_with_margin(result: dict, group: str) -> bool:
    """Pre-registered criterion: `group` has the largest share and every CI of its difference from
    another group excludes 0."""
    for key, d in result["differences"].items():
        a, b = key.split(" - ")
        if group == a and not d["ci95"][0] > 0:
            return False
        if group == b and not d["ci95"][1] < 0:
            return False
    return True

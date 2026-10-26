"""Code a picture-naming response with the standard error categories.

Categories and decision order follow the Philadelphia Naming Test scoring scheme
(Roach et al., 1996), simplified for automatic use:

  NoResponse   nothing, a refusal ("I don't know") or only fillers
  Correct      the target or an accepted alternate, allowing articles, plurals and modifiers
  Description  three or more words that don't contain the target ("a seat in the park")
  Semantic     a real word related in meaning only
  Formal       a real word related in sound only
  Mixed        a real word related in both
  Unrelated    a real word related in neither
  Nonword      a non-word that sounds like the target
  Neologism    a non-word that doesn't

Sound: the PNT criterion. The two share the first or last phoneme, the stressed vowel, or
at least two phonemes anywhere. English words get phonemes from the CMU Pronouncing
Dictionary; other strings get them from spelling rules.
Meaning: WordNet (same synset, a direct link, or Wu-Palmer similarity >= 0.8), then an
optional judge for associations and other languages (Muse Spark, see spark_semantic_judge).
Visual errors need the picture, so the Muse Spark second rater flags those.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import pronouncing
from wordfreq import zipf_frequency

WORD_MIN_ZIPF = 2.0  # wordfreq Zipf frequency at or above which a string counts as a real word
WUP_THRESHOLD = 0.8  # separated related from unrelated test pairs on Oct 26 (unrelated max 0.71)

LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "fr": "French", "hi": "Hindi", "sw": "Swahili"}
REFUSALS = {"i dont know", "dont know", "i do not know", "no idea", "pass", "not sure", "im not sure",
            "no se", "no lo se", "ni idea"}
FILLERS = {"um", "umm", "uh", "uhh", "er", "erm", "hmm", "mm", "ah", "eh", "este"}
ARTICLES = {"en": {"a", "an", "the"}, "es": {"el", "la", "los", "las", "un", "una", "unos", "unas"}}

SemanticJudge = Callable[[str, str, str], bool]
JUDGE_PROMPT_VERSION = 2  # part of the judge's cache key, so a prompt change re-asks every pair


@dataclass
class Coding:
    code: str
    head: str  # the word that was coded, after normalizing
    lexical: bool | None = None
    semantic: bool | None = None
    phonological: bool | None = None


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFC", text).lower().replace("’", "'")
    text = re.sub(r"[^\w\s'-]", " ", text)
    return [t for t in (w.strip("'-") for w in text.split()) if t and t not in FILLERS]


@lru_cache(maxsize=1)
def _wordnet():
    import nltk
    from nltk.corpus import wordnet as wn
    try:
        wn.ensure_loaded()
    except LookupError:
        nltk.download("wordnet", quiet=True)
    return wn


def _same_word(target: str, word: str, lang: str) -> bool:
    if word == target or word in (target + "s", target + "es"):
        return True
    if lang == "en":
        wn = _wordnet()
        return wn.morphy(word, wn.NOUN) == target
    return False


def is_word(word: str, lang: str) -> bool:
    """wordfreq alone admits web junk ("cag" has Zipf 2.5), so English words must also be in the
    CMU dictionary unless they are common."""
    zipf = zipf_frequency(word, lang)
    if lang == "en":
        return zipf >= 3.0 or (zipf >= WORD_MIN_ZIPF and bool(pronouncing.phones_for_word(word)))
    return zipf >= WORD_MIN_ZIPF


# --- sound -----------------------------------------------------------------------------

_EN_VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}
_EN_MULTI = [("tch", "CH"), ("ch", "CH"), ("sh", "SH"), ("th", "TH"), ("ph", "F"), ("ck", "K"), ("ng", "NG"),
             ("qu", "K W"), ("wh", "W"), ("ee", "IY"), ("ea", "IY"), ("oo", "UW"), ("ai", "EY"), ("ay", "EY"),
             ("oa", "OW"), ("ou", "AW"), ("ow", "OW"), ("oi", "OY"), ("oy", "OY"), ("er", "ER"), ("ir", "ER"),
             ("ur", "ER"), ("ar", "AA R"), ("or", "AO R")]
_EN_SINGLE = {"a": "AE", "e": "EH", "i": "IH", "o": "AA", "u": "AH", "b": "B", "d": "D", "f": "F", "g": "G",
              "h": "HH", "j": "JH", "k": "K", "l": "L", "m": "M", "n": "N", "p": "P", "r": "R", "s": "S",
              "t": "T", "v": "V", "w": "W", "x": "K S", "z": "Z"}


def _en_spelling_phonemes(word: str) -> list[str]:
    """Rough letter-to-sound rules for English strings missing from the CMU dictionary."""
    w = re.sub(r"(.)\1", r"\1", word.lower())  # "kettin" -> "ketin"
    if len(w) > 3 and w.endswith("e") and w[-2] not in "aeiou":
        w = w[:-1]  # silent final e
    out, i = [], 0
    while i < len(w):
        for spelled, sound in _EN_MULTI:
            if w.startswith(spelled, i):
                out += sound.split()
                i += len(spelled)
                break
        else:
            ch, nxt = w[i], w[i + 1:i + 2]
            if ch == "c":
                out.append("S" if nxt and nxt in "eiy" else "K")
            elif ch == "y":
                out.append("Y" if i == 0 else "IY")
            elif ch in _EN_SINGLE:
                out += _EN_SINGLE[ch].split()
            i += 1
    return out


def _es_spelling_phonemes(word: str) -> tuple[list[str], int | None]:
    """Spanish spelling is close to phonemic; returns units and the stressed vowel's index."""
    w = word.lower()
    vowels_in_word = [c for c in w if _strip_accents(c) in "aeiou"]
    accented = [k for k, c in enumerate(vowels_in_word) if c in "áéíóú"]
    n_vowels = len(vowels_in_word)
    if accented:
        stress_k = accented[0]
    elif n_vowels:
        stress_k = n_vowels - 2 if (_strip_accents(w[-1]) in "aeiouns" and n_vowels > 1) else n_vowels - 1
    else:
        stress_k = None
    out, i = [], 0
    while i < len(w):
        two, ch, nxt = w[i:i + 2], w[i], w[i + 1:i + 2]
        if two in ("ch", "ll", "rr"):
            out.append({"ch": "ch", "ll": "y", "rr": "r"}[two])
            i += 2
            continue
        if two == "qu" or (two == "gu" and w[i + 2:i + 3] in ("e", "i", "é", "í")):
            out.append("k" if two == "qu" else "g")
            i += 2
            continue
        soft = bool(nxt) and nxt in "eiéí"
        if ch == "c":
            out.append("s" if soft else "k")
        elif ch == "g":
            out.append("x" if soft else "g")
        elif ch in "zv j":
            out.append({"z": "s", "v": "b", "j": "x"}.get(ch, ch))
        elif ch == "h" or ch == " ":
            pass
        else:
            out.append(_strip_accents(ch))
        i += 1
    vowel_idx = [k for k, u in enumerate(out) if u in "aeiou"]
    stressed = vowel_idx[stress_k] if stress_k is not None and stress_k < len(vowel_idx) else None
    return out, stressed


@lru_cache(maxsize=None)
def phonemes(word: str, lang: str) -> tuple[tuple[str, ...], int | None]:
    """Phonemes (stress marks removed) and the index of the stressed vowel."""
    if lang == "en":
        prons = pronouncing.phones_for_word(word)
        if prons:
            ph = prons[0].split()
            stressed = next((k for k, p in enumerate(ph) if p.endswith("1")), None)
            return tuple(re.sub(r"\d", "", p) for p in ph), stressed
        ph = _en_spelling_phonemes(word)
        return tuple(ph), next((k for k, p in enumerate(ph) if p in _EN_VOWELS), None)
    if lang == "es":
        ph, stressed = _es_spelling_phonemes(word)
        return tuple(ph), stressed
    return tuple(word), None


def sound_related(target: str, response: str, lang: str) -> bool:
    t, t_stress = phonemes(target, lang)
    r, r_stress = phonemes(response, lang)
    if not t or not r:
        return False
    if lang != "en":
        return _sound_related_gendered(t, r)
    if t[0] == r[0] or t[-1] == r[-1]:
        return True
    if t_stress is not None and r_stress is not None and t[t_stress] == r[r_stress]:
        return True
    return sum((Counter(t) & Counter(r)).values()) >= 2


def _sound_related_gendered(t: tuple[str, ...], r: tuple[str, ...]) -> bool:
    """The PNT rule adapted for languages like Spanish, where most nouns end in a gender vowel
    (-o/-a) and there are only five vowels: a shared last sound counts only if it is a consonant,
    and the two-shared-sounds count ignores the final vowel (gato/pato yes, gato/mano no,
    cuchara/tenedor no)."""
    vowels = set("aeiou")
    if t[0] == r[0]:
        return True
    if t[-1] == r[-1] and t[-1] not in vowels:
        return True
    t_core = t[:-1] if len(t) > 1 and t[-1] in vowels else t
    r_core = r[:-1] if len(r) > 1 and r[-1] in vowels else r
    return sum((Counter(t_core) & Counter(r_core)).values()) >= 2


# --- meaning ---------------------------------------------------------------------------

def wordnet_related(target: str, response: str) -> bool:
    wn = _wordnet()
    targets, responses = wn.synsets(target, pos=wn.NOUN)[:3], wn.synsets(response, pos=wn.NOUN)[:3]
    for x in targets:
        linked = set(x.hypernyms() + x.hyponyms() + x.part_meronyms() + x.part_holonyms()
                     + x.member_meronyms() + x.member_holonyms() + x.substance_meronyms() + x.substance_holonyms())
        for y in responses:
            if x == y or y in linked or (x.wup_similarity(y) or 0) >= WUP_THRESHOLD:
                return True
    return False


def meaning_related(target: str, response: str, lang: str, judge: SemanticJudge | None) -> bool:
    if lang == "en" and wordnet_related(target, response):
        return True
    return bool(judge and judge(target, response, lang))


def spark_semantic_judge(api, cache_path: Path | None = None) -> SemanticJudge:
    """Muse Spark decides meaning relatedness WordNet can't (associations, other languages).
    Answers are cached on disk so a pair is only ever asked once."""
    from metalesionlab.meta_api import REPO_ROOT

    path = cache_path or REPO_ROOT / "runs" / "cache" / "semantic_judge.json"
    cache = json.loads(path.read_text()) if path.exists() else {}

    def judge(target: str, response: str, lang: str) -> bool:
        key = f"v{JUDGE_PROMPT_VERSION}|{lang}|{target}|{response}"
        if key not in cache:
            prompt = (
                "You are scoring a picture-naming test. A response counts as related in meaning to the target if "
                "it is a synonym; a member of the same category, even a broad one such as animals, foods, tools, "
                "clothing, furniture, body parts or vehicles (dog or duck for cat); a category name (animal for "
                "cat); a part or whole; or a strong associate (milk for cat, rain for umbrella). Sound similarity "
                f"does not count.\nLanguage: {LANGUAGE_NAMES.get(lang, lang)}\nTarget: {target}\n"
                f"Response: {response}\nAnswer with exactly one word: yes or no.")
            reply = api.chat([{"role": "user", "content": prompt}]).choices[0].message.content
            cache[key] = reply.strip().lower().startswith("yes")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
        return cache[key]

    return judge


# --- the decision tree -----------------------------------------------------------------

def classify(target: str, response: str, lang: str = "en", alternates: tuple[str, ...] = (),
             judge: SemanticJudge | None = None) -> Coding:
    target = target.lower().strip()
    words = tokens(response)
    if not words or _strip_accents(" ".join(words)).replace("'", "") in REFUSALS:
        return Coding("NoResponse", "")
    content = [w for w in words if w not in ARTICLES.get(lang, set())] or words
    accepted = (target,) + tuple(a.lower() for a in alternates)
    if any(_same_word(a, w, lang) for a in accepted for w in content):
        return Coding("Correct", next(w for w in content if any(_same_word(a, w, lang) for a in accepted)))
    if len(content) >= 3:
        return Coding("Description", " ".join(content))
    head = content[-1] if lang == "en" else content[0]  # head noun: last in English, first in Spanish

    lexical = is_word(head, lang)
    phon = sound_related(target, head, lang)
    if not lexical:
        return Coding("Nonword" if phon else "Neologism", head, lexical=False, phonological=phon)
    sem = meaning_related(target, head, lang, judge)
    code = {(True, True): "Mixed", (True, False): "Semantic", (False, True): "Formal"}.get((sem, phon), "Unrelated")
    return Coding(code, head, lexical=True, semantic=sem, phonological=phon)

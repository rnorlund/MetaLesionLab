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

Other languages (checked Oct 26 for French, Brazilian Portuguese, Hindi and Mandarin Chinese;
see docs/languages.md):
  - Correct allows each language's articles, framing words ("c'est", "é", "यह ... है") and
    regular plurals (chats, gatos, colheres, बिल्लियाँ), French elision (l'ancre), hyphenated or
    multi-word targets (guarda-chuva, "guarda chuva") and an article the transcript doubled
    ("UnUn chat").
  - Sound: French and Portuguese get rough spelling-to-sound rules (like Spanish). A response
    that sounds exactly like the target is the target spelled another way, as transcripts do:
    "une encre" for ancre, "cerrote" for serrote. Hindi compares letters, without the virama and
    nukta signs. Chinese characters don't spell sounds, so Chinese gets no sound relation (no
    Formal, Mixed or Nonword codes); the second rater covers those.
  - Chinese has no spaces: responses are split into words with wordfreq's Chinese word list
    (greedy longest match), after dropping frames such as 这是, a numeral plus measure word
    (一只, 一把) and final particles. A Description is three or more such words, or a phrase
    ending in 的 ("下雨用的"). Traditional characters are mapped to simplified first.
  - wordfreq's Hindi list is small, so a Hindi string it doesn't know still counts as a real
    word when the judge relates it to the target in meaning.

More languages (checked Oct 27: German, Italian, Dutch, Japanese, Korean, Arabic, Turkish, Polish,
Indonesian and Vietnamese; see docs/languages.md):
  - Articles and frames: der/die/das, il/la/un/l'/un', de/het/een, Turkish bir, Indonesian
    classifiers (seekor, sebuah), Vietnamese classifiers (con, cái, chiếc, quả), "das ist",
    "to jest", "ini", "đây là", "هذه". Italian elides like French (l'ancora, un'arpa).
  - Regular plurals: German (-n, -en, -e, -er, with or without an umlaut), Dutch (-en, -'s and
    diminutives: bankje, katje), Italian (gatti, carote, lumache), Turkish (-ler/-lar),
    Indonesian doubling (kucing-kucing).
  - German and Dutch compounds have the head last, so a compound ending in the name counts
    (Teekessel for Kessel, fluitketel for ketel), as does the name written in two parts.
  - Arabic: short-vowel marks and tatweel are dropped, alef forms, ta marbuta/ha and alef
    maqsura/ya are folded, and the article al- (also wa-l-, bi-l-) may be attached (القطة).
  - Korean: a name may carry a particle or the copula (고양이가, 고양이입니다); a compound ending in
    a name of two or more syllables counts (고무장갑). Sound comes from the jamo (NFD), with
    liaison and ㅐ/ㅔ merged, and the same sounds count as the name (파이네플 for 파인애플).
  - Japanese has no spaces and gets its own path, like Chinese: katakana and hiragana are the
    same (ネコ = ねこ); kanji spellings count through the set's alternates (Muse Spark lists the
    kana reading: 猫 -> ねこ, ネコ); frames (これは, です) are dropped; a compound ending in the
    name counts (子猫, 雨傘). Sound is compared in kana only. With the Muse Spark judge, a kanji
    transcript is also read aloud in kana, so a homophone counts (怒り for 錨, both いかり).
  - Accents still fold for Latin-script words, except Vietnamese, where the marks are tones and
    vowels (mèo "cat", méo "bent"); a Vietnamese transcript with no marks at all still matches.
  - For the new languages, a name the transcript split in two or ran together still counts.
  - No spelling-to-sound rules for these languages: sound is compared letter by letter (jamo
    for Korean, kana for Japanese).
  - English: a real word that wordfreq rates rare and CMU lacks is still a word if WordNet lists
    it (footstool) or it joins two real words (kiwifruit).
"""
from __future__ import annotations

import json
import math
import re
import threading
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import pronouncing
from wordfreq import available_languages, zipf_frequency

WORD_MIN_ZIPF = 2.0  # wordfreq Zipf frequency at or above which a string counts as a real word
WUP_THRESHOLD = 0.8  # separated related from unrelated test pairs on Oct 26 (unrelated max 0.71)

LANGUAGE_NAMES = {"en": "English", "es": "Spanish", "fr": "French", "pt": "Brazilian Portuguese", "hi": "Hindi",
                  "zh": "Mandarin Chinese", "de": "German", "it": "Italian", "nl": "Dutch", "ja": "Japanese",
                  "ko": "Korean", "ar": "Arabic", "tr": "Turkish", "pl": "Polish", "id": "Indonesian",
                  "vi": "Vietnamese", "sw": "Swahili"}
REFUSALS = {"i dont know", "dont know", "i do not know", "no idea", "pass", "not sure", "im not sure",
            "no se", "no lo se", "ni idea",
            "je ne sais pas", "je sais pas", "sais pas", "aucune idee", "je ne sais plus",
            "nao sei", "sei la", "nao faco ideia", "nao lembro",
            "पता नहीं", "नहीं पता", "मुझे नहीं पता", "मुझे पता नहीं", "मालूम नहीं", "मुझे नहीं मालूम",
            "不知道", "我不知道", "不清楚", "不记得", "忘了", "我忘了",
            "weiß nicht", "ich weiß nicht", "ich weiß es nicht", "keine ahnung",
            "non lo so", "non so", "non mi ricordo",
            "weet ik niet", "ik weet het niet", "geen idee",
            "わからない", "わかりません", "分からない", "分かりません", "知らない", "知りません",
            "모르겠어요", "모르겠습니다", "모르겠다", "몰라요", "몰라",
            "لا أعرف", "لا اعرف", "ما اعرف", "ما أعرف", "مش عارف",
            "bilmiyorum", "bilmem", "nie wiem", "tidak tahu", "saya tidak tahu", "nggak tahu", "gak tahu",
            "không biết", "tôi không biết"}
FILLERS = {"um", "umm", "uh", "uhh", "er", "erm", "hmm", "mm", "ah", "eh", "este", "euh", "heu", "hum", "हम्म", "उम्म",
           "äh", "ähm", "öhm", "ehm", "uhm", "eee", "yyy", "ıı", "ừm", "ờ", "えー", "えーと", "えっと", "음", "어"}
ARTICLES = {"en": {"a", "an", "the"}, "es": {"el", "la", "los", "las", "un", "una", "unos", "unas"},
            "fr": {"le", "la", "les", "l", "un", "une", "des", "du", "de", "d"},
            "pt": {"o", "a", "os", "as", "um", "uma", "uns", "umas"},
            "hi": {"एक"},
            "de": {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "eines"},
            "it": {"il", "lo", "la", "i", "gli", "le", "l", "un", "uno", "una", "dei", "degli", "delle", "del",
                   "della", "dello", "dell"},
            "nl": {"de", "het", "een", "n", "t"},  # 'n and 't lose their apostrophe in tokens()
            "tr": {"bir"},
            # Indonesian and Vietnamese count with classifiers, like Chinese measure words.
            "id": {"sebuah", "seekor", "sebatang", "sehelai", "sepasang", "sebiji", "satu"},
            "vi": {"con", "cái", "chiếc", "củ", "quả", "trái", "cây", "ngôi", "tấm", "cuốn", "quyển", "bông",
                   "đôi", "bức", "một", "những", "các"}}
# Words that frame a name without being part of it ("c'est un chat", "é um gato", "यह बिल्ली है");
# dropped along with articles before counting words.
FRAME_WORDS = {"fr": {"c", "ce", "est", "ça", "ca", "voilà", "voila"},
               "pt": {"é", "isso", "isto", "eh"},
               "hi": {"यह", "ये", "वह", "वो", "है", "हैं", "था", "थी"},
               "de": {"ist", "es", "dies", "hier"},
               "it": {"è", "questo", "questa", "ecco"},
               "nl": {"dit", "dat", "is"},
               "tr": {"bu", "şu"},
               "pl": {"to", "jest", "ten", "ta"},
               "id": {"ini", "itu", "adalah"},
               "vi": {"đây", "là", "này", "đó"},
               "ar": {"هذه", "هذا", "هذي", "هو", "هي"},
               "ko": {"이것은", "이건", "이거", "이것이", "이게", "그것은", "그건", "저것은", "저건"}}
POSTPOSITIONS = {"hi": {"का", "की", "के", "में", "पर", "को", "से", "ने", "तक", "लिए", "वाला", "वाली", "वाले"}}
# The head noun comes last (black cat, schwarze Katze, काली बिल्ली, 黑猫, 검은 고양이); else first (gato negro).
HEAD_LAST = {"en", "hi", "zh", "de", "nl", "pl", "tr", "ko", "ja"}
ELISION = {"fr": re.compile(r"^(l|d|j|c|qu|s|n|m|t)'(.+)$"),  # French l'ancre -> l + ancre
           "it": re.compile(r"^(l|un|dell|nell|all|dall|sull|quell|quest|c)'(.+)$")}  # un'arpa -> un + arpa
COMPOUND_HEAD_LAST = {"de", "nl"}  # compounds written as one word, head last (Teekessel)
# Languages added Oct 27, where a transcript that splits a name in two ("أنا ناس" for أناناس) or runs its
# words together ("càrốt" for cà rốt, "sarungtangan") still counts. English and Spanish codes stay as they were.
JOIN_LANGS = {"de", "it", "nl", "ko", "ar", "tr", "pl", "id", "vi"}
NO_ACCENT_FOLDING = {"vi"}  # Vietnamese marks are tones and vowels: mèo (cat), méo (bent)
# Korean particles and copula endings after a noun (고양이가, 닻을, 고양이입니다, 우산이에요), longest first.
_KO_SUFFIXES = ("입니다", "이에요", "이네요", "이었어요", "예요", "이야", "이다", "이네", "이요", "들이", "들은", "들을",
                "이", "가", "은", "는", "을", "를", "도", "의", "요", "야", "다", "들")

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


def _keep_char(c: str) -> bool:
    # Combining marks count as letters: Devanagari vowel signs and virama aren't \w ("बिल्ली").
    return c.isalnum() or c in "_'-" or c.isspace() or unicodedata.category(c).startswith("M")


def tokens(text: str) -> list[str]:
    # Turkish dotted capital İ: str.lower() would give "i" plus a combining dot ("İglo").
    text = unicodedata.normalize("NFC", text).replace("İ", "i").lower()
    text = text.replace("’", "'").replace("\u200c", "").replace("\u200d", "")
    text = "".join(c if _keep_char(c) else " " for c in text)
    return [t for t in (w.strip("'-") for w in text.split()) if t and t not in FILLERS]


def _norm(word: str) -> str:
    return unicodedata.normalize("NFC", word).lower().strip()


def _refusal_key(text: str) -> str:
    return _strip_accents(text).replace("'", "")


REFUSAL_KEYS = {_refusal_key(r) for r in REFUSALS}


# NLTK's WordNet reader loads lazily and reads through one shared file handle, so it isn't
# thread-safe; the web app scores several responses at once. Every WordNet lookup holds this lock.
WORDNET_LOCK = threading.RLock()


@lru_cache(maxsize=1)
def _wordnet():
    import nltk
    from nltk.corpus import wordnet as wn
    try:
        wn.ensure_loaded()
    except LookupError:
        nltk.download("wordnet", quiet=True)
    return wn


def _plural_forms(target: str, lang: str) -> set[str]:
    """Regular plural (and Hindi oblique) forms of a singular noun, beyond adding -s/-es."""
    t = target
    if lang == "fr":
        forms = {t + "x"}
        if t.endswith("al"):
            forms.add(t[:-2] + "aux")  # cheval -> chevaux
        return forms
    if lang == "pt":
        if t.endswith("ão"):
            return {t[:-2] + end for end in ("ões", "ães", "ãos")}
        if t.endswith("m"):
            return {t[:-1] + "ns"}  # homem -> homens
        if t.endswith("l"):
            return {t[:-1] + "is", t[:-2] + "éis", t[:-2] + "óis"}  # animal -> animais, papel -> papéis
        return set()
    if lang == "hi":
        t = t.replace("ँ", "ं")
        if t.endswith("ी"):
            return {t[:-1] + "ियां", t[:-1] + "ियों"}  # बिल्ली -> बिल्लियाँ, बिल्लियों
        if t.endswith("िया"):
            return {t + "ं", t[:-1] + "ों"}  # गुड़िया -> गुड़ियाँ
        if t.endswith("ा"):
            return {t[:-1] + "े", t[:-1] + "ों", t + "एं"}  # छाता -> छाते, छातों
        return {t + "ें", t + "ों", t + "एं"}  # किताब -> किताबें
    if lang == "de":
        forms = {t + "n", t + "en", t + "e", t + "er"}  # Katzen, Handschuhe
        m = re.search(r"(au|a|o|u)(?!.*(au|a|o|u))", t)  # the last a, o, u or au can take an umlaut
        if m:
            umlaut = t[:m.start()] + {"au": "äu", "a": "ä", "o": "ö", "u": "ü"}[m.group(1)] + t[m.end():]
            forms |= {umlaut, umlaut + "e", umlaut + "er"}  # Bänke, Fahrräder
        return forms
    if lang == "nl":
        forms = {t + "en", t + "'s", t + "je", t + "tje", t + "pje", t + "etje", t + "jes", t + "tjes"}
        if re.search(r"(^|[^aeiou])[aeiou][bdfgklmnprst]$", t):
            forms |= {t + t[-1] + "en", t + t[-1] + "etje"}  # kat -> katten, bal -> balletje
        if re.search(r"(aa|ee|oo|uu)[^aeiou]$", t):
            forms.add(t[:-2] + t[-1] + "en")  # schaar -> scharen, zaag -> zagen
        return forms
    if lang == "it":
        if t.endswith(("ca", "ga")):
            return {t[:-1] + "he"}  # lumaca -> lumache
        if t.endswith(("co", "go")):
            return {t[:-1] + "hi", t[:-1] + "i"}
        if t.endswith("io"):
            return {t[:-1]}  # cucchiaio -> cucchiai
        if t.endswith("a"):
            return {t[:-1] + "e"}  # carota -> carote
        if t.endswith(("o", "e")):
            return {t[:-1] + "i"}  # gatto -> gatti, bollitore -> bollitori
        return set()
    if lang == "tr":
        return {t + "ler", t + "lar"}
    if lang == "id":
        return {f"{t}-{t}"}  # kucing-kucing
    if lang == "ar":
        # Sound plural (شمعة -> شمعات; ta marbuta is folded to ha) and, for a noun of unit, its
        # collective (جزرة "a carrot" -> جزر "carrots", قطة -> قط).
        return {t[:-1] + "ات", t[:-1]} if t.endswith("ه") and len(t) > 2 else {t + "ات"}
    return set()


_AR_MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")  # short vowels, other marks, tatweel
_AR_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"})
_AR_PREFIXES = ("وال", "بال", "فال", "كال", "ال", "لل")  # al-, with "and", "with", "so", "like", "for" before it


def ar_norm(word: str) -> str:
    """Arabic spelling variation a transcript may show: short-vowel marks and tatweel dropped; alef
    forms (أ إ آ), ta marbuta and ha, alef maqsura and ya folded together. A final alef maqsura is
    the same final /a/ as ta marbuta (القطى for القطة), so it folds to ha."""
    return re.sub("ى(?=\\s|$)", "ه", _AR_MARKS.sub("", word)).translate(_AR_FOLD)


def _ar_bare(word: str) -> str:
    """The word without an attached article (القطة -> قطه), if at least two letters remain."""
    return next((word[len(p):] for p in _AR_PREFIXES if word.startswith(p) and len(word) - len(p) >= 2), word)


def _ko_same(target: str, word: str) -> bool:
    """고양이가, 고양이입니다: the name with a particle or the copula. A compound ending in a name of two or
    more syllables counts (고무장갑 for 장갑); a one-syllable name must stand alone (톱, not 데스크톱)."""
    for rest in (word, *(word[:-len(s)] for s in _KO_SUFFIXES if word.endswith(s) and len(word) > len(s))):
        if rest == target or (len(target) >= 2 and rest.endswith(target)):
            return True
    return False


def _fold_latin_accents(s: str) -> str:
    """Drop accents from Latin-script words only: in Devanagari the combining marks are vowel signs."""
    return _strip_accents(s) if all(ord(c) < 0x250 for c in unicodedata.normalize("NFC", s)) else s


def _same_word(target: str, word: str, lang: str) -> bool:
    if word == target or word in (target + "s", target + "es"):
        return True
    # A missing or extra accent is a spelling/transcription detail, not a naming error ("iglu" for "iglú").
    folded = _fold_latin_accents(word)
    if lang not in NO_ACCENT_FOLDING and (folded != word or _fold_latin_accents(target) != target):
        bare = _fold_latin_accents(target)
        if folded == bare or folded in (bare + "s", bare + "es"):
            return True
    # A Vietnamese transcript may drop every mark (thia for thìa, coi for còi): a word with no marks at all
    # matches the target's letters, but one with other marks is another word (méo "bent", not mèo "cat").
    if lang == "vi" and word.isascii() and word == _strip_accents(target).replace("đ", "d"):
        return True
    if lang == "en":
        with WORDNET_LOCK:
            wn = _wordnet()
            return wn.morphy(word, wn.NOUN) == target
    if lang == "hi":
        word = word.replace("ँ", "ं")  # chandrabindu and anusvara spell the same nasal (आँख, आंख)
        if word == target.replace("ँ", "ं"):
            return True
    if lang == "ar":
        target, word = _ar_bare(ar_norm(target)), _ar_bare(ar_norm(word))
        if word == target:
            return True
    if lang == "ko":
        return _ko_same(target, word)
    return word in _plural_forms(target, lang)


def _compound_match(target: str, words: list[str], lang: str) -> bool:
    """German and Dutch compounds are written as one word with the head last: a word ending in the
    name after at least three more letters is a kind of it (Teekessel, fluitketel, Regenschirm for
    Schirm). The name split in two by the transcript ("Regen Schirm", "Regen-Schirm") also counts."""
    if lang not in COMPOUND_HEAD_LAST:
        return False
    joined = [w.replace("-", "") for w in words] + [a + b for a, b in zip(words, words[1:])]
    return any(_same_word(target, w, lang) or any(_same_word(target, w[i:], lang) for i in range(3, len(w) - 1))
               for w in joined)


def _joined_match(target: str, words: list[str], lang: str) -> bool:
    """The name split in two by the transcript ("أنا ناس" for أناناس), or a several-word name run
    together ("càrốt" for cà rốt, "sarungtangan" for sarung tangan)."""
    if lang not in JOIN_LANGS:
        return False
    flat = re.sub(r"[\s-]+", "", target)
    return any(_same_word(flat, w.replace("-", ""), lang) for w in [*words, *(a + b for a, b in zip(words, words[1:]))])


def _phrase_match(target: str, words: list[str], lang: str) -> bool:
    """A multi-word or hyphenated target ("guarda-chuva") said with or without the hyphen, with a
    plural on its last part ("guarda-chuvas")."""
    parts = [p for p in re.split(r"[\s-]+", target) if p]
    if len(parts) < 2:
        return False
    flat = [p for w in words for p in w.split("-") if p]
    n = len(parts)
    return any(flat[i:i + n - 1] == parts[:-1] and _same_word(parts[-1], flat[i + n - 1], lang)
               for i in range(len(flat) - n + 1))


def word_zipf(word: str, lang: str) -> float:
    """wordfreq's Zipf frequency. Chinese is looked up directly in its word list: wordfreq would
    need jieba to tokenize it, and the classifier splits Chinese into words itself."""
    if lang == "zh":
        freq = _zh_words().get(_zh_simplify(word), 0.0)
        return round(math.log10(freq * 1e9), 2) if freq else 0.0
    try:
        return zipf_frequency(word, lang)
    except (ImportError, LookupError):  # a language whose tokenizer isn't installed (ja, ko): look the word up
        freq = _freq_dict(lang).get(word, 0.0)
        return round(math.log10(freq * 1e9), 2) if freq else 0.0


@lru_cache(maxsize=None)
def _freq_dict(lang: str) -> dict[str, float]:
    from wordfreq import get_frequency_dict
    try:
        return get_frequency_dict(lang, "best")
    except LookupError:
        return {}


def is_word(word: str, lang: str) -> bool:
    """wordfreq alone admits web junk ("cag" has Zipf 2.5), so English words must also be in the
    CMU dictionary unless they are common."""
    zipf = word_zipf(word, lang)
    if lang == "en":
        if zipf >= 3.0 or (zipf >= WORD_MIN_ZIPF and bool(pronouncing.phones_for_word(word))):
            return True
        # Real words that wordfreq rates rare and CMU lacks: WordNet lemmas (footstool), and closed
        # compounds of two real words (kiwifruit = kiwi + fruit). Each part must be common or in CMU and
        # also a WordNet lemma, so a nonword that splits into a name and a word (Caraloon: cara + loon)
        # stays a nonword.
        return _in_wordnet(word) or any(_compound_part(word[:i]) and _compound_part(word[i:])
                                        for i in range(3, len(word) - 2))
    return zipf >= WORD_MIN_ZIPF


def _in_wordnet(word: str) -> bool:
    with WORDNET_LOCK:
        return bool(_wordnet().synsets(word))


def _compound_part(part: str) -> bool:
    return (len(part) >= 3 and (word_zipf(part, "en") >= 3.0 or bool(pronouncing.phones_for_word(part)))
            and _in_wordnet(part))


def has_large_wordlist(lang: str) -> bool:
    return lang in available_languages("large")


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


# --- French and Portuguese spelling rules ---------------------------------------------------
# Rough letter-to-sound rules, like the Spanish ones: enough to compare sounds and to see that
# two spellings are the same spoken word ("encre"/"ancre", "cerrote"/"serrote"). Not a full
# phonology: liaison, most exceptions and Portuguese vowel height are ignored.

_FR_VOWEL_LETTERS = set("aeiouyéèêëàâîïôûùœ")
_FR_SOFT = set("eiyéèêë")
_FR_NASALS = [("ain", "ɛ̃"), ("aim", "ɛ̃"), ("ein", "ɛ̃"), ("oin", "w ɛ̃"), ("ien", "j ɛ̃"), ("an", "ɑ̃"), ("am", "ɑ̃"),
              ("en", "ɑ̃"), ("em", "ɑ̃"), ("on", "ɔ̃"), ("om", "ɔ̃"), ("in", "ɛ̃"), ("im", "ɛ̃"), ("yn", "ɛ̃"),
              ("ym", "ɛ̃"), ("un", "œ̃"), ("um", "œ̃")]
_FR_GROUPS = [("ouill", "u j"), ("aill", "a j"), ("eill", "ɛ j"), ("euill", "œ j"), ("ill", "i j"), ("eau", "o"),
              ("ou", "u"), ("oû", "u"), ("où", "u"), ("oo", "u"), ("oi", "w a"), ("oy", "w a j"), ("au", "o"),
              ("ai", "ɛ"), ("aî", "ɛ"), ("ei", "ɛ"), ("eu", "ø"), ("œu", "ø"), ("ch", "ʃ"), ("ph", "f"), ("gn", "ɲ"),
              ("qu", "k"), ("th", "t")]
_FR_SINGLE = {"é": "e", "è": "ɛ", "ê": "ɛ", "ë": "ɛ", "e": "ə", "à": "a", "â": "a", "î": "i", "ï": "i", "y": "i",
              "ô": "o", "u": "y", "û": "y", "ù": "y", "ç": "s", "j": "ʒ", "r": "ʁ", "x": "k s", "h": ""}
_FR_VOWELS = {"a", "e", "ɛ", "ə", "i", "o", "ɔ", "u", "y", "ø", "œ", "ɑ̃", "ɛ̃", "ɔ̃", "œ̃"}


def _fr_spelling_phonemes(word: str) -> tuple[list[str], int | None]:
    """French sounds from spelling; French stress falls on the last vowel."""
    w = word.lower().replace("-", "").replace("'", "")
    if len(w) > 3 and w[-1] in "sx":
        w = w[:-1]  # plural or silent final s/x
    if len(w) > 3 and w.endswith("et"):
        w = w[:-2] + "è"  # sifflet, poulet
    elif len(w) > 2 and w[-1] == "e":
        w = w[:-1]  # mute e; the consonant before it is said (carotte)
    elif len(w) > 2 and w[-1] in "tdpgz":
        w = w[:-1]  # silent final consonant (chat, nid); c, r, f and l are usually said
    out, i = [], 0
    while i < len(w):
        nasal = next((n for n in _FR_NASALS if w.startswith(n[0], i)), None)
        after = w[i + len(nasal[0]):i + len(nasal[0]) + 1] if nasal else ""
        if nasal and (not after or (after not in _FR_VOWEL_LETTERS and after not in "nm")):
            out += nasal[1].split()
            i += len(nasal[0])
            continue
        group = next((g for g in _FR_GROUPS if w.startswith(g[0], i)), None)
        if group:
            out += group[1].split()
            i += len(group[0])
            continue
        ch, nxt, prev = w[i], w[i + 1:i + 2], w[i - 1:i]
        if ch == prev and ch not in _FR_VOWEL_LETTERS:
            i += 1  # doubled consonant
            continue
        if ch == "c":
            if not (nxt and nxt in _FR_SOFT and prev == "s"):  # "sc" before e/i is one s (scie)
                out.append("s" if nxt and nxt in _FR_SOFT else "k")
        elif ch == "e":
            closed = len(w[i + 1:i + 3]) == 2 and not set(w[i + 1:i + 3]) & _FR_VOWEL_LETTERS
            out.append("ɛ" if closed or (nxt and i + 2 == len(w) and nxt not in _FR_VOWEL_LETTERS) else "ə")
        elif ch == "g":
            if nxt == "u" and w[i + 2:i + 3] in _FR_SOFT and w[i + 2:i + 3]:
                out.append("g")
                i += 1
            else:
                out.append("ʒ" if nxt and nxt in _FR_SOFT else "g")
        elif ch == "s":
            vowel_around = prev in _FR_VOWEL_LETTERS and prev and nxt in _FR_VOWEL_LETTERS and nxt
            out.append("z" if vowel_around else "s")
        elif ch in _FR_SINGLE:
            out += _FR_SINGLE[ch].split()
        else:
            out.append(ch)
        i += 1
    vowel_idx = [k for k, u in enumerate(out) if u in _FR_VOWELS]
    return out, (vowel_idx[-1] if vowel_idx else None)


_PT_VOWEL_LETTERS = set("aeiouáéíóúâêôãõàü")
_PT_SOFT = set("eiéêí")
_PT_PLAIN = {"á": "a", "à": "a", "â": "a", "é": "e", "ê": "e", "í": "i", "ó": "o", "ô": "o", "ú": "u", "ü": "u"}
_PT_NASAL = {"a": "ã", "e": "ẽ", "i": "ĩ", "o": "õ", "u": "ũ"}
_PT_VOWELS = set("aeiou") | set(_PT_NASAL.values())


def _pt_spelling_phonemes(word: str) -> tuple[list[str], int | None]:
    """Brazilian Portuguese sounds from spelling, with the stressed vowel (written accent, else the
    next-to-last vowel for words ending in a, e, o, am, em or ens, else the last)."""
    w = word.lower().replace("-", "")
    out, stress_at, i = [], None, 0
    while i < len(w):
        ch, nxt, prev = w[i], w[i + 1:i + 2], w[i - 1:i]
        two = w[i:i + 2]
        if two in ("ão", "ãe", "õe"):
            if stress_at is None:
                stress_at = len(out)
            out += [two[0], "w" if two == "ão" else "j"]
            i += 2
            continue
        if two in ("ch", "lh", "nh", "rr", "ss"):
            out.append({"ch": "ʃ", "lh": "ʎ", "nh": "ɲ", "rr": "R", "ss": "s"}[two])
            i += 2
            continue
        if two in ("qu", "gu") and w[i + 2:i + 3] in _PT_SOFT and w[i + 2:i + 3]:
            out.append("k" if two == "qu" else "g")
            i += 2
            continue
        if ch in _PT_VOWEL_LETTERS:
            v = _PT_PLAIN.get(ch, ch)
            after = w[i + 2:i + 3]
            if nxt in ("m", "n") and (not after or after not in _PT_VOWEL_LETTERS) and w[i + 1:i + 3] != "nh":
                v = _PT_NASAL.get(v, v)  # campo, ponte, bem
                i += 1
            if ch in "áéíóúâêô":
                stress_at = len(out)
            out.append(v)
        elif ch == "c":
            out.append("s" if nxt and nxt in _PT_SOFT else "k")
        elif ch == "g":
            out.append("ʒ" if nxt and nxt in _PT_SOFT else "g")
        elif ch == "s":
            out.append("z" if prev and nxt and prev in _PT_VOWEL_LETTERS and nxt in _PT_VOWEL_LETTERS else "s")
        elif ch == "r":
            out.append("R" if i == 0 else "r")
        else:
            out.append({"ç": "s", "j": "ʒ", "x": "ʃ", "h": "", "y": "i", "w": "u", "k": "k"}.get(ch, ch))
        i += 1
    out = [u for u in out if u]
    vowel_idx = [k for k, u in enumerate(out) if u in _PT_VOWELS]
    if stress_at is not None and stress_at in vowel_idx:
        return out, stress_at
    if not vowel_idx:
        return out, None
    penult = re.search(r"([aeo]s?|am|em|ens)$", w) and len(vowel_idx) > 1
    return out, vowel_idx[-2] if penult else vowel_idx[-1]


_HI_SILENT = {"्", "़"}  # virama and nukta: marks on a consonant, not sounds of their own
# Vowels for the gendered rule: Spanish and Portuguese phonemes, and letters standing in for
# sounds elsewhere (accented Latin vowels; Devanagari vowel letters and signs).
_VOWEL_LETTERS = (set("aeiouáàâãéèêíìîóòôõúùûü") | _PT_VOWELS
                  | {chr(c) for c in range(0x0904, 0x0915)} | {chr(c) for c in range(0x093E, 0x094D)})
HOMOPHONE_LANGS = {"es", "fr", "pt", "ko"}  # a response that sounds exactly like the target counts as the target
_KO_SILENT, _KO_FINAL_NG = "ᄋ", "ᆼ"  # syllable-initial ㅇ (silent) and final ㅇ (ng)
_KO_MERGED = {"ᅢ": "ᅦ", "ᅤ": "ᅨ"}  # ㅐ and ㅔ, ㅒ and ㅖ sound the same in Seoul speech


def _ko_sounds(word: str) -> list[str]:
    """Korean sounds from Hangul: the syllables' jamo (NFD), without the silent initial ㅇ, with a final
    consonant written as the same consonant at the start of a syllable (so 파인애플 and the liaison
    spelling 파이네플 match) and ㅐ/ㅔ merged."""
    out = []
    for c in unicodedata.normalize("NFD", word):
        if c == _KO_SILENT:
            continue
        if "ᆨ" <= c <= "ᇂ" and c != _KO_FINAL_NG:
            try:
                c = unicodedata.lookup(unicodedata.name(c).replace("JONGSEONG", "CHOSEONG"))
            except KeyError:  # a consonant cluster with no initial form
                pass
        out.append(_KO_MERGED.get(c, c))
    return out


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
    if lang in ("es", "fr", "pt"):
        ph, stressed = {"es": _es_spelling_phonemes, "fr": _fr_spelling_phonemes, "pt": _pt_spelling_phonemes}[lang](word)
        return tuple(ph), stressed
    if lang == "hi":
        return tuple(c for c in word if c not in _HI_SILENT), None
    if lang == "ko":
        return tuple(_ko_sounds(word)), None
    if lang == "ja":  # kana spell sounds (one per mora); kanji don't, so they get no sounds
        kana = ja_kana(word)
        return (tuple(kana) if _KANA_ONLY.match(kana) else ()), None
    return tuple(word), None


def same_sounds(target: str, response: str, lang: str) -> bool:
    """The response is the target spelled another way, as a transcript may write it: a misspelling
    ("bouilloir", "cerrote") or a real-word homophone ("encre" for "ancre", "si" for "scie")."""
    if lang not in HOMOPHONE_LANGS or re.search(r"[\s-]", target):
        return False
    r = phonemes(response, lang)
    if lang == "ko":  # also with a particle or the copula: 닻이에요, said with liaison, is spelled 다치에요
        return any(phonemes(target + s, lang) == r for s in ("", *_KO_SUFFIXES)) and bool(r[0])
    t = phonemes(target, lang)
    return bool(t[0]) and t == r  # same sounds and the same stressed vowel


def sound_related(target: str, response: str, lang: str) -> bool:
    if lang == "zh":
        return False  # characters don't spell sounds; see the module notes
    t, t_stress = phonemes(target, lang)
    r, r_stress = phonemes(response, lang)
    if not t or not r:
        return False
    if lang not in ("en", "fr", "ko", "ja"):  # French has no gender vowels once mute e is dropped, nor do
        return _sound_related_gendered(t, r)  # Korean and Japanese, so they use the PNT rule
    if t[0] == r[0] or t[-1] == r[-1]:
        return True
    if t_stress is not None and r_stress is not None and t[t_stress] == r[r_stress]:
        return True
    return sum((Counter(t) & Counter(r)).values()) >= 2


def _sound_related_gendered(t: tuple[str, ...], r: tuple[str, ...]) -> bool:
    """The PNT rule adapted for languages like Spanish, where most nouns end in a gender vowel
    (-o/-a) and there are only five vowels: a shared last sound counts only if it is a consonant,
    and the two-shared-sounds count ignores the final vowel (gato/pato yes, gato/mano no,
    cuchara/tenedor no). Letters stand in for sounds outside Spanish; Hindi's final ā and ī
    vowel signs work like gender vowels (छाता, बिल्ली)."""
    vowels = _VOWEL_LETTERS
    if t[0] == r[0]:
        return True
    if t[-1] == r[-1] and t[-1] not in vowels:
        return True
    t_core = t[:-1] if len(t) > 1 and t[-1] in vowels else t
    r_core = r[:-1] if len(r) > 1 and r[-1] in vowels else r
    return sum((Counter(t_core) & Counter(r_core)).values()) >= 2


# --- meaning ---------------------------------------------------------------------------

def wordnet_related(target: str, response: str) -> bool:
    with WORDNET_LOCK:
        return _wordnet_related(target, response)


def _wordnet_related(target: str, response: str) -> bool:
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

    judge.reading = spark_reading(api, path.with_name("ja_readings.json"))  # Japanese homophones, see _classify_ja
    return judge


def spark_reading(api, cache_path: Path) -> Callable[[str], str]:
    """Muse Spark reads a Japanese transcript aloud, in hiragana (怒り -> いかり), so a transcript that
    wrote the spoken name with other kanji can be matched by sound. Cached on disk like the judge."""
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    def reading(text: str) -> str:
        if text not in cache:
            prompt = ("Write how this Japanese text is most likely read aloud, in hiragana only: no kanji, no "
                      f"katakana, no spaces or punctuation.\nText: {text}\nReply with the hiragana only.")
            reply = api.chat([{"role": "user", "content": prompt}]).choices[0].message.content
            cache[text] = ja_kana("".join(tokens(reply)))
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
        return cache[text]

    return reading


# --- Chinese ---------------------------------------------------------------------------

_ZH_MEASURE = "个只把条根支枝辆架张台块件双副顶盏座本片头匹朵颗粒杯瓶部艘口棵面间位枚串套对捆柄具尊"
# Frames before a name: a filler, "这是/那是/它是/这就是", or a numeral or demonstrative plus a
# measure word ("一只", "这把"). Stripped repeatedly from the front ("这是一只猫" -> "猫").
_ZH_LEADING = re.compile(rf"^(?:[嗯呃啊哦额]|(?:这|那|它)[{_ZH_MEASURE}]?就?是|就是|是|[一两二三几这那每某][{_ZH_MEASURE}])")
_ZH_TRAILING = re.compile(r"(?:吧|呢|啊|呀|吗|了|嘛|哦|喔)+$")
_ZH_MODIFIERS = set("小大老黑白红黄蓝绿灰花母公")  # one-character modifiers of a one-character name (小猫, 黑猫)
_ZH_FUNCTION = {"的", "地", "得", "了", "是", "和", "在"}


@lru_cache(maxsize=1)
def _zh_words() -> dict[str, float]:
    from wordfreq import get_frequency_dict
    return get_frequency_dict("zh", "best")


@lru_cache(maxsize=1)
def _zh_simplify_table() -> dict:
    """wordfreq's traditional-to-simplified character table (read directly: wordfreq.chinese needs jieba)."""
    import gzip

    import msgpack
    from wordfreq.util import data_path
    with gzip.open(data_path("_chinese_mapping.msgpack.gz")) as f:
        try:
            return msgpack.load(f, raw=False, strict_map_key=False)
        except TypeError:  # pure-Python msgpack
            f.seek(0)
            return msgpack.load(f, raw=False)


def _zh_simplify(text: str) -> str:
    return text.translate(_zh_simplify_table()).casefold()


def zh_segment(text: str, max_len: int = 6) -> list[str]:
    """Split Chinese text into words by greedy longest match against wordfreq's word list."""
    return _segment(text, _zh_words(), max_len)


def _segment(text: str, words: dict, max_len: int) -> list[str]:
    out, i = [], 0
    while i < len(text):
        n = next(n for n in range(min(max_len, len(text) - i), 0, -1) if n == 1 or text[i:i + n] in words)
        out.append(text[i:i + n])
        i += n
    return out


def zh_core(response: str) -> str:
    """The response without punctuation, spaces, leading frames and final particles, in simplified characters."""
    s = _zh_simplify("".join(tokens(response)))
    while (m := _ZH_LEADING.match(s)) and m.end() < len(s):
        s = s[m.end():]
    return _ZH_TRAILING.sub("", s) or s


def _zh_same(target: str, word: str) -> bool:
    """The same name allowing the 子/儿 noun suffixes (锯/锯子, 猫儿) and a one-character modifier
    of a one-character name (小猫, 黑猫; not 熊猫, panda)."""
    if word == target or word in (target + "子", target + "儿") or target in (word + "子", word + "儿"):
        return True
    return len(word) == len(target) + 1 and word.endswith(target) and word[0] in _ZH_MODIFIERS


def _classify_zh(target: str, response: str, alternates: tuple[str, ...], judge: SemanticJudge | None) -> Coding:
    core = zh_core(response)
    if not core or core in REFUSAL_KEYS:
        return Coding("NoResponse", "")
    words = zh_segment(core)
    for name in (_zh_simplify(_norm(a)) for a in (target, *alternates)):
        # A name of two or more characters anywhere counts, like "glove" in "baseball glove" (电水壶 for 水壶).
        if (len(name) >= 2 and name in core) or any(_zh_same(name, w) for w in words):
            return Coding("Correct", name)
    content = [w for w in words if w not in _ZH_FUNCTION] or words
    if len(content) >= 3 or (len(core) > 1 and core.endswith("的")):  # "下雨用的": the one for rain
        return Coding("Description", core)
    head = content[-1]
    if not is_word(head, "zh"):
        return Coding("Neologism", head, lexical=False, phonological=False)
    sem = meaning_related(target, head, "zh", judge)
    return Coding("Semantic" if sem else "Unrelated", head, lexical=True, semantic=sem, phonological=False)


# --- Japanese --------------------------------------------------------------------------

# Frames before a name (fillers, "これは"); copula endings after it ("猫です", "ねこだよ").
_JA_LEADING = re.compile(r"^(?:えーと|ええと|えっと|えー|あのー|あの|これは|それは|あれは|これが|それが)")
_JA_ENDINGS = ("でしょうか", "でした", "ですね", "ですか", "です", "だね", "だよ", "だ")
_JA_POLITE = _JA_ENDINGS[:5]  # endings no name ends in, safe to drop before coding an error ("いかだ" keeps its だ)
_JA_FUNCTION = {"の", "は", "が", "を", "に", "で", "と", "も", "や", "へ", "な", "て", "た", "する", "ある", "いる",
                "もの", "こと", "ため", "よう", "やつ"}
_KANA_ONLY = re.compile(r"^[ぁ-ゟー]+$")  # hiragana and the long-vowel mark, after ja_kana()


def ja_kana(text: str) -> str:
    """NFKC (half-width katakana to full width), then katakana folded into hiragana: ネコ = ねこ."""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in unicodedata.normalize("NFKC", text))


def ja_core(response: str) -> str:
    """The response without punctuation, spaces and leading frames, in NFKC."""
    s = unicodedata.normalize("NFKC", "".join(tokens(response)))
    while (m := _JA_LEADING.match(s)) and m.end() < len(s):
        s = s[m.end():]
    return s


def _ja_name_in(name: str, core: str) -> bool:
    """Both in ja_kana form. The name, alone or with a copula ending, or at the end of a longer word or
    phrase, since Japanese puts the head last (子猫, 黒い猫, 雨傘). A name with kanji, two or more
    characters long, also counts anywhere (自転車に乗る)."""
    for ending in ("", *_JA_ENDINGS):
        if core.endswith(ending) and len(core) > len(ending):
            rest = core[:len(core) - len(ending)]
            if rest == name or rest.endswith(name):
                return True
    return len(name) >= 2 and not _KANA_ONLY.match(name) and name in core


def _classify_ja(target: str, response: str, alternates: tuple[str, ...], judge: SemanticJudge | None) -> Coding:
    core = ja_core(response)
    if not core or _refusal_key(core) in REFUSAL_KEYS:
        return Coding("NoResponse", "")
    accepted = [_norm(a) for a in (target, *alternates)]
    names = [ja_kana(a) for a in accepted]
    if name := next((a for a, n in zip(accepted, names) if n and _ja_name_in(n, ja_kana(core))), None):
        return Coding("Correct", name)
    # Kanji spell meanings, so a transcript may write the spoken name as a homophone (怒り for いかり, the
    # anchor 錨) or mix scripts (片つむり). With a reader (the Muse Spark judge has one), compare readings
    # with the target's kana spellings: like "encre" for ancre in French, the same sounds are the name.
    reader = getattr(judge, "reading", None)
    if reader and not _KANA_ONLY.match(ja_kana(core)):
        said = reader(core)
        if name := next((a for a, n in zip(accepted, names) if _KANA_ONLY.match(n) and _ja_name_in(n, said)), None):
            return Coding("Correct", name, phonological=True)
    plain = next((core[:-len(e)] for e in _JA_POLITE if core.endswith(e) and len(core) > len(e)), core)
    words = _segment(plain, _freq_dict("ja"), 8)
    content = [w for w in words if w not in _JA_FUNCTION] or words
    if len(content) >= 3 or plain.endswith(("もの", "やつ")) or (len(plain) > 2 and plain.endswith("の")):
        return Coding("Description", plain)  # "雨の日に使うもの": the thing for rainy days
    head = content[-1]
    # Sound needs kana: compare with the target, or else its kana reading among the alternates (猫 -> ねこ).
    sounding = next((n for n in names if _KANA_ONLY.match(n)), names[0])
    phon = sound_related(sounding, reader(head) if reader and not _KANA_ONLY.match(ja_kana(head)) else head, "ja")
    if not is_word(head, "ja"):
        return Coding("Nonword" if phon else "Neologism", head, lexical=False, phonological=phon)
    sem = meaning_related(target, head, "ja", judge)
    code = {(True, True): "Mixed", (True, False): "Semantic", (False, True): "Formal"}.get((sem, phon), "Unrelated")
    return Coding(code, head, lexical=True, semantic=sem, phonological=phon)


# --- the decision tree -----------------------------------------------------------------

def _clean_token(word: str, lang: str, names: tuple[str, ...] = ()) -> str:
    """Undo two transcript artifacts on short clips: a word written twice as one token (a leading
    article or frame word, "UnUn chien", "OO banco", "यहयह", or the name itself,
    "umbrellaumbrella"), and an article fused onto the name ("Uniglú"). Only articles, frame words
    and accepted names are touched, so real words (couscous, bonbon) are left alone."""
    small = ARTICLES.get(lang, set()) | FRAME_WORDS.get(lang, set())
    firsts = {re.split(r"[\s-]+", n)[0] for n in names if re.search(r"[\s-]", n)}  # "xexe đạp", "sarungsarung tangan"
    half = len(word) // 2
    if len(word) % 2 == 0 and word[:half] == word[half:] and word[:half] in small | set(names) | firsts:
        return word[:half]
    return next((n for n in names for a in ARTICLES.get(lang, set()) if word == a + n), word)


def _unelide(word: str, lang: str = "fr") -> tuple[str, ...]:
    m = ELISION[lang].match(word)
    return m.groups() if m else (word,)


def _head(content: list[str], lang: str) -> str:
    """The head noun: last in English, Hindi and Chinese (skipping Hindi postpositions), first in
    Spanish, French and Portuguese."""
    if lang not in HEAD_LAST:
        return content[0]
    return ([w for w in content if w not in POSTPOSITIONS.get(lang, set())] or content)[-1]


def classify(target: str, response: str, lang: str = "en", alternates: tuple[str, ...] = (),
             judge: SemanticJudge | None = None) -> Coding:
    if lang == "zh":
        return _classify_zh(target, response, alternates, judge)
    if lang == "ja":
        return _classify_ja(target, response, alternates, judge)
    target = _norm(target)
    words = tokens(response)
    if not words or _refusal_key(" ".join(words)) in REFUSAL_KEYS:
        return Coding("NoResponse", "")
    accepted = (target,) + tuple(_norm(a) for a in alternates)
    if lang in ELISION:
        # An apostrophe the transcript put inside the name ("L'umaca" for lumaca) isn't an elided article.
        words = [w.replace("'", "") if w.replace("'", "") in accepted else w for w in words]
        words = [p for w in words for p in _unelide(w, lang)]
    words = [_clean_token(w, lang, accepted) for w in words]
    content = [w for w in words if w not in ARTICLES.get(lang, set()) | FRAME_WORDS.get(lang, set())] or words
    if phrase := next((a for a in accepted if _phrase_match(a, words, lang)), None):
        return Coding("Correct", phrase)
    if any(_same_word(a, w, lang) for a in accepted for w in content):
        return Coding("Correct", next(w for w in content if any(_same_word(a, w, lang) for a in accepted)))
    if name := next((a for a in accepted if _compound_match(a, content, lang) or _joined_match(a, content, lang)),
                    None):
        return Coding("Correct", name)
    if len(content) >= 3:
        return Coding("Description", " ".join(content))
    head = _head(content, lang)
    if lang == "ko" and not is_word(head, lang):  # 강아지가 -> 강아지
        head = next((head[:-len(s)] for s in _KO_SUFFIXES
                     if head.endswith(s) and len(head) > len(s) and is_word(head[:-len(s)], lang)), head)
    if lang == "ar":  # السفارة -> سفارة (wordfreq knows both; sound is compared without the article)
        head = _ar_bare(head)
    if any(same_sounds(a, head, lang) for a in accepted):
        return Coding("Correct", head, phonological=True)

    lexical = is_word(head, lang)
    phon = sound_related(target, head, lang)
    sem = None
    if not lexical and not has_large_wordlist(lang):
        # wordfreq's small lists miss real words (Hindi घोंघा, केतली); one related in meaning is real.
        sem = meaning_related(target, head, lang, judge)
        lexical = sem
    if not lexical:
        return Coding("Nonword" if phon else "Neologism", head, lexical=False, phonological=phon)
    if sem is None:
        sem = meaning_related(target, head, lang, judge)
    code = {(True, True): "Mixed", (True, False): "Semantic", (False, True): "Formal"}.get((sem, phon), "Unrelated")
    return Coding(code, head, lexical=True, semantic=sem, phonological=phon)

"""Plato's Bird: does an AI *think* in textbook examples? "Name one member of the category bird."

Plato's Chair found that Muse Image draws the textbook chair. Here we ask whether the models also name
the textbook member of a category, and compare how concentrated their answers are with people's first
answers in the Banks & Connell (2023) category production norms (117 categories, 20 UK adults each).

Human data: Banks, B., & Connell, L. (2023). Category production norms for 117 concrete and abstract
categories. Behavior Research Methods, 55(3), 1292-1313. https://doi.org/10.3758/s13428-021-01787-z
Data: https://osf.io/jgcu6/ (CC BY 4.0). The raw files stay outside the repository.

Everything here is plain Python and numpy, so the web app and tests can import it without torch.
"""
from __future__ import annotations

import math
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np

BIRD_DIR = Path(os.environ.get("PLATO_BIRD_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/bird"))
HUMAN_CREDIT = ("Human data: Banks, B., & Connell, L. (2023). Category production norms for 117 concrete and "
                "abstract categories. Behavior Research Methods, 55(3), 1292-1313. "
                "https://doi.org/10.3758/s13428-021-01787-z. Data at https://osf.io/jgcu6/, licensed CC BY 4.0 "
                "(https://creativecommons.org/licenses/by/4.0/).")
PROMPT = "Name one member of the category {category}. Answer with one word or a short name only."
# Wittgenstein's example. The norms have no "game" category, so it is asked of the AI only.
EXTRA_CATEGORIES = {"game": "Abstract"}

# Muse Image draws these (doodle style, plato.STYLES); each maps to the norms category it is compared with.
PICTURE_CATEGORIES = {
    "fruit": ("a fruit", "fruit"),
    "bird": ("a bird", "bird"),
    "vegetable": ("a vegetable", "vegetable"),
    "vehicle": ("a vehicle", "vehicle"),
    "musical_instrument": ("a musical instrument", "musical instrument"),
    "game": ("a game", "game"),
    "sport": ("a sport", "sport"),
    "tool": ("a tool", "tool"),
    "flower": ("a flower", "flower"),
    "dog": ("a dog", "breed of dog"),
    "fish": ("a fish", "fish"),
    "furniture": ("a piece of furniture", "furniture"),
}


def prompt_for(category: str) -> str:
    return PROMPT.format(category=category)


def picture_label_prompt(phrase: str, noun: str) -> str:
    """The question a vision model answers for one drawing: which member of the category it shows."""
    return (f"Someone was asked to draw {phrase}. Which {noun} is in this drawing? Name the specific kind if you "
            f"can tell (for example, for a fruit: apple). Answer with one word or a short name only.")


# ---------- synonym map (hand-reviewed; same referent only, never two different members) ----------
# Spelling and US/UK variants, abbreviations and clipped forms that name the same thing. Applied to people's
# and the models' answers alike, after cleaning and singularizing.
SYNONYMS = {
    # US/UK names for the same thing
    "eggplant": "aubergine", "zucchini": "courgette", "cilantro": "coriander", "arugula": "rocket",
    "wrench": "spanner", "soccer": "football", "gasoline": "petrol", "lorry": "truck", "aeroplane": "airplane",
    "plane": "airplane", "ladybug": "ladybird", "sweater": "jumper", "attorney": "lawyer",
    "aluminum": "aluminium", "gray": "grey", "math": "maths", "mathematics": "maths", "whiskey": "whisky",
    "bathtub": "bath", "settee": "sofa", "setee": "sofa", "couch": "sofa", "television": "tv",
    "refrigerator": "fridge", "automobile": "car", "physician": "doctor", "mom": "mother", "mum": "mother",
    "mommy": "mother", "mummy": "mother", "dad": "father", "daddy": "father",
    # US/UK spelling
    "meter": "metre", "centimeter": "centimetre", "millimeter": "millimetre", "kilometer": "kilometre",
    "colour": "colour", "color": "colour", "jewelry": "jewellery", "chili": "chilli", "chili pepper": "chilli",
    "chilli pepper": "chilli", "chilli powder": "chilli", "blond": "blonde", "sulfur": "sulphur",
    "pediatrics": "paediatrics", "pediatric": "paediatrics", "paediatric": "paediatrics",
    # short and long forms
    "bike": "bicycle", "pushbike": "bicycle", "push bike": "bicycle", "pedal bike": "bicycle",
    "motorbike": "motorcycle", "kilo": "kilogram", "kg": "kilogram", "gramme": "gram", "lab": "labrador",
    "labrador retriever": "labrador", "alsatian": "german shepherd", "influenza": "flu", "common cold": "cold",
    "tuberculosis": "tb", "covid-19": "covid", "coronavirus": "covid", "covid 19": "covid",
    "obsessive compulsive disorder": "ocd", "bipolar disorder": "bipolar", "general practitioner": "gp",
    "microwave oven": "microwave", "english language": "english", "gull": "seagull", "noon": "midday",
    "tee shirt": "t-shirt", "tshirt": "t-shirt", "make-up": "makeup", "make up": "makeup",
    "one half": "half", "1/2": "half", "a half": "half", "one quarter": "quarter", "1/4": "quarter",
    "one third": "third", "1/3": "third", "3/4": "three quarters", "three-quarters": "three quarters",
    "coughing": "cough", "sneezing": "sneeze",
    # picture labels for "a game" (the singularizer would turn "bros" into "bro")
    "super mario bro": "super mario", "super mario bros": "super mario", "mario": "super mario",
    "super mario bros.": "super mario",
}
# Same-referent names that only hold within one category.
_WATER = {"pacific ocean": "pacific", "atlantic ocean": "atlantic", "indian ocean": "indian",
          "arctic ocean": "arctic", "amazon river": "amazon", "river amazon": "amazon", "nile river": "nile",
          "river nile": "nile", "river thames": "thames", "thames river": "thames",
          "mediterranean sea": "mediterranean"}
_INJURY = {"fracture": "broken bone", "bone fracture": "broken bone"}
# Forms of the same emotion or quality (the norms' referential version merges these, e.g. happiness = happy).
_FEELINGS = {
    "happiness": "happy", "sadness": "sad", "anger": "angry", "jealousy": "jealous", "excitement": "excited",
    "loneliness": "lonely", "anxiety": "anxious", "fearful": "fear", "scared": "fear", "afraid": "fear",
    "frightened": "fear", "joyful": "joy", "joyfulness": "joy", "disgusted": "disgust", "frustration": "frustrated",
    "worry": "worried", "nervousness": "nervous", "depression": "depressed", "love": "love", "hatred": "hate",
    "guilt": "guilty", "shame": "ashamed", "surprised": "surprise", "contentment": "content", "pride": "proud",
    "gratitude": "grateful", "boredom": "bored", "embarrassment": "embarrassed", "stress": "stressed",
}
_QUALITIES = {
    "honesty": "honest", "kindness": "kind", "friendliness": "friendly", "confidence": "confident",
    "loyalty": "loyal", "selfishness": "selfish", "generosity": "generous", "rudeness": "rude", "being rude": "rude",
    "cheerfulness": "cheerful", "helpfulness": "helpful", "intelligence": "intelligent", "arrogance": "arrogant",
    "laziness": "lazy", "greed": "greedy", "greediness": "greedy", "dishonesty": "dishonest", "patience": "patient",
    "compassion": "compassionate", "caringness": "caring", "caring nature": "caring", "gentleness": "gentle",
    "boastfulness": "boastful", "narcissism": "narcissistic", "pessimism": "pessimistic", "optimism": "optimistic",
    "stubbornness": "stubborn", "moodiness": "moody", "harshness": "harsh", "empathy": "empathetic",
    "empathic": "empathetic", "jealousy": "jealous", "anger": "angry", "happiness": "happy", "bravery": "brave",
    "courage": "courageous", "humility": "humble", "liar": "lying", "dishonest": "dishonest", "cruelty": "cruel",
    "impatience": "impatient", "ignorance": "ignorant","creativity": "creative",
    "reliability": "reliable", "integrity": "integrity", "respectfulness": "respectful", "humour": "funny",
    "sense of humour": "funny", "humorous": "funny", "humourous": "funny",
}
_WEATHER = {"rainy": "rain", "raining": "rain", "sunny": "sun", "sunshine": "sun", "snowy": "snow",
            "snowing": "snow", "windy": "wind", "cloudy": "cloud", "foggy": "fog", "stormy": "storm",
            "thunderstorm": "storm", "hailstone": "hail", "hailing": "hail", "drizzly": "drizzle",
            "misty": "mist", "breezy": "breeze"}
_FEELING_CATS = ("emotion", "positive emotion", "negative emotion")
_QUALITY_CATS = ("personal quality", "positive personal quality", "negative personal quality")
CATEGORY_SYNONYMS = {**{c: _FEELINGS for c in _FEELING_CATS}, **{c: _QUALITIES for c in _QUALITY_CATS},
                     "weather": _WEATHER, "body of water": _WATER, "injury": _INJURY}


def synonyms_for(category: str) -> dict[str, str]:
    return {**SYNONYMS, **CATEGORY_SYNONYMS.get(category, {})}


# ---------- answer normalization ----------

# Plurals that are not a plural of something shorter, or whose singular is irregular.
_SINGULAR_KEEP = {
    "glasses", "trousers", "jeans", "shorts", "scissors", "pliers", "tongs", "tweezers", "pants", "tights",
    "news", "physics", "mathematics", "maths", "economics", "politics", "ethics", "athletics", "gymnastics",
    "aerobics", "linguistics", "genetics", "statistics", "classics", "chess", "darts", "billiards", "bowls",
    "species", "series", "measles", "mumps", "rabies", "diabetes", "herpes", "shingles", "rickets", "aids",
    "bus", "gas", "lens", "iris", "virus", "cactus", "octopus", "hippopotamus", "platypus", "walrus", "albatross",
    "asparagus", "hummus", "citrus", "crocus", "hibiscus", "lotus", "narcissus", "papyrus", "fungus", "uterus",
    "chorus", "census", "status", "bonus", "circus", "atlas", "canvas", "christmas", "texas", "lupus", "tetanus",
    "pancreas", "abacus", "thesaurus", "bias", "alias", "dress", "cross", "grass", "glass", "class", "boss",
    "moss", "mass", "brass", "bass", "chess", "kiss", "loss", "stress", "fitness", "sadness", "happiness",
    "kindness", "loneliness", "jealousy", "goodness", "darkness", "illness", "sickness", "witness", "business",
    "princess", "goddess", "actress", "waitress", "duchess", "countess", "empress", "mattress", "fortress",
    "compass", "harness", "walrus", "tennis", "lacrosse", "squash", "polo", "always", "is", "yes", "this",
    "his", "hers", "its", "us", "plus", "minus", "thus", "tuesday", "wednesday", "thursday", "mars", "venus",
    "uranus", "jesus", "zeus", "paris", "swiss", "dutch", "fries", "cress", "watercress", "jodhpurs", "overalls",
    "pyjamas", "pajamas", "binoculars", "headphones", "earphones", "clothes", "dregs", "remains", "thanks",
    "congratulations", "odds", "means", "crossroads", "headquarters", "barracks", "gallows", "innings",
    "electronics", "acoustics", "graphics", "logistics", "robotics", "dynamics", "mechanics", "optics",
    "semantics", "phonetics", "pharmaceutics", "ceramics", "humanities", "biceps", "triceps", "forceps",
    "goggles", "jitters", "blues", "doldrums", "eaves", "tropics", "rapids", "falls", "narrows", "outskirts",
    "mumps", "hiccups", "cards", "dominoes", "marbles", "skittles", "checkers", "draughts", "jacks", "charades",
    "hopscotch", "sweets", "lungs", "bowels", "intestines", "genitals", "abs", "pecs",
}
_SINGULAR_IRREGULAR = {
    "geese": "goose", "mice": "mouse", "lice": "louse", "teeth": "tooth", "feet": "foot", "men": "man",
    "women": "woman", "children": "child", "people": "person", "oxen": "ox", "dice": "die", "cacti": "cactus",
    "fungi": "fungus", "loaves": "loaf", "knives": "knife", "leaves": "leaf", "wolves": "wolf", "calves": "calf",
    "halves": "half", "shelves": "shelf", "thieves": "thief", "wives": "wife", "lives": "life", "elves": "elf",
    "hooves": "hoof", "scarves": "scarf", "potatoes": "potato", "tomatoes": "tomato", "mangoes": "mango",
    "heroes": "hero", "echoes": "echo", "volcanoes": "volcano", "tornadoes": "tornado", "torpedoes": "torpedo",
    "buffaloes": "buffalo", "mosquitoes": "mosquito", "avocados": "avocado", "pianos": "piano", "cellos": "cello",
    "radios": "radio", "kilos": "kilo", "studios": "studio", "rhinos": "rhino", "hippos": "hippo", "photos": "photo",
    "ponies": "pony", "cherries": "cherry", "berries": "berry", "strawberries": "strawberry",
    "blueberries": "blueberry", "raspberries": "raspberry", "daisies": "daisy", "lilies": "lily",
    "puppies": "puppy", "flies": "fly", "butterflies": "butterfly", "ladies": "lady", "babies": "baby",
    "bodies": "body", "parties": "party", "cities": "city", "countries": "country", "families": "family",
    "bodies of water": "body of water", "crises": "crisis", "analyses": "analysis", "axes": "axe",
    "indices": "index", "matrices": "matrix", "vertices": "vertex", "criteria": "criterion",
    "phenomena": "phenomenon", "bacteria": "bacterium", "data": "data", "media": "media", "sheep": "sheep",
    "deer": "deer", "fish": "fish", "salmon": "salmon", "trout": "trout", "cod": "cod", "moose": "moose",
    "aircraft": "aircraft", "spacecraft": "spacecraft", "series": "series", "species": "species",
    "brownies": "brownie", "cookies": "cookie", "movies": "movie", "pies": "pie", "ties": "tie", "lies": "lie",
    "zombies": "zombie", "hippies": "hippie", "calories": "calorie", "prairies": "prairie", "rookies": "rookie",
    "genies": "genie", "pixies": "pixie", "aunties": "auntie", "goalies": "goalie", "selfies": "selfie",
    "beanies": "beanie", "budgies": "budgie", "collies": "collie", "corgis": "corgi", "kiwis": "kiwi",
}
_ES_PLURAL = ("ches", "shes", "sses", "xes", "zzes")  # "-oes" plurals are listed (potatoes); shoes -> shoe


def singular(word: str) -> str:
    """A small rule-based singularizer for single English nouns (lowercase)."""
    w = word
    if w in _SINGULAR_IRREGULAR:
        return _SINGULAR_IRREGULAR[w]
    if len(w) <= 3 or w in _SINGULAR_KEEP or not w.endswith("s"):
        return w
    if w.endswith("es") and w[:-2] in _SINGULAR_KEEP:  # buses, gases, lenses, viruses
        return w[:-2]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith(_ES_PLURAL):
        return w[:-2]
    if w.endswith(("ss", "us", "is", "ous")):
        return w
    return w[:-1]


def singular_phrase(phrase: str) -> str:
    """Singularize the head noun (the last word) of a short phrase: 'golden retrievers' -> 'golden retriever'.
    Whole phrases in the irregular table ('bodies of water') are looked up first."""
    if phrase in _SINGULAR_IRREGULAR or phrase in _SINGULAR_KEEP:
        return _SINGULAR_IRREGULAR.get(phrase, phrase)
    words = phrase.split()
    if not words:
        return phrase
    # "x of y": the head is the first part ("cups of tea" is rare in answers; keep it simple)
    if "of" in words[1:-1]:
        i = words.index("of")
        return " ".join([*words[:i - 1], singular(words[i - 1]), *words[i:]])
    return " ".join([*words[:-1], singular(words[-1])])


_NUMBER_WORDS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
                 "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
                 "thirteen": "13", "seventeen": "17", "nineteen": "19", "twenty-three": "23", "twenty three": "23",
                 "twenty-nine": "29", "thirty-one": "31"}


def clean(text: str) -> str:
    """The first item of an answer, lowercased, without markdown, quotes, articles or punctuation.
    'Robin.' -> 'robin'; '**A robin**' -> 'robin'; 'Apple, banana' -> 'apple'; 'The Owl (Strigiformes)' -> 'owl'."""
    s = unicodedata.normalize("NFKC", text or "").strip()
    s = next((line for line in s.splitlines() if line.strip()), "")
    s = re.sub(r"[*_`\"“”‘]", "", s.replace("’", "'"))
    # a short label before a colon ("Answer: Robin", "1st matching response: Red") is not the answer
    if re.match(r"^\s*(?:\S+\s+){0,3}\S+?:\s*\S", s):
        s = s.split(":", 1)[1]
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)  # parentheticals
    # keep the first item only; "and" is never a separator ("breaking and entering")
    s = re.split(r"[,;:]|\s[-–—]\s|\sor\s|\s/\s", s, maxsplit=1)[0]
    s = s.lower().strip().strip(".!?'").strip()
    s = re.sub(r"'s\b|s'(?=\s|$)", "", s)  # possessives: "alzheimer's" -> "alzheimer"
    s = re.sub(r"^(a|an|the|one|some)\s+(?=\S)", "", s)
    s = re.sub(r"\s+", " ", s)
    return _NUMBER_WORDS.get(s, s)


def normalize(text: str, synonyms: dict[str, str] | None = None) -> str:
    """clean, then singular, then the hand-reviewed synonym map (applied to both the cleaned and the singular
    form). Returns '' for an empty or unusable answer."""
    s = clean(text)
    if not s or len(s) > 40:
        return ""
    syn = synonyms or {}
    if s in syn:
        return syn[s]
    s1 = s if re.fullmatch(r"[\d\s/.]+", s) else singular_phrase(s)
    return syn.get(s1, s1)


def category_head(category: str) -> str | None:
    """The category's head noun: "tree" for "tree", "vehicle" for "four-wheeled vehicle", and the noun before
    the preposition for "room in a house" or "bird of prey" ("room", "bird")."""
    m = re.match(r"^(.*?)\s+(?:of|in)\s+", category)
    if m:
        return singular(m.group(1).split()[-1])
    return singular(category.split()[-1].split("-")[-1])


def category_aliases(category: str, pooled: Counter | dict, preferred: set[str] | frozenset = frozenset()
                     ) -> dict[str, str]:
    """Merge forms of the same answer within one category, from all sources' normalized answers pooled
    (people and every model), so both sides are merged the same way:
    - spacing and hyphens: 'blue bird' = 'bluebird', 't shirt' = 't-shirt';
    - the head noun: 'oak tree' = 'oak' and 'top hat' = 'top' when both forms occur (the norms' trial data
      often drop the head: 'pine' for pine nut).
    Each group is named by a `preferred` form if it has one (the norms' own referential member names, so
    'top hat' and 'pine nut' but 'beef', not 'beef meat'), then by a form with the head noun, then by its most
    frequent pooled form (ties: the longer, then alphabetical). Returns
    {form: canonical} for every form that changes."""
    head = category_head(category)
    parent: dict[str, str] = {}

    def find(k):
        while parent.get(k, k) != k:
            k = parent[k]
        return k

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    keys = [k for k in pooled if k]
    for k in keys:
        parent.setdefault(k, k)
    by_join: dict[str, str] = {}
    for k in keys:
        j = re.sub(r"[\s\-']", "", k)
        if j in by_join:
            union(by_join[j], k)
        else:
            by_join[j] = k
    with_head = set()
    if head:
        for k in keys:
            if k.endswith(" " + head) and (short := k[: -len(head) - 1].strip()) in pooled:
                union(short, k)
                with_head.add(k)
    groups: dict[str, list[str]] = {}
    for k in keys:
        groups.setdefault(find(k), []).append(k)
    out = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        canon = sorted(members, key=lambda m: (m not in preferred, m not in with_head, -pooled[m], -len(m), m))[0]
        out.update({m: canon for m in members if m != canon})
    return out


# ---------- concentration measures ----------

def counts_of(answers) -> Counter:
    return Counter(a for a in answers if a)


def dominance(counts: Counter | dict) -> float:
    """Share of the most common answer (the top answer's share)."""
    n = sum(counts.values())
    return max(counts.values()) / n if n else float("nan")


def entropy_bits(counts: Counter | dict) -> float:
    """Plug-in Shannon entropy of the answer distribution, in bits (0 = everyone gives the same answer)."""
    n = sum(counts.values())
    if not n:
        return float("nan")
    p = np.array([c for c in counts.values() if c > 0], float) / n
    return float(-(p * np.log2(p)).sum()) + 0.0


def match_probability(counts: Counter | dict) -> float:
    """Unbiased chance that two different answers are the same: sum c(c-1) / n(n-1) (Simpson's concentration).
    Unlike dominance and plug-in entropy it does not depend on n, so it compares 20 people with 50 samples."""
    n = sum(counts.values())
    if n < 2:
        return float("nan")
    return float(sum(c * (c - 1) for c in counts.values()) / (n * (n - 1)))


def top_answers(counts: Counter | dict) -> list[str]:
    """All answers tied for the most common, sorted."""
    if not counts:
        return []
    m = max(counts.values())
    return sorted(a for a, c in counts.items() if c == m)


def measures(answers) -> dict:
    c = counts_of(answers)
    return {"n": sum(c.values()), "dominance": dominance(c), "entropy_bits": entropy_bits(c), "distinct": len(c),
            "match_probability": match_probability(c), "top": top_answers(c)}


def equal_n(answers, n: int, reps: int = 1000, rng: np.random.Generator | None = None) -> dict:
    """Dominance, entropy and distinct answers of random n-answer subsets (without replacement), averaged:
    the AI's 50 answers at the human sample size, so small-sample bias is the same on both sides."""
    rng = rng or np.random.default_rng(0)
    a = np.array([x for x in answers if x], dtype=object)
    if len(a) == 0 or n < 1:
        return {"n": n, "dominance": float("nan"), "entropy_bits": float("nan"), "distinct": float("nan")}
    n = min(n, len(a))
    _, codes = np.unique(a.astype(str), return_inverse=True)
    dom, ent, dis = [], [], []
    for _ in range(reps):
        cnt = np.bincount(codes[rng.choice(len(a), n, replace=False)])
        cnt = cnt[cnt > 0]
        p = cnt / n
        dom.append(cnt.max() / n)
        ent.append(float(-(p * np.log2(p)).sum()))
        dis.append(len(cnt))
    return {"n": n, "dominance": float(np.mean(dom)), "entropy_bits": float(np.mean(ent)) + 0.0,
            "distinct": float(np.mean(dis))}


def from_probs(probs: dict[str, float], n: int, reps: int = 1000, rng: np.random.Generator | None = None) -> dict:
    """The same equal-n measures for n draws from a probability distribution (Glimmer's logit distribution)."""
    rng = rng or np.random.default_rng(0)
    keys = list(probs)
    p = np.array([probs[k] for k in keys], float)
    p = p / p.sum()
    draws = [[keys[i] for i in rng.choice(len(keys), n, p=p)] for _ in range(reps)]
    ms = [measures(d) for d in draws]
    return {"n": n, "dominance": float(np.mean([m["dominance"] for m in ms])),
            "entropy_bits": float(np.mean([m["entropy_bits"] for m in ms])),
            "distinct": float(np.mean([m["distinct"] for m in ms]))}


def exact_measures(probs: dict[str, float]) -> dict:
    """Population measures of a probability distribution: top probability, entropy (bits), match probability."""
    p = np.array([v for v in probs.values() if v > 0], float)
    p = p / p.sum()
    top = max(probs, key=probs.get) if probs else None
    return {"dominance": float(p.max()), "entropy_bits": float(-(p * np.log2(p)).sum()) + 0.0,
            "match_probability": float((p ** 2).sum()), "top": top}


def tempered(probs: dict[str, float], temperature: float) -> dict[str, float]:
    """Re-weight a distribution as sampling at another temperature would: p_T proportional to p ** (1/T)."""
    keys = [k for k, v in probs.items() if v > 0]
    logp = np.log(np.array([probs[k] for k in keys], float)) / temperature
    logp -= logp.max()
    w = np.exp(logp)
    w /= w.sum()
    return dict(zip(keys, w.tolist()))


# ---------- statistics over categories ----------

def bootstrap_mean_ci(x, reps: int = 10000, rng: np.random.Generator | None = None, level: float = 0.95) -> dict:
    """Mean over categories with a percentile bootstrap CI (resampling categories)."""
    rng = rng or np.random.default_rng(0)
    x = np.asarray([v for v in x if v == v], float)
    if not len(x):
        return {"mean": float("nan"), "ci95": [float("nan"), float("nan")], "n": 0}
    boots = x[rng.integers(0, len(x), (reps, len(x)))].mean(1)
    a = (1 - level) / 2
    return {"mean": float(x.mean()), "ci95": [float(np.quantile(boots, a)), float(np.quantile(boots, 1 - a))],
            "n": int(len(x))}


def bootstrap_group_diff(x, groups, a: str, b: str, reps: int = 10000,
                         rng: np.random.Generator | None = None) -> dict:
    """Mean of x in group a minus mean in group b, with a bootstrap CI that resamples within each group."""
    rng = rng or np.random.default_rng(0)
    x, g = np.asarray(x, float), np.asarray(groups)
    xa, xb = x[(g == a) & ~np.isnan(x)], x[(g == b) & ~np.isnan(x)]
    ba = xa[rng.integers(0, len(xa), (reps, len(xa)))].mean(1)
    bb = xb[rng.integers(0, len(xb), (reps, len(xb)))].mean(1)
    d = ba - bb
    return {"diff": float(xa.mean() - xb.mean()), "ci95": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))],
            "n": [int(len(xa)), int(len(xb))]}


def safe_float(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return float("nan")
    return f if math.isfinite(f) else float("nan")

"""Scorer: automatic first-pass scores for three picture-based language tasks. A person reviews them.

Picture naming
  The rule-based coder (naming_errors.classify) gives the first code. second_rater has Muse Spark
  code the same response independently, from written category definitions only (it never sees
  the first code), and agreement() reports percent agreement and Cohen's kappa between the two.
  The rater can also code Visual errors (a real word for something that looks like the picture),
  which need the picture and which the rule-based coder can't detect.

Picture description
  make_scene: Muse Spark writes an original scene brief (several people, objects and actions, a
  small mishap to talk about; nothing copied from existing tests such as the Cookie Theft
  picture), Muse Image draws it, and Muse Spark looks at the finished picture to list 10-20
  content units (key people, objects and actions) in the test language. The units come from the
  picture as drawn, not from the brief, so they only name what is really there.
  score_description: words and words per minute from the transcript, and the content units the
  speaker mentioned (Muse Spark matches paraphrases and synonyms), after the content-unit
  analyses of Yorkston & Beukelman (1980).

Category fluency
  score_fluency: the transcript is split into stretches at punctuation and conjunctions, and
  fillers and articles are dropped. Muse Spark judges every new stretch in one batched call: it
  lists the items in it (usually one; several when the speaker didn't pause and the transcript
  has no commas; none for a remark such as "let me think") and marks each item a member of the
  category (valid) or not (intrusion). Items are compared after normalizing case, accents,
  articles and plurals, so "Dogs" after "the dog" is a repetition.

Every Muse Spark answer is cached on disk under runs/cache/, keyed by a prompt version, so a
prompt change re-asks and a repeated call costs nothing. Scores are for research and teaching;
they are not a diagnosis.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path

from openai import BadRequestError
from PIL import Image

from metalesionlab.meta_api import REPO_ROOT, image_data_url
from metalesionlab.naming_errors import ARTICLES as NAMING_ARTICLES
from metalesionlab.naming_errors import LANGUAGE_NAMES, _strip_accents, _wordnet, tokens

CATEGORIES = ("Correct", "Semantic", "Formal", "Mixed", "Unrelated", "Nonword", "Neologism",
              "Description", "NoResponse", "Visual")

SECOND_RATER_PROMPT_VERSION = 1
SCENE_PROMPT_VERSION = 2
DESCRIPTION_PROMPT_VERSION = 2
FLUENCY_PROMPT_VERSION = 1

CACHE_DIR = REPO_ROOT / "runs" / "cache"
SCENE_DIR = REPO_ROOT / "runs" / "scenes"
SCENE_SIZE = "1536x1024"  # landscape, like printed description pictures
SCENE_SAVE_SIDE = 1280  # stored size; Muse Spark sees 1024 px
RATER_IMAGE_SIDE = 512

ARTICLES = {**NAMING_ARTICLES, "fr": {"le", "la", "les", "l", "un", "une", "des", "du", "de"}}
CONJUNCTIONS = {"en": {"and", "or", "then"}, "es": {"y", "e", "o", "u", "luego"}, "fr": {"et", "ou", "puis"}}
# Words people put between list items that are not part of an item.
LIST_FILLERS = {"en": {"also", "maybe", "oh", "ok", "okay", "another", "like", "so", "well"},
                "es": {"también", "tambien", "bueno", "pues", "otro", "otra", "eh", "mmm", "ah"},
                "fr": {"aussi", "euh", "bon", "alors", "ben"}}


def _language(lang: str) -> str:
    return LANGUAGE_NAMES.get(lang, lang)


def _json_from(text: str):
    match = re.search(r"[\[{].*[\]}]", text or "", re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _ask(api, content, reasoning_effort: str = "minimal") -> str:
    reply = api.chat([{"role": "user", "content": content}], reasoning_effort=reasoning_effort)
    return reply.choices[0].message.content or ""


def _png(image: bytes, side: int) -> bytes:
    img = Image.open(io.BytesIO(image)).convert("RGB")
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _digest(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()[:16]


class _JsonCache:
    """A small JSON file of answers, shared by threads in one process."""

    def __init__(self, name: str):
        self.name = name
        self._data: dict | None = None
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return CACHE_DIR / f"{self.name}.json"

    def _load(self) -> dict:
        if self._data is None:
            self._data = json.loads(self.path.read_text()) if self.path.exists() else {}
        return self._data

    def get(self, key: str):
        with self._lock:
            return self._load().get(key)

    def update(self, entries: dict) -> None:
        with self._lock:
            data = self._load()
            data.update(entries)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=0))
            tmp.replace(self.path)


_rater_cache = _JsonCache("second_rater")
_description_cache = _JsonCache("description_units")
_fluency_cache = _JsonCache("fluency_judge")


# --- picture naming: Muse Spark as second rater ----------------------------------------

_RATER_PROMPT = """\
You are the second rater for a picture-naming test in {language}. Code one response with exactly one \
category. Go through the categories in this order and use the first that applies.

1. NoResponse: nothing, a refusal ("I don't know") or only fillers ("um").
2. Correct: the target or an accepted synonym or alternate name, allowing articles, plurals and \
modifiers ("two red apples" for apple).
3. Description: three or more words that talk about the target without naming it ("you sit on it" for chair).
4. If the response is a real word of {language} (judge its head noun):
   - Related in meaning: a synonym; a member of the same category, even a broad one such as animals, \
foods, tools, clothing, furniture, body parts or vehicles; a category name; a part or whole; or a \
strong associate (bone for dog).
   - Related in sound: the two share the first sound, the last sound or the stressed vowel, or have \
at least two sounds in common anywhere.{sound_note}
   - Mixed: related in meaning and in sound (trumpet for trombone).
   - Semantic: related in meaning only (fork for spoon).
   - Formal: related in sound only (moon for spoon).
   - Visual: {visual_rule}
   - Unrelated: none of these.
5. If the response is not a real word of {language}:
   - Nonword: related in sound to the target, as defined above ("tebel" for table).
   - Neologism: not related in sound ("glimp" for table).

The response is an automatic transcript, so ignore punctuation and capitals.
Target: {target}
Response: "{response}"

Reply with only JSON: {{"code": "<category>", "rationale": "<one short sentence>"}}"""

_SPANISH_SOUND_NOTE = (" Most Spanish nouns end in a gender vowel, so a shared final -o or -a alone, or as one "
                       "of the two shared sounds, does not count.")
_VISUAL_WITH_PICTURE = ("a real word for something that looks like the object in the attached picture of the "
                        "target but is not related in meaning (moon for a drawing of a cookie). Check this "
                        "before Formal and Unrelated.")
_VISUAL_WITHOUT_PICTURE = "do not use; no picture is attached."


def second_rater(api, target: str, response: str, lang: str, image: bytes | None = None) -> dict:
    """Muse Spark codes a naming response on its own: {"code": category or "Visual", "rationale": text}."""
    image_key = hashlib.sha1(image).hexdigest()[:16] if image else "-"
    key = f"v{SECOND_RATER_PROMPT_VERSION}|{lang}|{target}|{response}|{image_key}"
    if (hit := _rater_cache.get(key)) is not None:
        return dict(hit)
    prompt = _RATER_PROMPT.format(
        language=_language(lang), target=target, response=response,
        sound_note=_SPANISH_SOUND_NOTE if lang == "es" else "",
        visual_rule=_VISUAL_WITH_PICTURE if image else _VISUAL_WITHOUT_PICTURE)
    content = ([{"type": "image_url", "image_url": {"url": image_data_url(_png(image, RATER_IMAGE_SIDE))}},
                {"type": "text", "text": prompt}] if image else prompt)
    for effort in ("minimal", "low"):  # one retry, with more thought, if the reply can't be read
        text = _ask(api, content, effort)
        result = _parse_rater_reply(text)
        if result:
            _rater_cache.update({key: result})
            return dict(result)
    raise ValueError(f"second rater reply has no category: {text[:200]!r}")


def _parse_rater_reply(text: str) -> dict | None:
    by_lower = {c.lower(): c for c in CATEGORIES}
    obj = _json_from(text)
    if isinstance(obj, dict):
        code = by_lower.get(str(obj.get("code", "")).strip().lower().replace(" ", ""))
        if code:
            return {"code": code, "rationale": str(obj.get("rationale", "")).strip()}
    found = re.findall(r"\b(" + "|".join(CATEGORIES) + r")\b", text or "")
    return {"code": found[0], "rationale": ""} if found else None


def agreement(codes_a: list[str], codes_b: list[str]) -> dict:
    """Percent agreement and Cohen's kappa between two raters' codes for the same items.
    Kappa is None when it is undefined (no items, or both raters used one same code throughout)."""
    if len(codes_a) != len(codes_b):
        raise ValueError(f"{len(codes_a)} codes vs {len(codes_b)}")
    n = len(codes_a)
    if n == 0:
        return {"n": 0, "percent": None, "kappa": None}
    observed = sum(a == b for a, b in zip(codes_a, codes_b)) / n
    count_a, count_b = Counter(codes_a), Counter(codes_b)
    expected = sum(count_a[c] * count_b[c] for c in count_a) / (n * n)
    kappa = None if expected == 1 else (observed - expected) / (1 - expected)
    return {"n": n, "percent": round(100 * observed, 1), "kappa": None if kappa is None else round(kappa, 3)}


# --- picture description ---------------------------------------------------------------

_SCENE_BRIEF = """\
Write a brief for an image model that will draw an original picture for a picture-description \
language test: the person looks at the picture and tells everything that is happening.
Setting: {setting}.
The picture needs 3 to 5 people of different ages doing different, clearly visible everyday \
actions; about 12 to 15 easily named objects; and one or two small mishaps or surprises that \
invite comment. It must be new: do not copy or echo any existing test picture (for example, no \
boy on a tipping stool taking cookies while a sink overflows, as in the Cookie Theft picture). \
Everything should be easy to name in any language and culture, and there must be no writing, \
letters, numbers, signs, logos, screens with text, books with visible titles or clocks.
Reply with only JSON: {{"setting": "<a few English words>", "brief": "<the image prompt, in English, \
under 120 words>"}}"""

_SCENE_STYLE = (" Style: a clear, friendly flat-color illustration with clean dark outlines, a wide view of the "
                "whole scene, every person and object easy to make out. Absolutely no text, letters, numbers, "
                "signs or logos anywhere in the picture.")

_SCENE_UNITS = """\
This picture is for a picture-description test in {language}: the person looks at it and tells \
everything that is happening. List its content units, the key people, objects and actions a full \
description would mention.
- 10 to 20 units, most important first.
- Each unit is one idea, as a short phrase in {language}: one person or object (like "the boy" or \
"the dog"), or one action (like "the boy is climbing the tree"). Never combine several objects in \
one unit ("a blanket with a bag and an apple" is three units), and leave out colors and other \
details unless they are needed to tell two things apart.
- Include only what is clearly visible, and name each thing as most speakers would; if you are \
not sure what something is, leave it out.
Also write a two-sentence description of the scene in {language}, and say whether any writing, \
letters or numbers appear anywhere in the picture.
Reply with only JSON: {{"description": "...", "content_units": ["...", ...], "has_text": true or false}}"""


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _strip_accents(text.lower())).strip("-")[:30] or "scene"


def _scene_units(api, image: bytes, lang: str) -> dict:
    """Muse Spark's description, content units and text check for a drawn scene."""
    content = [{"type": "image_url", "image_url": {"url": image_data_url(_png(image, 1024))}},
               {"type": "text", "text": _SCENE_UNITS.format(language=_language(lang))}]
    for effort in ("low", "medium"):  # one retry, with more thought, if the reply can't be read
        reply = _json_from(_ask(api, content, effort))
        if isinstance(reply, dict) and isinstance(reply.get("content_units"), list) and reply["content_units"]:
            return reply
    raise ValueError("Muse Spark returned no content units for the scene")


def make_scene(api, lang: str, theme: str | None = None, out_dir: Path | None = None) -> dict:
    """Draw a new scene for picture description and list its content units in `lang`.

    Returns {"id", "image_file" (absolute path of the PNG), "description", "content_units", ...}
    and writes <id>.png and <id>.json to out_dir (default runs/scenes/)."""
    out_dir = Path(out_dir or SCENE_DIR).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    setting = theme or "your choice of a familiar everyday place, such as a park, a market, a beach or a busy street"
    plan = _json_from(_ask(api, _SCENE_BRIEF.format(setting=setting), "low")) or {}
    brief = str(plan.get("brief") or f"A busy everyday scene: {theme or 'a park on a sunny afternoon'}, "
                                      "with several people doing different things.")
    prompt = brief + _SCENE_STYLE

    for attempt in range(2):  # redraw once if writing shows up in the picture
        try:
            image = api.generate_images(prompt, size=SCENE_SIZE)[0]
        except BadRequestError:  # size rejected: fall back to the default square
            image = api.generate_images(prompt)[0]
        saved = _png(image, SCENE_SAVE_SIDE)
        units_reply = _scene_units(api, image, lang)
        if not units_reply.get("has_text"):
            break

    units = [str(u).strip() for u in units_reply["content_units"] if str(u).strip()]
    stamp = f"{time.strftime('%Y%m%d-%H%M%S')}-{_digest(prompt, time.time())[:4]}"
    scene_id = f"{lang}_{_slug(plan.get('setting') or theme or 'scene')}_{stamp}"
    image_file = out_dir / f"{scene_id}.png"
    image_file.write_bytes(saved)
    scene = {
        "id": scene_id, "image_file": str(image_file),
        "description": str(units_reply.get("description") or "").strip(),
        "content_units": units[:20],
        "lang": lang, "theme": theme, "setting": plan.get("setting"), "prompt": prompt,
        "has_text": bool(units_reply.get("has_text")), "draws": attempt + 1,
        "prompt_version": SCENE_PROMPT_VERSION,
    }
    (out_dir / f"{scene_id}.json").write_text(json.dumps(scene, ensure_ascii=False, indent=1))
    return scene


_DESCRIPTION_MATCH = """\
Score a spoken picture description against the picture's content units. Check each unit on its \
own; one sentence can cover several units. Be generous with wording and strict with meaning:
- A unit is mentioned if the speaker conveys its main idea in any wording. Synonyms, paraphrases, \
clear pronouns and near descriptions of the same person, animal or thing count ("a man" for "the \
father", "a kitten" for "the cat", "racing along on his bike" for "the boy rides a bicycle").
- Details inside a unit, such as an exact number, a color or a place, need not be said ("some \
birds" counts for "two birds on the fence").
- For an action unit, the action must be described; naming only who does it is not enough.
- A unit the speaker gets wrong (a cat for the dog) or never mentions is not mentioned.
The transcript comes from speech recognition, so ignore spelling, punctuation and fillers.
Language: {language}
Content units:
{units}
Transcript: "{transcript}"
Reply with only JSON: {{"mentioned": [unit numbers]}}"""


def score_description(api, transcript: str, scene: dict, lang: str, duration_s: float | None = None) -> dict:
    """Words, words per minute and content units for one picture description."""
    words = len(tokens(transcript or ""))
    units = list(scene.get("content_units") or [])
    mentioned_idx: set[int] = set()
    if words and units:
        key = f"v{DESCRIPTION_PROMPT_VERSION}|{lang}|{_digest(units, transcript.strip())}"
        cached = _description_cache.get(key)
        if cached is None:
            listing = "\n".join(f"{i}. {u}" for i, u in enumerate(units, 1))
            reply = _json_from(_ask(api, _DESCRIPTION_MATCH.format(
                language=_language(lang), units=listing, transcript=transcript.strip()))) or {}
            raw = reply.get("mentioned") if isinstance(reply, dict) else None
            if not isinstance(raw, list):
                raise ValueError("description scorer reply has no 'mentioned' list")
            cached = sorted({int(i) for i in raw if str(i).isdigit() and 1 <= int(i) <= len(units)})
            _description_cache.update({key: cached})
        mentioned_idx = {i - 1 for i in cached}
    minutes = duration_s / 60 if duration_s else None
    mentioned = [u for i, u in enumerate(units) if i in mentioned_idx]
    return {
        "words": words,
        "words_per_min": round(words / minutes, 1) if minutes else None,
        "content_units_mentioned": mentioned,
        "content_units_missed": [u for i, u in enumerate(units) if i not in mentioned_idx],
        "cu_count": len(mentioned),
        "cu_per_min": round(len(mentioned) / minutes, 2) if minutes else None,
    }


# --- category fluency ------------------------------------------------------------------

def _singular(word: str, lang: str) -> str:
    """Singular form for comparison. Spanish gets a stem that singular and plural share, because
    -es can belong to the stem or the plural (tigre/tigres, león/leones): both lose a final -s and
    then a final -e after a consonant (tigr, leon)."""
    if lang == "en":
        # WordNet keeps some plurals as lemmas ("cows", "oxen", "tigers"), so prefer another base form.
        bases = _wordnet()._morphy(word, "n") if len(word) > 3 else []
        if others := [b for b in bases if b != word]:
            return others[0]
        if bases:
            return word  # a noun with no other base form: "news", "sheep"
        if word.endswith("ies") and len(word) > 4:
            return word[:-3] + "y"
        if re.search(r"(s|x|z|ch|sh)es$", word):
            return word[:-2]
        if word.endswith("s") and not word.endswith(("ss", "us", "is")) and len(word) > 3:
            return word[:-1]
        return word
    if lang == "es":
        w = _strip_accents(word)
        if w.endswith("ces") and len(w) > 4:
            return w[:-3] + "z"  # peces -> pez
        if w.endswith("s") and len(w) > 3:
            w = w[:-1]
        if w.endswith("e") and len(w) > 3 and w[-2] not in "aeiou":
            w = w[:-1]
        return w
    if lang == "fr":
        if word.endswith("aux") and len(word) > 4:
            return word[:-3] + "al"  # chevaux -> cheval
        if word.endswith(("s", "x")) and len(word) > 3:
            return word[:-1]
    return word


def _item_words(text: str, lang: str) -> list[str]:
    if lang == "fr":
        text = re.sub(r"\b([ldj])['’]", r"\1 ", text, flags=re.I)  # l'éléphant -> l éléphant
    drop = ARTICLES.get(lang, set()) | LIST_FILLERS.get(lang, set())
    return [w for w in tokens(text) if w not in drop]


def normalize_item(text: str, lang: str) -> str:
    """Comparison key for a fluency item, ignoring case, accents, articles and plurals
    ("The Dogs" -> "dog", "los leones" -> "leon")."""
    return _strip_accents(" ".join(_singular(w, lang) for w in _item_words(text, lang)))


def split_chunks(transcript: str, lang: str) -> list[str]:
    """Stretches of a fluency transcript between pauses: split at punctuation and conjunctions
    ("and", "y"), with fillers and articles removed. Usually one item each; a stretch spoken
    without pauses can hold several, which the judge separates."""
    joiners = CONJUNCTIONS.get(lang, set())
    chunks = []
    for piece in re.split(r"[,.;:!?¿¡\n，。、；：！？…।]+", transcript or ""):  # with Chinese and Hindi marks
        current: list[str] = []
        for w in piece.split() + [None]:
            if w is None or _strip_accents(w.lower().strip("'\"-")) in joiners:
                if cleaned := " ".join(_item_words(" ".join(current), lang)):
                    chunks.append(cleaned)
                current = []
            else:
                current.append(w)
    return chunks


_FLUENCY_JUDGE = """\
Category fluency test in {language}. The person named as many examples of this category as they \
could in 60 seconds: {category}.
Below is what they said, in numbered stretches from automatic speech recognition (allow odd \
spelling). For each stretch, list the items it contains, copying each item's words as transcribed \
and keeping multi-word names together ("polar bear"). Usually a stretch is one item; one spoken \
without pauses can hold several. A remark that is not an attempt at an item ("let me think", \
"that's all") contains no items.
Mark each item valid if it is a real member of the category (any specific kind counts, such as a \
breed), or not valid if it is not (an intrusion).
Stretches:
{chunks}
Reply with only JSON: {{"stretches": {{"<number>": [{{"item": "...", "valid": true or false}}, ...], ...}}}}"""


def score_fluency(api, transcript: str, category: str, lang: str) -> dict:
    """Valid unique items, repetitions and intrusions in a category-fluency transcript.

    Lists hold items as said (first occurrence for valid and intrusions). A repeated intrusion
    appears under both. Extra key "items" lists every item in order with its comparison key and
    status (valid, repetition, intrusion or comment) for the reviewer."""
    chunks = split_chunks(transcript, lang)
    cat_key = normalize_item(category, lang) or category.strip().lower()
    # Stretches with the same key ("dog", "the dogs") share one judgment.
    chunk_key = {c: normalize_item(c, lang) or c for c in chunks}
    cache_key = {k: f"v{FLUENCY_PROMPT_VERSION}|{lang}|{cat_key}|{k}" for k in chunk_key.values()}
    found = {k: _fluency_cache.get(ck) for k, ck in cache_key.items()}
    todo = [k for k, v in found.items() if v is None]
    if todo:
        first_said = {}
        for c in chunks:
            first_said.setdefault(chunk_key[c], c)
        listing = "\n".join(f"{i}. {first_said[k]}" for i, k in enumerate(todo, 1))
        reply = _json_from(_ask(api, _FLUENCY_JUDGE.format(
            language=_language(lang), category=category, chunks=listing))) or {}
        raw = reply.get("stretches") if isinstance(reply, dict) else None
        if not isinstance(raw, dict):
            raise ValueError("fluency judge reply has no 'stretches'")
        new = {}
        for i, k in enumerate(todo, 1):
            entries = raw.get(str(i))
            if isinstance(entries, list):
                found[k] = [[str(e.get("item", "")).strip(), bool(e.get("valid"))]
                            for e in entries if isinstance(e, dict) and str(e.get("item", "")).strip()]
                new[cache_key[k]] = found[k]
            else:
                found[k] = [[first_said[k], False]]  # unjudged: flagged as an intrusion for review, not cached
        _fluency_cache.update(new)

    seen: set[str] = set()
    items, valid, repetitions, intrusions = [], [], [], []
    for c in chunks:
        judged = found[chunk_key[c]]
        if not judged:
            items.append({"text": c, "key": "", "status": "comment"})
            continue
        if len(judged) == 1 and normalize_item(judged[0][0], lang) == chunk_key[c]:
            judged = [[c, judged[0][1]]]  # show it as this person said it ("dogs", not a cached "dog")
        for text, is_valid in judged:
            key = normalize_item(text, lang) or text.lower()
            if key in seen:
                status = "repetition"
                repetitions.append(text)
            else:
                status = "valid" if is_valid else "intrusion"
                (valid if is_valid else intrusions).append(text)
                seen.add(key)
            items.append({"text": text, "key": key, "status": status})
    return {"count": len(valid), "valid": valid, "repetitions": repetitions, "intrusions": intrusions,
            "items": items}

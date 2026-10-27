"""Test Studio: turn a word list into a checked picture-naming set, in any language.

For each word:
  1. Muse Spark plans the picture: an English gloss for SAM, a description to draw, and a flag
     for words that name more than one picturable thing ("banco": bench or bank).
  2. Muse Image draws candidates in one consistent style.
  3. SAM 3.1 checks that the picture holds exactly one clear object.
  4. Muse Spark names the picture in the test's language; the name is scored with the
     naming-error classifier, so agreement means the same thing as a correct response.
The best candidate that passes every check is kept, with its norms, in manifest.json.
"""
from __future__ import annotations

import io
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image

from metalesionlab.meta_api import MetaAPI, image_data_url
from metalesionlab.naming_errors import LANGUAGE_NAMES, classify, phonemes, spark_semantic_judge, word_zipf

STYLES = {
    "line": ("A simple black-and-white line drawing of {depiction}, centered on a plain white background. "
             "Clean dark outlines, no shading, no color, no text, no other objects, nothing cut off at the edges."),
    "color": ("A simple flat color illustration of {depiction}, centered on a plain white background. "
              "Clear shapes, no text, no other objects, nothing cut off at the edges."),
}
SAM_MIN_CONFIDENCE = 0.5
SAM_AREA_RANGE = (0.05, 0.95)  # fraction of the picture the object's box covers
SAVE_SIDE = 1024  # stored size; models get 512 px


@dataclass
class Concept:
    word: str
    hint: str = ""
    gloss: str = ""
    depiction: str = ""
    ambiguous: bool = False
    other_meanings: list[str] = field(default_factory=list)
    alternates: list[str] = field(default_factory=list)  # other spellings of the same word, accepted as correct


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def parse_word_list(lines: list[str]) -> list[Concept]:
    """One word per line; an optional hint after a colon disambiguates ("banco: bench")."""
    out = []
    for line in lines:
        if line.strip():
            word, _, hint = line.partition(":")
            out.append(Concept(_nfc(word).strip().lower(), hint.strip()))
    return out


def _json_from(text: str):
    match = re.search(r"[\[{].*[\]}]", text, re.S)
    return json.loads(match.group(0)) if match else None


def plan_concepts(api: MetaAPI, concepts: list[Concept], lang: str) -> list[Concept]:
    # One object, no colors (Oct 26): Chinese 手套 doesn't mark number and was planned as "a pair of
    # gloves", which SAM rightly counts as two objects; "an orange carrot" put color into line drawings.
    listing = "\n".join(f"- {c.word}" + (f" (meaning: {c.hint})" if c.hint else "") for c in concepts)
    prompt = (
        f"You are preparing pictures for a picture-naming test in {LANGUAGE_NAMES.get(lang, lang)}. "
        "For each word below give:\n"
        '- "gloss": one English noun for the intended object (follow the meaning hint when given)\n'
        '- "depiction": a short English phrase describing one typical, easy-to-recognize example to draw, '
        'starting with "a" or "an" and naming the object plainly ("a carrot with its leafy top"). Exactly one '
        'object, never a pair or a group, even when the word is plural or doesn\'t mark number (one glove, '
        'not gloves). Don\'t mention colors.\n'
        '- "ambiguous": true if the word also commonly names a different picturable thing\n'
        '- "other_meanings": those other meanings in English (empty list if none)\n'
        '- "spellings": other ways the SAME word is commonly written, which a speech transcript might '
        'produce: variant spellings, and for a loanword its spelling in the source language (Hindi '
        'कैक्टस -> "cactus"). Never synonyms or different words. Empty list if none.\n'
        'Return only JSON: {"items": [{"word": ..., "gloss": ..., "depiction": ..., "ambiguous": ..., '
        '"other_meanings": [...], "spellings": [...]}]} in the same order.\n\nWords:\n' + listing)
    reply = api.chat([{"role": "user", "content": prompt}], reasoning_effort="low")
    items = (_json_from(reply.choices[0].message.content) or {}).get("items", [])
    by_word = {_nfc(str(it.get("word", ""))).strip().lower(): it for it in items if isinstance(it, dict)}
    in_order = len(items) == len(concepts)
    for k, c in enumerate(concepts):
        # By word, else by position: a reply may spell a Devanagari or accented word differently.
        it = by_word.get(c.word) or (items[k] if in_order and isinstance(items[k], dict) else {})
        c.gloss = it.get("gloss") or c.hint or c.word
        c.depiction = it.get("depiction") or f"a {c.gloss}"
        c.ambiguous = bool(it.get("ambiguous"))
        c.other_meanings = list(it.get("other_meanings") or [])
        spellings = (_nfc(str(s)).strip().lower() for s in (it.get("spellings") or []) if isinstance(s, str))
        c.alternates = list(dict.fromkeys(s for s in spellings if s and s != c.word and len(s) <= 40))[:5]
    return concepts


# Oct 27: asked for "exactly one word", Muse Spark cut Vietnamese names to one syllable (mỏ neo -> "neo",
# ghế dài -> "ghế") or ran them together ("càrốt", and Indonesian "sarungtangan").
NAME_NOTES = {
    "vi": " A Vietnamese name may have two or more syllables (xe đạp); give all of them, without a classifier.",
    "id": " If the usual name is two words (sarung tangan), give both.",
}


def naming_prompt(lang: str) -> str:
    """What Muse Spark is asked when it names a candidate picture in the test's language."""
    return (f"Name the object in this picture with exactly one word in {LANGUAGE_NAMES.get(lang, lang)}."
            f"{NAME_NOTES.get(lang, '')} Reply with the word only.")


def _resized_png(image: bytes, side: int) -> bytes:
    img = Image.open(io.BytesIO(image)).convert("RGB")
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def check_candidate(api: MetaAPI, image: bytes, concept: Concept, lang: str, judge) -> dict:
    matches, _ = api.segment(image, concept.gloss)
    confident = [m for m in matches if (m.confidence or 0) >= SAM_MIN_CONFIDENCE]
    area = confident[0].area_fraction if len(confident) == 1 else None
    sam_ok = area is not None and SAM_AREA_RANGE[0] <= area <= SAM_AREA_RANGE[1]

    small = _resized_png(image, 512)
    reply = api.chat([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": image_data_url(small)}},
        {"type": "text", "text": naming_prompt(lang)},
    ]}])
    spark_name = reply.choices[0].message.content.strip()
    spark_code = classify(concept.word, spark_name, lang, alternates=tuple(concept.alternates), judge=judge).code
    return {
        "sam_objects": len(confident),
        "sam_confidence": round(confident[0].confidence, 3) if confident else None,
        "sam_area": round(area, 3) if area is not None else None,
        "sam_ok": sam_ok,
        "spark_name": spark_name,
        "spark_code": spark_code,
        "spark_ok": spark_code == "Correct",
    }


def build_set(words: list[str], lang: str, out_dir: Path, style: str = "line", candidates: int = 2,
              workers: int = 8, api: MetaAPI | None = None) -> dict:
    api = api or MetaAPI()
    judge = spark_semantic_judge(api)
    concepts = plan_concepts(api, parse_word_list(words), lang)
    (out_dir / "candidates").mkdir(parents=True, exist_ok=True)

    def run(concept: Concept) -> dict:
        prompt = STYLES[style].format(depiction=concept.depiction)
        results = []
        for k, image in enumerate(api.generate_images(prompt, n=candidates)):
            path = out_dir / "candidates" / f"{concept.word}_{k}.png"
            path.write_bytes(_resized_png(image, SAVE_SIDE))
            results.append({"file": str(path.relative_to(out_dir)), **check_candidate(api, image, concept, lang, judge)})
        passing = [r for r in results if r["sam_ok"] and r["spark_ok"]]
        best = max(passing, key=lambda r: r["sam_confidence"] or 0) if passing else None
        ph, _ = phonemes(concept.word, lang)
        return {
            **asdict(concept), "lang": lang, "style": style, "prompt": prompt,
            "zipf": round(word_zipf(concept.word, lang), 2), "phonemes": len(ph),
            "status": "kept" if best else "review", "image": best["file"] if best else None,
            "candidates": results,
        }

    with ThreadPoolExecutor(workers) as pool:
        items = list(pool.map(run, concepts))
    manifest = {"lang": lang, "style": style, "items": items}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest

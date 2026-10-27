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
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image

from metalesionlab.meta_api import MetaAPI, image_data_url, retry_network
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
        {"type": "text", "text": f"Name the object in this picture with exactly one word in "
                                 f"{LANGUAGE_NAMES.get(lang, lang)}. Reply with the word only."},
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


def load_progress(out_dir: Path, words: list[str]) -> tuple[list[Concept] | None, dict[str, dict]]:
    """A resumable build's saved plan (None unless it covers every word) and finished items by word."""
    plan_path, progress = out_dir / "plan.json", out_dir / "progress.jsonl"
    plan = None
    if plan_path.exists():
        saved = {c["word"]: c for c in json.loads(plan_path.read_text())}
        if all(w in saved for w in words):
            plan = [Concept(**saved[w]) for w in words]
    done = {}
    if progress.exists():
        for line in progress.read_text().splitlines():
            if line.strip():
                item = json.loads(line)
                done[item["word"]] = item
    return plan, done


def build_set(words: list[str], lang: str, out_dir: Path, style: str = "line", candidates: int = 2,
              workers: int = 8, api: MetaAPI | None = None, resume: bool = False) -> dict:
    """With resume, the plan and every finished item are saved as they come (plan.json,
    progress.jsonl), and a rerun after a crash only pays for the items still missing. Network
    calls are retried with backoff (retry_network) either way."""
    api = api or MetaAPI()
    judge = spark_semantic_judge(api)
    parsed = parse_word_list(words)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan, done = load_progress(out_dir, [c.word for c in parsed]) if resume else (None, {})
    concepts = plan or retry_network(lambda: plan_concepts(api, parsed, lang))
    if resume:
        (out_dir / "plan.json").write_text(json.dumps([asdict(c) for c in concepts], ensure_ascii=False))
    (out_dir / "candidates").mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    def run(concept: Concept) -> dict:
        if concept.word in done:
            return done[concept.word]
        prompt = STYLES[style].format(depiction=concept.depiction)
        results = []
        for k, image in enumerate(retry_network(lambda: api.generate_images(prompt, n=candidates))):
            path = out_dir / "candidates" / f"{concept.word}_{k}.png"
            path.write_bytes(_resized_png(image, SAVE_SIDE))
            check = retry_network(lambda: check_candidate(api, image, concept, lang, judge))  # noqa: B023
            results.append({"file": str(path.relative_to(out_dir)), **check})
        passing = [r for r in results if r["sam_ok"] and r["spark_ok"]]
        best = max(passing, key=lambda r: r["sam_confidence"] or 0) if passing else None
        ph, _ = phonemes(concept.word, lang)
        item = {
            **asdict(concept), "lang": lang, "style": style, "prompt": prompt,
            "zipf": round(word_zipf(concept.word, lang), 2), "phonemes": len(ph),
            "status": "kept" if best else "review", "image": best["file"] if best else None,
            "candidates": results,
        }
        if resume:
            with lock, (out_dir / "progress.jsonl").open("a") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    with ThreadPoolExecutor(workers) as pool:
        items = list(pool.map(run, concepts))
    manifest = {"lang": lang, "style": style, "items": items}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    return manifest


# --- one set of pictures, named in several languages -------------------------------------

def derive_language_manifest(en_manifest: dict, names: dict[str, list[str]], lang: str, source: str) -> dict:
    """A set in another language that reuses an English set's pictures: the same items, order,
    status and picture files, named with `names[english word]` (target first, then accepted
    alternates). The gloss is the English word, so the bilingual test matches items by it.
    The English set's checks (SAM, Muse Spark's English name) stay with the English set."""
    items = []
    for it in en_manifest["items"]:
        word = it["word"]
        if word not in names:
            raise KeyError(f"no {lang} name for {word!r}")
        target, *alts = [_nfc(n).strip().lower() for n in names[word]]
        ph, _ = phonemes(target, lang)
        items.append({
            "word": target, "hint": it.get("hint", ""), "gloss": word, "depiction": it.get("depiction", ""),
            "ambiguous": False, "other_meanings": [], "alternates": list(dict.fromkeys(a for a in alts if a != target)),
            "lang": lang, "style": it.get("style", en_manifest.get("style")), "prompt": it.get("prompt", ""),
            "zipf": round(word_zipf(target, lang), 2), "phonemes": len(ph),
            "status": it.get("status"), "image": it.get("image"),
            **({"drop_reason": it["drop_reason"]} if it.get("drop_reason") else {}),
            "candidates": [{"file": c["file"], "source": source} for c in it.get("candidates", [])],
        })
    return {"lang": lang, "style": en_manifest.get("style"), "pictures_from": source, "items": items}


def merge_alternates(manifest: dict, names: dict[str, list[str]]) -> dict:
    """Add accepted alternates (names[word][1:]) to a manifest's items, keeping the ones it has."""
    for it in manifest["items"]:
        extra = [_nfc(n).strip().lower() for n in names.get(it["word"], [])[1:]]
        it["alternates"] = list(dict.fromkeys([*(it.get("alternates") or []), *extra]))
    return manifest


def apply_review(manifest: dict, review: dict, redraws: dict[str, dict] | None = None) -> tuple[dict, list]:
    """Apply review decisions to a manifest. redraws: set name -> its manifest. Returns the new
    manifest and the files to copy, as (set name, source file, destination file) tuples."""
    copies = []
    by_word = {it["word"]: it for it in manifest["items"]}
    for word, d in review["items"].items():
        it = by_word.get(word)
        if it is None:
            raise KeyError(f"{word!r} is not in the set")
        action = d["action"]
        if action == "drop":
            it["status"], it["drop_reason"] = "dropped", d["reason"]
        elif action == "keep":
            if d["image"] not in {c["file"] for c in it["candidates"]}:
                raise ValueError(f"{word}: {d['image']} is not one of its candidates")
            it["status"], it["image"] = "kept", d["image"]
        elif action == "replace":
            src = (redraws or {})[d["from"]]
            new = next(x for x in src["items"] if x["word"] == word)
            candidates = []
            for c in new["candidates"]:
                dest = c["file"].replace(f"{word}_", f"{word}_redraw_")
                copies.append((d["from"], c["file"], dest))
                candidates.append({**c, "file": dest, "redrawn_from": d["from"]})
            it.update(depiction=new["depiction"], prompt=new["prompt"], hint=new.get("hint", it.get("hint", "")),
                      candidates=candidates, status="kept",
                      image=d["image"].replace(f"{word}_", f"{word}_redraw_"))
        else:
            raise ValueError(f"{word}: unknown action {action!r}")
        it["review"] = {"action": action, "reason": d["reason"]}
    return manifest, copies

"""A personal naming test from a photo of someone's home or belongings.

1. Muse Spark lists the clearly visible, nameable objects, named in the test's language, with an
   English name (for SAM) and a short description of how each one looks.
2. SAM 3.1 finds each object in the photo.
3. Muse Image redraws each object as a clean line drawing in the Test Studio style, from its
   description (or, if real photos are preferred, the object is cropped from the photo).
4. The usual Test Studio checks run on every picture: SAM 3.1 must see exactly one clear object,
   and Muse Spark must name it with the target word.

The photo is used in memory only, re-encoded without its metadata (EXIF, location), and never
saved. The finished items go back to the browser, which keeps them as a private set.
"""
from __future__ import annotations

import base64
import io
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from PIL import Image, ImageOps

from metalesionlab.meta_api import image_data_url
from metalesionlab.naming_errors import LANGUAGE_NAMES
from metalesionlab.test_studio import STYLES, Concept, _json_from, check_candidate

PHOTO_SIDE = 1600  # longest side kept in memory
SPARK_SIDE = 1024
ITEM_SIDE = 768
SAM_MIN_CONFIDENCE = 0.3
CROP_MARGIN = 0.08

LIST_PROMPT = """\
This photo shows someone's home or belongings. A clinician will turn the objects in it into a \
personal picture-naming test in {language}.
List the objects that are clearly visible, whole and easy to name: everyday things that most \
speakers of {language} would name with one common word. Leave out people, pets' faces, body \
parts, text, logos, brand names, screens, and anything partly hidden, tiny or unclear. Prefer \
objects that look different from one another. At most {max_items}, the clearest first.
For each object give:
- "name": its everyday name in {language}, singular, without an article (one or two words)
- "alternates": other names in {language} that should also count as correct (may be empty)
- "english": its name in English, one or two words
- "depiction": a short English description of this particular object's shape and features, \
without colors, starting with "a" or "an"
Reply with only JSON: {{"objects": [{{"name": "...", "alternates": [], "english": "...", "depiction": "..."}}]}}"""


def _jpeg(img: Image.Image, side: int, quality: int = 88) -> bytes:
    img = img.copy()
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality)  # no EXIF: location and camera data are dropped
    return buf.getvalue()


def _data_url(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _square_crop(img: Image.Image, box: tuple[float, float, float, float], size: tuple[int, int]) -> Image.Image:
    """The object's box from the photo (box is in the coordinates SAM saw), with a margin, on white."""
    sx, sy = img.width / size[0], img.height / size[1]
    x1, y1, x2, y2 = box[0] * sx, box[1] * sy, box[2] * sx, box[3] * sy
    mw, mh = (x2 - x1) * CROP_MARGIN, (y2 - y1) * CROP_MARGIN
    crop = img.crop((max(0, int(x1 - mw)), max(0, int(y1 - mh)), min(img.width, int(x2 + mw)), min(img.height, int(y2 + mh))))
    side = max(crop.width, crop.height)
    canvas = Image.new("RGB", (side, side), "white")
    canvas.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    return canvas


def list_objects(api, photo_jpeg: bytes, lang: str, max_items: int) -> list[dict]:
    prompt = LIST_PROMPT.format(language=LANGUAGE_NAMES.get(lang, lang), max_items=max_items)
    content = [{"type": "image_url", "image_url": {"url": image_data_url(photo_jpeg, "image/jpeg")}},
               {"type": "text", "text": prompt}]
    for effort in ("low", "medium"):
        reply = api.chat([{"role": "user", "content": content}], reasoning_effort=effort)
        data = _json_from(reply.choices[0].message.content or "") or {}
        objects = data.get("objects") if isinstance(data, dict) else None
        if isinstance(objects, list) and objects:
            break
    else:
        raise ValueError("Muse Spark didn't list any objects in the photo")
    seen, out = set(), []
    for o in objects:
        if not isinstance(o, dict):
            continue
        name = re.sub(r"\s+", " ", str(o.get("name", "")).strip().lower())
        english = str(o.get("english") or "").strip().lower()
        if not name or not english or name in seen or len(name.split()) > 2:
            continue
        seen.add(name)
        alts = [str(a).strip().lower() for a in o.get("alternates") or [] if str(a).strip() and str(a).strip().lower() != name]
        depiction = str(o.get("depiction") or f"a {english}").strip()
        out.append({"name": name, "english": english, "alternates": alts[:6], "depiction": depiction})
    return out[:max_items]


def build_from_photo(api, photo: bytes, mime: str, lang: str, style: str = "line", max_items: int = 8,
                     judge=None, progress: Callable[[str], None] | None = None) -> dict:
    """Items for a private naming set: {"lang", "style", "items": [{target, alternates, image (data URL),
    status, checks, ...}], "listed": n}."""
    say = progress or (lambda _msg: None)
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(photo))).convert("RGB")
    img.thumbnail((PHOTO_SIDE, PHOTO_SIDE))
    spark_jpeg = _jpeg(img, SPARK_SIDE)
    sam_jpeg = _jpeg(img, PHOTO_SIDE)
    sam_size = Image.open(io.BytesIO(sam_jpeg)).size

    say("Muse Spark is listing the objects it can see")
    objects = list_objects(api, spark_jpeg, lang, max_items)
    say(f"Found {len(objects)} objects; locating each with SAM 3.1")

    def one(obj: dict) -> dict:
        matches, _ = api.segment(sam_jpeg, obj["english"], mime="image/jpeg")
        good = sorted((m for m in matches if (m.confidence or 0) >= SAM_MIN_CONFIDENCE), key=lambda m: -(m.confidence or 0))
        located = good[0] if good else None
        item = {"target": obj["name"], "alternates": obj["alternates"], "english": obj["english"],
                "depiction": obj["depiction"], "located": located is not None,
                "located_confidence": round(located.confidence, 3) if located and located.confidence else None,
                "style": style}
        if style == "photo":
            if not located:
                return {**item, "status": "excluded", "note": "SAM 3.1 couldn't find this object in the photo."}
            crop = _square_crop(img, located.box, sam_size)
            picture, pic_mime = _jpeg(crop, ITEM_SIDE), "image/jpeg"
            crop.thumbnail((ITEM_SIDE, ITEM_SIDE))
            buf = io.BytesIO()
            crop.save(buf, "PNG")
            to_check = buf.getvalue()  # the checks send PNG
        else:
            prompt = STYLES["line"].format(depiction=obj["depiction"])
            drawn = api.generate_images(prompt, n=1)[0]
            out = Image.open(io.BytesIO(drawn)).convert("RGB")
            out.thumbnail((ITEM_SIDE, ITEM_SIDE))
            buf = io.BytesIO()
            out.save(buf, "PNG", optimize=True)
            picture, pic_mime = buf.getvalue(), "image/png"
            to_check = picture
        concept = Concept(word=obj["name"], gloss=obj["english"], depiction=obj["depiction"])
        checks = check_candidate(api, to_check, concept, lang, judge)
        ok = checks["sam_ok"] and checks["spark_ok"]
        note = None if ok else ("SAM 3.1 didn't see exactly one clear object." if not checks["sam_ok"]
                                else f"Muse Spark called it '{checks['spark_name']}'.")
        if style == "line" and not located:
            note = (note + " " if note else "") + "Not found in the photo by SAM 3.1; check it is their object."
        return {**item, "image": _data_url(picture, pic_mime), "checks": checks,
                "status": "kept" if ok and (located or style == "photo") else "review", "note": note}

    with ThreadPoolExecutor(4) as pool:
        items = list(pool.map(one, objects))
    say("Done")
    return {"lang": lang, "style": style, "listed": len(objects), "items": items}

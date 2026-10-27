import base64
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from metalesionlab.meta_api import SamMatch
from metalesionlab.test_studio import (apply_review, build_set, derive_language_manifest, merge_alternates,
                                       parse_word_list, plan_concepts)


class FakeChatAPI:
    def __init__(self, items):
        self.items = items

    def chat(self, messages, **kwargs):
        content = json.dumps({"items": self.items}, ensure_ascii=False)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_word_list_is_nfc_normalized_like_transcripts():
    # सीढ़ी typed with the precomposed letter ढ़ (U+095D); NFC spells it ढ + nukta, as tokens() does.
    [concept] = parse_word_list(["सीढ़ी: ladder"])
    assert concept.word == "सीढ़ी"
    assert concept.hint == "ladder"


def test_plan_keeps_other_spellings_of_the_same_word_as_alternates():
    concepts = parse_word_list(["कैक्टस", "बिल्ली"])
    api = FakeChatAPI([{"word": "कैक्टस", "gloss": "cactus", "spellings": ["Cactus", "कैक्टस", "cactus"]},
                       {"word": "बिल्ली", "gloss": "cat", "spellings": []}])
    cactus, cat = plan_concepts(api, concepts, "hi")
    assert cactus.alternates == ["cactus"]  # lowercased, deduplicated, without the word itself
    assert cat.alternates == []


def test_plan_falls_back_to_order_when_the_reply_respells_a_word():
    concepts = parse_word_list(["बिल्ली", "छाता"])
    api = FakeChatAPI([{"word": "billi", "gloss": "cat", "depiction": "a cat"},
                       {"word": "छाता", "gloss": "umbrella", "depiction": "an umbrella"}])
    planned = plan_concepts(api, concepts, "hi")
    assert [c.gloss for c in planned] == ["cat", "umbrella"]


WIDTH = {"cat": 64, "dog": 65}  # the fake picture of each word has its own width, so it can be named


class FakeBuildAPI:
    """Plans, draws, segments and names pictures; drawing `fail_word` raises (a crash)."""

    def __init__(self, fail_word=None):
        self.fail_word, self.drawn = fail_word, []

    def chat(self, messages, **kwargs):
        content = messages[0]["content"]
        if isinstance(content, str):  # the plan
            words = [line[2:] for line in content.split("Words:\n")[1].splitlines()]
            text = json.dumps({"items": [{"word": w, "gloss": w, "depiction": f"a {w}"} for w in words]})
        else:  # naming a picture
            url = content[0]["image_url"]["url"]
            width = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1]))).size[0]
            text = {v: k for k, v in WIDTH.items()}[width]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])

    def generate_images(self, prompt, n=1):
        word = prompt.split("drawing of a ")[1].split(",")[0]
        if word == self.fail_word:
            raise RuntimeError("crash")
        self.drawn.append(word)
        out = []
        for _ in range(n):
            buf = io.BytesIO()
            Image.new("RGB", (WIDTH[word], 64), "white").save(buf, "PNG")
            out.append(buf.getvalue())
        return out

    def segment(self, image, text):
        return [SamMatch(0, (0, 0, 32, 32), (64, 64), 0.9)], ""


def test_build_resumes_after_a_crash_without_redrawing_finished_words(tmp_path):
    api = FakeBuildAPI(fail_word="dog")
    with pytest.raises(RuntimeError):
        build_set(["cat", "dog"], "en", tmp_path, workers=1, api=api, resume=True)
    assert api.drawn == ["cat"]
    api.fail_word = None
    manifest = build_set(["cat", "dog"], "en", tmp_path, workers=1, api=api, resume=True)
    assert api.drawn == ["cat", "dog"]  # cat was not drawn (or paid for) again
    assert [it["status"] for it in manifest["items"]] == ["kept", "kept"]
    assert json.loads((tmp_path / "manifest.json").read_text())["items"][1]["word"] == "dog"


def test_language_set_reuses_english_pictures_with_target_names():
    en = {"lang": "en", "style": "line", "items": [
        {"word": "cat", "gloss": "cat", "status": "kept", "image": "candidates/cat_1.png",
         "candidates": [{"file": "candidates/cat_0.png", "sam_ok": True}, {"file": "candidates/cat_1.png"}]},
        {"word": "saw", "gloss": "handsaw", "status": "dropped", "drop_reason": "looks like a knife",
         "image": "candidates/saw_0.png", "candidates": [{"file": "candidates/saw_0.png"}]}]}
    es = derive_language_manifest(en, {"cat": ["Gato", "gatito", "gato"], "saw": ["sierra", "serrucho"]}, "es",
                                  "core100_en")
    cat, saw = es["items"]
    assert (cat["word"], cat["gloss"], cat["alternates"]) == ("gato", "cat", ["gatito"])
    assert cat["image"] == "candidates/cat_1.png" and cat["status"] == "kept" and cat["lang"] == "es"
    assert cat["candidates"] == [{"file": "candidates/cat_0.png", "source": "core100_en"},
                                 {"file": "candidates/cat_1.png", "source": "core100_en"}]
    assert saw["gloss"] == "saw"  # matched by the English word, not Spark's gloss
    assert saw["status"] == "dropped" and saw["drop_reason"] == "looks like a knife"
    assert es["pictures_from"] == "core100_en"


def test_review_keeps_drops_and_replaces_with_redrawn_pictures():
    def item(word, status="kept", image=None):
        return {"word": word, "status": status, "image": image, "depiction": f"a {word}", "prompt": "p",
                "candidates": [{"file": f"candidates/{word}_0.png"}, {"file": f"candidates/{word}_1.png"}]}

    manifest = {"items": [item("lemon", "review"), item("saw", "kept", "candidates/saw_0.png"),
                          item("tie", "kept", "candidates/tie_1.png")]}
    review = {"items": {
        "lemon": {"action": "keep", "image": "candidates/lemon_1.png", "reason": "SAM missed it"},
        "saw": {"action": "drop", "reason": "looks like a knife"},
        "tie": {"action": "replace", "from": "fix", "image": "candidates/tie_0.png", "reason": "a scarf"}}}
    redraw = {"items": [{**item("tie", "kept", "candidates/tie_0.png"), "depiction": "a necktie"}]}
    out, copies = apply_review(manifest, review, {"fix": redraw})
    lemon, saw, tie = out["items"]
    assert (lemon["status"], lemon["image"]) == ("kept", "candidates/lemon_1.png")
    assert (saw["status"], saw["drop_reason"]) == ("dropped", "looks like a knife")
    assert tie["image"] == "candidates/tie_redraw_0.png" and tie["depiction"] == "a necktie"
    assert [c["file"] for c in tie["candidates"]] == ["candidates/tie_redraw_0.png", "candidates/tie_redraw_1.png"]
    assert copies == [("fix", "candidates/tie_0.png", "candidates/tie_redraw_0.png"),
                      ("fix", "candidates/tie_1.png", "candidates/tie_redraw_1.png")]
    assert tie["review"] == {"action": "replace", "reason": "a scarf"}
    with pytest.raises(ValueError):
        apply_review({"items": [item("cat")]}, {"items": {"cat": {"action": "keep", "image": "x.png",
                                                                  "reason": ""}}})


def test_merge_alternates_keeps_existing_ones():
    m = {"items": [{"word": "axe", "alternates": ["axe head"]}, {"word": "cat"}]}
    merge_alternates(m, {"axe": ["axe", "ax", "hatchet"]})
    assert m["items"][0]["alternates"] == ["axe head", "ax", "hatchet"]
    assert m["items"][1]["alternates"] == []

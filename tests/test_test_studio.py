import json
from types import SimpleNamespace

from metalesionlab.test_studio import naming_prompt, parse_word_list, plan_concepts


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


def test_naming_prompt_asks_for_the_whole_name_where_names_have_several_words():
    # Oct 27: "exactly one word" made Muse Spark cut mỏ neo to "neo" and run cà rốt into "càrốt".
    assert "syllables" not in naming_prompt("en") and "Vietnamese" not in naming_prompt("en")
    assert "two or more syllables" in naming_prompt("vi") and "Vietnamese" in naming_prompt("vi")
    assert "sarung tangan" in naming_prompt("id")
    assert naming_prompt("fr") == "Name the object in this picture with exactly one word in French. Reply with the word only."

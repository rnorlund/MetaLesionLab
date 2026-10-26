import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from metalesionlab import scorer
from metalesionlab.scorer import (agreement, make_scene, normalize_item, score_description, score_fluency,
                                  second_rater, split_chunks)


class FakeAPI:
    """Stands in for MetaAPI.chat: returns canned replies in order and records the prompts."""

    def __init__(self, *replies: str):
        self.replies, self.prompts = list(replies), []

    def chat(self, messages, reasoning_effort="minimal", **kwargs):
        self.prompts.append(messages[0]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.replies.pop(0)))])

    def generate_images(self, prompt, n=1, size=None, output_format="png"):
        self.prompts.append(prompt)
        buf = io.BytesIO()
        Image.new("RGB", (300, 200), "white").save(buf, "PNG")
        return [buf.getvalue()]


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(scorer, "CACHE_DIR", tmp_path)
    for name in ("_rater_cache", "_description_cache", "_fluency_cache"):
        monkeypatch.setattr(scorer, name, scorer._JsonCache(getattr(scorer, name).name))


# --- agreement -------------------------------------------------------------------------

def test_agreement_matches_hand_computed_kappa():
    # po = 0.75; pe = (2*1 + 1*1 + 1*2) / 16 = 5/16; kappa = (0.75 - 0.3125) / 0.6875
    out = agreement(["a", "b", "a", "c"], ["a", "b", "c", "c"])
    assert out == {"n": 4, "percent": 75.0, "kappa": pytest.approx(0.636, abs=1e-3)}


def test_agreement_perfect_and_chance():
    assert agreement(["x", "y", "x"], ["x", "y", "x"])["kappa"] == 1.0
    # Rater B always says "x": agreement is exactly what chance predicts.
    assert agreement(["x", "y", "x", "y"], ["x", "x", "x", "x"])["kappa"] == 0.0


def test_agreement_undefined_cases():
    assert agreement([], []) == {"n": 0, "percent": None, "kappa": None}
    assert agreement(["x", "x"], ["x", "x"]) == {"n": 2, "percent": 100.0, "kappa": None}
    with pytest.raises(ValueError):
        agreement(["x"], ["x", "y"])


# --- fluency normalization ---------------------------------------------------------------

@pytest.mark.parametrize("text,lang,key", [
    ("The Dogs", "en", "dog"),
    ("a dog", "en", "dog"),
    ("polar bears", "en", "polar bear"),
    ("mice", "en", "mouse"),
    ("cows", "en", "cow"),
    ("butterflies", "en", "butterfly"),
    ("foxes", "en", "fox"),
    ("bus", "en", "bus"),
    ("um, lion", "en", "lion"),
    ("los leones", "es", "leon"),
    ("León", "es", "leon"),
    ("peces", "es", "pez"),
    ("Gatos", "es", "gato"),
    ("osos polares", "es", "oso polar"),
    ("l'éléphant", "fr", "elephant"),
    ("chevaux", "fr", "cheval"),
])
def test_normalize_item(text, lang, key):
    assert normalize_item(text, lang) == key


@pytest.mark.parametrize("a,b", [("tigre", "tigres"), ("elefante", "elefantes"), ("ratón", "ratones"),
                                 ("jirafa", "jirafas"), ("león", "leones")])
def test_spanish_singular_and_plural_share_a_key(a, b):
    assert normalize_item(a, "es") == normalize_item(b, "es")


def test_split_chunks_at_punctuation_and_conjunctions():
    assert split_chunks("Dog, cat, horse, dog, table, lion.", "en") == ["dog", "cat", "horse", "dog", "table", "lion"]
    assert split_chunks("um, let me think, dog cat and a horse... the dogs", "en") == [
        "let me think", "dog cat", "horse", "dogs"]
    assert split_chunks("Perro, gato y caballo. Eh, perros, la mesa", "es") == [
        "perro", "gato", "caballo", "perros", "mesa"]
    assert split_chunks("", "en") == []
    assert split_chunks("猫，狗、老虎。大象", "zh") == ["猫", "狗", "老虎", "大象"]
    assert split_chunks("बिल्ली, कुत्ता। शेर", "hi") == ["बिल्ली", "कुत्ता", "शेर"]


# --- fluency scoring with a fake judge ----------------------------------------------------

def _stretches(*items_per_line):
    return json.dumps({"stretches": {str(i): [{"item": t, "valid": v} for t, v in line]
                                     for i, line in enumerate(items_per_line, 1)}})


def test_score_fluency_counts_repetitions_intrusions_and_comments():
    # Unique stretches go to the judge once: dog, cat horse (said without a pause), table, let me think, lion.
    api = FakeAPI(_stretches([("dog", True)], [("cat", True), ("horse", True)], [("table", False)], [],
                             [("lion", True)]))
    out = score_fluency(api, "Dog, cat horse, the dogs, table, let me think, lion, table.", "animals", "en")
    assert out["count"] == 4
    assert out["valid"] == ["dog", "cat", "horse", "lion"]
    assert out["repetitions"] == ["dogs", "table"]  # as said
    assert out["intrusions"] == ["table"]
    assert [i["status"] for i in out["items"]] == [
        "valid", "valid", "valid", "repetition", "intrusion", "comment", "valid", "repetition"]
    assert len(api.prompts) == 1


def test_score_fluency_keys_an_item_the_judge_pulled_out_of_a_remark():
    api = FakeAPI(_stretches([("dog", True)], [("cat", True)], [("cat", True)]))
    out = score_fluency(api, "dog, I think a cat, cats", "animals", "en")
    assert out["valid"] == ["dog", "cat"] and out["repetitions"] == ["cats"]


def test_score_fluency_caches_judgments_per_stretch():
    api = FakeAPI(_stretches([("perro", True)], [("mesa", False)]))
    score_fluency(api, "perro, mesa", "animales", "es")
    out = score_fluency(FakeAPI(), "Perros. La mesa.", "animales", "es")  # no replies left: must hit the cache
    assert out["count"] == 1 and out["intrusions"] == ["mesa"]


# --- second rater and description with a fake model ---------------------------------------

def test_second_rater_parses_and_caches():
    api = FakeAPI('Sure. {"code": "semantic", "rationale": "Both are animals."}')
    assert second_rater(api, "cat", "dog", "en") == {"code": "Semantic", "rationale": "Both are animals."}
    assert second_rater(FakeAPI(), "cat", "dog", "en")["code"] == "Semantic"
    assert "Visual: do not use" in api.prompts[0]


def test_second_rater_retries_an_unreadable_reply():
    api = FakeAPI("I am not sure.", '{"code": "NoResponse", "rationale": "A refusal."}')
    assert second_rater(api, "cat", "I don't know", "en")["code"] == "NoResponse"


def test_score_description_rates_and_units():
    scene = {"content_units": ["the boy", "the dog", "the boy is kicking a ball", "the tree"]}
    api = FakeAPI('{"mentioned": [1, 3, 9]}')
    out = score_description(api, "Um, a kid is kicking a ball.", scene, "en", duration_s=30)
    assert out["words"] == 6
    assert out["words_per_min"] == 12.0
    assert out["content_units_mentioned"] == ["the boy", "the boy is kicking a ball"]
    assert out["content_units_missed"] == ["the dog", "the tree"]
    assert out["cu_count"] == 2 and out["cu_per_min"] == 4.0


def test_score_description_empty_transcript_needs_no_call():
    out = score_description(FakeAPI(), "", {"content_units": ["the boy"]}, "en")
    assert out["cu_count"] == 0 and out["words_per_min"] is None and out["content_units_missed"] == ["the boy"]


def test_make_scene_writes_picture_and_units(tmp_path):
    api = FakeAPI('{"setting": "city park", "brief": "A park with people."}',
                  '{"description": "Un parque.", "content_units": ["el niño", "el perro"], "has_text": false}')
    scene = make_scene(api, "es", "un parque", out_dir=tmp_path)
    assert scene["id"].startswith("es_city-park_")
    assert scene["content_units"] == ["el niño", "el perro"] and scene["description"] == "Un parque."
    assert Path(scene["image_file"]).exists() and (tmp_path / f"{scene['id']}.json").exists()
    assert "no text" in api.prompts[1]  # the drawing prompt forbids writing


def test_make_scene_redraws_once_when_the_picture_has_writing(tmp_path):
    units = '{"description": "d", "content_units": ["the boy"], "has_text": %s}'
    api = FakeAPI('{"setting": "beach", "brief": "A beach."}', units % "true", units % "false")
    assert make_scene(api, "en", out_dir=tmp_path)["draws"] == 2

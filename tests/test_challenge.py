"""You vs. the AI (/challenge): offline, with a temporary data folder and no Meta API."""
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab import meta_api
from metalesionlab.web import app as web
from metalesionlab.web import challenge

WORDS = ["cat", "umbrella", "anchor", "ladder", "glove", "scissors", "pineapple", "snail", "cactus", "harp", "kettle", "bench"]


def _lens(word, hit_from=42, lost=()):
    top = [["OK"]] * 52
    p = [0.0] * 52
    for layer in range(hit_from, 53):
        if layer not in lost:
            top[layer - 1], p[layer - 1] = [word], 0.5
    return {"top": top, "p_top": p, "p_correct": p}


def _write_data(root):
    d = root / "sets" / "demo_en"
    (d / "candidates").mkdir(parents=True)
    items = []
    for w in WORDS:
        Image.new("RGB", (32, 32), (255, 255, 255)).save(d / "candidates" / f"{w}_0.png")
        items.append({"word": w, "status": "kept", "image": f"candidates/{w}_0.png", "alternates": ["couch"] if w == "bench" else []})
    (d / "manifest.json").write_text(json.dumps({"lang": "en", "items": items}))
    runs = root / "lesion" / "demo_en"
    runs.mkdir(parents=True)
    intact = {"set": "demo_en", "condition": "intact", "spec": {"name": "intact", "layers": []}, "accuracy": 1.0, "seconds": 16.6,
              "items": [{"word": w, "said": w.capitalize(), "code": "Correct", "lens": _lens(w)} for w in WORDS]}
    (runs / "intact.json").write_text(json.dumps(intact))
    damaged = {"set": "demo_en", "condition": "layers:40-47-noise x2.181", "accuracy": 0.8,
               "spec": {"name": "layers:40-47", "method": "noise", "noise_scale": 2.181, "layers": list(range(40, 48))},
               "items": [{"word": w, "said": "Umb\n\nThe object is" if w == "umbrella" else w, "code": "Nonword" if w == "umbrella" else "Correct",
                          "lens": _lens(w, lost=range(43, 49))} for w in WORDS]}
    (runs / "layers-40-47-noise-x2.181.json").write_text(json.dumps(damaged))
    (runs / "index.json").write_text(json.dumps({"set": "demo_en", "conditions": []}))


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name, sub in [("DATA_DIR", ""), ("SETS_DIR", "sets"), ("LESION_DIR", "lesion"), ("CACHE_DIR", "cache")]:
        monkeypatch.setattr(web, name, tmp_path / sub if sub else tmp_path)

    def no_api(*_a, **_k):
        raise AssertionError("the game must not call the Meta API")

    monkeypatch.setattr(web, "get_api", no_api)
    monkeypatch.setattr(web, "judge", no_api)
    monkeypatch.setattr(meta_api.MetaAPI, "__init__", no_api)
    challenge._cache.clear()
    _write_data(tmp_path)
    return TestClient(web.app), tmp_path


def test_page_and_pages_flag(client):
    c, _ = client
    r = c.get("/challenge")
    assert r.status_code == 200 and "You vs. the AI" in r.text
    assert c.get("/api/pages").json() == {"assess": False, "challenge": True}


def test_game_uses_real_runs_and_shifts_layers_to_one_based(client):
    c, _ = client
    g = c.get("/api/challenge?lang=en").json()
    assert not g["sample"] and [it["word"] for it in g["items"]] == WORDS[:10]
    assert g["items"][1]["ai"] == {"said": "Umbrella", "code": "Correct"}
    assert g["items"][0]["image"] == "/media/sets/demo_en/candidates/cat_0.png?w=640"
    assert g["ai_summary"] == {"correct": 10, "n": 10, "run_seconds": 16.6, "run_n": 12}
    ins = g["inside"]
    assert ins["word"] == "umbrella" and ins["damaged"]["said"] == "Umb" and ins["damaged"]["code"] == "Nonword"
    assert ins["damage"]["layers"] == list(range(41, 49))  # engine layers 40-47 are 0-based
    assert ins["damage"]["plain"] == "Layers 41–48 of 52 disturbed with random noise"
    assert (ins["damage"]["accuracy"], ins["damage"]["correct"], ins["damage"]["n"]) == (80.0, 10, 12)
    assert len(ins["intact"]["top"]) == 52 and ins["intact"]["top"][41] == "umbrella"


def test_falls_back_to_the_labeled_sample(client):
    c, tmp = client
    for f in (tmp / "lesion" / "demo_en").iterdir():
        f.unlink()
    g = c.get("/api/challenge?lang=en").json()
    assert g["sample"] and g["note"]
    answered = [bool(it["ai"]) for it in g["items"]]
    assert answered[0] and answered == sorted(answered, reverse=True)  # pictures the sample answered come first
    assert g["inside"]["word"] in [it["word"] for it in g["items"]]


def test_missing_pictures_is_a_friendly_503(client):
    c, tmp = client
    (tmp / "sets" / "demo_en" / "manifest.json").unlink()
    r = c.get("/api/challenge?lang=en")
    assert r.status_code == 503 and "pictures" in r.json()["detail"]


def test_typed_scoring_is_free_and_uses_only_cached_judgments(client):
    c, tmp = client
    (tmp / "cache").mkdir()
    key = f"v{challenge.JUDGE_PROMPT_VERSION}|en|cat|milk"
    (tmp / "cache" / "semantic_judge.json").write_text(json.dumps({key: True}))
    answers = [("cat", "a cat"), ("cat", "dog"), ("cat", "milk"), ("cat", "tiger lily"), ("anchor", "ankle"), ("cat", ""),
               ("bench", "couch"), ("cat", "cat cat"), ("umbrella", "parasol")]
    r = c.post("/api/challenge/score", json={"lang": "en", "answers": [{"word": w, "response": s} for w, s in answers]})
    assert r.status_code == 200
    res = r.json()["results"]
    assert [x["code"] for x in res][:8] == ["Correct", "Semantic", "Semantic", "Unrelated", "Formal", "NoResponse", "Correct", "Correct"]
    assert res[2]["meaning_checked"] and not res[3]["meaning_checked"]  # milk was cached; tiger lily wasn't asked
    assert r.json()["correct"] == 3
    assert c.post("/api/challenge/score", json={"lang": "fr", "answers": [{"word": "chat", "response": "chat"}]}).status_code == 422
    too_many = [{"word": "cat", "response": "cat"}] * 21
    assert c.post("/api/challenge/score", json={"lang": "en", "answers": too_many}).status_code == 422


def test_typed_spanish_accepts_missing_accents(client):
    c, tmp = client
    d = tmp / "sets" / "demo_es"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"lang": "es", "items": [
        {"word": "piña", "status": "kept", "image": "x.png"}, {"word": "iglú", "status": "kept", "image": "y.png"}]}))
    r = c.post("/api/challenge/score", json={"lang": "es", "answers": [
        {"word": "piña", "response": "pina"}, {"word": "iglú", "response": "iglu"}, {"word": "piña", "response": "la piña"},
        {"word": "iglú", "response": "igloo"}]}).json()
    assert [x["code"] for x in r["results"]][:3] == ["Correct", "Correct", "Correct"] and not r["results"][3]["correct"]

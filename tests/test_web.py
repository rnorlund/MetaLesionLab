"""Web app routes, offline: a temporary data folder, and no Meta API calls."""
import hashlib
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab.meta_api import BudgetExceeded
from metalesionlab.web import app as web


def _png(path, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), color).save(path)


def _candidate(file, ok=True, name="cat"):
    return {"file": file, "sam_objects": 1 if ok else 0, "sam_confidence": 0.9 if ok else None,
            "sam_area": 0.4 if ok else None, "sam_ok": ok, "spark_name": name, "spark_code": "Correct", "spark_ok": True}


def _make_set(d):
    items = []
    for word in ("cat", "sofa"):
        for k in range(2):
            _png(d / "candidates" / f"{word}_{k}.png", (200, 40 * k, 40))
        items.append({"word": word, "hint": "", "gloss": word, "depiction": f"a {word}", "ambiguous": False,
                      "other_meanings": [], "lang": "en", "style": "line", "zipf": 4.5, "phonemes": 3,
                      "status": "kept", "image": f"candidates/{word}_0.png",
                      "candidates": [_candidate(f"candidates/{word}_0.png", name=word),
                                     _candidate(f"candidates/{word}_1.png", ok=False, name=word)]})
    (d / "manifest.json").write_text(json.dumps({"lang": "en", "style": "line", "items": items}))


class FakeAPI:
    def transcribe(self, wav, language=None):
        raise AssertionError("no transcription in these tests")


@pytest.fixture
def env(tmp_path, monkeypatch):
    for name, sub in [("DATA_DIR", ""), ("SETS_DIR", "sets"), ("SCENES_DIR", "scenes"), ("LESION_DIR", "lesion"),
                      ("CACHE_DIR", "cache")]:
        monkeypatch.setattr(web, name, tmp_path / sub if sub else tmp_path)
    monkeypatch.setattr(web, "get_api", lambda: FakeAPI())
    monkeypatch.setattr(web, "judge", lambda target, response, lang: False)
    monkeypatch.setattr(web, "PUBLIC", False)
    web.limiter.hits.clear()
    web._lab_cache.clear()
    _make_set(tmp_path / "sets" / "demo")
    return TestClient(web.app), tmp_path


def test_pages_and_status(env):
    client, _ = env
    for path in ("/", "/studio", "/scorer", "/lab"):
        r = client.get(path)
        assert r.status_code == 200 and "Tip of the Tongue" in r.text
    status = client.get("/api/status").json()
    assert {"meta_api", "audio", "scorer", "builds"} <= set(status["features"])
    assert status["limits"]["score"]["remaining"] == status["limits"]["score"]["per_day"]


def test_sets_list_detail_media_and_traversal(env):
    client, _ = env
    sets = client.get("/api/sets").json()
    assert [(s["id"], s["status"], s["kept"]) for s in sets] == [("demo", "done", 2)]
    detail = client.get("/api/sets/demo").json()
    assert detail["manifest"]["items"][0]["word"] == "cat"
    thumb = client.get("/media/sets/demo/candidates/cat_0.png?w=160")
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/webp"
    assert client.get("/media/sets/demo/manifest.json").status_code == 404
    assert client.get("/media/sets/demo/candidates/..%2F..%2F..%2Fsecret.png").status_code == 404
    assert client.get("/api/sets/..").status_code == 404


def test_item_edits(env):
    client, tmp = env
    r = client.patch("/api/sets/demo/items/1", json={"image": "candidates/sofa_1.png", "alternates": ["Couch", " ", "sofa"]})
    assert r.status_code == 200
    assert r.json()["image"] == "candidates/sofa_1.png" and r.json()["alternates"] == ["couch"]
    assert client.patch("/api/sets/demo/items/1", json={"image": "manifest.json"}).status_code == 422
    assert client.patch("/api/sets/demo/items/5", json={"status": "kept"}).status_code == 404
    saved = json.loads((tmp / "sets" / "demo" / "manifest.json").read_text())
    assert saved["items"][1]["alternates"] == ["couch"] and saved["items"][1]["reviewed"]


def test_public_mode_needs_the_edit_token(env, monkeypatch):
    client, tmp = env
    monkeypatch.setattr(web, "PUBLIC", True)
    (tmp / "sets" / "demo" / "webmeta.json").write_text(json.dumps({"token_sha": hashlib.sha256(b"secret").hexdigest()}))
    assert client.patch("/api/sets/demo/items/0", json={"status": "review"}).status_code == 403
    r = client.patch("/api/sets/demo/items/0", json={"status": "review"}, headers={"X-Edit-Token": "secret"})
    assert r.status_code == 200 and r.json()["status"] == "review"


def test_exports(env):
    client, _ = env
    csv = client.get("/api/sets/demo/norms.csv").content.decode("utf-8-sig").splitlines()
    assert csv[0].startswith("item,word,hint,gloss,alternates,status") and csv[1].startswith("1,cat,")
    pdf = client.get("/api/sets/demo/cards.pdf?per_page=2&word=0&page=a4")
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    assert client.get("/api/sets/demo/cards.pdf?per_page=5").status_code == 422
    names = zipfile.ZipFile(io.BytesIO(client.get("/api/sets/demo/set.zip").content)).namelist()
    assert {"demo/manifest.json", "demo/norms.csv", "demo/pictures/01_cat.png", "demo/candidates/sofa_1.png"} <= set(names)


def test_typed_naming_takes_target_and_alternates_from_the_set(env):
    client, _ = env
    client.patch("/api/sets/demo/items/1", json={"alternates": ["couch"]})
    body = {"target": "ignored", "response": "a couch", "lang": "en", "set_id": "demo", "item": 1, "second_rater": False}
    r = client.post("/api/score/naming/text", json=body).json()
    assert (r["target"], r["code"], r["second_status"]) == ("sofa", "Correct", "off")
    r = client.post("/api/score/naming/text", json={"target": "cat", "response": "", "second_rater": False}).json()
    assert r["code"] == "NoResponse"
    assert client.post("/api/score/naming/text", json={"target": "cat", "response": "x", "lang": "zz"}).status_code == 422


def test_second_rater_code_is_normalized(env, monkeypatch):
    import metalesionlab.scorer as scorer
    client, _ = env
    monkeypatch.setattr(scorer, "second_rater", lambda api, t, r, lang, image=None: {"code": "semantic", "rationale": "same category"})
    r = client.post("/api/score/naming/text", json={"target": "cat", "response": "dog", "set_id": "demo", "item": 0}).json()
    assert r["code"] == "Semantic" and r["second"] == {"code": "Semantic", "rationale": "same category"} and r["agree"]


def test_daily_limit_returns_429(env, monkeypatch):
    client, _ = env
    monkeypatch.setenv("TOT_LIMIT_SCORE", "2")
    body = {"target": "cat", "response": "cat", "second_rater": False}
    assert [client.post("/api/score/naming/text", json=body).status_code for _ in range(3)] == [200, 200, 429]
    assert client.get("/api/status").json()["limits"]["score"]["remaining"] == 0


def test_budget_cap_is_a_friendly_503(env, monkeypatch):
    client, _ = env

    def broke(*_):
        raise BudgetExceeded("spent $120.00 of the $120.00 cap")

    monkeypatch.setattr(web, "judge", broke)
    r = client.post("/api/score/naming/text", json={"target": "gato", "response": "perro", "lang": "es", "second_rater": False})
    assert r.status_code == 503 and "spending cap" in r.json()["detail"]


def test_missing_scorer_module_is_a_501(env, monkeypatch):
    client, _ = env
    real = web.importlib.import_module

    def fake_import(name, *a):
        if name == "metalesionlab.scorer":
            raise ImportError("not installed")
        return real(name, *a)

    monkeypatch.setattr(web.importlib, "import_module", fake_import)
    r = client.post("/api/score/fluency", data={"category": "animals", "transcript": "dog, cat"})
    assert r.status_code == 501 and "isn't available" in r.json()["detail"]


def test_create_set_validates_and_starts_a_build(env, monkeypatch):
    client, tmp = env
    started = []
    monkeypatch.setattr(web, "_build", lambda *args: started.append(args))
    assert client.post("/api/sets", json={"words": " \n "}).status_code == 422
    assert client.post("/api/sets", json={"words": "\n".join(f"w{i}" for i in range(99))}).status_code == 422
    r = client.post("/api/sets", json={"name": "Café set", "words": "cat\nbanco: bench\ncat", "lang": "es"})
    assert r.status_code == 202 and r.json()["id"] == "cafe-set" and r.json()["edit_token"]
    meta = json.loads((tmp / "sets" / "cafe-set" / "webmeta.json").read_text())
    assert meta["words"] == ["cat", "banco: bench"] and meta["token_sha"] != r.json()["edit_token"]
    assert started and started[0][0] == "cafe-set"
    monkeypatch.setattr(web, "ALLOW_BUILDS", False)
    assert client.post("/api/sets", json={"words": "cat"}).status_code == 403


def test_lab_serves_the_sample_until_real_conditions_exist(env):
    client, tmp = env
    listing = client.get("/api/lab/conditions").json()
    assert listing["sample"] and any(c["baseline"] for c in listing["conditions"])
    lens = {"p_correct": [0.0] * 52, "top": [["the"] * 5] * 52}
    real = {"id": "naming-34-44", "spec": {"site": "decoder", "localizer": "naming", "method": "zero",
                                          "layers": list(range(34, 45)), "fraction": 0.02},
            "accuracy": 0.5, "set": "demo",
            "items": [{"word": "cat", "said": "dog", "code": "Semantic", "lens": lens},
                      {"word": "sofa", "said": "sofa", "code": "Correct", "lens": lens}]}
    (tmp / "lesion").mkdir()
    (tmp / "lesion" / "naming-34-44.json").write_text(json.dumps(real))
    listing = client.get("/api/lab/conditions").json()
    assert not listing["sample"] and [c["id"] for c in listing["conditions"]] == ["naming-34-44"]
    c = listing["conditions"][0]
    assert c["accuracy"] == 50.0 and c["counts"] == {"Semantic": 1, "Correct": 1}
    assert c["label"] == "naming localizer · layers 34–44 · zero · 2% of units"
    detail = client.get("/api/lab/conditions/naming-34-44").json()
    assert detail["items"][0]["image_url"] == "/media/sets/demo/candidates/cat_0.png"


def test_human_profiles_use_the_shared_categories(env):
    client, _ = env
    hp = client.get("/api/lab/human").json()
    by_source = {p["source"]["key"]: p for p in hp["pooled"]}
    walker = by_source["walker2018"]
    assert walker["shares"]["Correct"] == pytest.approx(35662 / 63875, abs=1e-4)
    assert walker["shares"]["Nonword"] == pytest.approx((6049 + 1821) / 63875, abs=1e-4)  # nonword + neologism
    assert by_source["dell2007"]["missing"] == ["NoResponse"]
    for p in hp["pooled"]:
        assert sum(p["shares"].values()) == pytest.approx(1, abs=1e-3)
        assert set(p["shares"]) <= set(hp["codes"]) and p["source"]["short"][-4:].isdigit()
    assert [g["subtype"] for g in hp["subtypes"]["groups"]] == ["Anomic", "Broca's", "Conduction", "Wernicke's"]

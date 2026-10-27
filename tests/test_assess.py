"""Naming Assessment: timed scoring, first complete response, reports, parallel forms, the public
reference range and photo tests. Offline: a temporary data folder and a fake Meta API."""
import io
import json
import time
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab import assessment, audio, photo_test
from metalesionlab.meta_api import SamMatch
from metalesionlab.web import app as web
from metalesionlab.web import assess_routes

R = audio.SAMPLE_RATE


def wav_with_speech(lead_in=0.3, latency=1.0, speech=0.5, tail=0.5, amp=0.3):
    t = np.arange(int(speech * R)) / R
    x = np.concatenate([np.zeros(int((lead_in + latency) * R)), amp * np.sin(2 * np.pi * 200 * t), np.zeros(int(tail * R))])
    return audio.pcm16_wav((x * 32767).astype("<i2").tobytes())


def silent_wav(seconds):
    return audio.pcm16_wav(b"\x00\x00" * int(seconds * R))


class FakeAPI:
    def __init__(self):
        self.transcripts, self.calls = [], []

    def transcribe(self, wav, language=None):
        self.calls.append(("transcribe", language, audio.duration_s(wav)))
        return {"transcript": self.transcripts.pop(0) if self.transcripts else ""}


def _png(path, color=(200, 40, 40)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), color).save(path)


def _make_set(d, words=("cat", "sofa")):
    items = []
    for word in words:
        _png(d / "candidates" / f"{word}_0.png")
        items.append({"word": word, "status": "kept", "image": f"candidates/{word}_0.png", "candidates": [],
                      "alternates": ["couch"] if word == "sofa" else []})
    (d / "manifest.json").write_text(json.dumps({"lang": "en", "style": "line", "items": items}))


@pytest.fixture
def env(tmp_path, monkeypatch):
    for name, sub in [("DATA_DIR", ""), ("SETS_DIR", "sets"), ("SCENES_DIR", "scenes"), ("LESION_DIR", "lesion"),
                      ("CACHE_DIR", "cache")]:
        monkeypatch.setattr(web, name, tmp_path / sub if sub else tmp_path)
    api = FakeAPI()
    monkeypatch.setattr(web, "get_api", lambda: api)
    monkeypatch.setattr(web, "judge", lambda target, response, lang: (target, response) in {("cat", "dog")})
    monkeypatch.setattr(assess_routes, "NORMS_PUBLIC", tmp_path / "public_data")
    monkeypatch.setattr(assess_routes, "_contributions", {})
    web.limiter.hits.clear()
    _make_set(tmp_path / "sets" / "demo_en")
    return TestClient(web.app), tmp_path, api


def post_clip(client, wav, **form):
    data = {"target": "cat", "lang": "en", "picture_onset_ms": "300", **{k: str(v) for k, v in form.items()}}
    return client.post("/api/assess/naming", data=data, files={"audio": ("clip.wav", wav, "audio/wav")})


def test_pages_render(env):
    client, _, _ = env
    for path in ("/assess", "/take"):
        r = client.get(path)
        assert r.status_code == 200 and "Tippa Lingua" in r.text
    assert "no diagnosis or prognosis" in client.get("/assess").text
    # The public test reports numbers only; its wording never judges the person.
    take = client.get("/take").text.lower() + client.get("/static/js/take.js").text.lower()
    for banned in ("impaired", "normal", "diagnos", "screen", "risk"):
        assert banned not in take, banned


def test_timed_response_gives_latency_code_and_receipt(env):
    client, _, api = env
    api.transcripts = ["Cat."]
    r = post_clip(client, wav_with_speech(latency=1.2), set_id="demo_en", item=0).json()
    assert r["code"] == "Correct" and r["transcript"] == "Cat." and r["timeout"] is False
    assert r["latency_ms"] == pytest.approx(1200, abs=10) and r["duration_ms"] == pytest.approx(500, abs=15)
    assert r["receipt"] and assessment.read_receipt(r["receipt"], assess_routes.RECEIPT_KEY)["code"] == "Correct"
    kind, language, seconds = api.calls[0]
    assert (kind, language) == ("transcribe", "en")
    assert seconds == pytest.approx(0.05 + 1.2 + 0.5 + 0.5 + 2 * web.NAMING_PAD_S, abs=0.01)  # from the picture, padded


def test_first_complete_response_is_coded(env):
    client, _, api = env
    api.transcripts = ["Dog, no, cat."]
    r = post_clip(client, wav_with_speech(), set_id="demo_en", item=0).json()
    assert (r["scored_response"], r["code"], r["attempts"]) == ("dog", "Semantic", ["dog", "cat"])


def test_silence_to_the_limit_is_a_timeout_without_transcription(env):
    client, _, api = env
    r = post_clip(client, silent_wav(0.3 + 3.0), time_limit_s=3, set_id="demo_en", item=1).json()
    assert (r["code"], r["timeout"], r["latency_ms"]) == ("NoResponse", True, None)
    assert api.calls == []
    r = post_clip(client, silent_wav(0.3 + 1.0), time_limit_s=3).json()
    assert (r["code"], r["timeout"]) == ("NoResponse", False)  # the examiner moved on before the limit


def test_speech_after_the_time_limit_is_not_scored(env):
    client, _, api = env
    r = post_clip(client, wav_with_speech(latency=4.0), time_limit_s=3).json()
    assert (r["code"], r["timeout"], r["clip_s"]) == ("NoResponse", True, 3.3) and api.calls == []


def test_private_set_items_bring_their_own_alternates(env):
    client, _, api = env
    api.transcripts = ["kitty"]
    r = post_clip(client, wav_with_speech(), alternates=json.dumps(["kitty", "puss"])).json()
    assert r["code"] == "Correct" and r["receipt"] is None
    r = client.post("/api/assess/rescore", json={"target": "sofa", "response": "a couch", "set_id": "demo_en", "item": 1}).json()
    assert r["code"] == "Correct"
    r = client.post("/api/assess/rescore", json={"target": "gato", "response": "es un perro", "lang": "es"}).json()
    assert r["scored_response"] == "perro"


def test_bad_inputs(env):
    client, _, _ = env
    assert post_clip(client, wav_with_speech(), lang="zz").status_code == 422
    assert post_clip(client, b"not audio").status_code in (400, 503)
    assert post_clip(client, silent_wav(0.2), picture_onset_ms=500).status_code == 422


@pytest.mark.parametrize("said, scored", [
    ("dog, no, cat", "dog"), ("c-, cat", "cat"), ("Umbre... umbrella", "umbrella"), ("I don't know. Cat.", "cat"),
    ("Oh, it's a cat.", "cat"), ("it's round, you eat it", "round you eat it"), ("you sit on it", "you sit on it"),
    ("Hmm, let me think, scissors", "scissors"), ("no", ""), ("perro, digo, gato", "perro"), ("Es un gato.", "gato"),
    ("No sé, gato", "gato"),
])
def test_first_complete_response(said, scored):
    lang = "es" if any(w in said for w in ("perro", "gato")) else "en"
    assert assessment.first_complete_response(said, lang, "")["scored"] == scored


def test_summary_uses_reviewer_codes_and_latency_edits():
    items = [{"target": "a", "code": "Correct", "latency_ms": 900}, {"target": "b", "code": "Semantic", "reviewer": "Correct",
             "latency_ms": 1500}, {"target": "c", "code": "Correct", "latency_ms": 1100, "reviewer_latency_ms": 1300},
             {"target": "d", "code": "NoResponse", "timeout": True}, {"target": "p", "code": "Correct", "practice": True,
             "latency_ms": 100}]
    s = assessment.summarize(items)
    assert (s["n"], s["correct"], s["accuracy_pct"], s["timeouts"]) == (4, 3, 75.0, ["d"])
    assert (s["latency_median_ms"], s["latency_q1_ms"], s["latency_q3_ms"]) == (1300, 1100, 1400)


def test_report_pdf(env):
    client, _, _ = env
    items = [{"n": i + 1, "target": w, "transcript": t, "scored_response": t, "code": c, "latency_ms": lat, "timeout": lat is None}
             for i, (w, t, c, lat) in enumerate([("cat", "cat", "Correct", 1100), ("sofa", "", "NoResponse", None),
                                                 ("árbol", "árbol", "Correct", 1400)])]
    body = {"session": {"speaker": "S-01", "set_name": "Demo", "lang": "en", "items": items},
            "history": [{"date": "2026-10-20", "set_name": "Demo", "n": 3, "accuracy_pct": 66.7, "latency_median_ms": 1200}]}
    r = client.post("/api/assess/report.pdf", json=body)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-" and "S-01" in r.headers["content-disposition"]


def test_parallel_forms_are_balanced(env):
    client, _, _ = env
    words = "cat umbrella anchor kettle ladder bench glove spoon carrot bicycle scissors candle".split()
    r = client.post("/api/assess/forms", json={"lang": "en", "words": words}).json()
    assert sorted(r["A"] + r["B"]) == list(range(len(words))) and abs(len(r["A"]) - len(r["B"])) <= 1
    a, b = r["stats"]["A"], r["stats"]["B"]
    assert abs(a["zipf_mean"] - b["zipf_mean"]) < 0.15 and abs(a["phonemes_mean"] - b["phonemes_mean"]) < 0.5
    assert client.post("/api/assess/forms", json={"lang": "en", "words": ["a", "b"]}).status_code == 422


def _receipts(client, api, codes=("Cat", "sofa")):
    out = []
    for item, said in enumerate(codes):
        api.transcripts = [said]
        out.append(post_clip(client, wav_with_speech(latency=0.8 + 0.1 * item), set_id="demo_en", item=item).json()["receipt"])
    return out


def test_reference_range_stores_only_a_summary(env, monkeypatch):
    client, tmp, api = env
    assert client.get("/api/assess/norms/demo_en").json()["n"] == 0
    receipts = _receipts(client, api, ("cat", "dog"))
    bad = {"receipts": receipts, "consent": True, "adult_no_condition": False}
    assert client.post("/api/assess/norms/demo_en", json=bad).status_code == 422
    body = {"receipts": receipts, "consent": True, "adult_no_condition": True, "age_band": "45-59"}
    r = client.post("/api/assess/norms/demo_en", json=body)
    assert r.status_code == 201
    stored = [json.loads(line) for line in (tmp / "norms" / "demo_en.jsonl").read_text().splitlines()]
    assert len(stored) == 1 and set(stored[0]) == {"set", "set_version", "lang", "n_items", "correct", "accuracy_pct",
                                                   "median_latency_ms", "age_band", "date"}
    assert (stored[0]["correct"], stored[0]["accuracy_pct"], stored[0]["median_latency_ms"]) == (1, 50.0, 800)
    assert client.post("/api/assess/norms/demo_en", json=body).status_code == 409  # same receipts twice
    status = client.get("/api/assess/norms/demo_en").json()
    assert status["n"] == 1 and not status["ready"] and "accuracy_pct" not in status

    tampered = receipts[:1] + [receipts[1][:-3] + "abc"]
    assert client.post("/api/assess/norms/demo_en", json={**body, "receipts": tampered}).status_code == 422
    assert client.post("/api/assess/norms/demo_en", json={**body, "receipts": receipts[:1]}).status_code == 422
    assert client.get("/api/assess/norms/other").status_code == 404

    monkeypatch.setattr(assess_routes, "CONTRIBUTIONS_PER_DAY", 100)
    for _ in range(9):
        assert client.post("/api/assess/norms/demo_en", json={**body, "receipts": _receipts(client, api)}).status_code == 201
    status = client.get("/api/assess/norms/demo_en").json()
    assert status["ready"] and status["n"] == 10 and status["correct"]["p95"] == 2.0 and status["n_items"] == 2


def test_contributions_are_limited_per_visitor(env):
    client, _, api = env
    codes = []
    for _ in range(4):
        body = {"receipts": _receipts(client, api), "consent": True, "adult_no_condition": True}
        codes.append(client.post("/api/assess/norms/demo_en", json=body).status_code)
    assert codes == [201, 201, 201, 429]


def test_norms_summary_waits_for_ten():
    recs = [{"n_items": 20, "correct": c, "accuracy_pct": 5.0 * c, "median_latency_ms": 900 + 10 * c} for c in range(11, 20)]
    assert assessment.norms_summary(recs) == {"n": 9, "min_n": 10, "ready": False}
    s = assessment.norms_summary(recs + [{"n_items": 20, "correct": 20, "accuracy_pct": 100.0, "median_latency_ms": 1000}])
    assert s["ready"] and s["correct"]["mean"] == 15.5 and s["correct"]["p5"] == pytest.approx(11.45, abs=0.06)


# --- photo test ----------------------------------------------------------------------------

class FakePhotoAPI:
    def __init__(self):
        self.prompts = []

    def chat(self, messages, reasoning_effort="minimal", **kw):
        text = next(c["text"] for c in messages[0]["content"] if c["type"] == "text")
        self.prompts.append(text)
        if "List the objects" in text:
            reply = json.dumps({"objects": [
                {"name": "kettle", "alternates": ["teakettle"], "english": "kettle", "depiction": "a round kettle"},
                {"name": "kettle", "english": "kettle", "depiction": "dup"},
                {"name": "toaster", "alternates": [], "english": "toaster", "depiction": "a two-slot toaster"},
                {"name": "mug", "alternates": ["cup"], "english": "mug", "depiction": "a mug with a handle"}]})
        else:  # the naming check: Muse Spark calls every picture a kettle, so the toaster needs review
            reply = "kettle"
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])

    def segment(self, image, text, mime="image/png"):
        if text == "mug":
            return [], ""
        return [SamMatch(0, (100.0, 100.0, 300.0, 300.0), (400, 400), 0.9)], ""

    def generate_images(self, prompt, n=1, size=None, output_format="png"):
        buf = io.BytesIO()
        Image.new("RGB", (400, 400), "white").save(buf, "PNG")
        return [buf.getvalue()]


def _photo_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (180, 160, 140)).save(buf, "JPEG")
    return buf.getvalue()


@pytest.mark.parametrize("style", ["line", "photo"])
def test_photo_test_lists_locates_draws_and_checks(style):
    api = FakePhotoAPI()
    out = photo_test.build_from_photo(api, _photo_bytes(), "image/jpeg", "en", style=style, judge=lambda *a: False)
    by = {it["target"]: it for it in out["items"]}
    assert list(by) == ["kettle", "toaster", "mug"] and out["listed"] == 3
    assert by["kettle"]["status"] == "kept" and by["kettle"]["image"].startswith("data:image/")
    assert by["kettle"]["alternates"] == ["teakettle"] and by["toaster"]["status"] == "review"
    assert by["mug"]["located"] is False
    assert by["mug"]["status"] == ("excluded" if style == "photo" else "review")


def test_photo_test_route_hands_back_and_forgets(env, monkeypatch):
    client, _, _ = env
    api = FakePhotoAPI()
    monkeypatch.setattr(web, "get_api", lambda: api)
    r = client.post("/api/assess/photo-test", data={"lang": "en", "style": "photo", "max_items": "4"},
                    files={"photo": ("home.jpg", _photo_bytes(), "image/jpeg")})
    assert r.status_code == 202
    job = r.json()["job"]
    for _ in range(100):
        s = client.get(f"/api/assess/photo-test/{job}").json()
        if s["status"] in ("done", "error"):
            break
        time.sleep(0.05)
    assert s["status"] == "done" and len(s["result"]["items"]) == 3
    assert client.get(f"/api/assess/photo-test/{job}").status_code == 404
    bad = client.post("/api/assess/photo-test", data={"lang": "en"}, files={"photo": ("x.gif", b"GIF89a", "image/gif")})
    assert bad.status_code == 415


def test_a_network_failure_is_a_friendly_502(env):
    import httpx
    client, _, api = env

    def down(wav, language=None):  # MetaAPI.transcribe has already retried by the time this reaches the app
        raise httpx.ConnectError("nodename nor servname provided, or not known")

    api.transcribe = down
    r = post_clip(client, wav_with_speech(), set_id="demo_en", item=0)
    assert r.status_code == 502 and "try again" in r.json()["detail"]


def test_config_lists_language_status_and_answer_forms(env):
    client, tmp, _ = env
    _make_set(tmp / "sets" / "demo_zh", words=("cat", "dog", "cup", "pen", "hat"))
    _make_set(tmp / "sets" / "demo_fr", words=("cat", "dog", "cup", "pen", "hat"))
    for d in ("demo_zh", "demo_fr"):
        m = json.loads((tmp / "sets" / d / "manifest.json").read_text())
        (tmp / "sets" / d / "manifest.json").write_text(json.dumps({**m, "lang": d[-2:]}))
    cfg = client.get("/api/assess/config").json()
    langs = {l["code"]: l for l in cfg["languages"]}
    assert [langs[c]["status"] for c in ("en", "es", "fr", "pt")] == ["verified"] * 4
    assert langs["zh"]["status"] == "works with review" and langs["hi"]["status"] == "experimental"
    assert langs["es"]["example"] == "un gato" and "measure word" in langs["zh"]["instruction"]
    assert [p["id"] for p in cfg["public_sets"]] == ["demo_fr"]  # verified languages, 5+ pictures (demo_en has 2 here)
    assert {l["code"]: l["verified"] for l in client.get("/api/status").json()["languages"]}["pt"] is True


def test_other_languages_are_coded_whole():
    assert assessment.first_complete_response("一只，猫。", "zh", "猫")["scored"] == "一只，猫。"
    assert assessment.first_complete_response("chien, non, chat", "fr", "chat")["scored"] == "chien"
    assert assessment.first_complete_response("Je ne sais pas. Le chat.", "fr", "chat")["scored"] == "le chat"
    assert assessment.first_complete_response("Não sei, o gato", "pt", "gato")["scored"] == "o gato"


def test_wordnet_lookups_are_safe_from_many_threads():
    """The web app scores several responses at once; NLTK's WordNet reader isn't thread-safe."""
    from concurrent.futures import ThreadPoolExecutor

    from metalesionlab import naming_errors
    naming_errors._wordnet.cache_clear()
    wn = naming_errors._wordnet()
    wn._data_file_map.clear()  # force the lazy file loading that raced on Oct 26
    pairs = [("cat", "dog"), ("spoon", "fork"), ("anchor", "ladder"), ("kettle", "pot")] * 8
    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(lambda p: naming_errors.classify(p[0], p[1], "en").code, pairs))
    assert codes[:2] == ["Semantic", "Semantic"] and all(codes[k:k + 4] == codes[:4] for k in range(0, len(codes), 4))


def test_aggregate_norms_writes_only_from_ten(tmp_path, monkeypatch, capsys):
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("aggregate_norms", web.HERE.parents[1] / "scripts" / "aggregate_norms.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "norms").mkdir()
    rec = {"set": "demo_en", "set_version": "v1", "lang": "en", "n_items": 20, "correct": 19, "accuracy_pct": 95.0,
           "median_latency_ms": 950, "age_band": None, "date": "2026-10-31"}
    path = tmp_path / "norms" / "demo_en.jsonl"
    path.write_text("\n".join(json.dumps(rec) for _ in range(9)) + "\n")
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(sys, "argv", ["x", "--data-dir", str(tmp_path), "--out-dir", str(out)])
    mod.main()
    assert not list(out.iterdir()) and "needs 10" in capsys.readouterr().out
    path.write_text(path.read_text() + json.dumps({**rec, "correct": 17, "accuracy_pct": 85.0}) + "\n")
    mod.main()
    data = json.loads((out / "naming_norms_demo_en.json").read_text())
    assert data["n"] == 10 and data["correct"]["min"] == 17 and data["set_version"] == "v1"
    path.write_text(path.read_text() + json.dumps({**rec, "ip": "1.2.3.4"}) + "\n")
    with pytest.raises(SystemExit, match="unexpected fields"):
        mod.main()

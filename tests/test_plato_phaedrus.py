"""Seven meanings (/plato/phaedrus): the sentence, its meanings and Spark's prompt, the transcript checks, the prosody
reader on synthetic speech-like tones, the page and its data, the voice test's two routes (the free reader and the
paid transcription with Spark, through the spend guard and the per-visitor limits), the no-storage rule, and the
series card. A fake API stands in for Meta's; nothing is downloaded or paid for."""
import json
import logging
import re
import struct
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from metalesionlab import audio, meta_api
from metalesionlab import plato_phaedrus as P
from metalesionlab.web import app as web
from metalesionlab.web import guard as G
from metalesionlab.web import plato_phaedrus_routes as R
from metalesionlab.web import site
from metalesionlab.web.limits import DailyLimiter

DATA = web.HERE / "data"
REPO = web.HERE.parents[1]
SR = 16000


def tones(stress: int | None = None, base: float = 150.0, st: float = 5.0, gain: float = 2.0, stretch: float = 1.3,
          lead: float = 0.3):
    """A speech-like stand-in for the sentence: seven harmonic tones (one per word) on a falling melody, with gaps.
    The stressed one is st semitones higher, gain times louder and stretch times longer. Returns samples and the
    8 word boundaries in seconds."""
    durs = [0.15, 0.30, 0.25, 0.18, 0.30, 0.18, 0.45]
    gap = 0.04
    parts, edges, t = [np.zeros(int(lead * SR))], [], lead
    for k, d in enumerate(durs):
        if k == stress:
            d *= stretch
        n = int(d * SR)
        f0 = base * 2 ** (-0.6 * k / 12) * (2 ** (st / 12) if k == stress else 1)
        tt = np.arange(n) / SR
        y = sum(np.sin(2 * np.pi * f0 * hn * tt) / hn for hn in range(1, 11))
        env = np.minimum(1, np.minimum(tt / 0.02, (d - tt) / 0.02))
        amp = 0.12 * (gain if k == stress else 1)
        edges.append(t - (gap / 2 if k else 0))
        parts += [amp * env * y, np.zeros(int(gap * SR))]
        t += n / SR + gap
    edges.append(t - gap)
    parts.append(np.zeros(int(0.3 * SR)))
    return np.concatenate(parts), edges


def wav_bytes(x: np.ndarray, rate: int = SR) -> bytes:
    return audio.pcm16_wav((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes(), rate)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(R, "burst", DailyLimiter(window_s=60))
    monkeypatch.setattr(R, "limiter", DailyLimiter())
    return TestClient(web.app)


class FakeAPI:
    """Voice Transcribe and Muse Spark, offline. Spark picks the option that says it wasn't her."""

    def __init__(self, transcript="I never said she stole my money."):
        self.transcript, self.calls = transcript, []

    def transcribe(self, wav, language=None):
        self.calls.append(("transcribe", len(wav), language))
        return {"transcript": self.transcript, "audioDurationMs": 3000}

    def chat(self, messages, **kw):
        self.calls.append(("chat", kw.get("ledger_tag"), kw.get("reasoning_effort")))
        prompt = messages[0]["content"]
        letter = re.search(r"^([A-G])\. Someone stole the money, but it wasn't her\.$", prompt, re.M).group(1)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=letter))],
                               usage=SimpleNamespace(prompt_tokens=150, completion_tokens=100))


@pytest.fixture
def fake(monkeypatch):
    api = FakeAPI()
    monkeypatch.setattr(web, "get_api", lambda: api)
    monkeypatch.setattr(web, "api_key_present", lambda: True)
    return api


# --- the sentence, the meanings, the prompt ------------------------------------------------------------------

def test_seven_words_seven_meanings_in_the_sentences_order():
    assert P.SENTENCE == "I never said she stole my money." and len(P.WORDS) == 7 == len(P.MEANINGS)
    assert [m.word for m in P.MEANINGS] == list(P.WORDS)
    assert P.MEANINGS[3].gloss == "Someone else stole it, not her." and "borrowed" in P.MEANINGS[4].gloss
    assert len({m.option for m in P.MEANINGS}) == 7
    for m in P.MEANINGS:  # no option says which word was stressed
        assert "stress" not in m.option.lower() and "emphas" not in m.option.lower()


def test_writing_that_keeps_the_stress():
    assert P.stressed_text(3, "caps") == "I never said SHE stole my money."
    assert P.stressed_text(0, "italics") == "*I* never said she stole my money."
    assert P.stressed_text(6, "italics") == "I never said she stole my *money*."


def test_prompt_lists_all_seven_options_in_the_shuffled_order_and_parses_a_letter():
    import random
    order = P.option_order(random.Random(1))
    assert sorted(order) == list(range(7)) and order != list(range(7))
    prompt = P.build_prompt("i never said she stole my money", order)
    assert "i never said she stole my money" in prompt and prompt.endswith("Answer with the letter only.")
    for k, m in enumerate(order):
        assert f"{'ABCDEFG'[k]}. {P.MEANINGS[m].option}" in prompt
    assert P.parse_choice("C", order) == order[2] and P.parse_choice(" b.", order) == order[1]
    assert P.parse_choice("The answer is (E)", order) == order[4] and P.parse_choice("none", order) is None


def test_transcript_checks_find_leaks_and_the_sentence():
    same = P.leaks(["I never said she stole my money."] * 3)
    assert same["identical"] and same["same_words"]
    lk = P.leaks(["I never said she stole my money.", "i never said SHE stole my money", "I never said she stole my money!"])
    assert not lk["identical"] and lk["same_words"] and lk["capitalised_words"] == ["SHE"] and "!" in "".join(lk["punctuation"])
    assert not P.leaks(["I never never said she stole my money."] + ["I never said she stole my money."])["same_words"]
    assert P.is_the_sentence("i never said she stole my money") and P.is_the_sentence("I never never said she stole money")
    assert not P.is_the_sentence("The quick brown fox jumps over the lazy dog.") and not P.is_the_sentence("")


# --- the prosody reader --------------------------------------------------------------------------------------

def test_pitch_tracker_finds_a_harmonic_tone():
    tt = np.arange(int(0.6 * SR)) / SR
    for f in (110.0, 180.0, 260.0):
        x = 0.2 * sum(np.sin(2 * np.pi * f * hn * tt) / hn for hn in range(1, 8))
        f0 = P.pitch_track(x)
        assert abs(np.nanmedian(f0) / f - 1) < 0.02, f
    assert np.isnan(P.pitch_track(np.zeros(SR // 2))).all()


def test_dtw_path_is_monotonic_and_tied_at_both_ends():
    a = np.cumsum(np.ones((30, 2)), axis=0)
    b = np.repeat(a, 2, axis=0)
    path = P.dtw_path(a, b)
    assert tuple(path[0]) == (0, 0) and tuple(path[-1]) == (29, 59)
    assert (np.diff(path, axis=0) >= 0).all()


def templates():
    return [P.Template.from_json(t) for t in json.loads((DATA / "phaedrus_templates.json").read_text())["templates"]]


@pytest.mark.parametrize("k", range(7))
def test_reader_picks_the_word_that_is_higher_louder_and_longer(k):
    x, edges = tones(stress=k)
    r = P.read_stress(x, templates(), bounds_s=edges)
    assert r["guess"] == k, [round(float(v), 2) for v in r["prominence"]["total"]]
    c = P.contour(r)
    assert c["guess"] == k and len(c["bounds"]) == 8 and len(c["words"]) == 7 and len(c["t"]) <= 240


def test_aligner_recovers_word_boundaries_of_a_slower_reading():
    x, edges = tones()
    word_times = [(edges[i] + (0.02 if i else 0), edges[i + 1] - 0.02) for i in range(7)]
    t = P.make_template("tones", x, word_times)
    slow, slow_edges = tones(stress=None, base=140.0)
    slow = np.interp(np.arange(0, len(slow), 1 / 1.15), np.arange(len(slow)), slow)  # 15% slower and lower
    got = P.align(slow, [t])
    want = [e * 1.15 for e in slow_edges]
    assert np.median(np.abs(np.array(got[1:-1]) - np.array(want[1:-1]))) < 0.04


def test_exact_ci_and_binomial_tests():
    lo, hi = P.exact_ci(13, 91)
    assert 0.07 < lo < 0.09 and 0.22 < hi < 0.25
    assert P.exact_ci(0, 10)[0] == 0.0 and P.exact_ci(10, 10)[1] == 1.0
    assert P.binom_p_greater(80, 91) < 1e-30 and P.binom_p_greater(13, 91) > 0.4


# --- the page and its data -----------------------------------------------------------------------------------

def test_page_renders_with_the_verified_epigraph_and_the_listening_first(client):
    r = client.get("/plato/phaedrus")
    assert r.status_code == 200 and r.text.count('<header class="topbar site-head">') == 1 and "{{BRAND}}" not in r.text
    assert 'data-passage="phaedrus-276a"' in r.text and "no more than an image" in r.text
    t = r.text
    # the wow first: the recordings beside what a text-only AI receives, before the charts and the voice test
    assert t.index('id="cards"') < t.index('id="results"') < t.index('id="try"')
    assert t.index("This is all a text-only AI ever receives") < t.index('id="cards"')
    assert "never stored or logged" in t and "sent to Meta’s API" in t
    assert '<button type="button" class="ph-rec-btn" id="rec"' in t


def test_data_api_has_four_voices_of_seven_clips_and_the_results(client):
    d = client.get("/api/plato/phaedrus").json()
    assert d["sentence"] == P.SENTENCE and len(d["meanings"]) == 7
    assert [v["key"] for v in d["voices"]] == list(R.VOICES)
    for v in d["voices"]:
        assert len(v["clips"]) == 7 and v["neutral"]["src"].endswith("/neutral.mp3")
        for k, c in enumerate(v["clips"]):
            assert c["word"] == P.WORDS[k] and c["src"] == f"/api/plato/phaedrus/audio/{v['key']}/{k}_{c['word'].lower()}.mp3"
            assert c["transcript"] and c["contour"]["guess"] == c["reader"] and len(c["contour"]["bounds"]) == 8
    for b in (d["spark"]["transcript"], d["spark"]["caps"], d["spark"]["italics"], d["reader"]):
        assert 0 <= b["ci"][0] <= b["acc"] <= b["ci"][1] <= 1 and b["n"] > 0
    assert d["spark"]["transcript"]["n"] == 91 == d["reader"]["n"] and d["spark"]["caps"]["n"] == 35
    assert sum(map(sum, d["reader"]["confusion"])) == 91


def test_clips_are_served_and_nothing_else(client):
    r = client.get("/api/plato/phaedrus/audio/af_heart/3_she.mp3")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content[:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3")
    for bad in ("af_heart/3_she.wav", "someone/3_she.mp3", "af_heart/8_x.mp3", "af_heart/%2e%2e%2fplato_passages.json",
                "%2e%2e/plato_passages.json", "af_heart/3_she.mp3.mp3"):
        assert client.get(f"/api/plato/phaedrus/audio/{bad}").status_code == 404, bad


def test_missing_data_is_a_friendly_503(client, monkeypatch, tmp_path):
    from metalesionlab.web import plato_atlas_routes
    monkeypatch.setattr(R, "DATA", tmp_path / "none.json")
    plato_atlas_routes._cache.clear()
    assert client.get("/api/plato/phaedrus").status_code == 503
    assert client.get("/plato/phaedrus").status_code == 200


def test_shipped_audio_is_small_and_licensed():
    files = sorted((REPO / "public_data" / "plato_phaedrus_audio").rglob("*.mp3"))
    assert len(files) == 4 * 8 and sum(f.stat().st_size for f in files) < 1_000_000
    pub = json.loads((REPO / "public_data" / "plato_phaedrus.json").read_text())
    assert "Apache-2.0" in pub["license"] and "not included" in pub["license"]
    assert {e["family"] for e in pub["transcripts"]} == {"kokoro", "say", "espeak"} and len(pub["transcripts"]) == 104
    readme = (REPO / "public_data" / "README.md").read_text()
    assert "plato_phaedrus_audio" in readme and "plato_phaedrus.json" in readme


def test_page_assets_follow_the_theme_and_stay_fluid():
    css = (web.HERE / "static" / "css" / "plato_phaedrus.css").read_text()
    js = (web.HERE / "static" / "js" / "plato_phaedrus.js").read_text()
    html = (web.HERE / "pages" / "plato_phaedrus.html").read_text()
    hexes = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    assert not hexes.search(css) and not hexes.search(js)  # colours only through app.css's variables
    assert "clamp(" in css and "auto-fit" in css and "prefers-reduced-motion" in css
    assert not re.search(r"max-width:\s*\d{3}px;\s*margin:\s*0 auto", css)  # no fixed narrow centred column
    assert "localStorage" not in js and "indexedDB" not in js
    assert len(css) + len(js) + len(html) < 100 * 1024


# --- the voice test --------------------------------------------------------------------------------------------

def test_listen_reads_a_recording_without_any_api_call(client, monkeypatch):
    monkeypatch.setattr(web, "get_api", lambda: pytest.fail("the reader must not call the API"))
    x, _ = tones(stress=4)
    r = client.post("/api/phaedrus/listen", content=wav_bytes(x), headers={"content-type": "audio/wav"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert 0 <= d["reader"]["guess"] < 7 and d["reader"]["word"] == P.WORDS[d["reader"]["guess"]]
    assert len(d["contour"]["words"]) == 7 and len(d["contour"]["bounds"]) == 8


@pytest.mark.parametrize("body, status", [
    (b"not a wav at all", 415),
    (None, 422),            # 0.3 s: too short
    ("silent", 422),
    ("long", 413),
    ("44k", 415),
])
def test_recordings_are_checked(client, body, status):
    if body is None:
        body = wav_bytes(np.zeros(int(0.3 * SR)) + 0.01)
    elif body == "silent":
        body = wav_bytes(np.zeros(2 * SR))
    elif body == "long":
        body = wav_bytes(0.1 * np.sin(np.arange(13 * SR) / 10))
    elif body == "44k":
        body = wav_bytes(0.1 * np.sin(np.arange(2 * 44100) / 10), 44100)
    for path in ("/api/phaedrus/listen", "/api/phaedrus/read"):
        r = client.post(path, content=body, headers={"content-type": "audio/wav"})
        assert r.status_code in ((status, 503) if path.endswith("read") else (status,)), (path, r.status_code, r.text)


def test_read_transcribes_then_asks_spark_with_the_experiments_prompt(client, fake):
    x, _ = tones(stress=3)
    r = client.post("/api/phaedrus/read", content=wav_bytes(x), headers={"content-type": "audio/wav"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["transcript"] == P.SENTENCE and d["is_sentence"] and d["spark"]["guess"] == 3 and d["spark"]["word"] == "she"
    assert d["spark"]["gloss"] == P.MEANINGS[3].gloss
    assert [c[0] for c in fake.calls] == ["transcribe", "chat"]
    assert fake.calls[0][2] == "en" and fake.calls[1][1:] == ("phaedrus", "minimal")
    padded = audio.duration_s(wav_bytes(x)) + 2 * R.PAD_S
    assert abs(fake.calls[0][1] - (44 + padded * SR * 2)) < 8  # the WAV, padded with silence


def test_read_skips_spark_when_it_isnt_the_sentence(client, fake):
    fake.transcript = "Hello, is this thing on?"
    x, _ = tones()
    d = client.post("/api/phaedrus/read", content=wav_bytes(x), headers={"content-type": "audio/wav"}).json()
    assert not d["is_sentence"] and d["spark"] is None and "didn't ask Muse Spark" in d["note"]
    assert [c[0] for c in fake.calls] == ["transcribe"]


def test_read_reports_capitals_as_a_trace_of_the_voice(client, fake):
    fake.transcript = "I never said SHE stole my money."
    x, _ = tones()
    d = client.post("/api/phaedrus/read", content=wav_bytes(x), headers={"content-type": "audio/wav"}).json()
    assert d["capitalised"] == ["SHE"]


def test_read_without_a_key_or_over_budget_fails_gracefully(client, monkeypatch, fake):
    x, _ = tones()
    body = wav_bytes(x)
    monkeypatch.setattr(web, "api_key_present", lambda: False)
    r = client.post("/api/phaedrus/read", content=body, headers={"content-type": "audio/wav"})
    assert r.status_code == 503 and "prosody reader" in r.json()["detail"]
    monkeypatch.setattr(web, "api_key_present", lambda: True)
    monkeypatch.setattr(meta_api, "spent", lambda: meta_api.BUDGET_USD)
    r = client.post("/api/phaedrus/read", content=body, headers={"content-type": "audio/wav"})
    assert r.status_code == 503 and "spending cap" in r.json()["detail"] and fake.calls == []
    monkeypatch.setattr(meta_api, "spent", lambda: 0.0)

    def over(*a, **k):
        raise G.DailyCapReached("today's public demo budget is used up")
    monkeypatch.setattr(fake, "transcribe", over)
    r = client.post("/api/phaedrus/read", content=body, headers={"content-type": "audio/wav"})
    assert r.status_code == 503 and "00:00 UTC" in r.json()["detail"] and "still work" in r.json()["detail"]
    assert client.post("/api/phaedrus/listen", content=body, headers={"content-type": "audio/wav"}).status_code == 200


def test_per_visitor_limits(client, monkeypatch, fake):
    x, _ = tones()
    body = wav_bytes(x)
    monkeypatch.setenv("TOT_LIMIT_PHAEDRUS", "2")
    for _ in range(2):
        assert client.post("/api/phaedrus/read", content=body, headers={"content-type": "audio/wav"}).status_code == 200
    r = client.post("/api/phaedrus/read", content=body, headers={"content-type": "audio/wav"})
    assert r.status_code == 429 and "voice tries" in r.json()["detail"]
    monkeypatch.setenv("TOT_LIMIT_PHAEDRUS_BURST", "3")
    monkeypatch.setattr(R, "burst", DailyLimiter(window_s=60))
    for _ in range(3):
        assert client.post("/api/phaedrus/listen", content=body, headers={"content-type": "audio/wav"}).status_code == 200
    r = client.post("/api/phaedrus/listen", content=body, headers={"content-type": "audio/wav"})
    assert r.status_code == 429 and "a minute" in r.json()["detail"]


def test_status_says_what_happens_to_the_recording(client):
    st = client.get("/api/phaedrus/status").json()
    assert "never stored or logged" in st["privacy"] and "Meta’s API" in st["privacy"]
    assert st["max_seconds"] == R.MAX_S and st["limits"]["tries_per_day"] >= 1


# --- the no-storage rule ---------------------------------------------------------------------------------------

def test_recordings_are_never_written_or_logged(client, fake, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)

    def no(*a, **k):
        raise AssertionError("a recording must not touch the disk")
    for name in ("TemporaryDirectory", "NamedTemporaryFile", "mkstemp", "mkdtemp"):
        monkeypatch.setattr(tempfile, name, no)
    monkeypatch.setattr(audio, "to_wav16k", no)
    monkeypatch.setattr(Path, "write_bytes", no)
    monkeypatch.setattr(Path, "write_text", no)
    x, _ = tones(stress=2)
    body = wav_bytes(x)
    for path in ("/api/phaedrus/listen", "/api/phaedrus/read"):
        assert client.post(path, content=body, headers={"content-type": "audio/wav"}).status_code == 200
    assert not any("RIFF" in rec.getMessage() or "base64" in rec.getMessage() for rec in caplog.records)
    src = Path(R.__file__).read_text()
    assert "open(" not in src and "write_bytes" not in src and "log.info" not in src


# --- the spend guard -----------------------------------------------------------------------------------------

def test_the_guard_counts_read_as_paid_and_listen_as_free():
    g = G.Guard(G.Settings(public_demo=True), site="plato")
    assert g.match("POST", "/api/phaedrus/read").bucket == "phaedrus"
    assert g.match("POST", "/api/phaedrus/listen") is None and g.match("GET", "/api/phaedrus/status") is None
    assert G.Guard(G.Settings(public_demo=True), site="lingua").match("POST", "/api/phaedrus/read").bucket == "other"
    assert "Seven meanings" in g.budget_payload()["detail"] and "Seven meanings" in g.budget_payload()["paused"]


def test_at_the_daily_cap_read_stops_and_listen_goes_on(tmp_path, fake, monkeypatch):
    monkeypatch.setattr(R, "burst", DailyLimiter(window_s=60))
    monkeypatch.setattr(R, "limiter", DailyLimiter())
    ledger = tmp_path / "costs.jsonl"
    now = 20_000 * 86400 + 3600
    settings = G.Settings(public_demo=True, daily_usd=0.10, global_per_min=1000, phaedrus_per_day=2)
    guard = G.Guard(settings, ledger_path=lambda: ledger, clock=lambda: now, site="plato",
                    client_ip=lambda request: "9.9.9.9")
    app = FastAPI()
    app.include_router(R.router)
    app.add_middleware(G.GuardMiddleware, guard=guard)
    c = TestClient(app)
    x, _ = tones()
    body = wav_bytes(x)
    assert c.post("/api/phaedrus/read", content=body, headers={"content-type": "audio/wav"}).status_code == 200
    assert c.post("/api/phaedrus/read", content=body, headers={"content-type": "audio/wav"}).status_code == 200
    r = c.post("/api/phaedrus/read", content=body, headers={"content-type": "audio/wav"})
    assert r.status_code == 429 and "voice tries" in r.json()["detail"]  # the guard's own daily limit per visitor
    ledger.write_text(json.dumps({"ts": now, "kind": "chat", "model": "muse-spark-1.3", "usd": 0.10}) + "\n")
    r = c.post("/api/phaedrus/read", content=body, headers={"content-type": "audio/wav"})
    assert r.status_code == 503 and r.json()["guard"] == "budget"
    assert c.post("/api/phaedrus/listen", content=body, headers={"content-type": "audio/wav"}).status_code == 200
    big = audio.pcm16_wav(b"\0\0" * (300 * 1024), SR)
    assert c.post("/api/phaedrus/read", content=big, headers={"content-type": "audio/wav"}).status_code == 413


# --- the series card and Socrates ------------------------------------------------------------------------------

def test_series_card_states_the_finding():
    items = {s["path"]: s for s in site.series(web.app)}
    card = items["/plato/phaedrus"]
    assert card["title"] == "Seven meanings" and card["finding"] and "Spark" in card["finding"]
    assert json.loads((DATA / "series" / "phaedrus.json").read_text())["finding"] == card["finding"]
    landing = TestClient(web.app).get("/").text
    assert 'href="/plato/phaedrus"' in landing and "Can an AI that only reads hear what you meant?" in landing


def test_socrates_knows_the_experiment():
    from metalesionlab import socrates_agent as S
    r = S.plato_experiment("seven meanings")
    assert r["available"] and r["link"] == "/plato/phaedrus" and "Spark" in r["short_answer"]
    assert any(p["id"] == "phaedrus-276a" for p in S.passages())

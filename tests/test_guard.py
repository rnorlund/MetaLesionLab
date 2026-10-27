"""The public-demo spend guard (web/guard.py), offline: a fake clock, a temporary ledger, a toy app."""
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from metalesionlab import meta_api
from metalesionlab.meta_api import BudgetExceeded
from metalesionlab.web import guard as G

DAY = 86400
T0 = 20_000 * DAY + 3600  # 01:00 UTC on some day


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


def spend(ledger: Path, usd: float, ts: float = T0) -> None:
    with ledger.open("a") as f:
        f.write(json.dumps({"ts": ts, "kind": "chat", "model": "muse-spark-1.3", "usd": usd}) + "\n")


def toy_app(guard: G.Guard) -> FastAPI:
    app = FastAPI()

    @app.post("/api/sets")
    async def build(request: Request):
        return {"got": await request.json()}

    @app.post("/api/score/naming")
    async def naming(request: Request):
        return {"bytes": len(await request.body())}

    @app.post("/api/score/naming/text")
    def typed():
        return {"ok": True}

    @app.post("/api/ask")
    def ask():
        return {"answer": "42"}

    @app.post("/api/assess/photo-test")
    def photo():
        return {"job": "x"}

    @app.post("/api/challenge/score")
    def free():
        return {"free": True}

    @app.post("/api/something-new")
    def unknown():
        return {"new": True}

    @app.get("/api/sets")
    def sets():
        return []

    @app.get("/page")
    def page():
        return HTMLResponse("<html><body><p>hi</p></body></html>")

    @app.get("/api/boom")
    def boom():
        guard.check_call(0.0)  # what MetaAPI does before a call
        return {"called": True}

    app.add_middleware(G.GuardMiddleware, guard=guard)
    app.add_exception_handler(G.DailyCapReached, guard.budget_response)
    return app


@pytest.fixture
def setup(tmp_path):
    ledger = tmp_path / "costs.jsonl"
    clock = Clock()
    settings = G.Settings(public_demo=True, daily_usd=0.10, global_per_min=1000)
    guard = G.Guard(settings, ledger_path=lambda: ledger, clock=clock,
                    client_ip=lambda request: request.headers.get("x-test-ip", "1.1.1.1"))
    return SimpleNamespace(guard=guard, ledger=ledger, clock=clock, client=TestClient(toy_app(guard)))


# --- the ledger ------------------------------------------------------------------------------

def test_ledger_sums_today_only_and_reads_new_lines(tmp_path):
    ledger = tmp_path / "costs.jsonl"
    reader = G.DailyLedger(lambda: ledger)
    today = int(T0 // DAY)
    assert reader.spent_on(today) == 0.0  # no ledger yet
    spend(ledger, 5.0, ts=T0 - DAY)  # yesterday
    spend(ledger, 0.25)
    assert reader.spent_on(today) == pytest.approx(0.25)
    assert reader.spent_on(today - 1) == pytest.approx(5.0)
    spend(ledger, 0.5)
    with ledger.open("a") as f:  # a line still being written is left for later
        f.write('{"ts": %s, "usd": 1.0' % T0)
    assert reader.spent_on(today) == pytest.approx(0.75)
    with ledger.open("a") as f:
        f.write("}\nnot json\n")
    assert reader.spent_on(today) == pytest.approx(1.75)
    ledger.write_text("")  # truncated or replaced: start over
    spend(ledger, 0.1)
    assert reader.spent_on(today) == pytest.approx(0.1)


def test_check_call_refuses_at_the_cap_and_resets_at_midnight(setup):
    g = setup.guard
    spend(setup.ledger, 0.08)
    g.check_call(0.01)
    with pytest.raises(G.DailyCapReached):
        g.check_call(0.03)  # would go over
    spend(setup.ledger, 0.02)
    with pytest.raises(BudgetExceeded):  # at the cap, even a call priced at 0 (chat) is refused
        g.check_call(0.0)
    setup.clock.t = (T0 // DAY + 1) * DAY + 1  # next UTC day
    g.check_call(0.05)


def test_meta_api_runs_registered_checks(setup, monkeypatch, tmp_path):
    monkeypatch.setattr(meta_api, "LEDGER", tmp_path / "global.jsonl")
    monkeypatch.setattr(meta_api, "budget_checks", [setup.guard.check_call])
    meta_api._check_budget(0.01)
    spend(setup.ledger, 0.10)
    with pytest.raises(G.DailyCapReached):
        meta_api._check_budget(0.0)


# --- paid routes through the middleware -------------------------------------------------------

def test_paid_route_passes_until_the_daily_cap_then_explains(setup):
    c = setup.client
    assert c.post("/api/score/naming/text", json={}).json() == {"ok": True}
    spend(setup.ledger, 0.10)
    r = c.post("/api/score/naming/text", json={})
    assert r.status_code == 503 and r.headers["x-tippa-guard"] == "budget"
    body = r.json()
    assert "budget for AI calls is used up" in body["detail"] and body["examples"]
    assert int(r.headers["retry-after"]) == DAY - 3600 + 1
    # free routes and reads keep working
    assert c.post("/api/challenge/score", json={}).json() == {"free": True}
    assert c.get("/api/sets").json() == []
    # an API call that slipped past the route check is refused inside, with the same message
    r = c.get("/api/boom")
    assert r.status_code == 503 and r.json()["guard"] == "budget"


def test_burst_limit_per_visitor_and_window(setup):
    c = setup.client
    for _ in range(G.BURST_PER_MIN["score"]):
        assert c.post("/api/score/naming/text", json={}).status_code == 200
    r = c.post("/api/score/naming/text", json={})
    assert r.status_code == 429 and r.headers["x-tippa-guard"] == "rate" and "a minute per visitor" in r.json()["detail"]
    assert c.post("/api/score/naming/text", json={}, headers={"x-test-ip": "2.2.2.2"}).status_code == 200
    setup.clock.t += 61
    assert c.post("/api/score/naming/text", json={}).status_code == 200


def test_global_ceiling(setup):
    setup.guard.s.global_per_min = 3
    c = setup.client
    for i in range(3):
        assert c.post("/api/score/naming/text", json={}, headers={"x-test-ip": f"9.9.9.{i}"}).status_code == 200
    r = c.post("/api/score/naming/text", json={}, headers={"x-test-ip": "9.9.9.9"})
    assert r.status_code == 503 and r.json()["guard"] == "rate" and "busy" in r.json()["detail"]


def test_ask_has_a_daily_limit(setup):
    setup.guard.s.ask_per_day = 2
    c = setup.client
    for _ in range(2):
        assert c.post("/api/ask", json={"q": "why?"}).status_code == 200
        setup.clock.t += 61  # stay under the per-minute limit
    r = c.post("/api/ask", json={"q": "why?"})
    assert r.status_code == 429 and "per visitor per day" in r.json()["detail"]
    setup.clock.t += DAY
    assert c.post("/api/ask", json={"q": "why?"}).status_code == 200


def test_unknown_mutating_routes_count_as_paid(setup):
    c = setup.client
    assert c.post("/api/something-new").json() == {"new": True}
    spend(setup.ledger, 0.10)
    assert c.post("/api/something-new").status_code == 503


def test_builds_are_tiny(setup):
    c = setup.client
    words = "\n".join(["cat", "dog", "cup", "hat", "sun"])
    r = c.post("/api/sets", json={"words": words, "candidates": 2})
    assert r.status_code == 422 and "up to 4 words" in r.json()["detail"]
    r = c.post("/api/sets", json={"words": "cat\ndog\ncat: a pet", "candidates": 3, "lang": "en"})
    assert r.status_code == 200
    assert r.json()["got"] == {"words": "cat\ndog\ncat: a pet", "candidates": 2, "lang": "en"}
    assert "up to 2 pictures" in r.headers["x-tippa-guard-note"]


def test_build_estimate_counts_against_the_cap(setup):
    spend(setup.ledger, 0.05)
    r = setup.client.post("/api/sets", json={"words": "cat\ndog\ncup\nhat", "candidates": 2})  # about $0.13
    assert r.status_code == 503 and r.json()["guard"] == "budget"


def test_builds_and_photo_tests_can_be_off(setup):
    setup.guard.s.build_words = 0
    r = setup.client.post("/api/sets", json={"words": "cat"})
    assert r.status_code == 403 and r.json()["guard"] == "off"
    r = setup.client.post("/api/assess/photo-test", files={"photo": ("p.jpg", b"x" * 10, "image/jpeg")})
    assert r.status_code == 403 and "photo" in r.json()["detail"]


def test_audio_size_cap(setup):
    c = setup.client
    small = c.post("/api/score/naming", content=b"x" * 1000, headers={"content-type": "application/octet-stream"})
    assert small.json() == {"bytes": 1000}
    big = b"x" * (int(2.5 * G.MB) + 1)
    r = c.post("/api/score/naming", content=big, headers={"content-type": "application/octet-stream"})
    assert r.status_code == 413 and r.headers["x-tippa-guard"] == "size"

    def chunks():  # no Content-Length: counted as it arrives
        for _ in range(3):
            yield b"x" * G.MB
    r = c.post("/api/score/naming", content=chunks(), headers={"content-type": "application/octet-stream"})
    assert r.status_code == 413


def test_pages_get_the_banner_and_api_doesnt(setup):
    page = setup.client.get("/page")
    assert page.text.endswith(G.BANNER_TAG.decode() + "</body></html>")
    assert int(page.headers["content-length"]) == len(page.content)
    assert "guard-banner" not in setup.client.get("/api/sets").text


def test_route_matching():
    g = G.Guard(G.Settings(public_demo=True))
    bucket = lambda m, p: (r.bucket if (r := g.match(m, p)) else None)  # noqa: E731
    assert bucket("POST", "/api/sets") == "build"
    assert bucket("PATCH", "/api/sets/demo_en/items/3") is None
    assert bucket("POST", "/api/score/naming/text") == "score"
    assert bucket("POST", "/api/assess/naming") == "score"
    assert bucket("POST", "/api/assess/rescore") == "score"
    assert bucket("POST", "/api/score/description") == "score"
    assert bucket("POST", "/api/scenes") == "scene"
    assert bucket("GET", "/api/ask/stream") == "ask" and bucket("POST", "/api/ask") == "ask"
    assert bucket("POST", "/api/assess/report.pdf") is None and bucket("POST", "/api/assess/norms/demo_en") is None
    assert bucket("GET", "/api/lab/conditions") is None and bucket("GET", "/take") is None
    assert bucket("DELETE", "/api/whatever") == "other"


# --- wiring ------------------------------------------------------------------------------------

def test_local_mode_leaves_the_app_alone():
    from metalesionlab.web import app as web
    assert not any(m.cls is G.GuardMiddleware for m in web.app.user_middleware)
    assert meta_api.budget_checks == []
    assert TestClient(web.app).get("/api/guard").json() == {"public_demo": False}


def test_settings_from_env():
    s = G.Settings.from_env({"PUBLIC_DEMO": "1", "TIPPA_PUBLIC_DAILY_USD": "0.5", "TIPPA_PUBLIC_BUILD_WORDS": "0",
                             "TIPPA_PUBLIC_BUILD_CANDIDATES": "9"})
    assert s.public_demo and s.daily_usd == 0.5 and s.build_words == 0 and s.build_candidates == 3
    assert not G.Settings.from_env({}).public_demo


def test_configure_web(monkeypatch):
    for bucket in G.PUBLIC_LIMITS:
        monkeypatch.delenv(f"TOT_LIMIT_{bucket.upper()}", raising=False)
    monkeypatch.setenv("TOT_LIMIT_SCORE", "5")  # an explicit setting wins
    web = SimpleNamespace(PUBLIC=False, ALLOW_BUILDS=True, MAX_WORDS=24,
                          MAX_CLIP_S={"naming": 30, "description": 240, "fluency": 120})
    G.configure_web(web, G.Settings(public_demo=True))
    assert web.PUBLIC and web.ALLOW_BUILDS and web.MAX_WORDS == 4
    assert web.MAX_CLIP_S == {"naming": 30, "description": 90, "fluency": 60}
    assert os.environ["TOT_LIMIT_BUILD"] == "2" and os.environ["TOT_LIMIT_SCENE"] == "1"
    assert os.environ["TOT_LIMIT_SCORE"] == "5"
    G.configure_web(web, G.Settings(public_demo=True, build_words=0))
    assert not web.ALLOW_BUILDS


def test_whole_app_in_public_mode(tmp_path):
    """The real app started with PUBLIC_DEMO=1 (in a fresh process, so other tests keep local mode)."""
    ledger = tmp_path / "costs.jsonl"
    spend(ledger, 0.6, ts=time.time())
    script = textwrap.dedent("""
        import json
        from fastapi.testclient import TestClient
        from metalesionlab import meta_api
        from metalesionlab.web import app as web
        c = TestClient(web.app)
        out = {"page": "guard-banner.js" in c.get("/").text,
               "guard": c.get("/api/guard").json(),
               "status": c.get("/api/status").json(),
               "typed": c.post("/api/score/naming/text", json={"target": "cat", "response": "dog"}).json(),
               "public": web.PUBLIC, "max_words": web.MAX_WORDS, "clip": web.MAX_CLIP_S}
        try:
            meta_api._check_budget(0.0)
            out["hook"] = "allowed"
        except meta_api.BudgetExceeded as e:
            out["hook"] = type(e).__name__
        print(json.dumps(out))
    """)
    env = {**os.environ, "PUBLIC_DEMO": "1", "TIPPA_PUBLIC_DAILY_USD": "0.5", "MLL_LEDGER": str(ledger),
           "TIPPA_DATA_DIR": str(tmp_path / "data"), "MODEL_API_KEY": "test-not-a-key"}
    env.pop("TOT_LIMIT_BUILD", None)
    run = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=120,
                         cwd=Path(__file__).resolve().parents[1])
    assert run.returncode == 0, run.stderr[-2000:]
    out = json.loads(run.stdout.strip().splitlines()[-1])
    assert out["page"] and out["public"] and out["max_words"] == 4
    assert out["clip"] == {"naming": 30, "description": 90, "fluency": 60}
    assert out["guard"]["public_demo"] and out["guard"]["exhausted"] and out["guard"]["daily_cap_usd"] == 0.5
    assert out["status"]["limits"]["build"]["per_day"] == 2
    assert out["typed"]["guard"] == "budget"
    assert out["hook"] == "DailyCapReached"

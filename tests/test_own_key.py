"""A judge's own Meta API key (web/own_key.py, static/js/ownkey.js): kept in the browser tab, sent only with Ask
Socrates and the voice test, used for that request only (never stored, logged or billed to the demo), and it lifts the
demo's daily dollar caps but not the per-visitor limits. Also: the header stays on one line (static/js/navfit.js)."""
import json
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from metalesionlab import meta_api
from metalesionlab import socrates_agent as S
from metalesionlab.web import app as web
from metalesionlab.web import guard as G
from metalesionlab.web import own_key, site, socrates_routes
from tests.test_socrates import FakeAPI, _call, _lines, _reply

STATIC = web.HERE / "static"
JS = (STATIC / "js" / "ownkey.js").read_text()
NAVFIT = (STATIC / "js" / "navfit.js").read_text()
KEY = "LLM|judge_key_1234567890abcdef"


def test_only_key_shaped_values_are_taken():
    ok = {"x-meta-key": KEY}
    assert own_key.key_of(ok) == KEY and own_key.key_of({"x-meta-key": "  " + KEY + " "}) == KEY
    for bad in ("", "short", "has space " + "x" * 30, 'quote"' + "x" * 30, "x" * 401, "new\nline" + "x" * 30):
        assert own_key.key_of({"x-meta-key": bad}) is None, bad
    assert own_key.key_of({}) is None


def test_an_own_key_client_neither_checks_nor_records_the_demos_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_api, "LEDGER", tmp_path / "costs.jsonl")
    monkeypatch.setattr(meta_api, "BUDGET_USD", 0.5)
    api = own_key.api_for(SimpleNamespace(headers={"x-meta-key": KEY}))
    assert api.metered is False
    usage = SimpleNamespace(model_dump=lambda: {"prompt_tokens": 10, "completion_tokens": 5})
    monkeypatch.setattr(api.client.chat.completions, "create", lambda **kw: SimpleNamespace(usage=usage, choices=[]))
    meta_api.LEDGER.write_text(json.dumps({"ts": time.time(), "kind": "chat", "usd": 1.0}) + "\n")  # the demo is out of money
    api.chat([{"role": "user", "content": "hi"}])  # no BudgetExceeded, and nothing written
    assert len(meta_api.LEDGER.read_text().splitlines()) == 1
    site_api = meta_api.MetaAPI(api_key="site-key-0123456789abcdef")
    with pytest.raises(meta_api.BudgetExceeded):
        site_api.chat([{"role": "user", "content": "hi"}])


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_api, "LEDGER", tmp_path / "costs.jsonl")
    script = lambda n: (_reply(None, [_call("plato_stats", {"concept": "chair"}, n)]) if n % 2 == 0
                        else _reply("Spread 0.13 [plato_stats: chair].\n\nWhat is a chair for?"))
    made = []

    def make(history, context, mode="ask", concept=None, api=None):
        made.append(api)
        return S.SocratesAgent(FakeAPI(script), history=history, context=context, mode=mode, concept=concept)
    monkeypatch.setattr(socrates_routes, "make_agent", make)
    monkeypatch.setattr(web, "api_key_present", lambda: True)
    for var in ("TIPPA_SOCRATES_SESSION_TURNS", "TIPPA_SOCRATES_IP_TURNS", "TIPPA_SOCRATES_DAILY_USD"):
        monkeypatch.delenv(var, raising=False)
    socrates_routes.sessions.clear()
    socrates_routes.addresses.clear()
    monkeypatch.setattr(socrates_routes, "spend", socrates_routes.agent_routes._Spend(
        tag="socrates", cap=socrates_routes.daily_usd, reserve_usd=socrates_routes.RESERVE_USD))
    c = TestClient(web.app)
    c.made = made
    return c


def test_ask_socrates_on_an_own_key_past_the_demos_daily_budget(client):
    with meta_api.LEDGER.open("a") as f:  # today's Socrates budget is spent
        f.write(json.dumps({"ts": time.time(), "kind": "chat", "usd": 5.0, "tag": "socrates"}) + "\n")
    assert client.post("/api/socrates", json={"question": "chair?"}).status_code == 503
    st = client.get("/api/socrates/status", headers={"X-Meta-Key": KEY}).json()
    assert st["own_key"] and st["budget_left"] and st["enabled"]
    assert client.get("/api/socrates/status").json()["own_key"] is False
    r = client.post("/api/socrates", json={"question": "chair?"}, headers={"X-Meta-Key": KEY})
    assert r.status_code == 200 and _lines(r)[-2]["type"] == "answer"
    api = client.made[-1]
    assert api.meta.metered is False and api.make_claude is None  # their key, and no backup on the demo's account
    assert socrates_routes.spend.reserved == 0


def test_an_own_key_skips_the_guards_dollar_cap_but_not_its_rate_limits(tmp_path):
    ledger = tmp_path / "costs.jsonl"
    ledger.write_text(json.dumps({"ts": time.time(), "kind": "chat", "usd": 1.0}) + "\n")
    guard = G.Guard(G.Settings(public_demo=True, daily_usd=0.10, global_per_min=1000, socrates_per_day=2),
                    ledger_path=lambda: ledger, client_ip=lambda request: "9.9.9.9")
    app = FastAPI()

    @app.post("/api/socrates")
    def answer():
        return {"ok": True}
    app.add_middleware(G.GuardMiddleware, guard=guard)
    c = TestClient(app)
    assert c.post("/api/socrates", json={}).status_code == 503  # the demo's budget is spent
    mine = {"X-Meta-Key": KEY}
    assert [c.post("/api/socrates", json={}, headers=mine).status_code for _ in range(3)] == [200, 200, 429]


@pytest.mark.parametrize("path", ["/", "/plato", "/socrates", "/plato/phaedrus", "/damaged"])
def test_every_plato_page_gets_the_key_dialog_and_the_one_line_header(client, path):
    page = client.get(path).text
    assert page.count("/static/js/ownkey.js") == 1 and page.count("/static/css/ownkey.css") == 1
    assert page.count("/static/js/navfit.js") == 1
    once = site.add_own_key(site.add_navfit("<head></head>"))
    assert site.add_own_key(site.add_navfit(once)) == once


def test_the_key_stays_in_the_tab_and_goes_only_to_the_paid_routes():
    assert "sessionStorage" in JS and "localStorage" not in JS
    assert "/^\\/api\\/(socrates|phaedrus|plato\\/redraw|plato\\/telephone)(\\/|$|\\?)/" in JS and "X-Meta-Key" in JS
    assert "never stores or logs it" in JS
    assert "nav-accent" in NAVFIT and "nav-star" in NAVFIT and "innerWidth <= 860" in NAVFIT

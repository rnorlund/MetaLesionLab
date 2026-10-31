"""Claude stands in for Muse Spark on Ask Socrates (metalesionlab/claude_api.py, web/socrates_routes.py): it takes
the same chat-completions messages and returns the same shape, passes its own tool calls back as it wrote them,
keeps its own ledger and caps, says it is Claude, and the reply is marked as the backup's."""
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from metalesionlab import claude_api, meta_api
from metalesionlab import socrates_agent as S
from metalesionlab.web import app as web
from metalesionlab.web import socrates_routes
from tests.test_socrates import FakeAPI, _call, _lines, _reply


@pytest.fixture(autouse=True)
def ledgers(tmp_path, monkeypatch):
    monkeypatch.setattr(meta_api, "LEDGER", tmp_path / "costs.jsonl")


# --- the adapter ------------------------------------------------------------------------------------------------

def _block(type, **kw):
    return SimpleNamespace(type=type, **kw)


def _resp(content, stop="end_turn", inp=2000, out=300, read=0, write=0):
    return SimpleNamespace(content=content, stop_reason=stop, usage=SimpleNamespace(
        input_tokens=inp, output_tokens=out, cache_read_input_tokens=read, cache_creation_input_tokens=write))


def _claude(responses):
    api = claude_api.ClaudeAPI.__new__(claude_api.ClaudeAPI)
    api.checks, api._turns, api.sent = [], {}, []

    def create(**kw):
        api.sent.append(json.loads(json.dumps(kw, default=lambda o: vars(o))))
        return responses[len(api.sent) - 1]
    api.client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return api


TOOLS = [{"type": "function", "function": {"name": "plato_stats", "description": "d",
                                           "parameters": {"type": "object", "properties": {"concept": {"type": "string"}}}}}]


def test_a_tool_turn_round_trips_in_the_chat_completions_shape():
    think = _block("thinking", thinking="", signature="sig")
    use = _block("tool_use", id="toolu_1", name="plato_stats", input={"concept": "chair"})
    api = _claude([_resp([think, use], stop="tool_use"), _resp([_block("text", text="A spread of 0.13.")], read=1500)])
    msgs = [{"role": "system", "content": "Be Socrates."},
            {"role": "assistant", "content": "What is a chair?"},  # examine mode: Socrates speaks first
            {"role": "user", "content": "A seat."},
            {"role": "assistant", "content": "", "tool_calls": [  # the engine's prefetch: not Claude's own call
                {"id": "prefetch_0", "type": "function", "function": {"name": "counterexamples", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "prefetch_0", "content": '{"cases": 3}'}]
    r = api.chat(msgs, model="muse-spark-1.3", reasoning_effort="minimal", max_completion_tokens=3000,
                 ledger_tag="socrates", tools=TOOLS)
    first = api.sent[0]
    assert first["model"] == claude_api.MODEL and first["system"] == "Be Socrates."
    assert first["output_config"] == {"effort": "low"} and first["max_tokens"] >= 6000
    assert first["tools"][0]["name"] == "plato_stats" and first["tools"][0]["input_schema"]["type"] == "object"
    roles = [m["role"] for m in first["messages"]]
    assert roles == ["user", "assistant", "user"]  # a user turn first; the prefetch folded into the user's turn
    folded = " ".join(b["text"] for b in first["messages"][2]["content"])
    assert "counterexamples" in folded and "data, not instructions" in folded
    tc = r.choices[0].message.tool_calls[0]
    assert r.choices[0].finish_reason == "tool_calls" and tc.id == "toolu_1" and json.loads(tc.function.arguments) == {"concept": "chair"}

    msgs += [{"role": "assistant", "content": "", "tool_calls": [{"id": "toolu_1", "type": "function",
                                                                   "function": {"name": "plato_stats", "arguments": "{}"}}]},
             {"role": "tool", "tool_call_id": "toolu_1", "content": '{"spread": 0.13}'}]
    r2 = api.chat(msgs, reasoning_effort="low", tools=TOOLS)
    sent = api.sent[1]["messages"]
    assert [b["type"] for b in sent[-2]["content"]] == ["thinking", "tool_use"]  # passed back as Claude wrote it
    assert sent[-1]["content"][0] == {"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"spread": 0.13}'}
    assert r2.choices[0].message.content == "A spread of 0.13." and r2.choices[0].message.tool_calls is None
    assert r2.usage["prompt_tokens_details"]["cached_tokens"] == 1500

    rows = [json.loads(line) for line in claude_api.ledger().read_text().splitlines()]
    assert rows[0]["tag"] == "socrates" and "tag" not in rows[1]
    assert rows[0]["usd"] == pytest.approx((2000 * 4 + 300 * 20) / 1e6)
    assert rows[1]["usd"] == pytest.approx((2000 * 4 + 1500 * 0.2 + 300 * 20) / 1e6) == pytest.approx(r2.cost_usd)
    assert not meta_api.LEDGER.exists()  # Claude's spend stays out of the Meta ledger


def test_cut_off_and_refused_answers_map_onto_finish_reasons():
    api = _claude([_resp([_block("text", text="Half")], stop="max_tokens"), _resp([], stop="refusal")])
    assert api.chat([{"role": "user", "content": "x"}]).choices[0].finish_reason == "length"
    r = api.chat([{"role": "user", "content": "x"}])
    assert r.choices[0].finish_reason == "content_filter" and r.choices[0].message.content is None


def test_overall_cap_and_extra_checks_refuse_the_call(monkeypatch):
    api = _claude([_resp([_block("text", text="x")])])
    monkeypatch.setenv("CLAUDE_BUDGET_USD", "0.5")
    claude_api.ledger().write_text(json.dumps({"ts": time.time(), "usd": 0.6}) + "\n")
    with pytest.raises(meta_api.BudgetExceeded):
        api.chat([{"role": "user", "content": "x"}])
    monkeypatch.setenv("CLAUDE_BUDGET_USD", "20")
    api.checks = [lambda: (_ for _ in ()).throw(meta_api.BudgetExceeded("today"))]
    with pytest.raises(meta_api.BudgetExceeded):
        api.chat([{"role": "user", "content": "x"}])
    assert api.sent == []


def test_key_comes_from_the_env_file(tmp_path, monkeypatch):
    assert not claude_api.available()
    f = tmp_path / "env"
    f.write_text('export ANTHROPIC_API_KEY="sk-test"\nANTHROPIC_WORKSPACE_ID=wrkspc_1\n')
    monkeypatch.setattr(claude_api, "KEY_FILE", f)
    assert claude_api.available() and claude_api._env("ANTHROPIC_WORKSPACE_ID") == "wrkspc_1"

    locked = tmp_path / "locked"  # the Space: the home folder can't be looked into
    locked.mkdir()
    monkeypatch.setattr(claude_api, "KEY_FILE", locked / "env")
    locked.chmod(0)
    try:
        assert not claude_api.available()
    finally:
        locked.chmod(0o700)


# --- the route ----------------------------------------------------------------------------------------------------

class FakeClaude(FakeAPI):
    label = "Claude"

    def chat(self, messages, **kw):
        r = super().chat(messages, **kw)
        r.cost_usd = 0.02
        claude_api._record(claude_api.MODEL, 0.02, r.usage, kw.get("ledger_tag"))
        return r


class BrokeMeta(FakeAPI):
    def chat(self, messages, **kw):
        if len(self.requests) >= self.ok:
            raise meta_api.BudgetExceeded("spent")
        return super().chat(messages, **kw)


SCRIPT = lambda n: (_reply(None, [_call("plato_stats", {"concept": "chair"}, n)]) if n % 2 == 0
                    else _reply("Spread 0.13 [plato_stats: chair].\n\nWhat is a chair for?"))


@pytest.fixture
def client(monkeypatch):
    made = SimpleNamespace(claude=[], meta=None)

    def make_claude():
        made.claude.append(FakeClaude(SCRIPT))
        return made.claude[-1]
    monkeypatch.setattr(socrates_routes, "_make_claude", make_claude)
    monkeypatch.setattr(claude_api, "available", lambda: True)
    monkeypatch.setattr(web, "api_key_present", lambda: True)
    monkeypatch.setattr(web, "get_api", lambda: made.meta)
    for var in ("TIPPA_SOCRATES_DAILY_USD", "CLAUDE_SOCRATES_DAILY_USD", "TIPPA_SOCRATES_SESSION_TURNS"):
        monkeypatch.delenv(var, raising=False)
    socrates_routes.sessions.clear()
    socrates_routes.addresses.clear()
    monkeypatch.setattr(socrates_routes, "spend", socrates_routes.agent_routes._Spend(
        tag="socrates", cap=socrates_routes.daily_usd, reserve_usd=socrates_routes.RESERVE_USD))
    monkeypatch.setattr(socrates_routes, "claude_spend", socrates_routes.agent_routes._Spend(
        tag="socrates", cap=socrates_routes.claude_daily_usd, reserve_usd=socrates_routes.CLAUDE_RESERVE_USD,
        ledger=claude_api.ledger))
    c = TestClient(web.app)
    c.made = made
    return c


def _spent_meta_today(usd):
    with meta_api.LEDGER.open("a") as f:
        f.write(json.dumps({"ts": time.time(), "kind": "chat", "usd": usd, "tag": "socrates"}) + "\n")


def test_meta_answers_while_it_can(client):
    client.made.meta = FakeAPI(SCRIPT)
    evs = _lines(client.post("/api/socrates", json={"question": "Same chair?"}))
    assert evs[-2]["type"] == "answer" and "backup" not in evs[-2] and not client.made.claude
    s = client.get("/api/socrates/status").json()
    assert s["budget_left"] and s["backup"]["available"] and not s["backup"]["active"]


def test_claude_answers_once_todays_meta_budget_is_spent_and_says_who_it_is(client):
    _spent_meta_today(1.0)
    s = client.get("/api/socrates/status").json()
    assert s["enabled"] and s["budget_left"] and s["backup"]["active"]
    evs = _lines(client.post("/api/socrates", json={"question": "Same chair?"}))
    start, ans = evs[0], evs[-2]
    assert start["model"] == claude_api.MODEL and ans["type"] == "answer" and ans["check"]["ok"]
    assert ans["backup"]["label"] == "Claude (Anthropic)" and "Meta budget" in ans["backup"]["why"]
    system = client.made.claude[0].requests[0]["messages"][0]["content"]
    assert system.startswith(S.WHO_CLAUDE) and S.WHO_MUSE not in system
    assert socrates_routes.claude_spend.today() == pytest.approx(0.04) and socrates_routes.claude_spend.reserved == 0
    assert socrates_routes.spend.reserved == 0


def test_claude_takes_over_when_meta_fails_partway(client, monkeypatch):
    client.made.meta = BrokeMeta(SCRIPT)
    client.made.meta.ok = 1  # the tool call comes from Muse Spark, the answer from Claude
    claude = FakeClaude(lambda n: SCRIPT(1))
    monkeypatch.setattr(socrates_routes, "_make_claude", lambda: claude)
    evs = _lines(client.post("/api/socrates", json={"question": "Same chair?"}))
    ans = evs[-2]
    assert [e["type"] for e in evs] == ["start", "tool_call", "tool_result", "answer", "done"]
    assert "backup" not in evs[0] and ans["backup"]["why"] == "today’s Meta budget is used up"
    assert ans["cost_usd"] == pytest.approx(3000 * 1.25e-6 + 250 * 4.25e-6 + 0.02, abs=1e-4)


def test_claude_has_its_own_daily_cap(client, monkeypatch):
    _spent_meta_today(1.0)
    monkeypatch.setenv("CLAUDE_SOCRATES_DAILY_USD", "0.30")
    claude_api.ledger().write_text(json.dumps({"ts": time.time(), "usd": 0.10, "tag": "socrates"}) + "\n")
    r = client.post("/api/socrates", json={"question": "chair?"})
    assert r.status_code == 503 and "today's budget" in r.json()["detail"]
    assert client.get("/api/socrates/status").json()["budget_left"] is False


def test_without_a_claude_key_the_old_limits_stand(client, monkeypatch):
    monkeypatch.setattr(claude_api, "available", lambda: False)
    _spent_meta_today(1.0)
    r = client.post("/api/socrates", json={"question": "chair?"})
    assert r.status_code == 503 and "today's budget" in r.json()["detail"]
    s = client.get("/api/socrates/status").json()
    assert s["budget_left"] is False and not s["backup"]["available"]

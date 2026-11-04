"""Ask Socrates (/socrates): a short dialogue with Muse Spark playing Socrates about the Plato experiments.

POST /api/socrates takes the visitor's message, the dialogue so far (kept by the browser; nothing is
stored here) and, optionally, the visitor's drawing from /draw, and streams the agent's steps as JSON
lines, like /api/ask. The agent is metalesionlab/socrates_agent.py, on the engine Ask the Lab uses.

Request body:
    {"question": "...",                                   1-500 characters
     "history": [{"role": "visitor", "text": "..."},
                 {"role": "socrates", "text": "...", "tools": [{"name": "plato_stats", "args": {"concept": "chair"}}]},
                 ...],                                    at most 2 x MAX_TURNS items, each text up to 4,000 characters
     "context": {"concept": "chair", "originality": 73.4,  optional, from /draw's result: originality percentile,
                 "people_closer_to_muse": 40.5, "muse_closer": 12.0, "d_nearest_ai": 0.31, "d_nearest_human": 0.27,
                 "looks_like": ["chair", "bench"], "n_people": 200},
     "mode": "ask" | "examine",                            optional, default "ask"
     "concept": "chair" | "clock" | "bird" | "game"}       with mode "examine": what Socrates asks you to define
In "examine" mode ("Let him examine you") the history starts with the visitor's first definition: Socrates'
opening question is the page's own (from /api/socrates/status) and costs nothing. An examination has at most
socrates_agent.EXAMINE_MAX exchanges.
"tools" are the names and arguments the answer event returned in tools_used; they are re-run here for the
checks, never trusted as results. A dialogue has at most socrates_agent.MAX_TURNS visitor messages.

Limits for this route (a site-wide guard may add its own):
- TIPPA_SOCRATES_SESSION_TURNS (default 24) turns per browser session per day, counted by a cookie, and
  TIPPA_SOCRATES_IP_TURNS (default 60) per address per day.
- TIPPA_SOCRATES_DAILY_USD (default 1.00): spend today (UTC) from ledger entries tagged "socrates", plus
  a reserve for each turn in flight.
- MetaAPI's overall budget cap still applies.

Claude stands in when Muse Spark can't answer, so a visitor never gets an empty reply: when the Meta key is
missing, the Meta budget (overall or today's for Socrates) is spent, or the Meta API fails partway through a turn
(metalesionlab/claude_api.py, if an Anthropic key is set). It has its own ledger and limits:
- CLAUDE_SOCRATES_DAILY_USD (default 2.00): Claude's spend today on Socrates, plus a reserve per turn in flight.
- CLAUDE_BUDGET_USD (default 20.00): Claude's overall cap (claude_api.py).
Claude says it is Claude standing in for Muse Spark, and the reply is marked "backup" so the page can say so.

app.py includes this router with one line.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Callable, Literal

import httpx
import openai

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from metalesionlab import claude_api, meta_api, socrates_agent
from metalesionlab.web import agent_routes, own_key
from metalesionlab.web import app as web
from metalesionlab.web.limits import client_ip

log = logging.getLogger(__name__)
router = APIRouter()

COOKIE = "tl_socrates"
RESERVE_USD = 0.05  # held per turn in flight; a typical turn costs $0.01-0.03
CLAUDE_TURN_USD = 0.25  # Claude's per-turn cap (Opus costs about three times Muse Spark per token)
CLAUDE_RESERVE_USD = 0.25
STARTERS = [
    "Did the AI really draw the same chair 16 times?",
    "What would Plato say about AI art?",
    "Are people any different?",
    "Do all image AIs break the same way when damaged?",
    "Can you talk an AI out of the Platonic chair?",
]


def daily_usd() -> float:
    return float(os.environ.get("TIPPA_SOCRATES_DAILY_USD", "1"))


def session_cap() -> int:
    return int(os.environ.get("TIPPA_SOCRATES_SESSION_TURNS", "24"))


def ip_cap() -> int:
    return int(os.environ.get("TIPPA_SOCRATES_IP_TURNS", "60"))


def claude_daily_usd() -> float:
    return float(os.environ.get("CLAUDE_SOCRATES_DAILY_USD", "2"))


spend = agent_routes._Spend(tag=socrates_agent.LEDGER_TAG, cap=daily_usd, reserve_usd=RESERVE_USD)
claude_spend = agent_routes._Spend(tag=socrates_agent.LEDGER_TAG, cap=claude_daily_usd, reserve_usd=CLAUDE_RESERVE_USD,
                                   ledger=claude_api.ledger)


def _claude_today_check() -> None:
    if claude_spend.today() >= claude_daily_usd():
        raise meta_api.BudgetExceeded("Claude has used today's budget for Socrates")


class MetaThenClaude:
    """Muse Spark first; Claude for the rest of the turn once the Meta API can't answer (its budget is spent or
    it fails after its own retries). `claude` makes the stand-in when it's first needed (None: no stand-in)."""

    WHY = {"budget": "today’s Meta budget is used up", "error": "the Meta Model API didn’t answer"}

    def __init__(self, meta, claude: Callable[[], claude_api.ClaudeAPI] | None, why: str | None = None):
        self.meta, self.make_claude, self.claude = meta, claude, None
        self.why = why if meta is None else None  # set: Claude from the start
        self.switched: Callable[[], None] | None = None

    @property
    def on_claude(self) -> bool:
        return self.why is not None

    @property
    def label(self) -> str:
        return "Claude" if self.on_claude else "Muse Spark"

    def chat(self, messages, **kw):
        if not self.on_claude:
            try:
                return self.meta.chat(messages, **kw)
            except (meta_api.BudgetExceeded, openai.OpenAIError, httpx.HTTPError) as e:
                if self.make_claude is None:
                    raise
                log.warning("socrates: Meta API can't answer (%s); Claude stands in", type(e).__name__)
                self.why = "budget" if isinstance(e, meta_api.BudgetExceeded) else "error"
                if self.switched:
                    self.switched()
        if self.claude is None:
            self.claude = self.make_claude()
        swapped = [{**m, "content": m["content"].replace(socrates_agent.WHO_MUSE, socrates_agent.WHO_CLAUDE)}
                   if m.get("role") == "system" and isinstance(m.get("content"), str) else m for m in messages]
        return self.claude.chat(swapped, **kw)

    def note(self) -> dict:
        return {"model": claude_api.MODEL, "label": "Claude (Anthropic)", "why": self.WHY[self.why]}


def _make_claude() -> claude_api.ClaudeAPI:
    return claude_api.ClaudeAPI(checks=[_claude_today_check])


def meta_ready() -> bool:
    return web.api_key_present() and meta_api.spent() + RESERVE_USD <= meta_api.BUDGET_USD
sessions = agent_routes._Counter()
addresses = agent_routes._Counter()


@router.get("/socrates", include_in_schema=False)
def socrates_page():
    return FileResponse(web.HERE / "pages" / "socrates.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/socrates/status")
def socrates_status(request: Request):
    """Whether Socrates is available here, how many turns this browser has left today, and the starters."""
    sid, new = agent_routes._session(request, COOKIE)
    spent = spend.today()
    left = max(0, min(session_cap() - sessions.count(sid), ip_cap() - addresses.count(client_ip(request))))
    mine = own_key.key_of(request.headers) is not None  # a visitor's own key: their budget, not the demo's
    meta_left = mine or (meta_ready() and spend.left())
    claude_left = not mine and claude_api.available() and claude_spend.left()
    body = {"enabled": mine or web.api_key_present() or claude_api.available(), "starters": STARTERS, "turns_left": left,
            "per_session": session_cap(), "max_turns": socrates_agent.MAX_TURNS,
            "history_tokens": socrates_agent.HISTORY_TOKENS, "daily_cap_usd": daily_usd(),
            "spent_today_usd": round(spent, 4), "budget_left": bool(meta_left or claude_left),
            "own_key": mine,
            "backup": {"available": claude_api.available(), "active": bool(not meta_left and claude_left),
                       "model": claude_api.MODEL, "label": "Claude (Anthropic)"},
            "model": socrates_agent.MODEL, "reasoning_effort": socrates_agent.REASONING_EFFORT,
            "max_tool_calls": socrates_agent.MAX_TOOL_CALLS, "tools": socrates_agent.TOOL_NAMES,
            "examine": examine_info()}
    resp = JSONResponse(body)
    if new:
        agent_routes._set_cookie(resp, sid, COOKIE)
    return resp


class ToolUse(BaseModel):
    name: str = Field(..., max_length=40)
    args: dict = Field(default_factory=dict)


class Turn(BaseModel):
    role: Literal["visitor", "socrates"]
    text: str = Field(..., max_length=4000)
    tools: list[ToolUse] = Field(default_factory=list, max_length=socrates_agent.MAX_TOOL_CALLS)


class Dialogue(BaseModel):
    question: str = Field(..., min_length=1, max_length=socrates_agent.MAX_QUESTION_CHARS)
    history: list[Turn] = Field(default_factory=list, max_length=2 * socrates_agent.MAX_TURNS)
    context: dict | None = None
    mode: Literal["ask", "examine"] = "ask"
    concept: str | None = Field(None, max_length=30)

    @field_validator("context")
    @classmethod
    def small_context(cls, v):
        if v is not None and len(json.dumps(v, default=str)) > 2000:
            raise ValueError("context is too large")
        return v


def make_agent(history, context, mode: str = "ask", concept: str | None = None, api=None) -> socrates_agent.SocratesAgent:
    return socrates_agent.SocratesAgent(api or web.get_api(), history=history, context=context, mode=mode,
                                        concept=concept)


def examine_info() -> dict:
    """The examine mode's concepts and opening questions, written in advance (no model call)."""
    return {"concepts": [{"key": k, "label": e["label"], "question": e["question"], "opening": e["opening"],
                          "link": {"href": e["link"], "label": e["page"]}} for k, e in socrates_agent.EXAMINE.items()],
            "min_exchanges": socrates_agent.EXAMINE_MIN, "max_exchanges": socrates_agent.EXAMINE_MAX}


@router.post("/api/socrates")
def socrates(body: Dialogue, request: Request):
    """One turn of the dialogue. The reply is a stream of JSON lines, one per step."""
    question = socrates_agent.clean_question(body.question)
    if not question:
        raise HTTPException(422, "Say something first.")
    turn = socrates_agent.prepare_history(body.history)["turn"]
    concept = None
    if body.mode == "examine":
        concept = socrates_agent.examine_concept(body.concept or "chair")
        if concept is None:
            raise HTTPException(422, "Socrates examines a chair, a clock, a bird or a game.")
        if turn > socrates_agent.EXAMINE_MAX:
            raise HTTPException(422, f"This examination has had its {socrates_agent.EXAMINE_MAX} exchanges. Start "
                                     "another: Socrates never minded beginning again.")
    elif turn > socrates_agent.MAX_TURNS:
        raise HTTPException(422, f"This dialogue has had its {socrates_agent.MAX_TURNS} turns. Start a new one: "
                                 "Socrates never minded beginning again.")
    sid, new = agent_routes._session(request, COOKIE)
    ip = client_ip(request)
    if sessions.count(sid) >= session_cap() or addresses.count(ip) >= ip_cap():
        raise HTTPException(429, f"You've had {session_cap()} turns with Socrates today, the limit for this demo. "
                                 "Every page of the lab still works; come back tomorrow.")
    mine = own_key.api_for(request)  # a visitor's own key: their budget, so none of the demo's caps or backups
    backup = claude_api.available() and mine is None
    if mine is None and not web.api_key_present() and not backup:
        raise HTTPException(503, "Ask Socrates needs the Meta Model API, which isn't set up on this server.")
    held = None if mine is not None else (spend if meta_ready() and spend.reserve() else None)
    if mine is None and held is None:
        if not backup:
            if not meta_ready():
                raise HTTPException(503, web.BUDGET_MSG)
            raise HTTPException(503, "Socrates has used today's budget for dialogues. Every page of the lab still "
                                     "works, and he'll be back tomorrow.")
        if not claude_spend.reserve():
            raise HTTPException(503, "Socrates has used today's budget for dialogues. Every page of the lab still "
                                     "works, and he'll be back tomorrow.")
        held = claude_spend
    api = (MetaThenClaude(mine, None) if mine is not None else
           MetaThenClaude(web.get_api() if held is spend else None, _make_claude if backup else None,
                          why=None if held is spend else "budget"))
    try:
        agent = (make_agent(body.history, body.context, mode="examine", concept=concept, api=api) if concept
                 else make_agent(body.history, body.context, api=api))
    except BaseException:
        if held is not None:
            held.release()
        raise

    def to_claude():  # Claude's turns cost more per token: give it room, and say so in the trace
        agent.max_usd = max(agent.max_usd, CLAUDE_TURN_USD)
        agent.model = claude_api.MODEL
    api.switched = to_claude
    if api.on_claude:
        to_claude()

    def events():
        for e in agent.run(question):
            yield {**e, "backup": api.note()} if api.on_claude and e["type"] in ("start", "answer") else e

    sessions.take(sid)
    addresses.take(ip)
    resp = agent_routes.stream_events(events, held.release if held is not None else (lambda: None), "socrates",
                                      own_key=mine is not None)
    if new:
        agent_routes._set_cookie(resp, sid, COOKIE)
    return resp

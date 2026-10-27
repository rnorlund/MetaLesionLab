"""Ask the Lab (/ask): plain-language questions answered by a Muse Spark agent over the lab's results.

POST /api/ask streams the agent's steps as JSON lines (application/x-ndjson): start, thinking,
tool_call, tool_result, checking, answer and done, or error. The page shows each line as it arrives.
The agent and its tools are in metalesionlab/lab_agent.py; the tools only read results the lab has
already computed, so an answer costs only the Muse Spark calls (a few cents).

Limits for this route only (a site-wide guard may add its own):
- TIPPA_AGENT_SESSION_QUESTIONS (default 10) questions per browser session per day, counted by a
  cookie, and TIPPA_AGENT_IP_QUESTIONS (default 30) per address per day, for clients without cookies.
- TIPPA_AGENT_DAILY_USD (default 1.00): the agent's own spend today (UTC), read from the shared ledger
  entries tagged "ask", plus a reserve for each question in flight.
- MetaAPI's overall budget cap still applies.

The spend tracker, the counters, the session cookie and the streaming wrapper are shared with Ask
Socrates (socrates_routes.py), which keeps its own cookie, counters and ledger tag.

app.py includes this router with one line.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Callable, Iterator

import httpx
import openai
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from metalesionlab import lab_agent, meta_api
from metalesionlab.meta_api import BudgetExceeded
from metalesionlab.web import app as web
from metalesionlab.web.limits import client_ip

log = logging.getLogger("tot.ask")
router = APIRouter()

COOKIE = "tl_ask"
DAY_S = 24 * 3600
RESERVE_USD = 0.06  # held per question in flight; a typical answer costs $0.01-0.04
SUGGESTED = [
    "Which kind of damage makes the model make sound errors like 'Caraloon'?",
    "Does damage hurt Spanish more than English?",
    "Which concept does the AI draw most uniformly?",
    "Can I remove layers from Glimmer?",
    "How does lesioned Glimmer compare with people with aphasia?",
    "What does the word lens show for 'carrot' when the late layers are damaged?",
]


def daily_usd() -> float:
    return float(os.environ.get("TIPPA_AGENT_DAILY_USD", "1"))


def session_cap() -> int:
    return int(os.environ.get("TIPPA_AGENT_SESSION_QUESTIONS", "10"))


def ip_cap() -> int:
    return int(os.environ.get("TIPPA_AGENT_IP_QUESTIONS", "30"))


# --- today's agent spend, read incrementally from the shared ledger ------------------------------

class _Spend:
    """Today's spend for one ledger tag (default: Ask the Lab's), with a reserve held per request in flight
    so that parallel requests can't overshoot the daily cap."""

    def __init__(self, tag: str | None = None, cap: Callable[[], float] | None = None,
                 reserve_usd: float = RESERVE_USD):
        self.tag = tag or lab_agent.LEDGER_TAG
        self.cap = cap or daily_usd
        self.reserve_usd = reserve_usd
        self.lock = threading.Lock()
        self.path = None
        self.offset = 0
        self.day = None
        self.total = 0.0
        self.reserved = 0.0

    @staticmethod
    def _day_start(now: float) -> float:
        return now - now % DAY_S

    def today(self) -> float:
        """USD spent today (UTC) by calls with this tag. Reads only lines added since last time."""
        now = time.time()
        start = self._day_start(now)
        path = meta_api.LEDGER
        with self.lock:
            if path != self.path or start != self.day:
                self.path, self.day, self.offset, self.total = path, start, 0, 0.0
            try:
                size = path.stat().st_size
            except OSError:
                return self.total
            if size < self.offset:  # the ledger was replaced
                self.offset, self.total = 0, 0.0
            with path.open("rb") as f:
                f.seek(self.offset)
                chunk = f.read()
            end = chunk.rfind(b"\n") + 1  # a line still being written waits for next time
            for line in chunk[:end].splitlines():
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("tag") == self.tag and float(e.get("ts", 0)) >= start:
                    self.total += float(e.get("usd", 0))
            self.offset += end
            return self.total

    def left(self) -> bool:
        """Whether one more request fits under today's cap."""
        return self.today() + self.reserve_usd <= self.cap()

    def reserve(self) -> bool:
        spent = self.today()
        with self.lock:
            if spent + self.reserved + self.reserve_usd > self.cap():
                return False
            self.reserved += self.reserve_usd
            return True

    def release(self) -> None:
        with self.lock:
            self.reserved = max(0.0, self.reserved - self.reserve_usd)


spend = _Spend()


class _Counter:
    """Questions per key in the last 24 hours, in memory."""

    def __init__(self):
        self.lock = threading.Lock()
        self.hits: dict[str, deque] = defaultdict(deque)

    def count(self, key: str) -> int:
        now = time.time()
        with self.lock:
            q = self.hits[key]
            while q and q[0] <= now - DAY_S:
                q.popleft()
            return len(q)

    def take(self, key: str) -> None:
        with self.lock:
            self.hits[key].append(time.time())

    def clear(self) -> None:
        with self.lock:
            self.hits.clear()


sessions = _Counter()
addresses = _Counter()


def _session(request: Request, cookie: str = COOKIE) -> tuple[str, bool]:
    sid = request.cookies.get(cookie) or ""
    if 16 <= len(sid) <= 64 and sid.replace("-", "").replace("_", "").isalnum():
        return sid, False
    return secrets.token_urlsafe(18), True


def _set_cookie(resp, sid: str, cookie: str = COOKIE) -> None:
    resp.set_cookie(cookie, sid, max_age=DAY_S, httponly=True, samesite="lax")


def stream_events(events: Callable[[], Iterator[dict]], release: Callable[[], None], name: str = "ask"
                  ) -> StreamingResponse:
    """An agent's events as JSON lines. A failure after the stream has started is reported as an "error"
    line; `release` runs once, when the stream ends or (via a background task) if the client left first."""
    released = threading.Event()

    def release_once():
        if not released.is_set():
            released.set()
            release()

    def stream():
        try:
            for event in events():
                yield json.dumps(event, ensure_ascii=False, default=str) + "\n"
        except BudgetExceeded:
            yield json.dumps({"type": "error", "message": web.BUDGET_MSG}) + "\n"
        except (openai.OpenAIError, httpx.HTTPError) as e:
            log.warning("%s: Meta API error: %s", name, e)
            yield json.dumps({"type": "error", "message": f"The Meta Model API returned an error "
                                                          f"({type(e).__name__}). Please try again in a minute."}) + "\n"
        except Exception as e:  # the stream has started, so report the failure as a line
            log.exception("%s failed", name)
            yield json.dumps({"type": "error", "message": f"Something went wrong ({type(e).__name__})."}) + "\n"
        finally:
            release_once()

    return StreamingResponse(stream(), media_type="application/x-ndjson", background=BackgroundTask(release_once),
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --- routes ------------------------------------------------------------------------------------

@router.get("/ask", include_in_schema=False)
def ask_page():
    return FileResponse(web.HERE / "pages" / "ask.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/ask/status")
def ask_status(request: Request):
    """Whether the agent is available here, how many questions this browser has left today, and the
    suggested questions."""
    sid, new = _session(request)
    spent = spend.today()
    left = max(0, min(session_cap() - sessions.count(sid), ip_cap() - addresses.count(client_ip(request))))
    body = {"enabled": web.api_key_present(), "suggested": SUGGESTED, "questions_left": left,
            "per_session": session_cap(), "daily_cap_usd": daily_usd(), "spent_today_usd": round(spent, 4),
            "budget_left": spent + spend.reserve_usd <= daily_usd(), "model": lab_agent.MODEL,
            "reasoning_effort": lab_agent.REASONING_EFFORT, "max_tool_calls": lab_agent.MAX_TOOL_CALLS,
            "tools": lab_agent.TOOL_NAMES}
    resp = JSONResponse(body)
    if new:
        _set_cookie(resp, sid)
    return resp


class Question(BaseModel):
    question: str = Field(..., min_length=1, max_length=lab_agent.MAX_QUESTION_CHARS)


def make_agent() -> lab_agent.LabAgent:
    return lab_agent.LabAgent(web.get_api())


@router.post("/api/ask")
def ask(body: Question, request: Request):
    """Answer one question. The reply is a stream of JSON lines, one per step."""
    question = lab_agent.clean_question(body.question)
    if not question:
        raise HTTPException(422, "Type a question first.")
    sid, new = _session(request)
    ip = client_ip(request)
    if sessions.count(sid) >= session_cap() or addresses.count(ip) >= ip_cap():
        raise HTTPException(429, f"You've asked {session_cap()} questions today, the limit for this demo. "
                                 "Every page of the lab still works; try Ask the Lab again tomorrow.")
    if not web.api_key_present():
        raise HTTPException(503, "Ask the Lab needs the Meta Model API, which isn't set up on this server.")
    if meta_api.spent() + RESERVE_USD > meta_api.BUDGET_USD:
        raise HTTPException(503, web.BUDGET_MSG)
    agent = make_agent()
    if not spend.reserve():
        raise HTTPException(503, "Ask the Lab has used today's budget for questions. Every page of the lab still "
                                 "works, and the agent will be back tomorrow.")
    sessions.take(sid)
    addresses.take(ip)
    # The background task also releases, in case the client left before the stream started.
    resp = stream_events(lambda: agent.run(question), spend.release, "ask")
    if new:
        _set_cookie(resp, sid)
    return resp

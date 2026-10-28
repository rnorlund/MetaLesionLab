"""Spend guard for a public deployment of the web app (PUBLIC_DEMO=1).

Local mode, the default, is unchanged: install() only adds GET /api/guard, which says the guard is off.

With PUBLIC_DEMO=1, visitors can't run up the Meta API bill:
- Daily cap. All visitors together may spend TIPPA_PUBLIC_DAILY_USD (default $2) per UTC day, summed
  from the spend ledger (meta_api.LEDGER, one line per billable call). MetaAPI checks it before every
  call (meta_api.budget_checks), so a background build or a multi-step agent stops at the cap too,
  and paid routes check it before they start. Once it's reached, paid routes answer 503 with a plain
  message and links to recorded examples; browsing, the replays, typed challenge games and exports
  keep working. The overall cap (MLL_BUDGET_USD) still applies on top.
- Per-visitor limits. A burst limit per minute on every paid route, a daily limit for routes that
  limits.py doesn't count (the Ask the Lab and Ask Socrates agents, unknown routes), tighter daily defaults in limits.py
  (3 builds, 2 scenes, 150 scored answers), and a ceiling on paid requests per minute from everyone together.
- Test Studio builds are tiny: TIPPA_PUBLIC_BUILD_WORDS words (default 4; 0 turns building off) with
  at most TIPPA_PUBLIC_BUILD_CANDIDATES pictures per word (default 2). Personal tests from a photo are
  off (TIPPA_PUBLIC_PHOTO_TESTS=1 turns them on).
- Audio uploads are capped in size (TIPPA_PUBLIC_AUDIO_MB, default 2.5 MB for a naming answer, about a
  minute of 16 kHz WAV; 4 MB for a description or fluency recording) and in length (30 s naming,
  90 s description, 60 s fluency).
- Visitors can edit only the sets and scenes they built (as with TOT_PUBLIC=1).
- Every page loads static/js/guard-banner.js, which says how much of today's budget is left and,
  once it's used up, points to the recorded demos.

Any POST, PUT, PATCH or DELETE under /api/ that isn't on the FREE list below counts as paid, so a new
route is limited and stops at the cap until it's listed here. /api/ask... (Ask the Lab) and
/api/socrates... (Ask Socrates, one bucket per dialogue turn) are paid; their status polls (GET) are free.

The two sites (MLL_SITE, brand.py) serve different routes, so each guard knows only its own site's
routes: on the Plato site that is Ask Socrates and Seven meanings' voice test (paid) and Draw a chair and the
voice test's prosody reading (free), and everything else
under /api/ that mutates falls to the "other" bucket (and then 404s). The Lingua site has the rest.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request as StarletteRequest

from metalesionlab import meta_api
from metalesionlab.brand import LINGUA
from metalesionlab.meta_api import BudgetExceeded
from metalesionlab.web import limits

log = logging.getLogger("tot.guard")

DAY_S = 24 * 3600
MB = 1024 * 1024
DRAIN_BYTES = 16 * MB  # an oversized upload is read and dropped up to this size, so its sender gets the reply
BANNER_TAG = b'<script src="/static/js/guard-banner.js" defer></script>'
# Picture, SAM check and Muse Spark naming per candidate, as in app.COST_PER_CANDIDATE.
COST_PER_CANDIDATE = meta_api.IMAGE_PRICE + meta_api.SAM_PRICE + 0.002
# Shown when today's budget is used up: things that work without new Meta API calls, per site.
EXAMPLES = {
    "lingua": [
        {"label": "Watch the recorded Scorer demo", "href": "/scorer", "tour": "scorer"},
        {"label": "Play You vs. the AI (typed answers are free)", "href": "/challenge"},
        {"label": "Explore the Model Lab results", "href": "/lab"},
    ],
    "plato": [
        {"label": "See the experiments", "href": "/plato"},
        {"label": "Draw a chair (runs on our server, no AI calls)", "href": "/draw"},
        {"label": "Name the shadow", "href": "/plato/cave"},
    ],
}
# What pauses when the budget is used up, and what stays free (the banner and the 503 message say so).
PAUSED = {"lingua": "New scoring and picture generation pause",
          "plato": "Ask Socrates and the voice test in Seven meanings pause"}
STAYS_FREE = {"lingua": "Browsing, replays and exports are free.",
              "plato": "The experiments and Draw a chair are free."}
BUDGET_DETAIL = {
    "lingua": ("Today's live demo budget for AI calls is used up, so new scoring and picture generation "
               "are paused until 00:00 UTC ({wait} from now). Everything else still works: browse the results, "
               "play You vs. the AI with typed answers, or press Demo on any page for a recorded example."),
    "plato": ("Today's live demo budget for AI calls is used up, so Ask Socrates and the voice test in Seven meanings "
              "are paused until 00:00 UTC ({wait} from now). Everything else still works: every experiment replays "
              "recorded results, and Draw a chair runs on our own server."),
}
# Paid requests per visitor per minute, by bucket.
BURST_PER_MIN = {"build": 1, "scene": 1, "photo": 1, "score": 30, "ask": 4, "socrates": 5, "phaedrus": 6, "other": 10}  # a fast /take is ~20 a minute
# Daily limits the guard counts itself; limits.py counts builds, scenes and scored responses.
OTHER_PER_DAY = 100
# Daily limits.py defaults on the public demo (TOT_LIMIT_* in the environment still wins). Scoring is cheap
# (about $0.001-0.003 an answer) and visitors behind one office network share an address, so its limit is
# generous; the daily dollar cap is what bounds spending.
PUBLIC_LIMITS = {"build": 3, "scene": 2, "score": 150}
WHAT = {"build": "picture sets", "scene": "scenes", "photo": "photo tests", "score": "scored answers",
        "ask": "questions", "socrates": "dialogue turns", "phaedrus": "voice tries", "other": "requests"}

# Mutating /api/ routes that never call a Meta API, and the site that serves them. Everything else that
# mutates is treated as paid.
FREE = [
    ({"POST"}, re.compile(r"/api/challenge/score/?"), "lingua"),
    ({"POST"}, re.compile(r"/api/assess/(report\.pdf|forms)/?"), "lingua"),
    ({"POST"}, re.compile(r"/api/assess/norms/[^/]+/?"), "lingua"),
    ({"PATCH"}, re.compile(r"/api/sets/[^/]+/items/\d+/?"), "lingua"),
    ({"PATCH"}, re.compile(r"/api/scenes/[^/]+/?"), "lingua"),
    # Draw a chair: CPU only, no API calls; draw_routes.py has its own limits
    ({"POST"}, re.compile(r"/api/draw(/upload)?/?"), "plato"),
    # Seven meanings' prosody reading: numpy on our server, no API calls; plato_phaedrus_routes.py has its own limits
    ({"POST"}, re.compile(r"/api/phaedrus/listen/?"), "plato"),
]
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
# (methods, path, rule name, site)
PAID = [
    ({"POST"}, re.compile(r"/api/sets/?"), "build", "lingua"),
    ({"POST"}, re.compile(r"/api/scenes/?"), "scene", "lingua"),
    ({"POST"}, re.compile(r"/api/assess/photo-test/?"), "photo", "lingua"),
    ({"POST"}, re.compile(r"/api/score/naming/text/?"), "text", "lingua"),
    ({"POST"}, re.compile(r"/api/(score/naming|assess/naming)/?"), "audio_short", "lingua"),
    ({"POST"}, re.compile(r"/api/score/(description|fluency)/?"), "audio_long", "lingua"),
    ({"POST"}, re.compile(r"/api/assess/rescore/?"), "text", "lingua"),
    (MUTATING, re.compile(r"/api/ask(/.*)?"), "ask", "lingua"),  # GET /api/ask/status is free
    (MUTATING, re.compile(r"/api/socrates(/.*)?"), "socrates", "plato"),  # GET /api/socrates/status is free
    ({"POST"}, re.compile(r"/api/phaedrus/read/?"), "phaedrus", "plato"),  # Voice Transcribe and Muse Spark
]


class DailyCapReached(BudgetExceeded):
    """Today's public-demo budget is used up (a BudgetExceeded, so every existing handler applies)."""


def _env_num(env, name: str, default: float) -> float:
    try:
        return float(env.get(name, default))
    except (TypeError, ValueError):
        log.warning("%s=%r isn't a number; using %s", name, env.get(name), default)
        return default


@dataclass
class Settings:
    public_demo: bool = False
    daily_usd: float = 2.0
    build_words: int = 4
    build_candidates: int = 2
    photo_tests: bool = False
    ask_per_day: int = 20
    socrates_per_day: int = 30  # dialogue turns; a dialogue has up to 8
    phaedrus_per_day: int = 30  # Seven meanings' voice tries, about $0.003 each
    global_per_min: int = 60
    audio_mb: float = 2.5  # one naming answer
    long_audio_mb: float = 4.0  # a description or fluency recording
    clip_s: dict = field(default_factory=lambda: {"naming": 30, "description": 90, "fluency": 60})

    @classmethod
    def from_env(cls, env=os.environ) -> "Settings":
        return cls(
            public_demo=env.get("PUBLIC_DEMO", "0").strip().lower() in ("1", "true", "yes"),
            daily_usd=_env_num(env, "TIPPA_PUBLIC_DAILY_USD", 2.0),
            build_words=int(_env_num(env, "TIPPA_PUBLIC_BUILD_WORDS", 4)),
            build_candidates=max(1, min(3, int(_env_num(env, "TIPPA_PUBLIC_BUILD_CANDIDATES", 2)))),
            photo_tests=env.get("TIPPA_PUBLIC_PHOTO_TESTS", "0") == "1",
            ask_per_day=int(_env_num(env, "TIPPA_PUBLIC_ASK_PER_DAY", 20)),
            socrates_per_day=int(_env_num(env, "TIPPA_PUBLIC_SOCRATES_PER_DAY", 30)),
            phaedrus_per_day=int(_env_num(env, "TIPPA_PUBLIC_PHAEDRUS_PER_DAY", 30)),
            global_per_min=int(_env_num(env, "TIPPA_PUBLIC_GLOBAL_PER_MIN", 60)),
            audio_mb=_env_num(env, "TIPPA_PUBLIC_AUDIO_MB", 2.5),
        )


@dataclass(frozen=True)
class Rule:
    bucket: str
    max_bytes: int
    estimate_usd: float  # before the call; builds compute theirs from the request


def make_rules(s: Settings) -> dict[str, Rule]:
    return {
        "build": Rule("build", 64 * 1024, 0.0),
        "scene": Rule("scene", 16 * 1024, 0.03),
        "photo": Rule("photo", 13 * MB, 0.30),
        "audio_short": Rule("score", int(s.audio_mb * MB), 0.01),
        "audio_long": Rule("score", int(s.long_audio_mb * MB), 0.02),
        "text": Rule("score", 32 * 1024, 0.005),
        "ask": Rule("ask", 64 * 1024, 0.05),
        "socrates": Rule("socrates", 96 * 1024, 0.05),  # the dialogue so far rides along with each turn
        "phaedrus": Rule("phaedrus", 512 * 1024, 0.01),  # a 16 kHz WAV of at most 12 s; a try costs about $0.003
        "other": Rule("other", 256 * 1024, 0.01),
    }


class DailyLedger:
    """Spending per UTC day from the JSONL ledger, read incrementally: each call parses only the
    lines added since the last one (a partly written last line waits for its newline)."""

    def __init__(self, path_fn: Callable[[], Path]):
        self.path_fn = path_fn
        self.lock = threading.Lock()
        self._reset(None)

    def _reset(self, key) -> None:
        self.key, self.pos, self.by_day = key, 0, defaultdict(float)

    def spent_on(self, day: int) -> float:
        with self.lock:
            self._refresh()
            return self.by_day.get(day, 0.0)

    def _refresh(self) -> None:
        path = Path(self.path_fn())
        try:
            st = path.stat()
        except OSError:
            self._reset(None)
            return
        key = (str(path), st.st_ino, st.st_dev)
        if key != self.key or st.st_size < self.pos:  # a different or truncated file: start over
            self._reset(key)
        if st.st_size == self.pos:
            return
        with path.open("rb") as f:
            f.seek(self.pos)
            chunk = f.read(st.st_size - self.pos)
        end = chunk.rfind(b"\n") + 1
        for line in chunk[:end].splitlines():
            try:
                entry = json.loads(line)
                self.by_day[int(float(entry["ts"]) // DAY_S)] += float(entry["usd"])
            except (ValueError, KeyError, TypeError):
                continue
        self.pos += end


class Windows:
    """Sliding-window counters keyed by (bucket, visitor, window)."""

    def __init__(self):
        self.hits: dict[tuple, deque] = defaultdict(deque)
        self._swept = 0.0

    def _queue(self, key: tuple, now: float) -> deque:
        q = self.hits[key]
        while q and q[0] <= now - key[-1]:
            q.popleft()
        return q

    def retry_after(self, key: tuple, limit: int, now: float) -> int:
        """0 if one more hit fits in the window, else seconds until it would."""
        q = self._queue(key, now)
        if len(q) < limit:
            return 0
        return int(q[0] + key[-1] - now) + 1 if q else int(key[-1])

    def record(self, key: tuple, now: float) -> None:
        self._queue(key, now).append(now)
        if now - self._swept > 600:  # drop visitors with nothing in their window
            self._swept = now
            for k in [k for k, q in self.hits.items() if not self._queue(k, now)]:
                del self.hits[k]


@dataclass
class Decision:
    status: int | None = None  # None: let the request through
    payload: dict | None = None
    headers: dict = field(default_factory=dict)
    body: bytes | None = None  # a rewritten request body


def _hours(seconds: float) -> str:
    h = seconds / 3600
    return "less than an hour" if h < 1 else f"about {round(h)} h"


class Guard:
    def __init__(self, settings: Settings, ledger_path: Callable[[], Path] | None = None,
                 clock: Callable[[], float] = time.time, client_ip: Callable = limits.client_ip,
                 site: str | None = None):
        self.s = settings
        self.clock = clock
        self.ledger = DailyLedger(ledger_path or (lambda: meta_api.LEDGER))
        self.windows = Windows()
        self.lock = threading.Lock()
        self.rules = make_rules(settings)
        self.client_ip = client_ip
        # The routes of one site (install() passes the app's), or of both when no site is given.
        self.site = site
        self.text_site = site or "lingua"  # whose messages and examples to show
        self.paid = [(m, p, name) for m, p, name, where in PAID if site in (None, where)]
        self.free = [(m, p) for m, p, where in FREE if site in (None, where)]

    # --- today's budget ---------------------------------------------------------------------

    def spent_today(self) -> float:
        return self.ledger.spent_on(int(self.clock() // DAY_S))

    def resets_in_s(self) -> int:
        return int(DAY_S - self.clock() % DAY_S) + 1

    def ledger_writable(self) -> bool:
        """MetaAPI records a call after paying for it; if the ledger can't be written, the call would
        go uncounted, so the guard refuses every call instead (fails closed)."""
        path = Path(self.ledger.path_fn())
        if path.exists():
            return os.access(path, os.W_OK)
        folder = path.parent
        while not folder.exists() and folder != folder.parent:  # MetaAPI creates missing folders
            folder = folder.parent
        return os.access(folder, os.W_OK | os.X_OK)

    def would_exceed(self, estimate: float = 0.0) -> bool:
        if not self.ledger_writable():
            if not getattr(self, "_warned_ledger", False):
                self._warned_ledger = True
                log.error("The spend ledger %s isn't writable, so every Meta API call is refused.",
                          self.ledger.path_fn())
            return True
        spent = self.spent_today()
        return spent >= self.s.daily_usd or spent + max(0.0, estimate) > self.s.daily_usd

    def check_call(self, estimate: float = 0.0) -> None:
        """Registered in meta_api.budget_checks: runs before every Meta API call."""
        if self.would_exceed(estimate):
            raise DailyCapReached(f"today's public demo budget (${self.s.daily_usd:.2f}) is used up")

    def budget_payload(self) -> dict:
        wait = self.resets_in_s()
        return {"detail": BUDGET_DETAIL[self.text_site].format(wait=_hours(wait)),
                "guard": "budget", "resets_in_s": wait, "examples": EXAMPLES[self.text_site],
                "paused": PAUSED[self.text_site]}

    def budget_response(self, *_args) -> JSONResponse:
        payload = self.budget_payload()
        return JSONResponse(payload, status_code=503,
                            headers={"X-Tippa-Guard": "budget", "Retry-After": str(payload["resets_in_s"])})

    # --- routes -----------------------------------------------------------------------------

    def match(self, method: str, path: str) -> Rule | None:
        if not path.startswith("/api/") or method in ("HEAD", "OPTIONS"):
            return None
        for methods, pattern, name in self.paid:
            if method in methods and pattern.fullmatch(path):
                return self.rules[name]
        if method not in MUTATING or any(method in m and p.fullmatch(path) for m, p in self.free):
            return None
        return self.rules["other"]

    def gate(self, rule: Rule) -> Decision | None:
        """Features that are off on the public demo; decided before the body is read."""
        if rule.bucket == "photo" and not self.s.photo_tests:
            return Decision(403, {"detail": "Personal tests from a photo are turned off on the live demo: they draw "
                                            "many pictures, and photos of people's homes shouldn't go through a public "
                                            f"server. Run {LINGUA.name} yourself to make one.", "guard": "off"},
                            {"X-Tippa-Guard": "off"})
        if rule.bucket == "build" and self.s.build_words <= 0:
            return Decision(403, {"detail": "Building new picture sets is turned off on the live demo. Open one of the "
                                            f"demo sets below, or run {LINGUA.name} yourself to build your own.",
                                  "guard": "off"}, {"X-Tippa-Guard": "off"})
        return None

    def too_large(self, rule: Rule) -> Decision:
        what = "recording" if rule.bucket == "score" else "upload"
        return Decision(413, {"detail": f"That {what} is too large for the live demo ({rule.max_bytes / MB:.3g} MB at "
                                        "most).", "guard": "size"}, {"X-Tippa-Guard": "size"})

    def _build(self, body: bytes) -> tuple[Decision | None, float, bytes | None, str | None]:
        """Tiny builds: check the word count, lower the candidates. (decision, estimate, new body, note)."""
        try:
            data = json.loads(body or b"{}")
            words = {line.partition(":")[0].strip().lower() for line in str(data.get("words", "")).splitlines()}
            words.discard("")
            cands = int(data.get("candidates", 2))
        except (ValueError, TypeError, AttributeError):
            return None, 0.25, None, None  # the route will reject it; meanwhile assume a large build
        if len(words) > self.s.build_words:
            return (Decision(422, {"detail": f"On the live demo a set has up to {self.s.build_words} words "
                                             f"({len(words)} given). Run {LINGUA.name} yourself for longer sets.",
                                   "guard": "size"}, {"X-Tippa-Guard": "size"}), 0.0, None, None)
        new_body = note = None
        if cands > self.s.build_candidates:
            data["candidates"] = cands = self.s.build_candidates
            new_body = json.dumps(data).encode()
            note = (f"On the live demo each word gets up to {cands} picture{'s' if cands > 1 else ''}.")
        return None, len(words) * max(1, cands) * COST_PER_CANDIDATE + 0.01, new_body, note

    def admit(self, rule: Rule, ip: str, body: bytes = b"") -> Decision:
        estimate, new_body, note = rule.estimate_usd, None, None
        if rule.bucket == "build":
            rejected, estimate, new_body, note = self._build(body)
            if rejected:
                return rejected
        if self.would_exceed(estimate):
            payload = self.budget_payload()
            return Decision(503, payload, {"X-Tippa-Guard": "budget", "Retry-After": str(payload["resets_in_s"])})
        now = self.clock()
        checks = [(("*", "*", 60), self.s.global_per_min, "busy"),
                  ((rule.bucket, ip, 60), BURST_PER_MIN.get(rule.bucket, 10), "burst")]
        per_day = {"ask": self.s.ask_per_day, "socrates": self.s.socrates_per_day, "phaedrus": self.s.phaedrus_per_day,
                   "other": OTHER_PER_DAY}
        if rule.bucket in per_day:
            checks.append(((rule.bucket, ip, DAY_S), per_day[rule.bucket], "day"))
        with self.lock:
            for key, limit, kind in checks:
                wait = self.windows.retry_after(key, limit, now)
                if wait:
                    return self._limited(kind, limit, rule.bucket, wait)
            for key, _, _ in checks:
                self.windows.record(key, now)
        headers = {"X-Tippa-Guard-Note": note} if note else {}
        return Decision(None, None, headers, new_body)

    @staticmethod
    def _limited(kind: str, limit: int, bucket: str, wait: int) -> Decision:
        if kind == "busy":
            detail, status = "The live demo is busy right now. Please try again in a minute.", 503
        elif kind == "burst":
            detail, status = (f"Please slow down a little: the live demo allows {limit} {WHAT[bucket]} a minute per "
                              f"visitor. Try again in {wait} s."), 429
        else:
            detail, status = (f"Daily limit reached: {limit} {WHAT[bucket]} per visitor per day on the live demo. "
                              f"Try again in {_hours(wait)}."), 429
        return Decision(status, {"detail": detail, "guard": "rate"}, {"X-Tippa-Guard": "rate", "Retry-After": str(wait)})

    # --- status -----------------------------------------------------------------------------

    def status(self, request: Request, debug: bool = False) -> dict:
        spent = self.spent_today()
        out = {"public_demo": True, "daily_cap_usd": self.s.daily_usd, "spent_today_usd": round(spent, 4),
               "left_today_usd": round(max(0.0, self.s.daily_usd - spent), 4), "exhausted": self.would_exceed(),
               "ledger_ok": self.ledger_writable(),
               "resets_in_s": self.resets_in_s(), "examples": EXAMPLES[self.text_site],
               "paused": PAUSED[self.text_site], "free_note": STAYS_FREE[self.text_site],
               "per_minute": {b: n for b, n in BURST_PER_MIN.items()
                              if b == "other" or any(self.rules[name].bucket == b for _, _, name in self.paid)}}
        if self.site in (None, "lingua"):
            out.update({"studio": {"build_words": self.s.build_words, "build_candidates": self.s.build_candidates,
                                   "photo_tests": self.s.photo_tests},
                        "audio": {"max_mb": {"naming": self.s.audio_mb, "description": self.s.long_audio_mb,
                                             "fluency": self.s.long_audio_mb}, "max_s": dict(self.s.clip_s)},
                        "ask_per_day": self.s.ask_per_day})
        if self.site in (None, "plato"):
            out["socrates_per_day"] = self.s.socrates_per_day
            out["phaedrus_per_day"] = self.s.phaedrus_per_day
        if debug:  # to check the proxy settings after deploying: the address the limits count by
            out["you"] = {"ip_seen": self.client_ip(request), "x_forwarded_for": request.headers.get("x-forwarded-for")}
        return out


# --- ASGI middleware -----------------------------------------------------------------------------

async def _read_body(receive, max_bytes: int) -> tuple[bytes, bool]:
    """The request body, or (b"", True) once it passes max_bytes (the rest is drained, not kept)."""
    chunks, size, more = [], 0, True
    while more:
        message = await receive()
        if message["type"] != "http.request":
            break
        chunk = message.get("body", b"")
        size += len(chunk)
        more = bool(message.get("more_body"))
        if size > max_bytes:
            await _drain(receive, more, size)
            return b"", True
        chunks.append(chunk)
    return b"".join(chunks), False


async def _drain(receive, more: bool = True, size: int = 0) -> None:
    """Read and drop the rest of an upload (up to DRAIN_BYTES) before answering: a server that
    answers mid-upload resets the connection, and the browser shows a network error instead."""
    while more and size <= DRAIN_BYTES:
        message = await receive()
        if message["type"] != "http.request":
            return
        size += len(message.get("body", b""))
        more = bool(message.get("more_body"))


def _replay(body: bytes, receive):
    sent = False

    async def replay():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()
    return replay


async def _respond(send, d: Decision) -> None:
    raw = json.dumps(d.payload).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(raw)).encode())]
    headers += [(k.lower().encode(), str(v).encode("latin-1", "replace")) for k, v in d.headers.items()]
    await send({"type": "http.response.start", "status": d.status, "headers": headers})
    await send({"type": "http.response.body", "body": raw, "more_body": False})


def _with_headers(send, extra: dict):
    if not extra:
        return send

    async def wrapped(message):
        if message["type"] == "http.response.start":
            headers = MutableHeaders(raw=list(message["headers"]))
            for k, v in extra.items():
                headers[k] = v
            message = {**message, "headers": headers.raw}
        await send(message)
    return wrapped


def _with_banner(send):
    """Add the banner script to an HTML page, before </body>."""
    state: dict = {"start": None, "chunks": []}

    async def wrapped(message):
        if message["type"] == "http.response.start":
            ctype = Headers(raw=message["headers"]).get("content-type", "")
            if message.get("status") == 200 and ctype.startswith("text/html"):
                state["start"] = message
                return
        elif message["type"] == "http.response.body" and state["start"] is not None:
            state["chunks"].append(message.get("body", b""))
            if message.get("more_body"):
                return
            body = b"".join(state["chunks"])
            at = body.rfind(b"</body>")
            body = body[:at] + BANNER_TAG + body[at:] if at >= 0 else body + BANNER_TAG
            headers = MutableHeaders(raw=list(state["start"]["headers"]))
            headers["content-length"] = str(len(body))
            await send({**state["start"], "headers": headers.raw})
            await send({"type": "http.response.body", "body": body, "more_body": False})
            return
        await send(message)
    return wrapped


class GuardMiddleware:
    def __init__(self, app, guard: Guard):
        self.app, self.guard = app, guard

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        method, path = scope["method"], scope["path"]
        rule = self.guard.match(method, path)
        if rule is None:
            if method == "GET" and not path.startswith(("/api/", "/static/", "/media/")):
                send = _with_banner(send)
            return await self.app(scope, receive, send)
        declared = Headers(scope=scope).get("content-length", "")
        size = int(declared) if declared.isdigit() else None
        if (d := self.guard.gate(rule)) is not None:
            if size is None or size <= DRAIN_BYTES:
                await _drain(receive)
            return await _respond(send, d)
        if size is not None and size > rule.max_bytes:
            if size <= DRAIN_BYTES:
                await _drain(receive)
            return await _respond(send, self.guard.too_large(rule))
        body, too_big = await _read_body(receive, rule.max_bytes)
        if too_big:
            return await _respond(send, self.guard.too_large(rule))
        d = self.guard.admit(rule, self.guard.client_ip(StarletteRequest(scope)), body)
        if d.status is not None:
            return await _respond(send, d)
        if d.body is not None:
            body = d.body
            scope = {**scope, "headers": [(k, v) for k, v in scope["headers"] if k != b"content-length"]
                     + [(b"content-length", str(len(body)).encode())]}
        await self.app(scope, _replay(body, receive), _with_headers(send, d.headers))


# --- wiring --------------------------------------------------------------------------------------

def configure_web(web, s: Settings) -> None:
    """Public-demo settings in the main app module: visitors edit only what they built, tiny builds,
    shorter recordings, and tighter daily limits in limits.py (an explicit TOT_LIMIT_* still wins)."""
    web.PUBLIC = True
    if s.build_words <= 0:
        web.ALLOW_BUILDS = False
    else:
        web.MAX_WORDS = min(web.MAX_WORDS, s.build_words)
    for task, seconds in s.clip_s.items():
        web.MAX_CLIP_S[task] = min(web.MAX_CLIP_S.get(task, seconds), seconds)
    for bucket, n in PUBLIC_LIMITS.items():
        os.environ.setdefault(f"TOT_LIMIT_{bucket.upper()}", str(n))


def install(app: FastAPI, settings: Settings | None = None, web=None) -> Guard | None:
    """Called once per site by app.py (the app's site is app.state.site). Local mode: only GET /api/guard
    ({"public_demo": false})."""
    s = settings or Settings.from_env()
    if not s.public_demo:
        app.add_api_route("/api/guard", lambda: {"public_demo": False}, methods=["GET"], include_in_schema=False)
        return None
    site = getattr(app.state, "site", None)
    guard = Guard(s, site=site)
    web = web or sys.modules.get("metalesionlab.web.app")
    if web is not None and site in (None, "lingua"):  # builds, recordings and their limits are the Lingua site's
        configure_web(web, s)
    meta_api.budget_checks.append(guard.check_call)
    app.add_middleware(GuardMiddleware, guard=guard)
    app.add_exception_handler(DailyCapReached, guard.budget_response)

    def guard_status(request: Request, debug: bool = False):
        return guard.status(request, debug)
    app.add_api_route("/api/guard", guard_status, methods=["GET"], include_in_schema=False)
    log.warning("PUBLIC_DEMO=1 (%s site): Meta API spending capped at $%.2f per UTC day; paid routes: %s",
                site or "every", s.daily_usd, ", ".join(sorted({guard.rules[n].bucket for _, _, n in guard.paid})))
    return guard

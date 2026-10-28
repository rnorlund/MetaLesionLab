"""Seven meanings (/plato/phaedrus): "I never said she stole my money", spoken seven ways, and what writing keeps.

The page replays a finished experiment (docs/plato_phaedrus.md): web/data/plato_phaedrus.json (written by
scripts/plato_phaedrus_analyze.py) and the Kokoro clips in public_data/plato_phaedrus_audio/ (Kokoro-82M's
voice, Apache-2.0, with stress added by the WORLD vocoder). Listening and the results cost nothing.

"Try it yourself" takes the visitor's own reading. The browser records it, resamples it to a 16 kHz mono WAV and
sends it twice:
- POST /api/phaedrus/listen: the prosody reader (plato_phaedrus.read_stress, numpy on our server, no API call).
  Free, like Draw a chair; limited per visitor (limits.py "phaedrus_listen" a day, "phaedrus_burst" a minute).
- POST /api/phaedrus/read: Meta's Voice Transcribe writes it down and, if it is the sentence, Muse Spark guesses
  the meaning from the transcript alone, with the experiment's prompt. Paid (about $0.003 a try): the site's spend
  guard counts it (guard.py, bucket "phaedrus"), with limits.py's "phaedrus" a day and the overall budget.

Both take only a WAV (16 kHz, mono, 16-bit, 0.8 to 12 s) as the request body, so the recording is read in memory
and never written to disk. Nothing is stored or logged; the visitor's answer to "which word did you stress?" stays
in the browser. app.py includes this router with one line.
"""
from __future__ import annotations

import json
import logging
import random
import threading

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from metalesionlab import audio, meta_api
from metalesionlab import plato_phaedrus as P
from metalesionlab.meta_api import BudgetExceeded
from metalesionlab.web import app as web
from metalesionlab.web.limits import DailyLimiter, client_ip, limit_for, limiter
from metalesionlab.web.plato_atlas_routes import _load

log = logging.getLogger("tot.phaedrus")
router = APIRouter()

DATA = web.HERE / "data" / "plato_phaedrus.json"
TEMPLATES = web.HERE / "data" / "phaedrus_templates.json"
AUDIO = meta_api.REPO_ROOT / "public_data" / "plato_phaedrus_audio"
VOICES = ("af_heart", "am_michael", "bf_emma", "bm_george")
CLIPS = ("neutral",) + tuple(f"{i}_{w.lower()}" for i, w in enumerate(P.WORDS))
MAX_BYTES = 512 * 1024      # 12 s of 16 kHz 16-bit mono is 384 KB
MIN_S, MAX_S = 0.8, 12.0
PAD_S = 0.5                 # silence before and after, as in the experiment
RESERVE_USD = 0.01          # held against the overall budget before a try; a try costs about $0.003
COST_PER_TRY = 0.003
PRIVACY = ("Your recording is processed in memory and never stored or logged. To write it down and ask Muse Spark, "
           "it is sent to Meta’s API.")
burst = DailyLimiter(window_s=60)
_templates: list[P.Template] | None = None
_tpl_lock = threading.Lock()


def usable(d) -> bool:
    return (isinstance(d, dict) and isinstance(d.get("voices"), list) and bool(d["voices"])
            and isinstance(d.get("spark"), dict) and isinstance(d.get("reader"), dict))


def templates() -> list[P.Template]:
    global _templates
    with _tpl_lock:
        if _templates is None:
            try:
                raw = json.loads(TEMPLATES.read_text())
                _templates = [P.Template.from_json(t) for t in raw["templates"]]
            except (OSError, ValueError, KeyError) as e:
                raise HTTPException(503, "The prosody reader's templates aren't on this server.") from e
        return _templates


@router.get("/plato/phaedrus", include_in_schema=False)
def phaedrus_page():
    return FileResponse(web.HERE / "pages" / "plato_phaedrus.html", headers={"Cache-Control": "no-cache"})


@router.get("/api/plato/phaedrus")
def phaedrus_data():
    """The experiment for the page: the sentence and its seven meanings; per shipped voice, each clip's transcript,
    Spark's guess and the prosody reader's guess with its pitch and loudness contour; the accuracies with exact 95%
    CIs and the confusion tables."""
    d = _load(DATA)
    if not usable(d):
        raise HTTPException(503, "The Seven meanings results aren't on this server yet.")
    return d


@router.get("/api/plato/phaedrus/audio/{voice}/{name}", include_in_schema=False)
def phaedrus_audio(voice: str, name: str):
    stem = name.removesuffix(".mp3")
    if voice not in VOICES or stem not in CLIPS or not name.endswith(".mp3"):
        raise HTTPException(404, "No such clip.")
    path = AUDIO / voice / f"{stem}.mp3"
    if not path.is_file():
        raise HTTPException(404, "No such clip.")
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/api/phaedrus/status")
def phaedrus_status(request: Request):
    ip = client_ip(request)
    return {"enabled": web.api_key_present(), "privacy": PRIVACY, "max_seconds": MAX_S, "min_seconds": MIN_S,
            "cost_per_try_usd": COST_PER_TRY, "sentence": P.SENTENCE,
            "limits": {"tries_per_day": limit_for("phaedrus"), "tries_left_today": limiter.remaining("phaedrus", ip),
                       "per_minute": limit_for("phaedrus_burst")}}


async def read_wav(request: Request) -> bytes:
    """The request body, which must be a 16 kHz mono 16-bit WAV of MIN_S to MAX_S seconds; read into memory only."""
    size = int(request.headers.get("content-length") or 0)
    if size > MAX_BYTES:
        raise HTTPException(413, f"That recording is too long: say the sentence in under {MAX_S:.0f} seconds.")
    chunks, total = [], 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_BYTES:
            raise HTTPException(413, f"That recording is too long: say the sentence in under {MAX_S:.0f} seconds.")
        chunks.append(chunk)
    wav = b"".join(chunks)
    if not audio._is_transcribe_ready(wav):
        raise HTTPException(415, "Send the recording as a 16 kHz mono 16-bit WAV (the page does this for you).")
    seconds = audio.duration_s(wav)
    if seconds < MIN_S:
        raise HTTPException(422, "That was too short. Say the whole sentence: “I never said she stole my money.”")
    if seconds > MAX_S:
        raise HTTPException(413, f"That recording is too long: say the sentence in under {MAX_S:.0f} seconds.")
    return wav


def take(bucket: str, ip: str) -> None:
    try:
        burst.take("phaedrus_burst", ip)
    except HTTPException as e:
        raise HTTPException(429, "That's a lot of recordings in a minute. Take a breath and try again shortly.",
                            headers=e.headers) from None
    limiter.take(bucket, ip)


def not_silent(x: np.ndarray) -> None:
    if float(np.sqrt(np.mean(x ** 2))) < 1e-4:
        raise HTTPException(422, "That recording is silent. Check that the page can hear your microphone.")


def listen(wav: bytes) -> dict:
    x, sr = audio.samples(wav)
    not_silent(x)
    try:
        r = P.read_stress(x, templates(), sr)
    except ValueError:
        raise HTTPException(422, "That was too short to be the sentence. Say the whole of it.") from None
    c = P.contour(r)
    return {"reader": {"guess": c["guess"], "word": P.WORDS[c["guess"]]}, "contour": c}


@router.post("/api/phaedrus/listen")
async def phaedrus_listen(request: Request):
    """The prosody reader on the visitor's recording (a 16 kHz mono WAV as the body): per word, pitch, loudness and
    duration, their prominence, and the most prominent word. No API call."""
    take("phaedrus_listen", client_ip(request))
    wav = await read_wav(request)
    return await run_in_threadpool(listen, wav)


def spark_guess(api: meta_api.MetaAPI, transcript: str) -> dict:
    order = P.option_order(random.Random())
    resp = api.chat([{"role": "user", "content": P.build_prompt(transcript, order)}], reasoning_effort="minimal",
                    ledger_tag="phaedrus")
    answer = (resp.choices[0].message.content or "").strip()
    k = P.parse_choice(answer, order)
    return {"guess": k, "word": P.WORDS[k] if k is not None else None,
            "gloss": P.MEANINGS[k].gloss if k is not None else None, "answer": answer[:40]}


def read(wav: bytes) -> dict:
    not_silent(audio.samples(wav)[0])  # nothing to pay for
    api = web.get_api()
    body = api.transcribe(audio.pad_silence(wav, PAD_S), language="en")
    transcript = str(body.get("transcript") or "").strip()
    out = {"transcript": transcript, "is_sentence": P.is_the_sentence(transcript), "spark": None,
           "capitalised": P.leaks([transcript])["capitalised_words"]}
    if out["is_sentence"]:
        out["spark"] = spark_guess(api, transcript)
    else:
        out["note"] = ("That doesn't look like “I never said she stole my money”, so we didn't ask Muse Spark. "
                       "Try the sentence, stressing any one word.")
    return out


@router.post("/api/phaedrus/read")
async def phaedrus_read(request: Request):
    """Voice Transcribe writes the visitor's recording down (a 16 kHz mono WAV as the body); if it is the sentence,
    Muse Spark guesses the meaning from the transcript alone. Paid: about $0.003."""
    if not web.api_key_present():
        raise HTTPException(503, "The voice test needs the Meta Model API, which isn't set up on this server. "
                                 "The prosody reader and everything above still work.")
    take("phaedrus", client_ip(request))
    wav = await read_wav(request)
    if meta_api.spent() + RESERVE_USD > meta_api.BUDGET_USD:
        raise HTTPException(503, "This demo has reached its spending cap for Meta API calls, so the transcript and "
                                 "Muse Spark's guess are paused. The prosody reader and the seven recordings still work.")
    try:
        return await run_in_threadpool(read, wav)
    except BudgetExceeded:
        raise HTTPException(503, "Today's budget for AI calls is used up, so the transcript and Muse Spark's guess "
                                 "are paused until 00:00 UTC. The prosody reader and the seven recordings still work.",
                            headers={"X-Tippa-Guard": "budget"}) from None

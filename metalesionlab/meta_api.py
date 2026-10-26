"""Meta Model API client with a spend ledger and a hard budget cap.

Every billable call is appended to the ledger (runs/costs.jsonl by default), and
new calls are refused once the ledger total reaches MLL_BUDGET_USD (default $120).
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
from openai import OpenAI

BASE_URL = "https://api.meta.ai/v1"
KEY_FILE = Path.home() / ".config" / "meta-model-api" / "env"
REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path(os.environ.get("MLL_LEDGER", REPO_ROOT / "runs" / "costs.jsonl"))
BUDGET_USD = float(os.environ.get("MLL_BUDGET_USD", "120"))

CHAT_MODEL = "muse-spark-1.3"
IMAGE_MODEL = "muse-image-1.0"
SAM_MODEL = "sam-3.1"
ASR_MODEL = "muse-voice-transcribe-1.0"

# USD, from https://dev.meta.ai/docs/pricing-rate-limits (checked 2026-10-26).
# Token prices are per million tokens: (input, cached input, output).
# Only standard-mode models are listed, so a "-contributor" model fails loudly.
TOKEN_PRICES = {
    "muse-spark-1.3": (1.25, 0.15, 4.25),
    "muse-spark-1.2": (1.25, 0.15, 4.25),
    "muse-wonder-1.0": (4.00, 0.20, 20.00),
}
IMAGE_PRICE = 0.01
SAM_PRICE = 2.50 / 1000
ASR_PRICE_PER_HOUR = 0.18


class BudgetExceeded(RuntimeError):
    pass


def load_api_key() -> str:
    if key := os.environ.get("MODEL_API_KEY"):
        return key
    if KEY_FILE.exists() and (m := re.search(r"MODEL_API_KEY=(\S+)", KEY_FILE.read_text())):
        return m.group(1)
    raise RuntimeError(f"Set MODEL_API_KEY or put 'export MODEL_API_KEY=...' in {KEY_FILE}")


def spent() -> float:
    if not LEDGER.exists():
        return 0.0
    with LEDGER.open() as f:
        return sum(json.loads(line)["usd"] for line in f if line.strip())


def _check_budget(estimate: float = 0.0) -> None:
    total = spent()
    if total + estimate > BUDGET_USD:
        raise BudgetExceeded(f"spent ${total:.2f} of the ${BUDGET_USD:.2f} cap")


def _record(kind: str, model: str, usd: float, **extra) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": round(time.time(), 3), "kind": kind, "model": model, "usd": round(usd, 6), **extra}
    with LEDGER.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def token_cost(model: str, usage) -> float:
    """Cost of a call from its usage block (chat-completions or responses shape)."""
    p_in, p_cached, p_out = TOKEN_PRICES[model]
    u = usage.model_dump() if hasattr(usage, "model_dump") else dict(usage)
    n_in = u.get("prompt_tokens", u.get("input_tokens")) or 0
    n_out = u.get("completion_tokens", u.get("output_tokens")) or 0
    details = u.get("prompt_tokens_details") or u.get("input_tokens_details") or {}
    n_cached = details.get("cached_tokens") or 0
    return ((n_in - n_cached) * p_in + n_cached * p_cached + n_out * p_out) / 1e6


@dataclass
class SamMatch:
    obj_id: int
    box: tuple[float, float, float, float]  # x1, y1, x2, y2 in source pixels
    image_size: tuple[int, int]  # w, h
    confidence: float | None

    @property
    def area_fraction(self) -> float:
        x1, y1, x2, y2 = self.box
        w, h = self.image_size
        return max(0.0, x2 - x1) * max(0.0, y2 - y1) / (w * h)


_SAM_BOX = re.compile(r"(\d+)\s*<\|box;([^|]*)\|>")


def parse_sam_output(text: str) -> list[SamMatch]:
    """Boxes from SAM 3.1 output text. A still image is a single frame."""
    matches = []
    for obj_id, fields in _SAM_BOX.findall(text):
        kv = dict(item.split("=", 1) for item in fields.split(";") if "=" in item)
        matches.append(SamMatch(
            obj_id=int(obj_id),
            box=tuple(float(kv[k]) for k in ("x1", "y1", "x2", "y2")),
            image_size=(int(float(kv["w"])), int(float(kv["h"]))),
            confidence=float(kv["c"]) if "c" in kv else None,
        ))
    return matches


def image_data_url(image: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(image).decode()}"


class MetaAPI:
    def __init__(self, api_key: str | None = None):
        key = api_key or load_api_key()
        self.client = OpenAI(base_url=BASE_URL, api_key=key, max_retries=3)
        self.http = httpx.Client(base_url=BASE_URL, headers={"Authorization": f"Bearer {key}"}, timeout=120)

    def chat(self, messages: list[dict], model: str = CHAT_MODEL, reasoning_effort: str = "minimal", **kwargs):
        """reasoning_effort is minimal, low, medium, high, xhigh or max. Reasoning tokens bill as output:
        "minimal" used ~100 of them for a one-word answer, the default ~250."""
        _check_budget()
        resp = self.client.chat.completions.create(model=model, messages=messages,
                                                   reasoning_effort=reasoning_effort, **kwargs)
        _record("chat", model, token_cost(model, resp.usage), usage=resp.usage.model_dump())
        return resp

    def generate_images(self, prompt: str, n: int = 1, size: str | None = None,
                        output_format: str = "png") -> list[bytes]:
        _check_budget(n * IMAGE_PRICE)
        extra = {"size": size} if size else {}
        resp = self.client.images.generate(model=IMAGE_MODEL, prompt=prompt, n=n,
                                           output_format=output_format, **extra)
        _record("image", IMAGE_MODEL, len(resp.data) * IMAGE_PRICE, n=len(resp.data))
        return [base64.b64decode(d.b64_json) for d in resp.data]

    def segment(self, image: bytes, text: str, mime: str = "image/png") -> tuple[list[SamMatch], str]:
        """Find every instance of `text` in the image; returns parsed boxes and the raw output."""
        _check_budget(SAM_PRICE)
        resp = self.client.responses.create(
            model=SAM_MODEL,
            input=[{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": text},
                {"type": "input_image", "image_url": image_data_url(image, mime)},
            ]}],
            metadata={"include_confidence": "true"},
        )
        _record("sam", SAM_MODEL, SAM_PRICE)
        return parse_sam_output(resp.output_text), resp.output_text

    def transcribe(self, wav: bytes) -> dict:
        """Transcribe a mono 16-bit PCM WAV (16 or 24 kHz, up to 10 minutes)."""
        _check_budget()
        request = {"model": ASR_MODEL, "audioEncoding": "WAV", "mode": "PUSH_TO_TALK"}
        resp = self.http.post("/asr/transcribe", headers={"Accept": "application/json"}, files={
            "request": (None, json.dumps(request), "application/json"),
            "audio": ("audio.wav", wav, "audio/wav"),
        })
        resp.raise_for_status()
        body = resp.json()
        ms = body.get("audioDurationMs") or 0
        _record("asr", ASR_MODEL, ms / 3.6e6 * ASR_PRICE_PER_HOUR, audio_ms=ms)
        return body

"""Draw a chair: opt-in donation of a visitor's drawing for research. Off unless TIPPA_DONATIONS=1.

Off (the default), nothing here runs and nothing is stored: the page says drawings are never stored.
On, a visitor may tick "Donate my drawing to research (optional)" and "I am 18 or older". Only then, and
only if the drawing passes the checks below, one donation is appended:

  <donations dir>/donations.jsonl   one JSON line per donation (schema in docs/draw_donations.md)
  <donations dir>/png/<uuid>.png    the 256 px black-on-white picture DINOv2 saw

The donations dir is TIPPA_DONATIONS_DIR, else <data dir>/donations (TIPPA_DATA_DIR or TOT_DATA_DIR).
Data minimisation: a random UUID per donation (not linked to any session, cookie or address), the date
without a time, no IP, no name, no location. For uploads only the processed picture is kept, never the
photo. A donation is refused when the picture failed the drawing-on-paper check or looks like it has
writing in it (a name, say); scoring is not affected.

The consent text and the two placeholders Roger fills in (CONTACT, IRB_NOTE) live here.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import threading
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

# Placeholders until the IRB status is confirmed; the page shows them as written.
CONTACT = "{{CONTACT}}"
IRB_NOTE = "{{IRB_NOTE}}"
CONSENT_VERSION = "draft-2026-10-27"
CONSENT = {
    "label": "Donate my drawing to research (optional)",
    "adult": "I am 18 or older",
    "summary": "Not stored unless you choose to donate it.",
    "points": [
        ["What we keep", "your drawing as the black-on-white picture the model sees (for drawings on the pad, also "
                         "your pen strokes), the thing you drew, whether you drew it here or uploaded a photo, whether "
                         "you drew it before seeing the AI’s pictures, how long you took, your scores and the date. "
                         "Nothing else: no name, email, IP address, cookie or location. For a photo, we keep only "
                         "the cleaned-up drawing, never the photo itself."],
        ["Why", "to study how people and AI picture everyday things."],
        ["Sharing", "donated drawings may be shared with other researchers as an open dataset."],
        ["No take-backs", "because nothing links a drawing to you, it can’t be found or deleted later."],
        ["Questions", CONTACT],
    ],
    "irb": IRB_NOTE,
    "version": CONSENT_VERSION,
}
_lock = threading.Lock()


def enabled() -> bool:
    return os.environ.get("TIPPA_DONATIONS", "0").strip().lower() in ("1", "true", "yes")


def donations_dir() -> Path:
    if os.environ.get("TIPPA_DONATIONS_DIR"):
        return Path(os.environ["TIPPA_DONATIONS_DIR"])
    from metalesionlab.web import app as web

    return Path(web.DATA_DIR) / "donations"


def public_info() -> dict:
    """What the page needs to show (or not show) the donation option."""
    return {"enabled": True, **CONSENT} if enabled() else {"enabled": False}


def text_like(picture: Image.Image) -> bool:
    """A simple check for writing: several letter-sized blobs of similar height side by side on one line.

    Works on the 256 px ink-cropped picture. It's deliberately cautious (it only stops a donation, never a
    score): a row of 4 or more separate small marks of similar height counts as writing."""
    from scipy import ndimage

    ink = np.asarray(picture.convert("L")) < 128
    labels, n = ndimage.label(ink, structure=np.ones((3, 3)))
    if n < 4:
        return False
    boxes = ndimage.find_objects(labels)
    marks = []
    for sl in boxes:
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if 6 <= h <= 70 and 2 <= w <= 70:
            marks.append(((sl[0].start + sl[0].stop) / 2, h, (sl[1].start + sl[1].stop) / 2))
    if len(marks) < 4:
        return False
    for yc, h, _ in marks:  # marks on the same line as this one, of a similar height
        row = [m for m in marks if abs(m[0] - yc) <= max(6, h * 0.35) and 0.6 <= m[1] / h <= 1.6]
        if len(row) >= 4:
            xs = sorted(m[2] for m in row)
            gaps = np.diff(xs)
            if len(gaps) and np.median(gaps) <= 2.5 * h:  # close together, like letters in a word
                return True
    return False


def refusal(source: str, picture: Image.Image, problem: str | None) -> str | None:
    """Why a donation can't be accepted, or None."""
    if problem:
        return "it doesn't look like a line drawing on plain paper"
    if text_like(picture):
        return "it looks like it has writing in it"
    return None


def png_bytes(picture: Image.Image) -> bytes:
    buf = io.BytesIO()
    picture.convert("L").save(buf, "PNG", optimize=True)
    return buf.getvalue()


def donate(*, concept: str, source: str, picture: Image.Image, scores: dict, blind: bool | None,
           draw_seconds: float | None, strokes: list | None = None, problem: str | None = None) -> dict:
    """Store one donation if allowed. Returns {"status": "saved"} or {"status": "declined", "reason": ...}.
    The caller has checked enabled(), the donation tick and the age tick."""
    why = refusal(source, picture, problem)
    if why:
        return {"status": "declined", "reason": f"Thanks, but we can’t accept this one: {why}."}
    did = str(uuid.uuid4())
    record = {
        "id": did,
        "date": dt.datetime.now(dt.timezone.utc).date().isoformat(),
        "concept": concept,
        "source": source,  # "pad" or "upload"
        "blind": bool(blind) if blind is not None else None,
        "draw_seconds": round(float(draw_seconds), 1) if draw_seconds is not None else None,
        "scores": {k: scores.get(k) for k in ("originality", "d_human", "d_ai", "people_closer_to_muse",
                                              "muse_closer", "own_rank", "d_doodle", "nearest_ai", "nearest_human")},
        "strokes": strokes if source == "pad" else None,
        "png": f"png/{did}.png",
        "model": "facebook/dinov2-base",
        "consent": CONSENT_VERSION,
    }
    root = donations_dir()
    with _lock:
        (root / "png").mkdir(parents=True, exist_ok=True)
        with open(root / "png" / f"{did}.png", "xb") as f:  # never overwrite
            f.write(png_bytes(picture))
        with open(root / "donations.jsonl", "a", encoding="utf-8") as f:  # append only
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {"status": "saved"}

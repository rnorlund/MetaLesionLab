"""Smoke-test every Meta Model API we use: chat, vision chat, image generation, SAM 3.1, transcription.

Costs about $0.02. Outputs go to runs/smoke/.
Usage: python scripts/smoke_meta_api.py [speech.wav]
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from metalesionlab.meta_api import REPO_ROOT, MetaAPI, image_data_url, spent

OUT = REPO_ROOT / "runs" / "smoke"


def show(title, obj):
    print(f"\n== {title}\n{obj}")


def synth_wav(text: str) -> bytes | None:
    """Speak `text` with macOS `say` into a 16 kHz mono 16-bit WAV."""
    if not (shutil.which("say") and shutil.which("afconvert")):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        aiff, wav = Path(tmp) / "s.aiff", Path(tmp) / "s.wav"
        subprocess.run(["say", "-o", str(aiff), text], check=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(aiff), str(wav)], check=True)
        return wav.read_bytes()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    api = MetaAPI()

    r = api.chat([{"role": "user", "content": "Reply with exactly one word: what animal says meow?"}])
    show("chat", f"{r.choices[0].message.content!r}\nusage: {json.dumps(r.usage.model_dump())}")

    img = api.generate_images("A simple black line drawing of a single cat, centered, plain white background, no text")[0]
    (OUT / "cat.png").write_bytes(img)
    show("image", f"{len(img)} bytes -> {OUT / 'cat.png'}")

    r = api.chat([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": image_data_url(img)}},
        {"type": "text", "text": "Name the object in this picture with exactly one word."},
    ]}])
    show("vision chat", f"{r.choices[0].message.content!r}\nusage: {json.dumps(r.usage.model_dump())}")

    matches, raw = api.segment(img, "cat")
    show("sam", f"{len(matches)} match(es): {matches}\nraw (first 300 chars): {raw[:300]!r}")

    wav = Path(sys.argv[1]).read_bytes() if len(sys.argv) > 1 else synth_wav("cat. dog. umbrella.")
    if wav:
        show("transcribe", json.dumps(api.transcribe(wav), indent=1)[:800])
    else:
        print("\n== transcribe skipped (pass a WAV path)")

    print(f"\nLedger total: ${spent():.4f}")


if __name__ == "__main__":
    main()

"""Fetch the DINOv2-base ONNX model that /draw runs, at build time (standard library only).

The model is about 350 MB, far over the repository's 5 MB data guard, so it's never committed. This
downloads onnx-community's fp32 export of facebook/dinov2-base (Meta, Apache-2.0) at a pinned revision
and checks its SHA-256. Its CLS embeddings match the torch model the experiment used (cosine similarity
>= 0.99999 on 20 test drawings; scripts/draw_model.py verify). The Dockerfile runs:

    python metalesionlab/draw_fetch.py /app/models/dinov2-base.onnx

It needs no other file from the repository, so the Docker layer stays cached when the code changes.
scripts/draw_model.py export makes an equivalent file from the original weights with torch instead.
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
import urllib.request
from pathlib import Path

REPO_ID = "onnx-community/dinov2-base"
REVISION = "31ef06cac16d5d301c5930d147002a058c85a5e4"
FILE = "onnx/model.onnx"
SHA256 = "320d1012a6fc65b101fc85ca30ee7a47b2e4f6a2e8bd78fb9d7036def0e30cb0"
SIZE = 346627111
URL = f"https://huggingface.co/{REPO_ID}/resolve/{REVISION}/{FILE}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(out: Path, retries: int = 6, url: str = URL) -> Path:
    """Download to `out` (atomically) unless a verified copy is already there."""
    out = Path(out)
    if out.is_file() and out.stat().st_size == SIZE and sha256(out) == SHA256:
        print(f"{out} is already there and verified")
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    for attempt in range(retries):
        try:
            h = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=60) as r, tmp.open("wb") as f:
                for chunk in iter(lambda: r.read(1 << 20), b""):
                    f.write(chunk)
                    h.update(chunk)
            if h.hexdigest() != SHA256:
                raise ValueError("SHA-256 mismatch")
            os.replace(tmp, out)
            print(f"wrote {out} ({out.stat().st_size / 1e6:.0f} MB, SHA-256 verified)")
            return out
        except (OSError, ValueError) as e:
            wait = min(60, 5 * 2 ** attempt)
            print(f"download failed ({e}); retrying in {wait} s", flush=True)
            time.sleep(wait)
    tmp.unlink(missing_ok=True)
    raise SystemExit(f"couldn't download {url}")


if __name__ == "__main__":
    fetch(Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DRAW_MODEL", "dinov2-base.onnx")))

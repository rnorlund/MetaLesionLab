"""Check every passage in public_data/plato_passages.json word for word against its Project Gutenberg text.

Each passage's source_text_url is downloaded once (retrying with backoff, since DNS on the lab Mac drops
now and then), whitespace is collapsed on both sides, and the passage must appear as an exact substring.
Exit status 1 if any passage doesn't match. Ask Socrates may quote Plato only from this file.

    python scripts/verify_plato_passages.py [--cache DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASSAGES = ROOT / "public_data" / "plato_passages.json"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\r", "")).strip()


def fetch(url: str, cache: Path | None, tries: int = 6) -> str:
    if cache:
        hit = cache / re.sub(r"[^\w.]+", "_", url)
        if hit.exists():
            return hit.read_text(encoding="utf-8")
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                text = r.read().decode("utf-8")
            break
        except OSError as e:
            if attempt == tries - 1:
                raise
            wait = min(60, 3 * 2 ** attempt)
            print(f"  {url}: {e}; retrying in {wait} s", file=sys.stderr)
            time.sleep(wait)
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        hit.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", type=Path, help="keep downloaded texts here")
    args = ap.parse_args()
    data = json.loads(PASSAGES.read_text(encoding="utf-8"))
    sources: dict[str, str] = {}
    bad = 0
    for p in data["passages"]:
        url = p["source_text_url"]
        if url not in sources:
            sources[url] = norm(fetch(url, args.cache))
        ok = norm(p["text"]) in sources[url]
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {p['id']:<16} {p['work']} {p['stephanus']:<8} {len(p['text'].split())} words")
    print(f"{len(data['passages']) - bad} of {len(data['passages'])} passages match their Gutenberg text")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

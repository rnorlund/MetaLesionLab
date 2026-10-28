"""Check every passage in public_data/plato_passages.json word for word against its public-domain source.

The file holds the passages the site may quote: Plato in Benjamin Jowett's translation and Aristotle in
W. D. Ross's. Each source text is downloaded once (retrying with backoff, since DNS on the lab Mac drops now
and then) and every passage is checked:

1. Exact, against source_text_url: Project Gutenberg's plain text for Jowett; for Ross, the clean digital text
   of the MIT Internet Classics Archive. Whitespace is collapsed and curly quotes count as straight ones;
   otherwise the passage must appear character for character. A passage with "as_printed" quotes a word the
   source sets in capitals at the start of a book ("ALL men by nature ...") in sentence case: as_printed must
   appear exactly, and text must equal it but for letter case.
2. Word for word, against the printed edition (print_text_url, Aristotle only): the Internet Archive's scan of
   the Oxford edition whose year the translation names, read through its OCR. A digital transcription can
   drop a word (the MIT text of Physics II.3 reads "the 'why' of (which" where the 1930 printing has "the
   'why' of it (which"), so every word of the passage must also be in the printing, in order, none missing or
   changed. Only letters and digits are compared (OCR punctuation is unreliable), a hyphen joins its words,
   and the scan's extra tokens are skipped when they are margin numbers (they contain a digit) or a page
   break's footnotes and running head (8 or more tokens together). A dropped or changed word fails.

Exit status 1 if any passage fails. Ask Socrates may quote only these passages, and the pages' epigraphs are
rendered from them.

    python scripts/verify_passages.py [--cache DIR]
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASSAGES = ROOT / "public_data" / "plato_passages.json"
PAGE_BREAK = 8  # a run of at least this many extra scan tokens is a page break, not a dropped word
QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})
NUMERALS = str.maketrans({"i": "1", "l": "1", "o": "0"})  # OCR reads margin and list numbers as letters


def norm(text: str) -> str:
    """Whitespace collapsed, curly quotes straight: the exact comparison."""
    return re.sub(r"\s+", " ", text.replace("\r", "").translate(QUOTES)).strip()


def words(text: str) -> list[str]:
    """Letters and digits only, lower case, for comparing with OCR: hyphens join (also across a line end)."""
    t = text.lower().translate(QUOTES).replace("'", "")
    t = re.sub(r"-\s*\n\s*", "", t)
    t = re.sub(r"(?<=[a-z])-(?=[a-z])", "", t)
    out = []
    for w in re.findall(r"[a-z0-9]+", t):
        out.append(w.translate(NUMERALS) if w in ("i", "l") or any(c.isdigit() for c in w) else w)
    return out


def in_print(passage: str, scan: list[str]) -> tuple[bool, str]:
    """Is every word of the passage in the scan, in order, with only margin numbers or a page break between?"""
    want = words(passage)
    n = len(want)
    best = (None, f"not found in the printed edition: {' '.join(want[:6])} …")
    starts = set()
    for off in sorted({0, n // 2, max(0, n - 3)}):
        gram = want[off:off + 3]
        for k in range(len(scan) - len(gram) + 1):
            if scan[k:k + len(gram)] == gram:
                starts.add(max(0, k - off - 10))
    for s in sorted(starts):
        window = scan[s:s + n + 120]
        ops = difflib.SequenceMatcher(None, want, window, autojunk=False).get_opcodes()
        problems = []
        for tag, a1, a2, b1, b2 in ops:
            if tag == "equal" or (tag == "insert" and (a1 == 0 or a1 == n)):
                continue  # text before or after the passage
            if tag == "insert":
                extra = window[b1:b2]
                if all(any(c.isdigit() for c in w) for w in extra) or len(extra) >= PAGE_BREAK:
                    continue
                problems.append(f"print has {' '.join(extra)!r} after {' '.join(want[max(0, a1 - 3):a1])!r}")
            elif tag == "replace" and "".join(want[a1:a2]) == "".join(window[b1:b2]):
                continue  # the same letters split differently: a word broken at a line end without its hyphen
            else:
                problems.append(f"passage {' '.join(want[a1:a2])!r} vs print {' '.join(window[b1:b2])!r}")
        if not problems:
            return True, "ok"
        if best[0] is None or len(problems) < best[0]:
            best = (len(problems), "; ".join(problems[:3]))
    return False, best[1]


def fetch(url: str, cache: Path | None, tries: int = 6) -> str:
    if cache:
        hit = cache / re.sub(r"[^\w.]+", "_", url)
        if hit.exists():
            return hit.read_text(encoding="utf-8")
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MetaLesionLab passage check"})
            with urllib.request.urlopen(req, timeout=120) as r:
                text = r.read().decode("utf-8", errors="replace")
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


def ref(p: dict) -> str:
    return p.get("stephanus") or p.get("bekker") or "?"


def check(p: dict, sources: dict[str, str], scans: dict[str, list[str]], cache: Path | None) -> list[str]:
    """Problems with one passage ([] if it matches its source, and its printed edition if it has one)."""
    url = p["source_text_url"]
    if url not in sources:
        sources[url] = norm(fetch(url, cache))
    exact = p.get("as_printed", p["text"])
    problems = []
    if norm(exact) not in sources[url]:
        problems.append("not word for word in " + url)
    if "as_printed" in p and p["as_printed"].lower() != p["text"].lower():
        problems.append("text differs from as_printed by more than letter case")
    if p.get("print_text_url"):
        purl = p["print_text_url"]
        if purl not in scans:
            scans[purl] = words(fetch(purl, cache))
        ok, why = in_print(p["text"], scans[purl])
        if not ok:
            problems.append("printed edition: " + why)
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", type=Path, help="keep downloaded texts here")
    args = ap.parse_args()
    data = json.loads(PASSAGES.read_text(encoding="utf-8"))
    sources: dict[str, str] = {}
    scans: dict[str, list[str]] = {}
    bad = 0
    for p in data["passages"]:
        problems = check(p, sources, scans, args.cache)
        bad += bool(problems)
        where = "text + print" if p.get("print_text_url") else "text"
        print(f"{'BAD' if problems else 'ok '} {p['id']:<20} {p.get('author', 'Plato'):<9} "
              f"{p['work'] + ' ' + ref(p):<32} {len(p['text'].split()):>3} words ({where})")
        for why in problems:
            print("      " + why)
    n = len(data["passages"])
    print(f"{n - bad} of {n} passages match their sources word for word")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

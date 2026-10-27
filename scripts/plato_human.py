"""Plato's Chair, step 2: human drawings of the same concepts from Google Quick, Draw!

Usage: python -I scripts/plato_human.py [--keys chair sailboat ...] [--keep 200] [--max-lines 5000]

Streams the simplified ndjson for each category from the public bucket and stops after the first
`keep` drawings flagged recognized=true (never downloads a whole file). Each drawing is rendered at
256 px, black on white, to $PLATO_DIR/human/<key>/NNN.png, with the kept strokes in strokes.ndjson
(outside the repo; never commit the drawings).
Data: Google Quick, Draw! dataset, CC BY 4.0, https://github.com/googlecreativelab/quickdraw-dataset
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato import BY_KEY, CONCEPTS, PLATO_DIR, QUICKDRAW_URL, render_strokes, stream_quickdraw  # noqa: E402

OUT = PLATO_DIR / "human"


def fetch(key: str, keep: int, max_lines: int) -> str:
    folder = OUT / key
    if len(list(folder.glob("*.png"))) >= keep:
        return f"{key}: already have {keep}"
    concept = BY_KEY[key]
    kept = stream_quickdraw(concept.quickdraw, keep=keep, max_lines=max_lines)
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "strokes.ndjson").open("w") as f:
        for i, rec in enumerate(kept):
            render_strokes(rec["drawing"]).save(folder / f"{i:03d}.png")
            f.write(json.dumps(rec) + "\n")
    (folder / "meta.json").write_text(json.dumps({
        "concept": concept.label, "quickdraw": concept.quickdraw, "n": len(kept),
        "source": QUICKDRAW_URL.format(category=concept.quickdraw.replace(" ", "%20")),
        "filter": "first drawings in file order with recognized=true", "license": "CC BY 4.0",
        "countries": sorted({r["countrycode"] for r in kept if r.get("countrycode")}),
    }, indent=1))
    return f"{key}: kept {len(kept)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--keep", type=int, default=200)
    ap.add_argument("--max-lines", type=int, default=5000)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    keys = args.keys or [c.key for c in CONCEPTS]
    with ThreadPoolExecutor(args.workers) as pool:
        for msg in pool.map(lambda k: fetch(k, args.keep, args.max_lines), keys):
            print(msg, flush=True)


if __name__ == "__main__":
    main()

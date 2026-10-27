"""Collect Quick, Draw! doodles by country and render them as 256 px PNGs.

Streams each category's simplified ndjson (Google, CC BY 4.0) line by line and stops once every
country has enough recognized drawings, so whole files are never downloaded. Lines are parsed as
JSON data only. Run with `python -I` (this script adds the repo root to sys.path itself).

Writes $PLATO_LANG_DIR/human/<country>/<concept>/<key_id>.png and human/manifest.json.
Never commit these files.

Usage: python -I scripts/plato_lang_humans.py [--per-country 200] [--concepts chair,house]
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato_lang import CONCEPTS, COUNTRIES, OUT, QD_CREDIT, render_strokes, stream_quickdraw  # noqa: E402


def collect(concept: str, per_country: int) -> dict:
    t0 = time.time()
    records, n_bytes, n_lines = stream_quickdraw(concept, COUNTRIES, per_country)
    counts = {}
    for country, recs in records.items():
        folder = OUT / "human" / country / concept
        folder.mkdir(parents=True, exist_ok=True)
        for rec in recs:
            if not rec["key_id"].isdigit():
                continue
            render_strokes(rec["drawing"]).save(folder / f"{rec['key_id']}.png", optimize=True)
        counts[country] = len(recs)
    info = {"counts": counts, "mb_read": round(n_bytes / 1e6, 1), "lines_read": n_lines,
            "seconds": round(time.time() - t0, 1)}
    print(f"{concept}: {info}", flush=True)
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-country", type=int, default=200)
    ap.add_argument("--concepts", default=",".join(CONCEPTS))
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    concepts = args.concepts.split(",")
    with ThreadPoolExecutor(args.workers) as pool:
        infos = dict(zip(concepts, pool.map(lambda c: collect(c, args.per_country), concepts)))
    path = OUT / "human" / "manifest.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    old.update({"source": QD_CREDIT, "per_country": args.per_country, "countries": COUNTRIES})
    old.setdefault("concepts", {}).update(infos)
    path.write_text(json.dumps(old, indent=1))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()

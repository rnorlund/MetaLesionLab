"""The Atlas of Forms, steps 2 and 3: people's drawings and the DINOv2 embeddings.

  human   the first 200 recognized Quick, Draw! drawings of each new concept, rendered as in the core
          ($PLATO_ATLAS_DIR/human/<key>/NNN.png, strokes.ndjson, meta.json); reads up to 5,000 lines,
          then up to 20,000 if that held fewer than 200 (pre-registered)
  embed   DINOv2 (CLS and patch mean) of every new concept's Muse, SDXL and human pictures, ink-cropped
          exactly as in plato_embed.py ($PLATO_ATLAS_DIR/embeddings/<source>/<key>.npz). Core and forms
          concepts already have embeddings in their own folders and are only read.

Usage: python -I scripts/plato_atlas_data.py human [--keys ...] [--workers 6]
       python -I scripts/plato_atlas_data.py embed [--keys ...] [--device mps|cpu] [--sources human ...]
Human drawings: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0. They stay outside the repo.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from plato_embed import PREP, prepare  # noqa: E402

from metalesionlab.plato import (DINO_MODEL, QUICKDRAW_URL, Embedder, load_dir, render_strokes,  # noqa: E402
                                 stream_quickdraw)
from metalesionlab.plato_atlas import ATLAS_DIR, BY_KEY, N_HUMAN, NEW, embedding_path, folders  # noqa: E402

SOURCES = ("ai_doodle", "ai_sdxl_doodle", "human")


def fetch(key: str, keep: int) -> str:
    c = BY_KEY[key]
    folder = ATLAS_DIR / "human" / key
    if len(list(folder.glob("*.png"))) >= keep:
        return f"{key}: already have {keep}"
    for attempt in range(5):
        try:
            max_lines = 5000
            kept = stream_quickdraw(c.quickdraw, keep=keep, max_lines=max_lines)
            if len(kept) < keep:
                max_lines = 20000
                kept = stream_quickdraw(c.quickdraw, keep=keep, max_lines=max_lines)
            break
        except Exception as e:  # noqa: BLE001 - DNS drops on this Mac
            print(f"  {key} attempt {attempt + 1}: {type(e).__name__}: {e}", flush=True)
            time.sleep(10 * 2 ** attempt)
    else:
        return f"{key}: FAILED"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "strokes.ndjson").open("w") as f:
        for i, rec in enumerate(kept):
            render_strokes(rec["drawing"]).save(folder / f"{i:03d}.png")
            f.write(json.dumps(rec) + "\n")
    (folder / "meta.json").write_text(json.dumps({
        "concept": c.label, "quickdraw": c.quickdraw, "n": len(kept), "max_lines": max_lines,
        "source": QUICKDRAW_URL.format(category=c.quickdraw.replace(" ", "%20")),
        "filter": "first drawings in file order with recognized=true", "license": "CC BY 4.0",
        "countries": sorted({r["countrycode"] for r in kept if r.get("countrycode")})}, indent=1))
    return f"{key}: kept {len(kept)} (read up to {max_lines} lines)"


def cmd_human(args):
    keys = args.keys or [c.key for c in NEW]
    with ThreadPoolExecutor(args.workers) as pool:
        for msg in pool.map(lambda k: fetch(k, args.keep), keys):
            print(msg, flush=True)


def cmd_embed(args):
    keys = args.keys or [c.key for c in NEW]
    embed, t0, count = None, time.time(), 0
    for source in args.sources or SOURCES:
        for key in keys:
            c = BY_KEY[key]
            files = load_dir(folders(c)[source])
            if not files:
                continue
            out = embedding_path(c, source)
            names = [f.name for f in files]
            if out.exists():
                old = np.load(out)
                if list(old["files"]) == names and str(old["prep"]) == PREP:
                    continue
            embed = embed or Embedder(DINO_MODEL, args.device)
            vecs = embed([prepare(f, source) for f in files])
            out.parent.mkdir(parents=True, exist_ok=True)
            np.savez(out, files=np.array(names), model=DINO_MODEL, prep=PREP, **vecs)
            count += len(files)
            print(f"{source:15s} {key:16s} {len(files):4d} pictures ({time.time() - t0:.0f}s)", flush=True)
    print(f"embedded {count} pictures in {time.time() - t0:.0f}s" + (f" on {embed.device}" if embed else ""))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("human")
    h.add_argument("--keys", nargs="*")
    h.add_argument("--keep", type=int, default=N_HUMAN)
    h.add_argument("--workers", type=int, default=6)
    e = sub.add_parser("embed")
    e.add_argument("--keys", nargs="*")
    e.add_argument("--device")
    e.add_argument("--sources", nargs="*", choices=SOURCES)
    args = ap.parse_args()
    {"human": cmd_human, "embed": cmd_embed}[args.cmd](args)


if __name__ == "__main__":
    main()

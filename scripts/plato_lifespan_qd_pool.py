"""The life of a chair: a larger pool of Quick, Draw! drawings (CC BY 4.0) to pick stand-ins from.

Children's drawings are never shown (their license is non-commercial and share-alike, and they are
children's). To still show "what a typical drawing at age N looks like", the figures and the page show a
Quick, Draw! LOOKALIKE: the drawing in this pool nearest (DINOv2 cosine) to the age group's medoid. The pool
keeps recognized AND unrecognized drawings, so rough, scribbly drawings exist in it as well.

Usage: python -I scripts/plato_lifespan_qd_pool.py [--keys chair ...] [--n 3000]
Writes $PLATO_LIFESPAN_DIR/qd_pool/<key>.ndjson (strokes, key_id, recognized) and
embeddings/qd_pool/<key>.npz. Streams the public file line by line; retries with backoff.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab.plato import BY_KEY, DINO_MODEL, QUICKDRAW_URL, Embedder, ink_crop, render_strokes  # noqa: E402
from metalesionlab.plato_lifespan import LIFESPAN_DIR  # noqa: E402

PREP = "render_strokes(256, w3) + ink_crop(256)"


def stream_all(category: str, n: int, timeout: float = 60) -> list[dict]:
    import httpx

    url = QUICKDRAW_URL.format(category=category.replace(" ", "%20"))
    for attempt in range(6):
        kept = []
        try:
            with httpx.stream("GET", url, timeout=timeout) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if rec.get("word") == category:
                        kept.append({"key_id": rec.get("key_id"), "recognized": bool(rec.get("recognized")),
                                     "drawing": rec["drawing"]})
                    if len(kept) >= n:
                        return kept
            return kept
        except Exception as e:  # DNS drops on this Mac: back off and retry
            print(f"{category}: attempt {attempt} failed ({type(e).__name__}); retrying", flush=True)
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError(f"could not stream {category}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", nargs="*", default=["chair"])
    ap.add_argument("--n", type=int, default=3000)
    args = ap.parse_args()
    embed = None
    for key in args.keys:
        src = LIFESPAN_DIR / "qd_pool" / f"{key}.ndjson"
        if not src.exists():
            recs = stream_all(BY_KEY[key].quickdraw, args.n)
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text("\n".join(json.dumps(r) for r in recs))
        recs = [json.loads(line) for line in src.read_text().splitlines()]
        out = LIFESPAN_DIR / "embeddings" / "qd_pool" / f"{key}.npz"
        if out.exists() and len(np.load(out)["key_ids"]) == len(recs):
            continue
        embed = embed or Embedder(DINO_MODEL)
        vecs = embed([ink_crop(render_strokes(r["drawing"])) for r in recs])
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez(out, key_ids=np.array([str(r["key_id"]) for r in recs]),
                 recognized=np.array([r["recognized"] for r in recs]), model=DINO_MODEL, prep=PREP, **vecs)
        print(f"{key}: {len(recs)} drawings ({sum(r['recognized'] for r in recs)} recognized)", flush=True)


if __name__ == "__main__":
    main()

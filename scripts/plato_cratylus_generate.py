"""Plato's Cratylus, drawing arm: Muse Image draws "a shape called '<word>'" (plato_cratylus.WORDS).

Separate calls of n = 4 (Muse Image has no seed), pictures downscaled to 512 px and saved as
$CRATYLUS_DIR/ai/<slug>/p<i>.png with meta.json (prompt, call, time). Resumable: a word's finished
calls are skipped. Paid ($0.01 a picture); stops if the ledger passes $70 or this run passes --max-usd.
"""
import argparse
import json
import os
import time
from pathlib import Path

from metalesionlab import plato_cratylus as pk
from metalesionlab.meta_api import MetaAPI, retry_network, spent
from metalesionlab.plato import downscale

CRATYLUS_DIR = Path(os.environ.get("CRATYLUS_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/cratylus"))
LEDGER_STOP = 70.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", nargs="*", help="default: all of plato_cratylus.WORDS")
    ap.add_argument("--max-usd", type=float, default=2.6)
    args = ap.parse_args()
    api = MetaAPI()
    api.client = api.client.with_options(timeout=180)  # a hung call (seen once) times out and is retried
    start = spent()
    words = [pk.BY_WORD[w] for w in args.words] if args.words else pk.WORDS
    for w in words:
        folder = CRATYLUS_DIR / "ai" / pk.slug(w.word)
        folder.mkdir(parents=True, exist_ok=True)
        meta_path = folder / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"word": w.word, "prompt": pk.prompt_for(w.word),
                                                                          "pictures": []}
        calls = w.n // 4
        while len({p["call"] for p in meta["pictures"]}) < calls:
            if spent() > LEDGER_STOP or spent() - start > args.max_usd:
                raise SystemExit(f"stop: ledger ${spent():.2f}, this run ${spent() - start:.2f}")
            call = len({p["call"] for p in meta["pictures"]})
            pngs = retry_network(lambda: api.generate_images(meta["prompt"], n=4))
            for png in pngs:
                i = len(meta["pictures"])
                downscale(png).save(folder / f"p{i}.png")
                meta["pictures"].append({"file": f"p{i}.png", "call": call, "t": round(time.time(), 1)})
            meta_path.write_text(json.dumps(meta, indent=1))
            print(f"{w.word}: call {call + 1}/{calls}, {len(pngs)} pictures (run ${spent() - start:.2f})", flush=True)
    print(f"done; this run ${spent() - start:.2f}, ledger ${spent():.2f}")


if __name__ == "__main__":
    main()

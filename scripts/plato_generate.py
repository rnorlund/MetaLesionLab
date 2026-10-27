"""Plato's Chair, step 1: ask Muse Image to draw every concept 16 (tier 1) or 12 (tier 2) times.

Usage: python scripts/plato_generate.py [--style doodle|photo] [--keys chair sailboat ...]
       [--per-concept N] [--batch 4] [--workers 3] [--budget 9.0] [--shared-stop 40]

Concepts are drawn in priority order (tier 1 first), so the key comparisons exist even if we stop
early. Each concept gets n/batch separate calls (no seed parameter exists, so separate calls are
the natural variability). Pictures are downscaled to 512 px and saved as
$PLATO_DIR/ai/<style>/<key>/c<call>_<i>.png (outside the repo). Resumable: existing pictures are kept.
A concept's meta.json says "complete": true as soon as it has all its pictures.
This experiment's own spend is reserved before each call in $PLATO_DIR/spend.jsonl and capped by
--budget; every call also goes through MetaAPI, so the shared ledger (MLL_LEDGER) and its cap see it.
New calls stop once the shared ledger total passes --shared-stop.
"""
import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import APITimeoutError  # noqa: E402

from metalesionlab.meta_api import IMAGE_MODEL, IMAGE_PRICE, LEDGER, MetaAPI, spent  # noqa: E402
from metalesionlab.plato import BY_KEY, CONCEPTS, PHOTO_KEYS, PLATO_DIR, downscale, prompt_for  # noqa: E402

OUT = PLATO_DIR
SPEND_LOG = OUT / "spend.jsonl"
_lock = threading.Lock()


def my_spend() -> float:
    if not SPEND_LOG.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in SPEND_LOG.read_text().splitlines() if line.strip())


def log_spend(**entry) -> None:
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SPEND_LOG.open("a") as f:
        f.write(json.dumps({"ts": round(time.time(), 1), **entry}) + "\n")


def run_call(api: MetaAPI, style: str, key: str, call: int, n: int, budget: float, shared_stop: float,
             per_concept: int) -> tuple[str, int, int]:
    concept = BY_KEY[key]
    prompt = prompt_for(concept, style)
    with _lock:
        if my_spend() + n * IMAGE_PRICE > budget + 1e-9:
            raise RuntimeError(f"experiment budget ${budget:.2f} reached")
        if spent() > shared_stop:
            raise RuntimeError(f"shared ledger passed ${shared_stop:.2f}; stopping")
        log_spend(kind="reserve", usd=n * IMAGE_PRICE, style=style, key=key, call=call, n=n)
    images = []
    attempts = 6
    for attempt in range(attempts):
        try:
            images = api.generate_images(prompt, n=n)
            break
        except APITimeoutError:
            # the server may still have drawn (and billed) these: keep the reservation, don't retry
            print(f"  {key} call {call}: timed out; reservation kept", flush=True)
            return key, call, 0
        except Exception as e:  # noqa: BLE001 - DNS/connection errors, rate limits and server errors
            print(f"  {key} call {call} attempt {attempt + 1} failed: {type(e).__name__}: {e}", flush=True)
            if attempt < attempts - 1:
                time.sleep(15 * 2 ** attempt)  # 15 s, 30 s, ... 4 min: rides out a short network outage
    # refund the reservation for images that never came back (the shared ledger records actual spend)
    if len(images) < n:
        log_spend(kind="refund", usd=-(n - len(images)) * IMAGE_PRICE, style=style, key=key, call=call)
    folder = OUT / "ai" / style / key
    folder.mkdir(parents=True, exist_ok=True)
    for i, png in enumerate(images):
        downscale(png, 512).save(folder / f"c{call}_{i}.png")
    # mark the concept complete as soon as it has all its pictures, so other analyses can start on it
    with _lock:
        have = len(list(folder.glob("c*_*.png")))
        meta = json.loads((folder / "meta.json").read_text())
        meta.update(n=have, complete=have >= per_concept)
        (folder / "meta.json").write_text(json.dumps(meta, indent=1))
    return key, call, len(images)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="doodle", choices=["doodle", "photo"])
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--per-concept", type=int, help="override each concept's n_ai (16 tier 1, 12 tier 2)")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--workers", type=int, default=3)  # 8 parallel calls hung for 10+ min; 2 took 108 s
    ap.add_argument("--budget", type=float, default=9.0)
    ap.add_argument("--shared-stop", type=float, default=40.0)
    args = ap.parse_args()

    keys = args.keys or ([c.key for c in CONCEPTS] if args.style == "doodle" else PHOTO_KEYS)
    jobs = []
    for key in keys:
        per = args.per_concept or BY_KEY[key].n_ai
        folder = OUT / "ai" / args.style / key
        folder.mkdir(parents=True, exist_ok=True)
        have = len(list(folder.glob("c*_*.png")))
        meta = {"concept": BY_KEY[key].label, "quickdraw": BY_KEY[key].quickdraw, "style": args.style,
                "prompt": prompt_for(BY_KEY[key], args.style), "model": IMAGE_MODEL, "batch": args.batch,
                "n": have, "n_target": per, "complete": have >= per}
        (folder / "meta.json").write_text(json.dumps(meta, indent=1))
        calls_done = {int(p.stem.split("_")[0][1:]) for p in folder.glob("c*_*.png")}
        need, call = per - have, 0
        while need > 0:
            if call not in calls_done:
                jobs.append((key, call, min(args.batch, need), per))
                need -= min(args.batch, need)
            call += 1
    cost = sum(j[2] for j in jobs) * IMAGE_PRICE
    print(f"{len(jobs)} calls, {sum(j[2] for j in jobs)} images, ${cost:.2f}; "
          f"experiment spend so far ${my_spend():.2f} of ${args.budget:.2f}", flush=True)
    if not jobs:
        return
    print(f"shared ledger {LEDGER}: ${spent():.2f}", flush=True)
    api = MetaAPI()
    # fail fast instead of the client's silent 10-minute timeouts and retries
    api.client = api.client.with_options(timeout=400, max_retries=0)
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(run_call, api, args.style, key, call, n, args.budget, args.shared_stop, per)
                   for key, call, n, per in jobs]
        for done, fut in enumerate(as_completed(futures), 1):
            try:
                key, call, got = fut.result()
                print(f"[{done}/{len(jobs)}] {key} call {call}: {got} images ({time.time() - t0:.0f}s)", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{done}/{len(jobs)}] FAILED: {e}", flush=True)
    print(f"done in {time.time() - t0:.0f}s; experiment spend ${my_spend():.2f}; shared ledger ${spent():.2f}",
          flush=True)


if __name__ == "__main__":
    main()

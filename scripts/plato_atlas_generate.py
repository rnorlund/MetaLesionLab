"""The Atlas of Forms, step 1: Muse Image draws each of the 98 new concepts 12 times (3 calls of n = 4).

Usage: python scripts/plato_atlas_generate.py [--keys ant whale ...] [--workers 3] [--budget 14] [--shared-stop 70]

The prompt is the core doodle prompt (plato.STYLES["doodle"]) with the concept's phrase. Pictures are
downscaled to 512 px and saved as $PLATO_ATLAS_DIR/ai/doodle/<key>/c<call>_<i>.png with a meta.json, the
same layout as the core, so the rest of the pipeline reads them unchanged. Resumable: existing pictures
are kept.

Spend: each call is reserved in $PLATO_ATLAS_DIR/spend.jsonl before it is made and capped by --budget;
every call also goes through MetaAPI, so the shared ledger (MLL_LEDGER) sees it. New calls stop once the
shared ledger passes --shared-stop. Connection errors (DNS drops on this Mac) are retried with backoff;
a timed-out call keeps its reservation (it may have been billed) and is not retried in the same run.
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
from metalesionlab.plato import downscale  # noqa: E402
from metalesionlab.plato_atlas import ATLAS_DIR, BY_KEY, N_NEW, NEW, prompt_for  # noqa: E402

SPEND_LOG = ATLAS_DIR / "spend.jsonl"
_lock = threading.Lock()


def my_spend() -> float:
    if not SPEND_LOG.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in SPEND_LOG.read_text().splitlines() if line.strip())


def log_spend(**entry) -> None:
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SPEND_LOG.open("a") as f:
        f.write(json.dumps({"ts": round(time.time(), 1), **entry}) + "\n")


def folder_for(key: str) -> Path:
    return ATLAS_DIR / "ai" / "doodle" / key


def pictures(key: str) -> list[Path]:
    return sorted(folder_for(key).glob("c*_*.png"))


def run_call(api: MetaAPI, key: str, call: int, n: int, budget: float, shared_stop: float) -> tuple[str, int, int]:
    with _lock:
        if my_spend() + n * IMAGE_PRICE > budget + 1e-9:
            raise RuntimeError(f"atlas budget ${budget:.2f} reached")
        if spent() > shared_stop:
            raise RuntimeError(f"shared ledger passed ${shared_stop:.2f}; stopping")
        log_spend(kind="reserve", usd=n * IMAGE_PRICE, key=key, call=call, n=n)
    prompt = prompt_for(BY_KEY[key])
    images, attempts = [], 7
    for attempt in range(attempts):
        try:
            images = api.generate_images(prompt, n=n)
            break
        except APITimeoutError:
            print(f"  {key} call {call}: timed out; reservation kept", flush=True)
            return key, call, 0
        except Exception as e:  # noqa: BLE001 - DNS/connection errors, rate limits, server errors
            print(f"  {key} call {call} attempt {attempt + 1} failed: {type(e).__name__}: {e}", flush=True)
            if attempt < attempts - 1:
                time.sleep(min(15 * 2 ** attempt, 300))  # 15 s ... 5 min: rides out a DNS outage
    if len(images) < n:
        log_spend(kind="refund", usd=-(n - len(images)) * IMAGE_PRICE, key=key, call=call)
    folder = folder_for(key)
    for i, png in enumerate(images):
        downscale(png, 512).save(folder / f"c{call}_{i}.png")
    with _lock:
        meta = json.loads((folder / "meta.json").read_text())
        have = len(pictures(key))
        meta.update(n=have, complete=have >= meta["n_target"])
        (folder / "meta.json").write_text(json.dumps(meta, indent=1))
    return key, call, len(images)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--per-concept", type=int, default=N_NEW)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--budget", type=float, default=14.0)
    ap.add_argument("--shared-stop", type=float, default=70.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    keys = args.keys or [c.key for c in NEW]
    print(f"shared ledger {LEDGER}: ${spent():.2f}; atlas spend ${my_spend():.2f} of ${args.budget:.2f}", flush=True)
    jobs = []
    for key in keys:
        c = BY_KEY[key]
        folder = folder_for(key)
        folder.mkdir(parents=True, exist_ok=True)
        have = len(pictures(key))
        meta_path = folder / "meta.json"
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        meta.update({"concept": c.label, "quickdraw": c.quickdraw, "style": "doodle", "prompt": prompt_for(c),
                     "model": IMAGE_MODEL, "batch": args.batch, "n": have, "n_target": args.per_concept,
                     "complete": have >= args.per_concept})
        meta_path.write_text(json.dumps(meta, indent=1))
        done = {int(p.stem.split("_")[0][1:]) for p in pictures(key)}
        need, call = args.per_concept - have, 0
        while need > 0:
            if call not in done:
                k = min(args.batch, need)
                jobs.append((key, call, k))
                need -= k
            call += 1
    n_img = sum(j[2] for j in jobs)
    print(f"{len(jobs)} calls, {n_img} images, ${n_img * IMAGE_PRICE:.2f}", flush=True)
    if not jobs or args.dry_run:
        return
    api = MetaAPI()
    api.client = api.client.with_options(timeout=400, max_retries=0)
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(run_call, api, key, call, n, args.budget, args.shared_stop) for key, call, n in jobs]
        for done, fut in enumerate(as_completed(futures), 1):
            try:
                key, call, got = fut.result()
                print(f"[{done}/{len(jobs)}] {key} call {call}: {got} images ({time.time() - t0:.0f}s)", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{done}/{len(jobs)}] FAILED: {e}", flush=True)
    print(f"done in {time.time() - t0:.0f}s; atlas spend ${my_spend():.2f}; shared ledger ${spent():.2f}", flush=True)


if __name__ == "__main__":
    main()

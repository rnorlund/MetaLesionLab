"""Ask it to be a crowd, step 1: Muse Image doodles each concept 16 times, each call with one stated age.

Usage:
  MLL_LEDGER=<main repo>/runs/costs.jsonl python scripts/plato_crowd_generate.py --pilot     the 2 pilot pictures
  MLL_LEDGER=<main repo>/runs/costs.jsonl python scripts/plato_crowd_generate.py [--keys chair god ...] [--workers 3]

Picture i of every concept is drawn with plato_crowd.prompt_for(key, AGES[i]): the first run's doodle prompt, word for
word, after "Drawn by a 34-year-old: ". One call of n = 1 per picture (each picture has its own prompt), downscaled to
512 px, saved as $PLATO_CROWD_DIR/ai/persona/<key>/pNN_ageAA.png with a meta.json. Resumable: existing pictures are
kept. The pilot (plato_crowd.PILOT) goes to pilot/ and is not analysed.

Refusals are data (plato_ideas_generate.py's rules): a 4xx is recorded in calls.jsonl and tried again, at most
MAX_ATTEMPTS times in all; network errors are retried with backoff and are not refusals; a timed-out call keeps its
reservation and is not retried in this run.

Spend: every call goes through MetaAPI, so the shared ledger (MLL_LEDGER; set it to the main repository's
runs/costs.jsonl when running from a worktree) books it. This task's own cap is counted at IMAGE_USD a picture in
spend.jsonl, reserved before each call and refunded for pictures that never came back; no call is made past
BUDGET_USD, or once the shared ledger reaches SHARED_STOP.
"""
import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import openai  # noqa: E402
from openai import APITimeoutError  # noqa: E402

from metalesionlab.meta_api import IMAGE_MODEL, LEDGER, MetaAPI, spent  # noqa: E402
from metalesionlab.plato import downscale  # noqa: E402
from metalesionlab.plato_crowd import (AGES, BUDGET_USD, CROWD_DIR, DRAW_ORDER, IMAGE_USD, MAX_ATTEMPTS,  # noqa: E402
                                       PILOT, SHARED_STOP, file_name, folder, label, prompt_for)

SPEND_LOG = CROWD_DIR / "spend.jsonl"
CALL_LOG = CROWD_DIR / "calls.jsonl"
_lock = threading.RLock()  # re-entrant: the budget check and its reservation happen under one hold


def my_spend() -> float:
    if not SPEND_LOG.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in SPEND_LOG.read_text().splitlines() if line.strip())


def append(path: Path, **entry) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, path.open("a") as f:
        f.write(json.dumps({"ts": round(time.time(), 1), **entry}) + "\n")


def refusal(e: Exception) -> dict | None:
    """The API's refusal as {status, code, message}, or None for errors that aren't refusals."""
    if isinstance(e, openai.APIStatusError) and 400 <= e.status_code < 500 and e.status_code not in (408, 429):
        body = e.body if isinstance(e.body, dict) else {}
        err = body.get("error", body) if isinstance(body, dict) else {}
        return {"status": e.status_code, "code": (err or {}).get("code"), "message": str((err or {}).get("message") or e)[:300]}
    return None


def run_call(api: MetaAPI, key: str, i: int, age: int, out: Path, tag: str) -> tuple[str, int, int]:
    """One Muse Image call of n = 1, saved as out."""
    prompt = prompt_for(key, age)
    images: list[bytes] = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        with _lock:
            if my_spend() + IMAGE_USD > BUDGET_USD + 1e-9:
                raise RuntimeError(f"task budget ${BUDGET_USD:.2f} reached (counted at ${IMAGE_USD}/picture)")
            if spent() >= SHARED_STOP:
                raise RuntimeError(f"shared ledger reached ${SHARED_STOP:.2f}; stopping all paid calls")
            append(SPEND_LOG, kind="reserve", usd=IMAGE_USD, key=key, i=i, age=age, attempt=attempt, run=tag)
        net_tries = 0
        while True:
            try:
                images = api.generate_images(prompt, n=1)
                err = None
                break
            except APITimeoutError:
                # the server may still have drawn (and billed) it: keep the reservation, don't retry now
                append(CALL_LOG, key=key, i=i, age=age, attempt=attempt, got=0, outcome="timeout", run=tag)
                print(f"  {key} age {age}: timed out; reservation kept", flush=True)
                return key, age, 0
            except Exception as e:  # noqa: BLE001
                err = refusal(e)
                if err:
                    break
                net_tries += 1
                print(f"  {key} age {age} network try {net_tries} failed: {type(e).__name__}: {e}", flush=True)
                if net_tries >= 6:
                    err = {"status": None, "code": type(e).__name__, "message": str(e)[:300], "network": True}
                    break
                time.sleep(min(15 * 2 ** (net_tries - 1), 300))
        if err is None:
            append(CALL_LOG, key=key, i=i, age=age, attempt=attempt, got=len(images), prompt=prompt,
                   outcome="ok" if images else "short", run=tag)
            if not images:
                append(SPEND_LOG, kind="refund", usd=-IMAGE_USD, key=key, i=i, age=age, run=tag)
            break
        # nothing came back: refund this attempt's reservation (the ledger books only pictures it got)
        append(SPEND_LOG, kind="refund", usd=-IMAGE_USD, key=key, i=i, age=age, attempt=attempt, run=tag)
        outcome = "network_error" if err.get("network") else "refused"
        append(CALL_LOG, key=key, i=i, age=age, attempt=attempt, got=0, outcome=outcome, error=err, run=tag)
        print(f"  {key} age {age} attempt {attempt}: {outcome}: {err}", flush=True)
        if err.get("network"):
            break
    if images:
        out.parent.mkdir(parents=True, exist_ok=True)
        downscale(images[0], 512).save(out)
    return key, age, len(images)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", nargs="*", help="concepts to draw (default: all, in DRAW_ORDER)")
    ap.add_argument("--pilot", action="store_true", help="the 2 pilot pictures, into pilot/ (not analysed)")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    print(f"shared ledger {LEDGER}: ${spent():.2f}; this task so far ${my_spend():.3f} of ${BUDGET_USD:.2f}", flush=True)
    api = MetaAPI()
    api.client = api.client.with_options(timeout=400, max_retries=0)  # fail fast; we retry ourselves

    if args.pilot:
        for key, age in PILOT:
            out = CROWD_DIR / "pilot" / key / file_name(0, age)
            if out.exists():
                print(f"pilot {key} age {age}: already drawn", flush=True)
                continue
            got = run_call(api, key, 0, age, out, "pilot")
            print(f"pilot {key} age {age}: {got[2]} picture; prompt: {prompt_for(key, age)}", flush=True)
        print(f"done; this task ${my_spend():.3f}; shared ledger ${spent():.2f}", flush=True)
        return

    keys = args.keys or list(DRAW_ORDER)
    jobs = []
    for key in keys:
        out = folder(key)
        out.mkdir(parents=True, exist_ok=True)
        (out / "meta.json").write_text(json.dumps({
            "concept": label(key), "key": key, "style": "doodle, age persona", "model": IMAGE_MODEL, "batch": 1,
            "ages": list(AGES), "n_target": len(AGES),
            "prompts": {file_name(i, a): prompt_for(key, a) for i, a in enumerate(AGES)}}, indent=1))
        jobs += [(key, i, a) for i, a in enumerate(AGES) if not (out / file_name(i, a)).exists()]
    print(f"{len(jobs)} calls of n = 1, ${len(jobs) * IMAGE_USD:.2f} at ${IMAGE_USD}/picture "
          f"(the ledger books ${len(jobs) * 0.01:.2f})", flush=True)
    if my_spend() + len(jobs) * IMAGE_USD > BUDGET_USD + 1e-9:
        print(f"WARNING: that would pass the ${BUDGET_USD:.2f} cap; calls stop when it is reached", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(run_call, api, key, i, a, folder(key) / file_name(i, a), "main") for key, i, a in jobs]
        for k, fut in enumerate(as_completed(futures), 1):
            try:
                key, age, got = fut.result()
                print(f"[{k}/{len(jobs)}] {key} age {age}: {got} picture ({time.time() - t0:.0f}s)", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{k}/{len(jobs)}] FAILED: {e}", flush=True)
    for key in keys:
        out = folder(key)
        meta = json.loads((out / "meta.json").read_text())
        meta.update(n=len(list(out.glob("p*_age*.png"))))
        (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"done in {time.time() - t0:.0f}s; this task ${my_spend():.3f}; shared ledger ${spent():.2f}", flush=True)


if __name__ == "__main__":
    main()

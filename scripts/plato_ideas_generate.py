"""The invisible Forms, step 1: Muse Image doodles each abstract idea 16 times (4 calls of n = 4).

Usage:
  python scripts/plato_ideas_generate.py [--keys god love ...] [--workers 3]
  python scripts/plato_ideas_generate.py --pilot god justice      one picture each, into pilot/ (not analysed)
  python scripts/plato_ideas_generate.py --words                  the four words beyond nouns (running, thinking,
                                                                  something fast, something heavy), same settings,
                                                                  run tag "words", their own cap WORDS_BUDGET_USD

The prompt is the concrete things' doodle prompt, word for word (plato.STYLES["doodle"], plato_ideas.prompt_for),
and the settings are the first run's: separate calls of n = 4, no seed (none exists), pictures downscaled to
512 px and saved as $PLATO_IDEAS_DIR/ai/doodle/<key>/c<call>_<i>.png with a meta.json. Resumable.

Refusals are data. A call the API refuses (HTTP 400 content_policy_violation, or any other 4xx) is recorded
in calls.jsonl and tried again, at most MAX_ATTEMPTS times in all; network errors are retried with backoff
and are not refusals. A call that returns fewer pictures than asked is recorded too.

Spend: every call goes through MetaAPI, so the shared ledger (MLL_LEDGER; set it to the main repository's
runs/costs.jsonl when running from a worktree) books it. This task's own cap is counted separately at
IMAGE_USD a picture in spend.jsonl, reserved before each call and refunded for pictures that never came
back; no call is made past BUDGET_USD, or once the shared ledger reaches SHARED_STOP.
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
from metalesionlab.plato_ideas import (ANY as BY_KEY, BATCH, BUDGET_USD, IDEAS, IDEAS_DIR, IMAGE_USD,  # noqa: E402
                                       MAX_ATTEMPTS, N_AI, SHARED_STOP, WORDS, WORDS_BUDGET_USD, folder, prompt_for)

SPEND_LOG = IDEAS_DIR / "spend.jsonl"
CALL_LOG = IDEAS_DIR / "calls.jsonl"
_lock = threading.RLock()  # re-entrant: the budget check and its reservation happen under one hold
# The ideas' task counted every entry against BUDGET_USD; the words' task counts only its own run against its cap.
CAP = {"main": BUDGET_USD, "pilot": BUDGET_USD, "words": WORDS_BUDGET_USD}


def my_spend(run: str | None = None) -> float:
    """This task's spend at IMAGE_USD a picture: every entry for the ideas' runs, only its own for the words."""
    if not SPEND_LOG.exists():
        return 0.0
    rows = [json.loads(line) for line in SPEND_LOG.read_text().splitlines() if line.strip()]
    if run == "words":
        rows = [r for r in rows if r.get("run") == "words"]
    elif run is not None:
        rows = [r for r in rows if r.get("run") != "words"]
    return sum(r["usd"] for r in rows)


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


def run_call(api: MetaAPI, key: str, call: int, n: int, out_dir: Path, tag: str) -> tuple[str, int, int]:
    """One Muse Image call for n pictures, saved as c<call>_<i>.png in out_dir."""
    prompt = prompt_for(BY_KEY[key])
    images: list[bytes] = []
    refused = 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        with _lock:
            cap = CAP[tag]
            if my_spend(tag) + n * IMAGE_USD > cap + 1e-9:
                raise RuntimeError(f"task budget ${cap:.2f} reached (counted at ${IMAGE_USD}/picture)")
            if spent() >= SHARED_STOP:
                raise RuntimeError(f"shared ledger reached ${SHARED_STOP:.2f}; stopping all paid calls")
            append(SPEND_LOG, kind="reserve", usd=n * IMAGE_USD, key=key, call=call, attempt=attempt, n=n, run=tag)
        net_tries = 0
        while True:
            try:
                images = api.generate_images(prompt, n=n)
                err = None
                break
            except APITimeoutError:
                # the server may still have drawn (and billed) these: keep the reservation, don't retry
                append(CALL_LOG, key=key, call=call, attempt=attempt, n=n, got=0, outcome="timeout", run=tag)
                print(f"  {key} call {call}: timed out; reservation kept", flush=True)
                return key, call, 0
            except Exception as e:  # noqa: BLE001
                err = refusal(e)
                if err:
                    break
                net_tries += 1
                print(f"  {key} call {call} network try {net_tries} failed: {type(e).__name__}: {e}", flush=True)
                if net_tries >= 6:
                    err = {"status": None, "code": type(e).__name__, "message": str(e)[:300], "network": True}
                    break
                time.sleep(min(15 * 2 ** (net_tries - 1), 300))
        if err is None:
            append(CALL_LOG, key=key, call=call, attempt=attempt, n=n, got=len(images),
                   outcome="ok" if len(images) == n else "short", run=tag)
            if len(images) < n:
                append(SPEND_LOG, kind="refund", usd=-(n - len(images)) * IMAGE_USD, key=key, call=call, run=tag)
            break
        # nothing came back: refund this attempt's reservation (the ledger books only pictures it got)
        append(SPEND_LOG, kind="refund", usd=-n * IMAGE_USD, key=key, call=call, attempt=attempt, run=tag)
        outcome = "network_error" if err.get("network") else "refused"
        append(CALL_LOG, key=key, call=call, attempt=attempt, n=n, got=0, outcome=outcome, error=err, run=tag)
        print(f"  {key} call {call} attempt {attempt}: {outcome}: {err}", flush=True)
        if outcome == "refused":
            refused += 1
        if err.get("network"):
            break
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, png in enumerate(images):
        downscale(png, 512).save(out_dir / f"c{call}_{i}.png")
    return key, call, len(images)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", nargs="*", help="ideas to draw (default: all, in order)")
    ap.add_argument("--pilot", nargs="*", help="one picture of each named idea, into pilot/ (not analysed)")
    ap.add_argument("--words", action="store_true", help="the four words beyond nouns, run tag 'words'")
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    tag = "words" if args.words else "main"
    print(f"shared ledger {LEDGER}: ${spent():.2f}; this task so far ${my_spend(tag):.3f} of ${CAP[tag]:.2f}", flush=True)
    api = MetaAPI()
    api.client = api.client.with_options(timeout=400, max_retries=0)  # fail fast; we retry ourselves

    if args.pilot:
        for key in args.pilot:
            got = run_call(api, key, 0, 1, IDEAS_DIR / "pilot" / key, "pilot")
            print(f"pilot {key}: {got[2]} picture", flush=True)
        print(f"done; this task ${my_spend('pilot'):.3f}; shared ledger ${spent():.2f}", flush=True)
        return

    keys = args.keys or [i.key for i in (WORDS if args.words else IDEAS)]
    jobs = []
    for key in keys:
        idea, out = BY_KEY[key], folder(key)
        out.mkdir(parents=True, exist_ok=True)
        done = {int(p.stem.split("_")[0][1:]) for p in out.glob("c*_*.png")}
        (out / "meta.json").write_text(json.dumps({"idea": idea.label, "key": key, "style": "doodle",
                                                   "prompt": prompt_for(idea), "model": IMAGE_MODEL, "batch": BATCH,
                                                   "n_target": N_AI}, indent=1))
        jobs += [(key, call) for call in range(N_AI // BATCH) if call not in done]
    n_img = len(jobs) * BATCH
    print(f"{len(jobs)} calls, {n_img} pictures, ${n_img * IMAGE_USD:.2f} at ${IMAGE_USD}/picture "
          f"(the ledger books ${n_img * 0.01:.2f})", flush=True)
    if my_spend(tag) + n_img * IMAGE_USD > CAP[tag] + 1e-9:
        print(f"WARNING: that would pass the ${CAP[tag]:.2f} cap; calls stop when it is reached", flush=True)
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(run_call, api, key, call, BATCH, folder(key), tag) for key, call in jobs]
        for k, fut in enumerate(as_completed(futures), 1):
            try:
                key, call, got = fut.result()
                print(f"[{k}/{len(jobs)}] {key} call {call}: {got} pictures ({time.time() - t0:.0f}s)", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{k}/{len(jobs)}] FAILED: {e}", flush=True)
    for key in keys:
        out = folder(key)
        meta = json.loads((out / "meta.json").read_text())
        meta.update(n=len(list(out.glob("c*_*.png"))))
        (out / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"done in {time.time() - t0:.0f}s; this task ${my_spend(tag):.3f}; shared ledger ${spent():.2f}", flush=True)


if __name__ == "__main__":
    main()

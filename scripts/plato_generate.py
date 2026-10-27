"""Plato's Chair, step 1: ask Muse Image to draw every concept 16 (tier 1) or 12 (tier 2) times.

Usage: python scripts/plato_generate.py [--style doodle|photo|doodle_any|doodle_unusual|doodle_listed]
       [--keys chair sailboat ...] [--per-concept N] [--batch 4] [--workers 3] [--budget 9.0] [--shared-stop 40]

Concepts are drawn in priority order (tier 1 first), so the key comparisons exist even if we stop
early. Each concept gets n/batch separate calls (no seed parameter exists, so separate calls are
the natural variability). Pictures are downscaled to 512 px and saved as
$PLATO_DIR/ai/<style>/<key>/c<call>_<i>.png (outside the repo). Resumable: existing pictures are kept.
A concept's meta.json says "complete": true as soon as it has all its pictures.

Variety styles ("can you prompt it out of the Platonic chair?", plato.VARIETY_STYLES):
- doodle_any: the doodle prompt with "a chair (any kind of chair)"; all 35 concepts.
- doodle_unusual: "... (any kind of chair at all; pick an unusual or different kind)"; tier 1 only.
- doodle_listed: Muse Spark lists n_ai clearly different kinds (kinds.json, one chat call per concept),
  then Muse Image draws each kind once with the doodle prompt: p<i>.png shows kinds[i].
They reserve their spend in their own file (spend_variety.jsonl, default budget $12).

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

from metalesionlab.meta_api import (CHAT_MODEL, IMAGE_MODEL, IMAGE_PRICE, LEDGER, MetaAPI, spent,  # noqa: E402
                                    token_cost)
from metalesionlab.plato import (BY_KEY, CONCEPTS, PHOTO_KEYS, PLATO_DIR, STYLES, TIER1, downscale,  # noqa: E402
                                 listing_prompt, parse_kinds, prompt_for)

OUT = PLATO_DIR
SPEND_LOG = OUT / "spend.jsonl"
VARIETY_SPEND_LOG = OUT / "spend_variety.jsonl"
_lock = threading.Lock()


def my_spend() -> float:
    if not SPEND_LOG.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in SPEND_LOG.read_text().splitlines() if line.strip())


def log_spend(**entry) -> None:
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SPEND_LOG.open("a") as f:
        f.write(json.dumps({"ts": round(time.time(), 1), **entry}) + "\n")


def with_retries(fn, what: str, attempts: int = 6):
    """Retry connection errors, rate limits and server errors: 15 s, 30 s, ... 4 min (rides out a DNS outage)."""
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            print(f"  {what} attempt {attempt + 1} failed: {type(e).__name__}: {e}", flush=True)
            if attempt == attempts - 1:
                raise
            time.sleep(15 * 2 ** attempt)


def pictures_in(folder: Path, style: str) -> list[Path]:
    return list(folder.glob("p*.png" if style == "doodle_listed" else "c*_*.png"))


def run_call(api: MetaAPI, style: str, key: str, call: int, prompt: str, names: list[str], budget: float,
             shared_stop: float, per_concept: int) -> tuple[str, int, int]:
    """One Muse Image call for len(names) pictures, saved under those file names."""
    n = len(names)
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
    for name, png in zip(names, images):
        downscale(png, 512).save(folder / name)
    # mark the concept complete as soon as it has all its pictures, so other analyses can start on it
    with _lock:
        have = len(pictures_in(folder, style))
        meta = json.loads((folder / "meta.json").read_text())
        meta.update(n=have, complete=have >= per_concept)
        (folder / "meta.json").write_text(json.dumps(meta, indent=1))
    return key, call, len(images)


def ensure_kinds(api: MetaAPI, key: str, n: int, budget: float, shared_stop: float) -> list[str]:
    """Muse Spark's n kinds of the concept (kinds.json); one chat call, logged at its real cost."""
    folder = OUT / "ai" / "doodle_listed" / key
    path = folder / "kinds.json"
    if path.exists():
        kinds = json.loads(path.read_text())
        if len(kinds) >= n:
            return kinds[:n]
    with _lock:
        if my_spend() + 0.02 > budget or spent() > shared_stop:
            raise RuntimeError("budget reached before listing kinds")
    prompt = listing_prompt(BY_KEY[key], n)
    for _ in range(3):
        resp = with_retries(lambda: api.chat([{"role": "user", "content": prompt}], reasoning_effort="low"),
                            f"{key} kinds")
        log_spend(kind="chat", usd=token_cost(CHAT_MODEL, resp.usage), style="doodle_listed", key=key)
        kinds = parse_kinds(resp.choices[0].message.content or "", n)
        if len(kinds) == n:
            break
        print(f"  {key}: Spark listed {len(kinds)} of {n} kinds; asking again", flush=True)
    else:
        raise RuntimeError(f"{key}: Spark did not list {n} kinds")
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kinds, indent=1))
    (folder / "kinds_prompt.json").write_text(json.dumps({"model": CHAT_MODEL, "reasoning_effort": "low",
                                                          "prompt": prompt}, indent=1))
    return kinds


def main():
    global SPEND_LOG
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="doodle", choices=[*STYLES, "doodle_any", "doodle_unusual", "doodle_listed"])
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--per-concept", type=int, help="override each concept's n_ai (16 tier 1, 12 tier 2)")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--workers", type=int, default=3)  # 8 parallel calls hung for 10+ min; 2 took 108 s
    ap.add_argument("--budget", type=float, help="this experiment's cap (default $9; variety styles $12)")
    ap.add_argument("--shared-stop", type=float, default=40.0)
    ap.add_argument("--kinds-only", action="store_true", help="doodle_listed: only ask Spark for the kind lists")
    args = ap.parse_args()
    variety = args.style.startswith("doodle_")
    if variety:
        SPEND_LOG = VARIETY_SPEND_LOG
    budget = args.budget if args.budget is not None else (12.0 if variety else 9.0)

    all_keys = [c.key for c in CONCEPTS]
    default_keys = {"doodle": all_keys, "doodle_any": all_keys, "doodle_listed": all_keys,
                    "doodle_unusual": [k.replace(" ", "_") for k in TIER1]}
    keys = args.keys or default_keys.get(args.style, PHOTO_KEYS)
    print(f"shared ledger {LEDGER}: ${spent():.2f}", flush=True)
    api = MetaAPI()
    # fail fast instead of the client's silent 10-minute timeouts and retries
    api.client = api.client.with_options(timeout=400, max_retries=0)
    jobs = []  # (key, call, prompt, file names, per-concept target)
    for key in keys:
        c = BY_KEY[key]
        per = args.per_concept or c.n_ai
        folder = OUT / "ai" / args.style / key
        folder.mkdir(parents=True, exist_ok=True)
        have = len(pictures_in(folder, args.style))
        meta = {"concept": c.label, "quickdraw": c.quickdraw, "style": args.style, "model": IMAGE_MODEL,
                "n": have, "n_target": per, "complete": have >= per}
        if args.style == "doodle_listed":
            kinds = ensure_kinds(api, key, per, budget, args.shared_stop)
            print(f"  {key}: {'; '.join(kinds)}", flush=True)
            prompts = [STYLES["doodle"].format(phrase=k) for k in kinds]
            meta.update(batch=1, kinds=kinds, prompts={f"p{i}.png": p for i, p in enumerate(prompts)})
            jobs += [(key, i, p, [f"p{i}.png"], per) for i, p in enumerate(prompts)
                     if not (folder / f"p{i}.png").exists()]
        else:
            meta.update(prompt=prompt_for(c, args.style), batch=args.batch)
            calls_done = {int(p.stem.split("_")[0][1:]) for p in folder.glob("c*_*.png")}
            need, call = per - have, 0
            while need > 0:
                if call not in calls_done:
                    k = min(args.batch, need)
                    jobs.append((key, call, prompt_for(c, args.style), [f"c{call}_{i}.png" for i in range(k)], per))
                    need -= k
                call += 1
        (folder / "meta.json").write_text(json.dumps(meta, indent=1))
    n_img = sum(len(j[3]) for j in jobs)
    print(f"{len(jobs)} calls, {n_img} images, ${n_img * IMAGE_PRICE:.2f}; "
          f"experiment spend so far ${my_spend():.2f} of ${budget:.2f} ({SPEND_LOG.name})", flush=True)
    if not jobs or args.kinds_only:
        return
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(run_call, api, args.style, key, call, prompt, names, budget, args.shared_stop, per)
                   for key, call, prompt, names, per in jobs]
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

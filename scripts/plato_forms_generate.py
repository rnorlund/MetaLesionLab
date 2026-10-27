"""Plato's Forms: Muse Image pictures for the Platonic clock and for the bed and table (docs/plato_forms_plan.md).

  clock [--styles doodle photo] [--dry-run]
      Clocks with no time ("any", 16) and with each requested time (8 per time; photos: the 6 PHOTO_TIMES),
      in $PLATO_FORMS_DIR/clock/muse/<style>/<any|t0120...>/c<call>_<i>.png. The no-time doodle prompt is the
      core prompt, so the core's 12 clock doodles are copied in (c0-c2) and only 4 more are drawn.
  concepts [--keys bed table] [--styles doodle doodle_any doodle_listed] [--dry-run]
      Bed and table under the core pipeline's prompts, in $PLATO_FORMS_DIR/ai/<style>/<key>/ (the core layout):
      usual doodle and "any kind" as c<call>_<i>.png, named kinds as p<i>.png with Muse Spark's list in kinds.json.

Separate calls of n=4, as in the core run (no seed parameter exists). Pictures are downscaled to 512 px.
Resumable: existing pictures are kept. Each call's cost is reserved in $PLATO_FORMS_DIR/spend.jsonl before
it is made; calls stop at the experiment's $5 budget or once the shared ledger passes $70. Connection
errors (DNS drops) are retried with backoff; a timeout keeps its reservation and is not retried, since the
server may have drawn and billed the pictures.
"""
import argparse
import json
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import APITimeoutError  # noqa: E402

from metalesionlab.meta_api import CHAT_MODEL, IMAGE_MODEL, IMAGE_PRICE, LEDGER, MetaAPI, retry_network, spent, token_cost  # noqa: E402
from metalesionlab.plato import PLATO_DIR, STYLES, downscale, listing_prompt, parse_kinds, prompt_for  # noqa: E402
from metalesionlab.plato_forms import (BUDGET, CLOCK_TIMES, FORMS_BY_KEY, FORMS_DIR, PER_DEFAULT, PER_TIME,  # noqa: E402
                                       PHOTO_TIMES, SHARED_STOP, clock_prompt, log_spend, my_spend, slug)

_lock = threading.Lock()


class _TimedOut(Exception):
    pass


def plan_calls(folder: Path, prompt: str, n: int, batch: int = 4) -> list[tuple[str, list[str], Path]]:
    """(prompt, file names, folder) for the calls still needed to have n pictures c<call>_<i>.png."""
    have = len(list(folder.glob("c*_*.png")))
    calls_done = {int(p.stem.split("_")[0][1:]) for p in folder.glob("c*_*.png")}
    jobs, need, call = [], n - have, 0
    while need > 0:
        if call not in calls_done:
            k = min(batch, need)
            jobs.append((prompt, [f"c{call}_{i}.png" for i in range(k)], folder))
            need -= k
        call += 1
    return jobs


def write_meta(folder: Path, **meta) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "meta.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    have = len(list(folder.glob("*.png")))
    old.update(meta, model=IMAGE_MODEL, n=have, complete=have >= meta.get("n_target", 0))
    path.write_text(json.dumps(old, indent=1))


def run_call(api: MetaAPI, prompt: str, names: list[str], folder: Path) -> int:
    n = len(names)
    with _lock:
        if my_spend() + n * IMAGE_PRICE > BUDGET + 1e-9:
            raise RuntimeError(f"experiment budget ${BUDGET:.2f} reached")
        if spent() > SHARED_STOP:
            raise RuntimeError(f"shared ledger passed ${SHARED_STOP:.0f}; stopping")
        log_spend(kind="reserve", usd=n * IMAGE_PRICE, folder=str(folder.relative_to(FORMS_DIR)), n=n)
    def once():
        try:
            return api.generate_images(prompt, n=n)
        except APITimeoutError as e:  # a timeout subclasses the connection errors retry_network retries
            raise _TimedOut() from e

    try:
        images = retry_network(once, tries=7, base=15, cap=240)
    except _TimedOut:
        print(f"  {folder.name}: timed out; reservation kept", flush=True)
        return 0
    except Exception as e:  # noqa: BLE001
        log_spend(kind="refund", usd=-n * IMAGE_PRICE, folder=str(folder.relative_to(FORMS_DIR)))
        raise RuntimeError(f"{folder.name}: {type(e).__name__}: {e}") from e
    if len(images) < n:
        log_spend(kind="refund", usd=-(n - len(images)) * IMAGE_PRICE, folder=str(folder.relative_to(FORMS_DIR)))
    folder.mkdir(parents=True, exist_ok=True)
    for name, png in zip(names, images):
        downscale(png, 512).save(folder / name)
    return len(images)


def clock_jobs(styles: list[str]) -> list:
    jobs = []
    for style in styles:
        conds = [(None, PER_DEFAULT)] + [(t, PER_TIME) for t in (CLOCK_TIMES if style == "doodle" else PHOTO_TIMES)]
        for t, n in conds:
            folder = FORMS_DIR / "clock" / "muse" / style / slug(t)
            folder.mkdir(parents=True, exist_ok=True)
            if style == "doodle" and t is None:  # the core's 12 clocks, drawn with this exact prompt
                core = PLATO_DIR / "ai" / "doodle" / "clock"
                assert json.loads((core / "meta.json").read_text())["prompt"] == clock_prompt("doodle")
                for f in sorted(core.glob("c*_*.png")):
                    if not (folder / f.name).exists():
                        shutil.copy2(f, folder / f.name)
            write_meta(folder, style=style, time=t, prompt=clock_prompt(style, t), batch=4, n_target=n,
                       **({"reused": "c0-c2 copied from core ai/doodle/clock"} if style == "doodle" and t is None else {}))
            jobs += plan_calls(folder, clock_prompt(style, t), n)
    return jobs


def ensure_kinds(api: MetaAPI, key: str, n: int) -> list[str]:
    folder = FORMS_DIR / "ai" / "doodle_listed" / key
    path = folder / "kinds.json"
    if path.exists():
        return json.loads(path.read_text())[:n]
    if my_spend() + 0.02 > BUDGET or spent() > SHARED_STOP:
        raise RuntimeError("budget reached before listing kinds")
    prompt = listing_prompt(FORMS_BY_KEY[key], n)
    for _ in range(3):
        resp = retry_network(lambda: api.chat([{"role": "user", "content": prompt}], reasoning_effort="low"),
                             tries=7, base=15, cap=240)
        log_spend(kind="chat", usd=token_cost(CHAT_MODEL, resp.usage), what=f"kinds {key}")
        kinds = parse_kinds(resp.choices[0].message.content or "", n)
        if len(kinds) == n:
            break
        print(f"  {key}: Spark listed {len(kinds)} of {n}; asking again", flush=True)
    else:
        raise RuntimeError(f"{key}: Spark did not list {n} kinds")
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(kinds, indent=1))
    (folder / "kinds_prompt.json").write_text(json.dumps({"model": CHAT_MODEL, "reasoning_effort": "low",
                                                          "prompt": prompt}, indent=1))
    return kinds


def concept_jobs(api: MetaAPI, keys: list[str], styles: list[str], dry_run: bool) -> list:
    jobs = []
    for key in keys:
        c = FORMS_BY_KEY[key]
        for style in styles:
            folder = FORMS_DIR / "ai" / style / key
            if style == "doodle_listed":
                if dry_run and not (folder / "kinds.json").exists():
                    jobs += [(None, [f"p{i}.png"], folder) for i in range(c.n_ai)]
                    continue
                kinds = ensure_kinds(api, key, c.n_ai)
                print(f"  {key}: {'; '.join(kinds)}", flush=True)
                prompts = [STYLES["doodle"].format(phrase=k) for k in kinds]
                write_meta(folder, concept=c.label, quickdraw=c.quickdraw, style=style, batch=1, kinds=kinds,
                           prompts={f"p{i}.png": p for i, p in enumerate(prompts)}, n_target=c.n_ai)
                jobs += [(p, [f"p{i}.png"], folder) for i, p in enumerate(prompts) if not (folder / f"p{i}.png").exists()]
            else:
                write_meta(folder, concept=c.label, quickdraw=c.quickdraw, style=style, prompt=prompt_for(c, style),
                           batch=4, n_target=c.n_ai)
                jobs += plan_calls(folder, prompt_for(c, style), c.n_ai)
    return jobs


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("clock")
    p.add_argument("--styles", nargs="*", default=["doodle", "photo"], choices=["doodle", "photo"])
    p = sub.add_parser("concepts")
    p.add_argument("--keys", nargs="*", default=list(FORMS_BY_KEY), choices=list(FORMS_BY_KEY))
    p.add_argument("--styles", nargs="*", default=["doodle", "doodle_any", "doodle_listed"],
                   choices=["doodle", "doodle_any", "doodle_listed"])
    for p in sub.choices.values():
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    api = MetaAPI()
    api.client = api.client.with_options(timeout=400, max_retries=0)
    print(f"shared ledger {LEDGER}: ${spent():.2f}; this experiment ${my_spend():.2f} of ${BUDGET:.2f}", flush=True)
    jobs = clock_jobs(args.styles) if args.cmd == "clock" else concept_jobs(api, args.keys, args.styles, args.dry_run)
    n_img = sum(len(j[1]) for j in jobs)
    print(f"{len(jobs)} calls, {n_img} pictures, ${n_img * IMAGE_PRICE:.2f}", flush=True)
    if args.dry_run or not jobs:
        return
    if my_spend() + n_img * IMAGE_PRICE > BUDGET:
        sys.exit(f"would pass the ${BUDGET:.2f} budget; not starting")
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(run_call, api, prompt, names, folder): folder for prompt, names, folder in jobs}
        for i, fut in enumerate(as_completed(futs), 1):
            folder = futs[fut]
            try:
                got = fut.result()
                print(f"[{i}/{len(jobs)}] {folder.relative_to(FORMS_DIR)}: {got} ({time.time() - t0:.0f}s)", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{i}/{len(jobs)}] FAILED {folder.relative_to(FORMS_DIR)}: {e}", flush=True)
    for folder in {f for _, _, f in jobs}:
        write_meta(folder, n_target=json.loads((folder / "meta.json").read_text()).get("n_target", 0))
    print(f"done in {time.time() - t0:.0f}s; experiment ${my_spend():.2f}; shared ledger ${spent():.2f}", flush=True)


if __name__ == "__main__":
    main()

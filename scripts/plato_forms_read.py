"""Plato's Forms, the Platonic clock: Muse Spark (vision) reads the time on every clock.

  validate --prompt v1|v2 [--effort low]   draw the 28 validation clocks (24 known times, 4 without hands;
                                           plato_forms.validation_set) and read them; prints the accuracy
  read --prompt v2 [--effort low] [--sources muse_doodle ...]
                                           read every study picture that this reader hasn't read yet

Each answer is parsed with plato_forms.parse_reading. Readings are appended to
$PLATO_FORMS_DIR/clock/readings/<reader>.jsonl (validation: validation_<reader>.jsonl), one line per
picture with the raw answer, so a run is resumable and the analysis never calls the API.
Costs money: every call is logged at its real cost in $PLATO_FORMS_DIR/spend.jsonl; calls stop at this
experiment's budget (plato_forms.BUDGET, $5 including the pictures) or when the shared ledger (MLL_LEDGER)
passes plato_forms.SHARED_STOP ($70). DNS drops and rate limits are retried with backoff.
"""
import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.meta_api import CHAT_MODEL, MetaAPI, image_data_url, retry_network, spent, token_cost  # noqa: E402
from metalesionlab.plato import PLATO_DIR, load_dir  # noqa: E402
from metalesionlab.plato_forms import (BUDGET, FORMS_DIR, READER_PROMPTS, SHARED_STOP, draw_test_clock,  # noqa: E402
                                       fmt_time, log_spend, my_spend, parse_reading, parse_time, time_distance,
                                       is_ten_ten, validation_set)

CLOCK = FORMS_DIR / "clock"
# source -> folder; generator folders hold one subfolder per condition (any, t0120, ...)
SOURCES = {"muse_doodle": CLOCK / "muse" / "doodle", "muse_photo": CLOCK / "muse" / "photo",
           "sdxl_doodle": CLOCK / "sdxl" / "doodle", "sdxl_photo": CLOCK / "sdxl" / "photo",
           "people": PLATO_DIR / "human" / "clock"}  # the 200 cached Quick, Draw! clocks (read-only)
EST_READ = 0.004  # generous per-read reservation; the real cost is logged after the call
_lock = threading.Lock()
STOP_AT = BUDGET  # --stop-at lowers it


def reader_id(prompt: str, effort: str) -> str:
    return f"spark-{prompt}-{effort}"


def done_files(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(x)["path"] for x in path.read_text().splitlines() if x.strip()}


def read_one(api: MetaAPI, img_path: Path, prompt: str, effort: str) -> tuple[str, float]:
    msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_data_url(img_path.read_bytes())}},
                                        {"type": "text", "text": READER_PROMPTS[prompt]}]}]
    with _lock:
        if my_spend() + EST_READ > min(BUDGET, STOP_AT):
            raise RuntimeError(f"experiment budget ${BUDGET:.2f} reached")
        if spent() > SHARED_STOP:
            raise RuntimeError(f"shared ledger passed ${SHARED_STOP:.0f}; stopping")
    resp = retry_network(lambda: api.chat(msg, reasoning_effort=effort), tries=8, base=10, cap=240)
    usd = token_cost(CHAT_MODEL, resp.usage)
    log_spend(kind="read", usd=usd, file=img_path.name)
    return (resp.choices[0].message.content or "").strip(), usd


def run(api, jobs: list[tuple[dict, Path]], out: Path, prompt: str, effort: str, workers: int) -> None:
    """jobs: (record fields, image path). Appends one JSON line per reading to out."""
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def work(rec, path):
        text, usd = read_one(api, path, prompt, effort)
        p = parse_reading(text)
        row = {**rec, "reader": reader_id(prompt, effort), "model": CHAT_MODEL, "answer": text[:400], "usd": round(usd, 6),
               "status": p["status"], "hands": p["hands"], "time": fmt_time(p["time"]),
               "time_said": fmt_time(p["time_said"]), "from_hands": fmt_time(p["from_hands"])}
        with _lock, out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        return row

    with ThreadPoolExecutor(workers) as pool:
        futs = [pool.submit(work, rec, path) for rec, path in jobs]
        for i, fut in enumerate(as_completed(futs), 1):
            try:
                row = fut.result()
                if i % 20 == 0 or i == len(futs):
                    print(f"[{i}/{len(futs)}] {row['path']} -> {row['status']} {row['time']} "
                          f"({time.time() - t0:.0f}s; experiment ${my_spend():.2f})", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[{i}/{len(futs)}] FAILED: {type(e).__name__}: {e}", flush=True)


def cmd_validate(args, api):
    folder = CLOCK / "validation"
    folder.mkdir(parents=True, exist_ok=True)
    vs = validation_set()
    for v in vs:
        p = folder / f"{v['id']}.png"
        if not p.exists():
            draw_test_clock(v["time"], v["style"], v["seed"]).save(p)
    (folder / "truth.json").write_text(json.dumps(vs, indent=1))
    out = CLOCK / "readings" / f"validation_{reader_id(args.prompt, args.effort)}.jsonl"
    have = done_files(out)
    jobs = [({"path": f"validation/{v['id']}.png", "id": v["id"]}, folder / f"{v['id']}.png") for v in vs
            if f"validation/{v['id']}.png" not in have]
    print(f"{len(jobs)} validation clocks to read with {reader_id(args.prompt, args.effort)}", flush=True)
    run(api, jobs, out, args.prompt, args.effort, args.workers)
    score_validation(vs, out)


def score_validation(vs: list[dict], out: Path) -> dict:
    rows = {json.loads(x)["id"]: json.loads(x) for x in out.read_text().splitlines() if x.strip()}
    timed = [v for v in vs if v["time"]]
    within5 = within5_either = hour_ok = 0
    false_1010 = [v["id"] for v in timed if is_ten_ten(parse_time(rows[v["id"]]["time"]))
                  and not is_ten_ten(parse_time(v["time"]))]
    for v in timed:
        r = parse_time(rows[v["id"]]["time"])
        t = parse_time(v["time"])
        if r is None:
            print(f"  {v['id']} {v['style']:8s} truth {v['time']:>5s} read NONE ({rows[v['id']]['status']})")
            continue
        d, de = time_distance(r, t), time_distance(r, t, either_order=True)
        within5 += d <= 5
        within5_either += de <= 5
        hour_ok += r[0] == t[0]
        flag = "" if d <= 5 else ("  swapped" if de <= 5 else "  WRONG")
        print(f"  {v['id']} {v['style']:8s} truth {v['time']:>5s} read {fmt_time(r):>5s}"
              f" (said {rows[v['id']]['time_said']}, hands {rows[v['id']]['from_hands']}){flag}")
    nohands = [v for v in vs if not v["time"]]
    nh_ok = sum(rows[v["id"]]["status"] == "no_hands" for v in nohands)
    res = {"n": len(timed), "within5": within5, "within5_either_order": within5_either, "hour_correct": hour_ok,
           "false_ten_ten": false_1010, "no_hands_correct": nh_ok, "n_no_hands": len(nohands),
           "usd": round(sum(r["usd"] for r in rows.values()), 4)}
    print(json.dumps(res))
    return res


def cmd_read(args, api):
    out = CLOCK / "readings" / f"{reader_id(args.prompt, args.effort)}.jsonl"
    have = done_files(out)
    jobs = []
    for source in args.sources:
        root = SOURCES[source]
        if source == "people":
            groups = [("default", root)]
        else:
            groups = [(d.name, d) for d in sorted(root.iterdir()) if d.is_dir()] if root.exists() else []
        for cond, folder in groups:
            if args.conds and cond not in args.conds:
                continue
            for f in load_dir(folder):
                rel = f"{source}/{cond}/{f.name}"
                if rel not in have:
                    jobs.append(({"path": rel, "source": source, "cond": cond, "file": f.name}, f))
    print(f"{len(jobs)} pictures to read; about ${len(jobs) * 0.0015:.2f}; experiment so far ${my_spend():.2f}; "
          f"shared ledger ${spent():.2f}", flush=True)
    if jobs and not args.dry_run:
        run(api, jobs, out, args.prompt, args.effort, args.workers)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "read"):
        p = sub.add_parser(name)
        p.add_argument("--prompt", default="v2", choices=list(READER_PROMPTS))
        p.add_argument("--effort", default="low", choices=["minimal", "low", "medium", "high"])
        p.add_argument("--workers", type=int, default=4)
        if name == "read":
            p.add_argument("--sources", nargs="*", default=list(SOURCES), choices=list(SOURCES))
            p.add_argument("--conds", nargs="*", help="only these condition folders (any, t0120, ...)")
            p.add_argument("--stop-at", type=float, help="stop starting new reads once this experiment's spend passes this")
            p.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    global STOP_AT
    if getattr(args, "stop_at", None):
        STOP_AT = args.stop_at
    api = MetaAPI()
    api.client = api.client.with_options(timeout=180, max_retries=0)
    (cmd_validate if args.cmd == "validate" else cmd_read)(args, api)


if __name__ == "__main__":
    main()

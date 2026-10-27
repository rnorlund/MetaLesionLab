"""Plato's Bird, paid steps (Muse Spark and Muse Image). Costs money: every call goes to the shared ledger
(set MLL_LEDGER) and to this experiment's own spend log, $PLATO_BIRD_DIR/spend.jsonl.

  text   [--n 50] [--categories ...] [--workers 6]   Muse Spark names one member, n separate calls per
                                                     category (default sampling, minimal reasoning);
                                                     spark_text/<category>.json, resumable
  pilot                                              1 call for each of 10 categories (counts toward n);
                                                     prints the cost per call and the pre-registered n
  temp   --temperature T [--n 20] [--categories ...] the same at another temperature (exploratory check);
                                                     spark_text_T<T>/<category>.json
  images [--per-call 4] [--calls 3]                  Muse Image doodles of the 12 picture categories;
                                                     pictures/<key>/p<i>.png (512 px)
  label                                              Muse Spark (vision) names the member each picture shows;
                                                     picture_labels_spark.json

Stops when this experiment's spend reaches --budget (default $5) or the shared ledger passes --shared-stop ($70).
"""
import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab import meta_api  # noqa: E402
from metalesionlab.meta_api import CHAT_MODEL, MetaAPI, image_data_url, retry_network, spent, token_cost  # noqa: E402
from metalesionlab.plato_bird import BIRD_DIR, PICTURE_CATEGORIES, picture_label_prompt, prompt_for  # noqa: E402

SPEND = BIRD_DIR / "spend.jsonl"
PILOT = ["bird", "fruit", "emotion", "crime", "tool", "colour", "religion", "weather", "fish", "statistical term"]
_lock = threading.Lock()


class Stop(Exception):
    pass


def mine() -> float:
    if not SPEND.exists():
        return 0.0
    return sum(json.loads(x)["usd"] for x in SPEND.read_text().splitlines() if x.strip())


def log_spend(usd: float, **extra):
    with _lock, SPEND.open("a") as f:
        f.write(json.dumps({"ts": round(time.time(), 1), "usd": round(usd, 6), **extra}) + "\n")


def guard(args, estimate: float = 0.0):
    if mine() + estimate > args.budget:
        raise Stop(f"experiment budget ${args.budget:.2f} reached (spent ${mine():.2f})")
    if spent() > args.shared_stop:
        raise Stop(f"shared ledger passed ${args.shared_stop:.0f}")


def categories(args) -> list[dict]:
    cats = json.loads((BIRD_DIR / "categories.json").read_text())
    if args.categories:
        cats = [c for c in cats if c["category"] in args.categories]
    return cats


def ask(api, args, category: str, temperature: float | None = None) -> dict:
    guard(args, 0.002)
    msg = [{"role": "user", "content": prompt_for(category)}]
    extra = {"temperature": temperature} if temperature is not None else {}
    resp = retry_network(lambda: api.chat(msg, reasoning_effort="minimal", **extra), base=5, tries=8)
    usd = token_cost(CHAT_MODEL, resp.usage)
    u = resp.usage.model_dump()
    log_spend(usd, kind="text", category=category, **({"temperature": temperature} if temperature else {}))
    return {"answer": (resp.choices[0].message.content or "").strip()[:200], "usd": round(usd, 6),
            "out_tokens": u.get("completion_tokens"),
            "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens")}


def run_text(args, cats: list[dict], n: int, folder: Path, temperature: float | None = None):
    folder.mkdir(parents=True, exist_ok=True)
    api = MetaAPI()
    api.client = api.client.with_options(timeout=60, max_retries=0)

    def one_category(c):
        path = folder / f"{c['category']}.json"
        with _lock:
            rec = json.loads(path.read_text()) if path.exists() else {
                "category": c["category"], "domain": c.get("domain"), "prompt": prompt_for(c["category"]),
                "model": CHAT_MODEL, "reasoning_effort": "minimal", "temperature": temperature, "samples": []}
        while len(rec["samples"]) < n:
            s = ask(api, args, c["category"], temperature)
            with _lock:
                rec["samples"].append(s)
                path.write_text(json.dumps(rec, indent=0))
        return c["category"], [s["answer"] for s in rec["samples"]]

    stopped = None
    with ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(one_category, c) for c in cats]
        for f in futures:
            try:
                cat, answers = f.result()
                print(f"{cat:28s} {len(answers):3d} {answers[:6]}", flush=True)
            except Stop as e:
                stopped = e
    print(f"experiment spend ${mine():.3f}; shared ledger ${spent():.2f}", flush=True)
    if stopped:
        print(f"STOPPED: {stopped}", flush=True)


def cmd_pilot(args):
    cats = [c for c in categories(args) if c["category"] in PILOT]
    run_text(args, cats, 1, BIRD_DIR / "spark_text")
    costs = [json.loads((BIRD_DIR / "spark_text" / f"{c['category']}.json").read_text())["samples"][0]
             for c in cats]
    per = sum(s["usd"] for s in costs) / len(costs)
    total = per * 118 * 50
    print(f"pilot: {len(costs)} calls, mean ${per:.5f} per call, reasoning tokens "
          f"{[s['reasoning_tokens'] for s in costs]}; 118 x 50 would cost ${total:.2f}")
    print(f"pre-registered rule: n = {50 if total <= 3.5 else 30}")


def cmd_text(args):
    run_text(args, categories(args), args.n, BIRD_DIR / "spark_text")


def cmd_temp(args):
    run_text(args, categories(args), args.n, BIRD_DIR / f"spark_text_T{args.temperature:g}", args.temperature)


def cmd_images(args):
    from metalesionlab.plato import STYLES, downscale

    api = MetaAPI()
    for key, (phrase, _) in PICTURE_CATEGORIES.items():
        out = BIRD_DIR / "pictures" / key
        out.mkdir(parents=True, exist_ok=True)
        prompt = STYLES["doodle"].format(phrase=phrase)
        have = len(list(out.glob("p*.png")))
        for _call in range(args.calls - have // args.per_call):
            guard(args, args.per_call * meta_api.IMAGE_PRICE)
            pngs = retry_network(lambda: api.generate_images(prompt, n=args.per_call), base=5, tries=6)
            log_spend(len(pngs) * meta_api.IMAGE_PRICE, kind="image", key=key)
            for png in pngs:
                i = len(list(out.glob("p*.png")))
                downscale(png).save(out / f"p{i}.png")
        (out / "prompt.txt").write_text(prompt + "\n")
        print(f"{key:20s} {len(list(out.glob('p*.png')))} pictures; spend ${mine():.3f}", flush=True)


def cmd_label(args):
    api = MetaAPI()
    api.client = api.client.with_options(timeout=120, max_retries=0)
    path = BIRD_DIR / "picture_labels_spark.json"
    done = json.loads(path.read_text()) if path.exists() else {"model": CHAT_MODEL, "labels": {}}
    for key, (phrase, _) in PICTURE_CATEGORIES.items():
        noun = phrase.split(" ", 1)[1]
        prompt = picture_label_prompt(phrase, noun)
        rec = done["labels"].setdefault(key, {"prompt": prompt, "items": []})
        have = {r["file"] for r in rec["items"]}
        for f in sorted((BIRD_DIR / "pictures" / key).glob("p*.png"), key=lambda p: int(p.stem[1:])):
            if f.name in have:
                continue
            guard(args, 0.003)
            msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_data_url(f.read_bytes())}},
                                                {"type": "text", "text": prompt}]}]
            resp = retry_network(lambda: api.chat(msg, reasoning_effort="minimal"), base=5, tries=8)
            log_spend(token_cost(CHAT_MODEL, resp.usage), kind="label", key=key)
            rec["items"].append({"file": f.name, "answer": (resp.choices[0].message.content or "").strip()[:120]})
            path.write_text(json.dumps(done, indent=1))
        print(f"{key:20s} {[r['answer'] for r in rec['items']]}", flush=True)
    print(f"experiment spend ${mine():.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=float, default=5.0)
    ap.add_argument("--shared-stop", type=float, default=70.0)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pilot")
    p.add_argument("--categories", nargs="*")
    p.add_argument("--workers", type=int, default=5)
    p.set_defaults(fn=cmd_pilot)
    p = sub.add_parser("text")
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--categories", nargs="*")
    p.add_argument("--workers", type=int, default=6)
    p.set_defaults(fn=cmd_text)
    p = sub.add_parser("temp")
    p.add_argument("--temperature", type=float, required=True)
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--categories", nargs="*")
    p.add_argument("--workers", type=int, default=6)
    p.set_defaults(fn=cmd_temp)
    p = sub.add_parser("images")
    p.add_argument("--per-call", type=int, default=4)
    p.add_argument("--calls", type=int, default=3)
    p.set_defaults(fn=cmd_images)
    p = sub.add_parser("label")
    p.set_defaults(fn=cmd_label)
    args = ap.parse_args()
    try:
        args.fn(args)
    except Stop as e:
        print(f"STOPPED: {e}")


if __name__ == "__main__":
    main()

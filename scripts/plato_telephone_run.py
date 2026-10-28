"""Plato's Telephone: run the chains (costs money), then label each picture's kind (costs a little).

  run   [--seeds ...] [--chains 3] [--gens 10] [--workers 5] [--max-steps N]
        Each chain: g00 is the seed doodle. Step k: Muse Spark describes g(k-1) (DESCRIBE_PROMPT, fixed
        reasoning effort), Muse Image draws image_prompt(description) as g(k). After g10 Spark describes g10
        too, so every picture has a description. Resumable: a chain continues from its last saved step.
  label [--gens 0 1 2 ...]
        Muse Spark (vision) answers Plato's Chair's multiple-choice kind question for every picture
        (plato.labeling_prompt with the concept's listed kinds, forward order, parsed with plato.parse_letter).

Every call is checked against this experiment's own spend log ($PLATO_TELEPHONE_DIR/spend.jsonl, cap
BUDGET_USD) and the shared ledger (stop at SHARED_STOP), and network failures (DNS drops on this Mac) are
retried with backoff. Set MLL_LEDGER to the shared ledger before running.
"""
import argparse
import io
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from metalesionlab import meta_api  # noqa: E402
from metalesionlab import plato_telephone as T  # noqa: E402

SPEND = T.TELEPHONE_DIR / "spend.jsonl"
_lock = threading.Lock()


class Stop(RuntimeError):
    pass


def mine() -> float:
    if not SPEND.exists():
        return 0.0
    return sum(json.loads(x)["usd"] for x in SPEND.read_text().splitlines() if x.strip())


def log_spend(kind: str, usd: float, **extra) -> None:
    with _lock, SPEND.open("a") as f:
        f.write(json.dumps({"ts": round(time.time(), 1), "kind": kind, "usd": round(usd, 6), **extra}) + "\n")


def check(estimate: float) -> None:
    if mine() + estimate > T.BUDGET_USD:
        raise Stop(f"experiment budget: spent ${mine():.3f} of ${T.BUDGET_USD:.2f}")
    if meta_api.spent() > T.SHARED_STOP:
        raise Stop(f"shared ledger passed ${T.SHARED_STOP:.0f} (${meta_api.spent():.2f})")


def png_512(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((T.SPARK_SIDE, T.SPARK_SIDE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def api_client():
    api = meta_api.MetaAPI()
    api.client = api.client.with_options(timeout=180, max_retries=0)
    return api


def spark(api, image: bytes, text: str, tag: dict) -> tuple[str, float]:
    """One Muse Spark vision call; returns (text, usd). Network errors retry with backoff; an empty answer is
    asked again up to twice."""
    msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": meta_api.image_data_url(image)}},
                                        {"type": "text", "text": text}]}]
    for _ in range(3):
        check(0.01)
        resp = meta_api.retry_network(lambda: api.chat(msg, reasoning_effort=T.REASONING_EFFORT,
                                                       ledger_tag="telephone"))
        usd = meta_api.token_cost(meta_api.CHAT_MODEL, resp.usage)
        log_spend("chat", usd, **tag)
        out = (resp.choices[0].message.content or "").strip()
        if out:
            return out, usd
    raise RuntimeError(f"empty answers from Spark for {tag}")


def draw(api, prompt: str, tag: dict) -> bytes:
    """One Muse Image picture. Network errors retry with backoff; any other failure is tried 3 times."""
    import openai

    last = None
    for attempt in range(3):
        check(meta_api.IMAGE_PRICE)
        try:
            imgs = meta_api.retry_network(lambda: api.generate_images(prompt, n=1))
            log_spend("image", meta_api.IMAGE_PRICE * len(imgs), **tag)
            if imgs:
                return imgs[0]
        except openai.APIStatusError as e:  # e.g. a refused prompt; nothing is billed
            last = e
            print(f"  {tag} image attempt {attempt + 1}: {type(e).__name__} {str(e)[:120]}", flush=True)
            time.sleep(5)
    raise RuntimeError(f"Muse Image failed for {tag}: {last}")


def run_chain(seed: T.Seed, c: int, gens: int, api, stop_flag: threading.Event, max_steps: int | None) -> str:
    d = T.chain_dir(seed, c)
    d.mkdir(parents=True, exist_ok=True)
    meta_path = d / "chain.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {
        "seed": seed.key, "chain": c, "concept": seed.concept, "seed_file": f"ai/doodle_listed/{seed.concept}/{seed.file}",
        "kind": seed.kind, "describe_prompt": T.DESCRIBE_PROMPT, "reasoning_effort": T.REASONING_EFFORT,
        "spark_model": meta_api.CHAT_MODEL, "image_model": meta_api.IMAGE_MODEL, "steps": [], "complete": False}
    g0 = d / T.pic_name(0)
    if not g0.exists():
        g0.write_bytes(png_512((T.SEED_DIR / seed.concept / seed.file).read_bytes()))

    def save():
        meta_path.write_text(json.dumps(meta, indent=1))

    done = 0
    while not meta["complete"]:
        if stop_flag.is_set() or (max_steps is not None and done >= max_steps):
            return f"{seed.key} c{c}: paused at {len(meta['steps'])} descriptions"
        k = len(meta["steps"])  # describe picture k, then draw picture k+1 (unless k == gens)
        tag = {"seed": seed.key, "chain": c, "gen": k}
        try:
            text, usd_chat = spark(api, (d / T.pic_name(k)).read_bytes(), T.DESCRIBE_PROMPT, tag)
            step = {"gen": k, "description": text, "usd_chat": round(usd_chat, 6)}
            if k < gens:
                prompt = T.image_prompt(text)
                img = draw(api, prompt, {**tag, "gen": k + 1})
                (d / T.pic_name(k + 1)).write_bytes(png_512(img))
                step.update(prompt=prompt, drew=T.pic_name(k + 1), usd_image=meta_api.IMAGE_PRICE)
            meta["steps"].append(step)
            meta["complete"] = len(meta["steps"]) == gens + 1
            save()
            done += 1
            print(f"{seed.key:14s} c{c} g{k:02d}: {text[:110]}", flush=True)
        except Stop as e:
            stop_flag.set()
            return f"{seed.key} c{c}: stopped ({e})"
        except Exception as e:  # noqa: BLE001 - keep the other chains going
            meta.setdefault("errors", []).append({"gen": k, "error": f"{type(e).__name__}: {str(e)[:200]}"})
            save()
            return f"{seed.key} c{c}: failed at g{k} ({type(e).__name__})"
    return f"{seed.key} c{c}: complete"


def cmd_run(args):
    T.TELEPHONE_DIR.mkdir(parents=True, exist_ok=True)
    seeds = [T.BY_KEY[k] for k in args.seeds] if args.seeds else T.SEEDS
    api = api_client()
    stop_flag = threading.Event()
    jobs = [(s, c) for c in range(args.chains) for s in seeds]  # chain 0 of every seed first
    print(f"{len(jobs)} chains; experiment spend so far ${mine():.3f}; shared ledger ${meta_api.spent():.2f}", flush=True)
    with ThreadPoolExecutor(args.workers) as ex:
        for msg in ex.map(lambda j: run_chain(j[0], j[1], args.gens, api, stop_flag, args.max_steps), jobs):
            print(msg, flush=True)
    print(f"experiment spend ${mine():.3f}; shared ledger ${meta_api.spent():.2f}", flush=True)


def cmd_label(args):
    from metalesionlab.plato import BY_KEY, kind_options, labeling_prompt, parse_letter, ink_crop

    api = api_client()
    out_path = T.TELEPHONE_DIR / "labels_spark.json"
    out = json.loads(out_path.read_text()) if out_path.exists() else {
        "model": meta_api.CHAT_MODEL, "reasoning_effort": T.REASONING_EFFORT, "side": T.LABEL_SIDE, "items": {}}
    todo = []
    for s in T.SEEDS:
        for c in range(T.CHAINS):
            d = T.chain_dir(s, c)
            for g in args.gens:
                f = d / T.pic_name(g)
                key = f"{s.key}/c0/g00" if g == 0 else f"{s.key}/c{c}/{f.stem}"  # g00 is the same picture
                if f.exists() and key not in out["items"] and key not in [t[0] for t in todo]:
                    todo.append((key, s, f))
    print(f"{len(todo)} pictures to label; experiment spend ${mine():.3f}", flush=True)
    for i, (key, s, f) in enumerate(todo):
        concept = BY_KEY[s.concept]
        kinds = json.loads((T.SEED_DIR / s.concept / "kinds.json").read_text())[:concept.n_ai]
        opts = kind_options(concept, kinds)
        buf = io.BytesIO()
        ink_crop(Image.open(f).convert("RGB"), side=T.LABEL_SIDE).save(buf, "PNG")
        try:
            text, usd = spark(api, buf.getvalue(), labeling_prompt(concept, opts), {"label": key})
        except Stop as e:
            print(f"stopped: {e}", flush=True)
            break
        lab = parse_letter(text, len(opts))
        out["items"][key] = {"answer": text[:40], "label": lab, "option": opts[lab] if lab is not None else None,
                             "right": kinds.index(s.kind), "n_kinds": len(kinds)}
        if i % 10 == 0 or i == len(todo) - 1:
            out_path.write_text(json.dumps(out, indent=0))
            print(f"  {i + 1}/{len(todo)} {key}: {out['items'][key]['option']}; spend ${mine():.3f}", flush=True)
    out_path.write_text(json.dumps(out, indent=0))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--seeds", nargs="*")
    p.add_argument("--chains", type=int, default=T.CHAINS)
    p.add_argument("--gens", type=int, default=T.GENERATIONS)
    p.add_argument("--workers", type=int, default=5)
    p.add_argument("--max-steps", type=int, help="steps per chain in this call (a pilot)")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("label")
    p.add_argument("--gens", nargs="*", type=int, default=list(range(T.GENERATIONS + 1)))
    p.set_defaults(fn=cmd_label)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

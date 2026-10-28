"""An AI growing up, Arm B: language models of growing size draw a chair as SVG (docs/plato_scale_plan.md).

  open     on a GPU server: one open model (Hugging Face weights), 12 samples per temperature
  api      on the Mac: Muse Spark 1.3 or Muse Wonder 1.0 through the Meta Model API (spend-capped)
  measure  on the Mac: extract and render every SVG, classify failures, ink-crop and embed with DINOv2

Usage:
  python scripts/plato_scale_svg.py open --model qwen25_7b --out ~/MetaLesionLab_scale/svg
  MLL_LEDGER=.../runs/costs.jsonl python -I scripts/plato_scale_svg.py api --model spark --out $PLATO_SCALE_DIR/svg
  python -I scripts/plato_scale_svg.py measure --out $PLATO_SCALE_DIR/svg

Files: svg/raw/<model>_t<T>.json (the model's text for each sample, tokens, whether it finished),
svg/png/<model>_t<T>_<i>.png (the rendered drawing), svg/emb/<model>_t<T>.npz (DINOv2 of rendered drawings),
svg/measure.json (failure reason and ink per sample).
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from metalesionlab.plato_scale import (API_MAX_TOKENS, BY_KEY, MAX_NEW_TOKENS, MODELS, N_B, PROMPT, TEMPS_B,  # noqa: E402
                                       classify, gen_seed, touches_all_edges)

API_CAPS = {"spark": 0.75, "wonder": 1.5}   # USD per model (plan: at most $3 in all, Wonder under about $1.5)
TOTAL_CAP = 3.0
LEDGER_STOP = 70.0
TAG = "plato_scale"


def raw_path(out: Path, key: str, temp: float) -> Path:
    return out / "raw" / f"{key}_t{temp:.1f}.json"


# ---------- open models ----------

def load_open(m, device: str = "cuda:0"):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, FineGrainedFP8Config

    if m.key == "glimmer":
        from metalesionlab import glimmer

        model, processor = glimmer.load(fp8=True, device=device)
        return model, processor
    kw = {}
    if m.fp8:
        kw["quantization_config"] = FineGrainedFP8Config(modules_to_not_convert=["lm_head"])
    tok = AutoTokenizer.from_pretrained(m.hf, revision=m.revision)
    model = AutoModelForCausalLM.from_pretrained(m.hf, revision=m.revision, dtype=torch.bfloat16, device_map=device,
                                                 **kw).eval()
    return model, tok


def prompt_inputs(m, model, tok, device: str):
    if m.key == "glimmer":
        from metalesionlab import glimmer

        return glimmer.build_inputs(tok, None, PROMPT, device)
    messages = [{"role": "user", "content": PROMPT}]
    return tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt", return_dict=True,
                                   **dict(m.chat_kwargs)).to(device)


def decode(m, tok, ids) -> str:
    if m.key == "glimmer":
        from metalesionlab.glimmer import END_OF_TURN

        text = tok.decode(ids, skip_special_tokens=False)
        return text.split(END_OF_TURN)[0].split("<|eom|>")[0].strip()
    return tok.decode(ids, skip_special_tokens=True).strip()


def eos_ids(model, tok) -> set:
    ids = set()
    for src in (getattr(model, "generation_config", None), getattr(tok, "tokenizer", tok)):
        e = getattr(src, "eos_token_id", None)
        if e is None:
            continue
        ids.update(e if isinstance(e, (list, tuple)) else [e])
    return ids


def run_open(key: str, out: Path, device: str = "cuda:0", batch: int = N_B):
    import torch

    m = BY_KEY[key]
    todo = [t for t in TEMPS_B if not raw_path(out, key, t).exists()]
    if not todo:
        print(f"{key}: done already", flush=True)
        return
    t_load = time.time()
    model, tok = load_open(m, device)
    print(f"{key}: loaded in {time.time() - t_load:.0f}s, {torch.cuda.memory_allocated() / 2**30:.1f} GiB", flush=True)
    inputs = prompt_inputs(m, model, tok, device)
    n_in = inputs["input_ids"].shape[1]
    stop = eos_ids(model, tok)
    for temp in todo:
        t0 = time.time()
        samples, b = [], batch
        while len(samples) < N_B:
            k = min(b, N_B - len(samples))
            chunk = len(samples) // max(b, 1)
            torch.manual_seed(gen_seed(temp) + 1000 * chunk)
            try:
                with torch.no_grad():
                    gen = model.generate(**inputs, do_sample=True, temperature=temp, top_p=1.0, top_k=0, min_p=None,
                                         repetition_penalty=1.0, max_new_tokens=MAX_NEW_TOKENS, num_return_sequences=k)
            except torch.OutOfMemoryError:
                torch.cuda.empty_cache()
                b = max(1, b // 2)
                print(f"{key} t{temp}: out of memory, batch {b}", flush=True)
                continue
            for row in gen[:, n_in:].tolist():
                ids = row
                finished = any(t in stop for t in ids)
                if finished:  # cut at the first end token
                    first = min(i for i, t in enumerate(ids) if t in stop)
                    ids = ids[:first + 1]
                pad = getattr(getattr(tok, "tokenizer", tok), "pad_token_id", None)
                n_tok = len([t for t in ids if t != pad]) if not finished else len(ids)
                samples.append({"i": len(samples), "text": decode(m, tok, ids), "n_tokens": n_tok,
                                "finished": finished})
        rec = {"model": key, "hf": m.hf, "revision": m.revision, "temp": temp, "seed": gen_seed(temp), "batch": b,
               "prompt": PROMPT, "sampling": {"top_p": 1.0, "top_k": None, "repetition_penalty": 1.0,
                                              "max_new_tokens": MAX_NEW_TOKENS},
               "precision": "fp8 weights" if m.fp8 else "bf16", "prompt_tokens": n_in,
               "gpu": torch.cuda.get_device_name(0), "seconds": round(time.time() - t0, 1), "samples": samples}
        p = raw_path(out, key, temp)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec, indent=1))
        print(f"{key} t{temp}: {sum(s['finished'] for s in samples)}/{N_B} finished, "
              f"{np.mean([s['n_tokens'] for s in samples]):.0f} tokens on average, {rec['seconds']:.0f}s", flush=True)


# ---------- API models ----------

def tag_spend() -> dict:
    from metalesionlab import meta_api

    by = {}
    if meta_api.LEDGER.exists():
        for line in meta_api.LEDGER.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                if e.get("tag") == TAG:
                    by[e["model"]] = by.get(e["model"], 0.0) + e["usd"]
    return by


def run_api(key: str, out: Path, temps=TEMPS_B):
    from metalesionlab import meta_api

    m = BY_KEY[key]
    api = meta_api.MetaAPI()
    for temp in temps:
        p = raw_path(out, key, temp)
        rec = json.loads(p.read_text()) if p.exists() else {
            "model": key, "api_model": m.hf, "temp": temp, "prompt": PROMPT, "reasoning_effort": "minimal",
            "max_completion_tokens": API_MAX_TOKENS, "samples": []}
        have = {s["i"] for s in rec["samples"]}
        for i in range(N_B):
            if i in have:
                continue
            total, mine = meta_api.spent(), tag_spend()
            if total > LEDGER_STOP:
                raise SystemExit(f"shared ledger at ${total:.2f}, past the ${LEDGER_STOP} stop")
            if mine.get(m.hf, 0) >= API_CAPS[key] or sum(mine.values()) >= TOTAL_CAP:
                raise SystemExit(f"plato_scale spend cap reached: {mine}")
            t0 = time.time()
            r = meta_api.retry_network(lambda: api.chat([{"role": "user", "content": PROMPT}], model=m.hf,
                                                        reasoning_effort="minimal", ledger_tag=TAG, temperature=temp,
                                                        max_completion_tokens=API_MAX_TOKENS))
            u = r.usage.model_dump()
            c = r.choices[0]
            rec["samples"].append({"i": i, "text": c.message.content or "", "finished": c.finish_reason == "stop",
                                   "finish_reason": c.finish_reason, "n_tokens": u.get("completion_tokens"),
                                   "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                                   "usd": round(meta_api.token_cost(m.hf, r.usage), 6),
                                   "seconds": round(time.time() - t0, 1)})
            rec["samples"].sort(key=lambda s: s["i"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(rec, indent=1))
            print(f"{key} t{temp} #{i}: {u.get('completion_tokens')} tokens, ${rec['samples'][-1]['usd']:.4f}, "
                  f"{c.finish_reason}", flush=True)
        usd = sum(s["usd"] for s in rec["samples"])
        print(f"{key} t{temp}: ${usd:.3f} for {len(rec['samples'])} samples; plato_scale total {tag_spend()}", flush=True)


# ---------- render, classify, embed (Mac) ----------

def measure(out: Path, device: str | None = None):
    from metalesionlab.plato import DINO_MODEL, Embedder, ink_crop

    res_path = out / "measure.json"
    res = json.loads(res_path.read_text()) if res_path.exists() else {}
    emb = None
    for f in sorted((out / "raw").glob("*_t*.json")):
        rec = json.loads(f.read_text())
        name = f.stem
        if len(rec["samples"]) < N_B:
            print(f"{name}: only {len(rec['samples'])} samples so far, skipped", flush=True)
            continue
        if name in res and (out / "emb" / f"{name}.npz").exists():
            continue
        rows, crops, idx = [], [], []
        (out / "png").mkdir(parents=True, exist_ok=True)
        for s in rec["samples"]:
            c = classify(s["text"])
            row = {"i": s["i"], "reason": c["reason"], "ink": c["ink"], "finished": s.get("finished"),
                   "n_tokens": s.get("n_tokens"), "has_text_el": bool(c["svg"] and "<text" in c["svg"].lower())}
            if c.get("error"):
                row["error"] = c["error"]
            if c["image"] is not None:
                c["image"].save(out / "png" / f"{name}_{s['i']}.png")
                row["framed"] = touches_all_edges(c["image"])
            if c["ok"]:
                crops.append(ink_crop(c["image"].convert("RGB")))
                idx.append(s["i"])
            rows.append(row)
        if crops:
            emb = emb or Embedder(DINO_MODEL, device=device)
            vecs = emb(crops)
        else:
            vecs = {"cls": np.zeros((0, 768)), "patch_mean": np.zeros((0, 768))}
        (out / "emb").mkdir(exist_ok=True)
        np.savez(out / "emb" / f"{name}.npz", cls=vecs["cls"].astype(np.float32),
                 patch_mean=vecs["patch_mean"].astype(np.float32), idx=np.array(idx, int), model=DINO_MODEL)
        res[name] = {"model": rec["model"], "temp": rec["temp"], "samples": rows}
        res_path.write_text(json.dumps(res, indent=1))
        reasons = [r["reason"] for r in rows]
        print(f"{name}: {sum(r is None for r in reasons)}/{len(rows)} drew; failures "
              f"{ {k: reasons.count(k) for k in set(reasons) if k} }", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open")
    o.add_argument("--model", nargs="+", required=True, choices=[m.key for m in MODELS if m.kind == "open"])
    o.add_argument("--out", type=Path, required=True)
    o.add_argument("--device", default="cuda:0")
    o.add_argument("--batch", type=int, default=N_B)
    a = sub.add_parser("api")
    a.add_argument("--model", required=True, choices=["spark", "wonder"])
    a.add_argument("--out", type=Path, required=True)
    a.add_argument("--temps", type=float, nargs="+", default=TEMPS_B)
    me = sub.add_parser("measure")
    me.add_argument("--out", type=Path, required=True)
    me.add_argument("--device", default=None)
    args = ap.parse_args()
    if args.cmd == "open":
        import gc

        import torch

        for key in args.model:
            try:
                run_open(key, args.out, args.device, args.batch)
            except Exception as e:  # noqa: BLE001  one model failing must not stop the queue; it is reported
                print(f"{key}: FAILED {type(e).__name__}: {e}", flush=True)
            gc.collect()
            torch.cuda.empty_cache()
    elif args.cmd == "api":
        run_api(args.model, args.out, args.temps)
    else:
        measure(args.out, args.device)


if __name__ == "__main__":
    main()

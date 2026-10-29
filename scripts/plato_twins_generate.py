"""Prisoners of the cave: each twin answers the three requests, text only (docs/plato_cave_twins_plan.md).

Runs on a GPU server. Sampling is the scale experiment's (scripts/plato_scale_svg.py): pure temperature sampling
(top-p 1, no top-k, no repetition penalty), at most 2,048 new tokens, one batch of 12 per request and temperature,
torch seed 20261028 + 100 x temperature. Each model uses its own chat template, including any default system
prompt it adds. The vision twins get no picture: their input is the same words, through their processor.

  smoke   load a model and answer "Reply with the single word: ok" twice (no drawing, no description)
  run     the tasks for each model; a text twin's chair answers are reused from the scale experiment unless
          --chair-too is given

Usage:
  python scripts/plato_twins_generate.py smoke --model qwen25vl_7b
  python scripts/plato_twins_generate.py run --model qwen25vl_7b qwen25_7b --out ~/MetaLesionLab_twins/raw

Files: raw/<model>_<task>_t<T>.json (each answer's text, tokens, whether it finished; the full prompt as the model
saw it).
"""
import argparse
import gc
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from metalesionlab import plato_twins as pt  # noqa: E402


def load(m, device: str = "cuda:0"):
    import torch
    from transformers import FineGrainedFP8Config

    kw = {}
    if m.fp8:  # as in the scale experiment; a vision twin's picture encoder stays in BF16 (it is never used)
        kw["quantization_config"] = FineGrainedFP8Config(
            modules_to_not_convert=["lm_head", "visual"] if m.vl else ["lm_head"])
    if m.vl:
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        proc = AutoProcessor.from_pretrained(m.hf, revision=m.revision)
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(m.hf, revision=m.revision, dtype=torch.bfloat16,
                                                                   device_map=device, **kw).eval()
        return model, proc
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(m.hf, revision=m.revision)
    model = AutoModelForCausalLM.from_pretrained(m.hf, revision=m.revision, dtype=torch.bfloat16, device_map=device,
                                                 **kw).eval()
    return model, tok


def tokenizer_of(tok):
    return getattr(tok, "tokenizer", tok)


def inputs_for(m, tok, prompt: str, device: str):
    """One user turn, no system prompt of ours. Text only: the vision twin's message has no picture in it."""
    if m.vl:
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        x = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True,
                                    return_tensors="pt")
    else:
        messages = [{"role": "user", "content": prompt}]
        x = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt", return_dict=True)
    x = {k: v.to(device) for k, v in x.items() if k in ("input_ids", "attention_mask")}
    return x


def stop_ids(model, tok) -> set:
    ids = set()
    for src in (getattr(model, "generation_config", None), tokenizer_of(tok)):
        e = getattr(src, "eos_token_id", None)
        if e is None:
            continue
        ids.update(e if isinstance(e, (list, tuple)) else [e])
    return ids


def sample(model, tok, inputs, temp: float, n: int, max_new: int, batch: int, label: str) -> tuple[list, int]:
    """n answers in batches (halving on out-of-memory), seeded as in the scale experiment."""
    import torch

    n_in = inputs["input_ids"].shape[1]
    stop, pad = stop_ids(model, tok), tokenizer_of(tok).pad_token_id
    out, b = [], batch
    while len(out) < n:
        k = min(b, n - len(out))
        chunk = len(out) // max(b, 1)
        torch.manual_seed(pt.gen_seed(temp) + 1000 * chunk)
        try:
            with torch.no_grad():
                gen = model.generate(**inputs, do_sample=True, temperature=temp, top_p=1.0, top_k=0, min_p=None,
                                     repetition_penalty=1.0, max_new_tokens=max_new, num_return_sequences=k)
        except torch.OutOfMemoryError:
            torch.cuda.empty_cache()
            b = max(1, b // 2)
            print(f"{label}: out of memory, batch {b}", flush=True)
            continue
        for row in gen[:, n_in:].tolist():
            ids = row
            finished = any(t in stop for t in ids)
            if finished:  # cut at the first end token
                first = min(i for i, t in enumerate(ids) if t in stop)
                ids = ids[:first + 1]
            n_tok = len(ids) if finished else len([t for t in ids if t != pad])
            out.append({"i": len(out), "text": tokenizer_of(tok).decode(ids, skip_special_tokens=True).strip(),
                        "n_tokens": n_tok, "finished": finished})
    return out, b


def smoke(key: str, device: str):
    import torch

    m = pt.BY_KEY[key]
    t0 = time.time()
    model, tok = load(m, device)
    print(f"{key}: loaded in {time.time() - t0:.0f}s, {torch.cuda.memory_allocated() / 2**30:.1f} GiB", flush=True)
    x = inputs_for(m, tok, "Reply with the single word: ok", device)
    print("prompt as the model sees it:", repr(tokenizer_of(tok).decode(x["input_ids"][0])), flush=True)
    s, _ = sample(model, tok, x, 1.0, 2, 16, 2, key)
    print([a["text"] for a in s], flush=True)


def run(key: str, out: Path, tasks: list, device: str, chair_too: bool):
    import torch

    m = pt.BY_KEY[key]
    todo = []
    for task in tasks:
        t = pt.TASKS[task]
        if task == "chair" and m.scale_key and not chair_too:
            continue  # reused from the scale experiment (same prompt, settings, seed and precision)
        todo += [(t, temp) for temp in t.temps if not (out / f"{pt.raw_name(key, task, temp)}.json").exists()]
    if not todo:
        print(f"{key}: done already", flush=True)
        return
    t_load = time.time()
    model, tok = load(m, device)
    print(f"{key}: loaded in {time.time() - t_load:.0f}s, {torch.cuda.memory_allocated() / 2**30:.1f} GiB", flush=True)
    for t, temp in todo:
        x = inputs_for(m, tok, t.prompt, device)
        t0 = time.time()
        samples, b = sample(model, tok, x, temp, pt.N, pt.MAX_NEW_TOKENS, pt.N, f"{key} {t.key} t{temp}")
        rec = {"model": key, "hf": m.hf, "revision": m.revision, "arm": m.arm, "task": t.key, "temp": temp,
               "seed": pt.gen_seed(temp), "batch": b, "prompt": t.prompt,
               "prompt_as_seen": tokenizer_of(tok).decode(x["input_ids"][0]),
               "sampling": {"top_p": 1.0, "top_k": None, "repetition_penalty": 1.0, "max_new_tokens": pt.MAX_NEW_TOKENS},
               "precision": "fp8 weights" if m.fp8 else "bf16", "prompt_tokens": int(x["input_ids"].shape[1]),
               "picture_input": False, "gpu": torch.cuda.get_device_name(0), "seconds": round(time.time() - t0, 1),
               "samples": samples}
        p = out / f"{pt.raw_name(key, t.key, temp)}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec, indent=1))
        print(f"{key} {t.key} t{temp}: {sum(s['finished'] for s in samples)}/{pt.N} finished, "
              f"{np.mean([s['n_tokens'] for s in samples]):.0f} tokens on average, {rec['seconds']:.0f}s", flush=True)
    del model
    gc.collect()
    torch.cuda.empty_cache()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("smoke")
    s.add_argument("--model", required=True, choices=list(pt.BY_KEY))
    s.add_argument("--device", default="cuda:0")
    r = sub.add_parser("run")
    r.add_argument("--model", nargs="+", required=True, choices=list(pt.BY_KEY))
    r.add_argument("--tasks", nargs="+", default=list(pt.TASKS), choices=list(pt.TASKS))
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--device", default="cuda:0")
    r.add_argument("--chair-too", action="store_true", help="also redraw a text twin's chairs (not reused)")
    args = ap.parse_args()
    if args.cmd == "smoke":
        smoke(args.model, args.device)
        return
    for key in args.model:
        try:
            run(key, args.out, args.tasks, args.device, args.chair_too)
        except Exception as e:  # noqa: BLE001  one model failing must not stop the queue; it is reported
            print(f"{key}: FAILED {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()

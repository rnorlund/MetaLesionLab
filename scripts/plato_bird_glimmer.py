"""Plato's Bird on Muse Glimmer 30B (self-hosted, free): "Name one member of the category <X>."

  text  --categories FILE --out DIR [--probe]   on a GPU: for every category,
        (a) the logit distribution: the next-token distribution at the first answer position; the top first
            tokens (until 99% of the mass, at most 64) are each continued greedily to a full answer;
        (b) 50 samples at each temperature in --temps (default 0.7, 1.0, 1.5), top-k and top-p off.
        Writes DIR/<category>.json (resumable).
  judge --input PAIRS --out FILE                 on a GPU (exploratory): P(yes) that each answer is a member
        of its category, from the yes/no logits; applied to people's and the models' answers alike.
  label --input DIR --out FILE                   on a GPU: one greedy free-text answer per picture,
        "Someone was asked to draw a fruit. Which fruit is in this drawing? ..." (plato_bird.picture_label_prompt).
        DIR holds <key>/*.png and labels.json is written to FILE.

The reasoning channel is skipped by pre-filling the answer header (metalesionlab/glimmer.py), so the first
generated token is the first token of the answer. Sampling is a plain loop over the model's own logits (no
generation-config processors), so temperature 1.0 is the model's distribution.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab.plato_bird import PICTURE_CATEGORIES, picture_label_prompt, prompt_for  # noqa: E402


def stop_ids(model, tok) -> list[int]:
    from metalesionlab.model_lab import stop_token_ids

    return sorted(stop_token_ids(model, tok))


def decode(model, batch: dict, stops: list[int], max_new: int, temperature: float, first=None, gen=None):
    """Batched decoding with a KV cache. temperature 0 is greedy. `first` (B,) forces the first token.
    Returns (tokens (B, T) list of lists cut at the first stop token, first-step logits (B, V))."""
    import torch

    mask = batch["attention_mask"]
    pos = batch.get("position_ids")
    if pos is None:
        pos = (mask.cumsum(-1) - 1).clamp_min(0)
    out = model(**{**batch, "position_ids": pos}, use_cache=True, logits_to_keep=1)
    past, logits = out.past_key_values, out.logits[:, -1].float()
    first_logits = logits
    stop_t = torch.tensor(stops, device=logits.device)
    done = torch.zeros(len(logits), dtype=torch.bool, device=logits.device)
    cur = pos[:, -1:]
    toks = []
    for step in range(max_new):
        if step == 0 and first is not None:
            nxt = first.to(logits.device)
        elif temperature == 0:
            nxt = logits.argmax(-1)
        else:
            probs = torch.softmax(logits / temperature, dim=-1)
            nxt = torch.multinomial(probs, 1, generator=gen)[:, 0]
        nxt = torch.where(done, stop_t[0], nxt)
        toks.append(nxt)
        done |= torch.isin(nxt, stop_t)
        if bool(done.all()) or step == max_new - 1:
            break
        mask = torch.cat([mask, torch.ones_like(mask[:, :1])], dim=1)
        cur = cur + 1
        out = model(input_ids=nxt[:, None], attention_mask=mask, position_ids=cur, past_key_values=past,
                    use_cache=True)
        past, logits = out.past_key_values, out.logits[:, -1].float()
    rows = torch.stack(toks, 1).tolist()
    cut = []
    for r in rows:
        k = next((i for i, t in enumerate(r) if t in stops), len(r))
        cut.append(r[:k])
    return cut, first_logits


def repeat(batch: dict, n: int) -> dict:
    return {k: v.repeat(n, *([1] * (v.dim() - 1))) for k, v in batch.items()}


def cmd_text(args):
    import torch

    from metalesionlab import glimmer
    from metalesionlab.model_lab import to_device

    cats = json.loads(args.categories.read_text())
    if args.probe:
        cats = [c for c in cats if c["category"] in ("bird", "fruit", "emotion", "game")]
    args.out.mkdir(parents=True, exist_ok=True)
    todo = [c for c in cats if args.probe or not (args.out / f"{c['category']}.json").exists()]
    print(f"{len(todo)} categories to do", flush=True)
    if not todo:
        return
    t0 = time.time()
    model, processor = glimmer.load(fp8=True)
    tok = processor.tokenizer
    stops = stop_ids(model, tok)
    print(f"loaded Glimmer in {time.time() - t0:.0f}s; stop ids {stops}", flush=True)
    gen = torch.Generator(device=model.device).manual_seed(20261027)
    dec = lambda ids: tok.decode(ids, skip_special_tokens=True).strip()  # noqa: E731
    for c in todo:
        t1 = time.time()
        prompt = prompt_for(c["category"])
        one = to_device(dict(glimmer.build_inputs(processor, None, prompt, "cpu")), model.device)
        with torch.no_grad():
            greedy, logits = decode(model, one, stops, args.max_new, 0.0)
            logp = torch.log_softmax(logits[0], -1)
            p = logp.exp()
            order = torch.argsort(p, descending=True)
            cum = torch.cumsum(p[order], 0)
            k = int(min(args.top, int((cum < args.mass).sum()) + 1))
            top_ids = order[:k]
            cont, _ = decode(model, repeat(one, k), stops, args.max_new, 0.0, first=top_ids)
            expansion = [{"first_token": tok.decode([int(t)]), "p": round(float(p[t]), 6), "answer": dec(seq)}
                         for t, seq in zip(top_ids.tolist(), cont)]
            samples = {}
            for temp in args.temps:
                seqs, _ = decode(model, repeat(one, args.n), stops, args.max_new, temp, gen=gen)
                samples[str(temp)] = [dec(s) for s in seqs]
        rec = {"category": c["category"], "domain": c.get("domain"), "prompt": prompt, "model": glimmer.MODEL_ID,
               "greedy": dec(greedy[0]), "covered_mass": round(float(cum[k - 1]), 4), "expansion": expansion,
               "samples": samples, "max_new": args.max_new}
        if args.probe:
            print(json.dumps({**rec, "expansion": expansion[:8]}, indent=1)[:2500], flush=True)
        else:
            (args.out / f"{c['category']}.json").write_text(json.dumps(rec, indent=0))
        s1 = samples.get("1.0", [])
        print(f"{c['category']:28s} greedy={rec['greedy']!r:18s} k={k:2d} mass={rec['covered_mass']:.3f} "
              f"T1 top={max(set(s1), key=s1.count) if s1 else None!r} in {time.time() - t1:.1f}s", flush=True)
    print(f"done in {time.time() - t0:.0f}s; peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


def cmd_label(args):
    import torch
    from PIL import Image

    from metalesionlab import glimmer
    from metalesionlab.model_lab import build_batches, to_device

    model, processor = glimmer.load(fp8=True)
    tok = processor.tokenizer
    stops = stop_ids(model, tok)
    out = {}
    for key, (phrase, _norm) in PICTURE_CATEGORIES.items():
        files = sorted((args.input / key).glob("*.png"))
        if not files:
            continue
        noun = phrase.split(" ", 1)[1]
        prompt = picture_label_prompt(phrase, noun)
        answers = []
        for batch in build_batches(processor, [(Image.open(f).convert("RGB"), prompt) for f in files], args.batch):
            with torch.no_grad():
                seqs, _ = decode(model, to_device(batch, model.device), stops, args.max_new, 0.0)
            answers += [tok.decode(s, skip_special_tokens=True).strip() for s in seqs]
        out[key] = {"prompt": prompt, "items": [{"file": f.name, "answer": a} for f, a in zip(files, answers)]}
        print(f"{key:20s} {answers}", flush=True)
    args.out.write_text(json.dumps({"model": glimmer.MODEL_ID, "labels": out}, indent=1))


def judge_prompt(category: str, answer: str) -> str:
    return (f'Is "{answer}" a member of the category {category}? It counts if it is a real example of that '
            f"category, even an unusual one. Answer yes or no.")


def cmd_judge(args):
    """Exploratory validity check, applied to people's and the models' answers alike: P(yes) from the yes/no
    logits at the first answer position (softmax over the two)."""
    import torch

    from metalesionlab import glimmer
    from metalesionlab.model_lab import build_batches, to_device

    pairs = json.loads(args.input.read_text())
    model, processor = glimmer.load(fp8=True)
    tok = processor.tokenizer

    def ids(words):
        out = set()
        for w in words:
            t = tok(w, add_special_tokens=False)["input_ids"]
            if len(t) == 1:
                out.add(t[0])
        return sorted(out)

    yes, no = ids(["yes", "Yes", " yes", " Yes", "YES"]), ids(["no", "No", " no", " No", "NO"])
    print(f"{len(pairs)} pairs; yes ids {yes}, no ids {no}", flush=True)
    t0, out = time.time(), []
    examples = [(None, judge_prompt(p["category"], p["answer"])) for p in pairs]
    for i, batch in enumerate(build_batches(processor, examples, args.batch)):
        with torch.no_grad():
            logits = model(**to_device(batch, model.device), logits_to_keep=1).logits[:, -1].float()
        logp = torch.log_softmax(logits, -1)
        ly, ln = torch.logsumexp(logp[:, yes], -1), torch.logsumexp(logp[:, no], -1)
        p_yes = torch.sigmoid(ly - ln).tolist()
        mass = (ly.exp() + ln.exp()).tolist()
        out += [{"p_yes": round(a, 4), "mass": round(b, 4)} for a, b in zip(p_yes, mass)]
        if i % 20 == 0:
            print(f"  {len(out)}/{len(pairs)} in {time.time() - t0:.0f}s", flush=True)
    rows = [{**p, **o} for p, o in zip(pairs, out)]
    args.out.write_text(json.dumps({"model": glimmer.MODEL_ID, "prompt": judge_prompt("{category}", "{answer}"),
                                    "items": rows}, indent=0))
    print(f"done in {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("text")
    p.add_argument("--categories", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--temps", type=float, nargs="*", default=[0.7, 1.0, 1.5])
    p.add_argument("--top", type=int, default=64)
    p.add_argument("--mass", type=float, default=0.99)
    p.add_argument("--max-new", type=int, default=12)
    p.add_argument("--probe", action="store_true")
    p.set_defaults(fn=cmd_text)
    p = sub.add_parser("label")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--batch", type=int, default=12)
    p.add_argument("--max-new", type=int, default=12)
    p.set_defaults(fn=cmd_label)
    p = sub.add_parser("judge")
    p.add_argument("--input", type=Path, required=True, help='JSON list of {"category", "answer"}')
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--batch", type=int, default=64)
    p.set_defaults(fn=cmd_judge)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

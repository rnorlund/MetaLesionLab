"""Plato's Chair, damage, stretch: one model that both draws and understands (GPU part).

Janus-Pro-7B (DeepSeek, MIT; transformers format deepseek-community/Janus-Pro-7B) reads pictures and
draws them with the SAME language model. We damage that language model once (a random share of its
MLP neurons switched off, the same units for both tasks) and ask: do drawing and understanding fail
together?

  probe --out DIR                       module sizes, one drawing and one answer, timing
  draw --out DIR --doses 0 0.1 ...      the doodle prompt for chair kinds and the plain chair, n seeds
  read --pictures DIR --out DIR --doses ...
                                        the kind question (multiple choice, letter logits, forward and
                                        reversed order) on Muse Image's named-kind doodles
                                        (kinds_input/ai_doodle_listed) for chair, hat and bird

Pictures: <out>/lm-zero@<dose>/<key>/s<i>.png; seed i is torch.manual_seed(SEED + 1000 * prompt index + i).
"""
import argparse
import contextlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab.plato import BY_KEY as PLATO_KEYS, LETTERS, kind_options, labeling_prompt, load_dir  # noqa: E402
from metalesionlab.plato_damage import BY_KEY, KIND_PROMPTS, seed_for  # noqa: E402
from metalesionlab.sdxl_lesions import random_units  # noqa: E402

MODEL = "deepseek-community/Janus-Pro-7B"


def load():
    import torch
    from transformers import JanusForConditionalGeneration, JanusProcessor

    processor = JanusProcessor.from_pretrained(MODEL)
    model = JanusForConditionalGeneration.from_pretrained(MODEL, dtype=torch.bfloat16, device_map="cuda").eval()
    return model, processor


def mlp_modules(model):
    lm = model.model.language_model
    return [(f"lm.{i}", layer.mlp.down_proj) for i, layer in enumerate(lm.layers)]


@contextlib.contextmanager
def lm_zero(model, fraction: float, seed: int = 7):
    """Switch off a random `fraction` of every language-model layer's MLP neurons (nested across doses)."""
    import torch

    mods = mlp_modules(model)
    hooks = []
    if fraction > 0:
        chosen = random_units([m.in_features for _, m in mods], fraction, seed)
        for (name, m), idx in zip(mods, chosen):
            keep = torch.ones(m.in_features, dtype=torch.bfloat16, device=m.weight.device)
            keep[torch.as_tensor(idx, device=m.weight.device)] = 0
            hooks.append(m.register_forward_pre_hook(lambda _m, a, keep=keep: (a[0] * keep.to(a[0].dtype),) + tuple(a[1:])))
    try:
        yield
    finally:
        for h in hooks:
            h.remove()


def draw(model, processor, prompt: str, seed: int):
    import torch

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    text = processor.apply_chat_template(messages, add_generation_prompt=True)
    # a list: a bare string would be read as a batch of characters
    inputs = processor(text=[text], generation_mode="image", return_tensors="pt").to(model.device, dtype=torch.bfloat16)
    torch.manual_seed(seed)
    out = model.generate(**inputs, num_return_sequences=1, generation_mode="image", do_sample=True, use_cache=True,
                         max_new_tokens=576)
    img = model.decode_image_tokens(out).float()[0]  # (3, H, W) or (H, W, 3), values in [-1, 1]
    if img.shape[0] == 3:
        img = img.permute(1, 2, 0)
    arr = ((img.clamp(-1, 1) + 1) * 127.5).round().byte().cpu().numpy()
    from PIL import Image

    return Image.fromarray(arr)


def letter_ids(tok, n: int) -> list[list[int]]:
    out = []
    for letter in LETTERS[:n]:
        ids = set()
        for v in (letter, " " + letter):
            t = tok(v, add_special_tokens=False)["input_ids"]
            if len(t) == 1:
                ids.add(t[0])
        out.append(sorted(ids))
    return out


def mcq(model, processor, image, question: str, n_options: int) -> np.ndarray:
    import torch

    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": question}]}]
    text = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(text=[text], images=[image], generation_mode="text", return_tensors="pt").to(
        model.device, dtype=torch.bfloat16)
    with torch.no_grad():
        logits = model(**inputs).logits[0, -1].float()
    logp = torch.log_softmax(logits, -1)
    ids = letter_ids(processor.tokenizer, n_options)
    per = torch.stack([torch.logsumexp(logp[i], 0) for i in ids])
    return torch.softmax(per, 0).cpu().numpy()


def cmd_probe(args):
    import torch

    t0 = time.time()
    model, processor = load()
    mods = mlp_modules(model)
    print(f"loaded in {time.time() - t0:.0f}s; {len(mods)} LM layers x {mods[0][1].in_features} MLP neurons", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    p = BY_KEY["chair__rocking_chair"]
    for dose in (0.0, 0.2):
        t1 = time.time()
        with lm_zero(model, dose):
            img = draw(model, processor, p.prompt, seed_for(p, 0))
        img.save(args.out / f"probe_{dose:g}.png")
        print(f"dose {dose}: drew {img.size} in {time.time() - t1:.1f}s", flush=True)
    print(f"peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


def cmd_draw(args):
    model, processor = load()
    keys = args.keys or [p.key for p in KIND_PROMPTS if p.concept == "chair"]
    t0 = time.time()
    for dose in args.doses:
        cond = "intact" if dose == 0 else f"lm-zero@{dose:g}"
        with lm_zero(model, dose):
            for key in keys:
                p = BY_KEY[key]
                out = args.out / cond / key
                out.mkdir(parents=True, exist_ok=True)
                for i in range(args.n):
                    f = out / f"s{i}.png"
                    if f.exists():
                        continue
                    img = draw(model, processor, p.prompt, seed_for(p, i))
                    img.save(f)
                print(f"{cond:16s} {key:24s} ({time.time() - t0:.0f}s)", flush=True)


def cmd_read(args):
    from PIL import Image

    model, processor = load()
    args.out.mkdir(parents=True, exist_ok=True)
    for dose in args.doses:
        cond = "intact" if dose == 0 else f"lm-zero@{dose:g}"
        path = args.out / f"{cond}.json"
        if path.exists():
            continue
        rows = []
        t0 = time.time()
        with lm_zero(model, dose):
            for key in args.keys:
                c = PLATO_KEYS[key]
                kinds = json.loads((args.pictures.parent / "kinds" / f"{key}.json").read_text())[:c.n_ai]
                fwd, rev = kind_options(c, kinds), kind_options(c, kinds[::-1])
                k = len(kinds)
                back = list(range(k - 1, -1, -1)) + [k, k + 1]
                for f in load_dir(args.pictures / key):
                    im = Image.open(f).convert("RGB")
                    pf = mcq(model, processor, im, labeling_prompt(c, fwd), len(fwd))
                    pr = mcq(model, processor, im, labeling_prompt(c, rev), len(rev))
                    p_rev = np.zeros_like(pr)
                    p_rev[back] = pr
                    p = (pf + p_rev) / 2
                    rows.append({"key": key, "file": f.name, "true_kind": int(f.stem[1:]), "n_kinds": k,
                                 "label": int(np.argmax(p)), "p": [round(float(x), 4) for x in p]})
        path.write_text(json.dumps({"condition": cond, "dose": dose, "model": MODEL, "items": rows}, indent=0))
        acc = np.mean([r["label"] == r["true_kind"] for r in rows])
        plain = np.mean([r["label"] == r["n_kinds"] for r in rows])
        print(f"{cond:16s} kind acc {acc:.3f} plain {plain:.3f} ({len(rows)} pictures, {time.time() - t0:.0f}s)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe")
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(fn=cmd_probe)
    p = sub.add_parser("draw")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--doses", type=float, nargs="+", required=True)
    p.add_argument("--keys", nargs="*")
    p.add_argument("--n", type=int, default=4)
    p.set_defaults(fn=cmd_draw)
    p = sub.add_parser("read")
    p.add_argument("--pictures", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--doses", type=float, nargs="+", required=True)
    p.add_argument("--keys", nargs="*", default=["chair", "hat", "bird"])
    p.set_defaults(fn=cmd_read)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

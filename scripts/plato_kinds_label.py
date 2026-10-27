"""Plato's Chair, kinds: which KIND of object does each picture show? Muse Glimmer 30B labels it.

  prepare [--sources ...] [--keys ...]       on the Mac: ink-crop every picture to 448 px (plato.ink_crop,
                                             as for DINOv2) into $PLATO_DIR/kinds_input/<source>/<key>/,
                                             with the kind lists in kinds_input/kinds/<key>.json
  label --input DIR --out DIR [--probe]      on a GPU server: one multiple-choice answer per picture
  spark [--sources ...] [--per-group 4]      on the Mac, costs money: Muse Spark answers the same question
                                             for a small random sample (a second opinion), kinds_spark/

For each concept the choices are Muse Spark's listed kinds (ai/doodle_listed/<key>/kinds.json), then
"a plain, ordinary <concept>", then "can't tell, or not a <concept>" (plato.kind_options), asked as one
multiple-choice question with letters (plato.labeling_prompt). Glimmer's answer is read from the
letter logits at the first answer position (the reasoning channel is skipped, see glimmer.py), not
from generated text: each option's probability is the softmax over the option letters only. Letter
order matters to language models, so every picture is asked twice, with the listed kinds in forward
and in reversed order (the plain and can't-tell options stay last), and the two probability vectors
are averaged. "letter_mass" (the share of the full next-token distribution that falls on option
letters) checks that Glimmer is answering with a letter at all.

Sources (folders under $PLATO_DIR): ai_doodle (ai/doodle, the default prompt), ai_doodle_any,
ai_doodle_unusual, ai_doodle_listed, ai_sdxl_doodle, ai_sdxl_any, ai_sdxl_listed, and human (the 200
cached Quick, Draw! drawings per concept). Output: <out>/<source>__<key>.json, one file per group
(resumable). Copy the label files back to $PLATO_DIR/kinds/ for scripts/plato_variety_analyze.py.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab.plato import (BY_KEY, CONCEPTS, LETTERS, PLATO_DIR, kind_options, labeling_prompt,  # noqa: E402
                                 load_dir)

SOURCES = {"ai_doodle": "ai/doodle", "ai_doodle_any": "ai/doodle_any", "ai_doodle_unusual": "ai/doodle_unusual",
           "ai_doodle_listed": "ai/doodle_listed", "ai_sdxl_doodle": "ai/sdxl_doodle", "ai_sdxl_any": "ai/sdxl_any",
           "ai_sdxl_listed": "ai/sdxl_listed", "human": "human"}
SIDE = 448  # 32 x 32 patches of 14 px -> 256 image tokens


def letter_ids(tokenizer, n: int) -> list[list[int]]:
    """Token ids that start each option letter: 'A' and ' A' (never lowercase 'a', the article)."""
    out = []
    for letter in LETTERS[:n]:
        ids = set()
        for variant in (letter, " " + letter):
            toks = tokenizer(variant, add_special_tokens=False)["input_ids"]
            if len(toks) == 1:
                ids.add(toks[0])
        if not ids:
            raise ValueError(f"no single-token id for option letter {letter!r}")
        out.append(sorted(ids))
    return out


def option_probs(logits, ids: list[list[int]]):
    """(softmax over option letters, letter mass) from next-token logits (B, V)."""
    import torch

    logp = torch.log_softmax(logits.float(), dim=-1)
    per = torch.stack([torch.logsumexp(logp[:, i], dim=-1) for i in ids], dim=1)  # (B, n_options)
    return torch.softmax(per, dim=1).cpu().numpy(), per.exp().sum(1).cpu().numpy()


def cmd_prepare(args):
    from PIL import Image

    from metalesionlab.plato import ink_crop

    root = PLATO_DIR / "kinds_input"
    (root / "kinds").mkdir(parents=True, exist_ok=True)
    keys = args.keys or [c.key for c in CONCEPTS]
    for key in keys:
        src = PLATO_DIR / "ai" / "doodle_listed" / key / "kinds.json"
        if src.exists():
            (root / "kinds" / f"{key}.json").write_text(src.read_text())
    made = 0
    for source in args.sources:
        for key in keys:
            files = load_dir(PLATO_DIR / SOURCES[source] / key)
            out = root / source / key
            for f in files:
                if not (out / f.name).exists():
                    out.mkdir(parents=True, exist_ok=True)
                    ink_crop(Image.open(f).convert("RGB"), side=SIDE).save(out / f.name)
                    made += 1
    print(f"prepared {made} new pictures in {root}")


def cmd_label(args):
    import torch

    from metalesionlab import glimmer
    from metalesionlab.model_lab import build_batches, to_device
    from PIL import Image

    keys = args.keys or [c.key for c in CONCEPTS]
    args.out.mkdir(parents=True, exist_ok=True)
    todo = []
    for source in args.sources:
        for key in keys:
            files = load_dir(args.input / source / key)
            out = args.out / f"{source}__{key}.json"
            if files and (args.probe or not out.exists()):
                todo.append((source, key, files[:4] if args.probe else files, out))
    print(f"{len(todo)} groups, {sum(len(t[2]) for t in todo)} pictures", flush=True)
    if not todo:
        return
    t0 = time.time()
    model, processor = glimmer.load(fp8=True)
    print(f"loaded Glimmer in {time.time() - t0:.0f}s", flush=True)
    tok = processor.tokenizer
    for source, key, files, out in todo:
        c = BY_KEY[key]
        kinds = json.loads((args.input / "kinds" / f"{key}.json").read_text())[:c.n_ai]
        fwd, rev = kind_options(c, kinds), kind_options(c, kinds[::-1])
        k = len(kinds)
        back = list(range(k - 1, -1, -1)) + [k, k + 1]  # reversed position j holds forward option back[j]
        ids = letter_ids(tok, len(fwd))
        images = [Image.open(f).convert("RGB") for f in files]
        t1 = time.time()
        probs, masses = {}, {}
        for name, opts in (("fwd", fwd), ("rev", rev)):
            prompt = labeling_prompt(c, opts)
            p_all, m_all = [], []
            for batch in build_batches(processor, [(im, prompt) for im in images], args.batch):
                with torch.no_grad():
                    logits = model(**to_device(batch, model.device), logits_to_keep=1).logits[:, -1]
                p, m = option_probs(logits, ids)
                p_all.append(p)
                m_all.append(m)
            probs[name], masses[name] = np.concatenate(p_all), np.concatenate(m_all)
        p_rev = np.zeros_like(probs["rev"])
        p_rev[:, back] = probs["rev"]
        p = (probs["fwd"] + p_rev) / 2
        rows = [{"file": f.name, "label": int(np.argmax(p[i])), "p": [round(float(x), 4) for x in p[i]],
                 "label_fwd": int(np.argmax(probs["fwd"][i])), "label_rev": int(np.argmax(p_rev[i])),
                 "letter_mass": [round(float(masses["fwd"][i]), 4), round(float(masses["rev"][i]), 4)]}
                for i, f in enumerate(files)]
        if args.probe:
            for i, f in enumerate(files):
                r = rows[i]
                print(f"  {source:16s} {key:10s} {f.name:9s} -> {fwd[r['label']]!r} p={p[i].max():.2f} "
                      f"fwd={fwd[r['label_fwd']]!r} rev={fwd[r['label_rev']]!r} mass={r['letter_mass']}", flush=True)
            inputs = glimmer.build_inputs(processor, images[0], labeling_prompt(c, fwd), model.device)
            print("  generated for the first:", repr(glimmer.answer(model, processor, inputs, 6)), flush=True)
            continue
        out.write_text(json.dumps({"source": source, "key": key, "options": fwd, "n_kinds": k,
                                   "model": glimmer.MODEL_ID, "side": SIDE, "prompt_fwd": labeling_prompt(c, fwd),
                                   "items": rows}, indent=0))
        agree = np.mean([r["label_fwd"] == r["label_rev"] for r in rows])
        print(f"{source:16s} {key:12s} {len(files):4d} pictures in {time.time() - t1:5.1f}s; "
              f"orders agree {agree:.2f}; letter mass {np.mean([r['letter_mass'] for r in rows]):.3f}", flush=True)
    print(f"done in {time.time() - t0:.0f}s; peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


def cmd_spark(args):
    """Second opinion from Muse Spark (vision) on a sample: the same question and options (forward order),
    answered in text and parsed with plato.parse_letter. Costs money: each call is reserved in the
    variety spend log ($PLATO_DIR/spend_variety.jsonl) and stops at --budget or the shared --shared-stop."""
    from metalesionlab.meta_api import CHAT_MODEL, MetaAPI, image_data_url, spent, token_cost
    from metalesionlab.plato import parse_letter

    log = PLATO_DIR / "spend_variety.jsonl"
    mine = lambda: sum(json.loads(x)["usd"] for x in log.read_text().splitlines() if x.strip())  # noqa: E731
    root, out_dir = PLATO_DIR / "kinds_input", PLATO_DIR / "kinds_spark"
    out_dir.mkdir(parents=True, exist_ok=True)
    api = MetaAPI()
    api.client = api.client.with_options(timeout=120, max_retries=0)
    rng = np.random.default_rng(20261027)
    for source in args.sources:
        for key in args.keys or [c.key for c in CONCEPTS]:
            files = load_dir(root / source / key)
            if not files:
                continue
            c = BY_KEY[key]
            kinds = json.loads((root / "kinds" / f"{key}.json").read_text())[:c.n_ai]
            opts = kind_options(c, kinds)
            path = out_dir / f"{source}__{key}.json"
            done = json.loads(path.read_text()) if path.exists() else {"source": source, "key": key, "options": opts,
                                                                       "model": CHAT_MODEL, "items": []}
            have = {r["file"] for r in done["items"]}
            pick = [files[i] for i in sorted(rng.choice(len(files), min(args.per_group, len(files)), replace=False))]
            for f in pick:
                if f.name in have:
                    continue
                if mine() > args.budget - 0.01 or spent() > args.shared_stop:
                    print("budget reached; stopping")
                    return
                msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_data_url(f.read_bytes())}},
                                                    {"type": "text", "text": labeling_prompt(c, opts)}]}]
                for attempt in range(5):
                    try:
                        resp = api.chat(msg, reasoning_effort="minimal")
                        break
                    except Exception as e:  # noqa: BLE001 - DNS drops, rate limits
                        print(f"  {source} {key} {f.name} attempt {attempt + 1}: {type(e).__name__}", flush=True)
                        time.sleep(15 * 2 ** attempt)
                else:
                    continue
                usd = token_cost(CHAT_MODEL, resp.usage)
                with log.open("a") as fh:
                    fh.write(json.dumps({"ts": round(time.time(), 1), "kind": "chat", "usd": usd, "style": "kinds_spark",
                                         "key": key, "source": source}) + "\n")
                text = (resp.choices[0].message.content or "").strip()
                done["items"].append({"file": f.name, "answer": text[:40], "label": parse_letter(text, len(opts))})
                path.write_text(json.dumps(done, indent=0))
            print(f"{source:16s} {key:12s} {len(done['items'])} labeled; variety spend ${mine():.2f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("spark")
    p.add_argument("--sources", nargs="*", default=["ai_doodle_listed", "human", "ai_doodle"])
    p.add_argument("--keys", nargs="*")
    p.add_argument("--per-group", type=int, default=4)
    p.add_argument("--budget", type=float, default=12.0, help="cap on the variety experiment's total spend")
    p.add_argument("--shared-stop", type=float, default=40.0)
    p.set_defaults(fn=cmd_spark)
    p = sub.add_parser("prepare")
    p.add_argument("--sources", nargs="*", default=list(SOURCES))
    p.add_argument("--keys", nargs="*")
    p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("label")
    p.add_argument("--input", type=Path, required=True, help="a copy of $PLATO_DIR/kinds_input")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--sources", nargs="*", default=list(SOURCES))
    p.add_argument("--keys", nargs="*")
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--probe", action="store_true", help="4 pictures per group, print answers, write nothing")
    p.set_defaults(fn=cmd_label)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

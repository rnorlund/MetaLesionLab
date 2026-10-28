"""The invisible Forms, step 2: which emblem does each of Muse Image's doodles use? Muse Glimmer 30B labels it.

  prepare                                 on the Mac: ink-crop every main-run picture to 448 px (plato.ink_crop,
                                          as for DINOv2) into $PLATO_IDEAS_DIR/label_input/<key>/
  label --input DIR --out DIR [--probe]   on a GPU server: one multiple-choice answer and one short name per picture

The question and options are plato_ideas.labeling_prompt / options: the idea's emblems, then "something else",
then "can't tell". As in scripts/plato_kinds_label.py, Glimmer's answer is read from the letter logits at the
first answer position (the reasoning channel is skipped, glimmer.py), each option's probability being the
softmax over the option letters only. Every picture is asked twice, with the emblems in forward and in reversed
order (the last two options stay last), and the two probability vectors are averaged. "letter_mass" checks that
Glimmer is answering with a letter at all.

A second pass asks for the main symbol or figure in at most five words (plato_ideas.naming_prompt), greedy, at
most 16 new tokens. It names the "something else" pictures and gives the draw pad a short label; it changes no count.

Output: <out>/<key>.json, one file per idea (resumable). Copy them back to $PLATO_IDEAS_DIR/labels/.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from metalesionlab.plato import load_dir  # noqa: E402
from metalesionlab.plato_ideas import (BY_KEY, IDEAS, IDEAS_DIR, folder, labeling_prompt, naming_prompt,  # noqa: E402
                                       options, reverse_index, short_names)

SIDE = 448  # 32 x 32 patches of 14 px -> 256 image tokens, as in the kinds labeling


def cmd_prepare(args):
    from PIL import Image

    from metalesionlab.plato import ink_crop

    made = 0
    for key in args.keys or [i.key for i in IDEAS]:
        out = IDEAS_DIR / "label_input" / key
        for f in load_dir(folder(key)):
            if not (out / f.name).exists():
                out.mkdir(parents=True, exist_ok=True)
                ink_crop(Image.open(f).convert("RGB"), side=SIDE).save(out / f.name)
                made += 1
    print(f"prepared {made} new pictures in {IDEAS_DIR / 'label_input'}")


def cmd_label(args):
    import torch
    from PIL import Image

    from metalesionlab import glimmer
    from metalesionlab.model_lab import build_batches, to_device

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from plato_kinds_label import letter_ids, option_probs  # the kinds labeling's own letter reading

    args.out.mkdir(parents=True, exist_ok=True)
    todo = []
    for key in args.keys or [i.key for i in IDEAS]:
        files = load_dir(args.input / key)
        out = args.out / f"{key}.json"
        if files and (args.probe or not out.exists()):
            todo.append((key, files[:4] if args.probe else files, out))
    print(f"{len(todo)} ideas, {sum(len(t[1]) for t in todo)} pictures", flush=True)
    if not todo:
        return
    t0 = time.time()
    model, processor = glimmer.load(fp8=True)
    print(f"loaded Glimmer in {time.time() - t0:.0f}s", flush=True)
    tok = processor.tokenizer
    for key, files, out in todo:
        idea = BY_KEY[key]
        fwd, rev = options(idea), options(idea, reverse=True)
        back = reverse_index(len(idea.emblems))
        ids = letter_ids(tok, len(fwd))
        images = [Image.open(f).convert("RGB") for f in files]
        t1 = time.time()
        probs, masses = {}, {}
        for name, opts in (("fwd", fwd), ("rev", rev)):
            prompt = labeling_prompt(idea, opts)
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
        names = short_names(idea)
        texts = []
        for im in images:
            inputs = glimmer.build_inputs(processor, im, naming_prompt(idea), model.device)
            texts.append(glimmer.answer(model, processor, inputs, max_new_tokens=16))
        rows = [{"file": f.name, "label": int(np.argmax(p[i])), "emblem": names[int(np.argmax(p[i]))],
                 "p": [round(float(x), 4) for x in p[i]],
                 "label_fwd": int(np.argmax(probs["fwd"][i])), "label_rev": int(np.argmax(p_rev[i])),
                 "letter_mass": [round(float(masses["fwd"][i]), 4), round(float(masses["rev"][i]), 4)],
                 "name": texts[i]}
                for i, f in enumerate(files)]
        if args.probe:
            for r in rows:
                print(f"  {key:10s} {r['file']:9s} -> {r['emblem']!r} p={max(r['p']):.2f} fwd={names[r['label_fwd']]!r} "
                      f"rev={names[r['label_rev']]!r} mass={r['letter_mass']} name={r['name']!r}", flush=True)
            continue
        out.write_text(json.dumps({"key": key, "options": fwd, "short": names, "model": glimmer.MODEL_ID, "side": SIDE,
                                   "prompt_fwd": labeling_prompt(idea, fwd), "prompt_name": naming_prompt(idea),
                                   "items": rows}, indent=0))
        agree = np.mean([r["label_fwd"] == r["label_rev"] for r in rows])
        print(f"{key:10s} {len(files):3d} pictures in {time.time() - t1:5.1f}s; orders agree {agree:.2f}; "
              f"letter mass {np.mean([r['letter_mass'] for r in rows]):.3f}", flush=True)
    print(f"done in {time.time() - t0:.0f}s; peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--keys", nargs="*")
    p.set_defaults(fn=cmd_prepare)
    p = sub.add_parser("label")
    p.add_argument("--input", type=Path, required=True, help="a copy of $PLATO_IDEAS_DIR/label_input")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--keys", nargs="*")
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--probe", action="store_true", help="4 pictures per idea, print answers, write nothing")
    p.set_defaults(fn=cmd_label)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

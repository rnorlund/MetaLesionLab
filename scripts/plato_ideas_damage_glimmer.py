"""God and the other ideas, damaged: Muse Glimmer reads SDXL's pictures (GPU part; run on a lab GPU with Glimmer).

  label --run DIR --cropped DIR --out DIR [--conditions ...] [--keys ...] [--probe]

For every picture of every idea and word (docs/plato_ideas_damage_plan.md):
- the emblem: the ideas labeling's multiple choice, unchanged (plato_ideas.options / labeling_prompt, letter logits,
  forward and reversed option order averaged; scripts/plato_ideas_label.py), on the ink-cropped 448 px picture;
- P(yes) to plato_ideas_damage.PERSON (cropped picture) and CLEAN (the raw picture, as in plato_damage_glimmer);
- God's pictures also: P(yes) to BEARD and HALO (cropped);
- a short name: plato_ideas.naming_prompt, greedy, at most 16 new tokens (cropped).

The cropped copies come from the Mac (scripts/plato_ideas_damage.py crop; no scipy here). Output: <out>/<condition>.json,
one file per condition (resumable). Glimmer is intact here: only SDXL was damaged.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from metalesionlab import plato_ideas as I  # noqa: E402
from metalesionlab import plato_ideas_damage as ID  # noqa: E402

SIDE = 448


class Reader:
    def __init__(self, batch: int):
        import torch

        from metalesionlab import glimmer

        t0 = time.time()
        self.model, self.processor = glimmer.load(fp8=True)
        self.glimmer, self.torch, self.batch = glimmer, torch, batch
        tok = self.processor.tokenizer
        self.yes_no = []
        for words in (("Yes", " Yes", "yes", " yes"), ("No", " No", "no", " no")):
            got = set()
            for w in words:
                t = tok(w, add_special_tokens=False)["input_ids"]
                if len(t) == 1:
                    got.add(t[0])
            self.yes_no.append(sorted(got))
        print(f"loaded Glimmer in {time.time() - t0:.0f}s", flush=True)

    def _last_logits(self, images, prompt):
        from metalesionlab.model_lab import build_batches, to_device

        out = []
        for b in build_batches(self.processor, [(im, prompt) for im in images], self.batch):
            with self.torch.no_grad():
                out.append(self.model(**to_device(b, self.model.device), logits_to_keep=1).logits[:, -1].float())
        return self.torch.cat(out)

    def mcq(self, images, idea) -> list[dict]:
        from plato_kinds_label import letter_ids, option_probs

        fwd, rev = I.options(idea), I.options(idea, reverse=True)
        back = I.reverse_index(len(idea.emblems))
        ids = letter_ids(self.processor.tokenizer, len(fwd))
        probs, mass = {}, {}
        for name, opts in (("fwd", fwd), ("rev", rev)):
            p, m = option_probs(self._last_logits(images, I.labeling_prompt(idea, opts)), ids)
            probs[name], mass[name] = p, m
        p_rev = np.zeros_like(probs["rev"])
        p_rev[:, back] = probs["rev"]
        p = (probs["fwd"] + p_rev) / 2
        names = I.short_names(idea)
        return [{"label": int(np.argmax(p[i])), "emblem": names[int(np.argmax(p[i]))],
                 "p": [round(float(x), 4) for x in p[i]],
                 "label_fwd": int(np.argmax(probs["fwd"][i])), "label_rev": int(np.argmax(p_rev[i])),
                 "letter_mass": [round(float(mass["fwd"][i]), 4), round(float(mass["rev"][i]), 4)]}
                for i in range(len(images))]

    def yesno(self, images, prompt) -> list[float]:
        logp = self.torch.log_softmax(self._last_logits(images, prompt), dim=-1)
        yes = self.torch.logsumexp(logp[:, self.yes_no[0]], dim=-1)
        no = self.torch.logsumexp(logp[:, self.yes_no[1]], dim=-1)
        return [round(float(x), 4) for x in self.torch.sigmoid(yes - no).cpu().tolist()]

    def names(self, images, idea) -> list[str]:
        out = []
        for im in images:
            inputs = self.glimmer.build_inputs(self.processor, im, I.naming_prompt(idea), self.model.device)
            out.append(self.glimmer.answer(self.model, self.processor, inputs, max_new_tokens=16))
        return out


def cmd_label(args):
    from PIL import Image

    reader = Reader(args.batch)
    args.out.mkdir(parents=True, exist_ok=True)
    conds = sorted(p.name for p in args.run.iterdir() if p.is_dir() and (not args.conditions or p.name in args.conditions))
    conds.sort(key=lambda c: (c != "intact", c))
    for cond in conds:
        out = args.out / f"{cond}.json"
        if out.exists() and not args.probe:
            continue
        t0 = time.time()
        rows = []
        for key in args.keys or ID.IDEA_KEYS + ID.WORD_KEYS:
            folder = args.run / cond / key
            if not folder.is_dir():
                continue
            files = sorted(folder.glob("s*.png"), key=lambda p: int(p.stem[1:]))
            if args.probe:
                files = files[:4]
            idea = I.ANY[key]
            crops = [Image.open(args.cropped / cond / key / f.name).convert("RGB") for f in files]
            raws = [Image.open(f).convert("RGB").resize((SIDE, SIDE)) for f in files]
            mc = reader.mcq(crops, idea)
            person = reader.yesno(crops, ID.PERSON)
            clean = reader.yesno(raws, ID.CLEAN)
            beard = reader.yesno(crops, ID.BEARD) if key == "god" else [None] * len(files)
            halo = reader.yesno(crops, ID.HALO) if key == "god" else [None] * len(files)
            said = reader.names(crops, idea)
            for f, m, pe, cl, be, ha, nm in zip(files, mc, person, clean, beard, halo, said):
                rows.append({"key": key, "file": f.name, "seed_index": int(f.stem[1:]), **m, "p_person": pe,
                             "p_clean": cl, "p_beard": be, "p_halo": ha, "name": nm})
            if args.probe:
                for r in rows[-len(files):]:
                    print(f"  {cond:18s} {key:16s} {r['file']:7s} {r['emblem']!r:18s} person={r['p_person']:.2f} "
                          f"clean={r['p_clean']:.2f} beard={r['p_beard']} halo={r['p_halo']} name={r['name']!r}", flush=True)
        if args.probe:
            continue
        out.write_text(json.dumps({"condition": cond, "model": "meta-models/Muse-Glimmer-30B (FP8)", "side": SIDE,
                                   "questions": {"person": ID.PERSON, "clean": ID.CLEAN, "beard": ID.BEARD,
                                                 "halo": ID.HALO},
                                   "items": rows}, indent=0))
        print(f"{cond:20s} {len(rows):4d} pictures in {time.time() - t0:5.0f}s", flush=True)
    print(f"done; peak {reader.torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("label")
    p.add_argument("--run", type=Path, required=True, help="SDXL's pictures: <condition>/<key>/s<i>.png")
    p.add_argument("--cropped", type=Path, required=True, help="the Mac's 448 px ink-cropped copies, same layout")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--conditions", nargs="*")
    p.add_argument("--keys", nargs="*")
    p.add_argument("--batch", type=int, default=8)
    p.add_argument("--probe", action="store_true", help="4 pictures per key, print answers, write nothing")
    p.set_defaults(fn=cmd_label)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

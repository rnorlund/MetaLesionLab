"""Damage Meta's open AI, GPU part (docs/plato_glimmer_lesion_plan.md): a damaged Muse Glimmer 30B draws and describes.

  check-batch            greedy answers alone and in a left-padded batch must agree (the batching is harmless)
  pilot --conditions ... --n 4      small pilot that sets the dose ladders
  main [--conditions ...]           12 drawings and 12 descriptions of each thing per condition

Every condition is one generate call for the 36 drawings (3 things x 12, left-padded, stopping at the first
</svg> or the end of turn) and one for the 36 one-sentence descriptions, at temperature 1 with the same torch
seeds in every condition. Damage is a reversible hook (metalesionlab.lesions.lesion, method "zero"): weights are
never edited. Writes <out>/<cond>.json with the model's raw text per sample.

Usage (on a lab GPU, ~/MetaLesionLab_glesion is this repo's code):
  python scripts/plato_glimmer_lesion_run.py check-batch
  python scripts/plato_glimmer_lesion_run.py pilot --out ~/glimmer_lesion/pilot --n 4 --conditions intact all@0.1 ...
  python scripts/plato_glimmer_lesion_run.py main --out ~/glimmer_lesion/raw
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalesionlab import plato_glimmer_lesion as gl  # noqa: E402

SVG_RE = re.compile(r"<svg\b.*?</svg\s*>", re.I | re.S)


class Runner:
    def __init__(self, device: str = "cuda:0"):
        import torch

        from metalesionlab import glimmer

        self.torch, self.glimmer = torch, glimmer
        t0 = time.time()
        self.model, self.proc = glimmer.load(fp8=True, device=device)
        self.tok = self.proc.tokenizer
        self.device = device
        print(f"loaded Glimmer in {time.time() - t0:.0f}s, {torch.cuda.memory_allocated() / 2**30:.1f} GiB", flush=True)
        ids = set()
        for src in (getattr(self.model, "generation_config", None), self.tok):
            e = getattr(src, "eos_token_id", None)
            if e is not None:
                ids.update(e if isinstance(e, (list, tuple)) else [e])
        for t in (glimmer.END_OF_TURN, "<|eom|>"):
            i = self.tok.convert_tokens_to_ids(t)
            if isinstance(i, int) and i >= 0:
                ids.add(i)
        self.eos = sorted(ids)
        self.pad = self.tok.pad_token_id if self.tok.pad_token_id is not None else self.eos[0]

    def batch(self, prompts: list[str]) -> dict:
        """Left-padded chat inputs for text-only prompts (the answer prefix pre-filled, as in the scale run)."""
        torch = self.torch
        rows = [self.glimmer.build_inputs(self.proc, None, p, self.device) for p in prompts]
        width = max(r["input_ids"].shape[1] for r in rows)
        ids, mask = [], []
        for r in rows:
            k = width - r["input_ids"].shape[1]
            ids.append(torch.cat([torch.full((1, k), self.pad, dtype=r["input_ids"].dtype, device=self.device),
                                  r["input_ids"]], 1))
            mask.append(torch.cat([torch.zeros((1, k), dtype=r["attention_mask"].dtype, device=self.device),
                                   r["attention_mask"]], 1))
        return {"input_ids": torch.cat(ids), "attention_mask": torch.cat(mask)}

    def generate(self, prompts: list[str], seed: int, max_new: int, svg: bool, sample: bool = True) -> list[dict]:
        torch = self.torch
        inputs = self.batch(prompts)
        n_in = inputs["input_ids"].shape[1]
        torch.manual_seed(seed)
        kw = dict(do_sample=True, temperature=gl.TEMP, top_p=1.0, top_k=0, min_p=None) if sample else dict(do_sample=False)
        if svg:
            kw.update(stop_strings=["</svg>"], tokenizer=self.tok)
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=max_new, repetition_penalty=1.0, pad_token_id=self.pad,
                                      eos_token_id=self.eos, **kw)
        rows = []
        for row in out[:, n_in:].tolist():
            first = next((i for i, t in enumerate(row) if t in self.eos), None)
            eos = first is not None
            ids = row[:first] if eos else row
            while ids and ids[-1] == self.pad:
                ids = ids[:-1]
            text = self.tok.decode(ids, skip_special_tokens=False)
            text = text.split(self.glimmer.END_OF_TURN)[0].split("<|eom|>")[0].strip()
            if svg and text.rstrip().lower().endswith("</svg>"):
                stop = "svg_end"
            elif eos:
                stop = "end_of_turn"
            elif len(row) >= max_new and not eos:
                stop = "max_tokens"
            else:
                stop = "other"
            rows.append({"text": text, "n_tokens": len(ids), "stop": stop, "finished": stop != "max_tokens"})
        return rows

    def condition(self, cond: str, n: int, out: Path) -> dict:
        from metalesionlab.lesions import LesionSpec, lesion

        if cond == "intact":
            spec = LesionSpec(name="intact")
        else:
            t, dose = gl.parse_condition(cond)
            spec = LesionSpec.from_dict(gl.lesion_spec_dict(t, dose))
        t0 = time.time()
        with lesion(self.model, spec):
            draws = self.generate([t.draw for t in gl.THINGS for _ in range(n)], gl.SVG_SEED, gl.MAX_SVG_TOKENS, svg=True)
            t1 = time.time()
            descs = self.generate([t.describe for t in gl.THINGS for _ in range(n)], gl.DESC_SEED, gl.MAX_DESC_TOKENS,
                                  svg=False)
        t2 = time.time()
        rec = {"condition": cond, "n": n, "temp": gl.TEMP, "svg_seed": gl.SVG_SEED, "desc_seed": gl.DESC_SEED,
               "unit_seed": gl.UNIT_SEED, "spec": spec.to_dict(units=False), "gpu": self.torch.cuda.get_device_name(0),
               "seconds": {"draw": round(t1 - t0, 1), "describe": round(t2 - t1, 1)},
               "things": {}}
        for j, t in enumerate(gl.THINGS):
            rec["things"][t.key] = {"draw_prompt": t.draw, "describe_prompt": t.describe,
                                    "draw": [{"i": i, **draws[j * n + i]} for i in range(n)],
                                    "describe": [{"i": i, **descs[j * n + i]} for i in range(n)]}
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{cond}.json").write_text(json.dumps(rec, indent=1))
        summary = []
        for t in gl.THINGS:
            th = rec["things"][t.key]
            svgs = sum(bool(SVG_RE.search(s["text"])) for s in th["draw"])
            named = sum(gl.names_thing(s["text"], t.key) for s in th["describe"])
            summary.append(f"{t.key}: svg {svgs}/{n}, named {named}/{n}")
        print(f"{cond:14s} {'; '.join(summary)}; draw {rec['seconds']['draw']:.0f}s, describe "
              f"{rec['seconds']['describe']:.0f}s", flush=True)
        for t in gl.THINGS:
            print(f"   {t.key} says: {rec['things'][t.key]['describe'][0]['text'][:160]!r}", flush=True)
        return rec


def cmd_check_batch(args):
    r = Runner()
    prompts = [t.draw for t in gl.THINGS] + [t.describe for t in gl.THINGS]
    alone = [r.generate([p], 0, 48, svg=False, sample=False)[0]["text"] for p in prompts]
    together = [x["text"] for x in r.generate(prompts, 0, 48, svg=False, sample=False)]
    same = [a == b for a, b in zip(alone, together)]
    for p, a, b, s in zip(prompts, alone, together, same):
        print(f"{'SAME' if s else 'DIFF'} {p[:40]!r}\n  alone:    {a[:120]!r}\n  together: {b[:120]!r}", flush=True)
    print(f"{sum(same)}/{len(same)} identical", flush=True)


def cmd_run(args, default_n: int):
    r = Runner()
    conds = args.conditions or gl.conditions()
    t_all = time.time()
    for cond in conds:
        if (args.out / f"{cond}.json").exists():
            print(f"{cond}: done already", flush=True)
            continue
        r.condition(cond, args.n or default_n, args.out)
    print(f"all done in {(time.time() - t_all) / 60:.1f} min", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check-batch")
    for name in ("pilot", "main"):
        p = sub.add_parser(name)
        p.add_argument("--out", type=Path, required=True)
        p.add_argument("--conditions", nargs="*")
        p.add_argument("--n", type=int, default=None)
    args = ap.parse_args()
    if args.cmd == "check-batch":
        cmd_check_batch(args)
    elif args.cmd == "pilot":
        if not args.conditions:
            ap.error("pilot needs --conditions")
        cmd_run(args, 4)
    else:
        cmd_run(args, gl.N)


if __name__ == "__main__":
    main()

"""Plato's Cave and Cratylus on Muse Glimmer (GPU part, run on an Axon L40S).

  cave    STIMULI_DIR   names every picture of every version (stimuli/<version>/<word>.png, words and
                        alternates from stimuli/meta.json) with the naming prompt, greedy decoding and the
                        full word lens -> OUT/cave_glimmer.json
  choice                Cratylus choice arm: code-drawn round/spiky pairs, "Which one is '<word>'?",
                        p(left) vs p(right) from the first answer token, both placements; plus the
                        no-picture version (A/B) -> OUT/cratylus_choice_glimmer.json
  all     STIMULI_DIR   both, loading the model once

Reuses plato_glimmer.Probe (the Plato's Chair inside-Glimmer pass) for naming and the word lens.
"""
import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import torch

from metalesionlab import glimmer
from metalesionlab import plato_cratylus as pk
from metalesionlab.plato_glimmer import PROMPT, Probe, save_json

N_PAIRS = 8


@dataclass
class CavePicture:
    key: str          # the word
    source: str       # the version
    path: str
    index: int
    target: str
    alternates: tuple[str, ...] = field(default_factory=tuple)


def cave_pictures(stimuli: Path) -> list[CavePicture]:
    meta = json.loads((stimuli / "meta.json").read_text())
    pics = []
    for version in meta["versions"]:
        for i, it in enumerate(meta["items"]):
            pics.append(CavePicture(it["word"], version, str(stimuli / version / f"{it['word']}.png"), i, it["word"],
                                    tuple(it["alternates"])))
    return pics


def run_cave(model, processor, stimuli: Path, out: Path, batch: int):
    pics = cave_pictures(stimuli)
    probe = Probe.build(processor, pics, batch_size=batch)
    t0 = time.time()
    r = probe.run(model, processor, None, None, full_lens=True, keep_tops=True, condition="intact")
    r["prompt"] = PROMPT
    r["pictures"] = [{"word": p.key, "version": p.source, "alternates": list(p.alternates)} for p in pics]
    save_json(r, out / "cave_glimmer.json")
    by = {}
    for row in r["items"]:
        by.setdefault(row["source"], []).append(row["code"] == "Correct")
    print({k: round(sum(v) / len(v), 3) for k, v in by.items()}, f"{time.time() - t0:.0f}s", flush=True)


@torch.no_grad()
def answer_probs(model, processor, examples, options: dict[str, list[int]], batch: int) -> list[dict]:
    """For each (image, prompt): the probability of each option (summed over its first-token ids) from
    the first answer token, plus the mass of all options together."""
    from metalesionlab.model_lab import build_batches, to_device

    out = []
    for b in build_batches(processor, examples, batch):
        logits = model(**to_device(b, model.device), logits_to_keep=1).logits[:, -1].float()
        probs = torch.softmax(logits, -1)
        top = logits.argmax(-1).tolist()
        for k in range(probs.shape[0]):
            row = {name: float(probs[k, ids].sum()) for name, ids in options.items()}
            row["top"] = processor.tokenizer.decode([top[k]])
            out.append(row)
    return out


def run_choice(model, processor, out: Path, batch: int):
    tok = processor.tokenizer
    words = [w.word for w in pk.WORDS] + pk.CHOICE_EXTRA
    side_ids = {"left": glimmer.target_token_ids(tok, "left"), "right": glimmer.target_token_ids(tok, "right")}
    letter_ids = {"A": glimmer.target_token_ids(tok, "A"), "B": glimmer.target_token_ids(tok, "B")}
    assert not set(side_ids["left"]) & set(side_ids["right"]) and not set(letter_ids["A"]) & set(letter_ids["B"])
    rows, examples = [], []
    for word in words:
        for pair in range(N_PAIRS):
            r, s = pk.round_shape(pair), pk.spiky_shape(pair)
            for round_side in ("left", "right"):
                img = pk.pair_image(r, s) if round_side == "left" else pk.pair_image(s, r)
                examples.append((img, pk.choice_prompt(word)))
                rows.append({"word": word, "pair": pair, "round_side": round_side})
    t0 = time.time()
    for row, p in zip(rows, answer_probs(model, processor, examples, side_ids, batch)):
        mass = p["left"] + p["right"]
        row.update({"p_left": p["left"], "p_right": p["right"], "mass": mass, "top": p["top"],
                    "p_round": (p[row["round_side"]] / mass) if mass > 0 else None})
    text_rows, text_examples = [], []
    for word in words:
        for round_first in (True, False):
            text_examples.append((None, pk.text_choice_prompt(word, round_first)))
            text_rows.append({"word": word, "round_first": round_first})
    for row, p in zip(text_rows, answer_probs(model, processor, text_examples, letter_ids, batch)):
        mass = p["A"] + p["B"]
        p_round = (p["A"] if row["round_first"] else p["B"]) / mass if mass > 0 else None
        row.update({"p_A": p["A"], "p_B": p["B"], "mass": mass, "top": p["top"], "p_round": p_round})
    save_json({"prompt": pk.choice_prompt("<word>"), "text_prompt": pk.text_choice_prompt("<word>", True),
               "n_pairs": N_PAIRS, "side_token_ids": side_ids, "letter_token_ids": letter_ids,
               "image": rows, "text": text_rows}, out / "cratylus_choice_glimmer.json")
    for word in ("bouba", "kiki", "maluma", "takete"):
        ps_ = [r["p_round"] for r in rows if r["word"] == word]
        pt = [r["p_round"] for r in text_rows if r["word"] == word]
        print(f"{word}: p(round) picture {sum(ps_) / len(ps_):.3f}, text {sum(pt) / len(pt):.3f}", flush=True)
    print(f"choice done in {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cave", "choice", "all"])
    ap.add_argument("stimuli", type=Path, nargs="?")
    ap.add_argument("--out", type=Path, default=Path("runs/plato_cave"))
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(0)
    t0 = time.time()
    model, processor = glimmer.load()
    print(f"loaded in {time.time() - t0:.0f}s", flush=True)
    if args.cmd in ("choice", "all"):
        run_choice(model, processor, args.out, args.batch)
    if args.cmd in ("cave", "all"):
        run_cave(model, processor, args.stimuli, args.out, args.batch)
    print("done", flush=True)


if __name__ == "__main__":
    main()

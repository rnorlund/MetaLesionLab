"""GPU check for the lesion engine on a Test Studio set.

1. Batched naming (left padding, own greedy loop) gives the same answers as glimmer.answer.
2. The batched word lens matches glimmer.word_lens.
3. Lesions are reversible: an intact run after a lesioned run reproduces the first intact run.
4. Timing for a few batch sizes.

Usage: python scripts/lesion_check.py runs/sets/demo_en [--batch 10]
"""
import argparse
import time
from pathlib import Path

import torch
from PIL import Image

from metalesionlab import glimmer
from metalesionlab.lesions import LesionSpec
from metalesionlab.model_lab import NamingTest, naming_prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("set_dir", type=Path)
    ap.add_argument("--batch", type=int, nargs="+", default=[1, 5, 10, 20])
    ap.add_argument("--single", type=int, default=3, help="items to compare with the single-item path")
    args = ap.parse_args()

    t0 = time.time()
    model, processor = glimmer.load()
    print(f"loaded in {time.time() - t0:.0f}s")
    test = NamingTest.from_set(processor, args.set_dir, batch_size=max(args.batch))
    print(f"{len(test.items)} items; prompt tokens {test.batches[0]['input_ids'].shape[1]}; "
          f"batch keys {sorted(test.batches[0])}")

    intact = test.run(model, processor, condition="intact")  # also warms up the FP8 kernels
    intact = test.run(model, processor, condition="intact")
    print(f"intact accuracy {intact['accuracy']} ({intact['seconds']}s, {intact['items_per_s']} items/s)")
    for r in intact["items"]:
        print(f"  {r['word']:>12} -> {r['said']!r:16} {r['code']:10} p_final={r['lens']['p_correct'][-1]}")

    tok = processor.tokenizer
    for it, r in list(zip(test.items, intact["items"]))[:args.single]:
        inputs = glimmer.build_inputs(processor, Image.open(it.image).convert("RGB"), naming_prompt(it.lang), model.device)
        single = glimmer.answer(model, processor, inputs)
        lens = glimmer.word_lens(model, inputs)
        p = lens["logprobs"][:, glimmer.target_token_ids(tok, it.word)].exp().max(-1).values
        dmax = max(abs(a - b) for a, b in zip(p.tolist(), r["lens"]["p_correct"]))
        print(f"  single {it.word}: answer {single!r} vs batched {r['said']!r}; max |dp| over layers {dmax:.4f}")

    band = LesionSpec(method="zero", layers=list(range(20, 26)), name="zero L20-25")
    lesioned = test.run(model, processor, band)
    print(f"{band.name}: accuracy {lesioned['accuracy']} counts {lesioned['counts']}")
    print("  said:", [r["said"] for r in lesioned["items"]])
    again = test.run(model, processor, condition="intact again")
    same = [a["said"] == b["said"] for a, b in zip(intact["items"], again["items"])]
    dp = max(abs(x - y) for a, b in zip(intact["items"], again["items"])
             for x, y in zip(a["lens"]["p_correct"], b["lens"]["p_correct"]))
    print(f"reversible: {sum(same)}/{len(same)} answers identical; max |dp| {dp:.5f}")

    for bs in args.batch:
        t = NamingTest.from_set(processor, args.set_dir, batch_size=bs)
        r = t.run(model, processor)
        print(f"batch {bs:3d}: {r['seconds']}s for {r['n']} items = {r['items_per_s']} items/s; "
              f"peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB")
        torch.cuda.reset_peak_memory_stats()


if __name__ == "__main__":
    main()

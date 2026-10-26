"""Day-1 check: Glimmer loads on one L40S, names a picture, and the word lens agrees with the model.

Usage: python scripts/glimmer_probe.py IMAGE TARGET_WORD
"""
import sys
import time

import torch
from PIL import Image

from metalesionlab import glimmer


def main():
    image_path, target = sys.argv[1], sys.argv[2]
    t0 = time.time()
    model, processor = glimmer.load()
    print(f"loaded in {time.time() - t0:.0f}s; GPU memory {torch.cuda.memory_allocated() / 2**30:.1f} GiB")
    print("top-level modules:", [n for n, _ in model.model.named_children()], "| lm_head:", type(model.lm_head).__name__)
    print("decoder layer 0:", [n for n, _ in glimmer.decoder_layers(model)[0].named_children()])
    print("text config caps:", {k: v for k, v in model.config.get_text_config().to_dict().items() if "cap" in k})

    image = Image.open(image_path).convert("RGB")
    inputs = glimmer.build_inputs(processor, image, "Name the object in this picture with exactly one word.", model.device)
    print(f"prompt tokens: {inputs['input_ids'].shape[1]}")

    t0 = time.time()
    print(f"answer: {glimmer.answer(model, processor, inputs)!r} ({time.time() - t0:.2f}s)")

    t0 = time.time()
    lens = glimmer.word_lens(model, inputs)
    print(f"word lens forward: {time.time() - t0:.2f}s")
    diff = (lens["lens_final_logits"] - lens["final_logits"]).abs().max().item()
    print(f"lens vs model logits at last layer, max |diff|: {diff:.4f}")

    tok = processor.tokenizer
    tids = glimmer.target_token_ids(tok, target)
    p_target = lens["logprobs"][:, tids].exp().max(dim=-1).values
    for layer in range(0, len(p_target), 3):
        tops = [tok.decode([int(i)]) for i in lens["top_ids"][layer][:3]]
        print(f"layer {layer + 1:2d}  p({target})={p_target[layer]:.3f}  top3={tops}")
    print(f"layer {len(p_target):2d}  p({target})={p_target[-1]:.3f}")
    print(f"peak memory {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB")


if __name__ == "__main__":
    main()

"""Load Muse Glimmer and query it with the reasoning channel skipped.

Glimmer's chat template writes a final answer as '<|start|>assistant to=user<|message|>...'.
Pre-filling ' to=user<|message|>' after the generation prompt makes the next token the
first token of the answer, so naming needs no reasoning and the word lens reads the answer
from a single forward pass.
"""
from __future__ import annotations

import torch

MODEL_ID = "meta-models/Muse-Glimmer-30B"
ANSWER_PREFIX = " to=user<|message|>"
END_OF_TURN = "<|eot|>"


def load(fp8: bool = True, device: str = "cuda:0"):
    """Glimmer on one GPU. BF16 is 60 GB, so a 48 GB card needs FP8 for the decoder;
    the vision tower and lm_head stay in BF16."""
    from transformers import AutoModelForMultimodalLM, AutoProcessor, FineGrainedFP8Config

    processor = AutoProcessor.from_pretrained(MODEL_ID)
    kwargs = {}
    if fp8:
        # Patterns are matched from the start of the full module name.
        kwargs["quantization_config"] = FineGrainedFP8Config(modules_to_not_convert=[
            "model.vision_tower", "model.vision_adapter", "model.vision_projection", "lm_head"])
    model = AutoModelForMultimodalLM.from_pretrained(
        MODEL_ID, dtype=torch.bfloat16, device_map=device, **kwargs).eval()
    return model, processor


def decoder_layers(model):
    return model.model.language_model.layers


def build_inputs(processor, image, prompt: str, device, max_side: int = 512) -> dict:
    """Chat-formatted inputs for one image + prompt, ending at the start of the answer.
    Images are shrunk to max_side pixels: a 1600 px picture costs ~3,400 tokens."""
    if max(image.size) > max_side:
        image = image.copy()
        image.thumbnail((max_side, max_side))
    messages = [{"role": "user", "content": [{"type": "image", "image": image},
                                              {"type": "text", "text": prompt}]}]
    inputs = processor.apply_chat_template(messages, tokenize=True, return_dict=True, return_tensors="pt",
                                           add_generation_prompt=True, reasoning_strength="low")
    prefix = processor.tokenizer(ANSWER_PREFIX, add_special_tokens=False, return_tensors="pt")["input_ids"]
    inputs["input_ids"] = torch.cat([inputs["input_ids"], prefix], dim=1)
    inputs["attention_mask"] = torch.cat([inputs["attention_mask"], torch.ones_like(prefix)], dim=1)
    return inputs.to(device)


@torch.no_grad()
def answer(model, processor, inputs: dict, max_new_tokens: int = 8) -> str:
    out = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    text = processor.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=False)
    return text.split(END_OF_TURN)[0].split("<|eom|>")[0].strip()


def output_logits(model, normed_hidden: torch.Tensor) -> torch.Tensor:
    """Glimmer's output head after the final norm: lm_head, times output_multiplier, then a
    tanh softcap (T * tanh(x / T)). Mirrors the model's own forward."""
    cfg = model.config.get_text_config()
    logits = model.lm_head(normed_hidden).float() * cfg.output_multiplier
    cap = cfg.final_logit_softcapping
    return torch.tanh(logits / cap) * cap


@torch.no_grad()
def word_lens(model, inputs: dict, top_k: int = 5) -> dict:
    """Logit lens at the answer position: decode the residual stream after every decoder layer
    through the final norm and lm_head. Returns per-layer log-probs over the vocabulary's top_k
    plus the full final-layer logits for checking against the model's own output."""
    lm = model.model.language_model
    captured = []
    hooks = [layer.register_forward_hook(lambda _m, _i, out: captured.append(
        (out[0] if isinstance(out, tuple) else out)[0, -1].detach()))
        for layer in decoder_layers(model)]
    try:
        logits = model(**inputs).logits[0, -1].float()
    finally:
        for h in hooks:
            h.remove()
    resid = torch.stack(captured)  # (layers, hidden)
    lens_logits = output_logits(model, lm.norm(resid))  # (layers, vocab)
    logprobs = torch.log_softmax(lens_logits, dim=-1)
    top = logprobs.topk(top_k, dim=-1)
    return {"logprobs": logprobs, "top_ids": top.indices, "top_logprobs": top.values, "final_logits": logits,
            "lens_final_logits": lens_logits[-1]}


def target_token_ids(tokenizer, word: str) -> list[int]:
    """First-token ids for a word's spacing and capitalization variants."""
    ids = set()
    for variant in {word, word.lower(), word.capitalize(), " " + word, " " + word.lower(), " " + word.capitalize()}:
        toks = tokenizer(variant, add_special_tokens=False)["input_ids"]
        if toks:
            ids.add(toks[0])
    return sorted(ids)

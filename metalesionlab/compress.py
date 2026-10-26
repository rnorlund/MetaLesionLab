"""What can I cut? Remove whole decoder layers while the user's own tests guard the abilities that matter.

Method:
  1. Skip a layer reversibly (SkipLayers): its forward returns its input, so the residual stream
     passes through unchanged. A skipped layer still writes zero keys and values to the KV cache:
     the attention masks and generation read cache lengths from the first full-attention and the
     first sliding-window layer, so those lengths must stay right even when that layer is skipped.
  2. Two guards score every configuration:
     a) picture-naming accuracy on Test Studio sets (the answer channel is pre-filled, as in
        glimmer.build_inputs; answers are coded with naming_errors.classify, without the meaning
        judge, which never changes "Correct");
     b) next-token perplexity on plain sentences written by Muse Spark
        (public_data/general_text_guard.json), so a cut that keeps naming but breaks ordinary
        language is caught.
     The vision tower is never cut, so each picture's image features are computed once and reused.
  3. Importance scan: skip each layer alone and record the change in accuracy and perplexity. A
     cheaper score needs no skipping: block influence, 1 - cos(layer input, layer output) at the
     answer position (Men et al. 2024, "ShortGPT", arXiv:2403.03853).
  4. Greedy removal (greedy_path): each step scores every remaining layer by the perplexity after
     also skipping it, runs the naming test on the `shortlist` cheapest, and removes the one that
     keeps naming best (ties go to lower perplexity). The path runs past the guard, so the whole
     trade-off curve is recorded; `within_guard` marks the steps a user would accept.
  5. Real removal (remove_layers): delete the layers from the ModuleList, renumber each attention's
     layer_idx (its KV-cache slot) and shorten every per-layer config list (num_hidden_layers,
     layer_types, layer_rope_theta). The stock forward and cache then see a shorter model, and its
     outputs match the skip version.

Guard thresholds:
  ACC_FLOOR      naming accuracy, pooled over the guard sets, must stay at or above 95% of intact.
  PPL_TOLERANCE  perplexity may rise at most 10% above intact. That is about one model-size step in
                 an open family (Llama 2 13B -> 7B raises WikiText-2 perplexity from 4.88 to 5.47,
                 +12%), so a cut that costs more is worse than switching to a smaller model.
"""
from __future__ import annotations

import gc
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

import torch
import torch.nn.functional as F

from metalesionlab import glimmer
from metalesionlab.naming_errors import classify

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_TEXT = REPO_ROOT / "public_data" / "general_text_guard.json"
ACC_FLOOR = 0.95
PPL_TOLERANCE = 0.10
NAMING_PROMPTS = {
    "en": "Name the object in this picture with exactly one word.",
    # The Model Lab's Spanish wording: one-word answers for 19/19 demo_es pictures (Oct 26).
    "es": "Di el nombre del objeto con una sola palabra en español. Solo la palabra, sin artículo.",
}
GEN_PROMPT = "Describe a busy kitchen in a few sentences."


# --- model structure -------------------------------------------------------------------------

def decoder_stack(model) -> torch.nn.Module:
    """The module that owns the decoder layers: Glimmer's language model, or model.model for a
    Llama-style causal LM."""
    inner = model.model
    return getattr(inner, "language_model", inner)


def decoder_layers(model) -> torch.nn.ModuleList:
    return decoder_stack(model).layers


def text_configs(model) -> list:
    """Every distinct config object describing the decoder. The top-level text config and the
    decoder's own config can be separate objects; both must be edited."""
    out = []
    for cfg in (model.config.get_text_config(), decoder_stack(model).config):
        if not any(cfg is c for c in out):
            out.append(cfg)
    return out


def layer_types(model) -> list[str]:
    cfg = model.config.get_text_config()
    return list(getattr(cfg, "layer_types", None) or ["full_attention"] * cfg.num_hidden_layers)


# --- reversible skipping -----------------------------------------------------------------------

def _passthrough(layer, cfg) -> Callable:
    attn = getattr(layer, "self_attn", None)
    idx = getattr(attn, "layer_idx", None)
    n_kv = cfg.num_key_value_heads
    head_dim = getattr(cfg, "head_dim", None) or cfg.hidden_size // cfg.num_attention_heads

    def forward(hidden_states, *args, **kwargs):
        cache = kwargs.get("past_key_values", kwargs.get("past_key_value"))
        if cache is not None and idx is not None:
            shape = (hidden_states.shape[0], n_kv, hidden_states.shape[1], head_dim)
            cache.update(hidden_states.new_zeros(shape), hidden_states.new_zeros(shape), idx)
        return hidden_states

    return forward


class SkipLayers:
    """Skip decoder layers until remove() or the end of a with-block: each returns its input."""

    def __init__(self, model, layers: Iterable[int]):
        cfg = model.config.get_text_config()
        stack = decoder_layers(model)
        self.layers = [stack[i] for i in sorted(set(layers))]
        for layer in self.layers:
            layer.forward = _passthrough(layer, cfg)  # instance attribute shadows the class forward

    def remove(self) -> None:
        for layer in self.layers:
            layer.__dict__.pop("forward", None)
        self.layers = []

    def __enter__(self) -> SkipLayers:
        return self

    def __exit__(self, *exc) -> None:
        self.remove()


# --- real removal ------------------------------------------------------------------------------

def prune_layer_fields(cfg, keep: Sequence[int]) -> list[str]:
    """Shorten every per-layer list on a decoder config to the kept layers and set
    num_hidden_layers. A per-layer list is any public list or tuple field as long as the layer
    count. Returns the names of the fields changed."""
    n = cfg.num_hidden_layers
    keep = sorted(keep)
    if len(set(keep)) != len(keep) or any(not 0 <= i < n for i in keep):
        raise ValueError(f"keep must be distinct layer indices in [0, {n})")
    changed = []
    for name, value in list(vars(cfg).items()):
        if not name.startswith("_") and isinstance(value, (list, tuple)) and len(value) == n:
            setattr(cfg, name, type(value)(value[i] for i in keep))
            changed.append(name)
    cfg.num_hidden_layers = len(keep)
    return ["num_hidden_layers"] + changed


def remove_layers(model, layers: Iterable[int]) -> dict:
    """Delete decoder layers for real. Renumbers each kept layer's attention (its KV-cache slot) and
    edits the config so the stock forward, the KV cache and save_pretrained see a shorter model."""
    stack = decoder_stack(model)
    n = len(stack.layers)
    drop = sorted(set(layers))
    if any(not 0 <= i < n for i in drop):
        raise ValueError(f"layer indices must be in [0, {n})")
    keep = [i for i in range(n) if i not in drop]
    stack.layers = torch.nn.ModuleList([stack.layers[i] for i in keep])
    for j, layer in enumerate(stack.layers):
        for mod in (layer, getattr(layer, "self_attn", None)):
            if mod is not None and hasattr(mod, "layer_idx"):
                mod.layer_idx = j
    fields = [prune_layer_fields(cfg, keep) for cfg in text_configs(model)][0]
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return {"removed": drop, "kept": keep, "fields": fields}


# --- batching and decoding ---------------------------------------------------------------------

def left_pad(seqs: Sequence[torch.Tensor], pad_id: int) -> dict:
    """Left-pad 1-D id tensors so the last position is the answer position in every row. Position
    ids count from each row's first real token."""
    T = max(len(s) for s in seqs)
    ids = torch.full((len(seqs), T), pad_id, dtype=torch.long)
    mask = torch.zeros((len(seqs), T), dtype=torch.long)
    for i, s in enumerate(seqs):
        ids[i, T - len(s):] = s
        mask[i, T - len(s):] = 1
    return {"input_ids": ids, "attention_mask": mask, "position_ids": (mask.cumsum(-1) - 1).clamp_min(0)}


def stop_token_ids(model, tokenizer) -> set[int]:
    eos = model.generation_config.eos_token_id
    ids = set(eos if isinstance(eos, list) else [eos] if eos is not None else [])
    for tok in (glimmer.END_OF_TURN, "<|eom|>"):
        tid = tokenizer.convert_tokens_to_ids(tok)
        if isinstance(tid, int) and tid != tokenizer.unk_token_id:
            ids.add(tid)
    return ids


@torch.no_grad()
def greedy_decode(model, batch: dict, stop_ids: set[int], max_new_tokens: int) -> list[list[int]]:
    """Greedy decoding with a KV cache over a left-padded batch. Rows are cut at the first stop
    token; with no stop ids every row gets exactly max_new_tokens."""
    out = model(**batch, use_cache=True, logits_to_keep=1)
    past, mask, pos = out.past_key_values, batch["attention_mask"], batch["position_ids"][:, -1:]
    nxt = out.logits[:, -1].argmax(-1)
    stops = torch.tensor(sorted(stop_ids) or [-1], device=nxt.device)
    tokens, done = [nxt], torch.isin(nxt, stops)
    for _ in range(max_new_tokens - 1):
        if bool(done.all()):
            break
        mask = torch.cat([mask, torch.ones_like(mask[:, :1])], dim=1)
        pos = pos + 1
        out = model(input_ids=nxt[:, None], attention_mask=mask, position_ids=pos, past_key_values=past,
                    use_cache=True)
        past, nxt = out.past_key_values, out.logits[:, -1].argmax(-1)
        tokens.append(nxt)
        done |= torch.isin(nxt, stops)
    rows = torch.stack(tokens, dim=1).tolist()
    return [row[:next((k for k, t in enumerate(row) if t in stop_ids), len(row))] for row in rows]


def answer_text(raw: str) -> str:
    """The first line of an answer, without markdown or end punctuation."""
    text = raw.split(glimmer.END_OF_TURN)[0].split("<|eom|>")[0].replace("*", "").strip()
    return text.splitlines()[0].strip(" .!?") if text else ""


# --- guard (a): picture naming -----------------------------------------------------------------

@dataclass
class NamingItem:
    word: str
    lang: str
    image: Path


def load_naming_set(set_dir: Path, heldout: bool = False) -> list[NamingItem]:
    """The kept pictures of a Test Studio set. heldout=True instead gives each kept word's other
    Muse Image candidate that Muse Spark also named correctly: new pictures of the same words,
    used only to check a cut, never to choose it."""
    set_dir = Path(set_dir)
    manifest = json.loads((set_dir / "manifest.json").read_text())
    items = []
    for it in manifest["items"]:
        if it.get("status") != "kept":
            continue
        lang = it.get("lang") or manifest.get("lang", "en")
        if not heldout:
            items.append(NamingItem(it["word"], lang, set_dir / it["image"]))
            continue
        alt = next((c for c in it.get("candidates", []) if c["file"] != it["image"] and c.get("spark_ok")), None)
        if alt:
            items.append(NamingItem(it["word"], lang, set_dir / alt["file"]))
    return items


@dataclass
class NamingTest:
    """A picture-naming test prepared once: token ids and pixels on the CPU, image features on
    the GPU (the vision tower is never cut, so features are reused across configurations)."""
    name: str
    items: list[NamingItem]
    rows: list[dict] = field(repr=False)
    pad_id: int = 0

    @classmethod
    @torch.no_grad()
    def prepare(cls, name: str, model, processor, items: list[NamingItem],
                prompts: dict[str, str] = NAMING_PROMPTS, features: bool = True) -> NamingTest:
        """features=False keeps only pixels, so every run goes through the vision tower and no
        GPU memory is held between runs (for measuring a model as deployed)."""
        from PIL import Image

        rows = []
        for it in items:
            image = Image.open(it.image).convert("RGB")
            inputs = glimmer.build_inputs(processor, image, prompts[it.lang], "cpu")
            row = {"input_ids": inputs["input_ids"][0], "pixel_values": inputs["pixel_values"],
                   "image_grid_thw": inputs["image_grid_thw"]}
            if features:
                row["feats"] = tuple(model.model.get_image_features(
                    inputs["pixel_values"].to(model.device), inputs["image_grid_thw"].to(model.device)).pooler_output)
            rows.append(row)
        tok = processor.tokenizer
        pad = tok.pad_token_id if tok.pad_token_id is not None else 0
        return cls(name, items, rows, pad)

    @classmethod
    def prepare_pixels(cls, name: str, model, processor, items: list[NamingItem]) -> NamingTest:
        return cls.prepare(name, model, processor, items, features=False)

    def batch(self, idx: Sequence[int], device, vision: bool = False) -> dict:
        """A left-padded batch. vision=True runs the vision tower on the pixels (end-to-end timing);
        otherwise the cached image features are passed in."""
        from transformers.modeling_outputs import BaseModelOutputWithPooling

        rows = [self.rows[i] for i in idx]
        batch = {k: v.to(device) for k, v in left_pad([r["input_ids"] for r in rows], self.pad_id).items()}
        if vision:
            batch["pixel_values"] = torch.cat([r["pixel_values"] for r in rows]).to(device)
            batch["image_grid_thw"] = torch.cat([r["image_grid_thw"] for r in rows]).to(device)
        else:
            feats = tuple(f for r in rows for f in r["feats"])
            batch["mm_encoder_outputs"] = {"image": BaseModelOutputWithPooling(pooler_output=feats)}
        return batch

    @torch.no_grad()
    def run(self, model, processor, batch_size: int = 10, max_new_tokens: int = 8, vision: bool = False,
            keep_items: bool = True) -> dict:
        tok = processor.tokenizer
        stops = stop_token_ids(model, tok)
        out = []
        for start in range(0, len(self.rows), batch_size):
            idx = list(range(start, min(start + batch_size, len(self.rows))))
            for i, toks in zip(idx, greedy_decode(model, self.batch(idx, model.device, vision), stops,
                                                  max_new_tokens)):
                it = self.items[i]
                said = answer_text(tok.decode(toks, skip_special_tokens=False))
                out.append({"word": it.word, "lang": it.lang, "said": said,
                            "code": classify(it.word, said, it.lang).code})
        return summarize_naming(out, keep_items)

    @torch.no_grad()
    def block_influence(self, model, batch_size: int = 10) -> list[float]:
        """Block influence of every decoder layer at the answer position, averaged over pictures."""
        with BlockInfluence(model) as bi:
            for start in range(0, len(self.rows), batch_size):
                model(**self.batch(range(start, min(start + batch_size, len(self.rows))), model.device),
                      logits_to_keep=1)
        return bi.values()


def summarize_naming(items: list[dict], keep_items: bool = True) -> dict:
    by_lang = {}
    for lang in sorted({r["lang"] for r in items}):
        rows = [r for r in items if r["lang"] == lang]
        correct = sum(r["code"] == "Correct" for r in rows)
        by_lang[lang] = {"n": len(rows), "correct": correct, "accuracy": round(correct / len(rows), 4)}
    correct = sum(r["code"] == "Correct" for r in items)
    res = {"n": len(items), "correct": correct, "accuracy": round(correct / max(len(items), 1), 4),
           "by_lang": by_lang}
    if keep_items:
        res["items"] = items
    return res


# --- guard (b): general-language perplexity ----------------------------------------------------

def load_guard_text(path: Path = GUARD_TEXT) -> list[dict]:
    return json.loads(Path(path).read_text())["sentences"]


@dataclass
class TextGuard:
    """Next-token perplexity on plain sentences. Every token after the first in each sentence is
    scored; per-language perplexity comes from the same pass."""
    langs: list[str]
    seqs: list[torch.Tensor] = field(repr=False)
    pad_id: int = 0

    @classmethod
    def prepare(cls, tokenizer, sentences: list[dict]) -> TextGuard:
        seqs = [torch.tensor(tokenizer(s["text"], add_special_tokens=True)["input_ids"]) for s in sentences]
        pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
        return cls([s["lang"] for s in sentences], seqs, pad)

    @torch.no_grad()
    def run(self, model, batch_size: int = 30, subset: Sequence[int] | None = None) -> dict:
        idx = list(subset) if subset is not None else list(range(len(self.seqs)))
        nll = torch.zeros(len(idx), dtype=torch.float64)
        ntok = torch.zeros(len(idx), dtype=torch.long)
        for start in range(0, len(idx), batch_size):
            chunk = idx[start:start + batch_size]
            b = {k: v.to(model.device) for k, v in left_pad([self.seqs[i] for i in chunk], self.pad_id).items()}
            logits = model(**b).logits[:, :-1].float()
            target = b["input_ids"][:, 1:]
            valid = (b["attention_mask"][:, 1:] * b["attention_mask"][:, :-1]).bool()
            loss = F.cross_entropy(logits.transpose(1, 2), target, reduction="none")
            nll[start:start + len(chunk)] = (loss * valid).sum(1).double().cpu()
            ntok[start:start + len(chunk)] = valid.sum(1).cpu()
        langs = [self.langs[i] for i in idx]
        res = {"ppl": _ppl(nll, ntok), "tokens": int(ntok.sum())}
        for lang in sorted(set(langs)):
            sel = torch.tensor([lg == lang for lg in langs])
            res[f"ppl_{lang}"] = _ppl(nll[sel], ntok[sel])
        return res

    @torch.no_grad()
    def block_influence(self, model, batch_size: int = 30) -> list[float]:
        """Block influence of every decoder layer, averaged over all real tokens of the text."""
        with BlockInfluence(model, last_only=False) as bi:
            for start in range(0, len(self.seqs), batch_size):
                b = {k: v.to(model.device) for k, v in left_pad(self.seqs[start:start + batch_size], self.pad_id).items()}
                bi.set_mask(b["attention_mask"])
                model(**b, logits_to_keep=1)
        return bi.values()


def _ppl(nll: torch.Tensor, ntok: torch.Tensor) -> float:
    return round(math.exp(float(nll.sum()) / max(int(ntok.sum()), 1)), 4)


# --- block influence ---------------------------------------------------------------------------

class BlockInfluence:
    """Records 1 - cos(layer input, layer output) per decoder layer during forward passes.
    Prefill passes only (sequence length > 1); at the last position, or at every real token when a
    mask is set with set_mask()."""

    def __init__(self, model, last_only: bool = True):
        self.layers = decoder_layers(model)
        self.last_only = last_only
        self.sums = torch.zeros(len(self.layers), dtype=torch.float64)
        self.count = torch.zeros(len(self.layers), dtype=torch.long)
        self.mask: torch.Tensor | None = None
        self.hooks = [layer.register_forward_hook(self._hook(i), with_kwargs=True)
                      for i, layer in enumerate(self.layers)]

    def _hook(self, i: int):
        def fn(_m, args, kwargs, out):
            h_in = args[0] if args else kwargs["hidden_states"]
            h_out = out[0] if isinstance(out, tuple) else out
            if h_in.shape[1] < 2:
                return
            cos = F.cosine_similarity(h_in.float(), h_out.float(), dim=-1)  # (B, T)
            vals = cos[:, -1] if self.last_only or self.mask is None else cos[self.mask.bool()]
            self.sums[i] += float((1 - vals).sum())
            self.count[i] += vals.numel()
        return fn

    def set_mask(self, mask: torch.Tensor | None) -> None:
        self.mask = mask

    def values(self) -> list[float]:
        return [round(float(s / max(c, 1)), 6) for s, c in zip(self.sums, self.count)]

    def remove(self) -> None:
        for h in self.hooks:
            h.remove()
        self.hooks = []

    def __enter__(self) -> BlockInfluence:
        return self

    def __exit__(self, *exc) -> None:
        self.remove()


# --- configurations, scan and greedy path ------------------------------------------------------

@dataclass
class Guards:
    naming: NamingTest
    text: TextGuard
    processor: object

    def evaluate(self, model, skip: Iterable[int] = (), naming: bool = True, keep_items: bool = False) -> dict:
        with SkipLayers(model, skip):
            res = {"removed": sorted(set(skip)), **self.text.run(model)}
            if naming:
                nm = self.naming.run(model, self.processor, keep_items=keep_items)
                res.update(acc=nm["accuracy"], correct=nm["correct"], n=nm["n"],
                           **{f"acc_{lg}": v["accuracy"] for lg, v in nm["by_lang"].items()})
                if keep_items:
                    res["items"] = nm["items"]
        return res


def within_guard(res: dict, intact: dict, acc_floor: float = ACC_FLOOR, ppl_tolerance: float = PPL_TOLERANCE
                 ) -> dict:
    acc_ok = res["correct"] >= acc_floor * intact["correct"] - 1e-9
    ppl_ok = res["ppl"] <= (1 + ppl_tolerance) * intact["ppl"] + 1e-9
    return {"acc_ok": bool(acc_ok), "ppl_ok": bool(ppl_ok), "within_guard": bool(acc_ok and ppl_ok)}


def importance_scan(model, guards: Guards, intact: dict, log: Callable = print,
                    done: dict[int, dict] | None = None, on_result: Callable | None = None) -> list[dict]:
    """Skip each layer alone. done holds results already measured (resume after a restart)."""
    types = layer_types(model)
    out = []
    for i in range(len(decoder_layers(model))):
        res = (done or {}).get(i) or guards.evaluate(model, [i])
        row = {"layer": i, "type": types[i], "acc": res["acc"], "correct": res["correct"],
               **{k: res[k] for k in res if k.startswith(("acc_", "ppl"))},
               "skip_d_acc": round(res["acc"] - intact["acc"], 4),
               "skip_d_ppl": round(res["ppl"] - intact["ppl"], 4),
               "skip_d_ppl_rel": round(res["ppl"] / intact["ppl"] - 1, 4)}
        out.append(row)
        if on_result:
            on_result(i, res)
        log(f"skip {i:2d} ({types[i][:4]}): acc {res['acc']:.3f} ({row['skip_d_acc']:+.3f})  "
            f"ppl {res['ppl']:.3f} ({row['skip_d_ppl_rel']:+.1%})")
    return out


def greedy_path(model, guards: Guards, intact: dict, shortlist: int = 3, max_removed: int = 20,
                stop_acc: float = 0.5, stop_ppl: float = 3.0, log: Callable = print,
                steps: list[dict] | None = None, on_step: Callable | None = None) -> list[dict]:
    """Remove one layer per step: score every remaining layer by perplexity with it also skipped,
    run naming on the `shortlist` cheapest, and remove the one that keeps naming best (ties go to
    lower perplexity). Runs past the guard until accuracy falls below stop_acc x intact, perplexity
    passes stop_ppl x intact, or max_removed layers are gone. steps resumes an earlier path."""
    n = len(decoder_layers(model))
    steps = list(steps or [])
    removed = list(steps[-1]["removed"]) if steps else []
    while len(removed) < max_removed:
        t0 = time.time()
        cands = []
        for layer in (i for i in range(n) if i not in removed):
            with SkipLayers(model, removed + [layer]):
                cands.append((guards.text.run(model)["ppl"], layer))
        cands.sort()
        tried = [guards.evaluate(model, removed + [layer]) | {"layer": layer} for _, layer in cands[:shortlist]]
        best = max(tried, key=lambda r: (r["correct"], -r["ppl"]))
        removed = sorted(removed + [best["layer"]])
        step = {k: v for k, v in best.items() if k != "layer"} | {
            "added": best["layer"], "removed": removed, **within_guard(best, intact),
            "candidates": [{"layer": layer, "ppl": p} for p, layer in cands[:8]],
            "shortlist": [{"layer": r["layer"], "correct": r["correct"], "ppl": r["ppl"]} for r in tried],
            "seconds": round(time.time() - t0, 1)}
        steps.append(step)
        if on_step:
            on_step(steps)
        log(f"step {len(removed):2d}: +{best['layer']:2d} -> acc {best['acc']:.3f} "
            f"ppl {best['ppl']:.3f} ({best['ppl'] / intact['ppl'] - 1:+.1%})"
            f"{'' if step['within_guard'] else '  [outside guard]'} ({step['seconds']}s)")
        if best["correct"] < stop_acc * intact["correct"] or best["ppl"] > stop_ppl * intact["ppl"]:
            break
    return steps


def last_within_guard(steps: list[dict], key: str = "within_guard") -> dict | None:
    """The deepest step that passes, counting only the unbroken run from the start (a step that
    passes again after a failure is luck on a small test, not a safe cut)."""
    best = None
    for s in steps:
        if not s[key]:
            break
        best = s
    return best


# --- measuring a real (pruned) model ----------------------------------------------------------

def count_params(model) -> dict:
    """Weights only: FP8 block-scale tensors are excluded (they are <0.01% of the weights)."""
    total = decoder = 0
    for name, p in model.named_parameters():
        if "scale" in name.rsplit(".", 1)[-1]:
            continue
        total += p.numel()
        if ".layers." in name and "vision" not in name:
            decoder += p.numel()
    return {"params": total, "decoder_params": decoder}


def _sync() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


@torch.no_grad()
def time_generation(model, processor, n_tokens: int = 32, repeats: int = 5) -> dict:
    """Tokens per second for exactly n_tokens greedy tokens from a short text prompt, batch 1,
    with a KV cache. Median over repeats after one warm-up."""
    msgs = [{"role": "user", "content": [{"type": "text", "text": GEN_PROMPT}]}]
    ids = processor.apply_chat_template(msgs, tokenize=True, return_dict=True, return_tensors="pt",
                                        add_generation_prompt=True, reasoning_strength="low")["input_ids"][0]
    prefix = processor.tokenizer(glimmer.ANSWER_PREFIX, add_special_tokens=False, return_tensors="pt")["input_ids"][0]
    batch = {k: v.to(model.device) for k, v in left_pad([torch.cat([ids, prefix])], 0).items()}
    times = []
    for r in range(repeats + 1):
        _sync()
        t0 = time.perf_counter()
        toks = greedy_decode(model, batch, set(), n_tokens)
        _sync()
        if r:
            times.append(time.perf_counter() - t0)
    med = sorted(times)[len(times) // 2]
    return {"tok_per_s": round(n_tokens / med, 2), "gen_seconds": round(med, 4), "gen_tokens": len(toks[0]),
            "gen_text": processor.tokenizer.decode(toks[0])}


@torch.no_grad()
def time_naming(model, processor, test: NamingTest, repeats: int = 1) -> dict:
    """End-to-end time per picture at batch size 1: vision tower, prefill and decoding. Inputs are
    tokenized beforehand, so CPU preprocessing is excluded."""
    stops = stop_token_ids(model, processor.tokenizer)
    greedy_decode(model, test.batch([0], model.device, vision=True), stops, 8)  # warm-up
    times = []
    for _ in range(repeats):
        for i in range(len(test.rows)):
            b = test.batch([i], model.device, vision=True)
            _sync()
            t0 = time.perf_counter()
            greedy_decode(model, b, stops, 8)
            _sync()
            times.append(time.perf_counter() - t0)
    return {"ms_per_item": round(1000 * sum(times) / len(times), 1)}


@torch.no_grad()
def peak_memory(model, processor, test: NamingTest, batch_size: int = 10) -> dict:
    """Peak GPU memory for one end-to-end naming batch (vision tower included)."""
    stops = stop_token_ids(model, processor.tokenizer)
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    greedy_decode(model, test.batch(list(range(min(batch_size, len(test.rows)))), model.device, vision=True),
                  stops, 8)
    _sync()
    return {"peak_gb": round(torch.cuda.max_memory_allocated() / 2**30, 3), "peak_batch": batch_size}


@torch.no_grad()
def answer_logits(model, test: NamingTest, idx: Sequence[int], vision: bool = False) -> torch.Tensor:
    """Final logits at the answer position, one picture at a time (for skip-vs-removal checks)."""
    return torch.stack([model(**test.batch([i], model.device, vision), logits_to_keep=1).logits[0, -1].float().cpu()
                        for i in idx])


# --- report for the web app --------------------------------------------------------------------

def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def _ranks(x: Sequence[float]) -> list[float]:
    order = sorted(range(len(x)), key=lambda i: x[i])
    ranks = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1  # ties share their mean rank
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return round(cov / (sx * sy), 4) if sx and sy else 0.0


def rank_permutation_test(a: Sequence[float], b: Sequence[float], n_perm: int = 20000, seed: int = 0) -> float:
    """Two-sided p-value for a difference in mean rank between groups a and b (a permutation
    version of the Mann-Whitney test)."""
    import random

    ranks = _ranks(list(a) + list(b))
    na = len(a)
    observed = abs(sum(ranks[:na]) / na - sum(ranks[na:]) / len(b))
    rng = random.Random(seed)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(ranks)
        hits += abs(sum(ranks[:na]) / na - sum(ranks[na:]) / len(b)) >= observed - 1e-12
    return round((hits + 1) / (n_perm + 1), 4)


def _median(x: Sequence[float]) -> float:
    s = sorted(x)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def compare_layer_types(layers: list[dict]) -> dict:
    """Do full-attention layers matter more than sliding-window ones when skipped alone?"""
    out = {}
    for t in sorted({r["type"] for r in layers}):
        rows = [r for r in layers if r["type"] == t]
        ppl = [r["skip_d_ppl_rel"] for r in rows]
        out[t] = {"n": len(rows), "mean_d_ppl_rel": round(sum(ppl) / len(ppl), 4),
                  "median_d_ppl_rel": round(_median(ppl), 4),
                  "mean_d_acc": round(sum(r["skip_d_acc"] for r in rows) / len(rows), 4),
                  "layers_losing_naming": sum(r["skip_d_acc"] < 0 for r in rows),
                  "mean_block_influence": round(sum(r["block_influence"] for r in rows) / len(rows), 4)}
    full = [r for r in layers if r["type"] == "full_attention"]
    slide = [r for r in layers if r["type"] != "full_attention"]
    if full and slide:
        out["p_d_ppl"] = rank_permutation_test([r["skip_d_ppl_rel"] for r in full],
                                               [r["skip_d_ppl_rel"] for r in slide])
        out["p_d_acc"] = rank_permutation_test([r["skip_d_acc"] for r in full], [r["skip_d_acc"] for r in slide])
        out["p_block_influence"] = rank_permutation_test([r["block_influence"] for r in full],
                                                         [r["block_influence"] for r in slide])
    return out


GUARD_SETS = ("demo_en", "demo_es")
METRIC_KEYS = ("layers", "params", "decoder_params", "mem_gb", "peak_gb", "ms_per_item", "tok_per_s", "acc",
               "acc_en", "acc_es", "correct", "n", "heldout_acc", "ppl", "ppl_en", "ppl_es")
PATH_KEYS = ("removed", "added", "acc", "acc_en", "acc_es", "correct", "ppl", "ppl_en", "ppl_es", "heldout_acc",
             "acc_ok", "ppl_ok", "within_guard")


def _pct(new: float, old: float) -> float:
    return round(100 * (new - old) / old, 1)


def build_report(out_dir: Path) -> dict:
    """Merge scan.json, greedy.json, pruned.json and reload.json into the web app's file."""
    out_dir = Path(out_dir)
    read = lambda name: json.loads((out_dir / name).read_text()) if (out_dir / name).exists() else None  # noqa: E731
    scan, greedy, pruned, reload = read("scan.json"), read("greedy.json"), read("pruned.json")["cuts"], read("reload.json")
    ev = scan["intact"]
    base = pruned["intact"]

    layers = [{"layer": r["layer"], "type": r["type"], "skip_d_acc": r["skip_d_acc"], "skip_d_ppl": r["skip_d_ppl"],
               "skip_d_ppl_rel": r["skip_d_ppl_rel"], "block_influence": scan["block_influence"][r["layer"]],
               "block_influence_text": scan["block_influence_text"][r["layer"]], "acc_en": r.get("acc_en"),
               "acc_es": r.get("acc_es"), "ppl": r["ppl"]} for r in scan["layers"]]
    step0 = {"step": 0, "removed": [], "added": None, **{k: ev.get(k) for k in PATH_KEYS if k in ev},
             "heldout_acc": ev["heldout"]["accuracy"], "acc_ok": True, "ppl_ok": True, "within_guard": True}
    path = [step0] + [{"step": i + 1, **{k: s.get(k) for k in PATH_KEYS}} for i, s in enumerate(greedy["steps"])]

    cuts = []
    for name, c in pruned.items():
        row = {"name": name, "removed": c["removed"], **{k: c.get(k) for k in METRIC_KEYS},
               "acc_ci95": wilson(c["correct"], c["n"])}
        if c["removed"]:
            row["savings_pct"] = {k: _pct(c[k], base[k]) for k in
                                  ("params", "decoder_params", "mem_gb", "peak_gb", "ms_per_item", "tok_per_s", "ppl")}
            row["check"] = c.get("check")
        cuts.append(row)

    n_en, n_es = ev["by_lang"]["en"]["n"], ev["by_lang"]["es"]["n"]
    return {
        "model": glimmer.MODEL_ID,
        "precision": "decoder FP8 (FineGrainedFP8Config); vision tower, projector and lm_head BF16",
        "hardware": "1x NVIDIA L40S (46 GB)",
        "method": "Whole decoder layers removed. Reversible skip for the scan and the greedy path; real deletion "
                  "(ModuleList and config) for the pruned rows. See metalesionlab/compress.py.",
        "guards": {
            "naming": {"sets": list(GUARD_SETS), "n": ev["n"], "n_en": n_en, "n_es": n_es,
                       "heldout_n": ev["heldout"]["n"],
                       "heldout": "the other Muse Image picture of each word (Muse Spark named it correctly); "
                                  "never used to choose a cut"},
            "text": {"file": "public_data/general_text_guard.json", "sentences": 150, "tokens": ev["tokens"],
                     "source": "written by Muse Spark (muse-spark-1.3) for this project"},
            "acc_floor": ACC_FLOOR, "ppl_tolerance": PPL_TOLERANCE,
            "why": "Naming, pooled over both languages, must stay at or above 95% of intact. Perplexity may rise "
                   "at most 10%, about one model-size step in an open family (Llama 2 13B to 7B: WikiText-2 "
                   "4.88 to 5.47, +12%), so a bigger loss is worse than switching to a smaller model.",
        },
        "intact": {**{k: base.get(k) for k in METRIC_KEYS}, "acc_ci95": wilson(base["correct"], base["n"])},
        "layers": layers,
        "by_type": compare_layer_types(layers),
        "block_influence_vs_skip": {
            "spearman_bi_answer_vs_d_ppl": spearman([r["block_influence"] for r in layers],
                                                    [r["skip_d_ppl_rel"] for r in layers]),
            "spearman_bi_text_vs_d_ppl": spearman([r["block_influence_text"] for r in layers],
                                                  [r["skip_d_ppl_rel"] for r in layers]),
            "spearman_bi_answer_vs_acc_loss": spearman([r["block_influence"] for r in layers],
                                                       [-r["skip_d_acc"] for r in layers]),
        },
        "greedy": path,
        "greedy_rule": f"each step: perplexity for every remaining layer, naming for the {greedy.get('shortlist', 3)} "
                       "lowest, remove the one that keeps naming best (ties: lower perplexity)",
        "pruned": cuts,
        "reload": reload,
        "limits": [
            f"{ev['n']} guard pictures ({n_en} English, {n_es} Spanish): one picture moves a language's accuracy "
            f"by about 5 points; the 95% interval on the intact {ev['correct']}/{ev['n']} is "
            f"{wilson(ev['correct'], ev['n'])}.",
            "Cuts are chosen on the same pictures they are scored on, so guard accuracy is optimistic. The "
            "held-out pictures (same words, new drawings) are the fairer check; new words could fare worse.",
            "Perplexity is measured on 150 short model-written sentences (about 1,600 tokens), not on long "
            "documents, reasoning or instruction following, which these guards do not test.",
            "Speed is batch 1 on one L40S with an FP8 decoder. Savings follow the share of decoder weights "
            "removed and will differ on other hardware and batch sizes.",
        ],
    }

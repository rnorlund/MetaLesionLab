"""Model Lab: give Muse Glimmer a picture-naming test, intact or lesioned, and read its word lens.

One condition = one lesion spec run over every kept picture of a Test Studio set:
  1. Each picture is prompted with the naming instruction and the answer channel pre-filled
     (see glimmer.build_inputs), so the next token is the answer.
  2. Pictures run in left-padded batches. The prefill pass records the residual stream at the
     answer position after every decoder layer, then greedy decoding writes the answer.
  3. The answer is coded with naming_errors.classify after dropping a carrier phrase ("The
     object in the picture is a ...", "El objeto de la imagen es un ..."), as PNT scoring
     ignores them. "Correct" never depends on the meaning judge, so accuracy is final on the
     GPU box; Semantic vs Unrelated can be re-scored later with the Muse Spark judge
     (rescore_result).
  4. Word lens per item: the top-5 tokens and p(correct first token) after each layer, where
     p(correct) is the max over the target's spacing and capitalization variants.

Severity bisection searches the dose that brings naming accuracy to a target, assuming accuracy
falls as the dose grows. The dose is the fraction of a ranked unit list (from a localizer) or the
noise scale of a fixed lesion.
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import torch
from PIL import Image

from metalesionlab import glimmer
from metalesionlab.lesions import LesionSpec, UnitStats, lesion, site_dims
from metalesionlab.naming_errors import LANGUAGE_NAMES, classify

NAMING_PROMPTS = {
    "en": "Name the object in this picture with exactly one word.",
    # Oct 26, demo_es: this wording gave one-word answers for 19/19 pictures; "Nombra el objeto de
    # esta imagen con una sola palabra en español." gave carrier sentences for 7/19.
    "es": "Di el nombre del objeto con una sola palabra en español. Solo la palabra, sin artículo.",
}
VERIFY_PROMPTS = {
    "en": "Is this a {word}? Answer yes or no.",
    "es": "¿Esta imagen muestra: {word}? Responde sí o no.",
}
# Carrier phrases dropped before coding (matched on the lowercased first sentence).
CARRIERS = {
    "en": [r"(?:the )?(?:object|thing|item)(?: (?:in|on|of) (?:the|this) (?:picture|image|drawing))? (?:is|shows) ",
           r"(?:the |this )?(?:picture|image|drawing) (?:shows|is of|depicts) ", r"(?:this|that|it)(?: is|'s) ",
           r"i see "],
    "es": [r"(?:el )?objeto(?: de| en)? (?:la|esta) imagen es ", r"(?:la|esta) imagen (?:muestra|es de) ",
           r"(?:esto )?es ", r"veo "],
}
CODES = ("Correct", "Semantic", "Formal", "Mixed", "Unrelated", "Nonword", "Neologism", "Description", "NoResponse")
FLAGS = ("echo", "perseveration")


def answer_text(said: str, lang: str) -> str:
    """The naming response inside a model answer: first sentence or line (the first attempt, as in
    PNT scoring), with markdown and a carrier phrase removed."""
    text = re.split(r"(?<=[.!?])\s|\n", said.replace("*", "").strip())[0]
    for pattern in CARRIERS.get(lang, []):
        if m := re.match(pattern, text.lower()):
            text = text[m.end():]
            break
    return text.strip(" .!?")


def code_answer(item_word: str, said: str, lang: str, alternates: tuple[str, ...] = (), judge=None):
    return classify(item_word, answer_text(said, lang), lang, alternates=alternates, judge=judge)


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def response_flags(said: str, prompt: str, echo_ngram: int = 4, repeats: int = 4) -> list[str]:
    """Lesion signs the naming codes don't capture: "echo" when the answer repeats the instruction
    (4 words in a row from the prompt), "perseveration" when one token makes up at least half of
    the answer and occurs 4+ times ("self | self | self", '" " " "')."""
    flags = []
    w, p = _words(said), _words(prompt)
    grams = {tuple(p[i:i + echo_ngram]) for i in range(len(p) - echo_ngram + 1)}
    if any(tuple(w[i:i + echo_ngram]) in grams for i in range(len(w) - echo_ngram + 1)):
        flags.append("echo")
    toks = said.split()
    top = Counter(toks).most_common(1)
    if top and top[0][1] >= repeats and top[0][1] * 2 >= len(toks):
        flags.append("perseveration")
    return flags


def naming_prompt(lang: str) -> str:
    return NAMING_PROMPTS.get(lang) or (f"Name the object in this picture with exactly one word in "
                                        f"{LANGUAGE_NAMES.get(lang, lang)}.")


def verify_prompt(lang: str, word: str) -> str:
    return VERIFY_PROMPTS.get(lang, VERIFY_PROMPTS["en"]).format(word=word)


@dataclass
class Item:
    word: str
    lang: str
    image: Path
    gloss: str = ""
    alternates: tuple[str, ...] = ()


def load_set(set_dir: Path, include_review: bool = False) -> list[Item]:
    """Kept pictures of a Test Studio set (manifest.json)."""
    manifest = json.loads((Path(set_dir) / "manifest.json").read_text())
    items = []
    for it in manifest["items"]:
        if it.get("image") and (it.get("status") == "kept" or include_review):
            items.append(Item(it["word"], it.get("lang", manifest.get("lang", "en")), Path(set_dir) / it["image"],
                              it.get("gloss", ""), tuple(it.get("alternates") or ())))
    return items


# --- batching ---------------------------------------------------------------------------

def collate(inputs: list[dict], pad_id: int) -> dict:
    """Left-pad single-example inputs into one batch, so the answer position is -1 in every row.
    Position ids are counted from each row's first real token."""
    T = max(x["input_ids"].shape[1] for x in inputs)
    ids = torch.full((len(inputs), T), pad_id, dtype=torch.long)
    mask = torch.zeros((len(inputs), T), dtype=torch.long)
    for i, x in enumerate(inputs):
        n = x["input_ids"].shape[1]
        ids[i, T - n:] = x["input_ids"][0]
        mask[i, T - n:] = x["attention_mask"][0]
    batch = {"input_ids": ids, "attention_mask": mask, "position_ids": (mask.cumsum(-1) - 1).clamp_min(0)}
    with_images = [x for x in inputs if "pixel_values" in x]
    if with_images:
        batch["pixel_values"] = torch.cat([x["pixel_values"] for x in with_images])
        batch["image_grid_thw"] = torch.cat([x["image_grid_thw"] for x in with_images])
    return batch


def to_device(batch: dict, device) -> dict:
    return {k: v.to(device) for k, v in batch.items()}


def build_batches(processor, examples: list[tuple[Image.Image | None, str]], batch_size: int) -> list[dict]:
    """CPU batches for (image, prompt) pairs, built once and reused across conditions."""
    pad_id = processor.tokenizer.pad_token_id
    singles = [dict(glimmer.build_inputs(processor, img, prompt, "cpu")) for img, prompt in examples]
    return [collate(singles[i:i + batch_size], pad_id) for i in range(0, len(singles), batch_size)]


def stop_token_ids(model, tokenizer) -> set[int]:
    eos = model.generation_config.eos_token_id
    ids = set(eos if isinstance(eos, list) else [eos] if eos is not None else [])
    for tok in (glimmer.END_OF_TURN, "<|eom|>"):
        tid = tokenizer.convert_tokens_to_ids(tok)
        if isinstance(tid, int) and tid != tokenizer.unk_token_id:
            ids.add(tid)
    return ids


@torch.no_grad()
def generate_with_lens(model, batch: dict, stop_ids: set[int], max_new_tokens: int = 8
                       ) -> tuple[list[list[int]], torch.Tensor]:
    """Greedy decoding with a KV cache. Returns the new tokens per row (cut at the first stop
    token) and the residual stream at the answer position after each decoder layer, (B, L, H),
    recorded during the prefill pass."""
    captured = []

    def grab(_m, _i, out):
        h = out[0] if isinstance(out, tuple) else out
        if h.shape[1] > 1:  # prefill only
            captured.append(h[:, -1].detach())

    hooks = [layer.register_forward_hook(grab) for layer in glimmer.decoder_layers(model)]
    try:
        out = model(**batch, use_cache=True, logits_to_keep=1)
    finally:
        for h in hooks:
            h.remove()
    resid = torch.stack(captured, dim=1)
    past, mask, pos = out.past_key_values, batch["attention_mask"], batch["position_ids"][:, -1:]
    nxt = out.logits[:, -1].argmax(-1)
    tokens = [nxt]
    done = torch.isin(nxt, torch.tensor(sorted(stop_ids), device=nxt.device))
    for _ in range(max_new_tokens - 1):
        if bool(done.all()):
            break
        mask = torch.cat([mask, torch.ones_like(mask[:, :1])], dim=1)
        pos = pos + 1
        out = model(input_ids=nxt[:, None], attention_mask=mask, position_ids=pos, past_key_values=past,
                    use_cache=True)
        past = out.past_key_values
        nxt = out.logits[:, -1].argmax(-1)
        tokens.append(nxt)
        done |= torch.isin(nxt, torch.tensor(sorted(stop_ids), device=nxt.device))
    rows = torch.stack(tokens, dim=1).tolist()
    cut = [row[:next((k for k, t in enumerate(row) if t in stop_ids), len(row))] for row in rows]
    return cut, resid


@torch.no_grad()
def lens_readout(model, tokenizer, resid: torch.Tensor, target_ids: list[list[int]], top_k: int = 5) -> list[dict]:
    """Word lens for each row of resid (B, L, H): top-k tokens, p(top-1) and p(correct first
    token) after every layer."""
    norm = model.model.language_model.norm
    out = []
    for row, tids in zip(resid, target_ids):
        logprobs = torch.log_softmax(glimmer.output_logits(model, norm(row)), dim=-1)  # (L, V)
        top = logprobs.topk(top_k, dim=-1)
        p_correct = logprobs[:, tids].exp().max(dim=-1).values if tids else torch.zeros(len(row))
        out.append({
            "p_correct": [sig(p) for p in p_correct.tolist()],
            "p_top": [sig(p) for p in top.values[:, 0].exp().tolist()],
            "top": [[tokenizer.decode([i]).strip() or tokenizer.decode([i]) for i in ids] for ids in top.indices.tolist()],
        })
    return out


def sig(x: float, digits: int = 3) -> float:
    """Round to significant digits; keeps tiny probabilities readable on a log scale."""
    return float(f"{x:.{digits}g}") if x and math.isfinite(x) else 0.0


# --- a naming test ----------------------------------------------------------------------

@dataclass
class NamingTest:
    """A set's pictures, tokenized once. run() gives one condition's result."""
    name: str
    items: list[Item]
    batches: list[dict]
    target_ids: list[list[int]]
    prompt: str = ""
    meta: dict = field(default_factory=dict)

    @classmethod
    def from_set(cls, processor, set_dir: Path, batch_size: int = 10, transform: Callable | None = None,
                 limit: int | None = None) -> NamingTest:
        items = load_set(set_dir)[:limit]
        prompt = naming_prompt(items[0].lang) if items else ""
        examples = []
        for it in items:
            img = Image.open(it.image).convert("RGB")
            examples.append((transform(img) if transform else img, naming_prompt(it.lang)))
        tok = processor.tokenizer
        target_ids = [sorted({t for w in (it.word, *it.alternates) for t in glimmer.target_token_ids(tok, w)})
                      for it in items]
        return cls(Path(set_dir).name, items, build_batches(processor, examples, batch_size), target_ids, prompt)

    def run(self, model, processor, spec: LesionSpec | dict | None = None, stats: UnitStats | None = None,
            judge=None, max_new_tokens: int = 8, lens: bool = True, condition: str = "") -> dict:
        spec = spec if isinstance(spec, LesionSpec) else LesionSpec.from_dict(spec or {})
        tok, stops = processor.tokenizer, stop_token_ids(model, processor.tokenizer)
        said, lenses = [], []
        torch.cuda.synchronize()
        t0 = time.time()
        with lesion(model, spec, stats):
            start = 0
            for batch in self.batches:
                n = batch["input_ids"].shape[0]
                tokens, resid = generate_with_lens(model, to_device(batch, model.device), stops, max_new_tokens)
                said += [tok.decode(t, skip_special_tokens=True).strip() for t in tokens]
                if lens:
                    lenses += lens_readout(model, tok, resid, self.target_ids[start:start + n])
                start += n
        torch.cuda.synchronize()
        seconds = time.time() - t0
        items = [{"word": it.word, "said": answer} | ({"lens": lenses[k]} if lens else {})
                 for k, (it, answer) in enumerate(zip(self.items, said))]
        result = {
            "set": self.name, "condition": condition or spec.name or ("intact" if spec.is_intact else "lesion"),
            "lang": self.items[0].lang if self.items else "", "prompt": self.prompt,
            "spec": spec.to_dict(units=False), "units": spec.counts(site_dims(model)), "n": len(items),
            "seconds": round(seconds, 2), "items_per_s": round(len(items) / seconds, 3) if seconds else None,
            "items": items, **self.meta,
        }
        return rescore_result(result, judge, {it.word: it.alternates for it in self.items})


def rescore_result(result: dict, judge, alternates: dict[str, tuple[str, ...]] | None = None) -> dict:
    """Code (or re-code) a result's answers: naming code, the coded word and lesion flags, then the
    counts and accuracy. With a meaning judge (e.g. Muse Spark) this runs without the GPU."""
    lang, prompt = result.get("lang", "en"), result.get("prompt", "")
    for row in result["items"]:
        c = code_answer(row["word"], row["said"], lang, (alternates or {}).get(row["word"], ()), judge)
        row["code"], row["head"], row["flags"] = c.code, c.head, response_flags(row["said"], prompt)
    counts = Counter(r["code"] for r in result["items"])
    flags = Counter(f for r in result["items"] for f in r["flags"])
    result["counts"] = {c: counts.get(c, 0) for c in CODES}
    result["flags"] = {f: flags.get(f, 0) for f in FLAGS}
    result["accuracy"] = round(counts["Correct"] / max(len(result["items"]), 1), 4)
    result["judge"] = "spark" if judge else "none"
    # Keep the summary fields ahead of the long item list.
    return {k: result[k] for k in sorted(result, key=lambda k: k == "items")}


def save_result(result: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return path


def write_index(out_dir: Path) -> Path:
    """index.json: one row per condition file in out_dir, for the web app."""
    rows = []
    for f in sorted(out_dir.glob("*.json")):
        if f.name == "index.json" or f.name.startswith("severity_"):
            continue
        r = json.loads(f.read_text())
        if "accuracy" in r:
            rows.append({"file": f.name, "condition": r["condition"], "accuracy": r["accuracy"], "counts": r["counts"],
                         "flags": r.get("flags", {}),
                         "method": r["spec"]["method"], "recipe": r["spec"].get("recipe", {}), "judge": r.get("judge"),
                         "units": {k: r["units"][k] for k in ("mlp", "heads", "components")}})
    path = out_dir / "index.json"
    path.write_text(json.dumps({"set": out_dir.name, "conditions": rows}, ensure_ascii=False, indent=1))
    return path


# --- severity bisection -----------------------------------------------------------------

@dataclass
class SeverityCurve:
    """Accuracy as a function of lesion dose (fraction of ranked units, or noise scale).
    Evaluations are cached, so several targets share points."""
    evaluate: Callable[[float], float]
    points: dict[float, float] = field(default_factory=dict)

    def at(self, dose: float) -> float:
        dose = float(f"{dose:.4g}")
        if dose not in self.points:
            self.points[dose] = self.evaluate(dose)
        return self.points[dose]

    def bisect(self, target: float, lo: float, hi: float, steps: int = 5, tol: float = 0.05) -> dict:
        """Geometric bisection on (lo, hi] for accuracy == target +/- tol, in at most `steps` new
        evaluations. Points already evaluated tighten the bracket first. Returns the evaluated
        point closest to the target."""
        used = 0
        if float(f"{hi:.4g}") not in self.points:
            used += 1
        if self.at(hi) > target + tol:  # even the largest dose is too mild
            return self._best(target, lo, hi, tol, used, reachable=False)
        while used < steps:
            known = {f: a for f, a in self.points.items() if lo <= f <= hi}
            if any(abs(a - target) <= tol + 1e-9 for a in known.values()):
                break
            mild = max((f for f, a in known.items() if a > target), default=lo)
            severe = min((f for f, a in known.items() if a < target and f > mild), default=hi)
            self.at(math.sqrt(mild * severe) if mild > 0 else severe / 8)
            used += 1
        return self._best(target, lo, hi, tol, used, reachable=True)

    def closest(self, target: float, lo: float, hi: float, tol: float = 0.05) -> dict:
        """The evaluated dose in [lo, hi] whose accuracy is closest to target (smallest dose on ties).
        Call after every bisection, since a later search can land nearer an earlier target."""
        known = {f: a for f, a in self.points.items() if lo <= f <= hi}
        dose, acc = min(known.items(), key=lambda kv: (abs(kv[1] - target), kv[0]))
        return {"target": target, "dose": dose, "accuracy": acc, "within_tol": abs(acc - target) <= tol + 1e-9}

    def _best(self, target: float, lo: float, hi: float, tol: float, used: int, reachable: bool) -> dict:
        return {**self.closest(target, lo, hi, tol), "reachable": reachable, "evaluations": used}

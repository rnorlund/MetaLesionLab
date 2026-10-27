"""Bilingual lesion test: is Spanish (or French, Portuguese) naming more fragile than English?

The design removes the differences between earlier runs, which used different pictures and
differently worded prompts per language:
  - Same pictures: the 20 kept pictures of the English demo set are named in every language.
    Names in the other languages come from their demo sets, matched by English gloss, plus
    accepted alternates (EXTRA_NAMES) chosen to be equally lenient in every language.
  - Matched prompts: one instruction with the same structure in each language, written natively,
    asking for a single word in that language with no article (PROMPTS). A control variant asks
    for Spanish in English ("es_xen"), separating the instruction language from the answer language.
  - Same damage: one lesion spec per condition, applied in a fresh `lesion()` block per language,
    so noise lesions restart from the same seed, and mean/noise reference statistics pooled over
    held-out drawings with every language's prompt (pooled_unit_stats).

Measures per run (one condition, one language variant, one noise seed):
  - accuracy, coded with naming_errors.classify (first attempt, carrier phrase removed);
  - response language (language_of): the answer's words are sorted into the target language,
    English, both or neither, using the item's names in each language first and then wordfreq
    (a word leans to a language when it is common there and at least 10x more frequent than in
    the other); a short non-word that starts one language's name only (e.g. "Umb") leans to it.
    A language switch is an answer whose words lean only to English on a non-English trial;
    "mixed" answers have words leaning both ways. On English trials the same rule finds the
    reverse switch (a Spanish, French or Portuguese answer);
  - the word lens: after every decoder layer, log p(first token of the item's name) in each
    language, summed over the name's spelling and capitalization variants, plus the top token.

Analysis helpers (no GPU): scoring raw runs, paired bootstrap over pictures and seeds, sign-flip
permutation test over pictures, and lens summaries. See scripts/bilingual_run.py (GPU) and
scripts/bilingual_analyze.py (local).
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from metalesionlab.naming_errors import classify, tokens as word_tokens, word_zipf

LANGS = ("en", "es", "fr", "pt")
# Test variants: (answer language, instruction). "es_xen" asks for Spanish in English.
PROMPTS = {
    "en": "Say the name of the object in a single word in English. Just the word, no article.",
    # The Model Lab's tested Spanish wording (metalesionlab/model_lab.py): one-word answers for 19/19.
    "es": "Di el nombre del objeto con una sola palabra en español. Solo la palabra, sin artículo.",
    "fr": "Dis le nom de l'objet en un seul mot en français. Seulement le mot, sans article.",
    "pt": "Diga o nome do objeto com uma só palavra em português. Só a palavra, sem artigo.",
    "es_xen": "Say the name of the object in a single word in Spanish. Just the word, no article.",
}
VARIANT_LANG = {"en": "en", "es": "es", "fr": "fr", "pt": "pt", "es_xen": "es"}

# Accepted names beyond each set's target (and manifest alternates), keyed by the English word.
# Kept symmetric: the kettle picture also reads as a teapot, so every language accepts both
# (Spanish tetera, French théière and Portuguese bule mean teapot); diminutives for cat and the
# common short form for bicycle are accepted in every language that has one.
EXTRA_NAMES = {
    "en": {"cat": ["kitten"], "kettle": ["teakettle", "teapot"], "ladder": ["stepladder"],
           "bicycle": ["bike"], "saw": ["handsaw"]},
    "es": {"cat": ["gatito"], "umbrella": ["sombrilla"], "kettle": ["hervidor", "hervidora", "pava"],
           "bench": ["banca"], "bicycle": ["bici"], "scissors": ["tijera"], "pineapple": ["ananá", "ananás"],
           "saw": ["serrucho"], "cactus": ["cacto"], "whistle": ["pito"]},
    "fr": {"cat": ["chaton"], "kettle": ["théière"], "ladder": ["escabeau"], "bicycle": ["bicyclette"],
           "candle": ["chandelle"], "saw": ["égoïne"]},
    "pt": {"cat": ["gatinho"], "umbrella": ["sombrinha"], "kettle": ["bule"], "pineapple": ["ananás"],
           "saw": ["serra"]},
}
GLOSS_FIX = {"teapot": "kettle"}  # demo_es glosses tetera as teapot; the English picture is "kettle"
SET_FOR = {"en": "demo_en", "es": "demo_es", "fr": "demo_fr", "pt": "demo_pt"}


# --- items ------------------------------------------------------------------------------

@dataclass
class BiItem:
    en: str  # the English word, the item's id
    image: Path
    names: dict[str, list[str]]  # lang -> [target, *accepted alternates]

    def target(self, lang: str) -> str:
        return self.names[lang][0]

    def alternates(self, lang: str) -> tuple[str, ...]:
        return tuple(self.names[lang][1:])


def matched_items(sets_dir: Path, langs: tuple[str, ...] = LANGS) -> list[BiItem]:
    """The English set's kept pictures with each language's names, matched by English gloss."""
    sets_dir = Path(sets_dir)
    en = json.loads((sets_dir / SET_FOR["en"] / "manifest.json").read_text())
    by_lang = {}
    for lang in langs:
        if lang == "en":
            continue
        manifest = json.loads((sets_dir / SET_FOR[lang] / "manifest.json").read_text())
        by_lang[lang] = {GLOSS_FIX.get(it.get("gloss", ""), it.get("gloss", "")): it for it in manifest["items"]}
    items = []
    for it in en["items"]:
        if it.get("status") != "kept" or not it.get("image"):
            continue
        word = it["word"]
        names = {"en": _unique([word, *(it.get("alternates") or []), *EXTRA_NAMES["en"].get(word, [])])}
        for lang, table in by_lang.items():
            other = table.get(word)
            if other is None:
                raise KeyError(f"no {lang} item glossed {word!r}")
            # An alternate that is just the English word (pt "igloo", "cactus") would score an
            # English answer as correct in one language but not another, so it is dropped; a
            # target shared with English (es/fr cactus, fr igloo) stays.
            english = {_fold(n) for n in names["en"]}
            alts = [a for a in [*(other.get("alternates") or []), *EXTRA_NAMES.get(lang, {}).get(word, [])]
                    if _fold(a) not in english]
            names[lang] = _unique([other["word"], *alts])
        items.append(BiItem(word, sets_dir / SET_FOR["en"] / it["image"], names))
    return items


def _unique(xs):
    out = []
    for x in xs:
        if x and x not in out:
            out.append(x)
    return out


# --- response language ------------------------------------------------------------------

def first_attempt(said: str) -> str:
    """The first sentence or line of an answer (the PNT first attempt), markdown removed."""
    return re.split(r"(?<=[.!?])\s|\n", said.replace("*", "").strip())[0].strip(" .!?")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _name_forms(names: list[str]) -> tuple[set[str], set[str]]:
    """Whole-word forms of a language's names (with -s/-es plurals and hyphen parts of 4+
    letters), and the folded names for prefix checks."""
    forms, full = set(), set()
    for n in names:
        f = _fold(n)
        full.add(f)
        for part in {f, *(p for p in re.split(r"[\s-]+", f) if len(p) >= 4)}:
            forms |= {part, part + "s", part + "es"}
    return forms, full


WORD_ZIPF = 2.0  # a word leans to a language when it is at least this common there ...
LEAN = 1.0       # ... and at least this much more common (Zipf units: 10x) than in the other


def token_side(tok: str, a: str, b: str, names: dict[str, list[str]]) -> str | None:
    """Which of two languages a word belongs to: a, b, or None (both, neither, unknown)."""
    t = _fold(tok)
    forms_a, full_a = _name_forms(names.get(a, []))
    forms_b, full_b = _name_forms(names.get(b, []))
    in_a, in_b = t in forms_a, t in forms_b
    if in_a != in_b:
        return a if in_a else b
    if in_a and in_b:
        return None
    za, zb = word_zipf(tok, a), word_zipf(tok, b)
    if za >= WORD_ZIPF and za - zb >= LEAN:
        return a
    if zb >= WORD_ZIPF and zb - za >= LEAN:
        return b
    if len(t) >= 3 and max(za, zb) < WORD_ZIPF:  # a fragment such as "Umb" or "paragu"
        pa = any(n.startswith(t) for n in full_a)
        pb = any(n.startswith(t) for n in full_b)
        if pa != pb:
            return a if pa else b
    return None


# Labels a damaged model writes before or instead of a name ("Answer: paraguas"); not language.
FORMAT_WORDS = {"answer", "respuesta", "réponse", "reponse", "resposta", "assistant", "final", "user"}
# Chat-format leaks ("assistant to=selfDiga o nome..."): the answer channel broke, not the language.
LEAK = re.compile(r"assistant|to=\w|<\|", re.I)


def language_of(said: str, lang: str, other: str, names: dict[str, list[str]], prompt: str = "") -> dict:
    """Sort the first attempt's words into `lang` vs `other`. label: lang, other, "mixed"
    (words of both), "unclear" (no word leans either way, e.g. "cactus"), "none", or "leak" (a
    chat-format leak). Format words and the trial's own instruction words are ignored, so
    "Answer: paraguas" is Spanish and an echoed instruction is not a switch."""
    first = first_attempt(said)
    if LEAK.search(first):
        return {"label": "leak", "words": [], "sides": []}
    skip = FORMAT_WORDS | set(word_tokens(prompt))
    words = [w for w in word_tokens(first) if w not in skip]
    sides = [token_side(w, lang, other, names) for w in words]
    n_l, n_o = sides.count(lang), sides.count(other)
    if not words:
        label = "none" if not word_tokens(first) else "unclear"
    elif n_l and n_o:
        label = "mixed"
    elif n_o:
        label = other
    elif n_l:
        label = lang
    else:
        label = "unclear"
    return {"label": label, "words": words, "sides": sides}


# --- coding one run ---------------------------------------------------------------------

SWITCH_CODES = ("EnglishName", "EnglishOther", "MixedLanguage")


def code_run(raw: dict, items: dict[str, BiItem], judge=None) -> dict:
    """Code a raw run (scripts/bilingual_run.py output) in place: naming code, response language
    and switch codes per item, then the run's summary."""
    from metalesionlab.model_lab import answer_text, response_flags

    lang, prompt = raw["lang"], raw.get("prompt", "")
    for row in raw["items"]:
        it = items[row["en"]]
        said = row["said"]
        c = classify(it.target(lang), answer_text(said, lang), lang, it.alternates(lang), judge=judge)
        row["code"], row["head"] = c.code, c.head
        row["flags"] = response_flags(said, prompt) + (["leak"] if LEAK.search(first_attempt(said)) else [])
        if lang == "en":
            # Reverse direction: an answer in one of the other test languages.
            labels = {o: language_of(said, o, "en", it.names, prompt)["label"] for o in it.names if o != "en"}
            row["other_lang"] = sorted(o for o, lab in labels.items() if lab in (o, "mixed"))
            row["lang_label"] = "leak" if "leak" in labels.values() else "en"
            row["switch"] = bool(row["other_lang"])
            row["mixed"] = any(lab == "mixed" for lab in labels.values())
            row["switch_code"] = None
        else:
            lab = language_of(said, lang, "en", it.names, prompt)
            row["lang_label"] = lab["label"]
            row["switch"] = lab["label"] == "en"
            row["mixed"] = lab["label"] == "mixed"
            en_name = classify(it.target("en"), answer_text(said, "en"), "en", it.alternates("en")).code == "Correct"
            row["english_name"] = row["switch"] and en_name
            row["switch_code"] = (None if c.code == "Correct" else
                                  "EnglishName" if row["english_name"] else
                                  "EnglishOther" if row["switch"] else
                                  "MixedLanguage" if row["mixed"] else None)
    rows = raw["items"]
    n = len(rows)
    counts = Counter(r["code"] for r in rows)
    aware = Counter(r["switch_code"] or r["code"] for r in rows)
    raw["n"] = n
    raw["correct"] = counts.get("Correct", 0)
    raw["accuracy"] = round(raw["correct"] / max(n, 1), 4)
    raw["counts"] = dict(sorted(counts.items()))
    raw["counts_switch_aware"] = dict(sorted(aware.items()))
    raw["switch_n"] = sum(r["switch"] for r in rows)
    raw["mixed_n"] = sum(r["mixed"] for r in rows)
    raw["english_name_n"] = sum(bool(r.get("english_name")) for r in rows)
    raw["flags"] = dict(Counter(f for r in rows for f in r["flags"]))
    raw["judge"] = "spark" if judge else "none"
    return raw


# --- GPU side ---------------------------------------------------------------------------

@dataclass
class LangTest:
    variant: str
    lang: str
    prompt: str
    items: list[BiItem]
    batches: list[dict]
    name_ids: list[dict[str, list[int]]]  # per item: lang -> first-token ids of its names


def name_token_ids(tokenizer, names: list[str]) -> list[int]:
    from metalesionlab import glimmer
    return sorted({t for n in names for t in glimmer.target_token_ids(tokenizer, n)})


def build_tests(processor, items: list[BiItem], variants: tuple[str, ...], batch_size: int = 10
                ) -> dict[str, LangTest]:
    from PIL import Image

    from metalesionlab.model_lab import build_batches

    images = [Image.open(it.image).convert("RGB") for it in items]
    tok = processor.tokenizer
    ids = [{lang: name_token_ids(tok, names) for lang, names in it.names.items()} for it in items]
    tests = {}
    for v in variants:
        examples = [(img, PROMPTS[v]) for img in images]
        tests[v] = LangTest(v, VARIANT_LANG[v], PROMPTS[v], items, build_batches(processor, examples, batch_size), ids)
    return tests


def lens_names(model, tokenizer, resid, name_ids: list[dict[str, list[int]]]) -> list[dict]:
    """Per row of resid (B, L, H): log p(first token of each language's name) after every layer
    (summed over the name's variants) and the top token."""
    import torch

    from metalesionlab import glimmer

    norm = model.model.language_model.norm
    out = []
    with torch.no_grad():
        for row, ids in zip(resid, name_ids):
            lp = torch.log_softmax(glimmer.output_logits(model, norm(row)), dim=-1)  # (L, V)
            logp = {lang: [round(x, 3) for x in torch.logsumexp(lp[:, torch.as_tensor(i, device=lp.device)], -1).tolist()]
                    for lang, i in ids.items() if i}
            top = lp.argmax(-1).tolist()
            out.append({"logp": logp, "top1": [tokenizer.decode([t]).strip() or tokenizer.decode([t]) for t in top]})
    return out


def run_test(model, processor, test: LangTest, spec=None, stats=None, skip: list[int] | None = None,
             max_new_tokens: int = 12) -> dict:
    """One language variant under one condition. The lesion block is entered fresh, so a noise
    lesion restarts from spec.seed for every language."""
    import contextlib
    import time

    import torch

    from metalesionlab.compress import SkipLayers
    from metalesionlab.lesions import LesionSpec, lesion
    from metalesionlab.model_lab import generate_with_lens, stop_token_ids, to_device

    spec = spec if isinstance(spec, LesionSpec) else LesionSpec.from_dict(spec or {})
    tok, stops = processor.tokenizer, stop_token_ids(model, processor.tokenizer)
    said, lenses = [], []
    torch.cuda.synchronize()
    t0 = time.time()
    skipper = SkipLayers(model, skip) if skip else contextlib.nullcontext()
    with skipper, lesion(model, spec, stats):
        start = 0
        for batch in test.batches:
            n = batch["input_ids"].shape[0]
            toks, resid = generate_with_lens(model, to_device(batch, model.device), stops, max_new_tokens)
            said += [tok.decode(t, skip_special_tokens=True).strip() for t in toks]
            lenses += lens_names(model, tok, resid, test.name_ids[start:start + n])
            start += n
    torch.cuda.synchronize()
    return {"variant": test.variant, "lang": test.lang, "prompt": test.prompt, "seconds": round(time.time() - t0, 2),
            "items": [{"en": it.en, "target": it.target(test.lang), "said": s, "lens": ln}
                      for it, s, ln in zip(test.items, said, lenses)]}


def pooled_unit_stats(model, processor, sets_dir: Path, variants: tuple[str, ...], batch_size: int = 10):
    """Reference statistics for mean and noise lesions from the held-out drawings of the English
    set (the other Muse Image picture of each word, never a test picture), each named with every
    variant's prompt, so no language sets the lesion's scale."""
    from PIL import Image

    from metalesionlab.lesions import compute_unit_stats
    from metalesionlab.localizers import localizer_images
    from metalesionlab.model_lab import build_batches, to_device

    trials = localizer_images([Path(sets_dir) / SET_FOR["en"]], held_out=True)
    examples = [(Image.open(t.image).convert("RGB"), PROMPTS[v]) for v in variants for t in trials]
    batches = [to_device(b, model.device) for b in build_batches(processor, examples, batch_size)]
    source = f"{SET_FOR['en']}: {len(trials)} held-out drawings x prompts {'/'.join(variants)}"
    return compute_unit_stats(model, batches, source=source)


# --- analysis ---------------------------------------------------------------------------

def correct_matrix(runs: list[dict], words: list[str]) -> np.ndarray:
    """(items, seeds) 0/1 matrix from a condition's runs (one per seed), in `words` order."""
    cols = []
    for r in sorted(runs, key=lambda r: r.get("seed") or 0):
        by = {row["en"]: row["code"] == "Correct" for row in r["items"]}
        cols.append([float(by[w]) for w in words])
    return np.array(cols).T


def flag_matrix(runs: list[dict], words: list[str], key: str) -> np.ndarray:
    cols = []
    for r in sorted(runs, key=lambda r: r.get("seed") or 0):
        by = {row["en"]: bool(row.get(key)) for row in r["items"]}
        cols.append([float(by[w]) for w in words])
    return np.array(cols).T


def bootstrap_drop_diff(conds: list[tuple[np.ndarray, np.ndarray]], base_en: np.ndarray, base_l: np.ndarray,
                        keep: np.ndarray | None = None, n_boot: int = 10000, seed: int = 0) -> dict:
    """Paired by picture: mean over conditions of [drop in L - drop in English], where a drop is
    intact minus lesioned accuracy. conds = [(en (items, seeds), L (items, seeds))]. Pictures are
    resampled once per replicate (shared by every condition, as they are the same pictures) and
    seeds are resampled within each condition. `keep` restricts to some pictures."""
    rng = np.random.default_rng(seed)
    idx_all = np.flatnonzero(keep) if keep is not None else np.arange(len(base_en))
    n = len(idx_all)

    def stat(items, seed_draws):
        vals = []
        for (en, l), sd in zip(conds, seed_draws):
            e, x = en[items][:, sd], l[items][:, sd]
            drop_en = base_en[items][:, None] - e
            drop_l = base_l[items][:, None] - x
            vals.append((drop_l - drop_en).mean())
        return float(np.mean(vals))

    point = stat(idx_all, [np.arange(en.shape[1]) for en, _ in conds])
    boots = np.empty(n_boot)
    for b in range(n_boot):
        items = idx_all[rng.integers(0, n, n)]
        seed_draws = [rng.integers(0, en.shape[1], en.shape[1]) for en, _ in conds]
        boots[b] = stat(items, seed_draws)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"diff": round(point, 4), "ci95": [round(float(lo), 4), round(float(hi), 4)], "n_items": int(n),
            "n_conditions": len(conds), "n_boot": n_boot}


def bootstrap_mean(mats: list[np.ndarray], keep: np.ndarray | None = None, n_boot: int = 10000,
                   seed: int = 0) -> dict:
    """Mean of 0/1 (items, seeds) matrices pooled over conditions, with a picture-and-seed bootstrap CI."""
    rng = np.random.default_rng(seed)
    idx_all = np.flatnonzero(keep) if keep is not None else np.arange(mats[0].shape[0])
    n = len(idx_all)
    point = float(np.mean([m[idx_all].mean() for m in mats]))
    boots = np.empty(n_boot)
    for b in range(n_boot):
        items = idx_all[rng.integers(0, n, n)]
        boots[b] = np.mean([m[items][:, rng.integers(0, m.shape[1], m.shape[1])].mean() for m in mats])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"mean": round(point, 4), "ci95": [round(float(lo), 4), round(float(hi), 4)], "n_items": int(n),
            "n_conditions": len(mats)}


def sign_flip_test(d: np.ndarray, n_perm: int = 200000, seed: int = 0) -> float:
    """Two-sided p for mean(d) = 0, flipping the sign of each picture's difference at random."""
    d = d[~np.isnan(d)]
    if not len(d) or np.allclose(d, 0):
        return 1.0
    rng = np.random.default_rng(seed)
    obs = abs(d.mean())
    signs = rng.choice([-1.0, 1.0], size=(n_perm, len(d)))
    null = np.abs((signs * d).mean(axis=1))
    return float((np.sum(null >= obs - 1e-12) + 1) / (n_perm + 1))


def wilson(k: float, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [0.0, 1.0]
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, mid - half), 4), round(min(1.0, mid + half), 4)]


def disjoint_lens_items(items: list[BiItem], name_ids: dict, lang: str, pieces: dict | None = None) -> list[str]:
    """Pictures whose English and `lang` names start with different tokens (and different token
    strings, ignoring a leading space), so the word lens can tell them apart: cactus/cactus or
    helicopter/helicóptero, which share a first token, are dropped."""
    out = []
    for it in items:
        a, b = set(name_ids[it.en].get("en", [])), set(name_ids[it.en].get(lang, []))
        if not (a and b) or a & b:
            continue
        if pieces and set(pieces[it.en]["en"]) & set(pieces[it.en][lang]):
            continue
        out.append(it.en)
    return out


def strip_pieces(raw_pieces: dict) -> dict:
    """name_ids.json "pieces" -> word -> lang -> set of token strings without the leading space,
    comparable with the lens's stored top-1 strings."""
    return {w: {lang: {p.strip() for p in ps if p.strip()} for lang, ps in by.items()} for w, by in raw_pieces.items()}


CONFIDENT = 0.05  # a name "leads with confidence" when its first token has lens p >= this


def lens_pivot(runs: list[dict], words: list[str], lang: str, other: str = "en", pieces: dict | None = None) -> dict:
    """Over runs of `lang` trials and the pictures in `words`, per layer: mean p of each name's
    first token; the share of trials where the `other` name is above the `lang` name with
    p >= CONFIDENT; and with `pieces`, the share where the lens's top-1 token starts each name."""
    rows = [row for r in runs for row in r["items"] if row["en"] in words]
    if not rows:
        return {}
    a = np.array([row["lens"]["logp"][other] for row in rows])
    b = np.array([row["lens"]["logp"][lang] for row in rows])
    pa, pb = np.exp(a), np.exp(b)
    out = {"n_trials": len(rows), "mean_p_other": np.round(pa.mean(0), 4).tolist(),
           "mean_p_lang": np.round(pb.mean(0), 4).tolist(),
           "frac_other_above_confident": np.round(((a > b) & (pa >= CONFIDENT)).mean(0), 4).tolist(),
           "frac_lang_above_confident": np.round(((b > a) & (pb >= CONFIDENT)).mean(0), 4).tolist()}
    if pieces:
        top_o = np.array([[t in pieces[row["en"]][other] for t in row["lens"]["top1"]] for row in rows])
        top_l = np.array([[t in pieces[row["en"]][lang] for t in row["lens"]["top1"]] for row in rows])
        out["frac_top1_other"] = np.round(top_o.mean(0), 4).tolist()
        out["frac_top1_lang"] = np.round(top_l.mean(0), 4).tolist()
        # Per trial: did the other language's name lead the lens at any layer before the last?
        out["share_trials_other_top1_any_layer"] = round(float(top_o[:, :-1].any(1).mean()), 4)
        out["share_trials_other_confident_above_any_layer"] = round(
            float(((a > b) & (pa >= CONFIDENT))[:, :-1].any(1).mean()), 4)
    return out


@dataclass
class Condition:
    """A planned condition: a lesion spec recipe (see scripts/bilingual_run.py) and its seeds."""
    name: str
    family: str
    dose: float | None = None
    seeds: list[int] = field(default_factory=lambda: [0])
    recipe: dict = field(default_factory=dict)
    skip: list[int] = field(default_factory=list)
    stats: str = "pooled"  # which reference statistics: pooled, en or es (robustness check)
    variants: tuple[str, ...] = ("en", "es", "fr", "pt", "es_xen")

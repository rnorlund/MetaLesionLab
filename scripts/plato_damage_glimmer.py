"""Plato's Chair, damage: Muse Glimmer reads the pictures (GPU part; run on a lab GPU with Glimmer).

  label-sdxl --input DIR --out DIR        which kind does each damaged SDXL picture show? The kind
                                          labeler of plato_kinds_label.py (multiple choice, letter
                                          logits, forward and reversed order averaged) with this
                                          experiment's kinds (plato_damage.CONCEPT_KINDS). Pictures are
                                          ink-cropped to 448 px here. One file per condition.
  lesion --pictures DIR --out DIR --conditions ...
                                          the understanding arm: a DAMAGED Glimmer looks at Muse
                                          Image's named-kind doodles (kinds_input/ai_doodle_listed,
                                          picture p<i> shows kind i) and answers (1) the multiple-choice
                                          kind question and (2) "Name the object in this picture with
                                          exactly one word." Does a throne become "a plain chair"?

Conditions for `lesion`: intact, <family>@<dose> with the families below, and <family>-random@<dose>,
a random-unit control with the same number of units in the same layers (localizers.random_control).
Localizers (runs/localizers/<name>.pt) and mean-ablation statistics (runs/cache/unit_stats_demo_en.pt)
come from the lesion lab and are read from --runs.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from metalesionlab.plato import BY_KEY as PLATO_KEYS, CONCEPTS, kind_options, labeling_prompt, load_dir  # noqa: E402
from metalesionlab.plato_damage import CONCEPT_KINDS, KIND_PROMPTS  # noqa: E402

SIDE = 448
FAMILIES = {  # name -> how a dose becomes a lesion
    "language-mlp-mean": ("localizer", "language_en", "mlp", "mean"),
    "naming-mlp-mean": ("localizer", "naming_en", "mlp", "mean"),
    "visual-mlp-mean": ("localizer", "visual_en", "mlp", "mean"),
    "early-band-noise": ("site", "layers:8-15", None, "noise"),
    "late-band-noise": ("site", "layers:40-47", None, "noise"),
}


def build_spec(condition: str, runs: Path, dims, cache: dict):
    from metalesionlab.lesions import LesionSpec, site_spec
    from metalesionlab.localizers import Localizer, localizer_spec, random_control

    if condition == "intact":
        return LesionSpec(name="intact")
    fam, _, dose = condition.partition("@")
    dose = float(dose)
    control = fam.endswith("-random")
    base = fam.removesuffix("-random")
    kind, what, units, method = FAMILIES[base]
    if kind == "site":
        spec = site_spec(what, method, noise_scale=dose)
    else:
        loc = cache.setdefault(what, Localizer.load(runs / "localizers" / f"{what}.pt"))
        spec = localizer_spec(loc, units, dose, method)
        if control:
            spec = random_control(spec, dims, seed=0)
    spec.name = condition
    spec.recipe = {**spec.recipe, "family": fam, "dose": dose}
    return spec


class Reader:
    def __init__(self, runs: Path, batch: int):
        import torch

        from metalesionlab import glimmer
        from metalesionlab.lesions import UnitStats, site_dims

        t0 = time.time()
        self.model, self.processor = glimmer.load(fp8=True)
        print(f"loaded Glimmer in {time.time() - t0:.0f}s", flush=True)
        self.dims = site_dims(self.model)
        stats = runs / "cache" / "unit_stats_demo_en.pt"
        self.stats = UnitStats.load(stats, self.model.device) if stats.exists() else None
        self.batch, self.runs, self.cache = batch, runs, {}
        self.torch = torch

    def mcq(self, images, concept, kinds) -> list[dict]:
        """Forward and reversed option order, letter logits, averaged (as plato_kinds_label.py)."""
        from metalesionlab.model_lab import build_batches, to_device
        from plato_kinds_label import letter_ids, option_probs

        fwd, rev = kind_options(concept, kinds), kind_options(concept, kinds[::-1])
        k = len(kinds)
        back = list(range(k - 1, -1, -1)) + [k, k + 1]
        ids = letter_ids(self.processor.tokenizer, len(fwd))
        probs = {}
        for name, opts in (("fwd", fwd), ("rev", rev)):
            key = (concept.key, name, len(images), id(images[0]))
            batches = self._batches.get(key)
            if batches is None:
                batches = build_batches(self.processor, [(im, labeling_prompt(concept, opts)) for im in images],
                                        self.batch)
                self._batches[key] = batches
            p_all = []
            for b in batches:
                with self.torch.no_grad():
                    logits = self.model(**to_device(b, self.model.device), logits_to_keep=1).logits[:, -1]
                p_all.append(option_probs(logits, ids)[0])
            probs[name] = np.concatenate(p_all)
        p_rev = np.zeros_like(probs["rev"])
        p_rev[:, back] = probs["rev"]
        p = (probs["fwd"] + p_rev) / 2
        return [{"label": int(np.argmax(p[i])), "p": [round(float(x), 4) for x in p[i]],
                 "label_fwd": int(np.argmax(probs["fwd"][i])), "label_rev": int(np.argmax(p_rev[i]))}
                for i in range(len(images))]

    def name(self, images, key) -> list[str]:
        from metalesionlab.model_lab import build_batches, naming_prompt, stop_token_ids, generate_with_lens, to_device

        batches = self._batches.get(("name", key))
        if batches is None:
            batches = build_batches(self.processor, [(im, naming_prompt("en")) for im in images], self.batch)
            self._batches[("name", key)] = batches
        stops = stop_token_ids(self.model, self.processor.tokenizer)
        out = []
        for b in batches:
            toks, _ = generate_with_lens(self.model, to_device(b, self.model.device), stops, 12)
            out += [self.processor.tokenizer.decode(t, skip_special_tokens=True).strip() for t in toks]
        return out

    def yesno(self, images, prompt: str, cache_key) -> list[float]:
        """P(yes) from the yes/no token logits at the first answer position (softmax over the two)."""
        from metalesionlab.model_lab import build_batches, to_device

        batches = self._batches.get(("yesno", cache_key))
        if batches is None:
            batches = build_batches(self.processor, [(im, prompt) for im in images], self.batch)
            self._batches[("yesno", cache_key)] = batches
        tok = self.processor.tokenizer
        ids = []
        for words in (("Yes", " Yes", "yes", " yes"), ("No", " No", "no", " no")):
            got = set()
            for w in words:
                t = tok(w, add_special_tokens=False)["input_ids"]
                if len(t) == 1:
                    got.add(t[0])
            ids.append(sorted(got))
        out = []
        for b in batches:
            with self.torch.no_grad():
                logits = self.model(**to_device(b, self.model.device), logits_to_keep=1).logits[:, -1].float()
            logp = self.torch.log_softmax(logits, dim=-1)
            yes = self.torch.logsumexp(logp[:, ids[0]], dim=-1)
            no = self.torch.logsumexp(logp[:, ids[1]], dim=-1)
            out += self.torch.sigmoid(yes - no).cpu().tolist()
        return [round(x, 4) for x in out]

    _batches: dict = {}


IS_A = "Is this a drawing of {phrase}? Answer yes or no."
CLEAN = ("Is this a clean, simple line drawing, with black lines on a plain white background and no color, "
         "shading or texture? Answer yes or no.")


def cmd_label_sdxl(args):
    from PIL import Image

    from metalesionlab.lesions import LesionSpec, lesion

    reader = Reader(args.runs, args.batch)
    args.out.mkdir(parents=True, exist_ok=True)
    conds = sorted(p.name for p in args.input.iterdir() if p.is_dir() and (args.conditions is None or p.name in args.conditions))
    for cond in conds:
        out = args.out / f"{cond}.json"
        if out.exists():
            continue
        t0 = time.time()
        rows = []
        for concept_key, (plain, kinds) in CONCEPT_KINDS.items():
            concept = PLATO_KEYS[concept_key]
            prompts = [p for p in KIND_PROMPTS if p.concept == concept_key]
            files, truth = [], []
            for p in prompts:
                for f in load_dir(args.input / cond / p.key):
                    files.append((p.key, f))
                    truth.append(None if p.is_plain else kinds.index(p.kind))
            if not files:
                continue
            # ink-cropped 448 px copies made on the Mac (plato_damage_analyze.py crop; no scipy here)
            images = [Image.open(args.cropped / cond / key / f.name).convert("RGB") for key, f in files]
            raw = [Image.open(f).convert("RGB").resize((SIDE, SIDE)) for _, f in files]  # style: not cropped or flattened
            reader._batches.clear()
            with lesion(reader.model, LesionSpec(name="intact")):
                res = reader.mcq(images, concept, kinds)
                is_a = reader.yesno(images, IS_A.format(phrase=plain), f"{cond}|{concept_key}|is_a")
                clean = reader.yesno(raw, CLEAN, f"{cond}|{concept_key}|clean")
                names = reader.name(images, f"{cond}|{concept_key}") if args.naming else [None] * len(images)
            for (key, f), t, r, y, cl, said in zip(files, truth, res, is_a, clean, names):
                rows.append({"key": key, "file": f.name, "concept": concept_key, "true_kind": t, "p_is_a": y,
                             "p_clean": cl, "said": said, **r})
        out.write_text(json.dumps({"condition": cond, "kinds": {k: v[1] for k, v in CONCEPT_KINDS.items()},
                                   "items": rows}, indent=0))
        print(f"{cond:24s} {len(rows)} pictures in {time.time() - t0:.0f}s", flush=True)


def cmd_lesion(args):
    from PIL import Image

    from metalesionlab.lesions import lesion

    reader = Reader(args.runs, args.batch)
    keys = args.keys or [c.key for c in CONCEPTS]
    data = []
    for key in keys:
        files = load_dir(args.pictures / key)
        kinds_file = args.pictures.parent / "kinds" / f"{key}.json"
        if not files or not kinds_file.exists():
            continue
        c = PLATO_KEYS[key]
        kinds = json.loads(kinds_file.read_text())[:c.n_ai]
        data.append((c, kinds, files, [Image.open(f).convert("RGB") for f in files]))
    print(f"{len(data)} concepts, {sum(len(d[2]) for d in data)} pictures", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    for cond in args.conditions:
        out = args.out / f"{cond}.json"
        if out.exists():
            continue
        spec = build_spec(cond, args.runs, reader.dims, reader.cache)
        t0 = time.time()
        rows = []
        with lesion(reader.model, spec, reader.stats):
            for c, kinds, files, images in data:
                res = reader.mcq(images, c, kinds)
                names = reader.name(images, c.key) if not args.no_naming else [None] * len(images)
                for f, r, said in zip(files, res, names):
                    rows.append({"key": c.key, "file": f.name, "true_kind": int(f.stem[1:]), "n_kinds": len(kinds),
                                 "said": said, **r})
        n_units = spec.counts(reader.dims) if not spec.is_intact else {}
        acc = np.mean([r["label"] == r["true_kind"] for r in rows])
        plain = np.mean([r["label"] == r["n_kinds"] for r in rows])
        out.write_text(json.dumps({"condition": cond, "spec": spec.to_dict(units=False),
                                   "units": {"mlp": n_units.get("mlp"), "heads": n_units.get("heads")},
                                   "items": rows}, indent=0))
        print(f"{cond:28s} kind acc {acc:.3f}, plain {plain:.3f} ({len(rows)} pictures, {time.time() - t0:.0f}s)",
              flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("label-sdxl")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--conditions", nargs="*")
    p.add_argument("--cropped", type=Path, required=True, help="ink-cropped 448 px copies, same layout as --input")
    p.add_argument("--naming", action="store_true", help="also ask for a one-word name (what did it turn into?)")
    p.set_defaults(fn=cmd_label_sdxl)
    p = sub.add_parser("lesion")
    p.add_argument("--pictures", type=Path, required=True, help="kinds_input/ai_doodle_listed")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--conditions", nargs="+", required=True)
    p.add_argument("--keys", nargs="*")
    p.add_argument("--no-naming", action="store_true")
    p.set_defaults(fn=cmd_lesion)
    for p in sub.choices.values():
        p.add_argument("--runs", type=Path, default=Path("runs"))
        p.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

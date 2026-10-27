"""Plato's Cratylus: human round-to-spiky axis, roundness of every drawing, and the pre-registered contrasts.

  human    stream the first 200 recognized Quick, Draw! drawings of circle, cloud, star, zigzag and
           lightning (CC BY 4.0), rendered to $CRATYLUS_DIR/human/<category>/NNN.png
  measure  roundness of every Muse Image drawing (solidity, corners) and DINOv2 embeddings of the AI and
           human drawings (ink-cropped, as in the core Plato's Chair experiment) -> measures.json, embeddings.npz
  analyze  axis scores, the contrasts in docs/plato_cratylus_plan.md and the choice arm
           (cratylus_choice_glimmer.json from the GPU, choice_spark.json) -> results.json
  spark    Muse Spark's sampled answers in the choice arm (paid, about 96 calls) -> choice_spark.json

Excluded pictures (letters or text, checked by eye) are listed in $CRATYLUS_DIR/excluded.json:
{"<slug>/p<i>.png": "reason"}.
"""
import argparse
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from metalesionlab import plato_cratylus as pk  # noqa: E402
from metalesionlab import plato_shapes as ps  # noqa: E402
from metalesionlab.plato import (QUICKDRAW_URL, ci, ink_crop, load_dir, render_strokes,  # noqa: E402
                                 stream_quickdraw, to_jsonable)

D = Path(os.environ.get("CRATYLUS_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/cratylus"))
CATEGORIES = pk.ROUND_CATEGORIES + pk.SPIKY_CATEGORIES
MEASURES = ("solidity", "corners", "axis")
# sign so that a positive contrast always means "spikier": solidity falls as shapes get spiky
SPIKY_SIGN = {"solidity": -1, "corners": 1, "axis": 1}


def excluded() -> dict:
    p = D / "excluded.json"
    return json.loads(p.read_text()) if p.exists() else {}


def ai_pictures() -> list[tuple[str, Path]]:
    out = []
    skip = excluded()
    for w in pk.WORDS:
        for p in load_dir(D / "ai" / pk.slug(w.word)):
            if f"{pk.slug(w.word)}/{p.name}" not in skip:
                out.append((w.word, p))
    return out


def cmd_human(args):
    for cat in CATEGORIES:
        folder = D / "human" / cat
        if len(list(folder.glob("*.png"))) >= args.keep:
            print(cat, "cached")
            continue
        kept = stream_quickdraw(cat, keep=args.keep, max_lines=args.max_lines)
        folder.mkdir(parents=True, exist_ok=True)
        for i, rec in enumerate(kept):
            render_strokes(rec["drawing"]).save(folder / f"{i:03d}.png")
        (folder / "meta.json").write_text(json.dumps({
            "category": cat, "n": len(kept), "source": QUICKDRAW_URL.format(category=cat),
            "filter": "first drawings in file order with recognized=true", "license": "CC BY 4.0"}, indent=1))
        print(cat, len(kept), flush=True)


def cmd_measure(args):
    from metalesionlab.plato import Embedder

    rows = []
    pics = ai_pictures()
    for word, p in pics:
        r, _ = pk.roundness(Image.open(p))
        rows.append({"word": word, "file": f"{pk.slug(word)}/{p.name}", "solidity": r.solidity, "corners": r.corners,
                     "n_shapes": r.n_shapes, "fill_ratio": r.fill_ratio, "closing_radius": r.closing_radius})
    # choice-arm shapes, for reference on the same scales
    shapes = []
    for seed in range(8):
        for kind, fn in (("round", pk.round_shape), ("spiky", pk.spiky_shape)):
            m = fn(seed)
            shapes.append({"kind": kind, "seed": seed, "solidity": ps.solidity(m), "corners": ps.corner_count(m)})
    (D / "measures.json").write_text(json.dumps(to_jsonable({"ai": rows, "choice_shapes": shapes}), indent=0))
    embed = Embedder()
    ai_imgs = [ink_crop(Image.open(p).convert("RGB")) for _, p in pics]
    human_files = {cat: load_dir(D / "human" / cat) for cat in CATEGORIES}
    human_imgs = [ink_crop(Image.open(f).convert("RGB")) for cat in CATEGORIES for f in human_files[cat]]
    shape_imgs = []
    for seed in range(8):
        for fn in (pk.round_shape, pk.spiky_shape):
            m = fn(seed)
            shape_imgs.append(ink_crop(Image.fromarray(np.where(m, 0, 255).astype(np.uint8)).convert("RGB")))
    e_ai, e_h, e_s = embed(ai_imgs), embed(human_imgs), embed(shape_imgs)
    np.savez(D / "embeddings.npz", ai_cls=e_ai["cls"], human_cls=e_h["cls"], shapes_cls=e_s["cls"],
             ai_patch=e_ai["patch_mean"], human_patch=e_h["patch_mean"],
             ai_files=np.array([f"{pk.slug(w)}/{p.name}" for w, p in pics]),
             human_cats=np.array([cat for cat in CATEGORIES for _ in human_files[cat]]))
    print(f"measured {len(rows)} AI pictures; embedded {len(ai_imgs)} AI, {len(human_imgs)} human, "
          f"{len(shape_imgs)} shapes")


def axis_scores(x: np.ndarray, round_c: np.ndarray, spiky_c: np.ndarray) -> np.ndarray:
    """Projection on the round->spiky axis, 0 at the round centroid and 1 at the spiky one. Vectors are
    L2-normalized first (cosine geometry, as in the spread measure)."""
    def nrm(a):
        return a / np.linalg.norm(a, axis=-1, keepdims=True)
    x, r, s = nrm(x), round_c, spiky_c
    d = s - r
    return (x - r) @ d / (d @ d)


def human_axis(e: dict, kind: str = "cls"):
    def nrm(a):
        return a / np.linalg.norm(a, axis=-1, keepdims=True)
    h = nrm(e[f"human_{kind}"])
    cats = e["human_cats"]
    is_round = np.isin(cats, pk.ROUND_CATEGORIES)
    # each category weighs the same within its side
    rc = np.mean([h[cats == c].mean(0) for c in pk.ROUND_CATEGORIES], 0)
    sc = np.mean([h[cats == c].mean(0) for c in pk.SPIKY_CATEGORIES], 0)
    return rc, sc, is_round


def cmd_analyze(args):
    meas = json.loads((D / "measures.json").read_text())
    e = dict(np.load(D / "embeddings.npz"))
    rc, sc, is_round = human_axis(e)
    ai_axis = dict(zip(e["ai_files"], axis_scores(e["ai_cls"], rc, sc)))
    human_scores = axis_scores(e["human_cls"], rc, sc)
    rcp, scp, _ = human_axis(e, "patch")
    ai_axis_patch = dict(zip(e["ai_files"], axis_scores(e["ai_patch"], rcp, scp)))
    shapes_axis = axis_scores(e["shapes_cls"], rc, sc)
    rows = meas["ai"]
    for r in rows:
        r["axis"] = float(ai_axis[r["file"]])
        r["axis_patch"] = float(ai_axis_patch[r["file"]])
    by_word = {}
    for r in rows:
        by_word.setdefault(r["word"], []).append(r)

    def vals(word, m):
        return np.array([r[m] for r in by_word.get(word, []) if r[m] is not None and np.isfinite(r[m])], float)

    words = {}
    for w in pk.WORDS:
        rs = by_word.get(w.word, [])
        words[w.word] = {"group": w.group, "consonants": w.consonants, "vowels": w.vowels, "sound": w.sound,
                         "n": len(rs), **{m: {"mean": float(np.mean(vals(w.word, m))) if len(vals(w.word, m)) else None,
                                              "ci95": ci(boot_mean(vals(w.word, m))) if len(vals(w.word, m)) > 1 else None}
                                          for m in MEASURES + ("axis_patch",)},
                         "share_with_corners": float(np.mean(vals(w.word, "corners") > 0)) if rs else None}

    def signed(word, m):
        return SPIKY_SIGN.get(m, 1) * vals(word, m)

    contrasts = {}
    for name, (a, b) in {"kiki_vs_bouba": ("bouba", "kiki"), "takete_vs_maluma": ("maluma", "takete")}.items():
        contrasts[name] = {m: pk.bootstrap_contrast(signed(a, m), signed(b, m), seed=1) for m in MEASURES + ("axis_patch",)}
        # also raw (unsigned) means for the text
        for m in MEASURES:
            contrasts[name][m]["means"] = {a: float(vals(a, m).mean()), b: float(vals(b, m).mean())}
    contrasts["spiky_vs_round_class"] = {m: pk.hierarchical_contrast([signed(w, m) for w in pk.ROUND_CLASS],
                                                                      [signed(w, m) for w in pk.SPIKY_CLASS], seed=2)
                                         for m in MEASURES}
    for m in MEASURES:  # pooled AUC across the classes, for a single readable number
        x = np.concatenate([signed(w, m) for w in pk.ROUND_CLASS])
        y = np.concatenate([signed(w, m) for w in pk.SPIKY_CLASS])
        contrasts["spiky_vs_round_class"][m]["pooled"] = pk.bootstrap_contrast(x, y, seed=3)
    grid = {}
    for m in MEASURES:
        cell = {(c, v): [signed(w.word, m) for w in pk.GRID if w.consonants == c and w.vowels == v]
                for c in ("soft", "hard") for v in ("rounded", "unrounded")}
        grid[m] = {
            "consonant_effect": pk.hierarchical_contrast(cell[("soft", "rounded")] + cell[("soft", "unrounded")],
                                                         cell[("hard", "rounded")] + cell[("hard", "unrounded")], seed=4),
            "vowel_effect": pk.hierarchical_contrast(cell[("soft", "rounded")] + cell[("hard", "rounded")],
                                                     cell[("soft", "unrounded")] + cell[("hard", "unrounded")], seed=5),
            "cells": {f"{c}/{v}": float(np.mean([g.mean() for g in cell[(c, v)]])) for (c, v) in cell}}
    controls = {}
    for m in MEASURES:
        controls[m] = {
            "round_class": float(np.mean([vals(w, m).mean() for w in pk.ROUND_CLASS])),
            "spiky_class": float(np.mean([vals(w, m).mean() for w in pk.SPIKY_CLASS])),
            "neutral_controls": float(np.mean([vals(w.word, m).mean() for w in pk.WORDS if w.group == "control"])),
            "baseline": float(vals(pk.BASELINE, m).mean()) if len(vals(pk.BASELINE, m)) else None}
    spelling = {w.word: {m: float(vals(w.word, m).mean()) if len(vals(w.word, m)) else None for m in MEASURES}
                for w in pk.WORDS if w.group == "spelling"}
    human_ref = {cat: {"axis_mean": float(human_scores[e["human_cats"] == cat].mean()),
                       "n": int((e["human_cats"] == cat).sum())} for cat in CATEGORIES}
    shapes = meas["choice_shapes"]
    for s, a in zip(shapes, shapes_axis):
        s["axis"] = float(a)
    out = {"words": words, "contrasts": contrasts, "grid": grid, "controls": controls, "spelling": spelling,
           "human_axis": human_ref, "choice_shapes": shapes, "pictures": rows,
           "n_pictures": len(rows), "excluded": excluded(),
           "multi_shape_pictures": sum(r["n_shapes"] > 1 for r in rows),
           "unclosed_pictures": [r["file"] for r in rows if r["fill_ratio"] < 1.5]}
    out["choice"] = choice_summary()
    (D / "results.json").write_text(json.dumps(to_jsonable(out), indent=1))
    k = contrasts["kiki_vs_bouba"]
    print({m: (round(k[m]["auc"], 3), [round(v, 3) for v in k[m]["auc_ci"]]) for m in MEASURES})
    print("class", {m: (round(contrasts["spiky_vs_round_class"][m]["diff"], 3),
                        [round(v, 3) for v in contrasts["spiky_vs_round_class"][m]["diff_ci"]]) for m in MEASURES})
    print("grid", {m: {k2: round(v["diff"], 3) for k2, v in grid[m].items() if k2 != "cells"} for m in MEASURES})


def boot_mean(x: np.ndarray, reps: int = 2000, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.array([x[rng.integers(0, len(x), len(x))].mean() for _ in range(reps)])


def choice_summary() -> dict:
    out = {}
    g = D / "cratylus_choice_glimmer.json"
    if g.exists():
        data = json.loads(g.read_text())
        rows = data["image"]
        per = {}
        for r in rows:
            per.setdefault(r["word"], {}).setdefault(r["pair"], []).append(r["p_round"])
        glim = {}
        for word, pairs in per.items():
            pair_means = np.array([np.mean(v) for v in pairs.values()])  # both placements averaged
            sides = [r for r in rows if r["word"] == word]
            glim[word] = {"p_round": float(pair_means.mean()), "ci95": ci(boot_mean(pair_means)),
                          "mass": float(np.mean([r["mass"] for r in sides])),
                          "p_left_bias": float(np.mean([r["p_left"] / r["mass"] for r in sides])),
                          "n_pairs": len(pair_means)}
        text = {}
        for r in data["text"]:
            text.setdefault(r["word"], []).append(r["p_round"])
        out["glimmer_picture"] = glim
        out["glimmer_text"] = {w: {"p_round": float(np.mean(v)), "orders": v} for w, v in text.items()}
        out["glimmer_match"] = match_rate(glim)
        out["glimmer_text_match"] = match_rate({w: {"p_round": v["p_round"]} for w, v in out["glimmer_text"].items()})
        # people's headline counts a person only if BOTH trials match; for Glimmer, the chance that two
        # independent answers (bouba on a pair, kiki on the same pair and placement) both match
        both = [rb["p_round"] * (1 - rk["p_round"]) for rb in rows if rb["word"] == "bouba"
                for rk in rows if rk["word"] == "kiki" and rk["pair"] == rb["pair"]
                and rk["round_side"] == rb["round_side"]]
        out["glimmer_both_match"] = {"p": float(np.mean(both)), "ci95": ci(boot_mean(np.array(both)))}
        out["glimmer_grid"] = choice_grid({w: [np.mean(v) for v in per[w].values()] for w in per})
        out["glimmer_text_grid"] = choice_grid({w: v for w, v in text.items()})
    s = D / "choice_spark.json"
    if s.exists():
        rows = json.loads(s.read_text())["answers"]
        spark = {}
        for r in rows:
            spark.setdefault(r["word"], []).append(r["chose"] == "round" if r["chose"] in ("round", "spiky") else np.nan)
        out["spark"] = {}
        for w, v in spark.items():
            arr = np.array(v, float)
            ok = arr[np.isfinite(arr)]
            out["spark"][w] = {"p_round": float(ok.mean()) if len(ok) else None,
                               "ci95": ci(boot_mean(ok)) if len(ok) > 1 else None, "n": int(len(ok)),
                               "unparsed": int((~np.isfinite(arr)).sum())}
        out["spark_match"] = match_rate(out["spark"])
        keyed = {(r["word"], r["pair"], r["round_side"]): r["chose"] for r in rows}
        both = [keyed[("bouba", pair, side)] == "round" and keyed[("kiki", pair, side)] == "spiky"
                for (w, pair, side) in keyed if w == "bouba" and ("kiki", pair, side) in keyed]
        out["spark_both_match"] = {"p": float(np.mean(both)), "n": len(both)}
        out["spark_grid"] = choice_grid({w: [x for x in v if np.isfinite(x)] for w, v in spark.items()})
    return out


def choice_grid(per_word: dict) -> dict:
    """Consonant and vowel effects on p(round) in the grid words (positive = the expected direction: soft
    consonants or rounded vowels pick the round shape more), with a two-level bootstrap."""
    def cells(cons=None, vow=None):
        return [np.asarray(per_word[w.word], float) for w in pk.GRID if w.word in per_word
                and (cons is None or w.consonants == cons) and (vow is None or w.vowels == vow)]
    if not cells():
        return {}
    return {"consonant_effect": pk.hierarchical_contrast(cells(cons="hard"), cells(cons="soft"), seed=6),
            "vowel_effect": pk.hierarchical_contrast(cells(vow="unrounded"), cells(vow="rounded"), seed=7),
            "cells": {f"{c}/{v}": float(np.mean([g.mean() for g in cells(c, v)])) for c in ("soft", "hard")
                      for v in ("rounded", "unrounded")}}


def match_rate(per_word: dict) -> dict:
    """Mean of p(round | round-sounding word) and p(spiky | spiky-sounding word), for the classic pair, the
    classic four and the classes."""
    def p(w):
        return per_word.get(w, {}).get("p_round")
    res = {}
    for name, rounds, spikies in (("bouba_kiki", ["bouba"], ["kiki"]), ("maluma_takete", ["maluma"], ["takete"]),
                                  ("classes", list(pk.ROUND_CLASS), list(pk.SPIKY_CLASS))):
        vr = [p(w) for w in rounds if p(w) is not None]
        vs = [1 - p(w) for w in spikies if p(w) is not None]
        if vr and vs:
            res[name] = float((np.mean(vr) + np.mean(vs)) / 2)
    return res


def cmd_spark(args):
    from metalesionlab.meta_api import MetaAPI, image_data_url, retry_network, spent

    if spent() > 70:
        raise SystemExit("ledger above $70")
    api = MetaAPI()
    rng = np.random.default_rng(0)
    path = D / "choice_spark.json"
    done = json.loads(path.read_text()) if path.exists() else {"answers": []}
    seen = {(r["word"], r["pair"], r["round_side"]) for r in done["answers"]}
    words = [w.word for w in pk.WORDS if w.group in ("classic", "grid", "control")]
    pairs = sorted(rng.choice(8, args.pairs, replace=False).tolist())
    start = spent()
    for word in words:
        for pair in pairs:
            for round_side in ("left", "right"):
                if (word, pair, round_side) in seen:
                    continue
                r, s = pk.round_shape(pair), pk.spiky_shape(pair)
                img = pk.pair_image(r, s) if round_side == "left" else pk.pair_image(s, r)
                buf = io.BytesIO()
                img.save(buf, "PNG")
                content = [{"type": "image_url", "image_url": {"url": image_data_url(buf.getvalue())}},
                           {"type": "text", "text": pk.choice_prompt(word)}]
                reply = retry_network(lambda: api.chat([{"role": "user", "content": content}], ledger_tag="plato_cratylus"))
                text = reply.choices[0].message.content or ""
                side = pk.parse_side(text)
                chose = None if side is None else ("round" if side == round_side else "spiky")
                done["answers"].append({"word": word, "pair": pair, "round_side": round_side, "said": text.strip()[:80],
                                        "chose": chose})
                path.write_text(json.dumps(done, indent=0))
        got = [a["chose"] for a in done["answers"] if a["word"] == word]
        print(f"{word}: round {got.count('round')}/{len(got)} (run ${spent() - start:.2f})", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("human")
    p.add_argument("--keep", type=int, default=200)
    p.add_argument("--max-lines", type=int, default=5000)
    p.set_defaults(fn=cmd_human)
    sub.add_parser("measure").set_defaults(fn=cmd_measure)
    sub.add_parser("analyze").set_defaults(fn=cmd_analyze)
    p = sub.add_parser("spark")
    p.add_argument("--pairs", type=int, default=3)
    p.set_defaults(fn=cmd_spark)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

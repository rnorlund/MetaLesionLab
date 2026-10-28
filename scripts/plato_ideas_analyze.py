"""The invisible Forms, steps 3-4: embed the doodles, make contact sheets, and run the pre-registered statistics.

  embed    DINOv2-base CLS (and patch mean) of every main-run picture, ink-cropped exactly as the concrete things
           were (scripts/plato_embed.py's PREP): $PLATO_IDEAS_DIR/embeddings/ai_doodle/<key>.npz
  sheets   numbered 4 x 4 contact sheets per idea (sheets/<key>.png), for the label check by eye
  stats    the plan's tests (docs/plato_ideas_plan.md): emblem concentration (H1, H2), ideas against things in
           spread (H3), the label check, and the exploratory E1-E5. Writes $PLATO_IDEAS_DIR/results.json.
  words    the four words beyond nouns (docs/plato_ideas_damage_plan.md, W1-W4): the same measures, set beside the
           ideas and the things. Writes $PLATO_IDEAS_DIR/words_results.json. (embed and sheets take --words.)

Concrete things: Muse Image's first-run doodles of the Atlas's 135 things (metalesionlab/plato_atlas.py; their
embeddings were made with the same PREP and model) and the draw pad's 10 (scripts/draw_export.py KEYS).
No network, no API calls.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from metalesionlab import plato  # noqa: E402
from metalesionlab import plato_atlas as A  # noqa: E402
from metalesionlab import plato_ideas as I  # noqa: E402

PREP = "flatten_paper(21, 215) + ink_crop(256, margin 0.06, threshold 200, speck 3px)"  # = scripts/plato_embed.py
PAD_KEYS = ["chair", "umbrella", "bicycle", "house", "cat", "tree", "face", "sailboat", "cup", "book"]  # draw_export.KEYS
EMB = I.IDEAS_DIR / "embeddings" / "ai_doodle"


def emb_path(key: str) -> Path:
    return EMB / f"{key}.npz"


def which(args) -> list:
    return I.WORDS if getattr(args, "words", False) else I.IDEAS


def cmd_embed(args):
    embed = None
    t0 = time.time()
    for idea in which(args):
        files = plato.load_dir(I.folder(idea))
        if not files:
            print(f"{idea.key}: no pictures")
            continue
        names = [f.name for f in files]
        out = emb_path(idea.key)
        if out.exists():
            old = np.load(out)
            if list(old["files"]) == names and str(old["prep"]) == PREP:
                continue
        embed = embed or plato.Embedder(plato.DINO_MODEL, args.device)
        vecs = embed([plato.ink_crop(Image.open(f).convert("RGB")) for f in files])
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez(out, files=np.array(names), model=plato.DINO_MODEL, prep=PREP, **vecs)
        print(f"{idea.key:10s} {len(files):3d} pictures ({time.time() - t0:.0f}s)", flush=True)


def cmd_sheets(args):
    out = I.IDEAS_DIR / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    cell, cols = 300, 4
    for idea in which(args):
        files = plato.load_dir(I.folder(idea))
        rows = -(-len(files) // cols)
        sheet = Image.new("RGB", (cols * cell, rows * cell), "white")
        g = ImageDraw.Draw(sheet)
        for i, f in enumerate(files):
            tile = Image.open(f).convert("RGB").resize((cell - 8, cell - 8), Image.LANCZOS)
            x, y = (i % cols) * cell, (i // cols) * cell
            sheet.paste(tile, (x + 4, y + 4))
            g.rectangle((x, y, x + cell - 1, y + cell - 1), outline=(200, 200, 200))
            g.text((x + 8, y + 6), f"{i + 1} {f.stem}", fill=(200, 0, 0))
        sheet.save(out / f"{idea.key}.png")
    print(f"wrote {len(which(args))} sheets to {out}")


# ---------- statistics ----------

def load_cls(path: Path) -> np.ndarray | None:
    if not path.exists():
        return None
    z = np.load(path)
    if str(z["prep"]) != PREP or str(z["model"]) != plato.DINO_MODEL:
        raise SystemExit(f"{path}: made with a different model or preparation")
    return z["cls"].astype(np.float64)


def spread_with_boot(x: np.ndarray, rng) -> dict:
    d = plato.cosine_distances(x)
    boot = plato.bootstrap_spread(d, 2000, rng)
    return {"n": len(x), "spread": plato.spread(d), "spread_ci95": plato.ci(boot), "_boot": boot}


def concrete_sets(rng) -> dict[str, dict]:
    """Muse's spread for the Atlas's 135 things (with picture-level bootstraps), keyed by Atlas key."""
    out = {}
    for c in A.CONCEPTS:
        x = load_cls(A.embedding_path(c, "ai_doodle"))
        if x is None:
            raise SystemExit(f"missing Atlas embeddings for {c.key}")
        out[c.key] = {"label": c.label, "origin": c.origin, **spread_with_boot(x, rng)}
    return out


def load_glimmer() -> dict[str, dict]:
    out = {}
    for idea in I.IDEAS:
        p = I.IDEAS_DIR / "labels" / f"{idea.key}.json"
        if p.exists():
            out[idea.key] = json.loads(p.read_text())
    return out


def summarize_labels(idea: I.Idea, labels: list[str], rng) -> dict:
    emblems = [s for s, _ in idea.emblems]
    c = I.concentration(labels, emblems)
    boot = I.bootstrap_concentration(labels, emblems, 2000, rng)
    div = plato.kind_diversity([x for x in labels if x in emblems]) if any(x in emblems for x in labels) else {}
    return {**c, "share_ci95": plato.ci(boot), "_boot": boot,
            "effective_emblems": div.get("effective_kinds"), "simpson": div.get("simpson"),
            "n_something_else": labels.count("something else"), "n_cant_tell": labels.count("can't tell")}


def cmd_stats(args):
    rng = np.random.default_rng(I.SEED)
    glim = load_glimmer()
    eye_path = I.IDEAS_DIR / "labels_by_eye.json"
    eye = json.loads(eye_path.read_text()) if eye_path.exists() else None
    calls = [json.loads(x) for x in (I.IDEAS_DIR / "calls.jsonl").read_text().splitlines() if x.strip()]
    main_calls = [c for c in calls if c.get("run") == "main"]

    ideas = []
    for idea in I.IDEAS:
        files = [f.name for f in plato.load_dir(I.folder(idea))]
        mine = [c for c in main_calls if c["key"] == idea.key]
        refusals = {"attempts": len(mine), "refused": sum(c["outcome"] == "refused" for c in mine),
                    "short": sum(c["outcome"] == "short" for c in mine),
                    "timeouts": sum(c["outcome"] == "timeout" for c in mine),
                    "network_failures": sum(c["outcome"] == "network_error" for c in mine),
                    "messages": sorted({(c.get("error") or {}).get("code") or "" for c in mine if c["outcome"] == "refused"})}
        row = {"key": idea.key, "label": idea.label, "phrase": idea.phrase, "group": idea.group,
               "prompt": I.prompt_for(idea), "predicted": idea.predicted, "n": len(files), "files": files,
               "refusals": refusals, "analysed": len(files) >= 8}
        x = load_cls(emb_path(idea.key))
        if x is not None and row["analysed"]:
            if len(x) != len(files):
                raise SystemExit(f"{idea.key}: embeddings and pictures differ; run embed")
            row.update({"spread": spread_with_boot(x, rng)})
            grays = [A.ink_gray(I.folder(idea) / f) for f in files]
            row["pixel_spread"] = A.pixel_spread(grays)
        g = glim.get(idea.key)
        if g and row["analysed"]:
            items = {it["file"]: it for it in g["items"]}
            labels = [items[f]["emblem"] for f in files]
            row["glimmer"] = summarize_labels(idea, labels, rng)
            row["glimmer"]["labels"] = labels
            row["glimmer"]["names"] = [items[f]["name"] for f in files]
            row["glimmer"]["confidence"] = [round(max(items[f]["p"]), 3) for f in files]
            row["glimmer"]["orders_agree"] = float(np.mean([items[f]["label_fwd"] == items[f]["label_rev"] for f in files]))
            row["glimmer"]["letter_mass"] = float(np.mean([items[f]["letter_mass"] for f in files]))
        if eye and idea.key in eye["labels"] and row["analysed"]:
            mine_eye = [eye["labels"][idea.key][f] for f in files]
            row["by_eye"] = summarize_labels(idea, mine_eye, rng)
            row["by_eye"]["labels"] = mine_eye
            row["text_in_picture"] = len(eye.get("text", {}).get(idea.key, []))
            if "glimmer" in row:
                gl = row["glimmer"]["labels"]
                row["agreement"] = float(np.mean([a == b for a, b in zip(gl, mine_eye)]))
        if idea.key in I.HUMAN_LIKE and "glimmer" in row:
            hl = I.HUMAN_LIKE[idea.key]
            row["human_like"] = {"glimmer": sum(x in hl for x in row["glimmer"]["labels"]) / row["n"],
                                 **({"by_eye": sum(x in hl for x in row["by_eye"]["labels"]) / row["n"]} if "by_eye" in row else {})}
        ideas.append(row)

    done = [r for r in ideas if "spread" in r]
    things = concrete_sets(rng)
    pad = {k: things[k] for k in PAD_KEYS}

    def spread_test(group: dict) -> dict:
        a = [r["spread"]["_boot"] for r in done]
        b = [v["_boot"] for v in group.values()]
        av, bv = np.array([r["spread"]["spread"] for r in done]), np.array([v["spread"] for v in group.values()])
        _, ci = I.median_diff_ci(a, b, 5000, rng)
        return {"n_ideas": len(av), "n_things": len(bv), "median_ideas": float(np.median(av)),
                "median_things": float(np.median(bv)), "median_ideas_ci95": A.median_ci(a, rng=rng),
                "median_things_ci95": A.median_ci(b, rng=rng), "difference": float(np.median(av) - np.median(bv)),
                "difference_ci95": ci, "p_perm_one_sided": I.perm_p_median(av, bv, 10000, rng),
                "ideas_above_things_median": int((av > np.median(bv)).sum()),
                "ideas_above_things_max": int((av > bv.max()).sum()),
                "passes": bool(ci[0] > 0)}

    summary = {"n_ideas": len(ideas), "n_analysed": len(done),
               "pictures": sum(r["n"] for r in ideas),
               "refused_attempts": sum(r["refusals"]["refused"] for r in ideas),
               "attempts": sum(r["refusals"]["attempts"] for r in ideas)}
    if done:
        summary["H3_vs_atlas"] = spread_test(things)
        summary["H3_vs_pad"] = spread_test(pad)
        summary["E4_pixels"] = {"median_ideas": float(np.median([r["pixel_spread"] for r in done])),
                                "median_things": float(np.median(json_atlas_pixels())),
                                "ideas_above_things_median": int(sum(r["pixel_spread"] > np.median(json_atlas_pixels())
                                                                    for r in done))}
    labelled = [r for r in done if "glimmer" in r]
    if labelled:
        shares = np.array([r["glimmer"]["share"] for r in labelled])
        h1 = int((shares >= 0.5).sum())
        h2 = [r["key"] for r in labelled if r["glimmer"]["top"] == r["predicted"]]
        summary["H1"] = {"ideas_with_concentration_at_least_half": h1, "of": len(labelled), "passes": h1 >= 7,
                         "median_concentration": float(np.median(shares)),
                         "median_concentration_ci95": A.median_ci([r["glimmer"]["_boot"] for r in labelled], rng=rng)}
        summary["H2"] = {"predicted_emblem_on_top": len(h2), "of": len(labelled), "ideas": h2, "passes": len(h2) >= 6}
        rho = plato.spearman_ci([r["glimmer"]["share"] for r in labelled], [r["spread"]["spread"] for r in labelled],
                                5000, rng)
        summary["E1_concentration_vs_spread"] = rho
    with_eye = [r for r in labelled if "by_eye" in r]
    if with_eye:
        a = [x for r in with_eye for x in r["glimmer"]["labels"]]
        b = [x for r in with_eye for x in r["by_eye"]["labels"]]
        summary["label_check"] = {
            "pictures": len(a), "agreement": float(np.mean([x == y for x, y in zip(a, b)])),
            "kappa": I.cohen_kappa(a, b),
            "same_top_emblem": int(sum(r["glimmer"]["top"] == r["by_eye"]["top"] for r in with_eye)),
            "of": len(with_eye),
            "by_eye_H1": int(sum(r["by_eye"]["share"] >= 0.5 for r in with_eye)),
            "by_eye_H2": int(sum(r["by_eye"]["top"] == r["predicted"] for r in with_eye)),
            "labels_by_eye_sha256": hashlib.sha256(eye_path.read_bytes()).hexdigest()}
        summary["text_in_pictures"] = int(sum(r.get("text_in_picture", 0) for r in with_eye))

    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items() if not k.startswith("_")}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o

    out = {"experiment": "The invisible Forms", "plan": "docs/plato_ideas_plan.md", "model": "muse-image-1.0",
           "embedding": f"{plato.DINO_MODEL} CLS, {PREP}", "labeler": "meta-models/Muse-Glimmer-30B (FP8), letter logits",
           "summary": summary, "ideas": ideas,
           "things": [{"key": k, "label": v["label"], "origin": v["origin"], "n": v["n"], "spread": v["spread"],
                       "spread_ci95": v["spread_ci95"], "pad": k in PAD_KEYS} for k, v in things.items()]}
    path = I.IDEAS_DIR / "results.json"
    path.write_text(json.dumps(plato.to_jsonable(clean(out)), indent=1))
    print(json.dumps(plato.to_jsonable(clean(summary)), indent=1))
    for r in ideas:
        g, e = r.get("glimmer", {}), r.get("by_eye", {})
        print(f"{r['key']:10s} n={r['n']:2d} spread={r.get('spread', {}).get('spread', float('nan')):.3f} "
              f"glimmer top={g.get('top')!s:16s} {g.get('share', float('nan')):.2f} "
              f"eye top={e.get('top')!s:16s} {e.get('share', float('nan')):.2f} agree={r.get('agreement', float('nan')):.2f} "
              f"refused={r['refusals']['refused']}")
    print(f"wrote {path}")


def cmd_words(args):
    """Beyond nouns (docs/plato_ideas_damage_plan.md): the four words with the ideas' measures, and W1-W4."""
    rng = np.random.default_rng(I.SEED + 1)
    ideas_res = json.loads((I.IDEAS_DIR / "results.json").read_text())
    idea_spreads = {r["key"]: r["spread"]["spread"] for r in ideas_res["ideas"]}
    idea_median = float(np.median(list(idea_spreads.values())))
    eye_path = I.IDEAS_DIR / "labels_by_eye_words.json"
    eye = json.loads(eye_path.read_text()) if eye_path.exists() else None
    calls = [json.loads(x) for x in (I.IDEAS_DIR / "calls.jsonl").read_text().splitlines() if x.strip()]
    calls = [c for c in calls if c.get("run") == "words"]
    words = []
    for w in I.WORDS:
        files = [f.name for f in plato.load_dir(I.folder(w))]
        mine = [c for c in calls if c["key"] == w.key]
        row = {"key": w.key, "label": w.label, "phrase": w.phrase, "group": w.group, "prompt": I.prompt_for(w),
               "predicted": w.predicted, "n": len(files), "files": files,
               "refusals": {"attempts": len(mine), "refused": sum(c["outcome"] == "refused" for c in mine),
                            "short": sum(c["outcome"] == "short" for c in mine)}}
        x = load_cls(emb_path(w.key))
        if x is not None:
            if len(x) != len(files):
                raise SystemExit(f"{w.key}: embeddings and pictures differ; run embed --words")
            row["spread"] = spread_with_boot(x, rng)
            row["pixel_spread"] = A.pixel_spread([A.ink_gray(I.folder(w) / f) for f in files])
        g = I.IDEAS_DIR / "labels" / f"{w.key}.json"
        if g.exists():
            items = {it["file"]: it for it in json.loads(g.read_text())["items"]}
            labels = [items[f]["emblem"] for f in files]
            row["glimmer"] = {**summarize_labels(w, labels, rng), "labels": labels,
                              "names": [items[f]["name"] for f in files],
                              "orders_agree": float(np.mean([items[f]["label_fwd"] == items[f]["label_rev"] for f in files])),
                              "letter_mass": float(np.mean([items[f]["letter_mass"] for f in files]))}
        if eye and w.key in eye["labels"]:
            by_eye = [eye["labels"][w.key][f] for f in files]
            row["by_eye"] = {**summarize_labels(w, by_eye, rng), "labels": by_eye}
            row["text_in_picture"] = len(eye.get("text", {}).get(w.key, []))
            if "glimmer" in row:
                row["agreement"] = float(np.mean([a == b for a, b in zip(row["glimmer"]["labels"], by_eye)]))
        words.append(row)

    done = {r["key"]: r for r in words if "spread" in r and "glimmer" in r}
    tests = {}
    if len(done) == len(I.WORDS):
        sp = {k: r["spread"]["spread"] for k, r in done.items()}
        top_ok = [k for k, r in done.items() if r["glimmer"]["top"] == r["predicted"]]
        tests["W1"] = {"predicted_on_top": len(top_ok), "of": 4, "words": top_ok, "passes": len(top_ok) >= 3}
        tests["W2"] = {"concentration": {k: done[k]["glimmer"]["share"] for k in ("running", "thinking")},
                       "passes": all(done[k]["glimmer"]["share"] >= 0.5 for k in ("running", "thinking"))}
        adj, verbs = ("something_fast", "something_heavy"), ("running", "thinking")
        tests["W3"] = {"spread": sp, "passes": min(sp[a] for a in adj) > max(sp[v] for v in verbs)}
        tests["W4"] = {"ideas_median": idea_median, "passes": all(sp[a] > idea_median for a in adj)}
        if eye:
            top_eye = [k for k, r in done.items() if r.get("by_eye", {}).get("top") == r["predicted"]]
            tests["W1_by_eye"] = {"predicted_on_top": len(top_eye), "words": top_eye}
            tests["W2_by_eye"] = {k: done[k]["by_eye"]["share"] for k in ("running", "thinking")}
        # exploratory: where the words sit among the ideas and the Atlas's things
        things = concrete_sets(rng)
        tv = np.array([v["spread"] for v in things.values()])
        tests["context"] = {"things_median": float(np.median(tv)), "ideas_median": idea_median,
                            "words_median": float(np.median(list(sp.values()))),
                            "above_every_thing": [k for k, v in sp.items() if v > tv.max()],
                            "things_percentile": {k: float((tv < v).mean()) for k, v in sp.items()},
                            "ideas_below": {k: int(sum(s < v for s in idea_spreads.values())) for k, v in sp.items()}}
        if eye:
            a = [x for r in done.values() for x in r["glimmer"]["labels"]]
            b = [x for r in done.values() for x in r["by_eye"]["labels"]]
            tests["label_check"] = {"pictures": len(a), "agreement": float(np.mean([x == y for x, y in zip(a, b)])),
                                    "kappa": I.cohen_kappa(a, b),
                                    "labels_by_eye_sha256": hashlib.sha256(eye_path.read_bytes()).hexdigest()}

    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items() if not k.startswith("_")}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o

    out = {"experiment": "Beyond nouns", "plan": "docs/plato_ideas_damage_plan.md", "model": "muse-image-1.0",
           "embedding": f"{plato.DINO_MODEL} CLS, {PREP}", "tests": tests, "words": words}
    path = I.IDEAS_DIR / "words_results.json"
    path.write_text(json.dumps(plato.to_jsonable(clean(out)), indent=1))
    print(json.dumps(plato.to_jsonable(clean(tests)), indent=1))
    for r in words:
        g, e = r.get("glimmer", {}), r.get("by_eye", {})
        print(f"{r['key']:16s} n={r['n']:2d} spread={r.get('spread', {}).get('spread', float('nan')):.3f} "
              f"glimmer top={g.get('top')!s:16s} {g.get('share', float('nan')):.2f} eye top={e.get('top')!s:16s} "
              f"{e.get('share', float('nan')):.2f} agree={r.get('agreement', float('nan')):.2f}")
    print(f"wrote {path}")


def json_atlas_pixels() -> list[float]:
    r = json.loads((A.ATLAS_DIR / "results.json").read_text())
    return [c["pixel"]["muse_spread"] for c in r["concepts"]]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("embed")
    p.add_argument("--device")
    p.add_argument("--words", action="store_true", help="the four words beyond nouns instead of the ideas")
    p.set_defaults(fn=cmd_embed)
    p = sub.add_parser("sheets")
    p.add_argument("--words", action="store_true")
    p.set_defaults(fn=cmd_sheets)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    sub.add_parser("words").set_defaults(fn=cmd_words)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

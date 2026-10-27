"""Plato's Chair, damage: measures and statistics (on the Mac; the pictures come from plato_damage_sdxl.py).

  sheet RUN [--conditions ..] [--keys ..] [--n 4] --out PNG
                       contact sheet: one row per condition, the prompts' seeds side by side
  embed RUN            DINOv2 CLS of every ink-cropped picture, cached per condition in RUN/embeddings/
  measures RUN         per-picture drift measures (plato_damage.drift_measures) -> RUN/measures.json
  stats RUN [--labels DIR] [--clocks FILE] -> $DAMAGE_DIR/results.json and public_data/plato_damage.json
  clocks RUN           Muse Spark scores every clock picture with the rubric (costs money; capped)

RUN is a folder of <condition>/<prompt key>/s<i>.png under $DAMAGE_DIR (default PlatosChair/damage).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from metalesionlab.plato import DINO_MODEL, ink_crop, load_dir  # noqa: E402
from metalesionlab.plato_damage import (BY_KEY, CONCEPT_KINDS, DRAWING_FAMILIES, KIND_PROMPTS,  # noqa: E402
                                        LANGUAGE_FAMILIES, boot_mean_ci, drift_measures, parse_condition)

DAMAGE_DIR = Path(os.environ.get("DAMAGE_DIR", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/damage"))
PREP = "flatten_paper(21, 215) + ink_crop(256, margin 0.06, threshold 200, speck 3px)"  # as plato_embed.py


def conditions_in(run: Path) -> list[str]:
    conds = [p.name for p in run.iterdir() if p.is_dir() and (p / "meta.json").exists()]
    return sorted(conds, key=lambda c: (c != "intact", parse_condition(c)[0], parse_condition(c)[1]))


def font(size: int):
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def cmd_sheet(args):
    run = DAMAGE_DIR / args.run
    conds = args.conditions or conditions_in(run)
    keys = args.keys or sorted({p.parent.name for p in run.glob("intact/*/s0.png")})
    cell, label_w = args.cell, 170
    cols = len(keys) * args.n
    sheet = Image.new("RGB", (label_w + cols * cell + (len(keys) - 1) * 10, 30 + len(conds) * cell), "white")
    d = ImageDraw.Draw(sheet)
    for j, key in enumerate(keys):
        d.text((label_w + j * (args.n * cell + 10) + 4, 6), key.split("__")[-1].replace("_", " "), fill="black",
               font=font(16))
    for r, cond in enumerate(conds):
        d.text((6, 30 + r * cell + cell // 2 - 8), cond, fill="black", font=font(15))
        for j, key in enumerate(keys):
            for i in range(args.n):
                f = run / cond / key / f"s{i}.png"
                if f.exists():
                    im = Image.open(f).convert("RGB").resize((cell - 4, cell - 4))
                    sheet.paste(im, (label_w + j * (args.n * cell + 10) + i * cell, 30 + r * cell))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"{args.out}: {len(conds)} conditions x {len(keys)} prompts x {args.n} seeds")


def cmd_grid(args):
    """Rows = damage level (intact first), columns = lesion family (site); each cell shows the prompts
    (stacked) x seeds (side by side). Doses are each family's own, in increasing order."""
    run = DAMAGE_DIR / args.run
    conds = conditions_in(run)
    doses = {f: sorted(parse_condition(c)[1] for c in conds if parse_condition(c)[0] == f) for f in args.families}
    n_rows = 1 + max(len(v) for v in doses.values())
    cell, gap, label_w, head = args.cell, 18, 120, 56
    cw, ch = args.n * cell, len(args.keys) * cell
    sheet = Image.new("RGB", (label_w + len(args.families) * (cw + gap), head + n_rows * (ch + gap)), "white")
    d = ImageDraw.Draw(sheet)
    titles = {"text-zero": "language part damaged (text encoders)", "unet-zero": "drawing part damaged (UNet)",
              "text-noise": "language part, noise", "unet-noise": "drawing part, noise"}
    for j, fam in enumerate(args.families):
        d.text((label_w + j * (cw + gap), 8), titles.get(fam, fam), fill="black", font=font(20))
        d.text((label_w + j * (cw + gap), 32), fam + ": " + ", ".join(f"{x:g}" for x in doses[fam]), fill="gray",
               font=font(14))
    for r in range(n_rows):
        y = head + r * (ch + gap)
        d.text((6, y + ch // 2 - 10), "intact" if r == 0 else f"level {r}", fill="black", font=font(18))
        for j, fam in enumerate(args.families):
            cond = "intact" if r == 0 else (f"{fam}@{doses[fam][r - 1]:g}" if r - 1 < len(doses[fam]) else None)
            if cond is None:
                continue
            for k, key in enumerate(args.keys):
                for i in range(args.n):
                    f = run / cond / key / f"s{i}.png"
                    if f.exists():
                        im = Image.open(f).convert("RGB").resize((cell - 3, cell - 3))
                        sheet.paste(im, (label_w + j * (cw + gap) + i * cell, y + k * cell))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"{args.out}: {n_rows} rows x {len(args.families)} families")


def cmd_crop(args):
    """Ink-cropped 448 px copies of every picture for the Glimmer labeler (RUN_crop448/, same layout)."""
    run = DAMAGE_DIR / args.run
    out_root = DAMAGE_DIR / f"{args.run}_crop448"
    made = 0
    for f in sorted(run.glob("*/*/s*.png")):
        out = out_root / f.parent.parent.name / f.parent.name / f.name
        if not out.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            ink_crop(Image.open(f).convert("RGB"), side=448).save(out)
            made += 1
    print(f"cropped {made} new pictures -> {out_root}")


def cmd_embed(args):
    from metalesionlab.plato import Embedder

    run = DAMAGE_DIR / args.run
    embed = None
    t0, count = time.time(), 0
    for cond in conditions_in(run):
        out = run / "embeddings" / f"{cond}.npz"
        files = sorted(run.glob(f"{cond}/*/s*.png"), key=lambda p: (p.parent.name, int(p.stem[1:])))
        names = [f"{f.parent.name}/{f.name}" for f in files]
        if not files:
            continue
        if out.exists():
            old = np.load(out)
            if list(old["files"]) == names and str(old["prep"]) == PREP:
                continue
        embed = embed or Embedder(DINO_MODEL, args.device)
        vecs = embed([ink_crop(Image.open(f).convert("RGB")) for f in files])
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez(out, files=np.array(names), model=DINO_MODEL, prep=PREP, cls=vecs["cls"])
        count += len(files)
        print(f"{cond:24s} {len(files):4d} pictures ({time.time() - t0:.0f}s)", flush=True)
    print(f"embedded {count} pictures in {time.time() - t0:.0f}s")


def load_embeddings(run: Path) -> dict[str, dict[str, np.ndarray]]:
    """condition -> prompt key -> (n, d) CLS array in seed order."""
    out = {}
    for f in sorted((run / "embeddings").glob("*.npz")):
        z = np.load(f)
        by = {}
        for name, v in zip(z["files"], z["cls"]):
            key, fname = str(name).split("/")
            by.setdefault(key, []).append((int(fname[1:-4]), v))
        out[f.stem] = {k: np.array([v for _, v in sorted(rows)]) for k, rows in by.items()}
    return out


def picture_measures(emb: dict) -> list[dict]:
    """One row per damaged (or intact) picture of a named kind or plain prompt."""
    intact = emb["intact"]
    rows = []
    for cond, by in emb.items():
        family, dose = parse_condition(cond)
        for concept, (plain_phrase, kinds) in CONCEPT_KINDS.items():
            plain_key = f"{concept}__plain"
            if plain_key not in intact:
                continue
            kind_keys = [p.key for p in KIND_PROMPTS if p.concept == concept and not p.is_plain]
            for p in [x for x in KIND_PROMPTS if x.concept == concept]:
                if p.key not in by or p.key not in intact:
                    continue
                e = by[p.key]
                n = min(len(e), len(intact[p.key]))
                e, e0 = e[:n], intact[p.key][:n]
                if p.is_plain:
                    # the plain prompt: distance to its own prototype (leave-one-out is the kind centroid)
                    m = drift_measures(e, e0, intact[plain_key], intact[plain_key])
                else:
                    others = [intact[k] for k in kind_keys if k != p.key and k in intact]
                    m = drift_measures(e, e0, intact[p.key][:n], intact[plain_key], others=others)
                for i in range(n):
                    rows.append({"condition": cond, "family": family, "dose": dose, "key": p.key, "concept": concept,
                                 "kind": p.kind, "plain": p.is_plain, "seed_index": i,
                                 **{k: float(v[i]) for k, v in m.items()}})
    return rows


def cmd_measures(args):
    run = DAMAGE_DIR / args.run
    from metalesionlab.plato_damage import style_metrics

    rows = picture_measures(load_embeddings(run))
    for r in rows:  # pixel style of the raw picture
        r.update(style_metrics(np.asarray(Image.open(run / r["condition"] / r["key"] / f"s{r['seed_index']}.png")
                                          .convert("RGB"))))
    # paired change from intact for the same picture
    base = {(r["key"], r["seed_index"]): r for r in rows if r["condition"] == "intact"}
    for r in rows:
        b = base.get((r["key"], r["seed_index"]))
        if b:
            for k in ("drift", "tau", "d_proto", "d_kind", "drift_other", "colorfulness", "midtone", "ink", "clean"):
                if k in r and k in b:
                    r[f"delta_{k}"] = r[k] - b[k]
    (run / "measures.json").write_text(json.dumps(rows))
    print(f"{len(rows)} rows -> {run / 'measures.json'}")
    summarize(rows)


def summarize(rows: list[dict], concept: str | None = "chair") -> None:
    """Quick table: per condition, mean d_intact and delta_drift for named kinds."""
    from collections import defaultdict

    g = defaultdict(list)
    for r in rows:
        if not r["plain"] and (concept is None or r["concept"] == concept):
            g[r["condition"]].append(r)
    print(f"{'condition':24s} {'n':>4s} {'d_intact':>8s} {'d_proto':>8s} {'d_kind':>8s} {'Δdrift':>8s} {'Δtau':>7s} "
          f"{'Δd_proto':>8s} {'color':>6s} {'midtone':>7s}")
    for cond in sorted(g, key=lambda c: (c != "intact", parse_condition(c))):
        x = g[cond]
        f = lambda k: np.nanmean([r.get(k, np.nan) for r in x])  # noqa: E731
        print(f"{cond:24s} {len(x):4d} {f('d_intact'):8.3f} {f('d_proto'):8.3f} {f('d_kind'):8.3f} "
              f"{f('delta_drift'):8.3f} {f('delta_tau'):7.3f} {f('delta_d_proto'):+8.3f} {f('colorfulness'):6.1f} "
              f"{f('midtone'):7.3f}")


FAMILY_PAIRS = [("text-zero", "unet-zero"), ("text-noise", "unet-noise"), ("text-spec", "text-spec-random")]  # predicted signs: first two pairs only
TARGETED_PAIR = ("text-spec", "text-spec-random")
# Matched-severity contrasts, language minus drawing; the sign each hypothesis predicts.
CONTRASTS = {
    "delta_correct": ("H1a concept retention: still the asked kind", -1),
    "delta_p_is_a": ("concept retention: P(yes) 'is this a drawing of a chair?'", -1),
    "delta_p_clean": ("H1b drawing retention: P(yes) 'clean line drawing?'", +1),
    "delta_midtone": ("pixels: gray share (shading, charcoal texture)", 0),
    "delta_colorfulness": ("pixels: colorfulness", 0),
    "delta_d_proto": ("H2 distance to the plain prototype", -1),
    "delta_drift": ("H2 drift index d_kind - d_proto", +1),
    "delta_tau": ("position on the kind-to-prototype line", +1),
    "delta_drift_other": ("drift toward the other kinds", 0),
    "is_plain": ("H3 labeled 'a plain, ordinary ...'", +1),
    "is_cant": ("labeled 'can't tell, or not a ...'", -1),
    # exploratory (not in the plan): what Glimmer names the picture, one word
    "name_kind": ("named as the asked kind", 0),
    "name_other_object": ("named as some other object (car, bicycle, man ...)", 0),
    "name_no_object": ("named as no object (abstract, pattern, illusion ...)", 0),
}
TABLE_MEASURES = ["d_intact", "delta_correct", "is_plain", "is_cant", "is_other", "delta_p_is_a", "delta_p_clean",
                  "p_clean", "delta_d_proto", "delta_drift", "delta_tau", "colorfulness", "midtone", "ink",
                  "name_kind", "name_other_object", "name_no_object"]


def merge_labels(rows: list[dict], labels_dir: Path) -> None:
    """Add Glimmer's readings (labels_dir/<condition>.json) to the picture rows, and the paired changes."""
    from metalesionlab.plato_damage import kind_outcome, name_category

    found = {}
    for f in labels_dir.glob("*.json"):
        d = json.loads(f.read_text())
        for it in d["items"]:
            found[(d["condition"], it["key"], int(it["file"][1:-4]))] = it
    for r in rows:
        it = found.get((r["condition"], r["key"], r["seed_index"]))
        if not it:
            continue
        n_kinds = len(CONCEPT_KINDS[r["concept"]][1])
        r["outcome"] = kind_outcome(it["label"], it["true_kind"], n_kinds)
        r["p_is_a"], r["p_clean"], r["said"] = it.get("p_is_a"), it.get("p_clean"), it.get("said")
        r["name_category"] = name_category(it.get("said"), r["concept"], r["kind"])
        for cat in ("kind", "other_object", "no_object"):
            r[f"name_{cat}"] = float(r["name_category"] == cat)
    base = {(r["key"], r["seed_index"]): dict(r) for r in rows if r["condition"] == "intact"}  # copies: levels
    for r in rows:
        b = base.get((r["key"], r["seed_index"]))
        if not b or "outcome" not in r or "outcome" not in b:
            continue
        for k in ("p_is_a", "p_clean"):
            if r.get(k) is not None and b.get(k) is not None:
                r[f"delta_{k}"] = r[k] - b[k]
        for cat in ("kind", "other_object", "no_object"):  # names as changes from the intact twin
            r[f"name_{cat}"] = r[f"name_{cat}"] - b[f"name_{cat}"] if r["condition"] != "intact" else 0.0
        target = "plain" if r["plain"] else "correct"
        if b["outcome"] == target:  # outcome measures only for pictures read right when intact
            r["delta_correct"] = float(r["outcome"] == target) - 1.0
            r["is_plain"] = float(r["outcome"] == "plain") if not r["plain"] else np.nan
            r["is_cant"] = float(r["outcome"] == "cant_tell")
            r["is_other"] = float(r["outcome"] in ("other_kind", "specific"))


def unit_matrix(rows: list[dict], family: str, measure: str, units: list[tuple]) -> tuple[np.ndarray, list[float]]:
    """(units, doses) array of one measure for one family; units are (key, seed_index)."""
    doses = sorted({r["dose"] for r in rows if r["family"] == family})
    idx = {u: i for i, u in enumerate(units)}
    m = np.full((len(units), len(doses)), np.nan)
    for r in rows:
        if r["family"] == family and (r["key"], r["seed_index"]) in idx:
            v = r.get(measure)
            m[idx[(r["key"], r["seed_index"])], doses.index(r["dose"])] = np.nan if v is None else v
    return m, doses


def named_units(rows: list[dict], concept: str) -> list[tuple]:
    return sorted({(r["key"], r["seed_index"]) for r in rows if r["concept"] == concept and not r["plain"]
                   and r["family"] != "intact"})


def family_table(rows: list[dict], concept: str, rng, plain: bool = False) -> list[dict]:
    """Per family and dose (named kinds, or the plain prompt): means with picture-level bootstrap CIs."""
    from metalesionlab.plato_damage import boot_mean_ci

    out = []
    sel = [r for r in rows if r["concept"] == concept and r["plain"] == plain]
    fams = sorted({r["family"] for r in sel}, key=lambda f: (f != "intact", f))
    for fam in fams:
        for dose in sorted({r["dose"] for r in sel if r["family"] == fam}):
            x = [r for r in sel if r["family"] == fam and r["dose"] == dose]
            row = {"family": fam, "dose": dose, "n": len(x)}
            for k in TABLE_MEASURES:
                v = np.array([np.nan if r.get(k) is None else r.get(k) for r in x], float)
                if np.isfinite(v).any():
                    row[k] = boot_mean_ci(v, reps=1000, rng=rng)
            names = [r.get("name_category") for r in x if r.get("name_category")]
            if names:
                row["names"] = {c: names.count(c) / len(names)
                                for c in ("kind", "basic", "other_object", "no_object", "empty")}
            out.append(row)
    return out


def matched_contrasts(rows: list[dict], concept: str, rng, reps: int = 4000) -> dict:
    """Language minus drawing family at matched severity, for every measure in CONTRASTS."""
    from metalesionlab.plato_damage import at_severity, boot_matched_contrast

    units = named_units(rows, concept)
    groups = np.array([u[0] for u in units])
    out = {}
    for a, b in FAMILY_PAIRS:
        if not any(r["family"] == a for r in rows) or not any(r["family"] == b for r in rows):
            continue
        da, _ = unit_matrix(rows, a, "d_intact", units)
        db, _ = unit_matrix(rows, b, "d_intact", units)
        res = {}
        for measure, (label, sign) in CONTRASTS.items():
            va, _ = unit_matrix(rows, a, measure, units)
            vb, _ = unit_matrix(rows, b, measure, units)
            if not (np.isfinite(va).any() and np.isfinite(vb).any()):
                continue
            ok = np.isfinite(va).any(1) & np.isfinite(vb).any(1)  # units measured under both
            r1 = boot_matched_contrast(da[ok], va[ok], db[ok], vb[ok], reps=reps, rng=rng)
            r2 = boot_matched_contrast(da[ok], va[ok], db[ok], vb[ok], reps=reps // 2, rng=rng, groups=groups[ok])
            # each family alone at the matched severities (change from intact)
            fam_a = float(np.mean(at_severity(np.nanmean(da[ok], 0), np.nanmean(va[ok], 0), r1["targets"])))
            fam_b = float(np.mean(at_severity(np.nanmean(db[ok], 0), np.nanmean(vb[ok], 0), r1["targets"])))
            res[measure] = {"label": label, "predicted_sign": sign, "language": fam_a, "drawing": fam_b,
                            "difference": r1["estimate"], "ci95": r1["ci95"], "ci95_by_kind": r2["ci95"],
                            "targets": r1["targets"], "n_units": r1["n_units"]}
        out[f"{a} vs {b}"] = res
    return out


def pooled_family(rows: list[dict], concept: str, family: str, measure: str, rng) -> dict:
    """A family's mean change over all its doses (per picture, then over pictures)."""
    from metalesionlab.plato_damage import boot_mean_ci

    m, _ = unit_matrix(rows, family, measure, named_units(rows, concept))
    with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
        __import__("warnings").simplefilter("ignore")
        per = np.nanmean(m, axis=1)
    return boot_mean_ci(per, rng=rng)


def targeted_vs_random(rows: list[dict], concept: str, rng) -> list[dict]:
    """H5: the targeted 'specific-kind' lesion minus its matched random control, paired by picture, per dose."""
    from metalesionlab.plato_damage import boot_mean_ci

    a, b = TARGETED_PAIR
    units = named_units(rows, concept)
    out = []
    for measure in ("d_intact", "delta_correct", "delta_d_proto", "delta_p_clean"):
        ma, doses = unit_matrix(rows, a, measure, units)
        mb, doses_b = unit_matrix(rows, b, measure, units)
        if not doses or doses != doses_b:
            continue
        for j, dose in enumerate(doses):
            out.append({"measure": measure, "dose": dose, "targeted": float(np.nanmean(ma[:, j])),
                        "random": float(np.nanmean(mb[:, j])), "difference": boot_mean_ci(ma[:, j] - mb[:, j], rng=rng)})
    return out


def top_names(rows: list[dict], concept: str, families: list[str], k: int = 12) -> dict:
    """The most common one-word names Glimmer gives damaged named-kind pictures, per family (top two doses)."""
    from collections import Counter

    from metalesionlab.plato_damage import clean_name

    out = {}
    for fam in families:
        doses = sorted({r["dose"] for r in rows if r["family"] == fam})[-2:]
        names = [" ".join(clean_name(r.get("said")).split()[:3]) for r in rows if r["family"] == fam
                 and r["dose"] in doses and r["concept"] == concept and not r["plain"] and r.get("said")]
        out[fam] = Counter(n for n in names if n).most_common(k)
    return out


def cmd_stats(args):
    from metalesionlab.plato import to_jsonable

    rng = np.random.default_rng(20261027)
    run = DAMAGE_DIR / args.run
    rows = json.loads((run / "measures.json").read_text())
    if args.labels:
        merge_labels(rows, DAMAGE_DIR / args.labels)
        (run / "measures_labeled.json").write_text(json.dumps(rows))
    families = sorted({r["family"] for r in rows} - {"intact"})
    res = {"run": args.run, "n_pictures": len(rows), "concepts": {}}
    for concept in CONCEPT_KINDS:
        if not any(r["concept"] == concept for r in rows):
            continue
        c = {"table_named": family_table(rows, concept, rng), "table_plain": family_table(rows, concept, rng, plain=True),
             "matched": matched_contrasts(rows, concept, rng, reps=args.reps),
             "pooled": {f: {m: pooled_family(rows, concept, f, m, rng)
                            for m in ("delta_d_proto", "delta_drift", "delta_correct", "d_intact")} for f in families},
             "names": top_names(rows, concept, families)}
        if any(r["family"] == TARGETED_PAIR[0] for r in rows):
            c["targeted_vs_random"] = targeted_vs_random(rows, concept, rng)
        res["concepts"][concept] = c
        print(f"\n== {concept}")
        for pair, d in c["matched"].items():
            print(f"  {pair}")
            for m, v in d.items():
                print(f"    {m:20s} lang {v['language']:+.3f} draw {v['drawing']:+.3f}  diff {v['difference']:+.3f} "
                      f"[{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}] by kind [{v['ci95_by_kind'][0]:+.3f}, "
                      f"{v['ci95_by_kind'][1]:+.3f}] (pred {v['predicted_sign']:+d})")
    out = DAMAGE_DIR / f"results_{args.run}.json"
    out.write_text(json.dumps(to_jsonable(res), indent=1))
    print(f"-> {out}")


def glimmer_arm_stats(arm_dir: Path, rng) -> dict:
    """H7: a damaged Glimmer reads Muse Image's named-kind doodles. Among pictures it labels right when
    intact: the share now called "a plain, ordinary ..." (the semantic-dementia signature), "can't tell",
    another kind, or still right; each lesion against its random control (same count per layer),
    paired by picture, bootstrap over pictures and over concepts."""
    from metalesionlab.plato_damage import RELIABLE_KINDS, boot_mean_ci, code_name, kind_outcome

    conds = {}
    for f in sorted(arm_dir.glob("*.json")):
        d = json.loads(f.read_text())
        conds[d["condition"]] = d
    if "intact" not in conds:
        return {}
    kinds_cache = {}

    def kinds_of(key):
        if key not in kinds_cache:
            path = DAMAGE_DIR.parent / "core" / "kinds_input" / "kinds" / f"{key}.json"
            kinds_cache[key] = json.loads(path.read_text()) if path.exists() else []
        return kinds_cache[key]

    def items(cond):
        out = {}
        for it in conds[cond]["items"]:
            if it["key"] not in RELIABLE_KINDS:
                continue
            o = kind_outcome(it["label"], it["true_kind"], it["n_kinds"])
            kinds = kinds_of(it["key"])
            kind = kinds[it["true_kind"]] if it["true_kind"] < len(kinds) else ""
            basic = it["key"].replace("_", " ") if it["key"] != "yoga" else "person"
            # strict: an answer that changes with the option order is a letter habit, not a reading
            strict = o if it["label_fwd"] == it["label_rev"] else "order_bias"
            out[(it["key"], it["file"])] = {"outcome": o, "strict": strict,
                                            "name": code_name(it.get("said"), basic, kind),
                                            "said": it.get("said"), "key": it["key"]}
        return out

    base = items("intact")
    keep = [u for u, v in base.items() if v["outcome"] == "correct"]
    groups = np.array([u[0] for u in keep])
    res = {"n_pictures": len(base), "n_intact_correct": len(keep),
           "intact_accuracy": float(np.mean([v["outcome"] == "correct" for v in base.values()])),
           "intact_names": {c: float(np.mean([base[u]["name"] == c for u in keep]))
                            for c in ("specific", "basic", "other", "empty")},
           "conditions": {}, "vs_random": {}}
    ind = {}
    for cond in conds:
        cur = items(cond)
        m = {k: np.array([float(cur[u]["outcome"] == k) if u in cur else np.nan for u in keep])
             for k in ("correct", "plain", "cant_tell", "other_kind")}
        m.update({f"name_{k}": np.array([float(cur[u]["name"] == k) if u in cur else np.nan for u in keep])
                  for k in ("specific", "basic", "other", "empty")})
        m.update({f"strict_{k}": np.array([float(cur[u]["strict"] == k) if u in cur else np.nan for u in keep])
                  for k in ("correct", "plain", "other_kind", "cant_tell", "order_bias")})
        ind[cond] = m
        row = {k: boot_mean_ci(v, reps=2000, rng=rng) for k, v in m.items()}
        errors = m["plain"] + m["cant_tell"] + m["other_kind"]
        row["plain_share_of_errors"] = float(np.nansum(m["plain"]) / np.nansum(errors)) if np.nansum(errors) else None
        row["units"] = conds[cond].get("units")
        res["conditions"][cond] = row
    for cond in conds:
        if cond.endswith("-random") or "-random@" in cond or cond == "intact":
            continue
        fam, _, dose = cond.partition("@")
        ctrl = f"{fam}-random@{dose}"
        if ctrl not in conds:
            continue
        cmp = {}
        for k in ("plain", "cant_tell", "correct", "other_kind", "name_basic", "name_specific"):
            diff = ind[cond][k] - ind[ctrl][k]
            cmp[k] = {"lesion": float(np.nanmean(ind[cond][k])), "random": float(np.nanmean(ind[ctrl][k])),
                      "difference": boot_mean_ci(diff, rng=rng),
                      "difference_by_concept": boot_mean_ci(diff, rng=rng, groups=groups, reps=2000)}
        # plain vs can't tell within the lesion (the signature: specific -> general, not -> unrecognisable)
        cmp["plain_minus_cant_tell"] = boot_mean_ci(ind[cond]["plain"] - ind[cond]["cant_tell"], rng=rng)
        res["vs_random"][cond] = cmp
    # chair alone, for the page
    chair = [i for i, u in enumerate(keep) if u[0] == "chair"]
    res["chair"] = {cond: {k: float(np.nanmean(v[chair])) for k, v in m.items()} for cond, m in ind.items()} \
        if chair else {}
    res["chair_n"] = len(chair)
    # Letter check: "plain" is always the second-to-last option, but its letter depends on how many kinds
    # a thing has (12 kinds: M; 16 kinds: Q). A damaged model that just favours one letter would raise
    # "plain" for one group only.
    n_kinds = np.array([next(it["n_kinds"] for it in conds["intact"]["items"] if (it["key"], it["file"]) == u)
                        for u in keep])
    res["plain_by_letter"] = {cond: {f"{int(k)} kinds": float(np.nanmean(m["plain"][n_kinds == k]))
                                     for k in np.unique(n_kinds)} for cond, m in ind.items()}
    res["status"] = {"conditions_done": sorted(conds), "n_done": len(conds)}
    res["matched_loss"] = arm_matched_loss(ind, rng)
    return res


def arm_matched_loss(ind: dict, rng, reps: int = 2000) -> dict:
    """Exploratory (not in the plan): a targeted lesion and its random control compared at the SAME loss
    of correct kinds rather than the same unit count. For each, the share called "plain" (and "can't
    tell", "another kind") is read off its loss curve (intact = 0) at losses both reach; paired bootstrap
    over pictures."""
    from metalesionlab.plato_damage import matched_contrast, matched_targets

    out = {}
    n = len(next(iter(ind.values()))["correct"])
    for fam in ("language-mlp-mean", "naming-mlp-mean", "visual-mlp-mean"):
        doses = sorted(float(c.split("@")[1]) for c in ind if c.startswith(fam + "@"))
        if not doses or not all(f"{fam}-random@{d:g}" in ind for d in doses):
            continue

        def curves(idx, family):
            loss = [1 - np.nanmean(ind[f"{family}@{d:g}"]["correct"][idx]) for d in doses]
            vals = {k: [np.nanmean(ind[f"{family}@{d:g}"][k][idx]) for d in doses]
                    for k in ("plain", "cant_tell", "other_kind", "strict_plain", "strict_other_kind", "strict_order_bias")}
            return loss, vals

        all_i = np.arange(n)
        la, va = curves(all_i, fam)
        lb, vb = curves(all_i, fam + "-random")
        targets = matched_targets(la, lb)
        row = {"targets_loss": targets}
        for k in ("plain", "cant_tell", "other_kind", "strict_plain", "strict_other_kind", "strict_order_bias"):
            est = matched_contrast(la, va[k], lb, vb[k], targets)
            boots = []
            for _ in range(reps):
                i = rng.integers(0, n, n)
                a_l, a_v = curves(i, fam)
                b_l, b_v = curves(i, fam + "-random")
                boots.append(matched_contrast(a_l, a_v[k], b_l, b_v[k], targets))
            row[k] = {"difference": est, "ci95": [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))]}
        out[fam] = row
    return out


def cmd_glimmer(args):
    from metalesionlab.plato import to_jsonable

    rng = np.random.default_rng(20261028)
    res = glimmer_arm_stats(DAMAGE_DIR / args.arm, rng)
    out = DAMAGE_DIR / "results_glimmer_arm.json"
    out.write_text(json.dumps(to_jsonable(res), indent=1))
    print(f"intact accuracy {res.get('intact_accuracy', float('nan')):.3f}; {res.get('n_intact_correct')} intact-correct")
    for cond, row in res.get("conditions", {}).items():
        print(f"  {cond:30s} correct {row['correct']['mean']:.2f} plain {row['plain']['mean']:.2f} "
              f"cant {row['cant_tell']['mean']:.2f} other {row['other_kind']['mean']:.2f} "
              f"name basic {row['name_basic']['mean']:.2f} specific {row['name_specific']['mean']:.2f}")
    for cond, cmp in res.get("vs_random", {}).items():
        p = cmp["plain"]
        print(f"  {cond:30s} plain {p['lesion']:.2f} vs random {p['random']:.2f}: diff {p['difference']['mean']:+.3f} "
              f"[{p['difference']['ci95'][0]:+.3f}, {p['difference']['ci95'][1]:+.3f}] by concept "
              f"[{p['difference_by_concept']['ci95'][0]:+.3f}, {p['difference_by_concept']['ci95'][1]:+.3f}]")
    print(f"-> {out}")


CLOCK_FEATURES = [("clock", "a clock"), ("contour", "outline"), ("numbers_ok", "12 numbers in order"),
                  ("two_hands", "two hands"), ("time_ok", "the asked time"), ("shows_1010", "hands at 10:10")]


def clock_stats(run: Path, rng) -> dict:
    """H6: clock features per condition from Spark's rubric answers; the intact 10:10 bias; which feature
    fails first under each family."""
    from metalesionlab.plato_damage import BY_KEY as PROMPTS, boot_mean_ci, score_clock

    scores = json.loads((run / "clock_scores.json").read_text())
    rows = []
    for name, v in scores.items():
        cond, key, f = name.split("/")
        t = PROMPTS[key].kind
        sc = score_clock(v.get("rubric"), t)
        fam, dose = parse_condition(cond)
        rows.append({"condition": cond, "family": fam, "dose": dose, "time": t, "seed": int(f[1:-4]),
                     "parsed": v.get("rubric") is not None, "time_read": (v.get("rubric") or {}).get("time_read"), **sc})
    out = {"n_scored": len(rows), "n_unparsed": sum(not r["parsed"] for r in rows),
           "features": [k for k, _ in CLOCK_FEATURES], "feature_labels": dict(CLOCK_FEATURES), "conditions": {}}
    conds = sorted({r["condition"] for r in rows}, key=lambda c: (c != "intact", parse_condition(c)))
    for cond in conds:
        x = [r for r in rows if r["condition"] == cond and r["parsed"]]
        row = {"n": len(x)}
        for k, _ in CLOCK_FEATURES:
            row[k] = boot_mean_ci(np.array([float(bool(r[k])) for r in x]), reps=2000, rng=rng)
        row["total"] = boot_mean_ci(np.array([r["total"] for r in x], float), reps=2000, rng=rng)
        # among pictures that are still clocks: are the numbers still there? (layout given the object)
        clocks = [r for r in x if r["clock"]]
        row["numbers_given_clock"] = boot_mean_ci(np.array([float(bool(r["numbers_ok"])) for r in clocks]),
                                                  reps=2000, rng=rng)
        row["two_hands_given_clock"] = boot_mean_ci(np.array([float(bool(r["two_hands"])) for r in clocks]),
                                                    reps=2000, rng=rng)
        out["conditions"][cond] = row
    intact = [r for r in rows if r["condition"] == "intact" and r["parsed"]]
    not1010 = [r for r in intact if r["time"] != "10:10"]
    out["intact_1010_bias"] = {
        "share_showing_1010_when_asked_other": boot_mean_ci(np.array([float(r["shows_1010"]) for r in not1010]), rng=rng),
        "share_right_time_when_asked_other": boot_mean_ci(np.array([float(r["time_ok"]) for r in not1010]), rng=rng),
        "share_right_time_when_asked_1010": boot_mean_ci(np.array([float(r["time_ok"]) for r in intact
                                                                    if r["time"] == "10:10"]), rng=rng),
        "times_read": {t: [r["time_read"] for r in intact if r["time"] == t] for t in sorted({r["time"] for r in intact})},
        "n_other": len(not1010)}
    base = out["conditions"].get("intact", {})
    first = {}
    for fam in sorted({r["family"] for r in rows} - {"intact"}):
        doses = sorted({r["dose"] for r in rows if r["family"] == fam})
        surv = []
        for d in doses:
            row = out["conditions"][f"{fam}@{d:g}"]
            surv.append({k: (row[k]["mean"] / base[k]["mean"] if base.get(k) and base[k]["mean"] > 0 else None)
                         for k, _ in CLOCK_FEATURES if k != "shows_1010"})
        fails = None
        for d, sv in zip(doses, surv):
            lost = [k for k, v in sv.items() if v is not None and v < 0.5]
            if lost:
                fails = {"dose": d, "features": lost}
                break
        first[fam] = {"doses": doses, "survival_vs_intact": surv, "first_below_half": fails}
    out["first_to_fail"] = first
    return out


def cmd_clockstats(args):
    from metalesionlab.plato import to_jsonable

    rng = np.random.default_rng(20261029)
    res = clock_stats(DAMAGE_DIR / args.run, rng)
    (DAMAGE_DIR / "results_clocks.json").write_text(json.dumps(to_jsonable(res), indent=1))
    b = res["intact_1010_bias"]
    print(f"{res['n_scored']} clocks ({res['n_unparsed']} unparsed). Intact: asked another time, hands at 10:10 "
          f"{b['share_showing_1010_when_asked_other']['mean']:.2f}, right time {b['share_right_time_when_asked_other']['mean']:.2f} "
          f"(n {b['n_other']}); asked 10:10, right {b['share_right_time_when_asked_1010']['mean']:.2f}")
    print(f"{'condition':18s} {'n':>3s} " + " ".join(f"{k[:9]:>9s}" for k, _ in CLOCK_FEATURES) + "  total")
    for cond, row in res["conditions"].items():
        print(f"{cond:18s} {row['n']:3d} " + " ".join(f"{row[k]['mean']:9.2f}" for k, _ in CLOCK_FEATURES)
              + f"  {row['total']['mean']:.2f}")
    for fam, v in res["first_to_fail"].items():
        print(f"  {fam}: first below half of intact: {v['first_below_half']}")


def janus_stats(read_dir: Path, draw_dir: Path, rng) -> dict:
    """Stretch: Janus-Pro-7B draws and reads with one language model. Same damage (lm-zero) for both.
    Reading: the kind question on Muse Image's named-kind doodles (chair, hat, bird). Drawing: chair kinds
    and the plain chair; 'kind kept' = the damaged picture's nearest intact centroid (DINOv2, leave-one-
    seed-out, among the 9 chair prompts) is its own prompt's; d_intact as in the SDXL arm."""
    from metalesionlab.plato import Embedder
    from metalesionlab.plato_damage import boot_mean_ci, centroid, cos_dist, kind_outcome

    out = {"model": "deepseek-community/Janus-Pro-7B (DeepSeek, MIT)", "read": {}, "draw": {}}
    for f in sorted(read_dir.glob("*.json")):
        d = json.loads(f.read_text())
        oc = [kind_outcome(r["label"], r["true_kind"], r["n_kinds"]) for r in d["items"]]
        out["read"][d["condition"]] = {"dose": d["dose"], "n": len(oc),
                                       **{k: boot_mean_ci(np.array([float(o == k) for o in oc]), reps=2000, rng=rng)
                                          for k in ("correct", "plain", "other_kind", "cant_tell")}}
    conds = sorted([p.name for p in draw_dir.iterdir() if p.is_dir()], key=lambda c: (c != "intact", c)) \
        if draw_dir.exists() else []
    if "intact" not in conds:
        return out
    keys = sorted(p.name for p in (draw_dir / "intact").iterdir() if p.is_dir())
    embed = Embedder()
    emb = {}
    for c in conds:
        for k in keys:
            files = sorted((draw_dir / c / k).glob("s*.png"), key=lambda p: int(p.stem[1:]))
            if files:
                emb[(c, k)] = embed([ink_crop(Image.open(x).convert("RGB")) for x in files])["cls"]
    for c in conds:
        kept, dist = [], []
        for k in keys:
            if (c, k) not in emb or ("intact", k) not in emb:
                continue
            e, e0 = emb[(c, k)], emb[("intact", k)]
            n = min(len(e), len(e0))
            for i in range(n):
                cents = {kk: centroid(emb[("intact", kk)], leave_out=i if i < len(emb[("intact", kk)]) else None)
                         for kk in keys if ("intact", kk) in emb}
                best = min(cents, key=lambda kk: cos_dist(e[i:i + 1], cents[kk])[0])
                kept.append(float(best == k))
                dist.append(float(cos_dist(e[i:i + 1], e0[i])[0]))
        dose = 0.0 if c == "intact" else float(c.split("@")[1])
        out["draw"][c] = {"dose": dose, "n": len(kept), "kind_kept": boot_mean_ci(np.array(kept), reps=2000, rng=rng),
                          "d_intact": boot_mean_ci(np.array(dist), reps=2000, rng=rng)}
    return out


def cmd_janus(args):
    from metalesionlab.plato import to_jsonable

    rng = np.random.default_rng(20261030)
    res = janus_stats(DAMAGE_DIR / "janus_read", DAMAGE_DIR / "janus_draw", rng)
    (DAMAGE_DIR / "results_janus.json").write_text(json.dumps(to_jsonable(res), indent=1))
    for c, r in res["read"].items():
        print(f"read {c:14s} correct {r['correct']['mean']:.2f} {r['correct']['ci95']} plain {r['plain']['mean']:.2f}")
    for c, r in res["draw"].items():
        print(f"draw {c:14s} kind kept {r['kind_kept']['mean']:.2f} {r['kind_kept']['ci95']} "
              f"d_intact {r['d_intact']['mean']:.2f} (n {r['n']})")


def cmd_clocks(args):
    """Muse Spark (vision, minimal reasoning) scores each clock with plato_damage.CLOCK_RUBRIC. Resumable;
    every call goes in the shared ledger ($MLL_LEDGER) and in RUN/clock_spend.jsonl, and scoring stops
    at --budget (this experiment's own cap) or when the project total passes --shared-stop."""
    import io

    from metalesionlab.meta_api import CHAT_MODEL, MetaAPI, image_data_url, spent, token_cost
    from metalesionlab.plato_damage import CLOCK_RUBRIC, parse_clock_json

    run = DAMAGE_DIR / args.run
    out_path, log = run / "clock_scores.json", run / "clock_spend.jsonl"
    done = json.loads(out_path.read_text()) if out_path.exists() else {}
    mine = lambda: sum(json.loads(x)["usd"] for x in log.read_text().splitlines() if x.strip()) if log.exists() else 0.0  # noqa: E731
    files = sorted(run.glob("*/clock__*/s*.png"))
    if args.conditions:
        files = [f for f in files if f.parent.parent.name in args.conditions]
    if args.limit:
        files = files[:args.limit]
    import threading
    from concurrent.futures import ThreadPoolExecutor

    api = MetaAPI()
    api.client = api.client.with_options(timeout=120, max_retries=2)
    lock, stop = threading.Lock(), threading.Event()

    def score(f):
        name = f"{f.parent.parent.name}/{f.parent.name}/{f.name}"
        if name in done or stop.is_set():
            return
        with lock:  # the cap is checked before every call (a few calls in flight can pass it by cents)
            if mine() > args.budget - 0.01 or spent() > args.shared_stop:
                stop.set()
                return
        im = Image.open(f).convert("RGB")
        im.thumbnail((args.side, args.side))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_data_url(buf.getvalue())}},
                                            {"type": "text", "text": CLOCK_RUBRIC}]}]
        for attempt in range(5):
            try:
                resp = api.chat(msg, reasoning_effort="minimal", ledger_tag="plato_damage_clocks")
                break
            except Exception as e:  # noqa: BLE001 - DNS drops, rate limits
                print(f"  {name} attempt {attempt + 1}: {type(e).__name__}", flush=True)
                time.sleep(10 * 2 ** attempt)
        else:
            return
        usd = token_cost(CHAT_MODEL, resp.usage)
        text = (resp.choices[0].message.content or "").strip()
        with lock:
            with log.open("a") as fh:
                fh.write(json.dumps({"ts": round(time.time(), 1), "usd": usd, "file": name}) + "\n")
            done[name] = {"raw": text[:600], "rubric": parse_clock_json(text)}
            out_path.write_text(json.dumps(done, indent=0))
            if len(done) % 25 == 0:
                print(f"{len(done)} scored; this experiment ${mine():.3f}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(score, files))
    if stop.is_set():
        print(f"budget reached (mine ${mine():.2f}, project ${spent():.2f}); stopped")
    print(f"{len(done)} clocks scored; this experiment ${mine():.3f}; project ${spent():.2f}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sheet")
    p.add_argument("run")
    p.add_argument("--conditions", nargs="*")
    p.add_argument("--keys", nargs="*")
    p.add_argument("--n", type=int, default=4)
    p.add_argument("--cell", type=int, default=128)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(fn=cmd_sheet)
    p = sub.add_parser("grid")
    p.add_argument("run")
    p.add_argument("--families", nargs="+", default=["text-zero", "unet-zero"])
    p.add_argument("--keys", nargs="+", default=["chair__rocking_chair", "chair__wheelchair"])
    p.add_argument("--n", type=int, default=4)
    p.add_argument("--cell", type=int, default=150)
    p.add_argument("--out", type=Path, required=True)
    p.set_defaults(fn=cmd_grid)
    p = sub.add_parser("crop")
    p.add_argument("run")
    p.set_defaults(fn=cmd_crop)
    p = sub.add_parser("embed")
    p.add_argument("run")
    p.add_argument("--device")
    p.set_defaults(fn=cmd_embed)
    p = sub.add_parser("measures")
    p.add_argument("run")
    p.set_defaults(fn=cmd_measures)
    p = sub.add_parser("stats")
    p.add_argument("run")
    p.add_argument("--labels", help="folder (under DAMAGE_DIR) of Glimmer label files for this run")
    p.add_argument("--reps", type=int, default=4000)
    p.set_defaults(fn=cmd_stats)
    p = sub.add_parser("glimmer")
    p.add_argument("--arm", default="glimmer_arm", help="folder (under DAMAGE_DIR) of the damaged-Glimmer results")
    p.set_defaults(fn=cmd_glimmer)
    p = sub.add_parser("clockstats")
    p.add_argument("run")
    p.set_defaults(fn=cmd_clockstats)
    p = sub.add_parser("janus")
    p.set_defaults(fn=cmd_janus)
    p = sub.add_parser("clocks")
    p.add_argument("run")
    p.add_argument("--conditions", nargs="*")
    p.add_argument("--limit", type=int)
    p.add_argument("--side", type=int, default=384)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--budget", type=float, default=2.5, help="this experiment's cap in USD")
    p.add_argument("--shared-stop", type=float, default=70.0)
    p.set_defaults(fn=cmd_clocks)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

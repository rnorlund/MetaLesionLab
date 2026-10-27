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


FAMILY_PAIRS = [("text-zero", "unet-zero"), ("text-noise", "unet-noise")]


def unit_matrix(rows: list[dict], family: str, measure: str, units: list[tuple]) -> tuple[np.ndarray, list[float]]:
    """(units, doses) array of one measure for one family; units are (key, seed_index)."""
    doses = sorted({r["dose"] for r in rows if r["family"] == family})
    idx = {u: i for i, u in enumerate(units)}
    m = np.full((len(units), len(doses)), np.nan)
    for r in rows:
        if r["family"] == family and (r["key"], r["seed_index"]) in idx:
            m[idx[(r["key"], r["seed_index"])], doses.index(r["dose"])] = r.get(measure, np.nan)
    return m, doses


def family_table(rows: list[dict], concept: str, families: list[str], rng) -> list[dict]:
    """Per family and dose: mean severity and drift measures with picture-level bootstrap CIs."""
    from metalesionlab.plato_damage import boot_mean_ci

    out = []
    sel = [r for r in rows if r["concept"] == concept and not r["plain"]]
    for fam in families:
        for dose in sorted({r["dose"] for r in sel if r["family"] == fam}):
            x = [r for r in sel if r["family"] == fam and r["dose"] == dose]
            groups = np.array([r["key"] for r in x])
            row = {"family": fam, "dose": dose, "n": len(x)}
            for k in ("d_intact", "delta_drift", "delta_tau", "delta_drift_other", "delta_d_proto", "delta_d_kind"):
                v = np.array([r.get(k, np.nan) for r in x], float)
                row[k] = boot_mean_ci(v, reps=2000, rng=rng)
                if k == "delta_drift":
                    row["delta_drift_by_kind_boot"] = boot_mean_ci(v, reps=2000, rng=rng, groups=groups)
            out.append(row)
    return out


def drift_contrasts(rows: list[dict], concept: str, rng) -> dict:
    """H1: language vs drawing damage at matched severity (pictures resampled; kinds as a check)."""
    from metalesionlab.plato_damage import boot_mean_ci, boot_matched_contrast

    units = sorted({(r["key"], r["seed_index"]) for r in rows if r["concept"] == concept and not r["plain"]
                    and r["family"] != "intact"})
    groups = np.array([u[0] for u in units])
    out = {}
    for a, b in FAMILY_PAIRS:
        if not any(r["family"] == a for r in rows) or not any(r["family"] == b for r in rows):
            continue
        res = {}
        for measure in ("delta_drift", "delta_tau", "delta_drift_other"):
            da, _ = unit_matrix(rows, a, "d_intact", units)
            va, doses_a = unit_matrix(rows, a, measure, units)
            db, _ = unit_matrix(rows, b, "d_intact", units)
            vb, doses_b = unit_matrix(rows, b, measure, units)
            res[measure] = {"by_picture": boot_matched_contrast(da, va, db, vb, rng=rng),
                            "by_kind": boot_matched_contrast(da, va, db, vb, rng=rng, groups=groups, reps=2000)}
        va, _ = unit_matrix(rows, a, "delta_drift", units)
        res["pooled_delta_drift_" + a] = boot_mean_ci(np.nanmean(va, axis=1), rng=rng)
        vb, _ = unit_matrix(rows, b, "delta_drift", units)
        res["pooled_delta_drift_" + b] = boot_mean_ci(np.nanmean(vb, axis=1), rng=rng)
        out[f"{a} vs {b}"] = res
    return out


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
    api = MetaAPI()
    api.client = api.client.with_options(timeout=120, max_retries=2)
    for f in files:
        name = f"{f.parent.parent.name}/{f.parent.name}/{f.name}"
        if name in done:
            continue
        if mine() > args.budget - 0.01 or spent() > args.shared_stop:
            print(f"budget reached (mine ${mine():.2f}, project ${spent():.2f}); stopping")
            break
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
            continue
        usd = token_cost(CHAT_MODEL, resp.usage)
        with log.open("a") as fh:
            fh.write(json.dumps({"ts": round(time.time(), 1), "usd": usd, "file": name}) + "\n")
        text = (resp.choices[0].message.content or "").strip()
        done[name] = {"raw": text[:600], "rubric": parse_clock_json(text)}
        out_path.write_text(json.dumps(done, indent=0))
        if len(done) % 25 == 0:
            print(f"{len(done)} scored; this experiment ${mine():.3f}", flush=True)
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
    p = sub.add_parser("clocks")
    p.add_argument("run")
    p.add_argument("--conditions", nargs="*")
    p.add_argument("--limit", type=int)
    p.add_argument("--side", type=int, default=384)
    p.add_argument("--budget", type=float, default=2.5, help="this experiment's cap in USD")
    p.add_argument("--shared-stop", type=float, default=70.0)
    p.set_defaults(fn=cmd_clocks)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

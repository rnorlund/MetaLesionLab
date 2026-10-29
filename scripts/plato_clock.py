"""The clock test (docs/plato_clock_plan.md): Muse Image given the MoCA clock instruction, scored on the MoCA's three
clock points by eye and by Muse Spark, and placed beside the averages of 365 adults' clocks.

  generate --arm A|B      A: the instruction 16 times (4 calls of n = 4); B: 16 age personas (one call each)
  svg --model spark|wonder  C: a text model draws the clock as SVG, 16 samples; rendered with plato_scale.classify
  sheet ARM               enlarged pictures with file names only, for scoring by eye (writes CLOCK_DIR/sheets/)
  read ARM                Muse Spark's clock checklist (plato_damage.CLOCK_RUBRIC) on every picture of ARM; refuses
                          until every picture has an eye score in public_data/plato_clock_byeye.json
  embed                   DINOv2 (the draw pad's embedder) on every picture and on /plato/damage's SDXL clocks
  export                  the page's data (web/data/plato_clock.json), its pictures, and the draw pad's clock reference

Paid calls carry the ledger tag "plato_clock"; each is refused once the study's spend reaches $2.00 or the shared
ledger passes $70. Run with MLL_LEDGER pointing at the shared ledger (the main checkout's runs/costs.jsonl).
Pictures and readings stay in $PLATO_CLOCK_DIR, outside the repository.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from metalesionlab import plato_clock as C  # noqa: E402

ARMS = {"A": "default", "B": "persona", "spark": "svg_spark", "wonder": "svg_wonder"}
SVG_MODELS = {"spark": "muse-spark-1.3", "wonder": "muse-wonder-1.0"}


def arm_dir(arm: str) -> Path:
    return C.CLOCK_DIR / ARMS[arm]


def pictures(arm: str) -> list[Path]:
    """The arm's pictures in a fixed order (failed SVGs have no picture: they are listed in svg.json)."""
    d = arm_dir(arm)
    if arm == "B":
        return sorted(d.glob("age*.png"))
    if arm in SVG_MODELS:
        return sorted(d.glob("s*.png"), key=lambda p: int(p.stem[1:]))
    return sorted(d.glob("c*_*.png"))


# ---------- money ----------

def ledger():
    from metalesionlab import meta_api

    if not meta_api.LEDGER.exists():
        raise SystemExit(f"No ledger at {meta_api.LEDGER}: set MLL_LEDGER to the shared runs/costs.jsonl")
    return meta_api


def check_budget(estimate: float) -> None:
    m = ledger()
    mine, total = C.tag_spend(m.LEDGER), m.spent()
    if total > C.SHARED_STOP:
        raise SystemExit(f"shared ledger at ${total:.2f}, past ${C.SHARED_STOP:.0f}: stopping")
    if mine + estimate > C.BUDGET + 1e-9:
        raise SystemExit(f"this study has spent ${mine:.3f}; ${estimate:.3f} more would pass its ${C.BUDGET:.2f} cap")


# ---------- A and B: Muse Image ----------

def cmd_generate(args):
    from metalesionlab.plato import downscale

    m = ledger()
    api = m.MetaAPI()
    d = arm_dir(args.arm)
    d.mkdir(parents=True, exist_ok=True)
    jobs = []
    if args.arm == "A":
        for call in range(C.N // 4):
            names = [f"c{call}_{i}.png" for i in range(4)]
            if not all((d / n).exists() for n in names):
                jobs.append((C.IMAGE_PROMPT, names))
        meta = {"prompt": C.IMAGE_PROMPT, "calls": "4 x n=4"}
    else:
        decades = None
        pub = C.load_public()
        if pub:
            decades = [{"lo": x["age_lo"], "hi": x["age_hi"], "n": x["n"]} for x in pub.get("decades", [])
                       if "age_lo" in x and "age_hi" in x and x.get("n")] or None
        ages, rule = C.persona_ages(decades)
        old = d / "meta.json"
        if old.exists():  # the ages are fixed at the first run
            prev = json.loads(old.read_text())
            ages, rule = prev["ages"], prev["age_rule"]
        for a in ages:
            if not (d / f"age{a:02d}.png").exists():
                jobs.append((C.persona_prompt(a), [f"age{a:02d}.png"]))
        meta = {"prompt_template": C.persona_prompt(0).replace("a 0-year-old", "a {age}-year-old"), "ages": ages,
                "age_rule": rule, "calls": "16 x n=1"}
    meta["model"] = "muse-image-1.0"
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"arm {args.arm}: {len(jobs)} calls to make; ${0.01 * sum(len(n) for _, n in jobs):.2f}")
    if args.dry_run:
        for p, n in jobs:
            print(" ", n, "<-", p)
        return
    for prompt, names in jobs:
        check_budget(0.01 * len(names))
        t0 = time.time()
        images = m.retry_network(lambda: api.generate_images(prompt, n=len(names), ledger_tag=C.TAG), tries=5, base=15)
        for name, png in zip(names, images):
            downscale(png, 512).save(d / name)
        print(f"  {names[0]}..: {len(images)} pictures in {time.time() - t0:.0f}s; study ${C.tag_spend(m.LEDGER):.3f}",
              flush=True)


# ---------- C: SVG from text models ----------

def cmd_svg(args):
    from metalesionlab.plato_scale import classify

    m = ledger()
    api = m.MetaAPI()
    model = SVG_MODELS[args.model]
    d = arm_dir(args.model)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "svg.json"
    rec = json.loads(path.read_text()) if path.exists() else {
        "model": model, "prompt": C.SVG_PROMPT, "temperature": 1.0, "reasoning_effort": "minimal",
        "max_completion_tokens": C.SVG_MAX_TOKENS, "samples": []}
    have = {s["i"] for s in rec["samples"]}
    for i in range(args.n):
        if i in have:
            continue
        check_budget(0.03 if args.model == "wonder" else 0.01)
        t0 = time.time()
        r = m.retry_network(lambda: api.chat([{"role": "user", "content": C.SVG_PROMPT}], model=model,
                                             reasoning_effort="minimal", ledger_tag=C.TAG, temperature=1.0,
                                             max_completion_tokens=C.SVG_MAX_TOKENS), tries=5, base=15)
        c = r.choices[0]
        text = c.message.content or ""
        out = classify(text)
        if out["ok"]:
            out["image"].save(d / f"s{i}.png")
        rec["samples"].append({"i": i, "text": text, "finish_reason": c.finish_reason, "ok": out["ok"],
                               "reason": out["reason"], "usd": round(m.token_cost(model, r.usage), 6),
                               "n_tokens": r.usage.completion_tokens, "seconds": round(time.time() - t0, 1)})
        rec["samples"].sort(key=lambda s: s["i"])
        path.write_text(json.dumps(rec, indent=1))
        print(f"  {args.model} #{i}: {out['reason'] or 'ok'}, {r.usage.completion_tokens} tokens, "
              f"${rec['samples'][-1]['usd']:.4f}; study ${C.tag_spend(m.LEDGER):.3f}", flush=True)


# ---------- scoring by eye: sheets ----------

def cmd_sheet(args):
    from PIL import ImageDraw

    out = C.CLOCK_DIR / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    files = pictures(args.arm)
    for k in range(0, len(files), 4):
        chunk = files[k:k + 4]
        sheet = Image.new("RGB", (2 * 520, 2 * 548), "white")
        g = ImageDraw.Draw(sheet)
        for j, f in enumerate(chunk):
            im = Image.open(f).convert("RGB")
            im.thumbnail((512, 512))
            x, y = (j % 2) * 520 + 4, (j // 2) * 548 + 4
            sheet.paste(im, (x, y + 28))
            g.text((x, y + 4), f.name, fill=(200, 0, 0))
        p = out / f"{ARMS[args.arm]}_{k // 4}.png"
        sheet.save(p)
        print(p)


BYEYE = ROOT / "public_data" / "plato_clock_byeye.json"   # the eye scores are published with the repository


def byeye() -> dict:
    return {k: v for k, v in json.loads(BYEYE.read_text()).items() if not k.startswith("_")} if BYEYE.exists() else {}


def key_of(arm: str, f: Path) -> str:
    return f"{ARMS[arm]}/{f.name}"


# ---------- Muse Spark's checklist ----------

def cmd_read(args):
    from metalesionlab.plato_damage import CLOCK_RUBRIC, parse_clock_json

    m = ledger()
    eye = byeye()
    files = pictures(args.arm)
    missing = [key_of(args.arm, f) for f in files if key_of(args.arm, f) not in eye]
    if missing:
        raise SystemExit(f"score these by eye first: {missing}")
    path = C.CLOCK_DIR / "spark.json"
    done = json.loads(path.read_text()) if path.exists() else {}
    api = m.MetaAPI()
    for f in files:
        k = key_of(args.arm, f)
        if k in done:
            continue
        check_budget(0.006)
        im = Image.open(f).convert("RGB")
        im.thumbnail((384, 384))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        msg = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": m.image_data_url(buf.getvalue())}},
                                            {"type": "text", "text": CLOCK_RUBRIC}]}]
        r = m.retry_network(lambda: api.chat(msg, reasoning_effort="minimal", ledger_tag=C.TAG), tries=5, base=15)
        text = (r.choices[0].message.content or "").strip()
        done[k] = {"raw": text[:800], "rubric": parse_clock_json(text), "usd": round(m.token_cost(m.CHAT_MODEL, r.usage), 6)}
        path.write_text(json.dumps(done, indent=1))
        print(f"  {k}: {C.spark_points(done[k]['rubric'])}", flush=True)
    print(f"study ${C.tag_spend(m.LEDGER):.3f}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("generate")
    p.add_argument("--arm", choices=["A", "B"], required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_generate)
    p = sub.add_parser("svg")
    p.add_argument("--model", choices=list(SVG_MODELS), required=True)
    p.add_argument("--n", type=int, default=C.N)
    p.set_defaults(fn=cmd_svg)
    p = sub.add_parser("sheet")
    p.add_argument("arm", choices=list(ARMS))
    p.set_defaults(fn=cmd_sheet)
    p = sub.add_parser("read")
    p.add_argument("arm", choices=list(ARMS))
    p.set_defaults(fn=cmd_read)
    for name in ("embed", "export"):
        p = sub.add_parser(name)
        p.set_defaults(fn=globals()[f"cmd_{name}"])
    args = ap.parse_args()
    args.fn(args)


DAMAGE_IMG = ROOT / "metalesionlab" / "web" / "static" / "img" / "plato_damage"
SETS = ("default", "persona", "svg_spark", "svg_wonder")


def set_files(s: str) -> list[Path]:
    return pictures({v: k for k, v in ARMS.items()}[s])


def damage_files() -> list[Path]:
    """/plato/damage's SDXL clocks (public pictures in the repo): intact and three levels of each damage."""
    return sorted(DAMAGE_IMG.glob("clock_*.webp"))


def prepared(f: Path) -> Image.Image:
    """A picture prepared as the people's clocks were (plato_clock.face_normalise): centred and scaled on its face."""
    return C.face_normalise(Image.open(f).convert("RGB"))


def average_image(ims: list[Image.Image]) -> Image.Image:
    """The pixel average of face-normalised clocks, drawn as the export draws people's (README, bins.json): black ink
    with alpha = mean ink / the shared display scale, blurred with sigma 1 px at 256 px, at 512 px (RGBA)."""
    import numpy as np
    from scipy.ndimage import gaussian_filter

    ink = np.mean([1 - np.asarray(im.convert("L"), dtype=np.float32) / 255 for im in ims], axis=0)
    ink = gaussian_filter(ink, 1.0)
    alpha = np.clip(ink / C.DISPLAY_SCALE, 0, 1)
    a = Image.fromarray((alpha * 255).round().astype(np.uint8)).resize((512, 512), Image.LANCZOS)
    out = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    out.putalpha(a)
    return out


def cmd_embed(args):
    """DINOv2-base CLS (the draw pad's embedder, metalesionlab.draw) of every AI clock and of the damage clocks, each
    prepared as the people's clocks were, and each set's average clock. Writes CLOCK_DIR/emb.npz and avg_<set>.png."""
    import numpy as np

    from metalesionlab import draw

    model = draw.load_embedder()
    out, names = {}, {}
    groups = {s: set_files(s) for s in SETS} | {"damage": damage_files()}
    sheets = C.CLOCK_DIR / "sheets"
    sheets.mkdir(exist_ok=True)
    for s, files in groups.items():
        ims = [prepared(f) for f in files]
        out[s] = np.vstack([model(ims[i:i + 16]) for i in range(0, len(ims), 16)]).astype(np.float32)
        names[s] = [f.name for f in files]
        sheet = Image.new("RGB", (8 * 128, 128 * ((len(ims) + 7) // 8)), "white")
        for i, im in enumerate(ims):  # what DINOv2 saw, to check the face fits by eye
            sheet.paste(im.resize((128, 128)), ((i % 8) * 128, (i // 8) * 128))
        sheet.save(sheets / f"prepared_{s}.png")
        if s != "damage":
            average_image(ims).save(C.CLOCK_DIR / f"avg_{s}.png")
        print(f"{s}: {len(files)} pictures, {out[s].shape}", flush=True)
    np.savez(C.CLOCK_DIR / "emb.npz", **out)
    (C.CLOCK_DIR / "emb_files.json").write_text(json.dumps({"backend": getattr(model, "backend", "?"), "files": names},
                                                           indent=1))


WEB = ROOT / "metalesionlab" / "web"
IMG = WEB / "static" / "img" / "plato_clock"
DRAW_SPRITE = WEB / "static" / "img" / "draw" / "clock_muse.webp"
DAMAGE_LABELS = {"text-noise": "language part, noise", "text-zero": "language part, neurons off",
                 "unet-noise": "drawing part, noise", "unet-zero": "drawing part, neurons off"}


def display_crop(f: Path, side: int) -> Image.Image:
    """A square crop centred on the clock's face (the circle plato_clock.fit_face finds), 1.5 face radii each way, with
    the paper kept, for showing on the page. Numbers just outside the face stay in; a caption far below may not."""
    im = Image.open(f).convert("RGB")
    mask = C.ink_mask(im, max_side=max(im.size))
    cx, cy, r = C.fit_face(C.thin(mask))
    half = 1.5 * r
    sq = im.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half)))
    # the crop may pass the picture's edge: fill with the paper's colour, not black
    bg = Image.new("RGB", sq.size, tuple(int(v) for v in im.resize((1, 1), Image.BOX).getpixel((0, 0))))
    bg.paste(im.crop((max(0, int(cx - half)), max(0, int(cy - half)), min(im.width, int(cx + half)),
                      min(im.height, int(cy + half)))), (max(0, -int(cx - half)), max(0, -int(cy - half))))
    return bg.resize((side, side), Image.LANCZOS)


def save_webp(im: Image.Image, path: Path, quality: int = 80) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "WEBP", quality=quality, method=6)
    return "/" + str(path.relative_to(WEB))


def scored(set_name: str, files: list[Path], eye: dict, spark: dict) -> tuple[list[dict], list[dict], list[dict]]:
    keys = [f"{set_name}/{f.name}" for f in files]
    e = [C.eye_points(eye[k]) for k in keys]
    s = [C.spark_points(spark[k]["rubric"]) if k in spark else None for k in keys]
    return keys, e, s


def unit_rows(x):
    import numpy as np

    x = np.asarray(x, dtype=np.float64)
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


ABC_IMG = IMG / "abc"   # the people's group averages, from the private analysis's public export only
CREDIT = ("Clock averages: USC Aging Brain Cohort (IRB-approved), 315 adults aged 20 to 80 and over, shown only as "
          "group averages of 20 or more.")


def public_image(rel: str, dest: str) -> str:
    """One average image from the export (transparent PNG), re-encoded as WebP with its alpha. Only files under
    PUBLIC_DIR are ever read here."""
    src = (C.PUBLIC_DIR / rel).resolve()
    assert src.is_relative_to(C.PUBLIC_DIR.resolve()) and src.suffix == ".png", src
    im = Image.open(src).convert("RGBA")
    path = ABC_IMG / dest
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "WEBP", quality=88, method=6)
    return "/" + str(path.relative_to(WEB))


def people_block(stats: dict) -> dict:
    """What the page uses from the export: aggregates only (each group n >= 20), its averages as WebP."""
    bins = json.loads((C.PUBLIC_DIR / "averages_by_decade" / "bins.json").read_text())
    steps = json.loads((C.PUBLIC_DIR / "form_emerges" / "steps.json").read_text())
    levels = json.loads((C.PUBLIC_DIR / "averages_by_clock_score" / "levels.json").read_text())
    n = stats["n"]
    by_points = stats["validation"]["distance_by_clock_points"]
    full = by_points["3 (full)"]["n"]
    hands = stats["hands_in_the_averages"]
    decades = []
    for b, d in zip(bins["bins"], stats["by_decade"]):
        assert b["age_range_years"] == d["age_range_years"] and b["n"] == d["n"]
        r = d["age_range_years"]
        decades.append({"age_range_years": r, "n": d["n"], "src": public_image(f"averages_by_decade/{b['file']}",
                                                                              f"decade_{r.replace('+', 'plus')}.webp"),
                        "spread": d["spread"], "spread_ci95": d["spread_ci95"],
                        "distance": d["distance_to_typical"], "distance_ci95": d["distance_ci95"],
                        "mean_points": d["mean_clock_points"], "share_full": d["share_full_clock_points"],
                        "hands": {k.replace("ink_toward_", "to_").replace("_rel_median", ""): v
                                  for k, v in hands[r].items() if k.startswith("ink_toward")}})
    form = [{"n": s["n"], "src": public_image(f"form_emerges/{s['file']}", f"form_{s['n']:03d}.webp")}
            for s in steps["steps"]]
    lv = [{"points": int(x["moca_clock_points"]), "n": x["n"],
           "src": public_image(f"averages_by_clock_score/{x['file']}", f"points_{x['moca_clock_points']}.webp")}
          for x in levels["levels"]]
    ref = json.loads((C.PUBLIC_DIR / "drawing_pad_reference.json").read_text())
    ai = stats["ai_and_public_clocks"]
    return {
        "source": "The private analysis's public export (aggregates only; every group n >= 20).",
        "credit": CREDIT,
        "n_images": n["images"], "n_baseline": n["baseline_images"], "n_analysed": n["baseline_analysed"],
        "n_excluded": n["excluded_preprocessing"], "excluded_reasons": n["excluded_reasons"],
        "full_points": {"k": full, "n": n["baseline_analysed"]},
        "two_points": {"k": by_points["2"]["n"], "n": n["baseline_analysed"]},
        "spread": ai["human_moca_clocks"]["spread"], "spread_ci95": ai["human_moca_clocks"]["spread_ci95"],
        "distance_mean": ai["human_moca_clocks"]["distance_mean"],
        "quantiles": ref["distance_quantiles_all"],
        "validation": {"rho_distance_vs_points": stats["validation"]["rho_distance_vs_clock_points"],
                       "distance_full": by_points["3 (full)"], "distance_two": by_points["2"],
                       "auc_below_full_farther": stats["validation"]["auc_below_full_farther"]},
        "age_trend": stats["age_trend"],
        "decades": decades, "form": form, "levels": lv,
        "avg_all": form[-1]["src"],
    }


def bootstrap_mean_ci(x, reps: int = 4000, seed: int = 0) -> list[float]:
    import numpy as np

    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), (reps, len(x)))].mean(1)
    return [float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def diff_ci(a, b, reps: int = 4000, seed: int = 0) -> list[float]:
    """Bootstrap 95% CI of mean(b) - mean(a)."""
    import numpy as np

    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(seed)
    d = b[rng.integers(0, len(b), (reps, len(b)))].mean(1) - a[rng.integers(0, len(a), (reps, len(a)))].mean(1)
    return [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))]


def quantile_band(d: float, q: dict) -> list[int]:
    """The two published quantiles (percent) a distance sits between: [0, 5] ... [95, 100]."""
    keys = sorted((int(k[1:]), v) for k, v in q.items() if k.startswith("p"))
    lo = 0
    for p, v in keys:
        if d < v:
            return [lo, p]
        lo = p
    return [lo, 100]


def cmd_export(args):
    """The page's data (web/data/plato_clock.json), its pictures (static/img/plato_clock/), the draw pad's Muse sprite
    and the pad's clock reference (web/data/draw_clock.json: the people's centroid and quantiles, Muse's centroid)."""
    import numpy as np

    from metalesionlab.plato import bootstrap_spread, ci, cosine_distances, spearman_ci, spread, to_jsonable

    stats = C.load_public()
    if not stats:
        raise SystemExit(f"No public export at {C.PUBLIC_DIR}: the page needs the people's averages.")
    ref = json.loads((C.PUBLIC_DIR / "drawing_pad_reference.json").read_text())
    centroid = unit_rows(np.asarray(ref["centroid"], float))
    eye = byeye()
    spark = json.loads((C.CLOCK_DIR / "spark.json").read_text())
    emb = np.load(C.CLOCK_DIR / "emb.npz")
    files_of = json.loads((C.CLOCK_DIR / "emb_files.json").read_text())["files"]
    pmeta = json.loads((C.CLOCK_DIR / "persona" / "meta.json").read_text())
    rng = np.random.default_rng(20261028)
    people = people_block(stats)
    q = people["quantiles"]
    out = {"about": "The clock test (/plato/clock): Meta's Muse Image given the MoCA clock instruction, scored on the "
                    "MoCA's three clock points by eye and by Muse Spark, beside the averages of adults' clocks "
                    "(docs/plato_clock.md). Derived results only.",
           "instruction": C.INSTRUCTION, "prompt": C.IMAGE_PROMPT, "persona_prompt": pmeta["prompt_template"],
           "svg_prompt": C.SVG_PROMPT, "points": list(C.POINTS), "people": people,
           # other clocks on the people's measure, from the export: AI sets and Quick, Draw!'s players
           "references": {k: stats["ai_and_public_clocks"][k] for k in ("muse_doodle", "quickdraw", "sdxl_doodle")}}

    def block(set_name: str, folder: str, side: int = 320) -> dict:
        files = set_files(set_name)
        assert [f.name for f in files] == files_of[set_name], set_name
        keys, e, s = scored(set_name, files, eye, spark)
        x = unit_rows(emb[set_name])
        d = cosine_distances(x)
        dist = (1 - x @ centroid).tolist()
        clocks = []
        for f, k, ee, ss, dd in zip(files, keys, e, s, dist):
            clocks.append({"file": f.name, "src": save_webp(display_crop(f, side), IMG / folder / f"{f.stem}.webp"),
                           "eye": ee, "spark": ss, "hands_n": eye[k]["hands_n"], "ratio": eye[k].get("ratio"), "note": eye[k].get("note") or "",
                           "distance": dd, "band": quantile_band(dd, q)})
        cen = unit_rows(x.mean(0))
        b = {"n": len(files), "clocks": clocks, "eye": C.tally(e), "spark": C.tally([z for z in s if z]),
             "agreement": C.agreement(e, s) if all(s) else None,
             "spread": {"value": spread(d), "ci95": ci(bootstrap_spread(d, 2000, rng))},
             "distance": {"mean": float(np.mean(dist)), "ci95": bootstrap_mean_ci(dist), "min": min(dist),
                          "max": max(dist), "centroid": float(1 - cen @ centroid)},
             "beyond_p95": int(sum(v >= q["p95"] for v in dist)),
             "minute_at_2": sum(eye[k]["minute_to"] == 2 for k in keys)}
        if set_name == "default":  # the page and the pad show Muse's 16 laid on top of each other (the other sets aren't)
            img = Image.open(C.CLOCK_DIR / f"avg_{set_name}.png").convert("RGBA")
            path = IMG / f"{folder}_avg.webp"
            img.save(path, "WEBP", quality=88, method=6)
            b["avg"] = "/" + str(path.relative_to(WEB))
        return b

    out["muse"] = block("default", "muse")
    P = out["persona"] = block("persona", "persona")
    P.update(ages=pmeta["ages"], age_rule=pmeta["age_rule"])
    for c, a in zip(P["clocks"], pmeta["ages"]):
        assert c["file"] == f"age{a:02d}.png"
        c["age"] = a
    ages = np.array(pmeta["ages"], float)
    dist = [c["distance"] for c in P["clocks"]]
    eye_t = [c["eye"]["total"] for c in P["clocks"]]
    sp_t = [c["spark"]["total"] for c in P["clocks"]]
    P["trend"] = {"distance": spearman_ci(ages, dist, 2000, rng), "eye_points": spearman_ci(ages, eye_t, 2000, rng),
                  "spark_points": spearman_ci(ages, sp_t, 2000, rng)}
    dA, dB = cosine_distances(unit_rows(emb["default"])), cosine_distances(unit_rows(emb["persona"]))
    diff = bootstrap_spread(dB, 2000, np.random.default_rng(1)) - bootstrap_spread(dA, 2000, np.random.default_rng(2))
    P["spread_vs_default"] = {"difference": spread(dB) - spread(dA), "ci95": ci(diff)}
    # Q3: the change from the youngest decade to the oldest, the AI's personas against people's averages
    dec = people["decades"]
    young, old = dec[0], dec[-1]

    def in_range(a, r):
        lo, _, hi = r.partition("-")
        return int(lo.rstrip("+")) <= a <= (int(hi) if hi else 200)

    iy = [i for i, a in enumerate(pmeta["ages"]) if in_range(a, young["age_range_years"])]
    io = [i for i, a in enumerate(pmeta["ages"]) if in_range(a, old["age_range_years"])]
    comp = {}
    for name, vals, ppl in (("distance", dist, old["distance"] - young["distance"]),
                            ("eye_points", eye_t, old["mean_points"] - young["mean_points"]),
                            ("spark_points", sp_t, old["mean_points"] - young["mean_points"])):
        a, b = [vals[i] for i in iy], [vals[i] for i in io]
        change = float(np.mean(b) - np.mean(a))
        cic = diff_ci(a, b)
        comp[name] = {"ai_change": change, "ai_ci95": cic, "people_change": ppl,
                      "verdict": C.trend_verdict(change, cic, ppl)}
    P["vs_people"] = {"young": young["age_range_years"], "old": old["age_range_years"],
                      "ai_ages_young": [pmeta["ages"][i] for i in iy], "ai_ages_old": [pmeta["ages"][i] for i in io],
                      **comp}
    # the persona row under the decade averages: each decade's persona clocks
    for d in dec:
        d["personas"] = [i for i, a in enumerate(pmeta["ages"]) if in_range(a, d["age_range_years"])]

    out["svg"] = {}
    for m in SVG_MODELS:
        rec = json.loads((arm_dir(m) / "svg.json").read_text())
        b = block(f"svg_{m}", f"svg_{m}", 256)
        b.update(model=rec["model"], n_samples=len(rec["samples"]), failed=sum(not x["ok"] for x in rec["samples"]),
                 usd=round(sum(x["usd"] for x in rec["samples"]), 4))
        out["svg"][m] = b

    # the predictions for condition A (docs/plato_clock_plan.md), as they came out
    M = out["muse"]
    from scipy.stats import fisher_exact

    k_full = M["eye"]["all_three"]
    pf = float(fisher_exact([[k_full, 16 - k_full], [people["full_points"]["k"],
                                                     people["full_points"]["n"] - people["full_points"]["k"]]]).pvalue)
    wrong = {t: c for t, c in M["eye"]["times"].items() if t != "11:10"}
    out["predictions"] = {
        "P1": {"text": "hands point on at most 7 of 16; most common wrong time 10:10",
               "result": f"{M['eye']['hands']['k']} of 16 earned the hands point; wrong times: {wrong}",
               "supported": M["eye"]["hands"]["k"] <= 7},
        "P2": {"text": "minute hand at the 2 on at least 12 of 16", "result": f"{M['minute_at_2']} of 16",
               "supported": M["minute_at_2"] >= 12},
        "P3": {"text": "contour on at least 15, numbers on at least 12",
               "result": f"contour {M['eye']['contour']['k']}, numbers {M['eye']['numbers']['k']}",
               "supported": M["eye"]["contour"]["k"] >= 15 and M["eye"]["numbers"]["k"] >= 12},
        "P4": {"text": "Muse's share below people's (Fisher, p < 0.05)",
               "result": f"all three points: Muse {k_full} of 16, people {people['full_points']['k']} of "
                         f"{people['full_points']['n']}; Fisher p = {pf:.2f}",
               "supported": False if k_full / 16 >= people["full_points"]["k"] / people["full_points"]["n"] else pf < 0.05,
               "deviation": "The export reports the share with all three points, not the hands point alone, so the "
                            "test compares all three points."},
        "P5": {"text": "eye and Spark agree on at least 12 of 16 for each point",
               "result": {k: M["agreement"][k]["agree"] for k in C.POINTS},
               "supported": all(M["agreement"][k]["agree"] >= 12 for k in C.POINTS)},
    }
    out["muse"]["fisher_full"] = pf

    # the draw pad's reveal strip: Muse's 16 clocks as one sprite (8 x 2 cells of 112 px)
    cell, cols = 112, 8
    sheet = Image.new("RGB", (cell * cols, cell * 2), "white")
    for i, f in enumerate(set_files("default")):
        sheet.paste(display_crop(f, cell), ((i % cols) * cell, (i // cols) * cell))
    save_webp(sheet, DRAW_SPRITE, 82)
    M["sprite"] = {"src": "/static/img/draw/clock_muse.webp", "cell": cell, "cols": cols, "n": 16}

    # /plato/damage's SDXL clocks, scored with the same checklist there (contour + numbers + asked time, 0-3): the
    # export's mapping. Never matched to an age: every level, intact too, lies beyond every group of people.
    strip = json.loads((WEB / "data" / "plato_damage.json").read_text())["clocks"]["strip"]
    mapping = stats["sdxl_damage_mapping"]
    levels = json.loads((WEB / "data" / "plato_damage.json").read_text())["slider"]["levels"]
    damage = []
    for method in ("text-noise", "text-zero", "unet-noise", "unet-zero"):
        conds = [x["cond"] for x in levels[method]]
        row = []
        for i, p in enumerate(strip[method]["8_45"]):
            cond = "intact" if i == 0 else next(c for c in conds if c in mapping and
                                                 p["label"] in [x["label"] for x in levels[method] if x["cond"] == c])
            row.append({"cond": cond, "label": p["label"], "src": p["img"],
                        "src_3_00": strip[method]["3_00"][i]["img"],
                        "checklist": mapping[cond]["spark_checklist_pseudo_score_0_3"],
                        "beyond_every_human_group": mapping[cond]["beyond_every_human_group"]})
        damage.append({"method": method, "label": DAMAGE_LABELS[method], "levels": row})
    out["damage"] = damage

    problems = C.validate_public(people, allow_keys=set())
    if problems:
        raise SystemExit("the people's block is not public-ready: " + "; ".join(problems[:10]))
    dest = WEB / "data" / "plato_clock.json"
    dest.write_text(json.dumps(to_jsonable(out), ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"wrote {dest.relative_to(ROOT)} ({dest.stat().st_size // 1024} KB)")

    # the draw pad's clock: the people's centroid and quantiles, and Muse's centroid (condition A). Nothing else.
    muse_c = unit_rows(unit_rows(emb["default"]).mean(0))
    pad = {"about": "The draw pad's clock (/draw?thing=clock): the people's typical clock (the mean direction of the "
                    f"{ref['n_in_centroid']} adults' clocks with all three clock points, from the private analysis's "
                    "public export) with the quantiles of adults' distances to it, and Meta's Muse Image's average "
                    "clock (its 16 clocks for the MoCA instruction). Each a 768-number DINOv2-base CLS direction. "
                    "A drawing is prepared as the people's clocks were (plato_clock.face_normalise).",
           "model": "facebook/dinov2-base", "prep": "plato_clock.face_normalise",
           "concepts": [{
               "key": "clock", "label": "clock", "phrase": "a clock", "mode": "group", "group": "clock",
               "instruction": C.INSTRUCTION, "task": C.INSTRUCTION.removeprefix("Draw a clock. "),
               "n_people": ref["n_in_centroid"], "n_people_quantiles":
                   ref["distance_quantiles_all"]["n"], "n_ai": 16,
               "quantiles": {k: v for k, v in ref["distance_quantiles_all"].items() if k.startswith("p")},
               "d_ai_to_people": float(1 - muse_c @ centroid),
               "images": {"people": next(x["src"] for x in people["levels"] if x["points"] == 3), "ai": M["avg"]},
               "hook": f"Meta’s image AI, Muse Image, drew 10 past 11 on {M['eye']['times'].get('11:10', 0)} of its 16 clocks, by our count.",
               "sprites": {"muse": M["sprite"]},
               "prompt": C.IMAGE_PROMPT,
               "vectors": {"people_centroid": [round(float(v), 6) for v in centroid],
                           "ai_centroid": [round(float(v), 6) for v in muse_c]}}],
           "credits": [CREDIT, "Meta Muse Image 1.0; embeddings: Meta DINOv2-base."]}
    dpad = WEB / "data" / "draw_clock.json"
    dpad.write_text(json.dumps(pad, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"wrote {dpad.relative_to(ROOT)} ({dpad.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

"""The clock test (docs/plato_clock_plan.md): Muse Image given the MoCA clock instruction, scored on the MoCA's three
clock points by eye and by Muse Spark, and placed beside the averages of 365 adults' clocks.

  generate --arm A|B      A: the instruction 16 times (4 calls of n = 4); B: 16 age personas (one call each)
  svg --model spark|wonder  C: a text model draws the clock as SVG, 16 samples; rendered with plato_scale.classify
  sheet ARM               enlarged pictures with file names only, for scoring by eye (writes CLOCK_DIR/sheets/)
  read ARM                Muse Spark's clock checklist (plato_damage.CLOCK_RUBRIC) on every picture of ARM; refuses
                          until every picture has an eye score in CLOCK_DIR/byeye.json
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


def byeye() -> dict:
    p = C.CLOCK_DIR / "byeye.json"
    return json.loads(p.read_text()) if p.exists() else {}


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


def cmd_embed(args):
    raise SystemExit("embed: added after the runs")


def cmd_export(args):
    raise SystemExit("export: added after the runs")


if __name__ == "__main__":
    main()

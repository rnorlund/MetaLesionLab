"""Prisoners of the cave: render, blind coding sheets, the hash, and the automatic measures
(docs/plato_cave_twins_plan.md). Runs on the Mac, in this order:

  reuse    copy the text twins' chair answers from the scale experiment (same request and settings)
  render   extract and render every SVG and classify failures (objective; needed to see the drawings)
  sheets   write the three blind coding sheets (descriptions, chairs, clocks) and their keys
  seal     check the by-eye codes against the sheets and write their SHA-256 to docs/plato_cave_twins_codes.sha256
           (commit that file before running the next two steps)
  read     Google SigLIP 2 reads every rendered drawing among the 35 Plato's Chair names
  embed    Meta DINOv2 embeds every rendered drawing (ink-cropped)

Files under $PLATO_TWINS_DIR: raw/, png/, render.json, sheets/ (what the coder sees), codes/ (key_*.json, which
the coder doesn't open, and codes_*.json, the coder's codes), reader.json, emb/.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from metalesionlab import plato_scale as ps  # noqa: E402
from metalesionlab import plato_twins as pt  # noqa: E402

D = pt.TWINS_DIR
HASH_FILE = ROOT / "docs" / "plato_cave_twins_codes.sha256"
SHEETS = {"describe": "D", "chair": "S", "clock": "C"}  # sheet -> id prefix
CODE_KEYS = {"describe": pt.DESC_CODE_KEYS, "chair": pt.CHAIR_CODE_KEYS, "clock": pt.CLOCK_CODE_KEYS}


def raw(key: str, task: str, temp: float) -> dict:
    return json.loads((D / "raw" / f"{pt.raw_name(key, task, temp)}.json").read_text())


def reuse():
    for m in pt.MODELS:
        if not m.scale_key:
            continue
        for temp in pt.TASKS["chair"].temps:
            src = ps.SCALE_DIR / "svg" / "raw" / f"{m.scale_key}_t{temp:.1f}.json"
            rec = json.loads(src.read_text())
            assert rec["prompt"] == pt.TASKS["chair"].prompt and rec["revision"] == m.revision, src
            rec.update(task="chair", arm=m.arm, reused_from=str(src.relative_to(ps.SCALE_DIR.parent)), picture_input=False)
            dst = D / "raw" / f"{pt.raw_name(m.key, 'chair', temp)}.json"
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(json.dumps(rec, indent=1))
            print("reused", src.name, "->", dst.name)


def render():
    out = {}
    (D / "png").mkdir(parents=True, exist_ok=True)
    for m in pt.MODELS:
        for t in pt.TASKS.values():
            if not t.svg:
                continue
            for temp in t.temps:
                name = pt.raw_name(m.key, t.key, temp)
                rec = raw(m.key, t.key, temp)
                assert len(rec["samples"]) == pt.N, name
                rows = []
                for s in rec["samples"]:
                    c = ps.classify(s["text"])
                    row = {"i": s["i"], "reason": c["reason"], "ink": c["ink"], "finished": s.get("finished"),
                           "n_tokens": s.get("n_tokens"),
                           "has_text_el": bool(c["svg"] and "<text" in c["svg"].lower())}
                    if c.get("error"):
                        row["error"] = c["error"]
                    if c["image"] is not None:
                        c["image"].save(D / "png" / f"{name}_{s['i']}.png")
                    rows.append(row)
                out[name] = {"model": m.key, "task": t.key, "temp": temp, "samples": rows}
                reasons = [r["reason"] for r in rows]
                print(f"{name}: {sum(r is None for r in reasons)}/{len(rows)} drew; failures "
                      f"{ {k: reasons.count(k) for k in set(reasons) if k} }", flush=True)
    (D / "render.json").write_text(json.dumps(out, indent=1))


# ---------- blind sheets ----------

def items_for(task: str) -> list:
    return [(m.key, task, pt.PRIMARY_TEMP, i) for m in pt.MODELS for i in range(pt.N)]


def font(size: int):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def contact(ids: dict, rend: dict, path: Path, cols: int = 6, cell: int = 256, pad: int = 8, head: int = 30):
    """The drawings as the coder sees them: each full 256 x 256 render on white, its anonymous id above it."""
    n = len(ids)
    rows = -(-n // cols)
    W, H = cols * (cell + pad) + pad, rows * (cell + head + pad) + pad
    sheet = Image.new("RGB", (W, H), "white")
    dr, f = ImageDraw.Draw(sheet), font(20)
    for k, (sid, (key, task, temp, i)) in enumerate(ids.items()):
        x, y = pad + (k % cols) * (cell + pad), pad + (k // cols) * (cell + head + pad)
        dr.text((x, y + 4), sid, fill="black", font=f)
        reason = rend[pt.raw_name(key, task, temp)]["samples"][i]["reason"]
        png = D / "png" / f"{pt.raw_name(key, task, temp)}_{i}.png"
        box = (x, y + head, x + cell - 1, y + head + cell - 1)
        if reason is None or (reason in ("blank", "flooded") and png.exists()):
            sheet.paste(Image.open(png).convert("RGB").resize((cell, cell)), (x, y + head))
        if reason is not None:
            dr.text((x + 8, y + head + cell // 2 - 10), f"FAILED: {ps.FAILURE_LABELS[reason]}", fill="red", font=f)
        dr.rectangle(box, outline=(170, 170, 170))
    sheet.save(path)


def sheets():
    rend = json.loads((D / "render.json").read_text())
    (D / "sheets").mkdir(parents=True, exist_ok=True)
    (D / "codes").mkdir(parents=True, exist_ok=True)
    for sheet, prefix in SHEETS.items():
        ids = pt.sheet_ids(pt.blind_order(items_for(sheet), sheet), prefix)
        (D / "codes" / f"key_{sheet}.json").write_text(json.dumps({k: list(v) for k, v in ids.items()}, indent=1))
        if sheet == "describe":
            lines = [f"# Descriptions sheet ({len(ids)} answers, blind order)\n",
                     "Code each: seat, legs, back (1 if mentioned, also as a plain paraphrase; else 0).\n"]
            for sid, (key, task, temp, i) in ids.items():
                text = raw(key, task, temp)["samples"][i]["text"]
                lines.append(f"## {sid}\n\n{text}\n")
            (D / "sheets" / "describe.md").write_text("\n".join(lines))
        else:
            items = list(ids.items())
            for part in range(0, len(items), 24):
                contact(dict(items[part:part + 24]), rend, D / "sheets" / f"{sheet}_{part // 24 + 1}.png")
        print(f"{sheet}: {len(ids)} items")


def load_codes(sheet: str) -> dict:
    return json.loads((D / "codes" / f"codes_{sheet}.json").read_text())


def hash_codes():
    lines = ["# SHA-256 of the by-eye codes (canonical JSON: sorted keys, no spaces), written before any automatic",
             "# scoring (docs/plato_cave_twins_plan.md). Files: PlatosChair/cave_twins/codes/codes_<sheet>.json"]
    for sheet in SHEETS:
        key = json.loads((D / "codes" / f"key_{sheet}.json").read_text())
        codes = load_codes(sheet)
        errs = pt.validate_codes(codes, list(key), CODE_KEYS[sheet], sheet)
        if errs:
            raise SystemExit("\n".join(errs))
        h = pt.codes_hash(codes)
        lines.append(f"{h}  codes_{sheet}.json  ({len(codes)} items)")
        print(sheet, h)
        notes = D / "codes" / f"notes_{sheet}.json"
        if notes.exists():  # the coder's notes on borderline items, hashed with the codes
            lines.append(f"{pt.codes_hash(json.loads(notes.read_text()))}  notes_{sheet}.json")
    HASH_FILE.write_text("\n".join(lines) + "\n")
    print("wrote", HASH_FILE)


def check_hashes():
    """The codes must still be the ones whose hash was committed."""
    want = {}
    for line in HASH_FILE.read_text().splitlines():
        if line and not line.startswith("#"):
            h, name = line.split()[:2]
            want[name] = h
    for sheet in SHEETS:
        got = pt.codes_hash(load_codes(sheet))
        if want.get(f"codes_{sheet}.json") != got:
            raise SystemExit(f"codes_{sheet}.json changed since its hash was recorded")


# ---------- automatic measures (after the hash) ----------

def rendered(rend: dict):
    for name, v in rend.items():
        ok = [s["i"] for s in v["samples"] if s["reason"] is None]
        yield name, ok


def read():
    check_hashes()
    import importlib.util

    from metalesionlab.plato import ink_crop

    spec = importlib.util.spec_from_file_location("plato_scale_reader", ROOT / "scripts" / "plato_scale_reader.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rend = json.loads((D / "render.json").read_text())
    rd = mod.Reader()
    res = {"model": mod.MODEL, "template": mod.TEMPLATE, "labels": {}}
    for name, ok in rendered(rend):
        imgs = [ink_crop(Image.open(D / "png" / f"{name}_{i}.png").convert("RGB")) for i in ok]
        labels = rd(imgs) if imgs else []
        res["labels"][name] = dict(zip(map(str, ok), labels))
        print(name, {lb: labels.count(lb) for lb in sorted(set(labels))}, flush=True)
    (D / "reader.json").write_text(json.dumps(res, indent=1))


def embed():
    check_hashes()
    from metalesionlab.plato import DINO_MODEL, Embedder, ink_crop

    rend = json.loads((D / "render.json").read_text())
    (D / "emb").mkdir(exist_ok=True)
    emb = None
    for name, ok in rendered(rend):
        crops = [ink_crop(Image.open(D / "png" / f"{name}_{i}.png").convert("RGB")) for i in ok]
        if crops:
            emb = emb or Embedder(DINO_MODEL)
            vecs = emb(crops)
        else:
            vecs = {"cls": np.zeros((0, 768)), "patch_mean": np.zeros((0, 768))}
        np.savez(D / "emb" / f"{name}.npz", cls=vecs["cls"].astype(np.float32),
                 patch_mean=vecs["patch_mean"].astype(np.float32), idx=np.array(ok, int), model=DINO_MODEL)
        print(name, len(ok), "embedded", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["reuse", "render", "sheets", "seal", "read", "embed"])
    args = ap.parse_args()
    {"reuse": reuse, "render": render, "sheets": sheets, "seal": hash_codes, "read": read, "embed": embed}[args.cmd]()


if __name__ == "__main__":
    main()

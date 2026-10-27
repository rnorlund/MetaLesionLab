"""Draw a chair, uploads: does a photo of a drawing on paper score like the same drawing on the pad, and
does the validity check tell line drawings on paper from photos of things and scenes? No API calls.

1. Paper photos. People's Quick, Draw! drawings, redrawn as pen on paper and "photographed": pen width,
   ink colour, hand wobble, paper tint and texture, uneven light, a vignette, rotation, blur, sensor noise,
   JPEG, and in a third of them a wooden table around the sheet. Each goes through the upload path
   (draw.prepare_upload: flatten_paper, ink_crop, DINOv2) and the same strokes through the pad path
   (draw.render); we compare the two scores.
2. The validity check (draw.paper_stats, draw.upload_problem) on pictures that should pass (the paper
   photos, Muse Image's doodles, children's tablet drawings, line-art pictures) and pictures that should
   not (photos of clocks by Muse Image and SDXL, photo crops of a temple and a flower in colour and gray,
   colour illustrations, noise) and blank paper.

Reads $PLATO_DIR and the app's line-art sets in runs/ when they exist; writes
$PLATO_DIR/draw_upload_validation.json.

    python scripts/draw_validate_uploads.py [--per-concept 10]
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from metalesionlab import draw  # noqa: E402
from metalesionlab.plato import PLATO_DIR  # noqa: E402

PLATO_ROOT = PLATO_DIR.parent
RUNS = REPO / "runs" if (REPO / "runs" / "sets").is_dir() else Path("/Users/super/Documents/Meta_Hacking_Challenge/MetaLesionLab/runs")


# ---------- photo-like pictures of a drawing on paper ----------

def _blur_noise(rng, h, w, cell, amp):
    small = rng.normal(size=(max(2, h // cell), max(2, w // cell)))
    img = Image.fromarray(((small - small.min()) / (np.ptp(small) + 1e-9) * 255).astype(np.uint8))
    return (np.asarray(img.resize((w, h), Image.BICUBIC), dtype=np.float32) / 255 - 0.5) * 2 * amp


def paper_photo(drawing, rng, size=(1280, 960), table=False) -> Image.Image:
    """A Quick, Draw! drawing (strokes 0-255) as a pen drawing on paper, photographed; at most 1024 px,
    as the browser sends it."""
    W, H = size
    S = 2
    pw, ph = (int(W * 0.78), int(H * 0.86)) if table else (W, H)
    mask = Image.new("L", (pw * S, ph * S), 0)
    d = ImageDraw.Draw(mask)
    xs = [x for s in drawing for x in s[0]] or [0]  # no strokes: blank paper
    ys = [y for s in drawing for y in s[1]] or [0]
    ext = rng.uniform(0.45, 0.75) * min(pw, ph) * S
    k = ext / max(max(xs) - min(xs), max(ys) - min(ys), 1)
    ox = (pw * S - (max(xs) - min(xs)) * k) / 2 + rng.uniform(-0.06, 0.06) * pw * S - min(xs) * k
    oy = (ph * S - (max(ys) - min(ys)) * k) / 2 + rng.uniform(-0.06, 0.06) * ph * S - min(ys) * k
    width = int(round(rng.uniform(3, 7) * S))
    for sx, sy in drawing:
        pts = [(ox + x * k + rng.normal(0, 0.8 * S), oy + y * k + rng.normal(0, 0.8 * S)) for x, y in zip(sx, sy)]
        dense = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / (12 * S)))
            dense += [(x0 + (x1 - x0) * t / n + rng.normal(0, 0.4 * S), y0 + (y1 - y0) * t / n + rng.normal(0, 0.4 * S))
                      for t in range(n)]
        dense.append(pts[-1])
        dense = dense * 2 if len(dense) == 1 else dense
        d.line(dense, fill=255, width=width, joint="curve")
        for x, y in (dense[0], dense[-1]):
            d.ellipse((x - width / 2, y - width / 2, x + width / 2, y + width / 2), fill=255)
    m = np.asarray(mask.resize((pw, ph), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32) / 255
    base = rng.uniform(215, 248)
    tint = np.array([rng.uniform(0, 7), rng.uniform(-2, 3), rng.uniform(-9, 0)], dtype=np.float32)
    paper = np.ones((ph, pw, 3), dtype=np.float32) * (base + tint)
    paper += (_blur_noise(rng, ph, pw, 40, 4) + rng.normal(0, 2.0, size=(ph, pw)))[..., None]
    ink = np.array([45, 50, 95] if rng.random() < 0.4 else [35, 35, 40], dtype=np.float32) + rng.uniform(-10, 15)
    alpha = rng.uniform(0.8, 0.95)
    pic = Image.fromarray(np.clip(paper * (1 - m[..., None] * alpha) + ink * (m[..., None] * alpha), 0, 255).astype(np.uint8))
    angle = rng.uniform(-8, 8)
    if table:
        pic = pic.convert("RGBA").rotate(angle, resample=Image.BICUBIC, expand=True)
        wood = np.ones((H, W, 3), dtype=np.float32) * np.array([120, 85, 55], dtype=np.float32)
        wood += (_blur_noise(rng, H, W, 25, 18) + rng.normal(0, 4, size=(H, W)))[..., None]
        bg = Image.fromarray(np.clip(wood, 0, 255).astype(np.uint8)).convert("RGBA")
        bg.alpha_composite(pic, ((W - pic.width) // 2, (H - pic.height) // 2))
        pic = bg.convert("RGB")
    else:
        pic = pic.rotate(angle, resample=Image.BICUBIC, fillcolor=tuple(int(v) for v in base + tint))
    a = np.asarray(pic, dtype=np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    lo, th = rng.uniform(0.72, 0.95), rng.uniform(0, 2 * math.pi)
    shade = lo + (1 - lo) * np.clip(np.cos(th) * (xx / W - 0.5) + np.sin(th) * (yy / H - 0.5) + 0.5, 0, 1)
    vignette = 1 - 0.18 * (((xx / W - 0.5) ** 2 + (yy / H - 0.5) ** 2) / 0.5)
    a = a * (shade * vignette)[..., None] + rng.normal(0, 2.5, size=a.shape)
    pic = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.0)))
    out = Image.open(io.BytesIO(jpeg(pic, int(rng.uniform(70, 92))))).convert("RGB")
    out.thumbnail((1024, 1024), Image.LANCZOS)
    return out


def jpeg(img: Image.Image, q: int = 90) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=q)
    return buf.getvalue()


def on_white(path: str) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    return Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im).convert("RGB")


# ---------- the checks ----------

def verdict(embed, ref, img: Image.Image, key: str = "chair"):
    """(problem or None, stats, score or None) for one picture sent as the browser sends it."""
    try:
        pic, stats = draw.prepare_upload(jpeg(img, 90))
    except draw.DrawingError as e:
        return str(e), None, None
    s = ref.score(key, embed([pic])[0])
    stats["d_doodle"] = s["d_doodle"]
    return draw.upload_problem(stats), stats, s


def validity_sets(rng) -> dict[str, tuple[bool | None, list[Image.Image]]]:
    rand = random.Random(0)
    pick = lambda files, n: rand.sample(files, min(n, len(files)))  # noqa: E731
    sets: dict = {}
    pp = []
    for key in ["chair", "umbrella", "bicycle", "house", "cat", "tree", "face", "sailboat", "cup", "book"]:
        recs = [json.loads(x) for x in open(PLATO_DIR / "human" / key / "strokes.ndjson")]
        pp += [paper_photo(recs[150 + i]["drawing"], rng, table=(i % 3 == 2)) for i in range(6)]
    sets["paper photos"] = (True, pp)
    sets["Muse Image doodles"] = (True, [Image.open(f).convert("RGB") for f in pick(glob.glob(str(PLATO_DIR / "ai/doodle/*/*.png")), 60)])
    kids = glob.glob(str(PLATO_ROOT / "lifespan/kiddraw_raw/drawings/stringent_cleaned_dataset/*.png"))
    sets["children's tablet drawings"] = (True, [on_white(f) for f in pick(kids, 60)])
    sets["line-art pictures"] = (True, [Image.open(f).convert("RGB") for f in pick(glob.glob(str(RUNS / "sets/demo_*/candidates/*.png")), 40)])
    sets["clock photos (Muse Image, SDXL)"] = (False, [Image.open(f).convert("RGB") for f in sorted(glob.glob(str(PLATO_ROOT / "forms/clock/*/photo/*/*.png")))])
    nat = []
    try:
        from sklearn.datasets import load_sample_image
        for n in ("china.jpg", "flower.jpg"):
            im = Image.fromarray(load_sample_image(n))
            nat += [im, im.convert("L").convert("RGB")]
            for _ in range(6):
                w, h = im.size
                s = rng.uniform(0.35, 0.8)
                x0, y0 = rng.uniform(0, w * (1 - s)), rng.uniform(0, h * (1 - s))
                crop = im.crop((int(x0), int(y0), int(x0 + w * s), int(y0 + h * s)))
                nat += [crop, crop.convert("L").convert("RGB")]
    except ImportError:
        pass
    sets["photo crops, colour and gray"] = (False, nat)
    web = REPO / "metalesionlab/web/static/img"
    sets["colour illustrations"] = (False, [Image.open(f).convert("RGB") for f in sorted(glob.glob(str(web / "ill-*.webp")))] +
                                    [Image.open(f).convert("RGB") for f in glob.glob(str(RUNS / "scenes/*.png"))])
    sets["noise"] = (False, [Image.fromarray(rng.integers(0, 255, size=(400, 600, 3)).astype(np.uint8))
                             .filter(ImageFilter.GaussianBlur(rng.uniform(0, 3))) for _ in range(10)])
    sets["blank paper"] = (None, [paper_photo([], rng) for _ in range(5)])
    return sets


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-concept", type=int, default=10)
    args = ap.parse_args()
    rng = np.random.default_rng(0)
    ref = draw.Reference.load()
    embed = draw.load_embedder()
    out: dict = {"backend": embed.backend, "validity": {}, "agreement": {}}

    print("Validity check (share accepted as a drawing on paper):")
    for name, (should, imgs) in validity_sets(rng).items():
        if not imgs:
            continue
        verdicts = [verdict(embed, ref, im)[0] for im in imgs]
        accepted = sum(v is None for v in verdicts)
        blank = sum(v == draw.NO_INK for v in verdicts)
        edges = sum(v == draw.EDGES for v in verdicts)
        out["validity"][name] = {"n": len(imgs), "accepted": accepted, "no_ink": blank, "edges": edges,
                                 "should_pass": should}
        print(f"  {name:32s} n={len(imgs):3d}  accepted {accepted:3d} ({100 * accepted / len(imgs):.0f}%)"
              + (f", no drawing found {blank}" if blank else "") + (f", paper edge in view {edges}" if edges else ""),
              flush=True)

    print("Same drawing, photo on paper vs. pad:")
    rows = []
    for key in ref.entries:
        recs = [json.loads(x) for x in open(PLATO_DIR / "human" / key / "strokes.ndjson")]
        for i in range(args.per_concept):
            strokes = recs[100 + i]["drawing"]
            pad = ref.score(key, embed([draw.render(strokes)])[0])
            for table in (False, True):
                problem, stats, up = verdict(embed, ref, paper_photo(strokes, rng, table=table), key)
                if up is None:
                    rows.append({"key": key, "table": table, "rejected": problem})
                    continue
                rows.append({"key": key, "table": table, "rejected": problem, "pad": pad["originality"],
                             "upload": up["originality"], "d_pad": pad["d_human"], "d_upload": up["d_human"],
                             "pad_muse": pad["people_closer_to_muse"], "upload_muse": up["people_closer_to_muse"]})
    from scipy.stats import spearmanr

    for table in (False, True):
        r = [x for x in rows if x["table"] == table and "pad" in x]
        n_all = sum(x["table"] == table for x in rows)
        pad, up = np.array([x["pad"] for x in r]), np.array([x["upload"] for x in r])
        dp, du = np.array([x["d_pad"] for x in r]), np.array([x["d_upload"] for x in r])
        rejected = [x["rejected"] for x in rows if x["table"] == table and x["rejected"]]
        if len(r) < 3:
            res = {"n": n_all, "scored": len(r), "rejected": len(rejected),
                   "edge_rejections": sum(m == draw.EDGES for m in rejected)}
            out["agreement"]["with table" if table else "paper fills the photo"] = res
            print(f"  {'with a table around the paper' if table else 'paper fills the photo':30s} {json.dumps(res)}")
            continue
        res = {"n": n_all, "scored": len(r), "rejected": len(rejected),
               "edge_rejections": sum(m == draw.EDGES for m in rejected),
               "originality_spearman": round(float(spearmanr(pad, up).statistic), 3),
               "originality_mean_abs_diff": round(float(np.abs(pad - up).mean()), 1),
               "originality_median_abs_diff": round(float(np.median(np.abs(pad - up))), 1),
               "within_15_points": round(float(np.mean(np.abs(pad - up) <= 15)), 3),
               "mean_shift_upload_minus_pad": round(float((up - pad).mean()), 1),
               "distance_spearman": round(float(spearmanr(dp, du).statistic), 3),
               "muse_mean_abs_diff": round(float(np.abs(np.array([x["pad_muse"] for x in r]) - np.array([x["upload_muse"] for x in r])).mean()), 1)}
        out["agreement"]["with table" if table else "paper fills the photo"] = res
        print(f"  {'with a table around the paper' if table else 'paper fills the photo':30s} {json.dumps(res)}", flush=True)
    out["agreement_rows"] = rows
    path = PLATO_DIR / "draw_upload_validation.json"
    path.write_text(json.dumps(out, indent=1))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()

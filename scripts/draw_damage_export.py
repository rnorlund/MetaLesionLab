"""What damage does to an AI's chair (/draw): contact sheets for choosing seeds, and the page's thumbnails.

  sheet  --run DIR [--out PNG]           every intact candidate: one row per thing, one column per seed
  levels --run DIR [--out PNG]           every candidate dose for the candidate seeds of each thing
  export --run DIR [--sheet PNG]         the chosen seed and levels -> static/img/draw_damage/ (small WebPs)
                                         plus draw_damage.json next to them, and a contact sheet of the strips

DIR is a copy of scripts/draw_damage_sdxl.py's output (<condition>/<key>/s<i>.png), kept outside the
repository (PlatosChair/draw_damage/). The strip shows one fixed seed per thing: the intact picture, then
text-encoder noise ("the part that handles words") and UNet noise ("the part that draws") at five
increasing doses each. Doses are the damage experiment's noise doses (docs/plato_damage.md, the
/plato/damage slider: text x 0.25, 0.5, 0.75, 1 and UNet x 0.75, 0.9, 1, 1.1) plus one step between them
(text x 0.625, where most things first turn into something else; UNet x 0.825), and the noise uses its
unit statistics.

The strip is about the model only. Nothing here measures, embeds or scores the pictures, and the page
never compares a visitor's drawing with them.

SDXL: Stability AI, stabilityai/stable-diffusion-xl-base-1.0, CreativeML OpenRAIL++-M.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from draw_damage_sdxl import MODEL, THINGS, prompt, seed_for  # noqa: E402
from metalesionlab.plato import BY_KEY as PLATO, STYLES  # noqa: E402
from metalesionlab.plato_damage import NEGATIVE  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
IMG = REPO / "metalesionlab" / "web" / "static" / "img" / "draw_damage"
URL = "/static/img/draw_damage/"
RUN = Path("/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair/draw_damage/run")
BUDGET = 1_500_000  # bytes, every file in IMG together
SIDE, QUALITY = 176, 70

ROWS = {
    "language": {"family": "text-noise", "site": "text", "part": "the part that handles words",
                 "detail": "both text encoders (CLIP ViT-L and OpenCLIP bigG)",
                 "doses": [0.25, 0.5, 0.625, 0.75, 1.0]},
    "drawing": {"family": "unet-noise", "site": "unet", "part": "the part that draws",
                "detail": "the UNet's 70 transformer blocks",
                "doses": [0.75, 0.825, 0.9, 1.0, 1.1]},
}
# Candidate doses generated for choosing the five above (the experiment's four noise doses per family plus
# in-between and outside steps).
CANDIDATES = {"text-noise": [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0],
              "unet-noise": [0.5, 0.6, 0.75, 0.825, 0.9, 1.0, 1.05, 1.1]}
# The picture index (seed_for(key, i)) whose intact doodle is clean and recognizable and whose rows change visibly,
# chosen by eye from 12 intact candidates per thing and 3 candidates' dose sheets (PlatosChair/draw_damage/figures/).
PICKS = {"chair": 7, "umbrella": 1, "bicycle": 10, "house": 0, "cat": 6, "tree": 3, "face": 2, "sailboat": 8,
         "cup": 5, "book": 8}


def cond(family: str, dose: float) -> str:
    return f"{family}@{dose:g}"


def label(key: str) -> str:
    return PLATO[key].label


def font(size: int):
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def tile(path: Path, side: int) -> Image.Image:
    if not path.exists():
        im = Image.new("RGB", (side, side), (235, 235, 235))
        ImageDraw.Draw(im).text((8, side // 2 - 8), "missing", fill=(150, 0, 0), font=font(14))
        return im
    im = Image.open(path).convert("RGB")
    im.thumbnail((side, side), Image.LANCZOS)
    return im


def grid(rows: list[tuple[str, list[tuple[str, Path]]]], side: int, out: Path, title: str = "") -> Path:
    """A labelled contact sheet: one row per (row label, [(cell caption, picture)])."""
    lw, cap, gap, top = 150, 18, 6, 40 if title else 8
    cols = max(len(cells) for _, cells in rows)
    W = lw + cols * (side + gap) + gap
    H = top + len(rows) * (side + cap + gap) + gap
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((gap, 10), title, fill="black", font=font(20))
    for r, (name, cells) in enumerate(rows):
        y = top + r * (side + cap + gap)
        d.text((gap, y + side // 2 - 8), name, fill="black", font=font(15))
        for c, (caption, path) in enumerate(cells):
            x = lw + c * (side + gap)
            sheet.paste(tile(path, side), (x, y))
            d.rectangle([x, y, x + side - 1, y + side - 1], outline=(200, 200, 200))
            d.text((x + 2, y + side + 2), caption, fill=(80, 80, 80), font=font(12))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"wrote {out} ({W} x {H})")
    return out


def cmd_sheet(args):
    rows = []
    for key in THINGS:
        seeds = sorted(int(p.stem[1:]) for p in (args.run / "intact" / key).glob("s*.png"))
        rows.append((label(key), [(f"s{i}", args.run / "intact" / key / f"s{i}.png") for i in seeds]))
    grid(rows, 150, args.out or args.run.parent / "figures" / "intact_candidates.png", "SDXL intact doodles, seed index")


def cmd_levels(args):
    rows = []
    keys = args.keys or THINGS
    for key in keys:
        seeds = sorted({int(p.stem[1:]) for f in CANDIDATES for d in CANDIDATES[f]
                        for p in (args.run / cond(f, d) / key).glob("s*.png")})
        for i in seeds:
            for fam, doses in CANDIDATES.items():
                cells = [("intact", args.run / "intact" / key / f"s{i}.png")]
                cells += [(f"x{d:g}", args.run / cond(fam, d) / key / f"s{i}.png") for d in doses]
                rows.append((f"{label(key)} s{i} {fam.split('-')[0]}", cells))
    grid(rows, 120, args.out or args.run.parent / "figures" / "level_candidates.png", "Candidate doses")


def save_webp(src: Path, out: Path, side: int, quality: int) -> int:
    im = Image.open(src).convert("RGB")
    im.thumbnail((side, side), Image.LANCZOS)
    im.save(out, "WEBP", quality=quality, method=6)
    return out.stat().st_size


def cmd_export(args):
    IMG.mkdir(parents=True, exist_ok=True)
    for old in IMG.glob("*.webp"):
        old.unlink()
    quality = args.quality
    while True:
        things, total = [], 0
        for key in THINGS:
            i = PICKS[key]
            src = lambda c: args.run / c / key / f"s{i}.png"  # noqa: E731
            missing = [c for c in ["intact"] + [cond(r["family"], d) for r in ROWS.values() for d in r["doses"]]
                       if not src(c).exists()]
            if missing:
                raise SystemExit(f"{key} s{i}: missing {missing}")
            entry = {"key": key, "label": label(key), "prompt": prompt(key), "seed": seed_for(key, i)}
            total += save_webp(src("intact"), IMG / f"{key}_intact.webp", args.side, quality)
            entry["intact"] = URL + f"{key}_intact.webp"
            for row, r in ROWS.items():
                entry[row] = []
                for n, d in enumerate(r["doses"], 1):
                    name = f"{key}_{row}_{n}.webp"
                    total += save_webp(src(cond(r["family"], d)), IMG / name, args.side, quality)
                    entry[row].append(URL + name)
            things.append(entry)
        if total <= BUDGET * 0.9 or quality <= 40:
            break
        quality -= 6
        print(f"{total} bytes is over budget; quality {quality}")
    data = {
        "about": ("What damage does to an AI's drawing: Stable Diffusion XL, an open image model, asked for each "
                  "thing with one fixed seed, intact and with noise added to its text encoders (the part that "
                  "handles words) or its UNet (the part that draws) at five increasing doses. About the model "
                  "only: never compared with a visitor's drawing."),
        "model": MODEL,
        "credit": "Stable Diffusion XL base 1.0 (Stability AI), CreativeML OpenRAIL++-M",
        "license": "CreativeML OpenRAIL++-M",
        "prompt_template": STYLES["doodle"],
        "settings": {"size": 768, "steps": 25, "guidance_scale": 5.0, "negative": NEGATIVE, "saved_side": 512,
                     "thumb_side": args.side, "webp_quality": quality},
        "lesions": ("Gaussian noise on every neuron of the part, sd = dose x the neuron's sd over 16 reference doodle "
                    "prompts (the damage experiment's unit statistics), the same noise for every thing; "
                    "metalesionlab/sdxl_lesions.py, plato_damage.FAMILIES."),
        "rows": {row: {**r, "conditions": [cond(r["family"], d) for d in r["doses"]]} for row, r in ROWS.items()},
        "more": "/plato/damage",
        "total_bytes": total,
        "things": things,
    }
    (IMG / "draw_damage.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(things)} strips, {total / 1e6:.2f} MB of WebP at {args.side} px, quality {quality}")
    rows = []
    for t in things:
        cells = [("intact", IMG / Path(t["intact"]).name)]
        rows.append((f"{t['label']} words", cells + [(f"x{d:g}", IMG / Path(p).name)
                                                     for d, p in zip(ROWS["language"]["doses"], t["language"])]))
        rows.append((f"{t['label']} drawing", cells + [(f"x{d:g}", IMG / Path(p).name)
                                                       for d, p in zip(ROWS["drawing"]["doses"], t["drawing"])]))
    grid(rows, args.side, args.sheet or args.run.parent / "figures" / "strips.png",
         "What damage does to an AI's drawing (SDXL): words part (text noise) and drawing part (UNet noise)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("sheet", cmd_sheet), ("levels", cmd_levels), ("export", cmd_export)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--run", type=Path, default=RUN)
        if name in ("sheet", "levels"):
            p.add_argument("--out", type=Path)
        if name == "levels":
            p.add_argument("--keys", nargs="*", choices=THINGS)
        if name == "export":
            p.add_argument("--side", type=int, default=SIDE)
            p.add_argument("--quality", type=int, default=QUALITY)
            p.add_argument("--sheet", type=Path)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()

"""Plato's Chair for the web app: compact statistics and the few figures the /plato page shows.

Reads the Plato's Chair data folder, which lives outside this repository (default
/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair, or $PLATO_ROOT), and writes:
  metalesionlab/web/data/plato.json      statistics only (metalesionlab/plato_web.py)
  metalesionlab/web/static/img/plato/    13-15 compressed WebP figures, each under 300 KB

Figures that show people's drawings keep their Google Quick, Draw! (CC BY 4.0) credit inside the
image. The two-panel hero grids are split into an AI half and a people half, and each half gets a
credit line. No single drawing is ever copied into the repository.

Usage: python scripts/plato_web_export.py [--root PATH]   (no network, no API calls)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from metalesionlab import plato_web  # noqa: E402

DEFAULT_ROOT = Path(os.environ.get("PLATO_ROOT", "/Users/super/Documents/Meta_Hacking_Challenge/PlatosChair"))
WEB = REPO / "metalesionlab" / "web"
IMG = WEB / "static" / "img" / "plato"
MAX_BYTES = 300 * 1024
BG = (252, 252, 251)
FONTS = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
# Hero grids: core figure -> page key. Halves: AI x 18-873, people x 926-1781 (both 856 px wide).
GRIDS = {"grid_chair.png": "chair", "grid_sailboat.png": "boat", "grid_face.png": "face", "grid_yoga.png": "person"}
HALVES = {"ai": (18, 873), "people": (926, 1781)}
CREDITS = {"ai": "Drawings: Meta Muse Image 1.0",
           "people": "Drawings by people: Google Quick, Draw! dataset (Google Creative Lab), CC BY 4.0"}
COPIES = {  # (source relative to the root, output name, width)
    "languages/figures/grid_ai_chair.png": ("lang_chair_ai.webp", 1200),
    "languages/figures/grid_ai_hat.png": ("lang_hat_ai.webp", 1200),
    "languages/figures/average_chair.png": ("lang_chair_average.webp", 1200),
    "languages/figures/average_hat.png": ("lang_hat_average.webp", 1200),
    "inside_glimmer/figures/spread_by_layer.png": ("spread_by_layer.webp", 1200),
    "core/figures/grid3_chair.png": ("sdxl_chair.webp", 1500),  # Muse Image, SDXL and people; optional
    "core/figures/variety_chair.png": ("variety_chair.webp", 1600),  # four prompts and people; optional
}
OPTIONAL = {"core/figures/grid3_chair.png", "core/figures/variety_chair.png"}


def font(size: int):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def save_webp(img: Image.Image, out: Path, quality: int = 82) -> int:
    """Save under the size limit, lowering quality (then width) until it fits."""
    img = img.convert("RGB")
    while True:
        img.save(out, "WEBP", quality=quality, method=6)
        size = out.stat().st_size
        if size <= MAX_BYTES:
            return size
        if quality > 55:
            quality -= 8
        else:
            img = img.resize((int(img.width * 0.85), int(img.height * 0.85)), Image.LANCZOS)


def ink_rows(a) -> tuple[int, int]:
    """First and last row of the white picture cells (the grid without its title and footer)."""
    import numpy as np
    white = (np.asarray(a.convert("RGB")).min(axis=2) >= 254).mean(axis=1) > 0.3
    rows = np.where(white)[0]
    return int(rows[0]), int(rows[-1])


def split_grid(src: Path, key: str) -> list[tuple[str, int]]:
    im = Image.open(src).convert("RGB")
    top, bottom = ink_rows(im)
    out = []
    for half, (x0, x1) in HALVES.items():
        pad = 14
        crop = im.crop((x0 - pad, top - pad, x1 + pad + 1, bottom + pad + 1))
        f = font(19)
        strip = 40
        canvas = Image.new("RGB", (crop.width, crop.height + strip), BG)
        canvas.paste(crop, (0, 0))
        ImageDraw.Draw(canvas).text((pad, crop.height + 8), CREDITS[half], fill=(95, 99, 107), font=f)
        name = f"grid_{key}_{half}.webp"
        out.append((name, save_webp(canvas, IMG / name)))
    return out


def copy_figure(src: Path, name: str, width: int) -> int:
    im = Image.open(src).convert("RGBA")
    flat = Image.new("RGB", im.size, BG)
    flat.paste(im, mask=im.split()[-1])
    if flat.width > width:
        flat = flat.resize((width, round(flat.height * width / flat.width)), Image.LANCZOS)
    return save_webp(flat, IMG / name)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()
    root = args.root
    data = plato_web.build(root / "core", REPO / "public_data" / "plato_languages.json", root / "inside_glimmer")
    # Optional figures the page shows only when they were exported.
    data["figures"] = {name: f"{name}.webp" for name, src in (("sdxl_chair", "grid3_chair"), ("variety_chair", "variety_chair"))
                       if (root / f"core/figures/{src}.png").exists()}
    out = WEB / "data" / "plato.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"wrote {out.relative_to(REPO)} ({out.stat().st_size / 1024:.0f} KB); "
          f"SDXL: {'%d concepts' % data['sdxl']['n_concepts'] if data['sdxl'] else 'not yet'}")
    if args.no_figures:
        return
    IMG.mkdir(parents=True, exist_ok=True)
    for src, key in GRIDS.items():
        for name, size in split_grid(root / "core" / "figures" / src, key):
            print(f"  {name}: {size / 1024:.0f} KB")
    for src, (name, width) in COPIES.items():
        if src in OPTIONAL and not (root / src).exists():
            continue
        print(f"  {name}: {copy_figure(root / src, name, width) / 1024:.0f} KB")


if __name__ == "__main__":
    main()

"""Dense hero rows -> the site (display upgrade; docs/plato_damage.md, "Denser rows").

  python scripts/plato_damage_dense_web.py --src ~/.../PlatosChair/damage_dense/out [--sheets]

Reads <src>/<row>/s_0..9.png and meta.json (scripts/plato_damage_dense.py), writes small WebP tiles to
metalesionlab/web/static/img/plato_damage/dense/<row>_<level>.webp, and rewrites the hero carousel's slides (the JSON
and the no-JS first slide) in pages/damaged.html and pages/plato_damage.html: each row is undamaged plus 9 doses.
--sheets also writes a contact sheet per row to <src>/sheets/ for the look-by-eye check. No network."""
import argparse
import html
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

WEB = Path(__file__).resolve().parents[1] / "metalesionlab" / "web"
IMG = WEB / "static" / "img" / "plato_damage" / "dense"
URL = "/static/img/plato_damage/dense/"
ROWS = [  # (row, caption, subject for alt text, part damaged)
    ("rocking", "rocking chair → car", "A rocking chair", "words"),
    ("throne", "throne → bar", "A throne", "words"),
    ("god", "God → an ordinary person", "God", "words"),
    ("clock", "a clock losing its numbers", "A clock showing 8:45", "drawing"),
]


def dose_text(d: float) -> str:
    return f"noise × {d:g}"


def tiles(src: Path, row: str, subject: str, part: str) -> list[dict]:
    meta = json.loads((src / row / "meta.json").read_text())
    IMG.mkdir(parents=True, exist_ok=True)
    out = []
    for lvl, dose in enumerate(meta["doses"]):
        name = f"{row}_{lvl}.webp"
        im = Image.open(src / row / f"s_{lvl}.png").convert("RGB")
        im.thumbnail((360, 360), resample=3)
        im.save(IMG / name, "WEBP", quality=72, method=6)
        alt = (f"{subject} drawn by Stable Diffusion XL, undamaged" if lvl == 0 else
               f"{subject} with the {part} part damaged, step {lvl} of {len(meta['doses']) - 1}")
        out.append({"src": URL + name, "alt": alt, "label": "undamaged" if lvl == 0 else dose_text(dose)})
    return out


def static_html(slide: dict) -> str:
    pics = "".join(
        f'<figure class="hc-pic"><span class="hc-paper"><img src="{im["src"]}" alt="{html.escape(im["alt"])}" width="512" height="512" '
        f'decoding="async"></span><figcaption class="hc-lab">{html.escape(im["label"])}</figcaption></figure>' for im in slide["images"])
    return (f'<div class="hc-static"><div class="hc-strip" style="--n:{len(slide["images"])}">{pics}</div>'
            f'<p class="hc-cap"><a href="/plato/damage">{html.escape(slide["caption"])}</a></p></div>')


def rewrite(page: Path, slides: list[dict]) -> None:
    s = page.read_text()
    old = re.search(r'(data-hero-carousel[^>]*>\s*<script type="application/json">)(.*?)(</script>)', s, re.S)
    cfg = json.loads(old.group(2))
    for sl, new in zip(cfg["slides"], slides):
        sl["images"] = new["images"]
    s = s[:old.start(2)] + json.dumps(cfg, indent=1, ensure_ascii=False) + s[old.end(2):]
    s = re.sub(r'<div class="hc-static">.*?</p></div>', lambda m: static_html(cfg["slides"][0]), s, count=1, flags=re.S)
    page.write_text(s)


def sheet(src: Path, row: str) -> None:
    ims = [Image.open(src / row / f"s_{i}.png").convert("RGB").resize((256, 256)) for i in range(10)]
    meta = json.loads((src / row / "meta.json").read_text())
    sh = Image.new("RGB", (256 * 5, 276 * 2), "white")
    d = ImageDraw.Draw(sh)
    for i, im in enumerate(ims):
        x, y = (i % 5) * 256, (i // 5) * 276
        sh.paste(im, (x, y))
        d.text((x + 4, y + 258), f"{i}: {meta['doses'][i]:g}", fill="black")
    (src / "sheets").mkdir(exist_ok=True)
    sh.save(src / "sheets" / f"{row}.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--sheets", action="store_true")
    a = ap.parse_args()
    if a.sheets:
        for row, *_ in ROWS:
            sheet(a.src, row)
        return
    slides = []
    for row, cap, subject, part in ROWS:
        slides.append({"caption": cap, "images": tiles(a.src, row, subject, part)})
    for page in ("damaged.html", "plato_damage.html"):
        rewrite(WEB / "pages" / page, slides)
    print("tiles:", len(list(IMG.glob("*.webp"))), sum(f.stat().st_size for f in IMG.glob("*.webp")) // 1000, "KB")


if __name__ == "__main__":
    main()

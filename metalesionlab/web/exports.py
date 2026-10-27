"""Exports for a Test Studio set: a norms table (CSV), printable picture cards (PDF) and a ZIP."""
from __future__ import annotations

import csv
import io
import json
import os
import zipfile
from pathlib import Path

from PIL import Image

from metalesionlab.brand import BRAND

NORMS_COLUMNS = ["item", "word", "hint", "gloss", "alternates", "status", "image", "zipf", "phonemes",
                 "ambiguous", "other_meanings", "sam_objects", "sam_confidence", "sam_area", "spark_name",
                 "spark_code", "spark_agreement", "candidates", "lang", "style"]
# Card layouts: cards per page -> (columns, rows).
CARD_GRIDS = {1: (1, 1), 2: (1, 2), 3: (1, 3), 4: (2, 2), 6: (2, 3)}
UNICODE_FONTS = [
    os.environ.get("TOT_PDF_FONT", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]


def kept_candidate(item: dict) -> dict | None:
    return next((c for c in item.get("candidates", []) if c["file"] == item.get("image")), None)


def norms_rows(manifest: dict) -> list[dict]:
    rows = []
    for n, it in enumerate(manifest.get("items", []), 1):
        best = kept_candidate(it) or {}
        cands = it.get("candidates", [])
        rows.append({
            "item": n, "word": it["word"], "hint": it.get("hint", ""), "gloss": it.get("gloss", ""),
            "alternates": "; ".join(it.get("alternates", [])), "status": it.get("status", ""),
            "image": it.get("image") or "", "zipf": it.get("zipf"), "phonemes": it.get("phonemes"),
            "ambiguous": it.get("ambiguous", False), "other_meanings": "; ".join(it.get("other_meanings", [])),
            "sam_objects": best.get("sam_objects"), "sam_confidence": best.get("sam_confidence"),
            "sam_area": best.get("sam_area"), "spark_name": best.get("spark_name"),
            "spark_code": best.get("spark_code"),
            # Share of all drawn candidates that Muse Spark named correctly.
            "spark_agreement": round(sum(c.get("spark_ok", False) for c in cands) / len(cands), 2) if cands else None,
            "candidates": len(cands), "lang": it.get("lang", manifest.get("lang")),
            "style": it.get("style", manifest.get("style")),
        })
    return rows


def norms_csv(manifest: dict) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, NORMS_COLUMNS)
    writer.writeheader()
    writer.writerows(norms_rows(manifest))
    return buf.getvalue()


def _card_image(path: Path, side: int = 900) -> io.BytesIO:
    img = Image.open(path).convert("RGB")
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    buf.seek(0)
    return buf


def _unicode_font() -> str | None:
    return next((f for f in UNICODE_FONTS if f and Path(f).exists()), None)


def cards_pdf(manifest: dict, set_dir: Path, title: str, per_page: int = 4, show_word: bool = True,
              page_format: str = "letter", include_review: bool = False) -> bytes:
    """Printable picture cards, per_page to a page, each with its number and (optionally) the word."""
    from fpdf import FPDF

    cols, rows = CARD_GRIDS[per_page]
    items = [(n, it) for n, it in enumerate(manifest.get("items", []), 1)
             if it.get("image") and (it.get("status") == "kept" or (include_review and it.get("status") == "review"))]
    pdf = FPDF(format=page_format, unit="mm")
    pdf.set_auto_page_break(False)
    pdf.set_title(title)
    pdf.set_creator(BRAND)
    words = " ".join(it["word"] for _, it in items) + title
    family = "Helvetica"
    try:
        words.encode("latin-1")
    except UnicodeEncodeError:
        if font := _unicode_font():
            pdf.add_font("Unicode", "", font)
            family = "Unicode"
    margin, gap, label_h = 12.0, 6.0, (14.0 if show_word else 0.0)
    cell_w = (pdf.w - 2 * margin - (cols - 1) * gap) / cols
    cell_h = (pdf.h - 2 * margin - 8 - (rows - 1) * gap) / rows
    font_pt = 28 if per_page <= 2 else 22 if per_page <= 4 else 18

    if not items:
        pdf.add_page()
        pdf.set_font(family, size=14)
        pdf.text(margin, margin + 10, "No kept pictures in this set yet.")
    for k, (n, it) in enumerate(items):
        if k % per_page == 0:
            pdf.add_page()
            pdf.set_font(family, size=8)
            pdf.set_text_color(90, 90, 90)
            pdf.text(margin, pdf.h - 6, f"{title} · {BRAND} · pictures drawn with Muse Image")
        slot = k % per_page
        x = margin + (slot % cols) * (cell_w + gap)
        y = margin + (slot // cols) * (cell_h + gap)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, cell_w, cell_h, round_corners=True, corner_radius=3)
        side = min(cell_w, cell_h - label_h) - 10
        pdf.image(_card_image(set_dir / it["image"]), x=x + (cell_w - side) / 2, y=y + 5, w=side, h=side)
        pdf.set_text_color(90, 90, 90)
        pdf.set_font(family, size=9)
        pdf.text(x + 4, y + 7, str(n))
        if show_word:
            pdf.set_text_color(17, 24, 39)
            pdf.set_font(family, size=font_pt)
            word = it["word"]
            if family == "Helvetica":
                word = word.encode("latin-1", "replace").decode("latin-1")
            pdf.set_xy(x, y + cell_h - label_h - 2)
            pdf.cell(cell_w, label_h, word, align="C")
    return bytes(pdf.output())


def set_zip(manifest: dict, set_dir: Path, set_id: str) -> bytes:
    """manifest.json, norms.csv, the kept pictures (numbered) and every candidate."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{set_id}/manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        z.writestr(f"{set_id}/norms.csv", norms_csv(manifest))
        z.writestr(f"{set_id}/README.txt", (
            f"{BRAND} picture set '{set_id}' ({manifest.get('lang')}, {manifest.get('style')} style).\n"
            "pictures/   the kept picture for each item, numbered in test order\n"
            "candidates/ every drawn candidate; manifest.json has each one's checks\n"
            "norms.csv   word frequency (Zipf), length, SAM 3.1 checks and Muse Spark name agreement\n\n"
            "Pictures were drawn by Muse Image and checked with SAM 3.1 and Muse Spark.\n"
            "Research and teaching use only; this is not a diagnostic test.\n"))
        for n, it in enumerate(manifest.get("items", []), 1):
            if it.get("image") and (set_dir / it["image"]).exists():
                z.write(set_dir / it["image"], f"{set_id}/pictures/{n:02d}_{it['word']}{Path(it['image']).suffix}")
            for c in it.get("candidates", []):
                if (set_dir / c["file"]).exists():
                    z.write(set_dir / c["file"], f"{set_id}/{c['file']}")
    return buf.getvalue()

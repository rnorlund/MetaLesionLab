"""Build a checked picture-naming set and print a summary.

Usage: python scripts/build_test_set.py NAME LANG WORDS_FILE [--style line|color] [--candidates 2]
WORDS_FILE has one word per line; "banco: bench" pins an ambiguous word's meaning.
Output: runs/sets/NAME/ (manifest.json, candidates/, contact_sheet.png)
"""
import argparse
import time
from pathlib import Path

from PIL import Image, ImageDraw

from metalesionlab.meta_api import REPO_ROOT, spent
from metalesionlab.test_studio import build_set


def contact_sheet(manifest: dict, out_dir: Path, cell: int = 220) -> Path:
    """Every candidate in a grid, labeled with its checks, for a quick visual review."""
    rows = [(it, c) for it in manifest["items"] for c in it["candidates"]]
    cols = 6
    sheet = Image.new("RGB", (cols * cell, ((len(rows) + cols - 1) // cols) * (cell + 34)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (it, c) in enumerate(rows):
        x, y = (i % cols) * cell, (i // cols) * (cell + 34)
        img = Image.open(out_dir / c["file"]).convert("RGB")
        img.thumbnail((cell - 8, cell - 8))
        sheet.paste(img, (x + 4, y + 4))
        kept = "KEPT " if it["image"] == c["file"] else ""
        draw.text((x + 4, y + cell - 2), f"{kept}{it['word']} -> {c['spark_name']}", fill="black")
        draw.text((x + 4, y + cell + 12), f"SAM {c['sam_objects']} obj {c['sam_confidence']} area {c['sam_area']}",
                  fill="black" if c["sam_ok"] else "red")
    path = out_dir / "contact_sheet.png"
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("lang")
    ap.add_argument("words_file")
    ap.add_argument("--style", default="line")
    ap.add_argument("--candidates", type=int, default=2)
    args = ap.parse_args()

    out_dir = REPO_ROOT / "runs" / "sets" / args.name
    words = Path(args.words_file).read_text().splitlines()
    t0, cost0 = time.time(), spent()
    manifest = build_set(words, args.lang, out_dir, style=args.style, candidates=args.candidates)
    for it in manifest["items"]:
        flags = " AMBIGUOUS: " + ", ".join(it["other_meanings"]) if it["ambiguous"] else ""
        names = ", ".join(f"{c['spark_name']}({'ok' if c['sam_ok'] else 'sam'})" for c in it["candidates"])
        print(f"{it['status']:6s} {it['word']:12s} gloss={it['gloss']:12s} names: {names}{flags}")
    kept = sum(it["status"] == "kept" for it in manifest["items"])
    print(f"\n{kept}/{len(manifest['items'])} kept in {time.time() - t0:.0f}s for ${spent() - cost0:.2f}")
    print(f"contact sheet: {contact_sheet(manifest, out_dir)}")


if __name__ == "__main__":
    main()

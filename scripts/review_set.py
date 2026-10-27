"""Apply a visual review to a Test Studio set: keep, drop or redraw items, with reasons.

Test Studio's automatic checks (SAM 3.1, Muse Spark's name) choose a picture per word; a person
then looks at the contact sheet. The review file records each decision:

  {"set": "core100_en", "items": {
     "lemon":   {"action": "keep", "image": "candidates/lemon_1.png", "reason": "..."},
     "whistle": {"action": "replace", "from": "core100_fix", "image": "candidates/whistle_1.png", "reason": "..."},
     "saw":     {"action": "drop", "reason": "..."}}}

keep     use this candidate as the test picture (overrides the automatic choice)
replace  take the item's drawings from a redraw set (built by scripts/build_test_set.py); `image`
         names the test picture there, and its other drawing becomes the held-out one
drop     leave the item out of the test (status "dropped")

The automatic manifest is saved once as manifest_auto.json, so the review can be re-applied.
Also writes review_sheet.png: every test picture, for a last look.

Usage: python scripts/review_set.py scripts/replication/core100_review.json
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

from metalesionlab.meta_api import REPO_ROOT
from metalesionlab.test_studio import apply_review


def review_sheet(manifest: dict, set_dir: Path, cell: int = 180, cols: int = 10) -> Path:
    kept = [it for it in manifest["items"] if it.get("status") == "kept"]
    rows = (len(kept) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 16)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, it in enumerate(kept):
        x, y = (i % cols) * cell, (i // cols) * (cell + 16)
        img = Image.open(set_dir / it["image"]).convert("RGB")
        img.thumbnail((cell - 8, cell - 8))
        sheet.paste(img, (x + 4, y + 4))
        draw.text((x + 4, y + cell), it["word"] + (" *" if it.get("review") else ""), fill="black")
    path = set_dir / "review_sheet.png"
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("review", type=Path)
    args = ap.parse_args()
    review = json.loads(args.review.read_text())
    sets = REPO_ROOT / "runs" / "sets"
    set_dir = sets / review["set"]
    auto = set_dir / "manifest_auto.json"
    if not auto.exists():
        shutil.copy2(set_dir / "manifest.json", auto)
    manifest = json.loads(auto.read_text())
    redraw_names = {d["from"] for d in review["items"].values() if d["action"] == "replace"}
    redraws = {n: json.loads((sets / n / "manifest.json").read_text()) for n in redraw_names}
    manifest, copies = apply_review(manifest, review, redraws)
    for src_set, src, dest in copies:
        shutil.copy2(sets / src_set / src, set_dir / dest)
    manifest["review"] = {"file": str(args.review), "date": review.get("date", "")}
    (set_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    kept = sum(it.get("status") == "kept" for it in manifest["items"])
    dropped = [it["word"] for it in manifest["items"] if it.get("status") == "dropped"]
    review_only = [it["word"] for it in manifest["items"] if it.get("status") == "review"]
    print(f"{review['set']}: {kept} kept, dropped {dropped}, still in review {review_only}")
    print(f"sheet: {review_sheet(manifest, set_dir)}")


if __name__ == "__main__":
    main()

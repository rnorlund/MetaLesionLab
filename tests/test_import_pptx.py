"""scripts/import_pptx_test.py on a small generated PowerPoint."""
import csv
import importlib.util
import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

pptx = pytest.importorskip("pptx")
from pptx.util import Inches  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "import_pptx_test.py"
spec = importlib.util.spec_from_file_location("import_pptx_test", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _picture(path, shape):
    img = Image.new("RGB", (300, 300), "white")
    d = ImageDraw.Draw(img)
    {"circle": lambda: d.ellipse((50, 50, 250, 250), outline="black", width=8),
     "square": lambda: d.rectangle((60, 60, 240, 240), outline="black", width=8),
     "line": lambda: d.line((40, 260, 260, 40), fill="black", width=8),
     "logo": lambda: d.rectangle((0, 0, 300, 300), fill="gray")}[shape]()
    img.save(path)
    return path


def make_deck(tmp_path):
    prs = pptx.Presentation()
    blank = prs.slide_layouts[6]
    title = prs.slides.add_slide(prs.slide_layouts[0])
    title.shapes.title.text = "Naming test"  # no picture: skipped
    for shape in ("circle", "square", "line"):
        slide = prs.slides.add_slide(blank)
        slide.shapes.add_picture(str(_picture(tmp_path / f"{shape}.png", shape)), Inches(2), Inches(1), Inches(5), Inches(5))
        if shape == "square":  # a small logo too: the largest picture is the item
            slide.shapes.add_picture(str(_picture(tmp_path / "logo.png", "logo")), Inches(0.2), Inches(0.2), Inches(0.6), Inches(0.6))
    path = tmp_path / "deck.pptx"
    prs.save(path)
    return path


def test_pptx_to_zip(tmp_path):
    deck = make_deck(tmp_path)
    targets = tmp_path / "targets.txt"
    targets.write_text("ball: sphere; globe\nbox\n# a comment\nstick\n")
    data, log = mod.build_zip(deck, targets, practice=1)
    z = zipfile.ZipFile(io.BytesIO(data))
    assert sorted(z.namelist()) == ["001.png", "002.png", "003.png", "README.txt", "test.csv"]
    rows = list(csv.DictReader(io.StringIO(z.read("test.csv").decode())))
    assert [(r["file"], r["target"], r["alternates"], r["practice"]) for r in rows] == [
        ("001.png", "ball", "sphere; globe", "yes"), ("002.png", "box", "", ""), ("003.png", "stick", "", "")]
    assert Image.open(io.BytesIO(z.read("002.png"))).size == (300, 300)  # the big picture, not the logo
    assert Image.open(io.BytesIO(z.read("002.png"))).getpixel((150, 150)) == (255, 255, 255)
    assert log[0].startswith("slide   2 -> 001.png")


def test_mismatch_and_csv_targets(tmp_path):
    deck = make_deck(tmp_path)
    short = tmp_path / "short.txt"
    short.write_text("ball\nbox\n")
    with pytest.raises(SystemExit, match="3 slides have a picture"):
        mod.build_zip(deck, short)
    table = tmp_path / "targets.csv"
    table.write_text("target,alternates,practice\nball,,yes\nbox,crate,\n")
    data, _ = mod.build_zip(deck, table, skip={4})
    rows = list(csv.DictReader(io.StringIO(zipfile.ZipFile(io.BytesIO(data)).read("test.csv").decode())))
    assert [(r["target"], r["alternates"], r["practice"]) for r in rows] == [("ball", "", "yes"), ("box", "crate", "")]

"""The damage schematic, the 7-picture default, the rotating title word and the How-we-know list on /damaged and /plato/damage."""
import html as H
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "metalesionlab" / "web"
DAMAGED = (WEB / "pages" / "damaged.html").read_text()
PLATO = (WEB / "pages" / "plato_damage.html").read_text()
QUESTION = "What happens to an AI’s idea of a thing when we damage it?"
THINGS = {"a chair", "a rocking chair", "a throne", "God", "a clock"}  # things with damage results (the hero's four, plus the plain chair)


@pytest.mark.parametrize("page", [DAMAGED, PLATO])
def test_schematic_renders_with_three_versions(page):
    assert page.count("data-damage-schematic") == 1
    assert len(re.findall(r'class="ds-ver"', page)) == 3
    for t in ("Part 1: reads your words", "Part 2: paints the picture", "turns your words into an idea", "turns the idea into an image",
              "No damage", "Damage Part 1", "Damage Part 2", "it paints the wrong thing", "a smudged chair",
              "forgets <em>what</em> to draw", "forgets <em>how</em>", "Stable Diffusion XL, an open image AI"):
        assert t in page, t
    assert page.count("is-cracked") == 2
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", (WEB / "static/css/damage-schematic.css").read_text())
    for src in re.findall(r'/static/img/plato_damage/[\w.-]+', page):
        assert (WEB / src.lstrip("/")).exists(), src


def test_schematic_before_number_blocks_on_damaged():
    assert DAMAGED.index("data-damage-schematic") < DAMAGED.index('id="hero-stats"')
    assert DAMAGED.index("data-damage-schematic") > DAMAGED.index("data-hero-carousel")


def test_default_is_seven_pictures():
    js = (WEB / "static/js/hero-carousel.js").read_text()
    assert "DEFAULT_COUNT = 7" in js and "setCount(DEFAULT_COUNT)" in js and "COUNTS = [5, 7, 10]" in js


def test_title_keeps_the_full_question_and_words_are_damaged_things():
    h1 = re.search(r'<h1 id="hero-h" aria-label="([^"]+)">(.*?)</h1>', DAMAGED, re.S)
    assert H.unescape(h1.group(1)) == QUESTION
    assert H.unescape(re.sub(r"<[^>]+>", "", h1.group(2))) == QUESTION  # without JS it reads "a thing"
    words = re.search(r'data-rotating-word data-words="([^"]+)"', h1.group(2)).group(1).split("|")
    assert words and set(words) <= THINGS
    carousel = " ".join(re.findall(r'"caption":\s*"([^"]+)"', DAMAGED))
    for w in words:
        assert w.replace("a ", "") in carousel or w == "a chair", w


@pytest.mark.skipif(not shutil.which("node"), reason="node")
def test_how_list_has_no_bold_number_line_for_bar_pairs():
    code = ("const F=require(%s);const s={kind:'bars',o:{values:[38,25],labels:['Damaged the words part','Damaged the painting part'],"
            "tones:['blue','orange'],max:100,suffix:' of 100',label:'chairs stopped being the kind we asked for'},q:'Equal damage.'};"
            "console.log(JSON.stringify(F.how({stats:[s]})))" % json.dumps(str(WEB / "static/js/plato_firstlook.js")))
    out = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
    assert "<b>" not in out and "Damaged the words part" not in out

"""Damage, in a brain and in an AI (/damaged #brain-ai; static/js/brain-ai.js, static/css/brain-ai.css): its own section
after the first screen and before "Every damage experiment", with its images, plain words, the honest caption, and a
script that plays only on screen and respects reduced motion."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web

STATIC = Path(web.__file__).resolve().parent / "static"
JS = (STATIC / "js" / "brain-ai.js").read_text()
CSS = (STATIC / "css" / "brain-ai.css").read_text()
IMG = STATIC / "img" / "brain_ai"
BANNED = ["decline", "impaired", "normal", "abnormal", "healthy", "risk", "diagnose", "dementia", "disease"]


@pytest.fixture(scope="module")
def page():
    return TestClient(web.app_for("plato")).get("/damaged").text


@pytest.fixture(scope="module")
def section(page):
    m = re.search(r'<section\b[^>]*id="brain-ai"[^>]*>.*?</section>', page, re.S)
    assert m
    return m.group(0)


def test_section_sits_after_the_hero_and_before_results(page):
    hero, mine, results = page.index("dm-hero"), page.index('id="brain-ai"'), page.index('id="results"')
    assert hero < mine < results
    assert 'data-ask="What are we comparing this to?"' in page and 'aria-labelledby="brain-ai-h"' in page
    assert "Damage, in a brain and in an AI" in page
    assert "/static/js/brain-ai.js" in page and "/static/css/brain-ai.css" in page


def test_assets_exist():
    names = [f"brain_{i}.webp" for i in range(9)] + [f"loss_{i}.webp" for i in range(9)] + ["ghost_vent.webp", "lang.webp"]
    for n in names:
        assert (IMG / n).stat().st_size > 0, n
    assert "brain_\" + i" in JS and "loss_\" + i" in JS and "ghost_vent.webp" in JS and "lang.webp" in JS


def test_plain_words(section):
    text = re.sub(r"<[^>]+>", " ", section).lower()
    for w in BANNED:
        assert not re.search(rf"\b{w}", text), w
    digits = set(re.findall(r"\d+", text))
    assert digits <= {"20", "50", "80"}, digits


def test_honest_caption(section):
    assert "An AI-made illustration of an ageing brain scan, not a real person’s scan." in section
    assert "It’s a comparison, not a claim about any person." in section
    assert "Meta’s open AI, Muse Glimmer, asked to describe a chair" in section


def test_controls_are_labelled(section):
    assert re.search(r'<button[^>]*aria-label="[^"]+"', section)
    assert re.search(r'<input[^>]*type="range"[^>]*aria-label="[^"]+"', section)


def test_script_plays_only_on_screen_and_respects_reduced_motion():
    assert "IntersectionObserver" in JS and "prefers-reduced-motion" in JS
    assert "document.hidden" in JS and "visibilitychange" in JS
    assert "/api/plato/glimmer" in JS and ".catch(" in JS


def test_css_uses_tokens_only():
    css = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b(?![\w-])", css)
    for m in re.finditer(r"font-size\s*:\s*([^;}]+)", css):
        v = m.group(1).strip()
        assert v.startswith("var(--fs-") or re.fullmatch(r"[\d.]+(em|%)", v) , v
    assert "@media (prefers-reduced-motion" in CSS and "max-width: 800px" in CSS
    for m in re.finditer(r"rgba?\(([^)]*)\)", css):
        assert re.match(r"^\s*(0,\s*0,\s*0|255,\s*255,\s*255)\s*(,\s*[\d.]+\s*)?$", m.group(1)), m.group(0)

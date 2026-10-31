"""The next-question buttons (static/js/next-question.js, static/css/next-question.css, added to every Plato page by
site.py add_next): a section marked data-ask="…?" gets a button just above it that asks its question and scrolls the
page down to it. The questions are short, end in "?", differ on a page, and mark a section with a heading for focus
to land on; reduced motion jumps instead of scrolling; a hidden section hides its button."""
import re

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web
from metalesionlab.web import site

STATIC = web.HERE / "static"
JS = (STATIC / "js" / "next-question.js").read_text()
CSS = (STATIC / "css" / "next-question.css").read_text()
PAGES = {"/": 6, "/takehomes": 2, "/damaged": 1, "/plato/clock": 5, "/plato/phaedrus": 4, "/plato": 9,
         "/plato/ideas": 8,
         "/plato/bird": 6,
         "/plato/cave": 6,
         "/plato/cratylus": 5,
         "/plato/forms": 5,
         "/plato/lifespan": 6,
         "/plato/inside": 4,
         "/plato/glimmer": 3,
         "/plato/scale": 7,
         "/plato/atlas": 5,
         "/plato/telephone": 6,
         "/plato/damage": 2}
SECTION = re.compile(r'<section\b[^>]*\bdata-ask="([^"]*)"[^>]*>(.*?)</section>', re.S)


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


def test_added_to_every_plato_page_once(client):
    for path in PAGES:
        page = client.get(path).text
        assert page.count("/static/js/next-question.js") == 1 and page.count("/static/css/next-question.css") == 1, path
    assert site.add_next(site.add_next("<head></head>")).count(site.NEXT) == 1


@pytest.mark.parametrize("path,n", PAGES.items())
def test_each_page_asks_short_distinct_questions_over_sections_with_headings(client, path, n):
    found = SECTION.findall(client.get(path).text)
    asks = [q for q, _ in found]
    assert len(asks) == n and len(set(asks)) == n, asks
    for q, body in found:
        assert q.endswith("?") and 0 < len(q) <= 60, q
        assert "'" not in q, f"use a curly apostrophe: {q}"
        assert re.search(r"<h[123]\b", body), f"{q}: the section needs a heading for focus to land on"


def test_scrolls_smoothly_jumps_with_reduced_motion_and_moves_focus():
    assert "prefers-reduced-motion: reduce" in JS and "behavior: reduce ? 'auto' : 'smooth'" in JS
    assert "h.focus(" in JS and "setAttribute('tabindex', '-1')" in JS
    assert ".nq:has(+ [hidden]) { display: none; }" in CSS  # a hidden section hides its question
    assert "@media (prefers-reduced-motion: reduce) { .nq-arrow { animation: none; } }" in CSS


def test_tokens_only():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", CSS)

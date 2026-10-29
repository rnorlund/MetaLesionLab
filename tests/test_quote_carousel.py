"""The landing page's quote band as a carousel (static/js/quote-carousel.js, static/css/quote-carousel.css): every
quote in the rotation rendered word for word from the verified passages, the carousel's two files linked on every
page with a band (and only there), and the band still showing every quote without JavaScript."""
import html
import json
import re

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web
from metalesionlab.web import epigraph as E

REPO = web.HERE.parents[1]
P = {p["id"]: p for p in json.loads((REPO / "public_data" / "plato_passages.json").read_text())["passages"]}
JS = web.HERE / "static" / "js" / "quote-carousel.js"
CSS = web.HERE / "static" / "css" / "quote-carousel.css"
ROTATION = ["apology-38a", "metaphysics-980a21", "meno-86b", "phaedrus-276a", "theaetetus-155d", "ethics-1103a32",
            "republic-597c"]


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


@pytest.fixture(scope="module")
def landing(client):
    return client.get("/?nosplash=1").text


def _band(page: str) -> str:
    return re.search(r'<div class="epigraph-band">.*?</figure>\s*</div>', page, re.S).group(0)


def _css_rules(text: str):
    """(selector, body) for every innermost rule, inside @media blocks too."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text)]


def test_the_band_renders_every_quote_in_the_rotation(landing):
    band = _band(landing)
    figs = re.findall(r'<figure class="epigraph epigraph--band" data-passage="([^"]+)".*?</figure>', band, re.S)
    assert figs == ROTATION
    for pid, fig in zip(ROTATION, re.findall(r"<figure.*?</figure>", band, re.S)):
        assert html.unescape(re.search(r"<p>(.*?)</p>", fig, re.S).group(1)) == E.words(P[pid])  # word for word
        assert "<figcaption>" in fig and 'class="epigraph-face"' in fig
    assert {E.speaker(P[i]) for i in ROTATION} == {"Plato", "Socrates", "Aristotle"}
    assert "How do we come to know a thing? Plato, Socrates and Aristotle" in landing


def test_band_quotes_are_verified_and_never_repeated():
    for page in (web.HERE / "pages").glob("*.html"):
        text = page.read_text()
        for band in re.findall(r'<div class="epigraph-band">(.*?)</div>', text, re.S):
            ids = re.findall(r"<!--#epigraph:(\S+?)\s+band\s*-->", band)
            assert ids and all(i in P for i in ids), (page.name, [i for i in ids if i not in P])
            assert len(ids) == len(set(ids)), page.name
            assert not re.sub(r"<!--.*?-->|\s", "", band, flags=re.S), page.name  # nothing but verified quotes
    assert E.render("made-up-1a", "band") == ""  # an unverified id renders nothing


def test_carousel_files_load_on_pages_with_a_band(client, landing):
    head = landing[:landing.index("</head>")]
    assert len(re.findall(r'<link rel="stylesheet" href="/static/css/quote-carousel\.css\?v=\d+">', head)) == 1
    assert len(re.findall(r'<script src="/static/js/quote-carousel\.js\?v=\d+" defer></script>', head)) == 1
    assert head.index("epigraph.css") < head.index("quote-carousel.css")
    for f in ("/static/js/quote-carousel.js", "/static/css/quote-carousel.css"):
        assert client.get(f).status_code == 200, f
    bird = client.get("/plato/bird").text  # an epigraph, but no band
    assert 'data-passage="theaetetus-155d"' in bird and "quote-carousel" not in bird


def test_fill_links_the_carousel_only_for_a_band():
    page = "<html><head></head><body>{}</body></html>"
    band = E.fill(page.format('<div class="epigraph-band"><!--#epigraph:meno-86b band--><!--#epigraph:apology-38a band--></div>'))
    assert band.count(E.CAROUSEL) == 1 and band.index(E.CAROUSEL) < band.index("</head>")
    assert E.fill(band) == band  # linked once
    assert E.CAROUSEL not in E.fill(page.format("<!--#epigraph:meno-86b--><!--#epigraph:metaphysics-981a5 inline-->"))


def test_without_javascript_every_quote_stays_visible(landing):
    band = _band(landing)
    assert band.startswith('<div class="epigraph-band">')  # the script adds .qc; the page is served without it
    for fig in re.findall(r"<figure[^>]*>", band):
        assert not re.search(r"\b(hidden|inert|aria-hidden|style)\b", fig), fig
    assert "qc-" not in band and "aria-roledescription" not in band
    # epigraph.css lays the band out as a row of every quote that wraps ...
    assert re.search(r"\.epigraph-band \{ display: grid; grid-template-columns: repeat\(auto-fit",
                     (web.HERE / "static" / "css" / "epigraph.css").read_text())
    # ... and quote-carousel.css hides nothing unless the script has made the band a carousel
    for selector, body in _css_rules(CSS.read_text()):
        if re.search(r"visibility:\s*hidden|opacity:\s*0\s*;|display:\s*none", body):
            for s in selector.split(","):
                assert ".qc" in s, s
    assert re.search(r"if \(n < 2\) return;", JS.read_text())  # one quote: left as it is


def test_carousel_follows_the_aria_pattern_and_reduced_motion():
    js = JS.read_text()
    for needle in ("'aria-roledescription', 'carousel'", "'aria-roledescription', 'slide'", "'role', 'region'",
                   "'Quote ' + (i + 1) + ' of ' + n", "'aria-current', 'true'", "'aria-live', stopped || held ? 'polite' : 'off'",
                   "(prefers-reduced-motion: reduce)", "visibilitychange", "pointerenter", "focusin", ":focus-visible",
                   "'ArrowRight'", "'ArrowLeft'", "'Previous quote'", "'Next quote'", "'Pause the quotes'", "'Play the quotes'"):
        assert needle in js, needle
    css = CSS.read_text()
    secs = float(re.search(r"--qc-interval:\s*([\d.]+)s", css).group(1))
    assert 8 <= secs <= 9
    # every transition is inside the no-preference block, so reduced motion gets none
    motion = re.search(r"@media \(prefers-reduced-motion: no-preference\) \{(.*?)\n\}", css, re.S).group(1)
    outside = re.sub(r"/\*.*?\*/", "", css.replace(motion, ""), flags=re.S)
    assert "transition" not in outside and "transition" in motion
    # the slides share one grid cell, so the band is as tall as its tallest quote
    assert re.search(r"figure\.epigraph--band \{[^}]*grid-area: 1 / 1;", css)

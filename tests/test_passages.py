"""The verified passages beyond Ask Socrates: the epigraphs rendered from them, and the word-for-word checker
(scripts/verify_passages.py), offline."""
import html
import importlib.util
import json
import re

import pytest
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from metalesionlab.web import app as web
from metalesionlab.web import epigraph as E

REPO = web.HERE.parents[1]
DATA = json.loads((REPO / "public_data" / "plato_passages.json").read_text())
P = {p["id"]: p for p in DATA["passages"]}

spec = importlib.util.spec_from_file_location("verify_passages", REPO / "scripts" / "verify_passages.py")
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def _quoted(fig: str) -> str:
    """The words an epigraph shows, without the quotation marks and ellipses the renderer adds."""
    words = html.unescape(re.search(r"<blockquote[^>]*><p>(.*?)</p></blockquote>", fig, re.S).group(1))
    assert words.startswith("“") and words.endswith("”")
    return words[1:-1].removeprefix("…").removesuffix("…")


# --- epigraphs ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("pid", sorted(P))
def test_every_passage_renders_word_for_word_with_its_citation(pid):
    p, fig = P[pid], E.render(pid)
    assert fig.startswith('<figure class="epigraph"') and _quoted(fig) == p["text"]
    cap = html.unescape(re.search(r"<figcaption>(.*?)</figcaption>", fig, re.S).group(1))
    ref = p.get("stephanus") or p["bekker"]
    assert f'<span class="epigraph-ref">{ref}</span>' in cap and f"<cite>{p['work']}</cite>" in cap
    assert f'href="{p["source_url"]}"' in cap and f'cite="{p["source_url"]}"' in fig
    if p["author"] == "Aristotle":
        assert cap.startswith('<span class="epigraph-who">Aristotle,</span>') and "tr. W. D. Ross" in cap
        assert f"{p['book']}.{p['chapter']}," in cap
    else:
        assert "tr. Jowett" in cap
        lead = "Socrates, in Plato’s" if p["speaker"].startswith("Socrates") else "Plato,"
        assert cap.startswith(f'<span class="epigraph-who">{lead}</span>')


def test_epigraph_marks_fragments_and_refuses_unknown_ids():
    assert "<p>“…daily to discourse" in E.render("apology-38a") and "not worth living…”</p>" in E.render("apology-38a")
    assert "<p>“All men by nature desire to know." in E.render("metaphysics-980a21")
    assert "Aristotle,</span> <cite>Metaphysics</cite> I.1, <span class=\"epigraph-ref\">980a21–24" in E.render(
        "metaphysics-980a21")
    assert "Plato,</span> <cite>Timaeus</cite> <span" in E.render("timaeus-28a")  # Timaeus speaks, not Socrates
    assert "Socrates, in Plato’s</span> <cite>Republic</cite> VII, <span" in E.render("republic-518b")
    assert E.render("republic-999z") == "" and E.render("") == ""
    assert 'class="epigraph epigraph--inline"' in E.render("metaphysics-981a5", "inline")
    assert 'class="epigraph"' in E.render("metaphysics-981a5", "nonsense")


def test_fill_renders_markers_and_links_the_stylesheet_once():
    page = ("<html><head><title>t</title></head><body><!--#epigraph:theaetetus-155d-->"
            "<!--#epigraph:metaphysics-981a5 inline--><!--#epigraph:made-up-1a--></body></html>")
    out = E.fill(page)
    assert out.count('<figure class="epigraph') == 2 and "<!--#epigraph" not in out
    assert out.count(E.STYLESHEET) == 1 and out.index(E.STYLESHEET) < out.index("</head>")
    assert "IBM+Plex+Serif:ital,wght@1,300" in out
    assert E.fill("<html><head></head><body>none</body></html>") == "<html><head></head><body>none</body></html>"


def test_the_site_fills_epigraphs_on_every_html_page():
    web.app.add_api_route("/test-epigraph", lambda: HTMLResponse(
        "<html><head></head><body><main><!--#epigraph:cratylus-439b--></main></body></html>"),
        methods=["GET"], include_in_schema=False)
    route = web.app.router.routes[-1]
    try:
        got = TestClient(web.app).get("/test-epigraph").text
    finally:
        web.app.router.routes.remove(route)
    assert 'data-passage="cratylus-439b"' in got and "knowledge of things is not to be derived from names" in got
    assert re.search(r'href="/static/css/epigraph\.css\?v=\d+"', got)  # versioned like every stylesheet
    assert TestClient(web.app).get("/static/css/epigraph.css").status_code == 200


def test_pages_ask_only_for_verified_passages():
    for page in (web.HERE / "pages").glob("*.html"):
        for pid in re.findall(r"<!--#epigraph:(\S+?)(?:\s+\w+)?\s*-->", page.read_text()):
            assert pid in P, (page.name, pid)


PLACED = {  # each series page: one epigraph, just below its shared title header, no passage twice
    "plato_lifespan.html": "meno-85c", "plato_telephone.html": "republic-597e", "plato_cave.html": "republic-518b",
    "plato_cratylus.html": "cratylus-439b", "plato_atlas.html": "metaphysics-980a21",
    "plato_inside.html": "metaphysics-981a28", "plato_damage.html": "timaeus-28a", "plato_bird.html": "theaetetus-155d",
    "plato_forms.html": "republic-596a", "plato_clock.html": "republic-597c",
}


def test_each_series_page_has_one_epigraph_below_its_title():
    assert len(set(PLACED.values())) == len(PLACED)
    for name, pid in PLACED.items():
        text = (web.HERE / "pages" / name).read_text()
        assert text.count("<!--#epigraph:") == 1, name
        assert re.search(r'<div class="title-pair">.*?</div>\s*<!--#epigraph:' + re.escape(pid) + r"-->", text, re.S), name


def test_aristotles_reply_on_plato_is_a_labelled_framing():
    page = TestClient(web.app).get("/plato").text
    box = re.search(r'<aside class="pc-sec pc-reply" id="aristotle".*?</aside>', page, re.S).group(0)
    assert "A philosophical framing, not a finding" in box and "Aristotle’s reply" in box
    assert box.count("<figure class=") == 1 and 'data-passage="metaphysics-981a5"' in box and "tr. W. D. Ross" in box
    prose = re.search(r'<div class="pc-reply-text">.*?<p>(.*?)</p>', box, re.S).group(1)
    # short (the page's sections lead with at most two sentences) and no quotes
    assert 1 <= len(re.findall(r"[.?!](?:\s|$)", prose)) <= 2 and "“" not in prose and '"' not in prose
    assert '<a href="#aristotle">' in page and page.index('id="everything"') < page.index('id="aristotle"')


def test_landing_quote_band_sits_below_the_reveal():
    page = TestClient(web.app).get("/?nosplash=1").text
    band = re.search(r'<section class="band quote-band" id="quotes".*?</section>', page, re.S).group(0)
    assert page.index('id="reveal"') < page.index('id="quotes"') < page.index('id="findings"')
    ids = re.findall(r'data-passage="([^"]+)"', band)
    assert len(ids) == 7 and {P[i]["author"] for i in ids} == {"Plato", "Aristotle"}  # a carousel (test_quote_carousel)
    assert band.count('class="epigraph epigraph--band"') == 7 and 'class="epigraph-band"' in band


def test_epigraph_css_keeps_the_layout_tokens():
    css = (web.HERE / "static" / "css" / "epigraph.css").read_text()
    assert "var(--measure" in css and "font-style: italic" in css and "all-small-caps" in css
    assert "IBM Plex Serif" in css


# --- the word-for-word checker -----------------------------------------------------------------------------

SCAN = V.words("""BOOK A
I ALL men by nature desire to know. An indication of g8oa
this is the delight we take in our senses ; for even apart
from their usefulness they are loved for themselves. Now art 5
arises when from many notions gained by experi-
ence one universal judgement about a class of objects is in
clude produced. For men of experience know that the thing is so, but do not know

3o why, while the others know the ' why ' and the cause. 'Cause' means (i) that from which, as immanent 2

1 The double meaning of apxn - 'beginning ' and ' government ' - cannot be reproduced in English.

BOOK A. 2 ioi3a

material, a thing comes into being, e. g. the bronze is the 25 cause of the statue.
""")


@pytest.mark.parametrize("text", [
    "All men by nature desire to know.",
    "Now art arises when from many notions gained by experience one universal judgement",  # line-end hyphen
    "For men of experience know that the thing is so, but do not know why, while the others know the ‘why’ and the "
    "cause.",  # a margin number inside, curly quotes
    "‘Cause’ means (1) that from which, as immanent material, a thing comes into being, e.g. the bronze is the cause "
    "of the statue.",  # a page break (footnote and running head), OCR's (i) for (1)
])
def test_in_print_accepts_the_printed_words(text):
    assert V.in_print(text, SCAN) == (True, "ok")


@pytest.mark.parametrize("text, why", [
    ("For men of experience know that the thing is so, but do not know why, while the others know the why and cause.",
     "print has 'the'"),                                                       # a word dropped (MIT's kind of slip)
    ("Now art arises when from many notions gained by experience one universal judgment", "'judgment'"),  # changed
    ("All men by nature wish to know.", "'wish'"),
    ("Plato never wrote this sentence anywhere at all.", "not found"),
])
def test_in_print_rejects_a_dropped_or_changed_word(text, why):
    ok, msg = V.in_print(text, SCAN)
    assert not ok and why in msg


def test_check_compares_exactly_and_allows_only_the_printed_capitals(monkeypatch):
    src = {"https://x/source.txt": 'Book I\n"ALL men by nature desire to know. An indication of this is the delight.\n',
           "https://x/scan.txt": "I ALL men by nature desire to know. An indication of g8oa this is the delight."}
    monkeypatch.setattr(V, "fetch", lambda url, cache: src[url])
    base = {"source_text_url": "https://x/source.txt", "print_text_url": "https://x/scan.txt"}
    good = {**base, "text": "All men by nature desire to know.", "as_printed": "ALL men by nature desire to know."}
    assert V.check(good, {}, {}, None) == []
    assert V.check({**base, "text": "All men by nature desire to know."}, {}, {}, None) == [
        "not word for word in https://x/source.txt"]  # sentence case needs as_printed
    off = {**good, "text": "All men by nature wish to know."}
    assert "text differs from as_printed by more than letter case" in V.check(off, {}, {}, None)
    plato = {"source_text_url": "https://x/source.txt", "text": "An indication of this is the delight."}
    assert V.check(plato, {}, {}, None) == []  # no print_text_url: the exact check only


def test_every_aristotle_passage_names_its_printed_edition():
    for p in DATA["passages"]:
        if p["author"] == "Aristotle":
            scan = p["print_url"].rsplit("/", 1)[1]
            assert p["print_text_url"] == f"https://archive.org/download/{scan}/{scan}_djvu.txt"
    years = {"theworksofaristo08arisuoft": "1928", "theworksofaristo09arisuoft": "1925"}
    for p in DATA["passages"]:
        if p["author"] == "Aristotle":
            assert years[p["print_url"].rsplit("/", 1)[1]] in p["translation"]
    assert any("Physics" in n["what"] and "1930" in n["what"] for n in DATA["not_included"])

"""Plato, Socrates and Aristotle on the pages (web/portraits.py): every epigraph shows its speaker's face, the
landing hero has Plato pointing up, the series pages have Plato asking and Socrates as a floating guide, and
every portrait is credited "drawn by Meta's Muse Image"."""
import json
import re

from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab.web import app as web
from metalesionlab.web import epigraph as E
from metalesionlab.web import portraits as PT

STATIC = web.HERE / "static"
P = {p["id"]: p for p in json.loads((web.HERE.parents[1] / "public_data" / "plato_passages.json").read_text())["passages"]}
SRC = {"Plato": "/static/img/portraits/plato-neutral.webp", "Socrates": "/static/img/socrates/socrates-neutral.webp",
       "Aristotle": "/static/img/portraits/aristotle-neutral.webp"}


def _file(src: str):
    return STATIC / src[len("/static/"):]


def _face(html: str) -> re.Match | None:
    return re.search(r'<img class="epigraph-face" src="([^"]+)"[^>]*alt="([^"]+)"', html)


def test_each_epigraph_speaker_gets_the_right_portrait():
    expected = {"theaetetus-155d": "Socrates", "apology-38a": "Socrates", "republic-596a": "Socrates",
                "timaeus-28a": "Plato", "metaphysics-981a5": "Aristotle", "ethics-1103a32": "Aristotle"}
    for pid, who in expected.items():
        out = E.render(pid)
        m = _face(out)
        assert m and m.group(1) == SRC[who], (pid, out[:200])
        assert f'data-speaker="{who.lower()}"' in out
        assert who in m.group(2) and "drawn by Meta’s Muse Image" in m.group(2)  # alt: who, and the credit
    seen = set()
    for pid, p in P.items():  # every verified passage: the face is whoever the citation names
        who = E.speaker(p)
        out = E.render(pid)
        assert _face(out).group(1) == SRC[who], pid
        lead = re.search(r'<span class="epigraph-who">(.*?)</span>', out).group(1)
        assert lead.startswith(who), (pid, lead)
        seen.add(who)
    assert seen == {"Plato", "Socrates", "Aristotle"}
    for variant in ("inline", "band"):  # every variant shows the face
        assert _face(E.render("meno-86b", variant)).group(1) == SRC["Socrates"]


def test_an_unknown_speaker_gets_no_portrait(monkeypatch):
    stranger = {**P["timaeus-28a"], "id": "xenophon-1", "author": "Xenophon", "speaker": "Xenophon"}
    monkeypatch.setattr(E, "passages", lambda: {"xenophon-1": stranger})
    out = E.render("xenophon-1")
    assert out.startswith('<figure class="epigraph"') and "Xenophon," in out  # still rendered, just no face
    assert "<img" not in out and "data-speaker" not in out
    assert PT.face("Xenophon") == "" and PT.face("") == ""


def test_portrait_files_are_small_doodles():
    for src in SRC.values():
        f = _file(src)
        assert f.exists() and f.stat().st_size < 40 * 1024, f
        assert Image.open(f).size == (256, 256)
    assert Image.open(_file(PT.THINKING)).size == (256, 256)
    for name in ("plato-pointing-up.webp", "plato-pointing-up-420.webp", "aristotle-earth.webp", "socrates-and-plato.webp"):
        f = STATIC / "img" / "portraits" / name
        assert f.exists() and f.stat().st_size < 160 * 1024, f
        assert Image.open(f).mode == "RGBA"  # ink on transparent paper


def test_landing_hero_has_plato_pointing_up_with_alt_text():
    page = TestClient(web.app).get("/?nosplash=1").text
    hero = re.search(r'<section class="hero hero-draw".*?</section>', page, re.S).group(0)
    fig = re.search(r'<figure class="hero-plato">(.*?)</figure>', hero, re.S)
    assert fig, "no Plato in the landing hero"
    img = re.search(r"<img [^>]*>", fig.group(1)).group(0)
    alt = re.search(r'alt="([^"]+)"', img).group(1)
    assert "Plato" in alt and "pointing straight up" in alt and len(alt) > 60
    for src in re.findall(r"/static/img/portraits/[\w-]+\.webp", img):
        assert _file(src).exists(), src
    assert "Drawn by Meta’s Muse Image" in fig.group(1)
    # beside the question, before it in the markup, and the drawing pad still comes first
    assert hero.index('class="hero-pad"') < hero.index('class="hero-plato"') < hero.index("What would Plato ask an AI?")
    assert re.search(r'href="/static/css/portraits\.css\?v=\d+"', page)
    assert "Portraits of Plato, Socrates and Aristotle: marker doodles drawn by Meta’s Muse Image." in page


def test_series_pages_have_plato_asking_and_socrates_as_guide():
    c = TestClient(web.app)
    for path in ("/plato", "/plato/forms", "/plato/cave"):
        page = c.get(path).text
        assert page.count('class="pt-guide"') == 1 and 'href="/socrates"' in page, path
        kicker = re.search(r'<p class="title-kicker has-face"><img class="kicker-face" src="([^"]+)"[^>]*alt="([^"]+)"', page)
        assert kicker and _file(kicker.group(1)).exists() and "Plato" in kicker.group(2), path
        assert 'class="pt-credit"' in page and "drawn by Meta’s Muse Image" in page, path
        assert re.search(r'href="/static/css/portraits\.css\?v=\d+"', page), path
    for path in ("/", "/socrates", "/draw"):  # the guide is for the series pages only
        assert 'class="pt-guide"' not in c.get(path).text, path


def test_socrates_page_credits_its_pictures_once():
    page = TestClient(web.app).get("/socrates").text
    assert "socrates-and-plato.webp" in page and 'class="pt-credit"' not in page  # its footnote credits them
    note = re.search(r'<p class="footnote">(.*?)</p>', page, re.S).group(1)
    assert note.count("drawn by Meta’s Muse Image") == 1
    assert "Open Access, CC0" in page and "Public domain, via" in page
    for f in ("david-death-of-socrates.webp", "raphael-plato-aristotle.webp"):
        assert (STATIC / "img" / "portraits" / "art" / f).exists()
    notice = (web.HERE.parents[1] / "NOTICE").read_text()
    assert "The Death of Socrates" in notice and "CC0" in notice and "School of Athens" in notice
    assert "drawn by Meta's Muse Image" in notice


def test_portrait_colours_are_tokens_and_work_on_a_dark_page():
    css = (STATIC / "css" / "portraits.css").read_text()
    tokens, rest = css.split("html.portraits-chalk", 1)
    tokens = tokens[tokens.index(":where(:root)"):]
    # every colour is a token, set once in the :where(:root) block, which any theme's :root rule overrides
    assert not re.search(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(", rest), "colours outside the token block"
    for name in ("--portrait-paper", "--portrait-ring", "--portrait-sheet", "--portrait-line-filter"):
        assert name + ":" in tokens
    # black lines always sit on a light sheet: faces on paper, whole figures on a sheet (or light lines, chalk)
    assert re.search(r"\.epigraph-face, \.kicker-face, \.pt-guide img, \.demo-face \{[^}]*background: var\(--portrait-paper\)", css)
    assert re.search(r"\.hero-plato img, \.pt-athens img, \.so-pair img \{[^}]*background: var\(--portrait-sheet\)[^}]*"
                     r"filter: var\(--portrait-line-filter\)", css)
    assert "--portrait-line-filter: invert(1)" in rest
    # an epigraph with a face brings the portraits stylesheet with it, on any page
    out = E.fill("<html><head></head><body><!--#epigraph:cratylus-439b--></body></html>")
    assert out.count(PT.STYLESHEET) == 1 and out.index(PT.STYLESHEET) < out.index("</head>")


def test_tour_button_shows_socrates():
    page = TestClient(web.app).get("/?nosplash=1").text
    btn = re.search(r'<button type="button" class="demo-btn" data-tour-start[^>]*>(.*?)</button>', page, re.S).group(1)
    assert 'class="demo-face" src="/static/img/socrates/socrates-neutral.webp"' in btn and "Tour" in btn

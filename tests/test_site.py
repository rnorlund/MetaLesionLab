"""The site shell (web/site.py): one nav on every page, the name in one place, share tags, and the Plato
series cards that appear only once their pages are served."""
import json
import re
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab import brand
from metalesionlab.web import app as web
from metalesionlab.web import site

PAGES = ["/", "/plato", "/draw", "/challenge", "/lab", "/lab/cut", "/lab/bilingual", "/ask", "/scorer", "/studio",
         "/assess", "/take", "/socrates"]
REPO = Path(web.__file__).resolve().parents[2]


@pytest.fixture
def client():
    return TestClient(web.app)


@contextmanager
def served(*paths):
    """Pretend the app serves these pages (as an experiment's router would), then take them away again."""
    added = []
    for path in paths:
        web.app.add_api_route(path, lambda: HTMLResponse("<html><head></head><body>sub-page</body></html>"),
                              methods=["GET"], include_in_schema=False)
        added.append(web.app.router.routes[-1])
    try:
        yield
    finally:
        for route in added:
            web.app.router.routes.remove(route)


def nav_links(html: str) -> list[str]:
    nav = re.search(r'<nav class="topnav" aria-label="Main">(.*?)</nav>', html, re.S).group(1)
    return re.findall(r'href="([^"]+)"', nav)


def test_every_page_has_the_same_nav(client):
    seen = {}
    for path in PAGES:
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.text.count('<header class="topbar site-head">') == 1, path
        seen[path] = nav_links(r.text)
    first = seen["/"]
    assert all(links == first for links in seen.values()), seen
    # Plato first; everything else is under More (next test), so every page is one click away.
    assert first[:3] == ["/", "/draw", "/plato"] and "/plato#inside" in first


def test_more_menu_reaches_every_page(client):
    html = client.get("/plato").text
    more = re.search(r'<details class="nav-more[^"]*">(.*?)</details>', html, re.S).group(1)
    for path in ("/lab", "/lab/cut", "/lab/bilingual", "/ask", "/challenge", "/take", "/assess", "/scorer", "/studio"):
        assert f'href="{path}"' in more, path
    assert 'aria-current="page"' in nav_links_block(client.get("/lab").text)


def nav_links_block(html: str) -> str:
    return re.search(r'<header class="topbar site-head">.*?</header>', html, re.S).group(0)


def test_current_page_is_marked_once(client):
    for path, label in (("/", "Home"), ("/plato", "Experiments"), ("/draw", "Draw a chair")):
        nav = re.search(r'<nav class="topnav".*?</nav>', client.get(path).text, re.S).group(0)
        assert re.findall(r'<a [^>]*aria-current="page"[^>]*>([^<]+)', nav) == [label], path
    nav = re.search(r'<nav class="topnav".*?</nav>', client.get("/lab/cut").text, re.S).group(0)
    assert re.findall(r'aria-current="page"[^>]*>([^<]+)', nav) == ["What can I cut?"]


def test_header_keeps_page_chips(client):
    head = nav_links_block(client.get("/lab").text)
    assert 'id="sample-chip"' in head and "Muse Glimmer 30B" in head


def test_the_name_lives_in_one_place(client, monkeypatch):
    """Renaming is a change to metalesionlab/brand.py: no page, script or module spells the name itself."""
    for folder, pattern in (("metalesionlab/web/pages", "*.html"), ("metalesionlab/web/static/js", "*.js"),
                            ("metalesionlab", "**/*.py")):
        for f in (REPO / folder).glob(pattern):
            if f.name == "brand.py":
                continue
            assert brand.BRAND not in f.read_text(), f
    monkeypatch.setattr(site, "BRAND", "Plato’s Chair")
    for path in ("/", "/plato", "/lab"):
        html = client.get(path).text
        assert "Plato’s Chair" in re.search(r"<title>(.*?)</title>", html).group(1) or path == "/lab"
        assert '<a class="brand" href="/"><b>Plato’s Chair</b>' in html
        assert json.loads(re.search(r'id="site-data">(.*?)</script>', html).group(1))["brand"] == "Plato’s Chair"
        assert brand.BRAND not in html


def test_series_cards_and_links_appear_only_when_served(client):
    # sub-pages merge one by one, so count against what the app serves right now (Plato's Chair first), and
    # pretend to serve the first series page that isn't served yet
    base = [s["path"] for s in client.get("/api/site").json()["series"]]
    assert base[0] == "/plato"
    new = next((e for e in site.SERIES if e["path"] not in base), None)
    if new is None:
        pytest.skip("every series page is served")
    path = new["path"]
    landing = client.get("/").text
    assert landing.count('class="series-card"') == len(base) and 'href="/plato"' in landing
    assert new["question"] not in landing and f'href="{path}"' not in landing
    assert ('id="series"' in client.get("/plato").text) == (len(base) > 1)
    with served(path):
        landing = client.get("/").text
        assert landing.count('class="series-card"') == len(base) + 1
        assert new["question"] in landing and new["source"] in landing
        plato = client.get("/plato").text
        assert 'id="series"' in plato and plato.count('class="series-card"') == len(base)  # the sub-pages only
        assert f'href="{path}"' in nav_links_block(client.get("/lab").text)
        info = client.get("/api/site").json()
        assert info["pages"][path] and path in [s["path"] for s in info["series"]]
    assert f'href="{path}"' not in client.get("/").text


def test_series_override_file_sets_the_finding(client, tmp_path, monkeypatch):
    monkeypatch.setattr(site, "SERIES_DIR", tmp_path)
    (tmp_path / "cave.json").write_text(json.dumps({"finding": "It named 9 of 10 shadows.", "slug": "ignored"}))
    with served("/plato/cave"):
        assert "It named 9 of 10 shadows." in client.get("/").text


def test_calls_to_action_follow_the_routes(client):
    landing = client.get("/").text
    # /draw is served: the pad is on the landing page itself (draw first, then the reveal), plus a link to /draw.
    assert site.has_page(web.app, "/draw") and 'id="hero-draw"' in landing and 'id="skip-link"' in landing
    assert 'href="/draw">Draw something else' in landing and "TOTDraw" not in landing  # landing.js mounts it
    assert re.search(r'id="reveal"[^>]*hidden', landing) and landing.index('id="hero-draw"') < landing.index('id="chairs"')
    # Ask Socrates is served: hero button, its own band, and the nav (as an accent item).
    assert site.has_page(web.app, "/socrates") and landing.count('href="/socrates"') >= 3
    assert 'class="nav-accent"' in nav_links_block(client.get("/plato").text)
    assert "<!--#" not in landing and "{{" not in landing  # every template mark is filled in


def test_share_tags_and_card(client):
    for path in ("/", "/plato"):
        html = client.get(path, headers={"host": "example.org"}).text
        assert '<meta name="twitter:card" content="summary_large_image">' in html
        image = re.search(r'<meta property="og:image" content="([^"]+)"', html).group(1)
        assert image == "http://example.org/static/img/og-plato-chair.png"
        assert re.search(r'<meta property="og:title" content="[^"]+"', html)
    # Pages without their own tags get the default card.
    assert '<meta property="og:image" content="http://testserver/static/img/og-plato-chair.png">' in client.get("/lab").text
    card = web.HERE / "static" / "img" / "og-plato-chair.png"
    assert card.stat().st_size < 300 * 1024 and Image.open(card).size == (1200, 630)


def test_static_and_api_responses_are_untouched(client):
    r = client.get("/static/js/common.js")
    assert r.status_code == 200 and "site-data" in r.text and "{{BRAND}}" not in r.text
    assert client.get("/api/status").json()["features"]


def test_tour_is_plato_first_short_and_ends_at_draw():
    tour = (web.HERE / "static" / "js" / "tour.js").read_text()
    steps = tour.count("{ page:")
    assert 6 <= steps <= 10
    pages = re.findall(r"\{ page: '([^']*)'", tour)
    assert pages[0] == "/" and pages[1] == "/plato"
    assert "'/scorer" not in tour and "'/studio" not in tour  # the naming tools are no longer on the tour
    last = tour[tour.rindex("{ page:"):]
    assert "'/draw'" in last and "finish: true" in last

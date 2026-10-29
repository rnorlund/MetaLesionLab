"""The site shell (web/site.py) for the two sites one codebase serves (MLL_SITE, brand.py): each site has
only its own pages and APIs, its own nav and name, the sister link, share tags, and the Plato series cards
that appear only once their pages are served. The default site is Plato's Chair."""
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab import brand
from metalesionlab.web import app as web
from metalesionlab.web import site

REPO = Path(web.__file__).resolve().parents[2]
PAGES = {
    "plato": ["/", "/takehomes", "/draw", "/damaged", "/plato", "/plato/inside", "/plato/forms", "/plato/cave", "/plato/cratylus", "/plato/bird",
              "/plato/damage", "/plato/lifespan", "/plato/gallery", "/socrates"],
    "lingua": ["/", "/take", "/assess", "/scorer", "/studio", "/lab", "/lab/cut", "/lab/bilingual", "/ask", "/challenge"],
}
APIS = {  # GET endpoints that answer without data (200, or 503 while a data file is missing), never 404
    "plato": ["/api/plato", "/api/plato/inside", "/api/plato/forms", "/api/plato/cave", "/api/plato/cratylus", "/api/plato/bird",
              "/api/plato/damage", "/api/plato/lifespan", "/api/plato/gallery", "/api/draw/concepts", "/api/draw/status",
              "/api/socrates/status"],
    "lingua": ["/api/status", "/api/sets", "/api/scenes", "/api/lab/conditions", "/api/lab/human", "/api/lab/cut",
               "/api/lab/bilingual", "/api/ask/status", "/api/assess/config", "/api/pages"],
}
NAV = {
    # the Plato question first (Draw), damage second (Damaged AI, then Inside the model), the other experiments, the gallery last
    "plato": ["Home", "Take-homes", "Draw", "Damaged AI", "Inside the model", "Experiments", "Gallery", "Ask Socrates", "Code"],
    "lingua": ["Home", "Take the test", "Scorer", "Test Studio", "Model Lab", "Ask the Lab", "Code"],
}
OTHER = {"plato": "lingua", "lingua": "plato"}


@pytest.fixture
def client():
    return TestClient(web.app)  # the default site


def sites():
    return {key: TestClient(web.app_for(key)) for key in ("plato", "lingua")}


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


def nav_block(html: str) -> str:
    return re.search(r'<nav class="topnav" aria-label="Main">(.*?)</nav>', html, re.S).group(1)


def nav_links(html: str) -> list[str]:
    return re.findall(r'href="([^"]+)"', nav_block(html))


def nav_labels(html: str) -> list[str]:
    """The inline nav items, in order (the More menu's panel left out)."""
    inline = re.sub(r'<details class="nav-more.*?</details>', "", nav_block(html), flags=re.S)
    return [re.sub(r"<[^>]+>|↗", "", a).strip() for a in re.findall(r"<a [^>]*>(.*?)</a>", inline, re.S)]


def header(html: str) -> str:
    return re.search(r'<header class="topbar site-head">.*?</header>', html, re.S).group(0)


# --- one switch, two sites -------------------------------------------------------------------------

def test_the_default_site_is_platos_chair():
    assert web.app.state.site == "plato" == brand.DEFAULT_SITE
    assert web.app_for() is web.app and web.app_for("plato") is web.app


def test_site_key_reads_the_switch_and_refuses_typos(monkeypatch):
    monkeypatch.delenv("MLL_SITE", raising=False)
    assert brand.site_key() == "plato"
    monkeypatch.setenv("MLL_SITE", " Lingua ")
    assert brand.site_key() == "lingua" and brand.brand_for().name == brand.LINGUA.name
    assert brand.sister_of("lingua") is brand.PLATO and brand.sister_of("plato") is brand.LINGUA
    with pytest.raises(ValueError, match="MLL_SITE"):
        brand.site_key("lingau")


@pytest.mark.parametrize("key", ["plato", "lingua"])
def test_each_site_serves_only_its_own_pages_and_apis(key):
    c, other = sites()[key], OTHER[key]
    for path in PAGES[key]:
        assert c.get(path).status_code == 200, path
    for path in PAGES[other]:
        if path != "/":
            assert c.get(path).status_code == 404, path
    for path in APIS[key]:
        assert c.get(path).status_code in (200, 503), path
    for path in APIS[other]:
        assert c.get(path).status_code == 404, path
    for path in ("/api/site", "/api/guard", "/static/js/common.js"):  # shared by both
        assert c.get(path).status_code == 200, path


@pytest.mark.parametrize("key", ["plato", "lingua"])
def test_each_site_has_its_own_nav_on_every_page(key):
    c = sites()[key]
    seen = {path: nav_links(c.get(path).text) for path in PAGES[key]}
    first = seen["/"]
    assert all(links == first for links in seen.values()), seen  # the same nav on every page of the site
    assert nav_labels(c.get("/").text) == NAV[key]
    for path in PAGES[OTHER[key]]:  # and no link to the other site's pages
        if path != "/":
            assert f'href="{path}"' not in first, path


@pytest.mark.parametrize("key", ["plato", "lingua"])
def test_each_site_wears_its_own_name(key):
    c, b, other = sites()[key], brand.SITES[key], brand.SITES[OTHER[key]]
    for path in PAGES[key]:
        html = c.get(path).text
        assert f"<b>{site._esc(b.name)}</b>" in header(html), path
        assert json.loads(re.search(r'id="site-data">(.*?)</script>', html).group(1))["brand"] == b.name
        assert other.name not in header(html) and site._esc(other.name) not in header(html), path
        assert "{{" not in html and "<!--#" not in html, path  # every template mark is filled in
    info = c.get("/api/site").json()
    assert info["site"] == key and info["brand"] == b.name and info["tagline"] == b.tagline
    assert c.app.title == b.name


def test_plato_logo_and_favicons():
    s = sites()
    plato, lingua = s["plato"].get("/plato").text, s["lingua"].get("/lab").text
    assert 'class="brand-logo"' in header(plato) and 'class="brand-logo"' not in header(lingua)
    assert '<link rel="icon" href="/static/img/favicon-plato.svg"' in plato
    assert '<link rel="icon" href="/static/img/favicon.svg"' in lingua
    for c in s.values():
        assert c.get("/static/img/favicon-plato.svg").status_code == 200


@pytest.mark.parametrize("key", ["plato", "lingua"])
def test_sister_link_follows_the_setting(key, monkeypatch):
    c, other = sites()[key], brand.SITES[OTHER[key]]
    monkeypatch.delenv("MLL_SISTER_URL", raising=False)
    for path in ("/", PAGES[key][1]):
        html = c.get(path).text
        assert "Sister project" not in html and "sister-link" not in html, path
    assert c.get("/api/site").json()["sister"] is None
    monkeypatch.setenv("MLL_SISTER_URL", "https://other.example.org/")
    for path in PAGES[key]:
        html = c.get(path).text
        assert html.count("Sister project: " + site._esc(other.name)) == 1, path
        assert 'href="https://other.example.org/"' in html, path
    assert c.get("/api/site").json()["sister"]["name"] == other.name


def test_the_name_lives_in_brand_py(monkeypatch):
    """Renaming a site is a change to metalesionlab/brand.py. The Lingua name is spelled nowhere else; the Plato
    site is named after its first experiment, so that name appears as the experiment's, but the header, the
    titles and the site data all come from brand.py."""
    for folder, pattern in (("metalesionlab/web/pages", "*.html"), ("metalesionlab/web/static/js", "*.js"),
                            ("metalesionlab/web/static/css", "*.css"), ("metalesionlab", "**/*.py")):
        for f in (REPO / folder).glob(pattern):
            if f.name != "brand.py":
                assert brand.LINGUA.name not in f.read_text(), f
    s = sites()
    for key in ("plato", "lingua"):
        monkeypatch.setitem(brand.SITES, key, brand.Brand(key, f"Renamed {key}", f"Tagline {key}"))
        for path in PAGES[key][:4]:
            html = s[key].get(path).text
            assert f"<b>Renamed {key}</b>" in header(html) and f"Tagline {key}" in header(html), path
            assert f"Renamed {key}" in re.search(r"<title>(.*?)</title>", html).group(1) or path in ("/lab", "/scorer", "/studio")
            assert json.loads(re.search(r'id="site-data">(.*?)</script>', html).group(1))["brand"] == f"Renamed {key}"


def test_the_other_site_runs_in_its_own_process(tmp_path):
    """MLL_SITE=lingua in a fresh process: `app` is the Lingua site, with its own landing page and nav."""
    code = ("import json; from fastapi.testclient import TestClient; import metalesionlab.web.app as a; "
            "c = TestClient(a.app); h = c.get('/').text; "
            "print(json.dumps([a.app.state.site, c.get('/take').status_code, c.get('/plato').status_code, "
            "c.get('/draw').status_code, 'Not a medical test' in c.get('/take').text, h.count('class=\"series-card\"')]))")
    env = {**os.environ, "MLL_SITE": "lingua"}
    run = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120, cwd=REPO)
    assert run.returncode == 0, run.stderr[-2000:]
    assert json.loads(run.stdout.strip().splitlines()[-1]) == ["lingua", 200, 404, 404, True, 0]
    bad = subprocess.run([sys.executable, "-c", "import metalesionlab.web.app"], env={**os.environ, "MLL_SITE": "plat0"},
                         capture_output=True, text=True, timeout=120, cwd=REPO)
    assert bad.returncode != 0 and "MLL_SITE" in bad.stderr


# --- the Lingua landing page --------------------------------------------------------------------------

def test_lingua_landing_page_is_accurate_and_has_no_plato():
    c = sites()["lingua"]
    html = c.get("/").text
    main = re.search(r"<main.*?</main>", html, re.S).group(0)
    assert "16" in main and "languages measured" in main and "8</b><span>verified" in main
    for lang in ("English", "Spanish", "French", "Brazilian Portuguese", "German", "Turkish", "Polish", "Indonesian"):
        assert lang in main, lang
    assert "n = 100" in main and "100 new pictures" in main and "docs/replication.md" in main
    assert "+28 to +33" in main and "0.16%" in main and "57%" in main and "4<small> of 4" in main
    assert "Not a medical test" in main
    assert "Plato" not in main and "Socrates" not in main and "chair" not in main.lower()
    for path in ("/plato", "/draw", "/socrates"):  # no link to the sister site's pages (the sister link is a full URL)
        assert f'href="{path}' not in html, path
    lowered = re.sub(r"<[^>]+>", " ", main).lower()
    for word in ("diagnos", "screen", "impaired", "abnormal", "normal ", " risk", "healthy"):
        assert word not in lowered, word
    for path in ("/take", "/assess"):
        assert "Not a medical test" in c.get(path).text or "no diagnosis" in c.get(path).text, path
    assert 'property="og:image" content="http://testserver/static/img/og-tippa-lingua.jpg"' in html
    card = web.HERE / "static" / "img" / "og-tippa-lingua.jpg"
    assert card.stat().st_size < 300 * 1024 and Image.open(card).size == (1200, 630)


def test_tour_is_only_on_the_plato_site():
    s = sites()
    assert "data-tour-start" in header(s["plato"].get("/plato").text)
    for path in PAGES["lingua"]:
        html = s["lingua"].get(path).text
        assert "data-tour-start" not in header(html) and "/static/js/tour.js" not in html, path


# --- the Plato site's shell ------------------------------------------------------------------------

def test_more_menu_holds_the_series(client):
    html = client.get("/plato").text
    more = re.search(r'<details class="nav-more[^"]*">(.*?)</details>', html, re.S).group(1)
    for s in site.SERIES[1:]:
        if s["path"] == "/plato/inside":  # in the nav itself, so not repeated under More
            assert 'href="/plato/inside"' not in more
        elif site.has_page(web.app, s["path"]):
            assert f'href="{s["path"]}"' in more, s["path"]
        else:  # merged later (/plato/atlas, /plato/telephone): no link until its route exists
            assert f'href="{s["path"]}"' not in html, s["path"]
    assert "More from the lab" not in more
    # the damage experiments in a group of their own, after the rest of the series
    groups = re.split(r'<p class="nav-group">([^<]+)</p>', more)[1:]
    groups = dict(zip(groups[::2], groups[1::2]))
    assert list(groups) == ["The Plato series", "Damaged AI"]
    assert re.findall(r'href="([^"]+)"', groups["Damaged AI"]) == site.DAMAGED_PAGES
    assert not set(re.findall(r'href="([^"]+)"', groups["The Plato series"])) & set(site.DAMAGED_PAGES)


def current_labels(nav: str) -> list[str]:
    """The text of every link marked as the current page (a nav button's icon left out)."""
    return [re.sub(r"<[^>]+>", "", a).strip() for a in re.findall(r'<a [^>]*aria-current="page"[^>]*>(.*?)</a>', nav, re.S)]


def test_current_page_is_marked_once(client):
    for path, label in (("/", "Home"), ("/plato", "Experiments"), ("/draw", "Draw"), ("/socrates", "Ask Socrates")):
        nav = re.search(r'<nav class="topnav".*?</nav>', client.get(path).text, re.S).group(0)
        assert current_labels(nav) == [label], path
    nav = re.search(r'<nav class="topnav".*?</nav>', client.get("/plato/cave").text, re.S).group(0)
    assert current_labels(nav) == ["Experiments", "Name the shadow"]
    # the damage experiments belong to Damaged AI, not to Experiments
    nav = re.search(r'<nav class="topnav".*?</nav>', client.get("/damaged").text, re.S).group(0)
    assert current_labels(nav) == ["Damaged AI"]
    nav = re.search(r'<nav class="topnav".*?</nav>', client.get("/plato/damage").text, re.S).group(0)
    assert current_labels(nav) == ["Damaged AI", "Damage the painter"]
    # "Inside the model" is its own page once /plato/inside is served: the nav item, not Experiments, nor More
    html = client.get("/plato/inside").text
    nav = re.search(r'<nav class="topnav".*?</nav>', html, re.S).group(0)
    assert current_labels(nav) == ["Inside the model"]
    assert nav.count('href="/plato/inside"') == 1 and 'href="/plato#inside"' not in nav


def test_lingua_current_page_is_exact_for_the_lab():
    c = sites()["lingua"]
    nav = re.search(r'<nav class="topnav".*?</nav>', c.get("/lab/cut").text, re.S).group(0)
    assert re.findall(r'aria-current="page"[^>]*>([^<]+)', nav) == ["What can I cut?"]
    nav = re.search(r'<nav class="topnav".*?</nav>', c.get("/lab").text, re.S).group(0)
    assert re.findall(r'aria-current="page"[^>]*>([^<]+)', nav) == ["Model Lab"]


def test_header_keeps_page_chips():
    head = header(sites()["lingua"].get("/lab").text)
    assert 'id="sample-chip"' in head and "Muse Glimmer 30B" in head


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
    with served(path):
        landing = client.get("/").text
        assert landing.count('class="series-card"') == len(base) + 1
        assert new["question"] in landing and new["source"] in landing
        assert f'href="{path}"' in header(client.get("/socrates").text)
        info = client.get("/api/site").json()
        assert info["pages"][path] and path in [s["path"] for s in info["series"]]
    assert f'href="{path}"' not in client.get("/").text


def test_every_served_experiment_card_states_its_finding(client):
    """Every experiment served so far is finished: no card falls back to the "see what we found" link."""
    items = client.get("/api/site").json()["series"]
    assert len(items) >= 8 and items[1]["path"] == "/plato/inside"
    for item in items:
        assert item.get("finding"), item["path"]


def test_series_override_file_sets_the_finding(client, tmp_path, monkeypatch):
    monkeypatch.setattr(site, "SERIES_DIR", tmp_path)
    (tmp_path / "cave.json").write_text(json.dumps({"finding": "It named 9 of 10 shadows.", "slug": "ignored"}))
    assert "It named 9 of 10 shadows." in client.get("/").text


def test_calls_to_action_follow_the_routes(client):
    landing = client.get("/").text
    # /draw is served: the pad is on the landing page itself (draw first, then the reveal), plus a link to /draw.
    assert site.has_page(web.app, "/draw") and 'id="hero-draw"' in landing and 'id="skip-link"' in landing
    assert 'href="/draw">Draw something else' in landing and "TOTDraw" not in landing  # landing.js mounts it
    assert re.search(r'id="reveal"[^>]*hidden', landing) and landing.index('id="hero-draw"') < landing.index('id="chairs"')
    # Ask Socrates is served: hero button, its own band, and the nav (as an accent item).
    assert site.has_page(web.app, "/socrates") and landing.count('href="/socrates"') >= 3
    assert re.search(r'<a href="/socrates" class="nav-accent nav-btn"', header(client.get("/plato").text))
    assert "<!--#" not in landing and "{{" not in landing  # every template mark is filled in
    for path in ("/lab", "/take", "/ask", "/challenge", "/studio", "/scorer", "/assess"):  # nothing of the sister site's
        assert f'href="{path}"' not in landing and f'href="{path}/' not in landing, path


def test_share_tags_and_card(client):
    for path in ("/", "/plato"):
        html = client.get(path, headers={"host": "example.org"}).text
        assert '<meta name="twitter:card" content="summary_large_image">' in html
        image = re.search(r'<meta property="og:image" content="([^"]+)"', html).group(1)
        assert image == "http://example.org/static/img/og-plato-chair.png"
        assert re.search(r'<meta property="og:title" content="[^"]+"', html)
    # Pages without their own tags get the site's default card.
    assert '<meta property="og:image" content="http://testserver/static/img/og-plato-chair.png">' in client.get("/draw").text
    lingua = sites()["lingua"].get("/lab").text
    assert '<meta property="og:image" content="http://testserver/static/img/og-tippa-lingua.jpg">' in lingua
    card = web.HERE / "static" / "img" / "og-plato-chair.png"
    assert card.stat().st_size < 300 * 1024 and Image.open(card).size == (1200, 630)


def test_static_and_api_responses_are_untouched(client):
    r = client.get("/static/js/common.js")
    assert r.status_code == 200 and "site-data" in r.text and "{{BRAND}}" not in r.text
    assert client.get("/api/plato").json()["core"]
    assert sites()["lingua"].get("/api/status").json()["features"]


TOUR = web.HERE / "static" / "js" / "tour.js"
FACES = ("neutral", "questioning", "pointing")


def _tour_steps() -> list[str]:
    tour = TOUR.read_text()
    block = tour[tour.index("var STEPS = ["):tour.index("\n  ];", tour.index("var STEPS = ["))]
    return ["{ page:" + s for s in block.split("{ page:")[1:]]


def test_tour_is_plato_first_short_and_ends_at_draw():
    tour = TOUR.read_text()
    steps = tour.count("{ page:")
    assert 6 <= steps <= 10
    pages = re.findall(r"\{ page: '([^']*)'", tour)
    assert pages[:3] == ["/", "/", "/plato"]  # the blind draw, the chairs, then the experiment
    assert "'/scorer" not in tour and "'/studio" not in tour and "'/lab'" not in tour  # the sister site's pages
    last = tour[tour.rindex("{ page:"):]
    assert "'/draw'" in last and "finish: true" in last


def test_tour_is_guided_by_socrates_in_his_own_words():
    steps = _tour_steps()
    assert len(steps) == TOUR.read_text().count("{ page:")
    for s in steps:
        assert re.search(r"face: '(neutral|questioning|pointing)'", s), s[:60]
        assert re.search(r"\bq: ", s) and re.search(r"\bp: ", s), s[:60]
    # a question first: each step's question ends in a question mark (or is one, for the blind draw)
    questions = [m for s in steps for m in re.findall(r"\bq: '([^']+)'", s)]
    assert questions and all("?" in x for x in questions)
    assert questions[0] == "Before I tell you anything: what is a chair? Draw one, and we’ll see."
    assert "The machine drew the same chair sixteen times. Is that wisdom, or habit?" in questions
    for face in FACES:  # the portraits: Muse Image doodles, small
        f = web.HERE / "static" / "img" / "socrates" / f"socrates-{face}.webp"
        assert f.exists() and f.stat().st_size < 40 * 1024, f
        assert Image.open(f).size == (256, 256)
    tour = TOUR.read_text()
    assert "drawn by Meta’s Muse Image" in tour
    # the last step offers "Ask me yourself" (and the examination)
    last = steps[-1]
    assert "['Ask me yourself', '/socrates']" in last and "/socrates?mode=examine" in last


def test_tour_lines_are_written_in_advance_and_every_number_is_in_the_docs():
    tour = TOUR.read_text()
    assert "fetch(" not in tour and "T.api(" not in tour and "/api/" not in tour  # no AI (or any) calls
    docs = " ".join(p.read_text() for p in (REPO / "docs").glob("plato*.md"))
    lines = [x for s in _tour_steps() for x in re.findall(r"'((?:[^'\\]|\\.)*)'", s)
             if not re.match(r"^[#/.]|^(?:neutral|questioning|pointing)$", x)]
    numbers = {n for line in lines for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", line)}
    assert {"0.13", "0.36", "16", "35", "84"} <= numbers
    for n in numbers:
        assert re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", docs), f"{n} is not in docs/plato*.md"


def test_tour_keeps_the_blind_draw():
    steps = _tour_steps()
    first = steps[0]
    assert "target: '#hero-draw'" in first and "blind: true" in first  # Socrates asks for a chair first
    assert "revealChairs()" in steps[1] and "target: '#chairs'" in steps[1]  # the chairs only after that
    landing = "\n".join(line for line in (web.HERE / "static" / "js" / "landing.js").read_text().splitlines()
                        if not line.strip().startswith("//"))
    assert "reveal('tour')" not in landing  # starting the tour no longer shows the chairs by itself
    tour = TOUR.read_text()
    assert "tot-draw-seen" in tour and "if (!step.blind) markSeen()" in tour  # later drawings aren't blind


def test_tour_is_keyboard_and_motion_friendly():
    tour = TOUR.read_text()
    for key in ("'Escape'", "'ArrowRight'", "'ArrowLeft'"):
        assert key in tour
    assert "ui.card.focus(" in tour and "lastFocus.focus()" in tour and "role: 'dialog'" in tour
    css = (web.HERE / "static" / "css" / "tour.css").read_text()
    reduced = css[css.index("prefers-reduced-motion"):]
    assert ".tour-face.pop { animation: none; }" in reduced[:reduced.index("}\n") + 60]
    assert "@media (max-width: 640px)" in css and ".tour-face { width: 48px" in css


# --- the splash on Plato's landing page ------------------------------------------------------------

def test_splash_is_on_the_plato_landing_only(client):
    landing = client.get("/").text
    assert re.search(r'<script src="/static/js/splash\.js(\?v=\d+)?"></script>', landing)
    head = landing[:landing.index("</head>")]
    assert "splash-on" in head and "nosplash=1" in head and "prefers-reduced-motion" in head
    assert "tot-tour-step" in head and "pc-splash-seen" in head and "sessionStorage" in head
    assert re.search(r"try \{.*\} catch \(e\)", head, re.S)  # storage that throws means no splash, not a broken page
    for path in PAGES["plato"][1:]:
        assert "splash" not in client.get(path).text, path
    lingua = sites()["lingua"].get("/").text
    assert "splash" not in lingua


def test_splash_assets_are_small_webp_and_never_muse_images_chairs():
    folder = web.HERE / "static" / "img" / "splash"
    files = sorted(folder.iterdir())
    assert files and all(f.suffix == ".webp" for f in files)
    assert sum(f.stat().st_size for f in files) < 400 * 1024
    assert all(Image.open(f).format == "WEBP" for f in files)
    names = {f.stem for f in files}
    assert not any(n.startswith(("muse", "chair_muse", "hero")) for n in names)  # the 16 alike chairs stay for the reveal
    js = (web.HERE / "static" / "js" / "splash.js").read_text()
    assert "/static/img/splash/" in js and "/static/img/plato/" not in js and "/static/img/draw/" not in js
    assert "Skip" in js and "keydown" in js and "pc-splash-seen" in js
    assert "Republic 515c" in js and "Republic 596a" in js
    passages = (REPO / "public_data" / "plato_passages.json").read_text()  # quoted only from verified passages
    for quote in ("To them, I said, the truth would be literally nothing but the shadows of the images.",
                  "Whenever a number of individuals have a common name, we assume them to have also a corresponding idea or form"):
        assert quote in js and quote in passages


def test_static_links_carry_a_version(client):
    html = client.get("/").text
    links = re.findall(r'(?:href|src)="(/static/[^"]+\.(?:css|js)[^"]*)"', html)
    assert links and all("?v=" in l for l in links), links


def test_logo_has_an_intrinsic_size(client):
    html = client.get("/?nosplash=1").text
    assert re.search(r'<svg class="brand-logo"[^>]*width="38" height="38"', html)

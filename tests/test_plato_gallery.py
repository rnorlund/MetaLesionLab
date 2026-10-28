"""The gallery (/plato/gallery) and the "From the lab" band: the curated data file, its pictures, the route, the
band on every Plato page (and only there), and the size budget."""
import importlib.util
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab.web import app as web
from metalesionlab.web import plato_gallery_routes as R
from metalesionlab.web import site

REPO = Path(web.__file__).resolve().parents[2]
DATA = json.loads(R.DATA.read_text())
ITEMS = DATA["items"]
GALLERY_DIR = web.HERE / "static" / "img" / "gallery"
DOCS = "\n".join(p.read_text() for p in sorted((REPO / "docs").glob("plato*.md")))
FIELDS = {"id", "title", "caption", "category", "link", "thumb", "alt", "credit"}
PLATO_PAGES = ["/", "/draw", "/plato", "/plato/inside", "/plato/forms", "/plato/cave", "/plato/cratylus", "/plato/bird",
               "/plato/damage", "/plato/lifespan", "/plato/telephone", "/plato/atlas", "/socrates"]
LINGUA_PAGES = ["/", "/take", "/assess", "/scorer", "/studio", "/lab", "/lab/cut", "/lab/bilingual", "/ask", "/challenge"]


def plato():
    return TestClient(web.app_for("plato"))


def local(url: str) -> Path:
    assert url.startswith("/static/"), url
    return web.HERE / "static" / url[len("/static/"):]


def test_items_have_every_field_and_short_text():
    assert 30 <= len(ITEMS) <= 40
    assert DATA["categories"] == R.CATEGORIES == ["Watch it degrade", "The Forms", "Shadows", "Words and shapes", "Growing up"]
    ids = [i["id"] for i in ITEMS]
    assert len(ids) == len(set(ids)) and all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) for i in ids)
    for it in ITEMS:
        assert FIELDS <= set(it), it["id"]
        assert it["category"] in R.CATEGORIES, it["id"]
        assert len(it["title"].split()) <= 8, it["id"]
        assert len(it["caption"].split()) <= 30, it["id"]
        assert len(it["alt"]) >= 40, it["id"]  # alt text describes the picture, not just names it
        assert ("image" in it) != ("sequence" in it), it["id"]  # a still or a sequence
        if "sequence" in it:
            frames = it["sequence"]["frames"]
            assert len(frames) >= 3 and all(f["src"] and f["label"] for f in frames), it["id"]
            if any("pair" in f for f in frames):
                assert all("pair" in f for f in frames) and len(it["sequence"].get("pair_labels", [])) == 2, it["id"]
    # degradation sequences lead, and every category has something in it
    assert ITEMS[0]["category"] == "Watch it degrade"
    assert {i["category"] for i in ITEMS} == set(R.CATEGORIES)
    assert sum(i["category"] == "Watch it degrade" for i in ITEMS) >= 10


def test_every_number_in_a_caption_or_label_is_in_the_docs():
    number = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
    for it in ITEMS:
        texts = [it["caption"]] + [f["label"] for f in (it.get("sequence") or {}).get("frames", [])]
        for text in texts:
            for n in number.findall(text):
                n = n.rstrip(",")
                assert n in DOCS, (it["id"], n)


def test_damage_is_the_ais_and_neurology_is_only_an_analogy():
    for it in ITEMS:
        text = (it["title"] + " " + it["caption"]).lower()
        for word in ("patient", "dementia", "aphasia", "brain", "stroke", "disease", "diagnos"):
            assert word not in text, (it["id"], word)
    credits = " ".join(DATA["credits"])
    assert "analog" in credits and "Quick, Draw!" in credits and "CC BY 4.0" in credits
    for name in ("OpenRAIL++-M", "Muse Image", "Muse Glimmer", "Muse Spark", "Janus-Pro"):
        assert name in credits, name


def test_pictures_exist_are_webp_and_never_childrens():
    referenced = set()
    for it in ITEMS:
        for url in R.pictures(it):
            path = local(url)
            assert path.is_file(), (it["id"], url)
            assert path.suffix == ".webp" and Image.open(path).format == "WEBP", url
            assert not re.search(r"kid|child|lifespan/children", url, re.I), url
            referenced.add(path.resolve())
    for path in GALLERY_DIR.iterdir():  # nothing in the gallery folder that no item shows
        assert path.resolve() in referenced, path.name
    spec = importlib.util.spec_from_file_location("plato_gallery_export", REPO / "scripts" / "plato_gallery_export.py")
    export = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(export)
    for rel in ("lifespan/kiddraw_raw/chair/0.png", "lifespan/children/x.png"):  # the export refuses to open them
        with pytest.raises(ValueError, match="children"):
            export.src(rel)


def test_picture_sizes_and_the_budget():
    total = sum(p.stat().st_size for p in GALLERY_DIR.glob("*"))
    assert total < 4 * 1024 * 1024, total
    for it in ITEMS:
        tw, th = Image.open(local(it["thumb"])).size
        if "sequence" in it:  # a sprite: one equal cell per frame
            n = len(it["sequence"]["frames"])
            assert tw % n == 0 and 120 <= th <= 340, (it["id"], tw, th, n)
        else:
            assert th <= 340 and tw <= 760, (it["id"], tw, th)
            assert Image.open(local(it["image"])).size[0] <= 1200, it["id"]


def test_links_point_at_served_pages_and_real_anchors():
    c = plato()
    for it in ITEMS:
        path, _, anchor = it["link"].partition("#")
        r = c.get(path)
        assert r.status_code == 200, it["link"]
        if anchor:
            assert f'id="{anchor}"' in r.text, it["link"]


def test_route_and_api_on_the_plato_site_only():
    c = plato()
    r = c.get("/plato/gallery")
    assert r.status_code == 200 and "The gallery" in r.text and 'id="view"' in r.text and "<dialog" in r.text
    assert "{{ORIGIN}}" not in r.text and 'data-origin="http' in r.text  # share links use the site's own origin
    assert 'id="lab-strip"' not in r.text  # the gallery doesn't show the band about itself
    d = c.get("/api/plato/gallery")
    assert d.status_code == 200 and "max-age" in d.headers.get("cache-control", "")
    body = d.json()
    assert len(body["items"]) == len(ITEMS) and body["categories"] == R.CATEGORIES
    assert all(i["thumb_size"] and len(i["thumb_size"]) == 2 for i in body["items"])
    for path in ("/static/js/plato_gallery.js", "/static/css/plato_gallery.css", "/static/js/gallery-strip.js",
                 "/static/css/gallery-strip.css"):
        assert c.get(path).status_code == 200, path
    lingua = TestClient(web.app_for("lingua"))
    assert lingua.get("/plato/gallery").status_code == 404 and lingua.get("/api/plato/gallery").status_code == 404
    assert "plato_gallery_routes" in web.SITE_ROUTERS["plato"]
    assert "plato_gallery_routes" not in web.SITE_ROUTERS["lingua"]


def test_items_with_missing_pictures_are_left_out(tmp_path):
    bad = dict(ITEMS[0], id="missing", thumb="/static/img/gallery/nope.webp")
    f = tmp_path / "g.json"
    f.write_text(json.dumps({**DATA, "items": [ITEMS[1], bad]}))
    assert [i["id"] for i in R.load(f)["items"]] == [ITEMS[1]["id"]]
    assert R.load(tmp_path / "absent.json") is None


def test_the_band_is_on_every_plato_page_above_the_footer():
    c = plato()
    for path in PLATO_PAGES:
        html = c.get(path).text
        assert html.count('id="lab-strip"') == 1, path
        assert re.search(r'<script src="/static/js/gallery-strip\.js\?v=\d+" defer></script>', html), path
        assert re.search(r'<link rel="stylesheet" href="/static/css/gallery-strip\.css\?v=\d+">', html[:html.index("</head>")]), path
        strip = html.index('id="lab-strip"')
        assert html.rindex("</main>") < strip, path  # after the content: not over the drawing pad or the results
        for foot in ('class="footnote"', 'class="lfoot"', 'class="site-foot"'):
            if foot in html:
                assert strip < html.index(foot), (path, foot)
    assert "splash" not in c.get("/plato/telephone").text  # the band brings nothing of the landing's opening


def test_the_band_is_never_on_the_lingua_site():
    c = TestClient(web.app_for("lingua"))
    for path in LINGUA_PAGES:
        html = c.get(path).text
        assert "lab-strip" not in html and "gallery-strip" not in html, path
    assert not any(n["href"] == "/plato/gallery" for n in site.NAV["lingua"])


def test_gallery_is_in_the_plato_nav():
    html = plato().get("/plato/gallery").text
    nav = re.search(r'<nav class="topnav" aria-label="Main">(.*?)</nav>', html, re.S).group(1)
    assert re.search(r'<a href="/plato/gallery" aria-current="page">Gallery</a>', nav)
    assert '<a href="/plato" aria-current="page">' not in nav  # Experiments is not current on the gallery


def test_band_and_gallery_scripts_respect_motion_keys_and_the_blind_draw():
    strip = (web.HERE / "static" / "js" / "gallery-strip.js").read_text()
    assert "prefers-reduced-motion" in strip and "requestAnimationFrame" in strip
    assert "mouseenter" in strip and "focusin" in strip and "touchstart" in strip and "data-lab-pause" in strip
    assert "tot-draw-seen" in strip and "tot:revealed" in strip  # the landing page's drawing stays blind
    assert "loading: lazy === false ? null : 'lazy'" in strip and "'aria-hidden': clone ? 'true' : null" in strip
    page = (web.HERE / "static" / "js" / "plato_gallery.js").read_text()
    assert "ArrowLeft" in page and "ArrowRight" in page and "showModal" in page and "x.com/intent/post" in page
    assert "location.hash" in page and "replaceState" in page
    css = (web.HERE / "static" / "css" / "gallery-strip.css").read_text()
    assert "position: fixed" not in css and "position: sticky" not in css  # it sits at the page end
    assert "clamp(16px, 4vw, 96px)" in css and "prefers-reduced-motion" in css
    gcss = (web.HERE / "static" / "css" / "plato_gallery.css").read_text()
    assert "auto-fill" in gcss and "clamp(16px, 4vw, 96px)" in gcss

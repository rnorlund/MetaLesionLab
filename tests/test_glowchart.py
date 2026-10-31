"""Glowing charts (static/js/glowchart.js, static/css/glowchart.css): the layer-by-layer chart on the home and chair
pages is drawn live from a slim endpoint instead of a static picture, in the checked chart colours, tokens only."""
import re

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web

STATIC = web.HERE / "static"
JS = (STATIC / "js" / "glowchart.js").read_text()
CSS = (STATIC / "css" / "glowchart.css").read_text()
APP_CSS = (STATIC / "css" / "app.css").read_text()


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


def test_the_layer_endpoint_is_slim_and_complete(client):
    r = client.get("/api/plato/inside/layers")
    assert r.status_code == 200 and len(r.content) < 40_000  # the full page data is about 450 KB
    d = r.json()
    n = d["n_layers"]
    assert n == 52 and 1 <= d["collapse_layer"] <= n and len(d["things"]) == 35
    assert len(d["mean"]["muse"]) == len(d["mean"]["people"]) == n
    assert all(len(t["muse"]) == len(t["people"]) == n for t in d["things"])
    assert d["mean"]["muse"][-1] < 0.2 < d["mean"]["people"][-1]  # the AI's doodles end as one picture; people's don't


@pytest.mark.parametrize("path", ["/", "/plato"])
def test_home_and_chair_pages_draw_it_live(client, path):
    page = client.get(path).text
    assert 'data-glow="layers"' in page and "spread_by_layer.webp" not in page
    assert page.count("/static/js/glowchart.js") == 1 and page.count("/static/css/glowchart.css") == 1
    chart = re.search(r'<div class="glow-chart" data-glow="layers"[^>]*aria-label="([^"]+)"', page)
    assert chart and "52 stages" in chart.group(1)


def test_checked_chart_colours_on_both_themes():
    light, dark = APP_CSS.split(':root[data-theme="dark"] {', 1)
    for name in ("--chart-muse", "--chart-people", "--chart-you"):
        assert re.search(name + r":\s*#[0-9A-F]{6}", light) and re.search(name + r":\s*#[0-9A-F]{6}", dark), name
    assert "tok('--chart-muse')" in JS and "tok('--chart-people')" in JS


def test_tokens_only_and_motion_respected():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", CSS)
    assert not re.search(r"font-size:\s*\d", CSS)
    assert "prefers-reduced-motion: reduce" in JS and "IntersectionObserver" in JS


@pytest.mark.parametrize("path", ["/draw", "/", "/plato/clock"])
def test_draw_pages_load_the_glowing_charts_before_the_draw_script(client, path):
    page = client.get(path).text
    assert page.count("/static/js/glowchart.js") == 1 and page.count("/static/css/glowchart.css") == 1
    assert page.index("/static/js/glowchart.js") < page.index("/static/js/draw.js")


def test_draw_results_use_one_glowing_line_each_and_no_flat_map():
    draw = (STATIC / "js" / "draw.js").read_text()
    assert draw.count("GlowChart.swarm(") == 2 and "map-chart" not in draw and "mapChart" not in draw
    assert "'The AI’s usual ' + c.label" in draw and "'A typical person’s ' + c.label" in draw
    assert "function swarm(el, o)" in JS and "tinted(row.sprite.src" in JS


SKIN = (STATIC / "js" / "glowskin.js").read_text()
PLATO_PAGES = ["/", "/plato", "/damaged", "/takehomes", "/draw", "/socrates", "/plato/clock", "/plato/bird", "/plato/cave",
               "/plato/forms", "/plato/lifespan", "/plato/inside", "/plato/glimmer", "/plato/scale", "/plato/atlas"]


@pytest.mark.parametrize("path", PLATO_PAGES)
def test_every_plato_page_gets_the_glow_skin_once(client, path):
    page = client.get(path).text
    assert page.count("/static/js/glowskin.js") == 1 and page.count("/static/css/glowchart.css") == 1, path


def test_the_skin_lights_coloured_marks_only_and_keeps_straight_lines_visible():
    from metalesionlab.web import site
    once = site.add_glow("<head></head>")
    assert site.add_glow(once) == once and once.count("glowskin.js") == 1
    assert ':root[data-theme="dark"] svg .gl { filter: url(#pc-glow); }' in CSS  # dark theme only
    assert "s > 0.4" in SKIN  # saturated colours only: grids, axes and text stay flat
    assert "bb.width < 1 || bb.height < 1" in SKIN  # a filter sized from a flat box would hide the line
    assert "header, nav, .sp-stage, .splash" in SKIN  # icons and the intro are left alone

"""Inside the model (/plato/inside): the shipped data's schema and its agreement with the published statistics, the
map maker's helpers, the page and API routes, and the page's size budget. Offline: no model, no API."""
import importlib.util
import json
import re
import statistics
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab import brand
from metalesionlab.web import app as web
from metalesionlab.web import plato_inside_routes

REPO = Path(web.__file__).resolve().parents[2]
DATA = web.HERE / "data" / "plato_inside.json"
PUBLIC = REPO / "public_data" / "plato_glimmer_inside.json"
STATIC = web.HERE / "static"
SPRITES = STATIC / "img" / "plato_inside"
N_LAYERS = 52


@pytest.fixture
def client():
    plato_inside_routes._cache.clear()
    return TestClient(web.app)


@pytest.fixture(scope="module")
def data():
    return json.loads(DATA.read_text())


def _export():
    spec = importlib.util.spec_from_file_location("plato_inside_web_export", REPO / "scripts" / "plato_inside_web_export.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- the shipped data -----------------------------------------------------------------------------------

def test_data_is_compact_and_derived_only(data):
    text = DATA.read_text()
    assert DATA.stat().st_size <= 600 * 1024
    assert "/Users/" not in text and "/home/" not in text
    assert data["n_layers"] == N_LAYERS and len(data["concepts"]) == 35
    assert "Quick, Draw!" in data["attribution"] and "CC BY 4.0" in data["attribution"]
    for c in data["concepts"]:
        assert set(c) == {"key", "label", "n", "collapse_layer", "name_layer", "named", "spread", "pictures", "xy", "sprite"}


def test_chair_comes_first_then_alphabetical(data):
    labels = [c["label"] for c in data["concepts"]]
    assert labels[0] == "chair" and labels[1:] == sorted(labels[1:])


def test_every_layer_has_a_position_for_every_picture(data):
    for c in data["concepts"]:
        n = c["n"]["muse"] + c["n"]["people"]
        assert c["n"]["muse"] == c["n"]["people"] in (12, 16), c["key"]
        assert len(c["pictures"]) == n and len(c["xy"]) == N_LAYERS
        for layer in c["xy"]:
            assert len(layer) == 2 * n and all(isinstance(v, int) and 0 <= v <= 1000 for v in layer)
        # a later layer never jumps the whole map: the mean step is a small part of the frame
        xy = np.array(c["xy"], dtype=float).reshape(N_LAYERS, n, 2)
        steps = np.linalg.norm(np.diff(xy, axis=0), axis=2).mean(axis=1)
        assert steps.max() < 200, (c["key"], steps.max())


def test_pictures_carry_answers_and_word_lens_layers(data):
    for c in data["concepts"]:
        n = c["n"]["muse"]
        assert c["named"]["muse"] == sum(p["ok"] for p in c["pictures"][:n])
        assert c["named"]["people"] == sum(p["ok"] for p in c["pictures"][n:])
        for p in c["pictures"]:
            assert isinstance(p["said"], str) and len(p["said"]) <= 40
            assert p["lens"] is None or (p["ok"] and 1 <= p["lens"] <= N_LAYERS)
        lens = [p["lens"] for p in c["pictures"][:n] if p["lens"]]
        if lens:
            assert statistics.median(lens) == c["name_layer"]["muse"], c["key"]


def test_collapse_layer_follows_the_rule_on_the_shipped_spreads(data):
    for c in data["concepts"]:
        m, p = c["spread"]["muse"], c["spread"]["people"]
        assert len(m) == len(p) == N_LAYERS and all(0 < v < 1.2 for v in m + p)
        ratios = [a / b for a, b in zip(m, p)]
        rule = next((k + 1 for k in range(N_LAYERS) if all(r < 0.5 for r in ratios[k:])), None)
        assert rule == c["collapse_layer"], c["key"]


def test_agrees_with_the_published_statistics(data):
    pub = json.loads(PUBLIC.read_text())
    by_key = {c["key"]: c for c in pub["concepts"]}
    for c in data["concepts"]:
        q = by_key[c["key"]]
        assert c["label"] == q["label"] and c["collapse_layer"] == q["collapse_layer"]
        assert c["name_layer"] == q["name_appears_layer"]
        for stage, i in (("L13", 12), ("L26", 25), ("L39", 38), ("L46", 45), ("L52", 51)):
            assert abs(c["spread"]["muse"][i] - q["spread"][stage]["muse"]) <= 1.5e-3, (c["key"], stage)
            assert abs(c["spread"]["people"][i] - q["spread"][stage]["people"]) <= 1.5e-3, (c["key"], stage)
    s, ps = data["summary"], pub["summary"]
    assert s["median_collapse_layer"] == ps["median_collapse_layer"] == 36
    assert (s["earliest_collapse"], s["latest_collapse"]) == (30, 44) and s["never_collapse"] == ["person"]
    collapsed = [c for c in data["concepts"] if c["collapse_layer"]]
    assert s["n_with_both"] == len(collapsed) == 34
    assert s["collapse_at_or_before_name"] == sum(c["collapse_layer"] <= c["name_layer"]["muse"] for c in collapsed)
    assert [t["ratio"] for t in s["other_thresholds"]] == [0.4, 0.6]
    nb = s["same_thing_neighbour"]
    assert len(nb["muse"]) == len(nb["people"]) == N_LAYERS and all(0 <= v <= 1 for v in nb["muse"] + nb["people"])
    kept = data["map"]["spread_kept"]
    assert 0.7 <= kept["muse"] <= 1 and 0.7 <= kept["people"] <= 1


def test_sprites_match_the_pictures(data):
    for c in data["concepts"]:
        f = SPRITES / c["sprite"]
        assert f.suffix == ".webp" and f.stat().st_size <= 60 * 1024, c["sprite"]
        with Image.open(f) as im:
            assert im.size == (56 * len(c["pictures"]), 56) and im.mode == "RGBA"
    assert {f.name for f in SPRITES.iterdir()} == {c["sprite"] for c in data["concepts"]}


# --- the map maker ---------------------------------------------------------------------------------------

def test_mds_recovers_a_flat_layout_and_procrustes_a_rotation():
    ex = _export()
    rng = np.random.default_rng(0)
    pts = rng.normal(size=(20, 2))
    d = np.sqrt(((pts[:, None] - pts[None]) ** 2).sum(-1))
    w = np.ones_like(d)
    np.fill_diagonal(w, 0)
    x = ex.smacof(d, w, ex.classical_mds(d), None, 0.0)
    got = np.sqrt(((x[:, None] - x[None]) ** 2).sum(-1))
    assert np.abs(got - d).max() < 1e-3
    t = 0.7
    rot = np.array([[np.cos(t), -np.sin(t)], [np.sin(t), np.cos(t)]])
    q = ex.procrustes(pts @ rot, pts)
    assert np.allclose(pts @ rot @ q, pts, atol=1e-9)


def test_collapse_rule_and_spread():
    ex = _export()
    assert ex.collapse_layer([0.6, 0.2, 0.1], [0.5, 0.5, 0.5]) == 2
    assert ex.collapse_layer([0.6, 0.2, 0.3], [0.5, 0.5, 0.5]) is None  # must stay under half to the end
    assert ex.collapse_layer([0.28, 0.28, 0.28], [0.5, 0.5, 0.5], ratio=0.6) == 1
    u = np.eye(3)
    assert ex.spread(u) == pytest.approx(1.0)
    assert ex.map_spread(u) == pytest.approx(1.0)  # chord^2 / 2 = cosine distance for unit vectors


# --- the page ----------------------------------------------------------------------------------------------

def test_page_renders_with_the_site_header(client):
    r = client.get("/plato/inside")
    assert r.status_code == 200 and 'id="map"' in r.text and 'id="layer"' in r.text
    assert r.text.count('<header class="topbar site-head">') == 1
    assert "{{BRAND}}" not in r.text and brand.BRAND in r.text
    api = client.get("/api/plato/inside")
    assert api.status_code == 200 and len(api.json()["concepts"]) == 35


def test_missing_data_is_a_friendly_503(client, monkeypatch, tmp_path):
    monkeypatch.setattr(plato_inside_routes, "DATA", tmp_path / "none.json")
    assert client.get("/api/plato/inside").status_code == 503
    (tmp_path / "bad.json").write_text('{"concepts": []}')
    monkeypatch.setattr(plato_inside_routes, "DATA", tmp_path / "bad.json")
    assert client.get("/api/plato/inside").status_code == 503


def test_page_is_keyboard_and_motion_friendly_and_states_its_caveats():
    html = (web.HERE / "pages" / "plato_inside.html").read_text()
    script = (STATIC / "js" / "plato_inside.js").read_text()
    css = (STATIC / "css" / "plato_inside.css").read_text()
    rng = re.search(r'<input type="range" id="layer"[^>]*>', html).group(0)
    assert 'min="1"' in rng and 'max="52"' in rng and 'aria-label=' in rng
    for bid in ("play", "prev", "next"):
        assert re.search(rf'<button type="button" class="[^"]*" id="{bid}" aria-label="[^"]+"', html), bid
    assert "prefers-reduced-motion" in script and "prefers-reduced-motion" in css
    assert "after seeing the data" in html and "logit lens" in html and "not when the idea" in html
    assert "aria-valuetext" in script


def test_page_assets_stay_under_budget():
    html = (web.HERE / "pages" / "plato_inside.html").read_text()
    script = (STATIC / "js" / "plato_inside.js").read_text()
    css = STATIC / "css" / "plato_inside.css"
    for ref in re.findall(r'(?:href|src)="(/static/[^"]+)"', html):
        assert (web.HERE / ref.lstrip("/")).is_file(), ref
    sprites = sum(f.stat().st_size for f in SPRITES.iterdir())
    assert sprites <= 1024 * 1024
    assert sprites + len(html) + len(script) + css.stat().st_size <= 1.5 * 1024 * 1024
    assert "fetch(" not in script and "localStorage" not in script  # replays shipped data; stores nothing

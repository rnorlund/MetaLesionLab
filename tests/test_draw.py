"""Draw a chair (/draw), offline: stroke rendering, percentiles, the shipped reference data, the route's
limits and lazy model loading. A fake embedder stands in for DINOv2, so nothing is downloaded."""
import hashlib
import json
import logging
import subprocess
import sys

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab import draw, draw_fetch
from metalesionlab.plato import ink_crop, render_strokes
from metalesionlab.web import app as web
from metalesionlab.web import draw_routes
from metalesionlab.web import guard as G
from metalesionlab.web.limits import DailyLimiter

DATA = web.HERE / "data"
CHAIR = [[[10, 10], [5, 60]], [[10, 50], [40, 40]], [[50, 50], [40, 75]], [[10, 10], [60, 75]]]


# --- strokes -> picture --------------------------------------------------------------------------

def test_normalize_follows_the_quickdraw_recipe():
    out = draw.normalize_strokes([[[100, 300, 500], [200, 200, 200]], [[100, 100], [200, 400]]])
    xs = [x for s in out for x in s[0]]
    ys = [y for s in out for y in s[1]]
    assert min(xs) == 0 and min(ys) == 0 and max(max(xs), max(ys)) == 255  # aligned, longest side 0-255
    assert all(isinstance(v, int) for v in xs + ys)
    assert out[0] == [[0, 255], [0, 0]]  # resampled at 1 px, then RDP drops the straight line's middle
    assert draw.normalize_strokes([[[5], [5]], [[0, 10], [0, 10]]])[0] == [[128], [128]]  # a dot survives


def test_normalize_ignores_scale_and_position():
    small = draw.normalize_strokes(CHAIR)
    big = draw.normalize_strokes([[[3 * x + 400 for x in s[0]], [3 * y + 7 for y in s[1]]] for s in CHAIR])
    assert [len(s[0]) for s in small] == [len(s[0]) for s in big]
    assert all(np.abs(np.array(a) - np.array(b)).max() <= 1 for a, b in zip(small, big))  # rounding at .5 only


def test_render_is_the_experiments_pipeline():
    """Strokes already in Quick, Draw! form come out exactly as the experiment rendered people's drawings."""
    qd = [[[0, 255], [0, 0]], [[0, 0], [0, 200]], [[255, 255], [0, 200]]]
    assert draw.normalize_strokes(qd) == qd
    a = np.asarray(draw.render(qd))
    b = np.asarray(ink_crop(render_strokes(qd)))
    assert a.shape == (256, 256, 3) and np.array_equal(a, b) and a.min() == 0


@pytest.mark.parametrize("bad", [
    [], None, "chair", [[[1, 2], [1]]], [[[1, "x"], [1, 2]]], [[[1, float("nan")], [1, 2]]], [[[], []]],
    [[[1, 2], [1, 2]]] * (draw.MAX_STROKES + 1), [[list(range(9000)), list(range(9000))]],
])
def test_bad_strokes_are_refused(bad):
    with pytest.raises(draw.DrawingError):
        draw.normalize_strokes(bad)


def test_pixel_values_center_crop_and_normalise():
    img = Image.new("RGB", (256, 256), (255, 255, 255))
    img.putpixel((16, 16), (0, 0, 0))     # first pixel inside the 224 center crop
    img.putpixel((15, 15), (0, 0, 0))     # cropped away
    x = draw.pixel_values([img, img])
    assert x.shape == (2, 3, 224, 224) and x.dtype == np.float32
    white = (1 - draw.MEAN) / draw.STD
    assert np.allclose(x[0, :, 0, 0], -draw.MEAN / draw.STD) and np.allclose(x[0, :, 1, 1], white)
    assert np.allclose(draw.pixel_values([img.resize((512, 512))])[0, :, 100, 100], white)


# --- percentiles and scoring -----------------------------------------------------------------------

def test_percentile_below_counts_ties_as_half():
    ref = [0.1, 0.2, 0.2, 0.3]
    assert draw.percentile_below(0.05, ref) == 0
    assert draw.percentile_below(0.2, ref) == 50.0  # one below, two ties
    assert draw.percentile_below(0.25, ref) == 75.0
    assert draw.percentile_below(1.0, ref) == 100.0
    assert np.isnan(draw.percentile_below(0.5, []))


def toy_concept(rng=np.random.default_rng(0)):
    ai = draw.unit(np.eye(4)[0] + 0.05 * rng.normal(size=(6, 4)))
    people = draw.unit(np.eye(4)[1] + 0.4 * rng.normal(size=(40, 4)))
    hc = people.mean(0)
    loo = 1 - (draw.unit((people.sum(0) - people) / 39) * people).sum(1)
    return draw.Concept("chair", "chair", ai.mean(0), hc, np.zeros(4), np.eye(4)[:2], ai, people,
                        np.full(6, 0.01), loo, 1 - people @ draw.unit(ai.mean(0)))


def test_score_places_a_drawing_among_people():
    c = toy_concept()
    typical = draw.score(c.human_centroid, c)
    assert typical["d_human"] == 0 and typical["originality"] == 0  # the typical drawing is the least original
    odd = draw.score(-c.human_centroid, c)
    assert odd["originality"] == 100 and odd["d_human"] == pytest.approx(2.0)
    museish = draw.score(c.ai_centroid, c)
    assert museish["d_ai"] == 0 and museish["people_closer_to_muse"] == 0 and museish["muse_closer"] == 0
    p = c.people[7]
    s = draw.score(p, c)
    assert s["nearest_human"] == 7 and s["d_nearest_human"] == 0
    assert s["originality"] == pytest.approx(draw.percentile_below(1 - p @ draw.unit(c.human_centroid), c.human_loo), abs=0.05)
    lib = (["cat", "chair"], np.stack([np.eye(4)[2], c.human_centroid]))
    assert draw.score(c.human_centroid, c, lib)["looks_like"][0] == "chair"
    assert draw.score(np.eye(4)[2], c, lib)["own_rank"] == 2


def test_pack_round_trip():
    x = draw.unit(np.random.default_rng(1).normal(size=(5, 768)))
    assert np.allclose(draw.unpack(draw.pack(x)), x, atol=1e-6)
    q = draw.unit(draw.unpack(draw.pack_int8(x)))
    assert json.dumps(draw.pack_int8(x)) and (q * x).sum(1).min() > 0.9999


# --- the shipped reference data --------------------------------------------------------------------

@pytest.fixture(scope="module")
def ref():
    return draw.Reference.load(DATA / "draw.json")


def test_reference_schema(ref):
    d = ref.index
    assert d["model"] == "facebook/dinov2-base" and d["distance"] == "cosine"
    assert any("Quick, Draw!" in c and "CC BY 4.0" in c for c in d["credits"]) and any("DINOv2" in c for c in d["credits"])
    keys = [c["key"] for c in d["concepts"]]
    assert keys[0] == "chair" and {"umbrella", "house", "cat", "tree", "bicycle", "face"} <= set(keys)
    lib_keys, lib = ref.library
    assert lib.shape == (len(lib_keys), 768) and set(keys) <= set(lib_keys)
    for c in d["concepts"]:
        n_ai, n_h = c["n_ai"], c["n_human"]
        assert n_h == 200 and n_ai in (12, 16)
        assert len(c["human_loo"]) == len(c["human_to_ai"]) == len(c["map"]["human"]) == c["sprites"]["people"]["n"] == n_h
        assert len(c["ai_loo"]) == len(c["map"]["ai"]) == c["sprites"]["muse"]["n"] == n_ai
        assert all(0 <= v <= 2 for v in c["human_loo"] + c["ai_loo"] + c["human_to_ai"])
        assert {"ai_spread", "human_spread", "index", "when_asked"} <= set(c["stats"])
        for sp in c["sprites"].values():
            path = web.HERE / sp["src"].removeprefix("/")
            assert path.is_file() and path.stat().st_size < 300 * 1024
            w, h = Image.open(path).size
            assert w == sp["cols"] * sp["cell"] and h == -(-sp["n"] // sp["cols"]) * sp["cell"]
        assert (DATA / c["vectors"]).stat().st_size < 400 * 1024


def test_reference_vectors_reproduce_the_shipped_distances(ref):
    for key in ref.entries:
        c = ref.concept(key)
        e = ref.entries[key]
        assert c.ai.shape == (e["n_ai"], 768) and c.people.shape == (200, 768) and c.pca_axes.shape == (2, 768)
        assert np.allclose(np.linalg.norm(c.people, axis=1), 1)
        loo = 1 - (draw.unit((c.people.sum(0) - c.people) / 199) * c.people).sum(1)
        assert np.abs(loo - c.human_loo).max() < 0.01  # int8 vectors keep the distances
        xy = (c.people - c.pca_mean) @ c.pca_axes.T
        assert np.abs(xy - np.array(e["map"]["human"])).max() < 0.01
        # a person's own drawing is its own nearest neighbour, and Muse's doodles sit near Muse's prototype
        assert draw.score(c.people[3], c)["nearest_human"] == 3
        assert np.median([draw.score(v, c)["people_closer_to_muse"] for v in c.ai]) == 0


def test_public_data_has_no_vectors(ref):
    pub = ref.public()
    assert "centroids" not in pub and all("vectors" not in c for c in pub["concepts"])
    assert len(json.dumps(pub)) < 200_000


# --- the route ---------------------------------------------------------------------------------------

class FakeEmbedder:
    backend = "fake"

    def __init__(self, vec):
        self.vec = vec
        self.calls = 0

    def __call__(self, images):
        self.calls += 1
        assert all(im.size == (256, 256) for im in images)
        return np.stack([self.vec] * len(images))


@pytest.fixture
def client(monkeypatch, ref):
    built = []
    fake = FakeEmbedder(ref.concept("chair").human_centroid)

    def factory():
        built.append(1)
        return fake

    monkeypatch.setattr(draw_routes, "embedder", draw.LazyEmbedder(factory))
    monkeypatch.setattr(draw_routes, "burst", DailyLimiter(window_s=60))
    monkeypatch.setattr(draw_routes, "limiter", DailyLimiter())
    for name in ("TOT_LIMIT_DRAW", "TOT_LIMIT_DRAW_BURST"):
        monkeypatch.delenv(name, raising=False)
    c = TestClient(web.app)
    c.built, c.fake = built, fake
    return c


def post(c, strokes=CHAIR, concept="chair"):
    return c.post("/api/draw", json={"concept": concept, "strokes": strokes})


def test_page_and_concepts(client):
    r = client.get("/draw")
    assert r.status_code == 200 and "never stored or logged" in r.text and 'id="pad"' in r.text
    data = client.get("/api/draw/concepts").json()
    assert data["concepts"][0]["key"] == "chair" and "vectors" not in data["concepts"][0]


def test_model_loads_on_the_first_drawing_only(client):
    assert client.get("/api/draw/status").json()["model_loaded"] is False
    client.get("/draw")
    client.get("/api/draw/concepts")
    assert client.built == []
    r = post(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["originality"] == 0 and body["d_human"] == 0  # the fake returns the typical person's chair
    assert {"d_ai", "people_closer_to_muse", "xy", "nearest_ai", "nearest_human", "looks_like"} <= set(body)
    post(client)
    assert client.built == [1] and client.fake.calls == 2
    st = client.get("/api/draw/status").json()
    assert st["model_loaded"] is True and st["backend"] == "fake"


def test_bad_requests(client):
    assert post(client, concept="dragon").status_code == 422
    assert post(client, strokes=[]).status_code == 422
    assert client.post("/api/draw", content=b"{", headers={"content-type": "application/json"}).status_code == 422
    big = client.post("/api/draw", content=b" " * (draw_routes.MAX_BODY + 1), headers={"content-type": "application/json"})
    assert big.status_code == 413
    assert client.built == []  # none of these woke the model


def test_missing_model_is_a_friendly_503(client, monkeypatch):
    def missing():
        raise ImportError("No module named 'onnxruntime'")
    monkeypatch.setattr(draw_routes, "embedder", draw.LazyEmbedder(missing))
    r = post(client)
    assert r.status_code == 503 and "isn't installed" in r.json()["detail"]


def test_per_minute_and_daily_limits(client, monkeypatch):
    monkeypatch.setenv("TOT_LIMIT_DRAW_BURST", "3")
    for _ in range(3):
        assert post(client).status_code == 200
    r = post(client)
    assert r.status_code == 429 and "a minute" in r.json()["detail"] and r.headers["retry-after"]
    monkeypatch.setattr(draw_routes, "burst", DailyLimiter(window_s=60))  # a minute later
    monkeypatch.setenv("TOT_LIMIT_DRAW", "4")
    assert post(client).status_code == 200
    r = post(client)
    assert r.status_code == 429 and "Daily limit" in r.json()["detail"] and "drawings" in r.json()["detail"]
    other = client.post("/api/draw", json={"concept": "chair", "strokes": CHAIR}, headers={"x-forwarded-for": "1.2.3.4"})
    assert other.status_code == 429  # without TOT_TRUST_PROXY a forged header doesn't escape the limit


def test_drawings_are_not_logged(client, caplog):
    caplog.set_level(logging.DEBUG)
    marker = 123.4567
    r = post(client, strokes=[[[marker, 300.0, 300.0], [10.0, 10.0, 200.0]]])
    assert r.status_code == 200
    assert not any(str(marker) in rec.getMessage() for rec in caplog.records)


def test_the_guard_counts_drawing_as_free():
    g = G.Guard(G.Settings(public_demo=True))
    assert g.match("POST", "/api/draw") is None
    assert g.match("POST", "/api/drawings") is not None  # only the exact route


def test_the_app_never_imports_the_model_at_startup():
    code = ("import sys; from fastapi.testclient import TestClient; import metalesionlab.web.app as a; "
            "c = TestClient(a.app); assert c.get('/draw').status_code == 200; "
            "assert c.get('/api/draw/concepts').status_code == 200; assert c.get('/plato').status_code == 200; "
            "print(sorted(m for m in ('onnxruntime', 'torch', 'transformers') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "[]"


def test_nav_links_draw_a_chair():
    pages = web.HERE / "pages"
    for name in ("index.html", "challenge.html", "lab.html", "cut.html", "bilingual.html", "ask.html", "scorer.html",
                 "studio.html", "assess.html", "draw.html"):
        assert 'href="/draw"' in (pages / name).read_text(), name


# --- fetching the model at build time ------------------------------------------------------------------

def test_fetch_checks_the_sha256(tmp_path, monkeypatch):
    src = tmp_path / "model.onnx"
    src.write_bytes(b"not really a model")
    monkeypatch.setattr(draw_fetch, "SHA256", hashlib.sha256(src.read_bytes()).hexdigest())
    monkeypatch.setattr(draw_fetch, "SIZE", src.stat().st_size)
    monkeypatch.setattr(draw_fetch.time, "sleep", lambda s: None)
    out = draw_fetch.fetch(tmp_path / "models" / "m.onnx", url=src.as_uri())
    assert out.read_bytes() == src.read_bytes()
    assert draw_fetch.fetch(out, url="file:///nowhere") == out  # already there and verified: no download
    monkeypatch.setattr(draw_fetch, "SHA256", "0" * 64)
    with pytest.raises(SystemExit):
        draw_fetch.fetch(tmp_path / "bad.onnx", retries=2, url=src.as_uri())
    assert not (tmp_path / "bad.onnx").exists() and not (tmp_path / "bad.onnx.part").exists()

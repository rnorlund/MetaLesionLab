"""Draw a chair (/draw), offline: stroke rendering, percentiles, the shipped reference data, the route's
limits and lazy model loading. A fake embedder stands in for DINOv2, so nothing is downloaded."""
import hashlib
import io
import json
import logging
import math
import re
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
    # the abstract ideas have no people (test_plato_ideas.py); the clock test has only averages (test_plato_clock.py)
    for key in [k for k in ref.entries if not ref.ai_only(k) and not ref.group(k)]:
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
    assert r.status_code == 200 and "never stored or logged" in r.text and 'id="draw-app"' in r.text
    assert "TOTDraw.mount" in r.text and "/static/js/draw.js" in r.text
    data = client.get("/api/draw/concepts").json()
    assert data["concepts"][0]["key"] == "chair" and "vectors" not in data["concepts"][0]


def test_pages_are_blind_until_the_reveal(client):
    """Before drawing: no Muse Image pictures and no originality framing, on /draw and on the landing page."""
    page = client.get("/draw").text
    main = page[page.index("<main"):page.index("</main>")]
    assert "_muse.webp" not in main and "16 times" not in main
    assert re.search(r'<section class="dw-sec" id="how"[^>]*hidden', main)  # "How it works" waits for the reveal
    js = (web.HERE / "static" / "js" / "draw.js").read_text()
    pad_html = js[js.index("var PAD_HTML"):js.index("var RESULTS_HTML")]
    assert "Muse" not in pad_html and "original" not in pad_html
    landing = client.get("/").text
    hero = landing[landing.index('id="hero-draw"') - 200:landing.index('id="reveal"')]
    assert "Is there one ideal chair?" in hero and "Skip, just show me what the AI drew" in hero
    assert "hero_chairs_ai" not in hero and "16" not in hero
    assert re.search(r'<section class="hero reveal-band" id="reveal"[^>]*hidden', landing)
    reveal = landing[landing.index('id="reveal"'):]
    assert 'id="chairs"' in reveal and 'id="hero-results"' in reveal  # the stack animation and the results
    assert landing.index("/static/js/draw.js") < landing.index("/static/js/landing.js")


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


def test_preload_warms_the_model_before_the_first_drawing(client):
    draw_routes.preload().join(5)
    assert client.built == [1] and client.fake.calls == 1
    assert client.get("/api/draw/status").json()["model_loaded"] is True
    assert post(client).status_code == 200 and client.built == [1]


def test_the_image_preloads_the_model():
    with open(draw.REPO / "Dockerfile") as f:
        assert "DRAW_PRELOAD=1" in f.read()


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
    assert g.match("POST", "/api/draw") is None and g.match("POST", "/api/draw/upload") is None
    assert g.match("POST", "/api/drawings") is not None  # only the exact routes


def test_the_app_never_imports_the_model_at_startup():
    code = ("import sys; from fastapi.testclient import TestClient; import metalesionlab.web.app as a; "
            "c = TestClient(a.app); assert c.get('/draw').status_code == 200; "
            "assert c.get('/api/draw/concepts').status_code == 200; assert c.get('/plato').status_code == 200; "
            "print(sorted(m for m in ('onnxruntime', 'torch', 'transformers') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "[]"


def test_nav_links_draw_a_chair():
    c = TestClient(web.app_for("plato"))  # the nav comes from web/site.py, so check the pages as served
    for path in ("/", "/plato", "/plato/cave", "/plato/damage", "/socrates", "/draw"):
        assert 'href="/draw"' in c.get(path).text, path
    # Draw a chair is the Plato site's: the Lingua site neither serves it nor links to it
    lingua = TestClient(web.app_for("lingua"))
    assert lingua.get("/draw").status_code == 404 and 'href="/draw"' not in lingua.get("/lab").text


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


# --- uploads: a photo of a drawing on paper ---------------------------------------------------------

def photo(strokes=CHAIR, table=False, size=(1024, 768), seed=0, ink=(40, 40, 70)) -> Image.Image:
    """A photo-like picture of a pen drawing on paper: off-white, uneven light, grain, a slight tilt."""
    rng = np.random.default_rng(seed)
    w, h = size
    pw, ph = (int(w * 0.7), int(h * 0.75)) if table else (w, h)
    paper = Image.new("RGB", (pw, ph), (236, 233, 226))
    from PIL import ImageDraw
    d = ImageDraw.Draw(paper)
    xs = [x for s in strokes for x in s[0]] or [0]
    ys = [y for s in strokes for y in s[1]] or [0]
    k = 0.6 * min(pw, ph) / max(max(xs) - min(xs), max(ys) - min(ys), 1)
    ox, oy = pw / 2 - (max(xs) + min(xs)) / 2 * k, ph / 2 - (max(ys) + min(ys)) / 2 * k
    for sx, sy in strokes:
        d.line([(ox + x * k, oy + y * k) for x, y in zip(sx, sy)], fill=ink, width=4)
    paper = paper.rotate(4, resample=Image.BICUBIC, fillcolor=(236, 233, 226), expand=table)
    if table:
        bg = Image.new("RGB", size, (110, 80, 50))
        bg.paste(paper, ((w - paper.width) // 2, (h - paper.height) // 2))
        paper = bg
    a = np.asarray(paper, dtype=np.float32)
    shade = np.linspace(0.8, 1.0, w, dtype=np.float32)[None, :, None]
    a = np.clip(a * shade + rng.normal(0, 3, a.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(a)


def jpeg(img: Image.Image, fmt="JPEG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


def busy_scene(seed=1) -> Image.Image:
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (800, 600))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for _ in range(80):
        x, y = rng.integers(0, 800), rng.integers(0, 600)
        r = int(rng.integers(20, 120))
        d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(v) for v in rng.integers(0, 255, 3)))
    return img


def test_load_upload_decodes_safely():
    img = draw.load_upload(jpeg(photo()))
    assert img.mode == "RGB" and max(img.size) == draw.UPLOAD_SIDE
    rgba = Image.new("RGBA", (300, 200), (0, 0, 0, 0))  # black ink on transparent: composited on white
    rgba.paste((0, 0, 0, 255), (100, 90, 200, 110))
    flat = np.asarray(draw.load_upload(jpeg(rgba, "PNG")).convert("L"))
    assert flat[0, 0] == 255 and flat[100, 150] == 0
    for bad, msg in ((b"", "empty"), (b"not an image", "couldn't read"), (jpeg(photo(), "GIF"), "JPEG, PNG or WebP"),
                     (jpeg(Image.new("RGB", (40, 40), "white")), "too small"),
                     (b"x" * (draw.MAX_UPLOAD_BYTES + 1), "too big")):
        with pytest.raises(draw.DrawingError, match=msg):
            draw.load_upload(bad)


def test_exif_rotation_is_applied_and_dropped():
    img = photo()
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    up = draw.load_upload(buf.getvalue())
    assert up.size[0] < up.size[1] and not up.getexif()  # portrait now, and no EXIF left


def test_paper_check_tells_drawings_from_photos():
    ok = draw.paper_stats(draw.load_upload(jpeg(photo())))
    assert draw.upload_problem(ok) is None
    assert draw.upload_problem(draw.paper_stats(draw.load_upload(jpeg(photo(strokes=[]))))) == draw.NO_INK
    assert draw.upload_problem(draw.paper_stats(draw.load_upload(jpeg(busy_scene())))) == draw.NOT_A_DRAWING
    assert draw.upload_problem(draw.paper_stats(draw.load_upload(jpeg(photo(table=True))))) == draw.EDGES
    assert draw.upload_problem({**ok, "d_doodle": draw.MAX_DOODLE_DISTANCE + 0.01}) == draw.NOT_A_DRAWING
    pic, stats = draw.prepare_upload(jpeg(photo()))
    assert pic.size == (256, 256) and np.asarray(pic.convert("L")).min() < 100  # the lines survive the crop
    assert stats["span"] < draw.MAX_SPAN


def upload(c, body, concept="chair", **params):
    q = "&".join(f"{k}={v}" for k, v in {"concept": concept, **params}.items())
    return c.post(f"/api/draw/upload?{q}", content=body, headers={"content-type": "image/jpeg"})


def test_upload_scores_a_photo_and_returns_what_the_model_saw(client):
    r = upload(client, jpeg(photo()))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "upload" and body["originality"] == 0  # the fake model returns the typical chair
    assert body["picture"].startswith("data:image/png;base64,")
    pic = Image.open(io.BytesIO(__import__("base64").b64decode(body["picture"].split(",", 1)[1])))
    assert pic.size == (256, 256) and pic.mode == "L"
    assert "donation" not in body


def test_upload_refuses_photos_of_things_and_counts_against_the_limits(client, monkeypatch):
    r = upload(client, jpeg(busy_scene()))
    assert r.status_code == 422 and "plain paper" in r.json()["detail"]
    assert client.built == []  # refused before the model was needed
    assert upload(client, b"garbage").status_code == 422
    assert upload(client, jpeg(photo()), concept="dragon").status_code == 422
    big = client.post("/api/draw/upload?concept=chair", content=b"x" * (draw.MAX_UPLOAD_BYTES + 1),
                      headers={"content-type": "image/jpeg"})
    assert big.status_code == 413
    monkeypatch.setenv("TOT_LIMIT_DRAW_BURST", "4")
    assert upload(client, jpeg(photo())).status_code == 429  # refused ones count too: four this minute already


def test_upload_far_from_any_doodle_is_refused(client, ref):
    client.fake.vec = -ref.concept("chair").human_centroid  # nothing like any doodle
    r = upload(client, jpeg(photo()))
    assert r.status_code == 422 and "plain paper" in r.json()["detail"]


def test_uploads_are_not_logged(client, caplog):
    caplog.set_level(logging.DEBUG)
    assert upload(client, jpeg(photo())).status_code == 200
    assert not any("JFIF" in rec.getMessage() or "base64" in rec.getMessage() for rec in caplog.records)


# --- donations: off by default, opt-in, minimal -------------------------------------------------------

from metalesionlab.web import draw_donations as donations  # noqa: E402


@pytest.fixture
def ddir(tmp_path, monkeypatch):
    d = tmp_path / "donations"
    monkeypatch.setenv("TIPPA_DONATIONS_DIR", str(d))
    monkeypatch.delenv("TIPPA_DONATIONS", raising=False)
    return d


def files_in(d):
    return sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()) if d.exists() else []


def donate_post(c, **extra):
    return c.post("/api/draw", json={"concept": "chair", "strokes": CHAIR, "blind": True, "draw_ms": 4200, **extra})


def test_donations_are_off_by_default(client, ddir):
    st = client.get("/api/draw/status").json()
    assert st["donations"] == {"enabled": False} and "never stored" in st["privacy"]
    r = donate_post(client, donate=True, adult=True)
    assert r.status_code == 200 and "donation" not in r.json()
    assert upload(client, jpeg(photo()), donate=1, adult=1).status_code == 200
    assert files_in(ddir) == []
    assert "never stored or logged" in client.get("/draw").text


def test_donation_needs_consent_and_age(client, ddir, monkeypatch):
    monkeypatch.setenv("TIPPA_DONATIONS", "1")
    st = client.get("/api/draw/status").json()
    assert st["donations"]["enabled"] and st["privacy"] == "Not stored unless you choose to donate it."
    assert st["donations"]["points"][-1] == ["Questions", "{{CONTACT}}"] and st["donations"]["irb"] == "{{IRB_NOTE}}"
    assert "donation" not in donate_post(client).json()  # no tick: nothing kept
    assert files_in(ddir) == []
    r = donate_post(client, donate=True, adult=False)  # under 18 (or didn't say)
    assert r.status_code == 200 and r.json()["donation"]["status"] == "declined" and "18" in r.json()["donation"]["reason"]
    assert files_in(ddir) == []


def test_pad_donation_keeps_strokes_and_the_picture_only(client, ddir, monkeypatch):
    monkeypatch.setenv("TIPPA_DONATIONS", "1")
    r = donate_post(client, donate=True, adult=True)
    assert r.json()["donation"] == {"status": "saved"}
    files = files_in(ddir)
    assert files[0] == "donations.jsonl" and len(files) == 2 and files[1].startswith("png/")
    rec = json.loads((ddir / "donations.jsonl").read_text())
    assert set(rec) == {"id", "date", "concept", "source", "blind", "draw_seconds", "scores", "strokes", "png", "model", "consent"}
    assert rec["source"] == "pad" and rec["blind"] is True and rec["draw_seconds"] == 4.2 and len(rec["date"]) == 10
    assert rec["strokes"] == draw.normalize_strokes(CHAIR) and rec["png"] == f"png/{rec['id']}.png"
    assert Image.open(ddir / rec["png"]).size == (256, 256)
    assert "testclient" not in (ddir / "donations.jsonl").read_text()  # no address
    donate_post(client, donate=True, adult=True)
    assert len((ddir / "donations.jsonl").read_text().splitlines()) == 2  # appended


def test_upload_donation_never_writes_the_photo(client, ddir, monkeypatch):
    monkeypatch.setenv("TIPPA_DONATIONS", "1")
    raw = jpeg(photo())
    r = upload(client, raw, donate=1, adult=1, blind=0)
    assert r.json()["donation"] == {"status": "saved"}
    rec = json.loads((ddir / "donations.jsonl").read_text())
    assert rec["source"] == "upload" and rec["strokes"] is None and rec["blind"] is False
    png = Image.open(ddir / rec["png"])
    assert png.size == (256, 256) and png.mode == "L" and not png.getexif()
    for f in ddir.rglob("*"):
        if f.is_file():
            data = f.read_bytes()
            assert raw[:2000] not in data and b"JFIF" not in data and b"Exif" not in data


def test_writing_is_not_accepted_as_a_donation(client, ddir, monkeypatch):
    from PIL import ImageDraw, ImageFont
    monkeypatch.setenv("TIPPA_DONATIONS", "1")
    img = Image.new("RGB", (900, 400), (236, 233, 226))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 70)
    except OSError:
        font = ImageFont.load_default(size=70)
    ImageDraw.Draw(img).text((40, 150), "Jane Doe 2026", fill=(30, 30, 30), font=font)
    assert donations.text_like(ink_crop(img))
    assert not donations.text_like(draw.render(CHAIR))
    r = upload(client, jpeg(img), donate=1, adult=1)
    assert r.status_code == 200 and r.json()["donation"]["status"] == "declined"
    assert "writing" in r.json()["donation"]["reason"] and files_in(ddir) == []


def test_export_donations_writes_a_reviewable_dataset(client, ddir, monkeypatch, tmp_path):
    import importlib.util
    monkeypatch.setenv("TIPPA_DONATIONS", "1")
    donate_post(client, donate=True, adult=True)
    upload(client, jpeg(photo()), donate=1, adult=1)
    spec = importlib.util.spec_from_file_location("export_donations", web.HERE.parents[1] / "scripts" / "export_donations.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path / "dataset"
    monkeypatch.setattr(sys, "argv", ["export_donations.py", "--out", str(out), "--donations", str(ddir)])
    assert mod.main() == 0
    names = files_in(out)
    assert {"README.md", "LICENSE", "drawings.jsonl", "summary.json"} <= set(names)
    assert sum(n.startswith("png/") for n in names) == 2
    assert "CC BY 4.0" in (out / "LICENSE").read_text() and "{{IRB_NOTE}}" in (out / "README.md").read_text()
    assert json.loads((out / "summary.json").read_text())["by_source"] == {"pad": 1, "upload": 1}


def test_bundles_and_git_never_take_donations(tmp_path):
    import importlib.util
    script = web.HERE.parents[1] / "scripts" / "build_site_bundle.py"
    spec = importlib.util.spec_from_file_location("build_site_bundle_for_draw", script)
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)
    out = tmp_path / "bundle"
    (out / "donations" / "png").mkdir(parents=True)
    (out / "donations" / "donations.jsonl").write_text("{}\n")
    problems = B.check_bundle(out, require_patterns=False)
    assert any("donations/donations.jsonl" in p and "donated drawings" in p for p in problems)
    assert "donations/" in (web.HERE.parents[1] / ".gitignore").read_text().split()

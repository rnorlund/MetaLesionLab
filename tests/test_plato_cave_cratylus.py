"""Plato's Cave (/plato/cave) and Cratylus (/plato/cratylus): stimulus maker, statistics helpers, the shipped
data's schema, the pages and their size budget. Offline: no model, no API."""
import json
import math
import re
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from metalesionlab import brand
from metalesionlab import plato_cave as pc
from metalesionlab import plato_cratylus as pk
from metalesionlab.web import app as web
from metalesionlab.web import plato_cave_routes, plato_cratylus_routes

REPO = Path(web.__file__).resolve().parents[2]
DATA = web.HERE / "data"
STATIC = web.HERE / "static"
VERSIONS = ["original", "outline", "silhouette", "shadow"]


@pytest.fixture
def client():
    plato_cave_routes._cache.clear()
    plato_cratylus_routes._cache.clear()
    return TestClient(web.app)


# --- the stimulus maker ---------------------------------------------------------------------

def _cat_like(side=600):
    """A closed outline with inner detail, like the core drawings: a head with ears, eyes and a smile."""
    img = Image.new("RGB", (side, side), "white")
    d = ImageDraw.Draw(img)
    d.polygon([(150, 450), (150, 200), (200, 120), (250, 200), (350, 200), (400, 120), (450, 200), (450, 450)],
              outline="black", width=6)
    d.ellipse((230, 260, 260, 290), outline="black", width=4)
    d.ellipse((340, 260, 370, 290), outline="black", width=4)
    d.arc((250, 320, 350, 390), 20, 160, fill="black", width=4)
    return img


def test_make_versions_shares_one_crop_and_drops_the_inside():
    v = pc.make_versions(_cat_like())
    assert set(v.images) == set(VERSIONS) and v.source == "code" and v.radius == 0
    arrs = {k: np.asarray(im.convert("L"), float) for k, im in v.images.items()}
    assert all(a.shape == (pc.SIDE, pc.SIDE) for a in arrs.values())
    sil, out, orig = arrs["silhouette"] < 128, arrs["outline"] < 128, arrs["original"] < 128
    # the silhouette is solid where the drawing had eyes and a mouth; the outline has no inner detail
    assert sil[int(0.5 * pc.SIDE), int(0.5 * pc.SIDE)]
    assert out.sum() < 0.3 * sil.sum()
    inner = np.zeros_like(out)
    inner[int(0.42 * pc.SIDE):int(0.62 * pc.SIDE), int(0.35 * pc.SIDE):int(0.65 * pc.SIDE)] = True
    assert (orig & inner).sum() > 50 and (out & inner).sum() == 0
    # same crop: the silhouette covers the original's ink
    assert (orig & ~sil).sum() < 0.02 * orig.sum()
    # the shadow is gray on a lighter gray wall, never pure black or white
    sh = arrs["shadow"]
    assert 20 < sh.min() and sh.max() < 250 and sh[int(0.5 * pc.SIDE)].min() < sh[:10].mean() - 30


def test_make_versions_seals_an_open_drawing():
    img = Image.new("RGB", (500, 500), "white")
    ImageDraw.Draw(img).arc((100, 100, 400, 400), 40, 320, fill="black", width=5)  # a C, open on the right
    plain = pc.make_versions(img)
    sealed = pc.make_versions(img, seal=True)
    assert sealed.source == "sealed" and sealed.fill_ratio > 5 * plain.fill_ratio


def test_items_and_overrides():
    assert pc.VERSIONS == tuple(VERSIONS) and set(pc.OPEN_ITEMS) == {"foot", "ear", "nose"}
    assert pc.RADIUS_OVERRIDES == {"feather": 12}
    assert "Wagemans" in pc.CREDIT_NORMS and "10.1068/p5825" in pc.CREDIT_NORMS


# --- Cratylus helpers ---------------------------------------------------------------------------

def test_words_design():
    by_group = {}
    for w in pk.WORDS:
        by_group.setdefault(w.group, []).append(w)
    assert [w.word for w in by_group["classic"]] == ["bouba", "kiki", "maluma", "takete"]
    grid = by_group["grid"]
    assert len(grid) == 8
    for c in ("soft", "hard"):
        for v in ("rounded", "unrounded"):
            assert len([w for w in grid if w.consonants == c and w.vowels == v]) == 2
    soft, hard = set("bml"), set("ktp")
    for w in grid:
        cons = {ch for ch in w.word if ch not in "aeiou"}
        vows = {ch for ch in w.word if ch in "aeiou"}
        assert cons <= (soft if w.consonants == "soft" else hard), w.word
        assert vows <= (set("ou") if w.vowels == "rounded" else set("ie")), w.word
    assert len(by_group["control"]) == 4 and all(set(w.word) & set("bmlktp") == set() for w in by_group["control"])
    assert set(pk.ROUND_CLASS) | set(pk.SPIKY_CLASS) <= {w.word for w in pk.WORDS}
    assert sum(w.n for w in pk.WORDS) == 236  # the pre-registered picture count


def test_prompts_and_slugs():
    assert pk.prompt_for("kiki") == "A simple black outline drawing of a shape called 'kiki'. One shape only, no text."
    assert "called" not in pk.prompt_for(pk.BASELINE)
    assert pk.slug("kiki (pronounced KEE-kee)") == "kiki_pronounced_kee_kee" and pk.slug(pk.BASELINE) == "no_name"
    assert pk.parse_side("Left.") == "left" and pk.parse_side("**right**") == "right" and pk.parse_side("neither") is None
    assert "A is a rounded blob" in pk.text_choice_prompt("bouba", True)
    assert "A is a spiky star" in pk.text_choice_prompt("bouba", False)


def test_pair_image_puts_shapes_left_and_right():
    r, s = pk.round_shape(0), pk.spiky_shape(0)
    img = np.asarray(pk.pair_image(r, s).convert("L")) < 128
    w = r.shape[1]
    assert img.shape == (r.shape[0], 2 * w)
    assert (img[:, :w] == r).all() and (img[:, w:] == s).all()


def test_contrast_statistics():
    x, y = np.array([0.9, 0.92, 0.95, 0.91]), np.array([0.5, 0.55, 0.52, 0.6])
    assert pk.auc(-x, -y) == 1.0 and pk.auc(x, y) == 0.0 and pk.auc(x, x) == 0.5
    c = pk.bootstrap_contrast(-x, -y, reps=500)
    assert c["auc"] == 1.0 and c["diff"] > 0 and c["diff_ci"][0] > 0 and c["d"] > 2
    h = pk.hierarchical_contrast([[0.0, 0.1], [0.1, 0.2]], [[1.0, 1.1], [0.9, 1.0]], reps=500)
    assert math.isclose(h["diff"], 0.9, abs_tol=1e-9) and h["diff_ci"][0] > 0.6 and h["n_words"] == [2, 2]


def test_roundness_of_a_drawn_blob_and_star():
    from scipy import ndimage as ndi

    out = []
    for m in (pk.round_shape(1), pk.spiky_shape(1)):
        ring = m & ~ndi.binary_erosion(m, iterations=3)
        out.append(pk.roundness(Image.fromarray(np.where(ring, 0, 255).astype(np.uint8)))[0])
    blob, star = out
    assert blob.solidity > 0.85 and blob.corners == 0 and blob.n_shapes == 1
    assert star.solidity < 0.55 and star.corners >= 7


# --- shipped data ---------------------------------------------------------------------------------

def _all_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _all_keys(v)


def test_cave_data_schema():
    for path in (DATA / "plato_cave.json", REPO / "public_data" / "plato_cave.json"):
        d = json.loads(path.read_text())
        assert d["n_pictures"] == 100 and d["versions"] == VERSIONS
        for v in VERSIONS:
            a = d["accuracy"][v]
            assert 0 <= a["ci95"][0] <= a["accuracy"] <= a["ci95"][1] <= 1 and a["n"] == 100
        assert d["accuracy"]["original"]["accuracy"] >= d["accuracy"]["shadow"]["accuracy"]
        assert d["accuracy"]["shadow"]["diff_vs_original"] < 0
        h = d["human"]
        assert h["published"]["silhouette_mean_260"] == 0.647 and "Wagemans" in h["published"]["source"]
        r = h["silhouette"]["rho_correct"]
        assert -1 <= r["ci95"][0] <= r["rho"] <= r["ci95"][1] <= 1 and r["n"] == h["n_shared_concepts"] == 78
        # no item-level human rates (no licence): concept names in groups only
        assert not any(re.search(r"rate", k) for k in _all_keys(h))
        assert all(isinstance(w, str) for w in h["silhouette"]["both_fail"])
        assert len(d["word_lens"]["shadow"]["mean_p_name_by_layer"]) == d["word_lens_n_layers"] == 52
        m = d["medium_answers"]["shadow"]
        assert m["just_shadow"] <= m["medium"] and len(m["just_shadow_words"]) == m["just_shadow"]
        assert "/Users/" not in path.read_text()


def test_cave_game_items_have_pictures_and_answers():
    d = json.loads((DATA / "plato_cave.json").read_text())
    assert len(d["game"]) == 12 and len(d["items"]) == 100
    for g in d["game"]:
        for key in ("shadow_img", "original_img"):
            assert (STATIC / "img" / "plato_cave" / g[key]).is_file(), g[key]
        assert set(g["glimmer"]) == set(VERSIONS) and g["glimmer"]["shadow"]["said"]


def test_cratylus_data_schema():
    for path in (DATA / "plato_cratylus.json", REPO / "public_data" / "plato_cratylus.json"):
        d = json.loads(path.read_text())
        words = {w["word"]: w for w in d["words"]}
        assert set(words) == {w.word for w in pk.WORDS} and d["n_pictures"] == 236
        for w in d["words"]:
            for m in ("solidity", "corners", "axis"):
                e = w[m]
                assert e["ci95"][0] - 1e-9 <= e["mean"] <= e["ci95"][1] + 1e-9, (w["word"], m)
            assert 0 <= w["solidity"]["mean"] <= 1
        k = d["contrasts"]["kiki_vs_bouba"]["solidity"]
        assert 0 <= k["auc_ci"][0] <= k["auc"] <= k["auc_ci"][1] <= 1
        assert words["kiki"]["solidity"]["mean"] < words["bouba"]["solidity"]["mean"]
        c = d["choice"]
        assert all(0 <= v["p_round"] <= 1 for v in c["glimmer_picture"].values())
        assert set(c["spark"]) == {w.word for w in pk.WORDS if w.group in ("classic", "grid", "control")}
        p = d["people"]
        assert p["both_trials_match"] == 0.72 and p["n_people"] == 917 and "Ćwiek" in p["source"]
        assert "/Users/" not in path.read_text()


# --- pages ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("path,api,marker", [("/plato/cave", "/api/plato/cave", 'id="game-grid"'),
                                             ("/plato/cratylus", "/api/plato/cratylus", 'id="words-chart"')])
def test_pages_render_with_the_site_header(client, path, api, marker):
    r = client.get(path)
    assert r.status_code == 200 and marker in r.text
    assert r.text.count('<header class="topbar site-head">') == 1
    assert "{{BRAND}}" not in r.text and brand.BRAND in r.text
    assert client.get(api).status_code == 200


def test_pages_join_the_series(client):
    paths = [s["path"] for s in client.get("/api/site").json()["series"]]
    assert "/plato/cave" in paths and "/plato/cratylus" in paths
    for slug in ("cave", "cratylus"):
        finding = json.loads((DATA / "series" / f"{slug}.json").read_text())["finding"]
        assert finding and len(finding) < 200
        img = STATIC / "img" / "plato" / "series" / f"{slug}.webp"
        assert img.stat().st_size <= 120 * 1024 and Image.open(img).size == (1200, 675)


def test_missing_data_is_a_friendly_503(client, monkeypatch, tmp_path):
    monkeypatch.setattr(plato_cave_routes, "DATA", tmp_path / "none.json")
    monkeypatch.setattr(plato_cratylus_routes, "DATA", tmp_path / "none.json")
    assert client.get("/api/plato/cave").status_code == 503
    assert client.get("/api/plato/cratylus").status_code == 503


@pytest.mark.parametrize("page,js,css,folder", [
    ("plato_cave.html", "plato_cave.js", "plato_cave.css", "plato_cave"),
    ("plato_cratylus.html", "plato_cratylus.js", "plato_cratylus.css", "plato_cratylus"),
])
def test_page_assets_exist_and_stay_under_budget(page, js, css, folder):
    html = (web.HERE / "pages" / page).read_text()
    script = (STATIC / "js" / js).read_text()
    for name in re.findall(rf"/static/img/{folder}/([\w.]+\.webp)", html):
        assert (STATIC / "img" / folder / name).is_file(), name
    imgs = list((STATIC / "img" / folder).glob("*"))
    assert imgs and all(f.suffix == ".webp" and f.stat().st_size <= 300 * 1024 for f in imgs)
    added = sum(f.stat().st_size for f in imgs) + len(html) + len(script) + (STATIC / "css" / css).stat().st_size
    assert added <= 1.5 * 1024 * 1024
    assert "fetch(" not in script and "localStorage" not in script  # replays shipped data; stores nothing

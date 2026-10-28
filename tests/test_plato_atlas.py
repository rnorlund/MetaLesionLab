"""The Atlas of Forms: concept selection, statistics, the benchmark script, the data files and the page."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from metalesionlab import plato
from metalesionlab import plato_atlas as A


# --- the pre-registered concept list ---------------------------------------------------------------

def test_selection_is_reproducible_and_matches_the_plan():
    new = A.select_new()
    assert new == A.select_new(A.SEED) and len(new) == 98
    assert Counter(d for _, d in new) == Counter(A.QUOTAS)
    assert all(w in A.ELIGIBLE[d] for w, d in new)
    assert {"rain", "hurricane", "snowman"} <= {w for w, _ in new}
    # a few of the drawn concepts named in docs/plato_atlas_plan.md
    assert {"ant", "whale", "peas", "anvil", "submarine", "see saw", "skull", "teddy-bear"} <= {w for w, _ in new}


def test_concepts_cover_core_forms_and_new_once():
    keys = [c.key for c in A.CONCEPTS]
    assert len(keys) == len(set(keys)) == 135
    assert Counter(c.origin for c in A.CONCEPTS) == {"core": 35, "forms": 2, "new": 98}
    assert [c.key for c in A.CONCEPTS if c.origin == "core"] == [c.key for c in plato.CONCEPTS]
    assert sum(c.natural for c in A.CONCEPTS) == 51
    listed = [w for ws in A.EXCLUDED.values() for w in ws] + [w for ws in A.ELIGIBLE.values() for w in ws]
    studied = {c.quickdraw for c in A.CONCEPTS if c.origin != "new"}
    assert len(listed) == len(set(listed)) and not set(listed) & studied
    assert len(listed) + len(studied) == 345  # every Quick, Draw! category sorted exactly once
    assert all(c.domain in A.DOMAINS for c in A.CONCEPTS)


def test_prompt_phrases():
    by = {c.quickdraw: c for c in A.CONCEPTS}
    assert by["anvil"].phrase == "an anvil" and by["grapes"].phrase == "grapes" and by["moon"].phrase == "the moon"
    assert by["teddy-bear"].phrase == "a teddy bear" and by["teddy-bear"].label == "teddy bear"
    assert by["chair"].phrase == "a chair" and by["yoga"].phrase == "a person doing yoga"
    assert A.prompt_for(by["rain"]).startswith("A quick simple doodle sketch of rain, black marker")
    assert A.slug("t-shirt") == "t-shirt" and A.slug("sea_turtle") == "sea-turtle"


# --- statistics ------------------------------------------------------------------------------------

def test_spread_ratio_tight_set_is_below_one():
    rng = np.random.default_rng(0)
    center = rng.normal(size=32)
    tight = center + 0.1 * rng.normal(size=(12, 32))
    loose = center + 1.0 * rng.normal(size=(60, 32))
    r = A.spread_ratio(tight, loose, rng=rng, reps_ai=200, reps_human=100, subsets=50)
    assert r["n"] == 12 and r["ratio"] < 0.3 and r["ratio_ci95"][1] < 1
    assert r["spread_ci95"][0] <= r["spread"] <= r["spread_ci95"][1]
    assert len(r["_ratio_boot"]) == 100


def test_median_ci_and_wilson():
    boots = [np.full(50, v) for v in (0.2, 0.4, 0.5, 0.6, 0.8)]
    lo, hi = A.median_ci(boots, reps=500, rng=np.random.default_rng(1))
    assert 0.2 <= lo <= 0.5 <= hi <= 0.8
    lo, hi = A.wilson_ci(90, 98)
    assert 0.83 < lo < 0.92 < hi < 0.97
    assert A.wilson_ci(0, 10)[0] == 0


def test_form_average_is_crisp_for_copies_and_cloudy_for_variety():
    a = np.full((64, 64), 255.0)
    a[30:34, :] = 0
    copies = A.form_average([a] * 12)
    assert copies.min() == 0 and copies[0, 0] == 255 and (copies[30:34] == 0).all()
    shifted = [np.roll(a, s, axis=0) for s in range(-20, 21, 4)]
    cloud = A.form_average(shifted)
    assert cloud.min() == 0 and (cloud < 255).sum() > (copies < 255).sum()
    assert A.pixel_spread(shifted) > A.pixel_spread([a] * 5) - 1e-6


# --- the benchmark script on a tiny fixture (no network, no DINOv2) ------------------------------

def _load_benchmark():
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "plato_benchmark.py"
    spec = importlib.util.spec_from_file_location("plato_benchmark", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_embed(images):
    """A stand-in for DINOv2: the picture shrunk to 12 x 12 gray pixels."""
    vecs = [256.0 - np.asarray(im.convert("L").resize((12, 12)), float).ravel() + 1.0 for im in images]
    return {"cls": np.array(vecs)}


def _fake_quickdraw(category, keep=200, max_lines=5000):
    """Varied synthetic 'people's drawings': random polylines in the 0-255 Quick, Draw! box."""
    rng = np.random.default_rng(sum(map(ord, category)))
    out = []
    for i in range(min(keep, 40)):
        strokes = []
        for _ in range(rng.integers(1, 4)):
            xs = rng.integers(0, 256, rng.integers(2, 6)).tolist()
            ys = rng.integers(0, 256, len(xs)).tolist()
            strokes.append([xs, ys])
        out.append({"key_id": str(i), "countrycode": "US", "drawing": strokes})
    return out


def _doodles(folder, n, jitter):
    folder.mkdir(parents=True)
    rng = np.random.default_rng(n)
    for i in range(n):
        img = Image.new("RGB", (300, 300), "white")
        d = ImageDraw.Draw(img)
        j = rng.integers(-jitter, jitter + 1, 4)
        d.rectangle((60 + j[0], 60 + j[1], 240 + j[2], 240 + j[3]), outline="black", width=8)
        d.line((60, 150, 240, 150 + j[0]), fill="black", width=8)
        img.save(folder / f"{i}.png")


def test_benchmark_on_a_tiny_fixture(tmp_path):
    bench = _load_benchmark()
    root = tmp_path / "my_model"
    _doodles(root / "chair", 6, 3)
    _doodles(root / "Teddy_Bear", 5, 4)
    _doodles(root / "boat", 2, 3)        # an alias of sailboat, too few pictures
    _doodles(root / "spaceship", 4, 3)   # not an Atlas concept
    ref = tmp_path / "ref.json"
    ref.write_text(json.dumps({"concepts": [{"quickdraw": "chair", "ratio": 0.37, "sdxl_ratio": 1.1, "rank": 9}]}))
    cache = tmp_path / "cache"
    out = bench.run(root, _fake_embed, cache=cache, reference=ref, model_id="fake", fetch=_fake_quickdraw,
                    name="Fixture", log=lambda *a: None)
    assert out["model"] == "Fixture" and out["n_concepts"] == 2
    assert out["unknown_folders"] == ["spaceship"]
    assert out["skipped"] == [{"concept": "boat", "pictures": 2, "reason": "fewer than 4"}]
    rows = {r["quickdraw"]: r for r in out["concepts"]}
    assert set(rows) == {"chair", "teddy-bear"} and rows["chair"]["n"] == 6
    for r in rows.values():  # near-copies of one box are far more uniform than random scribbles
        assert r["ratio"] < 0.5 and r["ratio_ci95"][0] <= r["ratio"] <= r["ratio_ci95"][1] < 1
    assert rows["chair"]["muse_ratio"] == 0.37 and rows["teddy-bear"]["muse_ratio"] is None
    s = out["summary"]
    assert s["below_1"] == 2 and s["median_ratio_ci95"][1] < 1 and s["muse_n_same_concepts"] == 1
    assert (cache / "human" / "chair.npz").is_file() and (cache / "human" / "teddy-bear.npz").is_file()

    def offline(*a, **k):
        raise AssertionError("the cached human reference should be reused")

    again = bench.run(root, _fake_embed, cache=cache, reference=ref, model_id="fake", fetch=offline,
                      log=lambda *a: None)
    assert [r["ratio"] for r in again["concepts"]] == [r["ratio"] for r in out["concepts"]]
    assert "Fixture: 2 concepts" in bench.report(out)


def test_benchmark_cli_lists_the_concepts():
    import subprocess
    import sys

    path = Path(__file__).resolve().parents[1] / "scripts" / "plato_benchmark.py"
    out = subprocess.run([sys.executable, str(path), "--list"], capture_output=True, text=True, check=True).stdout
    names = out.split("\n")
    assert "chair" in names and "teddy-bear" in names and len([n for n in names if n]) == 135


def test_benchmark_names_and_aliases():
    bench = _load_benchmark()
    table = bench.lookup()
    assert table[bench.norm("Sea_Turtle")].quickdraw == "sea turtle"
    assert table[bench.norm("person")].key == "yoga" and table[bench.norm("lamp")].key == "floor_lamp"
    assert table[bench.norm("teddy bear")].quickdraw == "teddy-bear"
    assert len({c.key for c in table.values()}) == 135


# --- the data files ------------------------------------------------------------------------------

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "public_data" / "plato_atlas.json"


def _web():
    from metalesionlab.web import app as web

    return web


def _ok_ci(lo_v_hi):
    lo, v, hi = lo_v_hi
    return lo - 1e-6 <= v <= hi + 1e-6


def test_public_data_schema():
    d = json.loads(PUBLIC.read_text())
    assert "Quick, Draw!" in d["attribution"] and "CC BY 4.0" in d["attribution"]
    s = d["summary"]
    assert s["n_concepts"] == len(d["concepts"]) == 135 and s["n_new"] == 98
    c = s["confirmatory_new_98"]
    assert set(c) >= {"H1_median_below_1", "H2_most_below_1"}
    assert _ok_ci((c["H1_median_below_1"]["ci95"][0], c["H1_median_below_1"]["median"], c["H1_median_below_1"]["ci95"][1]))
    assert c["H2_most_below_1"]["n"] == 98 and 0 <= c["H2_most_below_1"]["below_1"] <= 98
    for k in ("new", "all", "core"):
        assert _ok_ci((s[k]["median_ci95"][0], s[k]["median"], s[k]["median_ci95"][1]))
    ranks = [r["rank"] for r in d["concepts"]]
    assert ranks == list(range(1, 136))
    ratios = [r["ratio"] for r in d["concepts"]]
    assert ratios == sorted(ratios)
    for r in d["concepts"]:
        assert r["ratio"] > 0 and _ok_ci((r["ratio_ci95"][0], r["ratio"], r["ratio_ci95"][1]))
        assert abs(r["ratio"] - r["muse_spread"] / r["human_spread"]) < 5e-3
        assert r["domain"] in A.DOMAINS and r["origin"] in ("core", "forms", "new")
        assert r["n_ai"] in (12, 16) and isinstance(r["natural"], bool)
    p = s["predictors"]
    for k in ("P1_muse_spread_vs_human_spread", "P2_ratio_vs_zipf"):
        assert -1 <= p[k]["ci95"][0] <= p[k]["rho"] <= p[k]["ci95"][1] <= 1 and p[k]["n"] == 135
    assert set(p["P4_ols_log_muse_spread"]["coefficients"]) == {"log_human_spread", "zipf", "natural"}
    text = PUBLIC.read_text()
    assert "/Users/" not in text and ".png" not in text  # derived statistics only, no paths or pictures


def test_web_data_and_pictures():
    web = _web()
    d = json.loads((web.HERE / "data" / "plato_atlas.json").read_text())
    img = web.HERE / "static" / "img" / "plato_atlas"
    assert len(d["concepts"]) == 135 and d["summary"]["n_concepts"] == 135
    keys = [c["key"] for c in d["concepts"]]
    assert len(set(keys)) == 135
    for c in d["concepts"]:
        for f in ("form_muse", "form_people", "tiles_muse", "tiles_people"):
            assert (img / c[f]).is_file(), c[f]
        assert len(c["people_sample"]) == 12
    files = list(img.iterdir())
    assert all(f.suffix == ".webp" and f.stat().st_size <= 40 * 1024 for f in files)
    assert sum(f.stat().st_size for f in files) <= 4 * 1024 * 1024  # the page's picture budget
    assert "/Users/" not in (web.HERE / "data" / "plato_atlas.json").read_text()


# --- the page --------------------------------------------------------------------------------------

def test_page_and_api_render():
    from fastapi.testclient import TestClient

    from metalesionlab import brand
    from metalesionlab.web import plato_atlas_routes

    plato_atlas_routes._cache.clear()
    client = TestClient(_web().app)
    r = client.get("/plato/atlas")
    assert r.status_code == 200 and 'id="grid"' in r.text and 'id="rank-chart"' in r.text
    assert r.text.count('<header class="topbar site-head">') == 1
    assert "{{BRAND}}" not in r.text and brand.BRAND in r.text
    assert "Quick, Draw!" in r.text and "CC BY 4.0" in r.text and "Muse Image" in r.text and "Stable Diffusion XL" in r.text
    a = client.get("/api/plato/atlas")
    assert a.status_code == 200 and len(a.json()["concepts"]) == 135


def test_missing_data_is_a_friendly_503(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from metalesionlab.web import plato_atlas_routes

    monkeypatch.setattr(plato_atlas_routes, "DATA", tmp_path / "none.json")
    client = TestClient(_web().app)
    assert client.get("/api/plato/atlas").status_code == 503
    assert client.get("/plato/atlas").status_code == 200


def test_page_assets_stay_lean():
    web = _web()
    html = (web.HERE / "pages" / "plato_atlas.html").read_text()
    script = (web.HERE / "static" / "js" / "plato_atlas.js").read_text()
    css = (web.HERE / "static" / "css" / "plato_atlas.css").read_text()
    assert len(html) + len(script) + len(css) < 120 * 1024
    assert "localStorage" not in script and "fetch(" not in script  # replays shipped data; stores nothing
    assert "loading: 'lazy'" in script

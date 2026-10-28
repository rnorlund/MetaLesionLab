import json
from pathlib import Path

import numpy as np
import pytest

from metalesionlab.plato import CONCEPTS
from metalesionlab.plato_lifespan import (AI_KEYS, CANDIDATES, CHECKPOINTS, KIDDRAW_TO_KEY, SHARED_KEYS, TIER1_KEYS,
                                          age_equivalent, clip_strokes, direction_cosines, kiddraw_name,
                                          loo_proto_distances, matched_spread, nearest, ols_slope, parse_svg_path,
                                          parse_svgs, proto_distances, prototype, quad_fit, quad_peak, rdp,
                                          recognized, resample, sd_seed, to_quickdraw, weighted_spread)


def test_concept_sets():
    keys = {c.key for c in CONCEPTS}
    assert set(KIDDRAW_TO_KEY.values()) <= keys
    assert len(SHARED_KEYS) == 20 and "umbrella" not in SHARED_KEYS and "chair" == SHARED_KEYS[0]
    assert AI_KEYS[:10] == TIER1_KEYS and len(AI_KEYS) == 21 and set(AI_KEYS) == set(SHARED_KEYS) | {"umbrella"}
    assert CANDIDATES[-1] == "umbrella" and len(set(CANDIDATES)) == 21
    assert "floor_lamp" not in SHARED_KEYS and "yoga" not in SHARED_KEYS


def test_checkpoints_are_in_training_order():
    steps = [c[2] for c in CHECKPOINTS]
    assert steps == sorted(steps) and CHECKPOINTS[0][0] == "v1.1" and CHECKPOINTS[-1][0] == "v1.5"
    assert all(c[3] == "v1.2" for c in CHECKPOINTS[2:])


def test_seeds_are_per_picture_and_shared_across_checkpoints():
    assert sd_seed("chair", 0) != sd_seed("chair", 1) != sd_seed("sailboat", 0)
    assert len({sd_seed(k, i) for k in AI_KEYS for i in range(16)}) == 21 * 16


def test_parse_svg_path_relative_and_axis_moves():
    pts = parse_svg_path("M10,20l5,0v3h-2l-1,-1 -1,-1")
    assert pts == [(10, 20), (15, 20), (15, 23), (13, 23), (12, 22), (11, 21)]
    assert parse_svg_path("M1,1L4,5") == [(1, 1), (4, 5)]
    assert parse_svg_path("M0,0l1,1z")[-1] == (0, 0)
    assert parse_svg_path("M1.5.5l-.5,2e1") == [(1.5, 0.5), (1.0, 20.5)]  # compact numbers


def test_parse_svgs_reads_the_python2_list():
    field = "[u'M0,0l10,0', u'M5,5v5']"
    assert parse_svgs(field) == [[(0, 0), (10, 0)], [(5, 5), (5, 10)]]


def test_rdp_keeps_corners_and_drops_collinear_points():
    line = np.array([[0, 0], [1, 0.1], [2, 0], [3, 0.1], [10, 0]], float)
    assert rdp(line, 0.5).tolist() == [[0, 0], [10, 0]]
    corner = np.array([[0, 0], [5, 0], [10, 0], [10, 5], [10, 10]], float)
    assert rdp(corner, 0.5).tolist() == [[0, 0], [10, 0], [10, 10]]


def test_resample_spacing():
    p = resample(np.array([[0, 0], [10, 0]], float), 1.0)
    assert len(p) == 11 and np.allclose(np.diff(p[:, 0]), 1)


def test_to_quickdraw_aligns_scales_and_simplifies():
    qd = to_quickdraw([[(100, 100), (150, 100), (200, 100)], [(100, 150), (100, 200)]])
    xs = [x for s in qd for x in s[0]]
    ys = [y for s in qd for y in s[1]]
    assert min(xs) == 0 and min(ys) == 0 and max(max(xs), max(ys)) == 255
    assert qd[0] == [[0, 255], [0, 0]]  # the collinear middle point is simplified away
    assert to_quickdraw([]) == []
    assert to_quickdraw([[(5, 5)], [(5, 5), (5, 5)]]) == []  # a single point is not a drawing


def test_clip_strokes_splits_at_the_canvas_edge():
    out = clip_strokes([[(10, 10), (10, 30), (900, 30), (900, 40), (20, 40)]], hi=100, spacing=2)
    assert len(out) == 2  # leaves the canvas, comes back: two pieces
    assert all(0 <= x <= 100 and 0 <= y <= 100 for s in out for x, y in s)
    assert clip_strokes([[(500, 500), (600, 600)]], hi=100) == []


def test_kiddraw_name():
    assert kiddraw_name("chair_sketch_age8_cdm_run_v31527960931784.png") == ("chair", 8, "cdm_run_v31527960931784")
    assert kiddraw_name("sketches_full_dataset/an ice cream_sketch_age10_cdm_run_v6x.png")[:2] == ("ice cream", 10)
    with pytest.raises(ValueError):
        kiddraw_name("not_a_drawing.png")


def test_prototype_distances_and_leave_one_out():
    x = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    p = prototype(x)
    assert np.isclose(np.linalg.norm(p), 1)
    assert np.allclose(proto_distances(np.array([[1.0, 1.0]]), p), 0)
    loo = loo_proto_distances(np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]))
    # the third vector's leave-one-out prototype is (1, 0): distance 1
    assert np.isclose(loo[2], 1.0)


def test_nearest_and_leave_one_out_recognition():
    protos = np.array([[1.0, 0.0], [0.0, 1.0]])
    x = np.array([[0.9, 0.1], [0.2, 0.8]])
    assert nearest(x, protos).tolist() == [0, 1]
    assert recognized(x, 0, protos).tolist() == [True, False]
    # leave-one-out: a lone outlier in its own set loses its own prototype
    own = np.array([[1.0, 0.0], [1.0, 0.0], [0.1, 1.0]])
    assert recognized(own, 0, protos, loo_own=own).tolist() == [True, True, False]


def test_matched_spread_and_weighted_spread():
    d = 1 - np.eye(30)
    assert np.isclose(matched_spread(d, 16, 20), 1.0)
    assert np.isclose(weighted_spread(d, np.array([2] + [0] * 28 + [1])), 1.0)  # self pairs never count
    assert np.isnan(weighted_spread(d, np.array([3] + [0] * 29)))


def test_slopes_and_quadratic_peak():
    ages = np.arange(2, 11)
    assert np.isclose(ols_slope(ages, 2 * ages + 1), 2)
    assert np.isclose(ols_slope(ages, np.where(ages == 5, np.nan, ages)), 1)
    y = -(ages - 5.0) ** 2 + 3
    a, b, c = quad_fit(ages, y)
    assert np.isclose(c, -1) and np.isclose(quad_peak(b, c), 5)


def test_age_equivalent():
    ages, curve = [2, 3, 4], [0.1, 0.3, 0.5]
    assert np.isclose(age_equivalent(0.2, ages, curve), 2.5)
    assert age_equivalent(0.05, ages, curve) == "<2"
    assert age_equivalent(0.9, ages, curve) == ">4"
    # a dip is ignored (running maximum), so the answer is the first crossing
    assert np.isclose(age_equivalent(0.35, [2, 3, 4, 5], [0.1, 0.4, 0.2, 0.6]), 2 + 0.25 / 0.3)


def test_direction_cosines():
    a = {"x": np.array([1.0, 0.0]), "y": np.array([0.0, 1.0])}
    same, null = direction_cosines(a, a)
    assert np.isclose(same, 1) and np.isclose(null, 0)
    with pytest.raises(ValueError):
        direction_cosines({"x": a["x"]}, a)


# ---------- the public file and the page ----------

PUBLIC = Path(__file__).resolve().parents[1] / "public_data" / "plato_lifespan.json"


@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_lifespan.json not written yet")
def test_public_file_is_group_level_only():
    d = json.loads(PUBLIC.read_text())
    assert "CC BY-NC-SA 4.0" in d["credits"]["children"] and "CC BY 4.0" in d["credits"]["adults"]
    cells = d["children"]["cells"]
    assert set(cells) == set(SHARED_KEYS)
    assert all(c["n"] >= 23 for ages in cells.values() for c in ages.values())  # every cell pools many drawings
    text = PUBLIC.read_text()
    for field in ('"files"', '"cls"', '"patch_mean"', "session", "cdm_run", ".png", '"svgs"', '"drawing"'):
        assert field not in text  # no file names, embeddings, strokes or per-drawing values


@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_lifespan.json not written yet")
def test_page_and_api_render():
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_lifespan_routes

    plato_lifespan_routes._cache.clear()
    c = TestClient(web.app)
    r = c.get("/plato/lifespan")
    assert r.status_code == 200 and "The life of a chair" in r.text and 'id="stop"' in r.text
    assert "Meno" in r.text and "CC BY-NC-SA 4.0" in r.text and "We never show a child’s drawing" in r.text
    d = c.get("/api/plato/lifespan").json()
    assert d["children"]["things"][0] == "chair" and "v1.5" in d["ai"]["cells"]["chair"]
    for path in ("/static/js/plato_lifespan.js", "/static/css/plato_lifespan.css",
                 "/static/img/plato_lifespan/chair_sd_v15.webp", "/static/img/plato/series/lifespan.webp"):
        assert c.get(path).status_code == 200
    assert 'id="learn"' in r.text and "Watch an AI learn what a chair is" in r.text
    if "sketch_seeds" in d:
        for path in ("/static/img/plato_lifespan/sketch/learn_sprite.webp", "/static/img/plato_lifespan/sketch/stroke_order.json"):
            assert c.get(path).status_code == 200


def test_api_reports_missing_data(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_lifespan_routes

    monkeypatch.setattr(plato_lifespan_routes, "DATA", tmp_path / "missing.json")
    plato_lifespan_routes._cache.clear()
    assert TestClient(web.app).get("/api/plato/lifespan").status_code == 503


def test_page_static_files_stay_small_and_hold_no_childrens_drawings():
    from metalesionlab.web import app as web

    folder = web.HERE / "static" / "img" / "plato_lifespan"
    imgs = [f for f in folder.glob("*") if f.is_file()]
    sketch = [f for f in (folder / "sketch").glob("*") if f.is_file()]
    files = [web.HERE / "static" / "js" / "plato_lifespan.js", web.HERE / "static" / "css" / "plato_lifespan.css",
             web.HERE / "static" / "img" / "plato" / "series" / "lifespan.webp", *imgs]
    assert sum(f.stat().st_size for f in files if f.exists()) < 1.5 * 1024 * 1024
    assert sum(f.stat().st_size for f in sketch) < 1024 * 1024  # the time-lapse sprite and the stroke-order drawing
    assert {p.name for p in folder.glob("*") if p.is_dir()} <= {"sketch"}
    # only Quick, Draw! (adults), Muse Image, Stable Diffusion and sketch-model pictures; never kiddraw
    assert all(f.name.startswith(("chair_adults", "chair_muse", "chair_sd_", "sketch_step")) for f in imgs)
    assert all(f.name in ("learn_sprite.webp", "stroke_order.json") for f in sketch)


@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_lifespan.json not written yet")
def test_sketch_seeds_block_is_group_level_and_complete():
    d = json.loads(PUBLIC.read_text()).get("sketch_seeds")
    if d is None:
        pytest.skip("no multi-seed sketch results yet")
    from metalesionlab.plato_sketch import STEPS, TEMPS

    assert d["steps"] == STEPS and d["temps"] == TEMPS and d["plan"] == "docs/plato_sketch_plan.md"
    ch = d["concepts"]["chair"]
    for t in TEMPS:
        c = ch["curves"][f"t{t}"]
        assert all(len(c[m]["mean"]) == len(STEPS) for m in ("recog", "d_adult", "spread", "delta"))
        assert ch["tests"][f"t{t}"]["last"]["verdict"] in ("narrower", "null", "wider")
    assert "runs" not in ch  # per-run raw rows stay in the results file outside the repo
    a = d["animation"]
    assert a["seed"] == 1 and a["temp"] == 1.0 and len(a["spread"]) == len(STEPS)
    text = json.dumps(d)
    assert "NaN" not in text and '"drawing"' not in text and '"strokes": [' not in text


@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_lifespan.json not written yet")
def test_sketch_big_block_is_group_level_and_follows_the_addendum():
    d = json.loads(PUBLIC.read_text()).get("sketch_big")
    if d is None:
        pytest.skip("no larger-model results yet")
    from metalesionlab.plato_sketch import MODELS

    cfg = MODELS["big"]
    assert d["steps"] == cfg["steps"] and d["temps"] == cfg["temps"] and "addendum" in d["plan"] and d["batch"] == 100
    ch = d["concepts"]["chair"]
    assert ch["seeds"] == cfg["seeds"]["chair"] and ch["test_seeds"] == cfg["test_seeds"]["chair"]  # all runs in
    for t in cfg["temps"]:
        assert all(len(ch["curves"][f"t{t}"][m]["mean"]) == len(cfg["steps"]) for m in ("recog", "d_adult", "spread", "delta"))
        last = ch["tests"][f"t{t}"]["last"]
        assert last["n_seeds"] == len(cfg["test_seeds"]["chair"]) and last["verdict"] in ("narrower", "null", "wider")
        assert ch["tests_all_seeds"][f"t{t}"]["last"]["n_seeds"] == len(cfg["seeds"]["chair"])
    assert "runs" not in ch
    a = d["animation"]
    assert a["seed"] == cfg["anim"]["seed"] and a["temp"] == cfg["anim"]["temp"] and len(a["recog"]) == len(cfg["steps"])
    text = json.dumps(d)
    assert "NaN" not in text and '"drawing"' not in text and '"strokes": [' not in text

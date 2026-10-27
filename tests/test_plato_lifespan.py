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

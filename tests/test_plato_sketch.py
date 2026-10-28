import math

import numpy as np
import pytest

from metalesionlab.plato_sketch import (ANIM, MAC_STEPS, SEEDS, STEPS, TEMPS, boot_counts, boot_spread,
                                        categorical_from_uniform, is_drawing, log_x, make_noise, offset_from_noise,
                                        parse_sample_name, pen_frames, polyline_length, polyline_prefix, sample_name,
                                        softmax, stroke_stats,
                                        t_interval, two_level_delta, verdict)


def test_design_matches_the_plan():
    assert len(STEPS) == 20 and STEPS == sorted(set(STEPS)) and STEPS[0] == 0 and STEPS[-1] == 25600
    assert set(MAC_STEPS) <= set(STEPS)  # every Mac checkpoint is measured again
    ratios = [b / a for a, b in zip(STEPS[1:], STEPS[2:])]
    assert all(1.3 <= r <= 2.0 for r in ratios)  # roughly log-spaced
    assert TEMPS[0] == 1.0 and len(TEMPS) >= 3
    assert len(SEEDS["chair"]) >= 5 and len(SEEDS["cat"]) >= 5
    assert ANIM == {"seed": 1, "temp": 1.0, "n": 16}


def test_sample_names_round_trip():
    assert sample_name(3200, 0.8) == "step3200_t0.8" and sample_name(0, 1.0) == "step0_t1.0"
    assert parse_sample_name("step3200_t0.8") == (3200, 0.8)
    assert parse_sample_name(sample_name(25600, 0.6)) == (25600, 0.6)


def test_noise_is_fixed_per_seed_and_differs_between_seeds():
    a, b, c = make_noise(1, 5, 7), make_noise(1, 5, 7), make_noise(2, 5, 7)
    assert set(a) == {"u_mix", "u_pen", "e1", "e2"} and a["e1"].shape == (5, 7)
    assert all(np.array_equal(a[k], b[k]) for k in a)
    assert not np.array_equal(a["e1"], c["e1"])
    assert 0 <= a["u_mix"].min() and a["u_mix"].max() < 1
    # more drawings don't change the first ones' noise only if drawn the same way; fixed n is the contract
    assert make_noise(1, 5, 7)["u_pen"].shape == (5, 7)


def test_categorical_from_uniform_inverts_the_cdf():
    logits = np.log(np.array([[0.2, 0.5, 0.3]]))
    u = np.array([0.1, 0.2, 0.21, 0.69, 0.71, 0.999999])
    k = categorical_from_uniform(np.repeat(logits, len(u), 0), u)
    assert k.tolist() == [0, 0, 1, 1, 2, 2]
    # empirical frequencies match the probabilities, and temperature sharpens them
    rng = np.random.default_rng(0)
    uu = rng.random(200000)
    k = categorical_from_uniform(np.repeat(logits, len(uu), 0), uu)
    assert np.allclose(np.bincount(k, minlength=3) / len(uu), [0.2, 0.5, 0.3], atol=0.005)
    p_cold = softmax(logits, 0.5)[0]
    assert p_cold[1] > 0.5 and np.isclose(p_cold.sum(), 1)
    assert categorical_from_uniform(logits, np.array([1.0]))[0] == 2  # never past the last category


def test_torch_sampler_matches_numpy():
    torch = pytest.importorskip("torch")
    from metalesionlab.plato_sketch import categorical_from_uniform_torch

    rng = np.random.default_rng(1)
    logits, u = rng.normal(size=(50, 6)), rng.random(50)
    for temp in TEMPS:
        a = categorical_from_uniform(logits, u, temp)
        b = categorical_from_uniform_torch(torch.tensor(logits), torch.tensor(u), temp).numpy()
        assert np.array_equal(a, b)


def test_offset_from_noise_has_the_right_covariance():
    rng = np.random.default_rng(2)
    e1, e2 = rng.standard_normal(200000), rng.standard_normal(200000)
    dx, dy = offset_from_noise(1.0, -2.0, 2.0, 0.5, 0.6, e1, e2, 1.0)
    assert abs(dx.mean() - 1) < 0.02 and abs(dy.mean() + 2) < 0.01
    assert abs(dx.std() - 2) < 0.02 and abs(dy.std() - 0.5) < 0.01
    assert abs(np.corrcoef(dx, dy)[0, 1] - 0.6) < 0.01
    dx_cold, _ = offset_from_noise(0.0, 0.0, 2.0, 0.5, 0.0, e1, e2, 0.6)
    assert abs(dx_cold.std() - 2 * math.sqrt(0.6)) < 0.02  # temperature scales the variance


def test_stroke_stats():
    d = [[[0, 10, 20], [0, 0, 5]], [[5, 5], [10, 30]]]
    assert stroke_stats(d) == (2, 5)
    assert is_drawing(d) and not is_drawing([]) and not is_drawing(None)


def test_polyline_prefix_walks_at_constant_speed():
    xs, ys = [0, 10, 10], [0, 0, 10]
    assert polyline_length(xs, ys) == 20 and polyline_length([3], [4]) == 0
    assert polyline_prefix(xs, ys, 5) == ([0, 5], [0, 0])
    assert polyline_prefix(xs, ys, 15) == ([0, 10, 10], [0, 0, 5])
    assert polyline_prefix(xs, ys, 99) == ([0, 10, 10], [0, 0, 10])
    assert polyline_prefix(xs, ys, 0) == ([0], [0])


def test_pen_frames_draw_every_stroke_in_order():
    d = [[[0, 10, 20], [0, 0, 0]], [[5, 5], [10, 30]]]
    frames = pen_frames(d, speed=5, pause=2)
    assert len(frames) == 4 + 2 + 4 + 2  # 20 units in 4 frames, a pause, 20 units in 4 frames, a pause
    first, down = frames[0]
    assert down and first == [[[0, 5], [0, 0]]]
    assert frames[4] == ([[[0, 10, 20], [0, 0, 0]]], False)
    strokes, down = frames[-1]
    assert not down and strokes == [[[0, 10, 20], [0, 0, 0]], [[5, 5], [10, 30]]]
    assert len(pen_frames([[[3], [4]]], speed=5, pause=0)) == 2  # a dot still gets frames


def test_boot_spread_matches_plain_spread_without_resampling():
    rng = np.random.default_rng(3)
    x = rng.normal(size=(30, 4))
    d = np.linalg.norm(x[:, None] - x[None], axis=-1)
    ones = np.ones((1, 30))
    assert np.isclose(boot_spread(d, ones)[0], d[np.triu_indices(30, 1)].mean())
    c = boot_counts(30, 500, rng)
    assert c.shape == (500, 30) and np.all(c.sum(1) == 30)
    b = boot_spread(d, c)
    assert abs(b.mean() - d[np.triu_indices(30, 1)].mean()) < 0.05 * b.mean()


def test_t_interval():
    r = t_interval([1.0, 2.0, 3.0])
    assert r["mean"] == 2.0 and r["n"] == 3 and np.isclose(r["sd"], 1.0)
    half = 4.302652729911275 / math.sqrt(3)  # t(0.975, 2)
    assert np.allclose(r["ci95"], [2 - half, 2 + half])
    assert math.isnan(t_interval([1.0])["ci95"][0])
    assert t_interval([1.0, np.nan, 3.0])["n"] == 2


def test_two_level_delta_and_verdict():
    rng = np.random.default_rng(4)
    seed_boots = np.array([[0.30] * 1000, [0.32] * 1000, [0.31] * 1000])
    ref = np.full(1000, 0.36)
    d = two_level_delta(seed_boots, ref, rng)
    assert d.shape == (1000,) and d.max() < 0 and abs(d.mean() + 0.05) < 0.005
    assert d.min() >= 0.30 - 0.36 - 1e-12 and d.max() <= 0.32 - 0.36 + 1e-12
    assert verdict([-0.05, -0.01], [-0.04, -0.02]) == "narrower"
    assert verdict([-0.05, 0.01], [-0.04, -0.02]) == "null"
    assert verdict([0.01, 0.05], [0.02, 0.04]) == "wider"


def test_log_axis():
    assert log_x(0) == math.log10(25) and log_x(25600) > log_x(19200) > log_x(0)

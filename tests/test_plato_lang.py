import numpy as np
import pytest
from PIL import Image, ImageDraw

from metalesionlab.plato_lang import (
    CANVAS, bootstrap, canonical_ai, centroid_distances, cosine_distances, english_prompt, group_measures,
    permutation_test, render_strokes,
)


def unit(x):
    return x / np.linalg.norm(x, axis=1, keepdims=True)


def clustered(rng, k=6, n=10, d=32, offset=0.0):
    """k groups of n unit vectors around a shared direction, group means shifted by `offset`."""
    base = np.zeros(d)
    base[0] = 4.0
    shifts = offset * rng.normal(size=(k, d))
    x = np.concatenate([base + shifts[g] + rng.normal(size=(n, d)) for g in range(k)])
    return unit(x), np.repeat(np.arange(k), n)


def test_share_is_near_zero_when_groups_do_not_differ():
    rng = np.random.default_rng(0)
    shares = [group_measures(cosine_distances(e), lab, 6)["share"]
              for e, lab in (clustered(rng) for _ in range(200))]
    assert abs(np.mean(shares)) < 0.01


def test_share_and_between_grow_with_a_real_group_effect():
    rng = np.random.default_rng(1)
    emb, lab = clustered(rng, offset=1.0)
    m = group_measures(cosine_distances(emb), lab, 6)
    assert m["share"] > 0.2
    assert m["B_mean"] > 0
    assert m["W"].shape == (6,)


def test_between_matches_half_the_squared_distance_of_true_means():
    # Euclidean version of the identity the measure relies on: B = |mu_g - mu_h|^2 / 2.
    rng = np.random.default_rng(2)
    mus = np.array([[0.0, 0.0], [3.0, 4.0]])
    x = np.concatenate([mus[g] + rng.normal(size=(4000, 2)) for g in range(2)])
    lab = np.repeat([0, 1], 4000)
    D = ((x[:, None, :] - x[None, :, :]) ** 2).sum(-1) / 2
    assert group_measures(D, lab, 2)["B"][0, 1] == pytest.approx(12.5, rel=0.05)


def test_permutation_and_bootstrap_shapes():
    rng = np.random.default_rng(3)
    emb, lab = clustered(rng, offset=1.0)
    perm = permutation_test(emb, lab, 6, n_perm=50)
    assert perm["share_p"] <= 0.05 and perm["centroid_mean"] > perm["centroid_mean_null"]
    boot = bootstrap(emb, lab, 6, n_boot=50)
    assert boot["W_ci"].shape == (2, 6) and boot["share_ci"][0] <= boot["share_ci"][1]
    assert centroid_distances(emb, lab, 6).shape == (6, 6)


def test_render_strokes_centres_the_drawing():
    img = render_strokes([[[0, 100], [0, 0]], [[0, 0], [0, 50]]])
    assert img.size == (CANVAS, CANVAS)
    ink = np.argwhere(np.asarray(img) < 128)
    assert abs(ink[:, 1].mean() - CANVAS / 2) < 40


def test_canonical_ai_crops_and_whitens(tmp_path):
    img = Image.new("RGB", (400, 300), (200, 200, 200))  # grey paper
    ImageDraw.Draw(img).rectangle((20, 20, 80, 60), outline="black", width=3)
    path = tmp_path / "d.png"
    img.save(path)
    out = np.asarray(canonical_ai(path))
    assert out.shape == (CANVAS, CANVAS)
    assert out[0, 0] == 255 and (out < 128).sum() > 100


def test_english_prompt_article():
    assert "an umbrella" in english_prompt("umbrella") and "a chair" in english_prompt("chair")

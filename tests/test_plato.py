import numpy as np
from PIL import Image, ImageDraw

from metalesionlab.plato import (BY_KEY, CONCEPTS, DEMO_MISSING, bootstrap_spread, cosine_distances, ink_crop,
                                 render_strokes, spread, subsample_spread)


def test_concepts_are_quickdraw_categories_in_priority_order():
    assert [c.key for c in CONCEPTS[:2]] == ["chair", "sailboat"]
    assert all(c.n_ai == 16 for c in CONCEPTS if c.tier == 1)
    assert all(c.n_ai == 12 for c in CONCEPTS if c.tier == 2)
    assert not {c.quickdraw for c in CONCEPTS} & set(DEMO_MISSING)
    assert BY_KEY["yoga"].label == "person" and BY_KEY["scissors"].phrase == "a pair of scissors"


def test_spread_is_mean_off_diagonal_distance():
    x = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    d = cosine_distances(x)
    assert np.allclose(np.diag(d), 0)
    expected = np.mean([1.0, 1 - 1 / np.sqrt(2), 1 - 1 / np.sqrt(2)])
    assert np.isclose(spread(d), expected)
    assert np.isclose(spread(d, np.array([0, 1])), 1.0)


def test_bootstrap_never_pairs_a_picture_with_itself():
    # identical pictures would give spread 0; distinct pictures at distance 1 must always give 1
    d = 1 - np.eye(6)
    assert np.allclose(bootstrap_spread(d, reps=200), 1.0)
    assert np.allclose(subsample_spread(d, k=3, reps=20), 1.0)


def test_render_and_crop_put_ink_in_a_centered_square():
    img = render_strokes([[[0, 100], [0, 0]]])  # one horizontal stroke
    assert img.size == (256, 256)
    assert np.asarray(img.convert("L")).min() == 0
    # a gray-paper picture with a small dark square: the paper becomes white, the square fills the frame
    paper = Image.new("L", (300, 200), 200)
    ImageDraw.Draw(paper).rectangle((140, 90, 160, 110), outline=0, width=3)
    out = np.asarray(ink_crop(paper.convert("RGB")).convert("L"))
    assert out.shape == (256, 256)
    assert out[0, 0] == 255 and out[128, 128] == 255  # white corner and white inside the square
    assert out[:, 20:40].min() < 100  # the square's left edge sits near the left margin

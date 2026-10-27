"""Silhouette and outline maker, solidity and corner count (metalesionlab/plato_shapes.py)."""
import math

import numpy as np
from PIL import Image, ImageDraw

from metalesionlab import plato_cratylus as pk
from metalesionlab import plato_shapes as ps


def _drawing(draw_fn, side=400):
    img = Image.new("L", (side, side), 255)
    draw_fn(ImageDraw.Draw(img))
    return img


def _star(k=5, r1=170, r2=70, c=200):
    pts = []
    for i in range(2 * k):
        r = r1 if i % 2 == 0 else r2
        a = math.pi * i / k - math.pi / 2
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    return pts


def _sil(img, **kw):
    return ps.silhouette_mask(ps.ink_mask(ps.to_gray(img, None)), **kw)


def test_flood_fill_fills_a_closed_outline():
    img = _drawing(lambda d: d.ellipse((60, 60, 340, 340), outline=0, width=4))
    sil = _sil(img)
    area = sil.mask.sum()
    assert abs(area - math.pi * 140 ** 2) / (math.pi * 140 ** 2) < 0.03
    assert sil.radius == 0 and sil.fill_ratio > 10


def test_flood_fill_fills_holes_and_keeps_the_outside_empty():
    def draw(d):
        d.rectangle((50, 50, 350, 350), outline=0, width=4)
        d.ellipse((150, 150, 250, 250), outline=0, width=4)  # an inner ring: a hole, filled like the SV silhouettes
    sil = _sil(_drawing(draw))
    assert sil.mask[200, 200] and sil.mask[100, 100]
    assert not sil.mask[20, 20] and not sil.mask[380, 380]


def test_small_gap_is_closed_but_shape_is_kept():
    # a circle with a ~10 px gap leaks at radius 0; the search closes it
    img = _drawing(lambda d: d.arc((60, 60, 340, 340), 2, 358, fill=0, width=4))
    sil = _sil(img)
    assert sil.radius > 0
    assert sil.mask[200, 200]
    assert abs(sil.mask.sum() - math.pi * 140 ** 2) / (math.pi * 140 ** 2) < 0.05


def test_a_wide_open_curve_is_not_forced_shut_but_can_be_sealed():
    img = _drawing(lambda d: d.arc((60, 60, 340, 340), 30, 330, fill=0, width=4))  # a C open on the right
    ink = ps.ink_mask(ps.to_gray(img, None))
    assert ps.silhouette_mask(ink).fill_ratio < 1.5
    sealed, edge = ps.seal_open_drawing(ink)
    assert edge is not None and sealed[200, 200]


def test_outline_is_a_thin_ring_on_the_silhouette_edge():
    img = _drawing(lambda d: d.ellipse((60, 60, 340, 340), fill=0))
    sil = _sil(img).mask
    ring = ps.outline_mask(sil, width=5)
    assert ring.sum() < 0.1 * sil.sum()
    assert not ring[200, 200] and ring[200, 62]
    assert (ring & ~sil).sum() == 0


def test_cast_shadow_is_gray_on_a_lighter_wall():
    sil = _sil(_drawing(lambda d: d.ellipse((100, 100, 300, 300), fill=0))).mask
    sh = np.asarray(ps.cast_shadow(sil, side=256).convert("L"), float)
    assert sh.shape == (256, 256)
    centre, corner = sh[100:156, 100:156].mean(), sh[:20, :20].mean()
    assert 30 < centre < corner  # darker than the wall, but not black


def test_solidity():
    disc = _sil(_drawing(lambda d: d.ellipse((60, 60, 340, 340), fill=0))).mask
    square = _sil(_drawing(lambda d: d.rectangle((80, 80, 320, 320), fill=0))).mask
    star = _sil(_drawing(lambda d: d.polygon(_star(), fill=0))).mask
    assert ps.solidity(disc) > 0.97 and ps.solidity(square) > 0.98
    assert 0.4 < ps.solidity(star) < 0.6


def test_corner_count():
    disc = _sil(_drawing(lambda d: d.ellipse((60, 60, 340, 340), fill=0))).mask
    square = _sil(_drawing(lambda d: d.rectangle((80, 80, 320, 320), fill=0))).mask
    assert ps.corner_count(disc) == 0
    assert ps.corner_count(square) == 4
    for k in (5, 8):
        star = _sil(_drawing(lambda d, k=k: d.polygon(_star(k, 170, 80), fill=0))).mask
        assert ps.corner_count(star) == k


def test_choice_arm_shapes_are_round_and_spiky():
    for seed in range(4):
        r, k = pk.round_shape(seed), pk.spiky_shape(seed)
        assert ps.corner_count(r) == 0 and ps.solidity(r) > 0.8
        assert ps.corner_count(k) >= 7 and ps.solidity(k) < 0.55


def test_stroke_width():
    img = _drawing(lambda d: d.ellipse((60, 60, 340, 340), outline=0, width=6))
    w = ps.stroke_width(ps.ink_mask(ps.to_gray(img, None)))
    assert 4 <= w <= 8

"""The stronger chair learners for "Watch an AI learn what a chair is": the larger Sketch-RNN (the plan's addendum),
the pixel diffusion pilot and Magenta's pretrained chair (a ceiling reference)."""
import base64
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from metalesionlab.plato_sketch import BIG, DIFF, LAST3, MODELS, SEEDS, STEPS, TEMPS, make_noise, model_run_name

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_model_configs():
    small, big = MODELS["small"], MODELS["big"]
    # the small model's entry is exactly the original plan's
    assert small["steps"] == STEPS and small["temps"] == TEMPS and small["seeds"] == SEEDS and small["last3"] == LAST3
    assert small["test_seeds"] == SEEDS and small["public_key"] == "sketch_seeds"
    # the larger model's checkpoints extend the small one's, still roughly log-spaced, to 102,400
    assert big["steps"][:len(STEPS)] == STEPS and big["steps"] == sorted(set(big["steps"])) and big["steps"][-1] == 102400
    assert all(1.3 <= b / a <= 2.0 for a, b in zip(big["steps"][1:], big["steps"][2:]))
    assert big["last3"] == [51200, 76800, 102400] and big["temps"][0] == 1.0 and 1.0 in big["temps"]
    # the test leaves out the pilot seed, whose drawings and measures were seen first; at least 3 fresh seeds
    assert 1 not in big["test_seeds"]["chair"] and len(big["test_seeds"]["chair"]) >= 3
    assert set(big["test_seeds"]["chair"]) < set(big["seeds"]["chair"])
    assert big["anim"]["seed"] == 1 and big["anim"]["temp"] in big["temps"] and big["anim"]["n"] == 16
    assert big["public_key"] == "sketch_big" and BIG["hidden"] == 2048
    assert model_run_name("small", "chair", 3) == "chair_s3" and model_run_name("big", "chair", 3) == "big_s3"
    assert DIFF["steps"][:len(STEPS)] == STEPS


def test_big_model_batches_and_schedule():
    torch = pytest.importorskip("torch")
    big = load("plato_sketch_big")
    X = torch.ones(10, 5, 5)
    mask = torch.ones(10, 4)
    xb, mb = big.batch_at(X, mask, torch.arange(10), torch.Generator().manual_seed(0))
    s = xb[:, :, :2]
    assert ((s >= 0.85 - 1e-6) & (s <= 1.15 + 1e-6)).all() and (xb[:, :, 2:] == 1).all()  # only offsets are scaled
    assert torch.allclose(s[:, 0], s[:, 3])  # one scale per drawing and axis
    assert np.isclose(big.lr_at(0, 1e-3), 1e-3) and big.lr_at(10 ** 6, 1e-3) == BIG["min_lr"]
    assert big.lr_at(1000, 1e-3) < 1e-3


def test_big_model_samples_with_the_fixed_noise_sampler():
    pytest.importorskip("torch")
    big = load("plato_sketch_big")
    seeds = load("plato_sketch_seeds")
    torch = pytest.importorskip("torch")
    model = big.build("cpu", hidden=32)
    torch.manual_seed(0)
    a = seeds.sample_fixed(model, make_noise(1, 6, 30), 1.0, 50.0, "cpu", max_len=30)
    b = seeds.sample_fixed(model, make_noise(1, 6, 30), 1.0, 50.0, "cpu", max_len=30)
    assert a == b and len(a) == 6  # same noise and weights, same drawings


def _fake_gen_model(H: int = 3, seed: int = 0):
    """A tiny Magenta 'gen' model in sketch-rnn-js's format: int16 weights, base64, scaled by 10 / 32767."""
    rng = np.random.default_rng(seed)
    shapes = [[H, 123], [123], [5, 4 * H], [H, 4 * H], [4 * H]]
    ints = [rng.integers(-3000, 3000, size=int(np.prod(s))).astype("<i2") for s in shapes]
    blobs = [base64.b64encode(a.tobytes()).decode() for a in ints]
    info = {"mode": 2, "max_seq_len": 12, "name": "chair", "scale_factor": 100.0}
    return [info, shapes, blobs], [a.astype(float) / 32767 * 10 for a in ints]


def test_magenta_weights_decode_like_sketch_rnn_js():
    mg = load("plato_sketch_magenta")
    raw, expect = _fake_gen_model()
    info, ws = mg.decode_weights(raw)
    assert info["mode"] == 2 and len(ws) == 5
    for w, e, d in zip(ws, expect, raw[1]):
        assert w.shape == tuple(d) and np.allclose(w.ravel(), e)


def test_magenta_lstm_cell_and_sampler():
    mg = load("plato_sketch_magenta")
    raw, _ = _fake_gen_model(H=3)
    m = mg.MagentaGen(json.loads(json.dumps(raw)))
    rng = np.random.default_rng(1)
    x, h, c = rng.normal(size=(2, 5)), rng.normal(size=(2, 3)), rng.normal(size=(2, 3))
    z = np.concatenate([x, h], 1) @ m.W + m.b
    sig = lambda v: 1 / (1 + np.exp(-v))  # noqa: E731
    i, g, f, o = z[:, :3], z[:, 3:6], z[:, 6:9], z[:, 9:]  # sketch_rnn.js: input, cell, forget (+1), output
    c2 = c * sig(f + 1) + sig(i) * np.tanh(g)
    h2, c3 = m.step(x, h, c)
    assert np.allclose(c3, c2) and np.allclose(h2, np.tanh(c2) * sig(o))
    pi, mx, my, sx, sy, r, pen = m.params(h2)
    assert pi.shape == (2, 20) and pen.shape == (2, 3) and (sx > 0).all() and (np.abs(r) < 1).all()
    d1 = m.sample(make_noise(1, 4, 12), 0.5)
    assert d1 == m.sample(make_noise(1, 4, 12), 0.5) and len(d1) == 4


def test_diffusion_schedule_noise_and_deterministic_sampling():
    torch = pytest.importorskip("torch")
    df = load("plato_sketch_diffusion")
    a, s = df.alpha_sigma(torch.tensor([0.0, 0.3, 0.7, 1.0]))
    assert np.isclose(float(a[0]), 1) and float(s[0]) < 1e-6 and float(a[-1]) < 1e-6
    assert torch.allclose(a ** 2 + s ** 2, torch.ones(4), atol=1e-6) and (a[1:] < a[:-1]).all()
    n1, n2 = df.make_image_noise(1, 3, 32), df.make_image_noise(1, 3, 32)
    assert n1.shape == (3, 1, 32, 32) and np.array_equal(n1, n2) and not np.array_equal(n1, df.make_image_noise(2, 3, 32))
    model = df.build_unet(32).eval()
    assert model(torch.zeros(2, 1, 32, 32), torch.rand(2)).shape == (2, 1, 32, 32)
    x = torch.tensor(n1)
    u1, u2 = df.to_u8(df.ddim(model, x, 3)), df.to_u8(df.ddim(model, x, 3))
    assert u1.dtype == np.uint8 and np.array_equal(u1, u2)  # DDIM with eta = 0: same noise, same picture


def test_diffusion_blank_pictures_and_measuring_prep():
    df = load("plato_sketch_diffusion")
    blank = np.full((64, 64), 250, np.uint8)
    ink = blank.copy()
    ink[20:40, 30] = 0
    assert not df.has_ink(blank) and df.has_ink(ink)
    out = df._prep(ink)
    assert out.shape == (256, 256, 3) and out.min() < 128  # back at the measuring size, ink-cropped, ink kept


def test_compare_grid_layout():
    pytest.importorskip("PIL")
    cmp = load("plato_sketch_compare")
    from PIL import Image

    g = cmp.grid([Image.new("RGB", (cmp.CELL, cmp.CELL), "white")] * 16)
    assert g.size == (4 * cmp.CELL + 3 * cmp.GAP,) * 2
    t = cmp.tile_strokes([[[0, 255], [0, 255]]])
    assert t.size == (cmp.CELL, cmp.CELL) and cmp.tile_strokes(None).getextrema() == ((255, 255),) * 3

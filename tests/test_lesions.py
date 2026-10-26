"""Lesion hooks, localizer statistics and severity bisection on tiny CPU stand-ins for Glimmer."""
import json
import random
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch import nn

from metalesionlab.lesions import LesionSpec, Moments, UnitStats, lesion, site_dims, site_spec
from metalesionlab.localizers import (Localizer, random_control, random_like, scramble_tiles, scramble_words,
                                      top_units, welch_t)
from metalesionlab.model_lab import SeverityCurve, answer_text, code_answer, collate

L, N, H, HD, VT, PJ, D = 3, 8, 2, 4, 6, 5, 7  # layers, neurons, heads, head dim, vision/projector widths, hidden


class Layer(nn.Module):
    def __init__(self):
        super().__init__()
        self.mlp = nn.Module()
        self.mlp.down_proj = nn.Linear(N, D, bias=False)
        self.self_attn = nn.Module()
        self.self_attn.o_proj = nn.Linear(H * HD, D, bias=False)


class Adapter(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(VT, 3)

    def forward(self, x):
        return self.fc1(x)


class FakeGlimmer(nn.Module):
    """Only the module paths and config fields the lesion code reads."""

    def __init__(self):
        super().__init__()
        self.model = nn.Module()
        self.model.language_model = nn.Module()
        self.model.language_model.layers = nn.ModuleList([Layer() for _ in range(L)])
        self.model.vision_adapter = Adapter()
        self.model.vision_projection = nn.Linear(3, PJ, bias=False)
        cfg = SimpleNamespace(num_attention_heads=H, head_dim=HD)
        self.config = SimpleNamespace(get_text_config=lambda: cfg)

    @property
    def device(self):
        return torch.device("cpu")


def capture(module, x, pre=True):
    """What `module` receives (pre=True) or returns when called on x."""
    seen = {}
    hook = (module.register_forward_pre_hook(lambda _m, a: seen.setdefault("x", a[0])) if pre
            else module.register_forward_hook(lambda _m, _a, out: seen.setdefault("x", out)))
    out = module(x)
    hook.remove()
    return seen["x"] if pre else out


def fake_stats():
    return UnitStats(mlp_mean=torch.full((L, N), 7.0), mlp_std=torch.ones(L, N),
                     head_mean=torch.full((L, H * HD), 3.0), head_std=torch.ones(L, H * HD),
                     vision_tower_mean=torch.full((VT,), 2.0), vision_tower_std=torch.ones(VT),
                     projector_mean=torch.full((PJ,), 5.0), projector_std=torch.ones(PJ))


@pytest.fixture
def model():
    torch.manual_seed(0)
    return FakeGlimmer()


def test_spec_round_trips_through_json():
    spec = LesionSpec(method="noise", mlp={3: [5, 1]}, heads={7: None}, components={"projector": None},
                      layers=[10, 11], noise_scale=0.5, seed=2, name="x", recipe={"localizer": "naming"})
    back = LesionSpec.from_dict(json.loads(json.dumps(spec.to_dict())))
    assert back.mlp == {3: [1, 5]} and back.heads == {7: None} and back.components == {"projector": None}
    assert (back.method, back.noise_scale, back.seed, back.layers, back.recipe) == ("noise", 0.5, 2, [10, 11],
                                                                                     {"localizer": "naming"})
    assert spec.to_dict(units=False)["mlp"] == {"3": 2}
    with pytest.raises(ValueError):
        LesionSpec(method="scramble")
    with pytest.raises(ValueError):
        LesionSpec(components={"retina": None})


def test_counts_include_whole_layer_bands(model):
    spec = LesionSpec(mlp={0: [1, 2]}, heads={1: [0]}, layers=[2])
    c = spec.counts(site_dims(model))
    assert c["mlp"] == 2 + N and c["heads"] == 1 + H
    assert c["mlp_by_layer"] == {0: 2, 2: N}


def test_zero_mlp_neurons_only_in_chosen_layer_and_reversible(model):
    down = model.model.language_model.layers[1].mlp.down_proj
    other = model.model.language_model.layers[0].mlp.down_proj
    x = torch.randn(2, 3, N)
    with lesion(model, LesionSpec(mlp={1: [0, 3]})):
        seen = capture(down, x)
        assert torch.all(seen[..., [0, 3]] == 0)
        assert torch.equal(seen[..., [1, 2, 4, 5, 6, 7]], x[..., [1, 2, 4, 5, 6, 7]])
        assert torch.equal(capture(other, x), x)
    assert torch.equal(capture(down, x), x)  # hooks removed


def test_zero_head_covers_its_whole_slice(model):
    o = model.model.language_model.layers[2].self_attn.o_proj
    x = torch.randn(1, 2, H * HD)
    with lesion(model, LesionSpec(heads={2: [1]})):
        seen = capture(o, x)
    assert torch.all(seen[..., HD:] == 0) and torch.equal(seen[..., :HD], x[..., :HD])


def test_mean_lesion_uses_reference_means(model):
    stats = fake_stats()
    down = model.model.language_model.layers[0].mlp.down_proj
    x = torch.randn(1, 4, N)
    with lesion(model, LesionSpec(method="mean", mlp={0: [2]}), stats):
        seen = capture(down, x)
    assert torch.all(seen[..., 2] == 7.0) and torch.equal(seen[..., 3], x[..., 3])
    with pytest.raises(ValueError):
        with lesion(model, LesionSpec(method="mean", mlp={0: [2]})):
            pass


def test_noise_is_seeded_and_scaled(model):
    stats = fake_stats()
    down = model.model.language_model.layers[0].mlp.down_proj
    x = torch.zeros(4096, N)
    spec = LesionSpec(method="noise", mlp={0: [1]}, noise_scale=2.0, seed=3)
    with lesion(model, spec, stats):
        a = capture(down, x)
    with lesion(model, spec, stats):
        b = capture(down, x)
    assert torch.equal(a, b)
    assert abs(a[:, 1].std().item() - 2.0) < 0.15 and torch.all(a[:, 0] == 0)


def test_components_and_bands(model):
    stats = fake_stats()
    vt_in = torch.randn(5, VT)
    with lesion(model, LesionSpec(method="mean", components={"vision_tower": None, "projector": [0]}), stats):
        assert torch.all(capture(model.model.vision_adapter, vt_in) == 2.0)
        out = capture(model.model.vision_projection, torch.randn(5, 3), pre=False)
        assert torch.all(out[:, 0] == 5.0)
    x = torch.randn(1, 2, N)
    with lesion(model, {"layers": [1]}):  # a plain dict works too
        assert torch.all(capture(model.model.language_model.layers[1].mlp.down_proj, x) == 0)
        assert torch.all(capture(model.model.language_model.layers[1].self_attn.o_proj, torch.randn(1, 2, H * HD)) == 0)


def test_hooks_removed_after_error(model):
    down = model.model.language_model.layers[0].mlp.down_proj
    with pytest.raises(RuntimeError):
        with lesion(model, LesionSpec(mlp={0: None})):
            raise RuntimeError("boom")
    assert not down._forward_pre_hooks


def test_welch_t_and_top_units():
    a, b = Moments((2, 3), "cpu"), Moments((2, 3), "cpu")
    g = torch.Generator().manual_seed(0)
    base = torch.zeros(2, 3)
    base[1, 2] = 3.0  # one unit responds more in A
    a.add(base + torch.randn(50, 2, 3, generator=g))
    b.add(torch.randn(50, 2, 3, generator=g))
    t = welch_t(a, b)
    assert t.argmax().item() == 5 and t[1, 2] > 10
    assert top_units(t, 1 / 6) == {1: [2]}
    assert top_units(torch.full((2, 3), -1.0), 0.5) == {}  # only positive t is kept
    silent = Moments((1,), "cpu")
    silent.add(torch.zeros(4, 1))
    assert welch_t(silent, silent).item() == 0


def test_random_control_matches_counts_and_avoids_targets():
    units = {0: [1, 2, 3], 4: [0]}
    r = random_like(units, size=10, seed=1)
    assert {k: len(v) for k, v in r.items()} == {0: 3, 4: 1}
    assert not set(r[0]) & {1, 2, 3} and r[4] != [0]
    spec = LesionSpec(method="mean", heads={5: [1, 2]}, name="loc")
    ctrl = random_control(spec, SimpleNamespace(mlp=10, heads=32), seed=0)
    assert ctrl.method == "mean" and len(ctrl.heads[5]) == 2 and ctrl.recipe["control"] == "random"


def test_localizer_save_load(tmp_path):
    loc = Localizer("naming", {"mlp": torch.randn(L, N), "heads": torch.randn(L, H)}, 4, 4, {"contrast": "naming"})
    loc.save(tmp_path / "loc.pt")
    back = Localizer.load(tmp_path / "loc.pt")
    assert torch.allclose(back.t["mlp"], loc.t["mlp"], atol=1e-2) and back.meta == {"contrast": "naming"}
    assert len(loc.summary()["heads_t"]) == L


def test_scramblers():
    s = "The cat sleeps on the warm windowsill."
    w = scramble_words(s, random.Random(0))
    assert sorted(w.split()) == sorted(s.rstrip(".").lower().split()) and w != s.rstrip(".").lower()
    from PIL import Image
    img = Image.new("RGB", (100, 100), "white")
    img.paste((0, 0, 0), (0, 0, 50, 50))
    out = scramble_tiles(img, grid=4, side=64)
    assert out.size == (64, 64)
    pixels = lambda im: sorted(map(tuple, np.asarray(im).reshape(-1, 3).tolist()))
    assert pixels(out) == pixels(img.resize((64, 64)))  # same pixels, moved


def test_collate_left_pads_and_counts_positions():
    a = {"input_ids": torch.tensor([[5, 6, 7]]), "attention_mask": torch.ones(1, 3, dtype=torch.long)}
    b = {"input_ids": torch.tensor([[8]]), "attention_mask": torch.ones(1, 1, dtype=torch.long)}
    batch = collate([a, b], pad_id=0)
    assert batch["input_ids"].tolist() == [[5, 6, 7], [0, 0, 8]]
    assert batch["attention_mask"].tolist() == [[1, 1, 1], [0, 0, 1]]
    assert batch["position_ids"][:, -1].tolist() == [2, 0]


def test_severity_bisection_finds_targets_and_reuses_points():
    calls = []

    def acc(frac):  # accuracy falls smoothly with the lesioned fraction
        calls.append(frac)
        return max(0.0, 1.0 - 4 * frac)

    curve = SeverityCurve(acc)
    for target in (0.8, 0.6, 0.4):
        level = curve.bisect(target, 0.0, 0.2, steps=5)
        assert level["within_tol"], level
        assert abs(level["dose"] - (1 - target) / 4) < 0.02
    assert len(calls) <= 12
    too_mild = SeverityCurve(lambda f: 0.95).bisect(0.4, 0.0, 0.2)
    assert not too_mild["reachable"] and too_mild["evaluations"] == 1
    edge = SeverityCurve(lambda f: 0.75).bisect(0.8, 0.0, 0.2)  # |0.75 - 0.8| is 0.05000000000000004
    assert edge["within_tol"] and edge["evaluations"] == 1


@pytest.mark.parametrize("said,lang,expected", [
    ("cat", "en", "cat"),
    ("The object in the picture is a cat", "en", "a cat"),
    ("The object is an umbrella. The picture", "en", "an umbrella"),
    ("It's a **saw**.", "en", "a saw"),
    ("El objeto de la imagen es un **paraguas**.", "es", "un paraguas"),
    ("La imagen muestra una tetera.", "es", "una tetera"),
    ("Gato", "es", "Gato"),
])
def test_answer_text_drops_carrier_phrases(said, lang, expected):
    assert answer_text(said, lang) == expected


def test_carrier_answers_are_coded_by_their_noun():
    assert code_answer("silbato", "El objeto de la imagen es un micrófono.", "es").code != "Description"
    assert code_answer("bench", "The object is a park bench. The", "en").code == "Correct"


def test_site_spec_names():
    assert site_spec("vision_tower", "noise", 8).components == {"vision_tower": None}
    assert site_spec("layers:40-43").layers == [40, 41, 42, 43]
    assert site_spec("mlp:5").mlp == {5: None} and site_spec("heads:1-2").heads == {1: None, 2: None}
    with pytest.raises(ValueError):
        site_spec("cortex")

"""Watch an AI forget what a chair is (docs/plato_sketch_forget_plan.md): the design, the reversible damage hooks,
and the measures and rules for the plan's three questions."""
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

from metalesionlab.plato_sketch import MODELS
from metalesionlab.plato_sketch_forget import (ARMS, DISPLAY, HIDDEN, NOISE, PRIMARY_DOSES, SILENCE, STEP, TEMPS, TEST_SEEDS,
                                               gap_verdict, half_forgotten, keep_mask, kept_share, learn_interp, n_off,
                                               nearest_person, nearest_step, parse_set_name, path_doses, path_gap, set_name,
                                               sign_verdict, unit_order)

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_design_matches_the_learning_run():
    big = MODELS["big"]
    assert STEP == big["steps"][-1] == 102400 and HIDDEN == 2048
    # the display run is the learning animation's: seed 1, its temperature, 16 drawings; the tests leave seed 1 out
    assert DISPLAY["seed"] == big["anim"]["seed"] and DISPLAY["temp"] == big["anim"]["temp"] and DISPLAY["n"] == 16
    assert TEST_SEEDS == big["test_seeds"]["chair"] and set(TEMPS) <= set(big["temps"]) and 1.0 in TEMPS
    assert SILENCE[:10] == [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9] and SILENCE[-1] == 1.0
    assert PRIMARY_DOSES == SILENCE[1:10] and NOISE[0] == 0 and NOISE == sorted(NOISE)
    assert set(ARMS) == {"silence", "noise", "readout"} and ARMS["readout"] == SILENCE
    assert path_doses("silence") == PRIMARY_DOSES and path_doses("noise") == NOISE[1:]
    assert parse_set_name(set_name("silence", 0.3, 1.0)) == ("silence", 0.3, 1.0) and set_name("noise", 0.05, 0.4) == "noise_d0.05_t0.4"


def test_unit_orders_are_fixed_per_seed_and_doses_nested():
    a, b = unit_order(2), unit_order(2)
    assert np.array_equal(a, b) and sorted(a) == list(range(HIDDEN)) and not np.array_equal(a, unit_order(3))
    masks = [keep_mask(a, d) for d in SILENCE]
    assert masks[0].all() and not masks[-1].any()
    for lo, hi in zip(masks, masks[1:]):  # every unit off at a dose is also off at every higher dose
        assert ((hi == 1) <= (lo == 1)).all()
    assert [int((m == 0).sum()) for m in masks] == [n_off(d) for d in SILENCE] and n_off(0.5) == 1024


def _tiny(hidden=16):
    torch = pytest.importorskip("torch")
    ls = load("plato_lifespan_sketch")
    torch.manual_seed(0)
    model = ls.build("cpu", hidden=hidden, mixtures=3)
    model.eval()
    return torch, model


def test_damage_hooks_are_reversible_and_never_edit_weights():
    torch, model = _tiny()
    fg = load("plato_sketch_forget")
    before = {k: v.clone() for k, v in model.state_dict().items()}
    x = torch.randn(4, 1, 5)
    with torch.no_grad():
        y0, s0 = model(x)
        order = unit_order(1, hidden=16)
        for arm in ("silence", "readout"):
            with fg.Damage(model, arm, mask=torch.tensor(keep_mask(order, 0.0))):
                y, _ = model(x)
            assert torch.equal(y, y0)  # dose 0 changes nothing
            with fg.Damage(model, arm, mask=torch.tensor(keep_mask(order, 1.0))):
                y, (h, c) = model(x)
            assert torch.allclose(y, model.out.bias.expand_as(y))  # every unit off: only the head's bias is left
            if arm == "silence":
                assert torch.equal(h, torch.zeros_like(h))  # and nothing is carried to the next step
            else:
                assert torch.equal(h, s0[0])  # readout only: the memory is untouched
        eps = torch.randn(3, 4, 16)
        with fg.Damage(model, "noise", k=0.0, sd=torch.ones(16), eps=eps):
            y, _ = model(x)
        assert torch.equal(y, y0)
        with fg.Damage(model, "noise", k=1.0, sd=torch.ones(16), eps=eps) as dmg:
            y1, (h1, _) = model(x)
            y2, _ = model(x, (h1, s0[1]))
        assert dmg.t == 2 and torch.allclose(h1[0], s0[0][0] + eps[0])  # step t gets eps[t]
        y, _ = model(x)
    assert torch.equal(y, y0)  # hooks removed on exit
    assert len(model.lstm._forward_hooks) == 0 and len(model.out._forward_pre_hooks) == 0
    assert all(torch.equal(before[k], v) for k, v in model.state_dict().items())


def test_damage_hooks_while_sampling_with_fixed_noise():
    torch, model = _tiny()
    fg = load("plato_sketch_forget")
    seeds = load("plato_sketch_seeds")
    from metalesionlab.plato_sketch import make_noise

    noise = make_noise(1, 6, 200)
    intact = seeds.sample_fixed(model, noise, 1.0, 40.0, "cpu")
    with fg.Damage(model, "silence", mask=torch.tensor(keep_mask(unit_order(1, 16), 0.0))):
        same = seeds.sample_fixed(model, noise, 1.0, 40.0, "cpu")
    eps = torch.randn(200, 6, 16, generator=torch.Generator().manual_seed(1))
    with fg.Damage(model, "noise", k=2.0, sd=torch.ones(16), eps=eps):
        noisy = seeds.sample_fixed(model, noise, 1.0, 40.0, "cpu")
    again = seeds.sample_fixed(model, noise, 1.0, 40.0, "cpu")
    assert same == intact and again == intact and noisy != intact


def test_learning_path_interpolation_never_extrapolates():
    r = [0.2, 0.5, 0.5, 0.8]
    d = [0.5, 0.3, 0.32, 0.2]
    y = learn_interp(r, d, [0.2, 0.5, 0.65, 0.1, 0.9])
    assert np.allclose(y[:3], [0.5, 0.31, 0.255]) and np.isnan(y[3]) and np.isnan(y[4])
    mean, gaps = path_gap(r, d, [0.65, 0.95], [0.3, 0.1])
    assert np.isclose(mean, 0.045) and np.isnan(gaps[1])
    assert math.isnan(path_gap(r, d, [0.95], [0.1])[0])
    # a damaged point on the learning path has no gap; the nearest training step is found on both axes
    assert np.isclose(path_gap(r, d, [0.8], [0.2])[0], 0)
    assert nearest_step([0.2, 0.5, 0.8], [0.5, 0.3, 0.2], [0, 100, 1000], 0.48, 0.31) == 100


def test_half_forgotten_dose_uses_recognizability_only():
    doses = [0.0, 0.1, 0.2, 0.3]
    assert half_forgotten(doses, [0.9, 0.85, 0.5, 0.3], 0.9, 0.2, last=0.3) == 0.2   # first at or below 0.55
    assert half_forgotten(doses, [0.9, 0.85, 0.8, 0.7], 0.9, 0.2, last=0.3) == 0.3   # never: the last dose
    assert half_forgotten(doses, [0.9, float("nan"), 0.4, 0.3], 0.9, 0.2, last=0.3) == 0.2


def test_verdict_rules():
    assert gap_verdict([-0.01, 0.02], [-0.02, 0.01]) == "retraces"
    assert gap_verdict([0.01, 0.02], [0.005, 0.025]) == "retraces"  # a small real gap inside the margin still retraces
    assert gap_verdict([0.02, 0.09], [0.04, 0.08]) == "further"
    assert gap_verdict([-0.09, -0.02], [-0.08, -0.04]) == "closer"
    assert gap_verdict([-0.02, 0.09], [0.0, 0.08]) == "unclear"
    assert gap_verdict([float("nan"), 0.1], [0.0, 0.1]) == "unclear"
    assert sign_verdict([0.1, 0.2], [0.1, 0.3], "up", "down", "none") == "up"
    assert sign_verdict([-0.1, 0.2], [0.1, 0.3], "up", "down", "none") == "none"
    assert sign_verdict([-0.3, -0.2], [-0.3, -0.1], "up", "down", "none") == "down"


def test_kept_share_and_nearest_person():
    assert np.allclose(kept_share([0.5, 0.2, 0.35], 0.2, 0.5), [1, 0, 0.5])
    rng = np.random.default_rng(0)
    ref = rng.random((5, 8, 8))
    x = np.stack([ref[2], 2 * ref[3] + 1, rng.random((8, 8))])
    m = nearest_person(x, ref)
    assert np.allclose(m[:2], 1) and m[2] < 1  # a map matches itself, whatever its brightness and contrast


def test_ink_maps_keep_shape_coarse_and_lines_fine():
    from PIL import Image, ImageDraw

    from metalesionlab.plato_sketch_forget import COARSE, FINE, ink_maps

    img = Image.new("L", (256, 256), 255)
    ImageDraw.Draw(img).line([(40, 128), (216, 128)], fill=0, width=3)
    c, f = ink_maps(img)
    assert c.shape == (COARSE, COARSE) and f.shape == (FINE, FINE)
    assert 0 <= c.min() and f.max() <= 1 and f.max() > c.max()  # the fine map keeps the line sharper
    assert np.isclose(c.sum() * (256 / COARSE) ** 2, f.sum() * (256 / FINE) ** 2, rtol=0.05)  # the same ink at both scales


# ---------- the page, its data and its words ----------

PUBLIC = ROOT / "public_data" / "plato_sketch_forget.json"
STATIC = ROOT / "metalesionlab" / "web" / "static"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web

    return TestClient(web.app_for("plato"))


def test_forget_section_sits_right_below_learn(client):
    page = client.get("/plato/lifespan").text
    learn, forget, method = (page.index(f'id="{k}"') for k in ("learn", "forget", "method"))
    assert learn < forget < method
    sec = page[forget:page.index("</section>", forget)]
    assert page[learn:forget].count("</section>") == 1 and page[learn:forget].count("<section") == 1  # directly after #learn
    assert 'href="/static/css/plato_forget.css' in sec and "Then watch it forget" in sec  # (the site adds ?v=)
    assert page.count('src="/static/js/plato_forget.js') == 1
    assert page.index('src="/static/js/plato_lifespan.js') < page.index('src="/static/js/plato_forget.js')


@pytest.mark.skipif(not PUBLIC.exists(), reason="no forgetting results yet")
def test_forget_api_and_public_file_are_group_level(client):
    r = client.get("/api/plato/lifespan/forget")
    assert r.status_code == 200
    d = r.json()
    assert d["plan"] == "docs/plato_sketch_forget_plan.md" and d["test_seeds"] == TEST_SEEDS and d["step"] == STEP
    assert d["arms"] == {k: v for k, v in ARMS.items()} and d["display_doses"][0] == 0 and d["display_doses"][-1] == 1.0
    text = PUBLIC.read_text()
    assert '"strokes":[[' not in text and "cls" not in d and len(text) < 400_000  # numbers only: no drawings, no embeddings
    for tk in ("t1.0", "t0.4"):
        t = d["tests"][tk]["silence"]["test_seeds"]
        assert t["seeds"] == TEST_SEEDS and t["half_forgotten_dose"] in PRIMARY_DOSES
        for q in ("q1_distance_gap", "q2_primary", "q3_primary"):
            assert len(t[q]["t_ci95"]) == 2 and len(t[q]["boot_ci95"]) == 2 and t[q]["verdict"]
        assert len(d["forget"][tk]["silence_display"]["recog"]["mean"]) == len(d["display_doses"])
    # the damage is reversible: dose 0 draws exactly the learning run's last drawings, and so does the model after
    for seed, c in d["checks"].items():
        for tk in ("t1.0", "t0.4"):
            assert c["dose0_vs_learning"][tk]["identical_to_learning_run"] == c["dose0_vs_learning"][tk]["of"] == 200
            assert c["hooks_removed"][tk]["identical"] == 200
    a = d["animation"]
    assert a["seed"] == DISPLAY["seed"] and a["temp"] == DISPLAY["temp"] and len(a["recog"]) == len(a["doses"]) == 16
    assert len(a["learn_recog"]) == len(a["learn_steps"]) == len(MODELS["big"]["steps"])


def test_forget_api_reports_missing_data(client, monkeypatch, tmp_path):
    from metalesionlab.web import plato_lifespan_routes as routes

    monkeypatch.setattr(routes, "FORGET", tmp_path / "missing.json")
    assert client.get("/api/plato/lifespan/forget").status_code == 503


def test_forget_pictures_are_small_and_cut_to_the_sprite():
    sprite = STATIC / "img" / "plato_forget" / "forget_sprite.webp"
    if not sprite.exists():
        pytest.skip("no sprite yet")
    from PIL import Image

    from metalesionlab.plato_sketch_forget import DISPLAY_DOSES

    assert sprite.stat().st_size < 600 * 1024
    w, h = Image.open(sprite).size
    assert w == h == 4 * (4 * 180 + 3 * 8) and len(DISPLAY_DOSES) == 16  # 4 x 4 frames of 4 x 4 drawings
    thumbs = load("plato_hub_thumbs")
    assert thumbs.FORGET_DOSES == DISPLAY_DOSES and "damaged-forget" in thumbs.DAMAGED
    card = STATIC / "img" / "plato" / "hub" / "damaged-forget.webp"
    assert card.exists() and card.stat().st_size < 60_000


def test_damaged_hub_has_a_card_for_forgetting(client):
    from metalesionlab.web import damaged_routes

    card = [c for c in damaged_routes.CARDS if c["slug"] == "damaged-forget"]
    assert len(card) == 1 and card[0]["path"] == "/plato/lifespan#forget"
    assert 'href="/plato/lifespan#forget"' in client.get("/damaged").text


def js_strings(js: str) -> list[str]:
    """The string literals of a script (single or double quotes; comments skipped)."""
    out, i, n = [], 0, len(js)
    while i < n:
        c = js[i]
        if js.startswith("//", i):
            i = js.find("\n", i) if js.find("\n", i) >= 0 else n
        elif js.startswith("/*", i):
            i = js.index("*/", i) + 2
        elif c in "'\"":
            j, buf = i + 1, []
            while js[j] != c:
                if js[j] == "\\":
                    j += 1
                buf.append(js[j])
                j += 1
            out.append("".join(buf))
            i = j + 1
        else:
            i += 1
    return out


def test_forget_words_are_plain():
    """The section's visible strings (plato_forget.js and its paragraph) avoid unexplained jargon
    (docs/style_plain_language.md); "spread" appears only as "(we call this spread)"."""
    import re

    shown = " ".join(js_strings((STATIC / "js" / "plato_forget.js").read_text()))
    page = (ROOT / "metalesionlab" / "web" / "pages" / "plato_lifespan.html").read_text()
    sec = page[page.index('id="forget"'):page.index('id="method"')]
    shown += " " + re.sub(r"<[^>]+>", " ", sec)
    shown = shown.replace("(we call this spread)", "")
    for word in (r"\bLSTM\b", r"[Tt]emperature", r"[Cc]heckpoint", r"\bspread\b", r"\bCI\b", r"\bseed", r"\bdose", r"\bn\s*=",
                 r"\bintact\b", r"\bablat", r"\blesion", r"[Pp]re-registered", r"\bhidden units?\b"):
        assert not re.search(word, shown), word
    assert "a Meta AI that compares pictures (DINOv2)" in shown and "artificial neurons" in shown

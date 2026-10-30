"""Damage Meta's open AI: what does it forget first? (docs/plato_glimmer_lesion_plan.md)

The design (requests, damage types, nested random units), the description rubric, the retention statistics and the
verdict rule, the lesion hooks on a tiny stand-in for Glimmer, and the page (/plato/glimmer): its data, its first screen
(run under node on the real data), its plain words and its place in Damaged AI."""
import json
import re
import shutil
import subprocess

import numpy as np
import pytest
import torch

from metalesionlab import plato_glimmer_lesion as gl
from metalesionlab.lesions import LesionSpec, lesion
from metalesionlab.plato_scale import PROMPT

# ---------- the design ----------


def test_the_chair_request_is_the_scale_experiments_word_for_word():
    assert gl.BY_KEY["chair"].draw == PROMPT
    assert "10 past 11" in gl.BY_KEY["clock"].draw and "all the numbers" in gl.BY_KEY["clock"].draw
    assert [t.describe for t in gl.THINGS] == ["Describe a chair in one sentence.", "Describe a clock in one sentence.",
                                                "Describe God in one sentence."]
    assert gl.N == 12 and gl.TEMP == 1.0


def test_conditions_are_intact_plus_five_steps_per_type():
    conds = gl.conditions()
    assert conds[0] == "intact" and len(conds) == 1 + 5 * len(gl.DAMAGE) and len(set(conds)) == len(conds)
    for d in gl.DAMAGE:
        assert len(d.doses) == 5 and list(d.doses) == sorted(d.doses) and 0 < d.doses[0] and d.doses[-1] <= 1
    assert gl.parse_condition("early@0.4") == ("early", 0.4) and gl.parse_condition("intact") == ("intact", 0.0)
    with pytest.raises(ValueError):
        gl.parse_condition("middle@0.4")


def test_early_and_late_are_the_first_and_last_thirds():
    assert gl.EARLY == list(range(17)) and gl.LATE == list(range(35, 52))
    assert not set(gl.EARLY) & set(gl.LATE)


def test_damage_is_nested_and_shared_between_types():
    light, heavy = gl.damage_units("all", 0.1), gl.damage_units("all", 0.3)
    for layer in range(gl.N_LAYERS):
        assert set(light[layer]) <= set(heavy[layer])
        assert len(heavy[layer]) == round(0.3 * gl.N_NEURONS)
    early = gl.damage_units("early", 0.3)
    assert set(early) == set(gl.EARLY) and all(early[k] == heavy[k] for k in gl.EARLY)
    heads = gl.damage_units("heads", 0.25)
    assert all(len(v) == 8 and max(v) < gl.N_HEADS for v in heads.values())
    assert gl.units_off("late", 1.0)["share_of_model"] == pytest.approx(17 / 52)


def test_spec_round_trips_and_switches_off_exactly_those_neurons():
    d = gl.lesion_spec_dict("early", 0.5, n_neurons=8, n_heads=2)
    spec = LesionSpec.from_dict(d)
    assert spec.method == "zero" and set(spec.mlp) == set(gl.EARLY) and all(len(v) == 4 for v in spec.mlp.values())
    assert spec.recipe["type"] == "early"

    m = TinyGlimmer()
    units = gl.damage_units("all", 0.5, n_neurons=8, n_heads=2)
    spec = LesionSpec(method="zero", mlp={0: units[0]})
    x = torch.ones(1, 8)
    down = m.model.language_model.layers[0].mlp.down_proj
    with lesion(m, spec):
        seen = capture(down, x)
    off = torch.zeros(8, dtype=torch.bool)
    off[units[0]] = True
    assert torch.all(seen[0, off] == 0) and torch.all(seen[0, ~off] == 1)
    assert torch.all(capture(down, x) == 1)  # undone on exit


class TinyGlimmer(torch.nn.Module):
    """Only the module paths and config fields the lesion code reads: 52 layers of 8 neurons and 2 heads of 4."""

    def __init__(self):
        from types import SimpleNamespace

        nn = torch.nn
        super().__init__()

        def layer():
            m = nn.Module()
            m.mlp, m.self_attn = nn.Module(), nn.Module()
            m.mlp.down_proj, m.self_attn.o_proj = nn.Linear(8, 3, bias=False), nn.Linear(8, 3, bias=False)
            return m
        self.model = nn.Module()
        self.model.language_model = nn.Module()
        self.model.language_model.layers = nn.ModuleList([layer() for _ in range(gl.N_LAYERS)])
        self.model.vision_adapter = nn.Module()
        self.model.vision_adapter.fc1 = nn.Linear(4, 3)
        self.model.vision_projection = nn.Linear(3, 5, bias=False)
        cfg = SimpleNamespace(num_attention_heads=2, head_dim=4)
        self.config = SimpleNamespace(get_text_config=lambda: cfg)

    @property
    def device(self):
        return torch.device("cpu")


def capture(module, x):
    """What `module` receives when called on x."""
    seen = {}
    h = module.register_forward_pre_hook(lambda _m, a: seen.setdefault("x", a[0]))
    try:
        module(x)
    finally:
        h.remove()
    return seen["x"]


# ---------- the rubric ----------

def zipf(word):  # no wordfreq lookups in the tests: every word here is English
    return 5.0


def score(text, key, finished=True):
    return gl.score_description(text, key, finished, zipf=zipf)


def test_rubric_counts_a_plain_correct_description():
    s = score("A chair is a piece of furniture with a seat, a back and four legs, made for sitting.", "chair")
    assert s["correct"] and s["fluent"] and {"seat", "legs", "furniture"} <= set(s["attributes"])
    assert score("A clock is a device that measures and displays the time.", "clock")["correct"]
    assert score("God is the eternal, all-powerful creator of the universe.", "god")["correct"]


def test_rubric_needs_the_name_and_a_typical_property():
    assert not score("A chair is a chair.", "chair")["correct"]               # names it, says nothing
    assert not score("It is wooden and has four legs.", "chair")["correct"]   # never names it
    assert not score("No.", "god")["correct"]
    assert score("The Almighty is the creator of heaven and earth.", "god")["names"]


def test_rubric_rejects_rambles_and_code_that_mention_the_thing():
    ramble = ("In a clock, you have the current time etc. " * 8).strip()
    assert score(ramble, "clock")["names"] and not score(ramble, "clock")["correct"]
    assert not score("A clock shows the time", "clock", finished=False)["correct"]  # ran out of tokens
    assert not score("<svg> a clock shows the time </svg>", "clock")["correct"]


def test_fluency_checks():
    ok = gl.fluency("A chair is something you sit on.", zipf=zipf)
    assert ok["fluent"]
    assert not gl.fluency("a chair is something you sit on.", zipf=zipf)["fluent"]       # no capital
    assert not gl.fluency("A chair is something you sit on", zipf=zipf)["fluent"]        # no full stop
    assert not gl.fluency("A chair chair chair is here.", zipf=zipf)["fluent"]           # a loop
    assert not gl.fluency("Ok.", zipf=zipf)["fluent"]                                    # too short
    assert not gl.fluency("Xq zzv brr kkt plo.", zipf=lambda w: 0.0)["fluent"]          # not English words


def test_clock_numbers():
    svg = "<svg>" + "".join(f'<text x="1" y="2">{n}</text>' for n in range(1, 13)) + "</svg>"
    assert gl.clock_numbers(svg) == {"numbers": list(range(1, 13)), "all_12": True}
    assert gl.clock_numbers('<svg><text><tspan>12</tspan></text><text>3</text></svg>')["numbers"] == [3, 12]
    assert gl.clock_numbers(None)["all_12"] is False


# ---------- the statistics and the verdict rule ----------

def outcomes(rates, n=12):
    """(conditions, things, n) of 0/1 from rates (conditions, things)."""
    r = np.asarray(rates, float)
    return (np.arange(n)[None, None, :] < np.round(r[..., None] * n)).astype(float)


def test_retention_is_each_things_share_of_its_undamaged_rate():
    x = outcomes([[1.0, 0.5], [0.5, 0.25], [0.0, 0.5]])
    assert gl.retention_curves(x) == pytest.approx([0.5, 0.5])  # (0.5 + 0.5) / 2, then (0 + 1) / 2


def test_first_below_half_and_order():
    assert gl.first_below_half([0.9, 0.6, 0.4, 0.1], 1.0) == 3
    assert gl.first_below_half([0.9, 0.8], 1.0) is None and gl.first_below_half([0.1], 0.0) is None
    assert gl.order_verdict(2, 4) == "picture first" and gl.order_verdict(4, 2) == "word first"
    assert gl.order_verdict(3, 3) == "together" and gl.order_verdict(None, None) == "neither"
    assert gl.order_verdict(2, None) == "picture first" and gl.order_verdict(None, 5) == "word first"


def test_gap_verdict_and_bootstrap():
    steps = [1.0, 0.75, 0.5, 0.25, 0.0, 0.0]
    pic = outcomes([[s, s] for s in steps])
    word = outcomes([[1.0, 1.0]] * 6)
    b = gl.boot_gap(pic, word, reps=500)
    assert b["gap"] == pytest.approx(1 - np.mean(steps[1:])) and b["ci95"][0] > 0
    assert gl.gap_verdict(b["ci95"]) == "picture first"
    assert gl.gap_verdict(gl.boot_gap(word, pic, reps=500)["ci95"]) == "word first"
    same = gl.boot_gap(pic, pic, reps=500)
    assert same["gap"] == 0 and gl.gap_verdict(same["ci95"]) == "together"
    assert gl.gap_verdict([float("nan")] * 2) == "not testable"
    lo, hi = gl.boot_gap_difference(b, same)
    assert lo > 0


# ---------- the page ----------

from fastapi.testclient import TestClient  # noqa: E402

from metalesionlab.web import app as web  # noqa: E402
from metalesionlab.web import damaged_routes, site  # noqa: E402
from metalesionlab.web import plato_glimmer_routes as R  # noqa: E402

DATA = R.DATA
NODE = shutil.which("node")
needs_data = pytest.mark.skipif(not DATA.exists(), reason="web/data/plato_glimmer.json not written yet")


@pytest.fixture(scope="module")
def client():
    R._cache.clear()
    return TestClient(web.app_for("plato"))


def test_registered_in_damaged_ai_on_the_plato_site_only():
    assert "plato_glimmer_routes" in web.SITE_ROUTERS["plato"] and "plato_glimmer_routes" not in web.SITE_ROUTERS["lingua"]
    assert "/plato/glimmer" in site.DAMAGED_PAGES and site.DAMAGED_TITLES["/plato/glimmer"]
    assert not any(s["path"] == "/plato/glimmer" for s in site.SERIES)  # Damaged AI, not the Plato series
    assert any(c["path"].startswith("/plato/glimmer") for c in damaged_routes.CARDS)


def test_swear_words_are_masked_the_comic_strip_way():
    assert gl.grawlix("What a chair is? Fuck you 😂") == "What a chair is? F&$# you 😂"
    assert gl.grawlix("Holy shit, you want the infinite") == "Holy s&$#, you want the infinite"
    assert gl.grawlix("motherfucking clocks") == "m&$#@!%&$#@!%" + " clocks"
    for fine in ("A chair has a seat, a back and legs.", "Dickens, class, assessment, Scunthorpe, cocktail", "", None):
        assert gl.grawlix(fine) == (fine or "")


@needs_data
def test_the_public_file_shows_no_swear_words():
    said = json.dumps(json.loads(DATA.read_text())["sentences"], ensure_ascii=False)
    assert not gl.SWEARS.search(said)
    assert "F&$# you" in said and "Holy s&$#" in said  # still there, masked, so a reader can tell what was said


def test_api_reports_missing_data(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "DATA", tmp_path / "missing.json")
    R._cache.clear()
    assert TestClient(web.app_for("plato")).get("/api/plato/glimmer").status_code == 503
    R._cache.clear()


@needs_data
def test_page_api_and_sprites(client):
    r = client.get("/plato/glimmer")
    assert r.status_code == 200 and "{{BRAND}}" not in r.text
    assert 'id="trio"' in r.text and 'id="charts"' in r.text and 'id="grid"' in r.text
    d = client.get("/api/plato/glimmer").json()
    assert gl.validate_public(d) == []
    assert [t["key"] for t in d["things"]] == [t.key for t in gl.THINGS]
    assert [t["key"] for t in d["damage"]] == [t.key for t in gl.DAMAGE]
    for t in d["damage"]:
        assert [s["cond"] for s in t["steps"]] == ["intact"] + [gl.condition_name(t["key"], x) for x in gl.DAMAGE_BY_KEY[t["key"]].doses]
        for th in d["things"]:
            assert client.get(d["sprites"]["grid"].replace("{type}", t["key"]).replace("{thing}", th["key"])).status_code == 200
        assert client.get(d["sprites"]["featured"].replace("{type}", t["key"])).status_code == 200
    for cond, things in d["conditions"].items():
        for th, row in things.items():
            assert row["n"] == gl.N and len(d["sentences"][cond][th]) == gl.N
            assert row["named"] <= row["drew"] and row["correct"] <= row["names"]
            for m in ("drew", "named", "correct", "fluent"):
                assert d["marks"][cond][th][m].count("1") == row[m]
    imgs = list((web.HERE / "static" / "img" / "plato_glimmer").glob("*"))
    assert all(f.suffix == ".webp" for f in imgs) and sum(f.stat().st_size for f in imgs) < 2.5 * 1024 * 1024


@needs_data
def test_verdicts_follow_the_rule():
    d = json.loads(DATA.read_text())
    for k, v in d["verdict"]["types"].items():
        if "gap" not in v:
            continue
        assert v["verdict"] == gl.gap_verdict(v["ci95"]), k
        assert v["order"] == gl.order_verdict(v["step_picture"], v["step_word"]), k
        assert v["step_picture"] == gl.first_below_half(v["curves"]["named"][1:], 1.0)
        assert v["curves"]["named"][0] == 1 and v["curves"]["correct"][0] == 1
        assert v["ci95"][0] <= v["gap"] <= v["ci95"][1]


def main_text(html: str) -> str:
    main = html[html.index("<main"):html.index('<section class="gl-sec gl-method"')]  # the method may name the terms
    main = re.sub(r"<script.*?</script>", "", main, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", main))


JARGON = [r"\bSDXL\b", r"\bSVG\b", r"\bMLP\b", r"\bCI\b", r"[Pp]re-registered", r"\bintact\b", r"\bn\s*=", r"\blayers?\b",
          r"\bspread\b", r"\bseed\b", r"\bprompt\b", r"\bdose\b", r"\btemperature\b", r"\blesion", r"\bablat"]


def run_headline():
    """GlimmerPage.headline on the real data, under node."""
    js = web.HERE / "static" / "js"
    code = ("const FL=require(%r);global.FirstLook=FL;const G=require(%r);const d=JSON.parse(require('fs').readFileSync(%r));"
            "const h=G.headline(d);h.html=h.stats.map(FL.figure).join('');console.log(JSON.stringify(h));"
            % (str(js / "plato_firstlook.js"), str(js / "plato_glimmer.js"), str(DATA)))
    run = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@needs_data
@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_first_screen_numbers_come_from_the_data():
    d, h = json.loads(DATA.read_text()), run_headline()
    v = d["verdict"]["types"]["all"]
    assert len(h["stats"]) == 3
    first = h["stats"][0]["o"]
    k = min(v["step_picture"] or 99, v["step_word"] or 99)
    k = k if k != 99 else len(d["damage"][0]["steps"]) - 1
    rows = {r["label"]: r["v"] for r in first["rows"]}
    assert rows["drawing"] == pytest.approx(min(1, v["curves"]["named"][k])) and rows["describing"] == pytest.approx(min(1, v["curves"]["correct"][k]))
    assert ("predicted" in h["stats"][0]["verdict"]["text"]) and (h["stats"][0]["verdict"]["tone"] == ("yes" if v["verdict"] == "picture first" else "no"))
    last = d["damage"][0]["steps"][-1]["cond"]
    fl = sum(d["conditions"][last][t]["fluent"] for t in ("chair", "clock", "god"))
    assert h["stats"][2]["o"]["rows"][0]["v"] == pytest.approx(fl / 36)


@needs_data
@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_the_page_speaks_plain_words(client):
    """docs/style_plain_language.md: no unexplained jargon in what a visitor reads above the method notes."""
    html = client.get("/plato/glimmer").text
    h = run_headline()
    shown = main_text(html) + " " + h["answer"] + " " + h["note"] + " " + re.sub(r"<[^>]+>", " ", h["html"])
    for word in JARGON:
        assert not re.search(word, shown), word
    assert "Meta’s open AI model, Muse Glimmer (one anyone can download and look inside)" in shown
    assert "switched off" in shown and "artificial neurons" in shown


def test_no_god_picture_on_the_hub_card():
    card = next(c for c in damaged_routes.CARDS if c["path"].startswith("/plato/glimmer"))
    assert "god" not in card["slug"].lower()
    pic = web.HERE / "static" / "img" / "plato" / "hub" / f"{card['slug']}.webp"
    assert pic.is_file() and pic.stat().st_size < 60_000

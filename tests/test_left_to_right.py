"""Time, training, age, size and damage run left to right, from least to most, on a horizontal axis (site-wide rule).

Pins the cheap parts: the data orders behind the progressions, the stylesheets (no right-to-left rows; narrow screens
scroll sideways instead of wrapping a progression), and the hero rows' step control (always the first and last step)."""
import json
import re
import shutil
import subprocess

import pytest

from metalesionlab.web import app as web

HERE = web.HERE
CSS = {p.name: p.read_text() for p in (HERE / "static" / "css").glob("*.css")}


def load(name):
    return json.loads((HERE / "data" / name).read_text())


def test_the_crowd_averages_and_the_age_groups_run_from_fewest_and_youngest():
    clock = load("plato_clock.json")
    ns = [f["n"] for f in clock["people"]["form"]]
    assert ns == sorted(ns) and ns[0] == 20 and ns[-1] == 315
    starts = [int(re.match(r"\d+", d["age_range_years"]).group(0)) for d in clock["people"]["decades"]]
    assert starts == sorted(starts) and starts[0] == 20
    assert clock["persona"]["ages"] == sorted(clock["persona"]["ages"])


def test_damage_doses_rise_left_to_right_in_every_slider():
    for name, get in (("plato_damage.json", lambda d: d["slider"]["levels"]), ("plato_ideas.json", lambda d: d["damage"]["levels"])):
        for fam, levels in get(load(name)).items():
            doses = [float(l["cond"].partition("@")[2] or 0) for l in levels]
            assert doses == sorted(doses) and doses[0] == 0, (name, fam)
    for row in load("plato_clock.json")["damage"]:
        assert len(row["levels"]) >= 4


def test_no_stylesheet_runs_a_row_right_to_left():
    for name, css in CSS.items():
        assert "row-reverse" not in css and "direction: rtl" not in css and "direction:rtl" not in css, name


def test_progressions_scroll_sideways_on_narrow_screens_instead_of_wrapping():
    assert "pk-scrollx" in CSS["plato_clock.css"] and "min-width: 880px" in CSS["plato_clock.css"]  # age groups
    assert "overflow-x: auto" in CSS["plato_firstscreen.css"].split("max-width: 560px")[1].split(".tp-answer")[0]  # telephone copies
    assert not re.search(r"\.pk-decades \{ grid-template-columns: repeat\((2|3),", CSS["plato_clock.css"])


def test_model_sizes_are_sorted_smallest_first():
    js = (HERE / "static" / "js" / "plato_scale.js").read_text()
    assert "a.params_b - b.params_b" in js and "a.size - b.size" in js


NODE = shutil.which("node")


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_the_steps_control_always_keeps_the_first_and_last_step():
    src = (HERE / "static" / "js" / "hero-carousel.js").read_text()
    script = ("global.window={matchMedia:()=>null};global.document={readyState:'complete',addEventListener(){},querySelectorAll:()=>[]};"
              + src + ";const out={};for(const n of [4,6,10,12]){for(const k of [5,7,10]){out[n+'_'+k]=window.HeroCarousel.pick(n,k);}}"
              "console.log(JSON.stringify(out));")
    got = json.loads(subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True).stdout)
    for key, picks in got.items():
        n, k = map(int, key.split("_"))
        assert picks[0] == 0 and picks[-1] == n - 1, key
        assert picks == sorted(set(picks)) and len(picks) == min(n, k), key
    assert got["10_10"] == list(range(10)) and got["10_5"] == [0, 2, 5, 7, 9] and got["10_7"] == [0, 2, 3, 5, 6, 8, 9]


def test_every_hero_row_has_ten_steps_undamaged_first():
    """Stable Diffusion XL's rows have ten steps (undamaged + 9 doses). The one documented exception: Muse Glimmer's rows on
    /damaged have as many steps as that experiment has (undamaged + 5 doses of switched-off neurons = 6); no step is invented."""
    glimmer_steps = len(load("plato_glimmer.json")["damage"][0]["steps"])
    assert glimmer_steps == 6
    for page in ("damaged.html", "plato_damage.html"):
        text = (HERE / "pages" / page).read_text()
        carousels = re.findall(r'data-hero-carousel[^>]*>\s*<script type="application/json">(.*?)</script>', text, re.S)
        assert carousels and (page != "damaged.html" or len(carousels) == 2), page
        for raw in carousels:
            for s in json.loads(raw)["slides"]:
                want = glimmer_steps if s["caption"].startswith("Muse Glimmer") else 10
                assert len(s["images"]) == want, (page, s["caption"])
                assert s["images"][0]["label"] == "undamaged"
                assert all((HERE / "static" / im["src"][len("/static/"):]).is_file() for im in s["images"])

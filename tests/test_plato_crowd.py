"""Ask it to be a crowd (docs/plato_crowd_plan.md): the age-persona prompt is the house prompt word for word after
the prefix, the ages are fixed, and the paired statistics behave."""
import numpy as np
import pytest

from metalesionlab import plato, plato_crowd as pc, plato_ideas


def test_ages_are_sixteen_adults_evenly_spread_from_20_to_80():
    assert pc.AGES == (20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80)
    assert len(set(np.diff(pc.AGES))) == 1


def test_concepts_are_the_pad_things_and_god():
    assert pc.THINGS == ("chair", "umbrella", "bicycle", "house", "cat", "tree", "face", "sailboat", "cup", "book")
    assert set(pc.DRAW_ORDER) == set(pc.KEYS) and pc.DRAW_ORDER[:2] == ("chair", "god")
    assert pc.IDEA in plato_ideas.BY_KEY


@pytest.mark.parametrize("key", ["chair", "umbrella", "sailboat", "god"])
def test_prompt_is_the_house_prompt_after_an_age_only_prefix(key):
    phrase = plato_ideas.BY_KEY[key].phrase if key == "god" else plato.BY_KEY[key].phrase
    house = plato.STYLES["doodle"].format(phrase=phrase)
    p = pc.prompt_for(key, 36)
    assert p == "Drawn by a 36-year-old: " + house[0].lower() + house[1:]
    assert p.endswith("black marker on plain white, like a 20-second drawing, no text, no shading.")


def test_examples_from_the_plan():
    assert pc.prompt_for("chair", 34).startswith("Drawn by a 34-year-old: a quick simple doodle sketch of a chair, ")
    assert pc.prompt_for("god", 80).startswith("Drawn by an 80-year-old: a quick simple doodle sketch of God, ")
    assert pc.prompt_for("umbrella", 20).startswith("Drawn by a 20-year-old: a quick simple doodle sketch of an umbrella, ")


def test_no_other_traits_in_the_prefix():
    for age in pc.AGES:
        prefix = pc.prompt_for("chair", age).split(":")[0]
        assert prefix in (f"Drawn by a {age}-year-old", f"Drawn by an {age}-year-old")


def test_file_names_carry_the_age():
    names = [pc.file_name(i, a) for i, a in enumerate(pc.AGES)]
    assert names[0] == "p00_age20.png" and names[-1] == "p15_age80.png"
    assert [pc.age_of(n) for n in names] == list(pc.AGES)
    # the house loader sorts by (len(stem), stem): the same order as the ages
    assert sorted(names, key=lambda n: (len(n), n)) == names


def test_paired_bootstrap_is_centred_on_the_paired_difference():
    rng = np.random.default_rng(0)
    a = [np.full(50, 0.3), np.full(50, 0.5)]
    b = [np.full(50, 0.1), np.full(50, 0.2)]
    boots = pc.paired_mean_diff_boot(a, b, reps=500, rng=rng)
    assert boots.min() >= 0.2 - 1e-9 and boots.max() <= 0.3 + 1e-9
    assert pc.signflip_p([0.2, 0.3, 0.1, 0.25], reps=2000, rng=rng) < 0.1
    assert pc.signflip_p([-0.2, -0.3, 0.1], reps=2000, rng=rng) > 0.5


def test_age_trend_finds_a_planted_trend_and_not_noise():
    rng = np.random.default_rng(1)
    ages = {k: np.array(pc.AGES, float) for k in "abcde"}
    planted = {k: np.array(pc.AGES, float) / 100 + rng.normal(0, 0.01, 16) for k in ages}
    noise = {k: rng.normal(0, 1, 16) for k in ages}
    t = pc.age_trend(planted, ages, reps=500, rng=rng)
    assert t["mean_rho"] > 0.8 and t["p_perm_two_sided"] < 0.01
    assert pc.age_trend(noise, ages, reps=500, rng=rng)["p_perm_two_sided"] > 0.01


def test_centroid_distances():
    x = np.array([[1.0, 0.0], [0.0, 1.0]])
    c = pc.centroid(x)
    assert np.allclose(pc.distance_to(x, c), 1 - np.sqrt(0.5))
    assert np.allclose(pc.loo_distances(x), [1.0, 1.0])


# --- the shipped data and /plato's "Ask it to be a crowd" section -------------------------------------

import json  # noqa: E402
import re  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from metalesionlab.web import app as web  # noqa: E402

DATA = web.HERE / "data" / "plato_crowd.json"
STATIC = web.HERE / "static"


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


@pytest.fixture(scope="module")
def data():
    return json.loads(DATA.read_text())


def crowd_section(client) -> str:
    page = client.get("/plato").text
    start = page.index('<section class="pc-sec pc-crowd" id="crowd"')
    return page[start:page.index("</section>", start)]


def test_data_matches_the_plan(data):
    assert data["ages"] == list(pc.AGES) and data["prompt_example"] == pc.prompt_for("chair", 34)
    assert [t["key"] for t in data["things"]] == list(pc.THINGS)
    assert data["verdict"] in ("default_not_limit", "some_variety", "no_change")
    assert DATA.stat().st_size < 30_000
    for t in data["things"]:
        assert t["persona_ci95"][0] <= t["persona"] <= t["persona_ci95"][1]
        assert t["reaches_people"] == (t["persona"] >= t["people"])
    assert data["h2"]["n_reach"] == sum(t["reaches_people"] for t in data["things"])


def test_god_result_is_in_the_data_for_the_ideas_page(data):
    god = data["god"]
    assert god["n_persona"] == 16 and god["default_by_eye"]["bearded_man"] == 16
    eye = god["persona_by_eye"]
    assert eye["n"] == 16 and 0 <= eye["bearded_man_with_halo"] <= eye["bearded_man"] <= 16
    assert set(eye["by_age"]) == {str(a) for a in pc.AGES}
    assert god["sentence"] and "people" not in god["sentence"]  # AI only: no people's drawings of God


def test_sprites_are_small_house_sprites_of_muse_only(data):
    for key, s in data["sprites"].items():
        f = STATIC / s["src"][len("/static/"):]
        assert f.is_file() and f.stat().st_size < 60_000 and s["src"].endswith(f"{key}_crowd_muse.webp")
        assert (s["cell"], s["cols"], s["n"]) == (112, 8, 16) and s["ages"] == list(pc.AGES)
        assert (STATIC / s["default"][len("/static/"):]).is_file()


def test_plato_shows_two_rows_of_sixteen_chairs(client, data):
    sec = crowd_section(client)
    assert sec.count('data-row="default"') == 1 and sec.count('data-row="persona"') == 1
    assert sec.count("--c:") == 32
    ages = re.findall(r"<small>(\d+)</small>", sec)
    assert ages == [str(a) for a in pc.AGES]


def test_crowd_numbers_match_the_data(client, data):
    sec = crowd_section(client)
    chair = data["things"][0]
    assert f'data-values="{chair["default"]:.2f},{chair["persona"]:.2f},{chair["people"]:.2f}"' in sec
    h1 = data["h1"]
    assert f'data-values="{h1["mean_default"]:.2f},{h1["mean_persona"]:.2f},{h1["mean_people"]:.2f}"' in sec
    assert f'data-k="{data["h2"]["n_reach"]}" data-n="{h1["n_things"]}"' in sec
    assert f'data-value="×{chair["persona_vs_default"]:.1f}"' in sec
    assert f'data-value="×{h1["median_ratio_vs_default"]:.1f}"' in sec
    lo, hi = chair["persona_vs_default_ci95"]
    assert f"95% CI {lo:.2f} to {hi:.2f}" in sec
    assert data["answer"].replace("’", "&rsquo;") in sec or data["answer"] in sec
    assert len(re.findall(r'data-sv="(dots|spread|layers|bars)"', sec)) == 3


def test_crowd_section_sits_after_the_hub_and_before_the_method(client):
    page = client.get("/plato").text
    assert page.index('id="experiments"') < page.index('id="crowd"') < page.index('id="method"')
    assert 'href="#crowd"' in page


def test_landing_and_draw_stay_blind_to_the_persona_drawings(client):
    for path in ("/", "/draw"):
        assert "_crowd_muse" not in client.get(path).text, path
    assert "_crowd_muse" not in (STATIC / "js" / "draw.js").read_text()

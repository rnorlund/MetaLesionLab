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

import numpy as np
import pytest

from metalesionlab.plato_damage import (ALL_PROMPTS, BY_KEY, CLOCK_PROMPTS, CONCEPT_KINDS, KIND_PROMPTS,
                                        boot_mean_ci, centroid, condition_name, cos_dist, drift_measures,
                                        family_spec, kind_outcome, matched_doses, outcome_shares,
                                        parse_clock_json, parse_condition, score_clock, seed_for,
                                        target_positions)
from metalesionlab.sdxl_lesions import DamageSpec, matched_random, random_units, top_units


def test_prompts_cover_kinds_plain_and_clocks_with_distinct_seeds():
    assert BY_KEY["chair__plain"].phrase == "a chair" and BY_KEY["chair__plain"].is_plain
    assert BY_KEY["chair__rocking_chair"].kind == "a rocking chair"
    assert "a rocking chair" in BY_KEY["chair__rocking_chair"].prompt and "doodle" in BY_KEY["chair__plain"].prompt
    assert len([p for p in KIND_PROMPTS if p.concept == "chair"]) == 1 + len(CONCEPT_KINDS["chair"][1]) == 9
    assert all(p.phrase.startswith("a simple clock face showing") for p in CLOCK_PROMPTS)
    seeds = {seed_for(p, i) for p in ALL_PROMPTS for i in range(50)}
    assert len(seeds) == 50 * len(ALL_PROMPTS)  # no two prompts share a starting noise
    assert len({p.key for p in ALL_PROMPTS}) == len(ALL_PROMPTS)


def test_family_specs_and_condition_names_round_trip():
    d = family_spec("text-zero", 0.1)
    assert d["site"] == "text" and d["method"] == "zero" and d["fraction"] == 0.1
    n = family_spec("unet-noise", 0.5)
    assert n["fraction"] == 1.0 and n["noise_scale"] == 0.5
    assert parse_condition(condition_name("unet-zero", 0.05)) == ("unet-zero", 0.05)
    assert parse_condition("intact") == ("intact", 0.0)
    spec = DamageSpec.from_dict(d)
    assert DamageSpec.from_dict(spec.to_dict()).to_dict() == spec.to_dict()
    assert DamageSpec(fraction=0.0).is_intact and not spec.is_intact
    with pytest.raises(ValueError):
        DamageSpec(site="vae")


def test_random_units_are_nested_across_doses():
    small, big = random_units([100, 50], 0.1, seed=3), random_units([100, 50], 0.3, seed=3)
    assert [len(x) for x in small] == [10, 5] and [len(x) for x in big] == [30, 15]
    assert all(set(a) <= set(b) for a, b in zip(small, big))  # cumulative damage
    assert all(len(set(x)) == len(x) for x in big)


def test_top_units_and_matched_random_control():
    scores = {"a": np.array([5.0, -1, 3, 0]), "b": np.array([4.0, 2, -3, 1])}
    top = top_units(scores, 0.5)  # 4 of 8 units: 5, 4, 3, 2
    assert top == {"a": [0, 2], "b": [0, 1]}
    ctrl = matched_random(top, {"a": 4, "b": 4}, seed=0)
    assert {k: len(v) for k, v in ctrl.items()} == {"a": 2, "b": 2}
    assert not set(ctrl["a"]) & set(top["a"]) and not set(ctrl["b"]) & set(top["b"])


def test_drift_is_positive_when_a_picture_moves_to_the_prototype():
    rng = np.random.default_rng(0)
    proto_dir, kind_dir = np.array([1.0, 0, 0, 0]), np.array([0, 1.0, 0, 0])
    plain = proto_dir + 0.05 * rng.normal(size=(6, 4))
    kind = kind_dir + 0.05 * rng.normal(size=(4, 4))
    intact = drift_measures(kind, kind, kind, plain)
    assert np.all(intact["d_intact"] < 1e-9) and np.all(intact["drift"] < 0)
    assert np.all(np.abs(intact["tau"]) < 0.2)
    moved = plain[:4] + 0.01  # damage turned every rocking chair into the plain chair
    m = drift_measures(moved, kind, kind, plain)
    assert np.all(m["drift"] > 0) and np.all(m["tau"] > 0.8) and np.all(m["d_intact"] > 0.5)
    other = [np.array([[0, 0, 1.0, 0]])]
    assert "drift_other" in drift_measures(moved, kind, kind, plain, others=other)


def test_centroid_leave_one_out_and_cos_dist():
    x = np.array([[1.0, 0], [0, 1.0], [0, 2.0]])
    assert np.allclose(centroid(x, leave_out=0), [0, 1])
    assert np.isclose(cos_dist(np.array([[1.0, 0]]), np.array([0, 1.0]))[0], 1.0)


def test_bootstrap_ci_brackets_the_mean_and_respects_groups():
    x = np.r_[np.zeros(10), np.ones(10)]
    r = boot_mean_ci(x, reps=500)
    assert r["ci95"][0] < 0.5 < r["ci95"][1] and r["n"] == 20
    g = boot_mean_ci(x, reps=500, groups=np.repeat([0, 1], 10))  # two clusters: very wide
    assert g["ci95"][0] == 0.0 and g["ci95"][1] == 1.0
    assert np.isnan(boot_mean_ci(np.array([np.nan]))["mean"])


def test_matched_doses_interpolates_each_severity_curve():
    curves = {"text": {0.0: 0.0, 0.1: 0.2, 0.2: 0.4}, "unet": {0.0: 0.0, 0.05: 0.4}}
    out = matched_doses(curves, [0.2, 0.3])
    assert np.allclose(out["text"], [0.1, 0.15]) and np.allclose(out["unet"], [0.025, 0.0375])


def test_kind_outcomes():
    n = 8  # 8 kinds, then plain (8), then can't tell (9)
    assert kind_outcome(3, 3, n) == "correct" and kind_outcome(2, 3, n) == "other_kind"
    assert kind_outcome(8, 3, n) == "plain" and kind_outcome(9, 3, n) == "cant_tell"
    assert kind_outcome(1, None, n) == "specific" and kind_outcome(8, None, n) == "plain"
    s = outcome_shares(["correct", "plain", "plain", "cant_tell"])
    assert s["correct"] == 0.25 and s["plain"] == 0.5 and np.isclose(s["plain_share_of_errors"], 2 / 3)


def test_clock_rubric_parsing_and_scoring():
    assert target_positions("3:00") == (3, 12) and target_positions("8:45") == (9, 9)
    assert target_positions("10:10") == (10, 2) and target_positions("1:55") == (2, 11)
    r = parse_clock_json('Sure: {"is_clock": true, "contour": true, "numbers_count": 12, "numbers_in_order": true, '
                         '"extra_or_wrong_numbers": false, "hands": 2, "hour_hand_points_to": 10, '
                         '"minute_hand_points_to": 2, "time_read": "10:10"}')
    s = score_clock(r, "3:00")
    assert s["numbers_ok"] and s["two_hands"] and s["shows_1010"] and not s["time_ok"] and s["total"] == 3
    assert score_clock(r, "10:10")["time_ok"] and score_clock(r, "10:10")["total"] == 5
    assert parse_clock_json("no json here") is None and score_clock(None, "3:00")["total"] is None
    blank = score_clock(parse_clock_json('{"is_clock": false, "hands": "none"}'), "6:30")
    assert blank["total"] == 0 and not blank["two_hands"]


def test_naming_answers_are_cleaned_and_coded():
    from metalesionlab.plato_damage import clean_name, code_name

    assert clean_name("The object in this picture is a throne.") == "throne"
    assert clean_name("Rocking chair") == "rocking chair"
    assert code_name("rockingchair", "chair", "a rocking chair") == "specific"
    assert code_name("Wheelchair", "chair", "a wheelchair") == "specific"
    assert code_name("The object in this picture is a chair.", "chair", "a throne") == "basic"
    assert code_name("The object in this picture is", "chair", "a throne") == "empty"
    assert code_name("Stool", "chair", "a high chair") == "other"
    assert code_name("Highchair", "chair", "a highchair") == "specific"


def test_matched_severity_contrast():
    from metalesionlab.plato_damage import at_severity, boot_matched_contrast, matched_contrast, matched_targets

    # family a: severity 0.1, 0.2, 0.4 with outcome 0.05, 0.1, 0.2 (slope 0.5); family b: slope 0
    assert np.allclose(at_severity([0.1, 0.2, 0.4], [0.05, 0.1, 0.2], [0.1, 0.3]), [0.05, 0.15])
    assert np.allclose(at_severity([0.2, 0.1], [1.0, 2.0], [0.2]), [2.0])  # running max keeps it monotone
    t = matched_targets([0.1, 0.4], [0.2, 0.3])
    assert np.allclose(t, [0.075, 0.15, 0.225])
    assert np.isclose(matched_contrast([0.1, 0.2, 0.4], [0.05, 0.1, 0.2], [0.1, 0.3], [0, 0], t), 0.075)
    rng = np.random.default_rng(1)
    d = np.tile([0.1, 0.2, 0.3], (30, 1)) + 0.01 * rng.normal(size=(30, 3))
    r = boot_matched_contrast(d, 0.5 * d, d, 0 * d, reps=300)
    assert r["ci95"][0] > 0 and np.isclose(r["estimate"], 0.5 * np.mean(r["targets"]), atol=0.01)


def test_style_metrics_tell_a_clean_doodle_from_texture_and_color():
    from metalesionlab.plato_damage import style_metrics

    doodle = np.full((40, 40, 3), 255, np.uint8)
    doodle[10:12, 5:35] = 0  # one black line on white
    m = style_metrics(doodle)
    assert m["colorfulness"] < 1e-9 and m["midtone"] == 0 and m["clean"] == 1 and 0 < m["ink"] < 0.1
    texture = np.random.default_rng(0).integers(70, 190, (40, 40, 1)).repeat(3, axis=2).astype(np.uint8)
    assert style_metrics(texture)["midtone"] > 0.95
    red = np.zeros((40, 40, 3), np.uint8)
    red[..., 0] = 220
    red[:20] = 255
    assert style_metrics(red)["colorfulness"] > 50


def test_name_categories_separate_other_objects_from_patterns():
    from metalesionlab.plato_damage import name_category

    assert name_category("bicycle", "chair", "a wheelchair") == "other_object"
    assert name_category("Abstract", "chair", "a wheelchair") == "no_object"
    assert name_category("optical illusion", "chair", "a rocking chair") == "no_object"
    assert name_category("Wheelchair", "chair", "a wheelchair") == "kind"
    assert name_category("chair", "chair", "a throne") == "basic"
    assert name_category("Chair", "chair", "plain") == "kind"
    assert name_category("The object in this picture is", "chair", "plain") == "empty"


def test_damage_route_loads_and_caches_its_statistics(tmp_path):
    import os

    from metalesionlab.web.plato_damage_routes import load_data

    f = tmp_path / "plato_damage.json"
    assert load_data(f) is None
    f.write_text('{"curves": {}}')
    assert load_data(f) == {"curves": {}}
    f.write_text("[1, 2]")  # not an object
    os.utime(f, ns=(1, 10 ** 18))
    assert load_data(f) is None

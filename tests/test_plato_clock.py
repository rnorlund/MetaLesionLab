"""The clock test (/plato/clock), offline: the prompts fixed in the pre-registration, the persona ages, the MoCA's
three clock points from an eye score or Muse Spark's checklist, agreement, and the guard that keeps anything per
person out of what is published."""
import pytest

from metalesionlab import plato_clock as C
from metalesionlab.plato_damage import CLOCK_KEYS


def test_prompts_keep_the_moca_words():
    moca = "Draw a clock. Put in all the numbers and set the time to 10 past 11."
    assert C.INSTRUCTION == moca
    assert C.IMAGE_PROMPT == moca + " Simple black pen drawing on white paper."
    assert C.SVG_PROMPT.startswith(moca)
    p = C.persona_prompt(34)
    assert p == "Drawn by a 34-year-old: " + C.IMAGE_PROMPT
    # the age and nothing else: no other trait slips into a persona
    assert p.replace("Drawn by a 34-year-old: ", "") == C.IMAGE_PROMPT
    plan = (C.Path(__file__).resolve().parents[1] / "docs" / "plato_clock_plan.md").read_text()
    for prompt in (C.IMAGE_PROMPT, C.SVG_PROMPT):
        assert prompt in plan.replace("*", "")


def test_persona_ages_even_without_the_export():
    ages, rule = C.persona_ages(None)
    assert rule == "even" and ages == list(range(20, 81, 4)) and len(ages) == 16


def test_persona_ages_follow_the_decades():
    decades = [{"lo": 20, "hi": 29, "n": 40}, {"lo": 30, "hi": 39, "n": 40}, {"lo": 40, "hi": 49, "n": 40},
               {"lo": 50, "hi": 59, "n": 120}, {"lo": 60, "hi": 69, "n": 80}, {"lo": 70, "hi": 80, "n": 20}]
    ages, rule = C.persona_ages(decades)
    assert rule == "stratified" and len(ages) == 16 and ages == sorted(ages)
    per = [sum(d["lo"] <= a <= d["hi"] for a in ages) for d in decades]
    assert min(per) >= 1 and per[3] == max(per)  # every decade has a place; the biggest has the most
    assert all(20 <= a <= 80 for a in ages)


@pytest.mark.parametrize("hands,h,m,label", [
    (2, 11, 2, "11:10"), (2, 10, 2, "10:10"), (2, 2, 11, "swapped"), (2, 3, 9, "other"), (1, 11, 2, "none"),
    (2, None, 2, "none"), (2, "11", "2", "11:10"), (2, 23, 14, "11:10"), (2, 0, 2, "other"),
])
def test_time_label(hands, h, m, label):
    assert C.time_label(hands, h, m) == label


def rubric(**kw):
    r = dict.fromkeys(CLOCK_KEYS)
    r.update(is_clock=True, contour=True, numbers_count=12, numbers_in_order=True, extra_or_wrong_numbers=False, hands=2,
             hour_hand_points_to=11, minute_hand_points_to=2)
    r.update(kw)
    return r


def test_spark_points_follow_the_moca_rules():
    assert C.spark_points(rubric()) == {"contour": True, "numbers": True, "hands": True, "total": 3, "time": "11:10",
                                        "read": True}
    ten = C.spark_points(rubric(hour_hand_points_to=10))
    assert ten["hands"] is False and ten["time"] == "10:10" and ten["total"] == 2
    assert C.spark_points(rubric(numbers_count=11))["numbers"] is False
    assert C.spark_points(rubric(extra_or_wrong_numbers=True))["numbers"] is False
    assert C.spark_points(rubric(numbers_in_order=False))["numbers"] is False
    assert C.spark_points(rubric(hands=3))["hands"] is False
    assert C.spark_points(None) == {"contour": False, "numbers": False, "hands": False, "total": 0, "time": "none",
                                    "read": False}


def test_eye_points_need_the_hands_at_11_and_2():
    e = {"contour": True, "numbers": False, "hands": True, "hands_n": 2, "hour_to": 11, "minute_to": 2, "note": ""}
    assert C.eye_points(e) == {"contour": True, "numbers": False, "hands": True, "total": 2, "time": "11:10"}
    with pytest.raises(ValueError):
        C.eye_points({**e, "hour_to": 10})
    with pytest.raises(ValueError):
        C.eye_points({**e, "contour": None})


def test_agreement_and_kappa():
    eye = [C.eye_points({"contour": True, "numbers": n, "hands": False, "hands_n": 2, "hour_to": 10, "minute_to": 2})
           for n in (True, True, False, False)]
    spark = [C.spark_points(rubric(numbers_count=12 if n else 9, hour_hand_points_to=10)) for n in (True, False, False, False)]
    a = C.agreement(eye, spark)
    assert a["contour"] == {"agree": 4, "n": 4, "kappa": None}  # all yes on both sides: kappa is undefined
    assert a["numbers"]["agree"] == 3 and a["numbers"]["kappa"] == pytest.approx(0.5)
    assert a["time"] == {"agree": 4, "n": 4}


def test_tally_counts_points_and_times():
    s = [C.spark_points(rubric()), C.spark_points(rubric(hour_hand_points_to=10)), C.spark_points(None)]
    t = C.tally(s)
    assert t["hands"]["k"] == 1 and t["contour"]["k"] == 2 and t["times"] == {"11:10": 1, "10:10": 1, "none": 1}
    assert t["all_three"] == 1 and t["mean_total"] == pytest.approx(5 / 3)


@pytest.mark.parametrize("ai,ci,people,verdict", [
    (0.1, [0.05, 0.15], 0.08, "matches"), (0.3, [0.2, 0.4], 0.05, "exaggerates"),
    (-0.1, [-0.2, -0.01], 0.05, "contradicts"), (0.1, [-0.02, 0.2], 0.05, "no clear change"),
])
def test_trend_verdict(ai, ci, people, verdict):
    assert C.trend_verdict(ai, ci, people) == verdict


def test_validate_public_refuses_anything_per_person():
    ok = {"n": 336, "decades": [{"label": "20s", "age_range": [20, 29], "n": 41, "mean_points": 2.6}],
          "quantiles": {"q": [10, 25, 50, 75, 90], "d": [0.1, 0.12, 0.15, 0.2, 0.25]}}
    assert C.validate_public(ok) == []
    bad = {"subject_ids": ["x"], "n": 12, "dob": "1960-01-02", "distances": list(range(300)),
           "groups": [{"participant": 1}], "visit": "3/14/2021"}
    problems = " ".join(C.validate_public(bad))
    for what in ("subject_ids", "a group of 12", "dob", "a list of 300 numbers", "participant", "visit", "looks like a date"):
        assert what in problems, what

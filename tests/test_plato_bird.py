import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from metalesionlab.plato_bird import (PICTURE_CATEGORIES, bootstrap_group_diff, bootstrap_mean_ci, clean,
                                      dominance, entropy_bits, equal_n, exact_measures, from_probs,
                                      match_probability, measures, normalize, picture_label_prompt, prompt_for,
                                      singular, singular_phrase, tempered, top_answers)


# ---------- normalization ----------

@pytest.mark.parametrize("raw, expected", [
    ("Robin.", "robin"),
    ("**A robin**", "robin"),
    ("  the Owl (Strigiformes)\nIt is nocturnal.", "owl"),
    ("Answer: Sparrow", "sparrow"),
    ("Apple, banana", "apple"),
    ("Sparrow or robin", "sparrow"),
    ("Hammer - a tool", "hammer"),
    ("Breaking and entering", "breaking and entering"),  # "and" never splits an answer
    ("“Rose”", "rose"),
    ("Two", "2"),
])
def test_clean_keeps_the_first_item_without_articles_or_markup(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("plural, single", [
    ("cabbages", "cabbage"), ("daffodils", "daffodil"), ("cherries", "cherry"), ("boxes", "box"),
    ("dishes", "dish"), ("buses", "bus"), ("geese", "goose"), ("knives", "knife"), ("potatoes", "potato"),
    ("roses", "rose"), ("apples", "apple"), ("cacti", "cactus"),
])
def test_singular_handles_regular_and_irregular_plurals(plural, single):
    assert singular(plural) == single


@pytest.mark.parametrize("word", ["glasses", "scissors", "gymnastics", "chess", "happiness", "tennis", "gas",
                                  "hibiscus", "cactus", "trousers", "news", "measles", "fish", "sheep"])
def test_singular_leaves_words_that_only_look_plural(word):
    assert singular(word) == word


def test_singular_phrase_changes_the_head_noun_only():
    assert singular_phrase("golden retrievers") == "golden retriever"
    assert singular_phrase("bodies of water") == "body of water"
    assert singular_phrase("cups of tea") == "cup of tea"
    assert normalize("Blue Tits") == "blue tit"


def test_synonym_map_applies_before_and_after_singular():
    syn = {"eggplant": "aubergine", "soccer": "football", "wrench": "spanner"}
    assert normalize("Eggplants", syn) == "aubergine"
    assert normalize("Soccer.", syn) == "football"
    assert normalize("a wrench", syn) == "spanner"
    assert normalize("Robins", syn) == "robin"


def test_empty_and_overlong_answers_are_unusable():
    assert normalize("") == ""
    assert normalize("   \n  ") == ""
    assert normalize("x" * 60) == ""
    assert clean("1/2") == "1/2"


# ---------- concentration measures ----------

def test_dominance_and_entropy_on_known_distributions():
    one = Counter({"robin": 10})
    even = Counter({"a": 5, "b": 5, "c": 5, "d": 5})
    assert dominance(one) == 1.0 and entropy_bits(one) == 0.0
    assert dominance(even) == 0.25 and math.isclose(entropy_bits(even), 2.0)
    skew = Counter({"apple": 15, "orange": 3, "banana": 2})
    assert dominance(skew) == 0.75
    p = np.array([15, 3, 2]) / 20
    assert math.isclose(entropy_bits(skew), float(-(p * np.log2(p)).sum()))
    assert top_answers(Counter({"owl": 3, "eagle": 3, "pigeon": 1})) == ["eagle", "owl"]


def test_match_probability_is_unbiased_and_independent_of_n():
    assert match_probability(Counter({"a": 1, "b": 1})) == 0.0
    assert match_probability(Counter({"a": 2})) == 1.0
    # population p = (0.5, 0.5): match probability 0.5 at any n, in expectation
    rng = np.random.default_rng(1)
    for n in (5, 50):
        vals = [match_probability(Counter(rng.choice(["a", "b"], n))) for _ in range(4000)]
        assert abs(np.mean(vals) - 0.5) < 0.02


def test_measures_ignore_empty_answers():
    m = measures(["robin", "robin", "", "sparrow"])
    assert m["n"] == 3 and m["distinct"] == 2 and math.isclose(m["dominance"], 2 / 3) and m["top"] == ["robin"]


def test_equal_n_subsampling_matches_small_sample_bias():
    # 50 answers spread over 25 kinds: at n = 50 the top share is 0.04; in subsets of 20 it is higher
    answers = [f"k{i % 25}" for i in range(50)]
    full = measures(answers)
    sub = equal_n(answers, 20, reps=300)
    assert full["dominance"] == pytest.approx(0.04)
    assert sub["dominance"] > full["dominance"]
    assert sub["distinct"] <= 20 and sub["entropy_bits"] < full["entropy_bits"]
    # all the same: still 1 and 0 at any n
    same = equal_n(["apple"] * 50, 20, reps=50)
    assert same["dominance"] == 1.0 and same["entropy_bits"] == 0.0 and same["distinct"] == 1.0
    # asking for more than there are uses all of them
    assert equal_n(["a", "b"], 20, reps=5)["n"] == 2


def test_probability_measures_and_temperature():
    probs = {"robin": 0.8, "sparrow": 0.15, "owl": 0.05}
    ex = exact_measures(probs)
    assert ex["top"] == "robin" and ex["dominance"] == pytest.approx(0.8)
    assert ex["match_probability"] == pytest.approx(0.8 ** 2 + 0.15 ** 2 + 0.05 ** 2)
    hot, cold = tempered(probs, 2.0), tempered(probs, 0.5)
    assert sum(hot.values()) == pytest.approx(1) and sum(cold.values()) == pytest.approx(1)
    assert hot["robin"] < 0.8 < cold["robin"]
    assert tempered(probs, 1.0)["sparrow"] == pytest.approx(0.15)
    sim = from_probs(probs, 20, reps=400)
    assert 0.75 < sim["dominance"] < 0.9


def test_bootstrap_helpers():
    ci = bootstrap_mean_ci([0.1, 0.2, 0.3, float("nan")], reps=2000)
    assert ci["n"] == 3 and ci["mean"] == pytest.approx(0.2) and ci["ci95"][0] < 0.2 < ci["ci95"][1]
    d = bootstrap_group_diff([1, 1, 1, 0, 0, 0], ["A", "A", "A", "C", "C", "C"], "A", "C", reps=500)
    assert d["diff"] == 1.0 and d["ci95"] == [1.0, 1.0] and d["n"] == [3, 3]


def test_prompts():
    assert prompt_for("bird") == "Name one member of the category bird. Answer with one word or a short name only."
    assert len(PICTURE_CATEGORIES) == 12
    assert PICTURE_CATEGORIES["dog"] == ("a dog", "breed of dog")
    assert "Which fruit is in this drawing?" in picture_label_prompt("a fruit", "fruit")


# ---------- category aliases and synonyms ----------

def test_category_aliases_merge_spacing_and_head_noun_variants():
    from metalesionlab.plato_bird import category_aliases, category_head

    assert category_head("tree") == "tree" and category_head("four-wheeled vehicle") == "vehicle"
    assert category_head("room in a house") == "room" and category_head("bird of prey") == "bird"
    assert category_aliases("room in a house", Counter({"living": 2, "living room": 1})) == {"living": "living room"}
    assert normalize("Alzheimer's") == "alzheimer" and normalize("fisherman's") == "fisherman"
    # spacing: the most frequent form wins
    assert category_aliases("bird", Counter({"bluebird": 4, "blue bird": 1})) == {"blue bird": "bluebird"}
    # head noun: the fuller form names the group, and only when both forms occur
    assert category_aliases("hat", Counter({"top": 5, "top hat": 1, "cap": 4})) == {"top": "top hat"}
    assert category_aliases("nut", Counter({"pine nut": 3})) == {}
    # the norms' own name for a merged group wins: "beef", not "beef meat"
    assert category_aliases("meat", Counter({"beef": 40, "beef meat": 2}), {"beef"}) == {"beef meat": "beef"}
    # different members are never merged
    assert category_aliases("bird", Counter({"robin": 9, "sparrow": 9})) == {}


def test_category_synonyms_stay_in_their_category():
    from metalesionlab.plato_bird import synonyms_for

    assert normalize("Happiness", synonyms_for("emotion")) == "happy"
    assert normalize("Depression", synonyms_for("psychological illness")) == "depression"  # not "depressed"
    assert normalize("Pacific Ocean", synonyms_for("body of water")) == "pacific"
    assert normalize("Fracture", synonyms_for("injury")) == "broken bone"
    assert normalize("Soccer", synonyms_for("sport")) == "football"
    assert normalize("1/2", synonyms_for("fraction")) == "half"
    assert normalize('1st matching response: "Red" – a basic colour name') == "red"


# ---------- the public statistics file ----------

PUBLIC = Path(__file__).resolve().parents[1] / "public_data" / "plato_bird.json"


def _strict(text):
    def bad(c):
        raise ValueError(f"non-standard JSON constant {c}")
    return json.loads(text, parse_constant=bad)


@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_bird.json not written yet")
def test_public_file_schema_and_credit():
    text = PUBLIC.read_text()
    d = _strict(text)  # no NaN: browsers reject it
    assert d["n_categories"] == len(d["categories"]) == 117
    assert "Banks" in d["credit"] and "CC BY 4.0" in d["credit"] and d["human_data"]["license"] == "CC BY 4.0"
    assert d["prompt"] == "Name one member of the category {category}. Answer with one word or a short name only."
    assert {r["domain"] for r in d["categories"]} == {"Concrete", "Abstract"}
    assert [r["category"] for r in d["ai_only"]] == ["game"]
    for r in d["categories"]:
        assert 13 <= r["n_human"] <= 20
        for src in ("human", "spark", "glimmer_logits", "glimmer_T1.0"):
            assert 0 < r[src]["dominance"] <= 1 and r[src]["entropy_bits"] >= 0 and r[src]["top"]
        t = r["tables"]
        assert sum(n for _, n in t["human_first"]) == r["n_human"]
        assert sum(n for _, n in t["spark"]) == 50
        # production counts distinct people, so a merged member never exceeds the number of people
        assert all(len(row) == 3 and 1 <= row[1] <= r["n_people"] <= 20 for row in t["human_named"])
    s = d["summary"]
    for src in ("spark", "glimmer_logits", "glimmer_T1.0"):
        for m in ("dominance", "entropy_bits"):
            c = s[src][m]["diff"]
            assert c["ci95"][0] <= c["mean"] <= c["ci95"][1] and s[src][m]["n"] == 117
    assert len(d["pictures"]) == 12 and all(len(p["spark"]["labels"]) == 12 for p in d["pictures"].values())
    # aggregate counts only: no participant codes, ages or response times
    for field in ("participant", "response_code", "trial.RT", "participant.age", "participant.sex", "mean.RT"):
        assert f'"{field}"' not in text


# ---------- the page ----------

@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_bird.json not written yet")
def test_page_and_api_render():
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_bird_routes

    plato_bird_routes._cache.clear()
    c = TestClient(web.app)
    r = c.get("/plato/bird")
    assert r.status_code == 200 and "Plato’s Bird" in r.text and 'id="game-form"' in r.text
    assert "Banks" in r.text and "CC BY 4.0" in r.text
    d = c.get("/api/plato/bird").json()
    assert d["n_categories"] == 117 and any(x["category"] == "bird" for x in d["categories"])
    for path in ("/static/js/plato_bird.js", "/static/css/plato_bird.css", "/static/img/plato_bird/bird.webp"):
        assert c.get(path).status_code == 200


def test_api_reports_missing_data(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_bird_routes

    monkeypatch.setattr(plato_bird_routes, "DATA", tmp_path / "missing.json")
    plato_bird_routes._cache.clear()
    assert TestClient(web.app).get("/api/plato/bird").status_code == 503


def test_page_static_files_stay_small():
    from metalesionlab.web import app as web

    files = [web.HERE / "static" / "js" / "plato_bird.js", web.HERE / "static" / "css" / "plato_bird.css",
             *(web.HERE / "static" / "img" / "plato_bird").glob("*")]
    assert sum(f.stat().st_size for f in files if f.exists()) < 1.5 * 1024 * 1024

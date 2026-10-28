import numpy as np

from metalesionlab.plato_robust import (ALTERNATIVES, EMBEDDERS, MIN_CONCEPTS_BELOW, REFERENCE,
                                        hierarchical_median_ci, verdict)


def test_embedders_are_open_and_the_reference_is_the_core_model():
    from metalesionlab.plato import DINO_MODEL

    assert EMBEDDERS[REFERENCE].model_id == DINO_MODEL
    assert REFERENCE not in ALTERNATIVES and set(ALTERNATIVES) <= set(EMBEDDERS)
    assert all(EMBEDDERS[t].license == "Apache-2.0" for t in EMBEDDERS)
    assert {EMBEDDERS[t].maker for t in ALTERNATIVES} == {"Meta", "Google"}


def test_median_ci_collapses_without_noise_and_widens_with_it():
    # 35 identical items with no sampling noise: the median is certain
    assert hierarchical_median_ci(np.full((35, 50), 0.5), reps=200) == [0.5, 0.5]
    # items spread over 0.3..0.7, no within-item noise: the CI covers the true median and stays inside the items
    items = np.linspace(0.3, 0.7, 35)[:, None] * np.ones((35, 50))
    lo, hi = hierarchical_median_ci(items, reps=1000)
    assert 0.3 <= lo < 0.5 < hi <= 0.7
    # the same items with within-item noise: a wider CI, still around 0.5
    noisy = items + np.random.default_rng(1).normal(0, 0.2, items.shape)
    lo2, hi2 = hierarchical_median_ci(noisy, reps=1000)
    assert lo2 < 0.5 < hi2 and hi2 - lo2 > hi - lo


def test_nearest_centroid_leave_one_out_removes_the_picture_from_its_own_mean():
    from metalesionlab.plato_robust import nearest_centroid_share

    # concept a: two orthogonal pictures; concept b: two identical pictures leaning slightly toward both of a's
    b = np.array([0.3, 0.3, 1.0])
    sets = {"a": np.array([[1.0, 0, 0], [0, 1.0, 0]]), "b": np.array([b, b])}
    # counting itself, each a-picture is closest to its own set (0.5 > 0.28); without itself it is not (0 < 0.28)
    assert nearest_centroid_share(sets, sets) == {"a": 1.0, "b": 1.0}
    assert nearest_centroid_share(sets, sets, leave_one_out=True) == {"a": 0.0, "b": 1.0}
    # new pictures (e.g. AI doodles) against people's sets; length does not matter, only direction
    assert nearest_centroid_share({"b": 5 * np.array([b])}, sets) == {"b": 1.0}


def _reference_like(**changes) -> dict:
    s = {"index_median": 0.49, "index_median_ci95": [0.42, 0.56], "concepts_below_1": 34, "n_concepts": 35,
         "chair_index_ci95": [0.24, 0.55], "muse_over_sdxl_median_ci95": [0.35, 0.5], "concepts_muse_below_sdxl": 34,
         "sdxl_index_median_ci95": [1.1, 1.35], "any_vs_default_median": 0.96, "any_vs_people_median_ci95": [0.42, 0.58],
         "listed_vs_people_median_ci95": [1.15, 1.45], "listed_vs_default_median_ci95": [2.3, 3.1]}
    s.update(changes)
    return s


def test_verdict_on_the_reference_and_on_failures():
    v = verdict(_reference_like())
    assert v["core"] == "holds" and v["variety"] == "holds" and v["sdxl_not_below_people"]
    assert v["checks"]["ranks_agree"] is None  # the reference has no rank agreement with itself
    assert verdict(_reference_like(rho_index_vs_reference=0.75))["core"] == "holds"
    # concept ranks disagree, or the chair is not clearly flattened: direction only
    assert verdict(_reference_like(rho_index_vs_reference=0.45))["core"] == "holds in direction"
    assert verdict(_reference_like(chair_index_ci95=[0.6, 1.05]))["core"] == "holds in direction"
    # median below 1 but its CI reaches 1, or too few concepts below 1, or Muse not below SDXL: weaker
    assert verdict(_reference_like(index_median=0.9, index_median_ci95=[0.8, 1.02]))["core"] == "weaker"
    assert verdict(_reference_like(concepts_below_1=MIN_CONCEPTS_BELOW - 1))["core"] == "weaker"
    assert verdict(_reference_like(muse_over_sdxl_median_ci95=[0.8, 1.1]))["core"] == "weaker"
    assert verdict(_reference_like(index_median=1.02, index_median_ci95=[0.95, 1.1]))["core"] == "does not hold"
    # variety: "any kind" doubles the spread but named kinds still lift above people -> partly
    v = verdict(_reference_like(any_vs_default_median=2.0, any_vs_people_median_ci95=[0.9, 1.2]))
    assert v["variety"] == "partly" and not v["checks"]["any_about_default"]
    v = verdict(_reference_like(any_vs_default_median=1.5, listed_vs_people_median_ci95=[0.9, 1.2]))
    assert v["variety"] == "does not hold"
    assert not verdict(_reference_like(sdxl_index_median_ci95=[0.7, 0.95]))["sdxl_not_below_people"]

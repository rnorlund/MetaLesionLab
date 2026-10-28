"""The Atlas of Forms: concept selection, statistics, the benchmark script, the data files and the page."""
from collections import Counter

import numpy as np

from metalesionlab import plato
from metalesionlab import plato_atlas as A


# --- the pre-registered concept list ---------------------------------------------------------------

def test_selection_is_reproducible_and_matches_the_plan():
    new = A.select_new()
    assert new == A.select_new(A.SEED) and len(new) == 98
    assert Counter(d for _, d in new) == Counter(A.QUOTAS)
    assert all(w in A.ELIGIBLE[d] for w, d in new)
    assert {"rain", "hurricane", "snowman"} <= {w for w, _ in new}
    # a few of the drawn concepts named in docs/plato_atlas_plan.md
    assert {"ant", "whale", "peas", "anvil", "submarine", "see saw", "skull", "teddy-bear"} <= {w for w, _ in new}


def test_concepts_cover_core_forms_and_new_once():
    keys = [c.key for c in A.CONCEPTS]
    assert len(keys) == len(set(keys)) == 135
    assert Counter(c.origin for c in A.CONCEPTS) == {"core": 35, "forms": 2, "new": 98}
    assert [c.key for c in A.CONCEPTS if c.origin == "core"] == [c.key for c in plato.CONCEPTS]
    assert sum(c.natural for c in A.CONCEPTS) == 51
    listed = [w for ws in A.EXCLUDED.values() for w in ws] + [w for ws in A.ELIGIBLE.values() for w in ws]
    studied = {c.quickdraw for c in A.CONCEPTS if c.origin != "new"}
    assert len(listed) == len(set(listed)) and not set(listed) & studied
    assert len(listed) + len(studied) == 345  # every Quick, Draw! category sorted exactly once
    assert all(c.domain in A.DOMAINS for c in A.CONCEPTS)


def test_prompt_phrases():
    by = {c.quickdraw: c for c in A.CONCEPTS}
    assert by["anvil"].phrase == "an anvil" and by["grapes"].phrase == "grapes" and by["moon"].phrase == "the moon"
    assert by["teddy-bear"].phrase == "a teddy bear" and by["teddy-bear"].label == "teddy bear"
    assert by["chair"].phrase == "a chair" and by["yoga"].phrase == "a person doing yoga"
    assert A.prompt_for(by["rain"]).startswith("A quick simple doodle sketch of rain, black marker")
    assert A.slug("t-shirt") == "t-shirt" and A.slug("sea_turtle") == "sea-turtle"


# --- statistics ------------------------------------------------------------------------------------

def test_spread_ratio_tight_set_is_below_one():
    rng = np.random.default_rng(0)
    center = rng.normal(size=32)
    tight = center + 0.1 * rng.normal(size=(12, 32))
    loose = center + 1.0 * rng.normal(size=(60, 32))
    r = A.spread_ratio(tight, loose, rng=rng, reps_ai=200, reps_human=100, subsets=50)
    assert r["n"] == 12 and r["ratio"] < 0.3 and r["ratio_ci95"][1] < 1
    assert r["spread_ci95"][0] <= r["spread"] <= r["spread_ci95"][1]
    assert len(r["_ratio_boot"]) == 100


def test_median_ci_and_wilson():
    boots = [np.full(50, v) for v in (0.2, 0.4, 0.5, 0.6, 0.8)]
    lo, hi = A.median_ci(boots, reps=500, rng=np.random.default_rng(1))
    assert 0.2 <= lo <= 0.5 <= hi <= 0.8
    lo, hi = A.wilson_ci(90, 98)
    assert 0.83 < lo < 0.92 < hi < 0.97
    assert A.wilson_ci(0, 10)[0] == 0


def test_form_average_is_crisp_for_copies_and_cloudy_for_variety():
    a = np.full((64, 64), 255.0)
    a[30:34, :] = 0
    copies = A.form_average([a] * 12)
    assert copies.min() == 0 and copies[0, 0] == 255 and (copies[30:34] == 0).all()
    shifted = [np.roll(a, s, axis=0) for s in range(-20, 21, 4)]
    cloud = A.form_average(shifted)
    assert cloud.min() == 0 and (cloud < 255).sum() > (copies < 255).sum()
    assert A.pixel_spread(shifted) > A.pixel_spread([a] * 5) - 1e-6

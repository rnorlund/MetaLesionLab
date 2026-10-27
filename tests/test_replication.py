import numpy as np
import pytest

from metalesionlab import replication as R


@pytest.mark.parametrize("said, code, expected", [
    ("Caraloon? Wait object is carrot. One word:", "Nonword", True),
    ("Hel-​s? Actually helicopter.\n\nHelicopter", "Formal", False),  # target is helicopter, not carrot
    ("Umb", "Nonword", False),
    ("Carrot", "Correct", False),
    ("The object is a crayon. It is orange.", "Formal", False),
])
def test_self_correction(said, code, expected):
    assert R.self_correction(said, code, "carrot") is expected


def test_self_correction_with_alternates_and_other_targets():
    assert R.self_correction("Hel-s? Actually helicopter.\n\nHelicopter", "Formal", "helicopter")
    assert R.self_correction("Pante... Wait object is a teapot, also", "Neologism", "kettle", ("teapot",))


@pytest.mark.parametrize("said, code, expected", [
    ("5-01-26-01-01-01-", "Unrelated", True),
    (": 2025-2025-2025-202", "Unrelated", True),
    ('">The McGob!_2025-2025', "Neologism", True),
    ("FileImageUrl: \"https://www.shutterstock.com/", "Description", False),
    ("Name the object in this picture with exactly one word.", "Description", False),
    ("", "NoResponse", False),
    ("Crayon", "Formal", False),
])
def test_jargon(said, code, expected):
    assert R.is_jargon(said, code) is expected


def test_error_types_row():
    t = R.error_types({"said": "The object is a teapot.", "code": "Semantic"}, "kettle")
    assert t == {"error": True, "meaning": True, "sound": False, "self_correction": False, "jargon": False}


def test_matrix_orders_pictures_and_runs():
    runs = [{"items": [{"word": "a", "code": "Correct"}, {"word": "b", "code": "Formal"}]},
            {"items": [{"word": "b", "code": "Correct"}, {"word": "a", "code": "Correct"}]}]
    m = R.matrix(runs, ["a", "b"], R.correct)
    assert m.tolist() == [[1, 1], [0, 1]]


def test_paired_bootstrap_direction_and_ci():
    rng = np.random.default_rng(1)
    targeted = (rng.random((100, 1)) < 0.5).astype(float)
    controls = np.ones((100, 5))
    r = R.paired_bootstrap(targeted, controls, n_boot=500)
    assert r["diff"] == pytest.approx(1 - targeted.mean(), abs=1e-4)
    assert r["ci95"][0] > 0.3 and r["p_sign_flip"] < 0.001
    same = R.paired_bootstrap(controls, controls, n_boot=200)
    assert same["diff"] == 0 and same["ci95"] == [0, 0]


def test_share_bootstrap_and_criterion():
    n = 60
    errors = np.ones((n, 2))
    hits_a = np.ones((n, 2))           # every error is of the type at site a
    hits_b = np.zeros((n, 2))
    hits_c = np.zeros((n, 2))
    hits_c[::4] = 1                    # a quarter at site c
    res = R.share_bootstrap({"a": (errors, hits_a), "b": (errors, hits_b), "c": (errors, hits_c)}, n_boot=300)
    assert res["shares"]["a"]["share"] == 1.0 and res["shares"]["c"]["share"] == 0.25
    assert res["differences"]["a - b"]["diff"] == 1.0
    assert R.largest_with_margin(res, "a")
    assert not R.largest_with_margin(res, "c")

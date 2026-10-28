import json

import numpy as np
import pytest

from metalesionlab import plato_telephone as T
from metalesionlab.plato import STYLES


def test_seeds_are_eight_chairs_and_two_controls():
    assert len(T.SEEDS) == 10 and len(T.CHAIR_SEEDS) == 8
    assert {s.concept for s in T.CHAIR_SEEDS} == {"chair"}
    assert [s.concept for s in T.SEEDS if s.control] == ["hat", "clock"]
    assert len(T.BY_KEY) == 10
    for s in T.SEEDS:  # every seed's own name is found by its kind word, and the category word too
        assert T.has_word(s.kind, s.kind_word), s.key
        assert T.has_word(s.kind, T.CATEGORY_WORD[s.concept]) or s.key in {"throne", "cuckoo_clock"} or s.control


@pytest.mark.skipif(not (T.SEED_DIR / "chair" / "kinds.json").exists(), reason="seed doodles not on this machine")
def test_seed_files_are_the_listed_kinds():
    for s in T.SEEDS:
        kinds = json.loads((T.SEED_DIR / s.concept / "kinds.json").read_text())
        assert s.file == f"p{kinds.index(s.kind)}.png" and (T.SEED_DIR / s.concept / s.file).exists()


def test_phrase_cleans_only_the_edges():
    assert T.phrase('  "A chair with   four legs."  ') == "a chair with four legs"
    assert T.phrase("The throne has a tall back. It has armrests.") == "the throne has a tall back. It has armrests"
    assert T.phrase("Another chair.") == "Another chair"  # only a whole leading article is lower-cased
    assert T.phrase("x " * 400, max_chars=20).endswith("x") and len(T.phrase("x " * 400, max_chars=20)) <= 20
    assert T.phrase("") == ""


def test_image_prompt_uses_the_core_doodle_template():
    p = T.image_prompt("A rocking chair with curved runners.")
    assert p == STYLES["doodle"].format(phrase="a rocking chair with curved runners")
    assert p.startswith("A quick simple doodle sketch of a rocking chair") and p.endswith("no shading.")


def test_kind_and_category_words():
    by = T.BY_KEY
    assert T.has_word("an old ROCKING chair", by["rocking_chair"].kind_word)
    assert T.has_word("curved rockers", by["rocking_chair"].kind_word)
    assert T.has_word("a bean bag seat", by["beanbag"].kind_word) and T.has_word("a bean-bag", by["beanbag"].kind_word)
    assert T.has_word("a high chair with a tray", by["high_chair"].kind_word)
    assert T.has_word("a high-chair", by["high_chair"].kind_word)
    assert not T.has_word("a chair with a high back", by["high_chair"].kind_word)
    assert T.has_word("a folded metal chair", by["folding_chair"].kind_word)
    assert T.has_word("a wheel chair", by["wheelchair"].kind_word)
    assert T.has_word("an armchair", T.CATEGORY_WORD["chair"]) and T.has_word("a wheelchair", T.CATEGORY_WORD["chair"])
    assert T.has_word("a tall hat", T.CATEGORY_WORD["hat"]) and not T.has_word("that thing", T.CATEGORY_WORD["hat"])
    assert T.presence(["a throne", "a chair", "a regal throne"], by["throne"].kind_word) == [True, False, True]


def test_first_loss_is_censored_at_the_end():
    assert T.first_loss([True, True, False, True]) == 2
    assert T.first_loss([False]) == 0
    assert T.first_loss([True, True]) == 2


def test_content_words():
    w = T.content_words("A simple doodle of a rocking chair with curved runners, four legs and a slatted back.")
    assert w == {"rocking", "chair", "curved", "runner", "leg", "slatted", "back"}
    assert "glass" in T.content_words("glass") and "cactus" in T.content_words("cactus")  # no bad plural cuts


def test_word_runs_and_gained_words():
    texts = ["a rocking chair with runners", "a chair with runners", "a chair with four legs"]
    assert T.word_runs(texts) == {"chair": 3, "rocking": 1, "runner": 2}
    assert T.gained_words(texts) == {"leg"}
    assert T.word_runs([]) == {} and T.gained_words([]) == set()


def test_cluster_weights_draw_seeds_then_chains():
    rng = np.random.default_rng(0)
    for _ in range(20):
        w = T.cluster_weights(8, 3, rng)
        assert w.shape == (8, 3) and w.sum() == 24 and np.all(w.sum(1) % 3 == 0)


def test_weighted_mean_skips_missing():
    x = np.array([[1.0, 3.0], [np.nan, 5.0]])
    assert T.weighted_mean(x, np.ones((2, 2))) == pytest.approx(3.0)
    assert T.weighted_mean(x, np.array([[2.0, 0.0], [1.0, 1.0]])) == pytest.approx((2 + 5) / 3)
    assert np.isnan(T.weighted_mean(np.full((1, 1), np.nan), np.ones((1, 1))))


def test_pair_mean_between_and_within_seeds():
    # 2 seeds x 2 chains on a line: seed 0 at 0 and 1, seed 1 at 10 and 12
    pos = np.array([[0.0, 1.0], [10.0, 12.0]])
    d = np.abs(pos[:, :, None, None] - pos[None, None, :, :])
    ones = np.ones((2, 2))
    assert T.pair_mean(d, ones, same_seed=True) == pytest.approx((1 + 2) / 2)
    assert T.pair_mean(d, ones, same_seed=False) == pytest.approx((10 + 12 + 9 + 11) / 4)
    # a chain drawn twice is still never paired with itself
    w = np.array([[2.0, 0.0], [1.0, 1.0]])
    assert T.pair_mean(d, w, same_seed=True) == pytest.approx(2.0)
    d2 = d.copy()
    d2[0, 0, 1, 0] = d2[1, 0, 0, 0] = np.nan
    assert T.pair_mean(d2, ones, same_seed=False) == pytest.approx((12 + 9 + 11) / 3)


def test_gap_closed():
    assert T.gap_closed(0.5, 0.3, 0.1) == pytest.approx(0.5)
    assert T.gap_closed(0.5, 0.1, 0.1) == pytest.approx(1.0)
    assert np.isnan(T.gap_closed(0.2, 0.1, 0.2))

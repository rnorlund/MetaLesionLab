import numpy as np
from PIL import Image, ImageDraw

from metalesionlab.plato import (BY_KEY, CONCEPTS, DEMO_MISSING, bootstrap_simpson, bootstrap_spread,
                                 cosine_distances, ink_crop, kind_diversity, kind_options, labeling_prompt,
                                 listing_prompt, none_option, parse_kinds, parse_letter, plain_option, prompt_for,
                                 render_strokes, spread, subsample_spread, variety_phrase)


def test_concepts_are_quickdraw_categories_in_priority_order():
    assert [c.key for c in CONCEPTS[:2]] == ["chair", "sailboat"]
    assert all(c.n_ai == 16 for c in CONCEPTS if c.tier == 1)
    assert all(c.n_ai == 12 for c in CONCEPTS if c.tier == 2)
    assert not {c.quickdraw for c in CONCEPTS} & set(DEMO_MISSING)
    assert BY_KEY["yoga"].label == "person" and BY_KEY["scissors"].phrase == "a pair of scissors"


def test_spread_is_mean_off_diagonal_distance():
    x = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    d = cosine_distances(x)
    assert np.allclose(np.diag(d), 0)
    expected = np.mean([1.0, 1 - 1 / np.sqrt(2), 1 - 1 / np.sqrt(2)])
    assert np.isclose(spread(d), expected)
    assert np.isclose(spread(d, np.array([0, 1])), 1.0)


def test_bootstrap_never_pairs_a_picture_with_itself():
    # identical pictures would give spread 0; distinct pictures at distance 1 must always give 1
    d = 1 - np.eye(6)
    assert np.allclose(bootstrap_spread(d, reps=200), 1.0)
    assert np.allclose(subsample_spread(d, k=3, reps=20), 1.0)


def test_render_and_crop_put_ink_in_a_centered_square():
    img = render_strokes([[[0, 100], [0, 0]]])  # one horizontal stroke
    assert img.size == (256, 256)
    assert np.asarray(img.convert("L")).min() == 0
    # a gray-paper picture with a small dark square: the paper becomes white, the square fills the frame
    paper = Image.new("L", (300, 200), 200)
    ImageDraw.Draw(paper).rectangle((140, 90, 160, 110), outline=0, width=3)
    out = np.asarray(ink_crop(paper.convert("RGB")).convert("L"))
    assert out.shape == (256, 256)
    assert out[0, 0] == 255 and out[128, 128] == 255  # white corner and white inside the square
    assert out[:, 20:40].min() < 100  # the square's left edge sits near the left margin


# ---------- can you prompt it out of the Platonic chair? ----------

def test_variety_prompts_keep_the_doodle_template():
    chair = BY_KEY["chair"]
    # the pilot's wording, so its pictures still fit
    assert variety_phrase(chair, "unusual") == "a chair (any kind of chair at all; pick an unusual or different kind)"
    assert prompt_for(chair, "doodle_any") == prompt_for(chair, "doodle").replace("a chair", "a chair (any kind of chair)")
    assert variety_phrase(BY_KEY["yoga"], "any") == "a person doing yoga (any person, any pose)"
    assert variety_phrase(BY_KEY["scissors"], "any") == "a pair of scissors (any kind of scissors)"
    assert variety_phrase(BY_KEY["floor_lamp"], "any") == "a floor lamp (any kind of floor lamp)"
    assert "16 clearly different kinds of chair" in listing_prompt(chair, 16)
    assert "yoga poses" in listing_prompt(BY_KEY["yoga"], 12)


def test_parse_kinds_cleans_spark_lists():
    text = "1. A rocking chair\n- **an armchair**.\n\nan Armchair\nRocking chairs are nice\n3) a bar stool\n* a throne"
    assert parse_kinds(text, 16) == ["A rocking chair", "an armchair", "a bar stool", "a throne"]
    assert parse_kinds(text, 2) == ["A rocking chair", "an armchair"]


def test_kind_options_end_with_plain_and_cant_tell():
    umbrella = BY_KEY["umbrella"]
    opts = kind_options(umbrella, ["a golf umbrella", "a lace parasol"])
    assert opts[-2] == plain_option(umbrella) == "a plain, ordinary umbrella"
    assert opts[-1] == none_option(umbrella) == "can't tell, or not an umbrella"
    assert none_option(BY_KEY["chair"]) == "can't tell, or not a chair"
    prompt = labeling_prompt(umbrella, opts)
    assert "A. a golf umbrella" in prompt and "D. can't tell, or not an umbrella" in prompt
    assert 'pick "a plain, ordinary umbrella"' in prompt and prompt.endswith("Answer with the letter only.")


def test_parse_letter_reads_only_a_standalone_letter():
    for text, want in [("B", 1), ("B.", 1), ("**B**", 1), ("Answer: B", 1), ("(B) a sofa", 1), (" c\n", 2)]:
        assert parse_letter(text, 5) == want, text
    assert parse_letter("A plain, ordinary chair", 5) is None  # the article, not option A
    assert parse_letter("Z", 5) is None and parse_letter("", 5) is None


def test_kind_diversity_counts_kinds_not_cant_tell():
    labels = ["plain"] * 6 + ["rocking"] * 2 + ["?"] * 2
    d = kind_diversity(labels, plain="plain", none="?")
    assert d["n"] == 10 and d["n_kind"] == 8 and d["share_none"] == 0.2
    assert d["distinct"] == 2 and d["prototype"] == "plain" and d["prototype_share"] == 0.75
    assert d["share_plain"] == 0.75
    # chance that two different pictures show different kinds: 1 - (6*5 + 2*1) / (8*7)
    assert np.isclose(d["simpson"], 1 - 32 / 56)
    assert np.isclose(d["effective_kinds"], 2 ** d["entropy_bits"])
    assert kind_diversity(["a"] * 5)["simpson"] == 0.0
    assert kind_diversity(["a", "b", "c"])["simpson"] == 1.0
    assert kind_diversity(["?"], none="?")["prototype"] is None


def test_bootstrap_simpson_never_pairs_a_picture_with_itself():
    assert np.allclose(bootstrap_simpson(list("abcdefgh"), reps=200), 1.0)
    assert np.allclose(bootstrap_simpson(["a"] * 8, reps=50), 0.0)
    assert np.isnan(bootstrap_simpson(["a", "?"], none="?", reps=3)).all()

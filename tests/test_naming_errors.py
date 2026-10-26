import pytest

from metalesionlab.naming_errors import classify, phonemes, sound_related

ASSOCIATES = {("cat", "milk"), ("umbrella", "rain"), ("gato", "perro"), ("gato", "pato"), ("cuchara", "tenedor")}


def fake_judge(target, response, lang):
    return (target, response) in ASSOCIATES


@pytest.mark.parametrize("target,response,expected", [
    ("cat", "cat", "Correct"),
    ("cat", "Cats.", "Correct"),
    ("cat", "a black cat", "Correct"),
    ("cat", "", "NoResponse"),
    ("cat", "um, I don't know", "NoResponse"),
    ("cat", "dog", "Semantic"),
    ("cat", "milk", "Semantic"),       # association, from the judge
    ("cat", "hat", "Formal"),
    ("cat", "rat", "Mixed"),
    ("skirt", "shirt", "Mixed"),
    ("anchor", "ankle", "Formal"),
    ("cat", "chair", "Unrelated"),
    ("bench", "river", "Unrelated"),
    ("cat", "cag", "Nonword"),
    ("kettle", "kettin", "Nonword"),
    ("ladder", "blorf", "Neologism"),
    ("bench", "a seat in the park", "Description"),
    ("umbrella", "rain", "Semantic"),
])
def test_english_codes(target, response, expected):
    assert classify(target, response, "en", judge=fake_judge).code == expected


def test_alternate_names_count_as_correct():
    assert classify("couch", "sofa", alternates=("sofa",)).code == "Correct"
    assert classify("couch", "sofa").code == "Semantic"


@pytest.mark.parametrize("target,response,expected", [
    ("gato", "gato", "Correct"),
    ("gato", "el gato", "Correct"),
    ("gato", "gatos", "Correct"),
    ("gato", "no sé", "NoResponse"),
    ("gato", "perro", "Semantic"),
    ("gato", "pato", "Mixed"),
    ("gato", "silla", "Unrelated"),
    ("gato", "gapo", "Nonword"),
])
def test_spanish_codes(target, response, expected):
    assert classify(target, response, "es", judge=fake_judge).code == expected


def test_spanish_spelling_rules():
    assert phonemes("queso", "es")[0] == ("k", "e", "s", "o")
    assert phonemes("cielo", "es")[0][0] == "s"
    assert phonemes("árbol", "es") == (("a", "r", "b", "o", "l"), 0)


def test_sound_relation_uses_cmu_for_words_and_spelling_for_nonwords():
    assert phonemes("cat", "en")[0] == ("K", "AE", "T")
    assert sound_related("cat", "cag", "en")
    assert not sound_related("cat", "dog", "en")

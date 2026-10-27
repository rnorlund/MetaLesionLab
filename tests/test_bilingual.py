"""Bilingual test helpers: response language, switch coding and the paired statistics (no GPU)."""
import numpy as np
import pytest

from metalesionlab import bilingual as B

NAMES = {
    "cat": {"en": ["cat", "kitten"], "es": ["gato", "gatito"], "fr": ["chat", "chaton"], "pt": ["gato", "gatinho"]},
    "umbrella": {"en": ["umbrella"], "es": ["paraguas", "sombrilla"], "fr": ["parapluie"],
                 "pt": ["guarda-chuva", "guarda chuva", "sombrinha"]},
    "igloo": {"en": ["igloo"], "es": ["iglú"], "fr": ["igloo", "iglou"], "pt": ["iglu"]},
    "cactus": {"en": ["cactus"], "es": ["cactus", "cacto"], "fr": ["cactus"], "pt": ["cacto"]},
}
ITEMS = {w: B.BiItem(w, None, names) for w, names in NAMES.items()}


def code(word, variant, said):
    raw = {"lang": B.VARIANT_LANG[variant], "prompt": B.PROMPTS[variant], "items": [{"en": word, "said": said}]}
    B.code_run(raw, ITEMS)
    return raw["items"][0], raw


@pytest.mark.parametrize("word,variant,said,label,switch,switch_code", [
    ("umbrella", "es", "paraguas", "es", False, None),
    ("umbrella", "es", "Umbrella", "en", True, "EnglishName"),
    ("umbrella", "es", "Umb", "en", True, "EnglishOther"),          # a fragment of the English name only
    ("cat", "es", "The object is a cat", "en", True, "EnglishName"),
    ("igloo", "es", "Igloo", "en", True, "EnglishName"),
    ("igloo", "fr", "igloo", "unclear", False, None),               # same word in French and English
    ("cactus", "es", "Cactus", "unclear", False, None),
    ("umbrella", "es", "Paraguas (umbrella)", "mixed", False, None),
    ("umbrella", "es", "Answer: paraguas", "es", False, None),      # format label, not English
    ("umbrella", "pt", "assistant to=selfDiga o nome", "leak", False, None),
    ("umbrella", "es_xen", "Say the name of the object in a single word", "unclear", False, None),  # echo
    ("umbrella", "pt", "Guarda-chuva", "pt", False, None),
])
def test_response_language(word, variant, said, label, switch, switch_code):
    row, _ = code(word, variant, said)
    assert row["lang_label"] == label
    assert row["switch"] is switch
    assert row["switch_code"] == switch_code


def test_reverse_direction_on_english_trials():
    row, raw = code("cat", "en", "gato")
    assert row["switch"] and row["other_lang"] == ["es", "pt"]
    assert row["wrong_name"] and row["other_name"] == ["es", "pt"]
    row, raw = code("cat", "en", "The object is a cat")
    assert not row["switch"] and not row["wrong_name"] and row["code"] == "Correct"
    assert raw["accuracy"] == 1.0
    row, _ = code("cactus", "en", "cactus")  # also the Spanish and French name, but correct in English
    assert not row["wrong_name"]


def test_wrong_name_and_later_english():
    row, raw = code("umbrella", "es", "Umbrella")
    assert row["wrong_name"] and raw["wrong_name_n"] == 1
    row, _ = code("umbrella", "es", "paragu\n\nWait object is umbrella")
    assert row["lang_label"] == "es" and row["later"]          # first attempt Spanish, English self-correction
    row, _ = code("umbrella", "es", "paraguas\n\nparaguas")
    assert not row["later"]
    row, _ = code("umbrella", "en", "umbre\n\nWait object is umbrella")
    assert not row["later"]


def test_english_alternate_dropped_from_other_languages(tmp_path):
    """A manifest alternate that is just the English word (pt "igloo") is not accepted."""
    import json

    def write(set_name, lang, words):
        d = tmp_path / set_name
        (d / "candidates").mkdir(parents=True)
        items = [{"word": w, "gloss": g, "lang": lang, "status": "kept", "image": f"candidates/{w}.png",
                  "alternates": alts} for w, g, alts in words]
        (d / "manifest.json").write_text(json.dumps({"lang": lang, "items": items}))

    write("demo_en", "en", [("igloo", "igloo", None)])
    write("demo_pt", "pt", [("iglu", "igloo", ["igloo"])])
    items = B.matched_items(tmp_path, ("en", "pt"))
    assert items[0].names["pt"] == ["iglu"]


def test_bootstrap_drop_diff_signs():
    n = 20
    base = np.ones(n)
    en = np.ones((n, 3))
    es = np.ones((n, 3))
    es[:10] = 0  # half the pictures fail in Spanish only
    res = B.bootstrap_drop_diff([(en, es)], base, base, n_boot=500)
    assert res["diff"] == pytest.approx(0.5)
    assert res["ci95"][0] > 0.2
    same = B.bootstrap_drop_diff([(en, en.copy())], base, base, n_boot=200)
    assert same["diff"] == 0 and same["ci95"] == [0.0, 0.0]


def test_sign_flip_test():
    assert B.sign_flip_test(np.full(12, 0.5), n_perm=5000) < 0.001
    assert B.sign_flip_test(np.zeros(12)) == 1.0
    rng = np.random.default_rng(1)
    assert B.sign_flip_test(rng.normal(0, 1, 20), n_perm=5000) > 0.05


def test_lens_pivot_top1():
    pieces = {"cat": {"en": {"cat", "Cat"}, "es": {"gat", "G"}}}
    rows = [{"en": "cat", "lens": {"logp": {"en": [-20, -1, -3], "es": [-20, -5, -0.1]}, "top1": ["x", "Cat", "G"]}}]
    out = B.lens_pivot([{"items": rows}], ["cat"], "es", pieces=pieces)
    assert out["frac_top1_other"] == [0, 1, 0]
    assert out["frac_top1_lang"] == [0, 0, 1]
    assert out["share_trials_other_top1_any_layer"] == 1.0
    assert out["frac_other_above_confident"] == [0, 1, 0]

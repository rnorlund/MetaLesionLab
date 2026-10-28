import json

import numpy as np
import pytest

from metalesionlab import meta_api
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


# ---------- public file, page and API ----------

PUBLIC = meta_api.REPO_ROOT / "public_data" / "plato_telephone.json"


@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_telephone.json not written yet")
def test_public_file_schema_and_no_pictures():
    d = json.loads(PUBLIC.read_text())
    assert [s["key"] for s in d["seeds"]] == [s.key for s in T.SEEDS]
    assert d["gens"] == list(range(T.GENERATIONS + 1))
    assert len(d["chains"]) == len(T.SEEDS) * T.CHAINS
    for c in d["chains"]:
        assert c["seed"] in T.BY_KEY and 0 <= c["chain"] < T.CHAINS
        for k in ("d_proto", "d_start", "descriptions", "kind_word", "category_word", "labels"):
            assert len(c[k]) == T.GENERATIONS + 1, k
        assert c["d_start"][0] == 0 and all(isinstance(t, str) and t for t in c["descriptions"])
        assert "word_runs" not in c
    for name in ("d_proto", "d_start", "between", "within", "kind_word", "category_word", "label_kind"):
        cv = d["curves"][name]
        assert len(cv["mean"]) == len(cv["ci95"]) == T.GENERATIONS + 1
    for t in ("P1_drift_to_form", "P1_specificity", "P2_convergence", "P3_kind_first"):
        assert isinstance(d["tests"][t]["supported"], bool)
    assert set(d["sprites"]) == {f"{s.key}_c{c}" for s in T.SEEDS for c in range(T.CHAINS)}
    assert d["cost"]["total_usd"] <= T.BUDGET_USD
    text = PUBLIC.read_text()
    for field in ('"cls"', '"patch_mean"', "base64", '"files"'):
        assert field not in text  # no embeddings, pictures or file lists


@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_telephone.json not written yet")
def test_page_and_api_render_and_quote_only_the_passages_file():
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_telephone_routes as R

    R._cache.clear()
    c = TestClient(web.app)
    r = c.get("/plato/telephone")
    assert r.status_code == 200 and "Plato’s Telephone" in r.text and 'id="gen"' in r.text and 'id="rows"' in r.text
    assert "{{BRAND}}" not in r.text and "site-head" in r.text
    d = c.get("/api/plato/telephone").json()
    assert len(d["chains"]) == 30 and d["passages"]
    file = {p["id"]: p for p in json.loads(R.PASSAGE_FILE.read_text())["passages"]}
    assert [p["id"] for p in d["passages"]] == R.PASSAGES
    assert all(p["text"] == file[p["id"]]["text"] for p in d["passages"])  # word for word from the verified file
    for path in ["/static/js/plato_telephone.js", "/static/css/plato_telephone.css", *d["sprites"].values()]:
        assert c.get(path).status_code == 200, path


def test_api_reports_missing_data(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_telephone_routes as R

    monkeypatch.setattr(R, "DATA", tmp_path / "missing.json")
    R._cache.clear()
    assert TestClient(web.app).get("/api/plato/telephone").status_code == 503


def test_page_static_files_stay_small():
    from metalesionlab.web import app as web

    imgs = list((web.HERE / "static" / "img" / "plato_telephone").glob("*"))
    files = [web.HERE / "static" / "js" / "plato_telephone.js", web.HERE / "static" / "css" / "plato_telephone.css", *imgs]
    assert sum(f.stat().st_size for f in files if f.exists()) < 1.5 * 1024 * 1024
    assert all(f.suffix == ".webp" for f in imgs)

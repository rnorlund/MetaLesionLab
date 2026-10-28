"""Second language (/lab/bilingual): the route, the shipped data and scripts/bilingual_web_export.py on a
small made-up results file (no runs/ needed)."""
import importlib.util
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web
from metalesionlab.web import bilingual_routes

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bilingual_web_export.py"
spec = importlib.util.spec_from_file_location("bilingual_web_export", SCRIPT)
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)

LANGS = ("es", "fr", "pt")
VARIANTS = ("en",) + LANGS + ("es_xen",)
WORDS = ["cat", "umbrella", "pineapple"]
NAMES = {"cat": {"en": ["cat"], "es": ["gato"], "fr": ["chat"], "pt": ["gato"]},
         "umbrella": {"en": ["umbrella"], "es": ["paraguas"], "fr": ["parapluie"], "pt": ["guarda-chuva"]},
         "pineapple": {"en": ["pineapple"], "es": ["piña"], "fr": ["ananas"], "pt": ["abacaxi"]}}
N_LAYERS = 52
LANG_OF = {"en": "en", "es": "es", "fr": "fr", "pt": "pt", "es_xen": "es"}


def _curve(peak_at: int, height: float) -> list[float]:
    return [round(height if i == peak_at else 0.0, 4) for i in range(N_LAYERS)]


def _run(cond, family, dose, seed, v, correct: set[str], english: set[str] = frozenset()):
    items = []
    for w in WORDS:
        target = NAMES[w][LANG_OF[v]][0]
        said = target if w in correct else (w.capitalize() if w in english else "xx")
        items.append({"en": w, "target": target, "said": said, "code": "Correct" if w in correct else "Nonword",
                      "switch": w in english, "wrong_name": w in english, "mixed": False})
    return {"condition": cond, "family": family, "dose": dose, "seed": seed, "variant": v, "n": len(WORDS),
            "correct": len(correct), "switch_n": len(english), "wrong_name_n": len(english), "items": items}


def fake_results() -> dict:
    conds = [("intact", "intact", None, [0], None), ("layers 0-7 noise x1", "layers 0-7", 1.0, [0, 1], "decoder noise"),
             ("naming_en mlp mean f0.2 random0", "random mlp mean", 0.2, [0], "unit ablation or pruning"),
             ("naming_en mlp mean f0.2 random1", "random mlp mean", 0.2, [0], "unit ablation or pruning")]
    runs, conditions = [], []
    for name, fam, dose, seeds, group in conds:
        by_variant = {}
        for v in VARIANTS:
            if name == "intact":
                ok, eng = set(WORDS), set()
            elif v == "en":
                ok, eng = {"cat", "umbrella"}, set()
            else:
                ok, eng = {"cat"}, {"umbrella"}
            for seed in seeds:
                runs.append(_run(name, fam, dose, seed, v, ok, eng))
            acc = len(ok) / len(WORDS)
            by_variant[v] = {"accuracy": acc, "accuracy_ci95": [max(0, acc - 0.2), min(1, acc + 0.1)]}
            if v != "en" and name != "intact":
                by_variant[v]["drop_minus_en"] = {"diff": 0.3333, "ci95": [0.1, 0.5]}
        conditions.append({"condition": name, "family": fam, "group": group, "dose": dose, "seeds": seeds, "by_variant": by_variant})
    mc = {"mean": 0.3, "ci95": [0.2, 0.4], "n_items": 3, "n_conditions": 3}
    lens = {}
    for v in LANGS:
        top_en = [0.0] * N_LAYERS
        top_l = [0.0] * N_LAYERS
        for i in range(38, 46):
            top_en[i] = 0.9
        for i in range(47, N_LAYERS):
            top_l[i] = 1.0
        lens[v] = {"items": ["umbrella", "pineapple"], "n_items": 2,
                   "intact": {"mean_p_other": _curve(40, 0.4), "mean_p_lang": _curve(51, 0.95), "frac_top1_other": top_en,
                              "frac_top1_lang": top_l, "peak_frac_top1_english": 0.9, "peak_frac_top1_english_layer": 40,
                              "peak_mean_p_english": 0.4, "peak_layer_english": 40, "final_mean_p_lang": 0.95},
                   "lesioned": {"share_trials_other_top1_any_layer": 0.5},
                   "intact_items": {w: {"said": NAMES[w][v][0], "english_top1_layers": list(range(38, 47)),
                                        "target_top1_layers": list(range(47, N_LAYERS)),
                                        "top1_by_layer": ["x"] * 38 + [w] * 9 + [NAMES[w][v][0][:2]] * 5}
                                    for w in ("umbrella", "pineapple")},
                   "intact_items_english_top1_any": 2}
    lens["reverse_en_trials_es_above_en"] = {"intact": {"frac_top1_lang": [0.0] * 39 + [1.0] * 13, "frac_top1_other": [0.0] * N_LAYERS}}
    return {
        "meta": {"model": "meta-models/Muse-Glimmer-30B", "precision": "FP8", "analyzed": "2026-10-26 21:32",
                 "pictures": WORDS, "n_pictures": len(WORDS), "n_main_conditions": 3, "names": NAMES},
        "intact": {v: {"accuracy": 1.0, "correct": 3} for v in VARIANTS},
        "common_correct": {v: list(WORDS) for v in VARIANTS if v != "en"},
        "primary": {v: {"diff": 0.3333, "ci95": [0.1, 0.5], "acc_en": 0.6667, "acc_lang": 0.3333, "n_items": 3, "n_conditions": 3,
                        "p_sign_flip": 0.25, "items_worse_in_lang": 1, "items_worse_in_en": 0} for v in VARIANTS if v != "en"},
        "by_family": {"layers 0-7": {v: {"diff": 0.3333, "ci95": [0.1, 0.5]} for v in VARIANTS if v != "en"}},
        "switching": {"lesioned": {v: {"english_answers": mc, "english_name": mc,
                                       "english_share_of_errors": {"share_of_errors": 0.5, "n_errors": 6, "ci95": [0.2, 0.8]}}
                                   for v in VARIANTS if v != "en"},
                      "reverse_on_english_trials": {"non_english_answers": {**mc, "mean": 0.01, "ci95": [0, 0.02]},
                                                    "item_name_in_other_language": {**mc, "mean": 0.0, "ci95": [0, 0]}}},
        "dose_response": {"layers 0-7": [], "random mlp mean": []},
        "conditions": conditions, "runs": runs, "lens": lens,
    }


def write_raw(folder: Path) -> None:
    for v in LANGS:
        items = [{"en": w, "lens": {"logp": {lang: [-20.0] * 40 + [-0.5] * 12 for lang in ("en", "es", "fr", "pt")}}}
                 for w in ("umbrella", "pineapple")]
        (folder / f"intact__{v}__s0.json").write_text(json.dumps({"items": items}))


def test_export_schema_from_a_small_results_file(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    write_raw(raw)
    d = export.build(fake_results(), raw)
    assert d["schema"] == export.SCHEMA and bilingual_routes.usable(d)
    assert d["source"]["n_pictures"] == 3 and d["source"]["trials_per_language"] == 4 * 3  # 4 lesioned runs (2 noise seeds, 2 random draws) x 3 pictures
    assert set(d["languages"]) == {"en", *LANGS} and d["languages"]["es"]["color"] == "#eb6834"
    for v in LANGS:
        s = d["summary"][v]
        assert s["ci95"][0] <= s["extra_drop"] <= s["ci95"][1]
        assert s["conditions"] == {"worse": 3, "tied": 0, "better": 0, "reliably_worse": 3, "reliably_better": 0}
        sw = d["switching"][v]
        assert sw["english_answers"]["mean"] == 0.3 and sw["counts"]["name_in_other_language"] == 4
        assert sw["examples"]["names"][0] == {"picture": "umbrella", "target": NAMES["umbrella"][v][0], "said": "Umbrella", "n": 4}
        L = d["lens"][v]
        assert L["english_majority_layer"] == 38 and L["target_majority_layer"] == 47 and L["n_layers"] == N_LAYERS
        assert [e["picture"] for e in L["examples"]] == ["pineapple", "umbrella"]  # preferred order, only testable pictures
        e = L["examples"][0]
        assert len(e["p_english"]) == len(e["p_target"]) == len(e["top1"]) == N_LAYERS and e["p_target"][-1] == pytest.approx(0.6065, abs=1e-4)
    assert "es_xen" in d["summary"] and "examples" not in d["switching"]["es_xen"]
    assert d["switching"]["reverse"]["counts"]["trials"] == 12
    assert d["lens"]["english_trials"] == {"english_majority_layer": 39, "max_share_spanish_top1": 0.0}
    fams = {f["key"]: f for f in d["dose"]}
    assert list(fams) == ["layers 0-7", "random mlp mean"]
    noise = fams["layers 0-7"]
    assert noise["label"] == "Layers 0–7 (first)" and noise["kind"] == "noise" and noise["extra_drop"]["es"]["diff"] == 0.3333
    assert [p["tick"] for p in noise["points"]] == ["none", "×1"] and noise["points"][1]["seeds"] == 2
    assert noise["points"][0]["acc"]["en"] == [1.0, 0.8, 1.0]
    rnd = fams["random mlp mean"]["points"][1]
    assert rnd["n_conditions"] == 2 and rnd["tick"] == "20%"
    m, lo, hi = rnd["acc"]["es"]
    assert m == pytest.approx(1 / 3, abs=1e-3) and lo <= m <= hi  # bootstrapped over pictures and the two random draws
    assert len(json.dumps(d).encode()) < export.MAX_BYTES


def test_export_without_raw_files_has_no_lens_examples():
    d = export.build(fake_results(), None)
    assert all(d["lens"][v]["examples"] == [] for v in LANGS) and d["lens"]["es"]["mean_p"]["english"][40] == 0.4


def test_export_main_writes_compact_json(tmp_path, monkeypatch):
    folder = tmp_path / "bilingual"
    (folder / "raw").mkdir(parents=True)
    write_raw(folder / "raw")
    (folder / "results.json").write_text(json.dumps(fake_results()))
    out = tmp_path / "web" / "bilingual.json"
    monkeypatch.setattr("sys.argv", ["bilingual_web_export.py", "--dir", str(folder), "--out", str(out)])
    export.main()
    text = out.read_text()
    assert text.endswith("\n") and "\n" not in text[:-1] and json.loads(text)["summary"]["es"]["n_items"] == 3


@pytest.fixture
def client():
    bilingual_routes._cache.clear()
    return TestClient(web.app_for("lingua"))


def test_page_and_shipped_data(client):
    r = client.get("/lab/bilingual")
    assert r.status_code == 200 and "Does damage hurt a second language first?" in r.text
    for el in ('id="lang-seg"', 'id="drop-chart"', 'id="dose-chart"', 'id="switch-big"', 'id="lens-chart"', 'id="means"', 'id="doesnt"'):
        assert el in r.text
    for page in ("/lab", "/lab/cut"):
        assert 'href="/lab/bilingual"' in client.get(page).text
    d = client.get("/api/lab/bilingual").json()
    assert d["schema"] == export.SCHEMA and d["source"]["n_pictures"] >= 20
    for v in LANGS:
        s = d["summary"][v]
        assert s["extra_drop"] == pytest.approx(s["acc_en"] - s["acc_lang"], abs=0.002)  # both start at 100% on these pictures
        assert 0 < s["ci95"][0] <= s["extra_drop"] <= s["ci95"][1]
        assert d["switching"][v]["english_answers"]["mean"] > 5 * d["switching"]["reverse"]["other_language_answers"]["mean"]
        L = d["lens"][v]
        assert L["english_majority_layer"] < L["target_majority_layer"] < L["n_layers"]
        assert L["examples"], v
    assert (bilingual_routes.SHIPPED).stat().st_size <= export.MAX_BYTES


def test_route_says_when_results_are_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr(bilingual_routes, "SHIPPED", tmp_path / "nothing.json")
    assert client.get("/api/lab/bilingual").status_code == 503
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"summary": {}}))
    monkeypatch.setattr(bilingual_routes, "SHIPPED", bad)
    assert client.get("/api/lab/bilingual").status_code == 503


def test_public_wording():
    """No clinical labels about people on the page, the teaser or the tour step."""
    here = web.HERE
    text = " ".join([(here / "pages" / "bilingual.html").read_text(), (here / "static" / "js" / "bilingual.js").read_text()])
    banned = r"\b(diagnos\w*|impaired|impairment|screen(ing)?|risk\w*|abnormal|normal|healthy)\b"
    assert not re.findall(banned, text, flags=re.I)
    assert "Not a medical test" in text and "not of people" in text

"""Plato's Chair (/plato) and What can I cut? (/lab/cut): offline, from the data shipped with the app."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from metalesionlab import plato_web
from metalesionlab.web import app as web
from metalesionlab.web import cut_routes, plato_routes

DATA = web.HERE / "data"
IMG = web.HERE / "static" / "img" / "plato"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "DATA_DIR", tmp_path)
    monkeypatch.setattr(plato_routes, "PLATO_DIR", tmp_path / "no-plato-folder")
    plato_routes._cache.clear()
    cut_routes._cache.clear()
    return TestClient(web.app), tmp_path


def test_pages_render(client):
    c, _ = client
    r = c.get("/plato")
    assert r.status_code == 200 and "Plato’s Chair" in r.text and 'id="who-seg"' in r.text
    r = c.get("/lab/cut")
    assert r.status_code == 200 and "What can I cut?" in r.text and 'id="tol"' in r.text


def test_plato_data_is_statistics_with_credits(client):
    c, _ = client
    d = c.get("/api/plato").json()
    assert d["core"]["n_concepts"] == 35 and d["core"]["below_1"] == 34
    chair = next(h for h in d["hero"] if h["key"] == "chair")
    assert round(1 - chair["index"], 2) == 0.63  # "63% less varied"
    assert [h["key"] for h in d["hero"]] == ["chair", "boat", "face", "person"]
    assert "CC BY 4.0" in d["credits"]["human_drawings"] and "outside this repository" in d["data_folder"]
    assert d["inside"]["bench"]["top"][d["inside"]["bench"]["layers"].index(40)] == "bench"
    assert d["inside"]["bench"]["said"] == "Table"
    assert all(abs(r["rho"]) < 0.3 and r["ci95"][0] < 0 < r["ci95"][1] for r in d["inside"]["lesions"])  # the honest null


def test_shipped_figures_exist_and_are_small():
    d = json.loads((DATA / "plato.json").read_text())
    names = [h[k] for h in d["hero"] for k in ("ai_img", "people_img")] + list(d.get("figures", {}).values())
    page = (web.HERE / "pages" / "plato.html").read_text() + (web.HERE / "static" / "js" / "plato.js").read_text()
    names += re.findall(r"plato/([\w.]+\.webp)", page)
    for name in set(names):
        assert (IMG / name).is_file(), name
    for f in IMG.iterdir():
        assert f.suffix == ".webp" and f.stat().st_size <= 300 * 1024, f.name
    assert (DATA / "plato.json").stat().st_size <= 200 * 1024
    assert (DATA / "cut_glimmer.json").stat().st_size <= 200 * 1024


def test_second_model_card_falls_back_to_in_progress(client, monkeypatch, tmp_path):
    c, _ = client
    shipped = json.loads((DATA / "plato.json").read_text())
    shipped["sdxl"] = None
    path = tmp_path / "plato.json"
    path.write_text(json.dumps(shipped))
    monkeypatch.setattr(plato_routes, "DATA", path)
    assert c.get("/api/plato").json()["sdxl"] is None  # the page shows "in progress"


def test_second_model_card_reads_the_data_folder(client, monkeypatch, tmp_path):
    c, _ = client
    folder = tmp_path / "core"
    folder.mkdir()
    monkeypatch.setattr(plato_routes, "PLATO_DIR", folder)
    sdxl = {"image_models": {"sdxl": "stabilityai/stable-diffusion-xl-base-1.0"},
            "summary": {"n_concepts": 8, "sdxl_vs_human": {"median_index": 1.25, "concepts_with_index_above_1": ["chair"]},
                        "muse_vs_sdxl": {"concepts_muse_more_uniform": 8, "median_muse_over_sdxl": 0.31},
                        "partial_rank_correlation_sdxl_vs_muse_given_human": {"rho": -0.5, "ci95": [float("nan"), float("nan")]}},
            "concepts": [{"label": "chair", "sdxl_index": 1.17, "muse_index": 0.37, "sdxl_spread": float("nan")}]}
    (folder / "results_sdxl.json").write_text(json.dumps(sdxl))  # Python writes NaN, which browsers can't parse
    r = c.get("/api/plato")
    assert r.status_code == 200 and "NaN" not in r.text
    s = r.json()["sdxl"]
    assert s["source"] == "data folder" and s["n_concepts"] == 8 and not s["complete"] and s["concepts"][0]["sdxl_spread"] is None
    # SDXL fields nested in the core results are read too
    (folder / "results_sdxl.json").unlink()
    (folder / "results.json").write_text(json.dumps({"summary": {"n_concepts": 35}, "sdxl": sdxl}))
    plato_routes._cache.clear()
    assert c.get("/api/plato").json()["sdxl"]["n_concepts"] == 8


def test_sdxl_block_ignores_results_without_a_comparison():
    assert plato_web.sdxl_block(None) is None
    assert plato_web.sdxl_block({"summary": {"n_concepts": 35}}) is None


def test_cut_results_come_from_the_shipped_copy(client):
    c, _ = client
    d = c.get("/api/lab/cut").json()
    assert d["source"] == "shipped" and len(d["layers"]) == 52 and d["intact"]["layers"] == 52
    steps = d["greedy"]
    # Your tests stop after layers 27 and 30; a perplexity-only guard would allow 5 layers.
    safe = max(i for i, s in enumerate(steps) if all(t["confirmed"] for t in steps[:i + 1]))
    assert sorted(steps[safe]["removed"]) == [27, 30]
    ppl_only = max(i for i, s in enumerate(steps) if all(t["ppl_ok"] for t in steps[:i + 1]))
    assert ppl_only == 5
    real = {p["name"]: p for p in d["pruned"]}
    assert real["confirmed"]["check"]["same_answers_all_pictures"] and real["confirmed"]["check"]["max_abs_logit_diff"] == 0
    assert any(x["word"] == "paraguas" and x["said"] == "Umbrella" for x in d["answers_lost"]["perplexity_only"])
    assert d["layers"][0]["skip_d_acc"] < -0.3  # layer 0 is critical


def test_cut_prefers_the_run_folder(client):
    c, root = client
    shipped = json.loads((DATA / "cut_glimmer.json").read_text())
    run = {k: v for k, v in shipped.items() if k != "answers_lost"}
    (root / "compress").mkdir()
    (root / "compress" / "glimmer.json").write_text(json.dumps(run))
    d = c.get("/api/lab/cut").json()
    assert d["source"] == "run" and d["answers_lost"] == shipped["answers_lost"]


def test_navigation_and_landing_link_the_new_pages():
    pages = web.HERE / "pages"
    for name in ("challenge.html", "lab.html", "studio.html", "scorer.html", "assess.html", "cut.html", "plato.html", "index.html"):
        assert 'href="/plato"' in (pages / name).read_text(), name
    assert 'href="/lab/cut"' in (pages / "lab.html").read_text()
    landing = (pages / "index.html").read_text()
    assert 'href="/lab/cut"' in landing and "plato-teaser" in landing


def test_tour_has_a_plato_step_and_stays_short():
    tour = (web.HERE / "static" / "js" / "tour.js").read_text()
    assert "page: '/plato'" in tour
    assert tour.count("{ page:") <= 13


def test_variety_section_is_shipped(client):
    c, _ = client
    assert 'id="variety"' in c.get("/plato").text
    v = c.get("/api/plato").json()["variety"]
    cond = v["conditions"]
    # "any kind" leaves Muse Image's spread where it was; one doodle of each named kind beats people's
    assert cond["any"]["median_ratio"] < 0.6 and cond["listed"]["median_ratio"] > 1
    assert cond["unusual"]["n"] == 10 and cond["listed"]["recognised"] < cond["default"]["recognised"]
    k = v["kinds"]
    assert k["n_pictures"] == 460 and k["chance"] < k["accuracy"] and k["reliable"] >= 10
    assert k["summary"]["default"]["mean_simpson"] < k["summary"]["people"]["mean_simpson"] < k["summary"]["listed"]["mean_simpson"]
    assert v["focus"]["chair"]["kinds"]["people"]["prototype"] == "a plain, ordinary chair"


def test_variety_block_needs_a_default_and_one_more_prompt():
    assert plato_web.variety_block(None) is None
    vis = {"n_concepts": 35, "median_ratio_vs_people": 0.49, "concepts_above_people": 1,
           "nearest_own_human_centroid": 0.85}
    assert plato_web.variety_block({"visual": {"all": {"default": vis}}}) is None
    res = {"visual": {"all": {"default": vis, "unusual": None,
                              "any": {**vis, "median_ratio_vs_people": 1.2, "median_ratio_vs_default": 2.5}}},
           "concepts": [{"key": "chair", "label": "chair",
                         "default": {"spread": 0.13, "ratio_vs_people": 0.37, "human_spread": 0.36},
                         "any": {"spread": float("nan"), "ratio_vs_people": 1.5},
                         "kinds": {"people": {"simpson": 0.3, "prototype": "a plain, ordinary chair"}}}],
           "kinds": {"validation": {"n_pictures": 0}}}
    v = plato_web.variety_block(res)
    assert set(v["conditions"]) == {"default", "any"} and v["conditions"]["any"]["median_vs_default"] == 2.5
    assert v["concepts"] == [{"key": "chair", "label": "chair", "default": 0.37, "any": 1.5}]
    chair = v["focus"]["chair"]
    assert chair["people_spread"] == 0.36 and chair["spread"]["any"] is None  # NaN is cleaned for browsers
    assert chair["kinds"]["people"]["prototype"] == "a plain, ordinary chair"
    assert v["kinds"] is None  # no labeler validation yet

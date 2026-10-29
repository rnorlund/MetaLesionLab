"""Prisoners of the cave (docs/plato_cave_twins_plan.md): the twins, the tasks, the rubric's keyword check, the
blind sheets and their hash, the verdict rules and the public file's schema."""
import json
from pathlib import Path

import numpy as np
import pytest

from metalesionlab import plato_scale as ps
from metalesionlab import plato_twins as pt

ROOT = Path(__file__).resolve().parents[1]


# ---------- the design ----------

def test_twins_pair_up_by_size():
    assert set(pt.PAIRS) == {"7B", "32B"}
    for size, (text, vision) in pt.PAIRS.items():
        assert text.arm == "text" and vision.arm == "vision" and text.size == vision.size == size
        assert vision.hf.replace("-VL-", "-") == text.hf  # Qwen2.5-VL-7B-Instruct is Qwen2.5-7B-Instruct's twin
        assert text.fp8 == vision.fp8  # same precision within a pair


def test_every_twin_is_pinned_and_apache():
    for m in pt.MODELS:
        assert m.licence == "Apache-2.0"
        assert len(m.revision) == 40 and all(c in "0123456789abcdef" for c in m.revision)


def test_text_twins_reuse_the_scale_experiments_pins():
    for m in pt.MODELS:
        if m.scale_key:
            s = ps.BY_KEY[m.scale_key]
            assert (s.hf, s.revision, s.fp8) == (m.hf, m.revision, m.fp8)
            assert m.arm == "text"


def test_the_chair_request_is_the_scale_experiments():
    t = pt.TASKS["chair"]
    assert t.prompt == ps.PROMPT and t.svg and t.temps[0] == pt.PRIMARY_TEMP
    assert tuple(ps.TEMPS_B) == t.temps
    assert not pt.TASKS["describe"].svg
    assert "10 past 11" in pt.TASKS["clock"].prompt and "no text" not in pt.TASKS["clock"].prompt
    assert pt.N == 12 and pt.gen_seed(1.0) == ps.gen_seed(1.0)


# ---------- descriptions ----------

@pytest.mark.parametrize("text,want", [
    ("A chair has a flat seat held up by four legs and a backrest.", {"seat": 1, "legs": 1, "back": 1}),
    ("It is something you sit on, with a back to lean against.", {"seat": 1, "legs": 0, "back": 1}),
    ("A chair is a piece of furniture.", {"seat": 0, "legs": 0, "back": 0}),
    ("Four LEGS support it.", {"seat": 0, "legs": 1, "back": 0}),
    ("Its legacy is a backpack.", {"seat": 0, "legs": 0, "back": 0}),  # whole words only
])
def test_keyword_parts(text, want):
    assert pt.keyword_parts(text) == want
    assert pt.rubric_score(want) == sum(want.values())


def test_first_sentence():
    assert pt.first_sentence("A chair has a seat. It has legs.") == "A chair has a seat."
    assert pt.first_sentence("  A chair\nhas legs!  More.") == "A chair has legs!"
    assert pt.first_sentence("No full stop here") == "No full stop here"
    assert len(pt.first_sentence("x" * 500)) == 220


# ---------- blind sheets and the hash ----------

def test_blind_order_is_fixed_and_a_permutation():
    items = [(k, "describe", 1.0, i) for k in pt.BY_KEY for i in range(12)]
    a, b = pt.blind_order(items, "describe"), pt.blind_order(items, "describe")
    assert a == b and sorted(a) == sorted(items) and a != items
    assert pt.blind_order(items, "clock") != a  # each sheet has its own order
    ids = pt.sheet_ids(a, "D")
    assert list(ids)[:2] == ["D01", "D02"] and len(ids) == 48 and ids["D01"] == a[0]


def test_hash_ignores_key_order_but_not_values():
    c1 = {"D01": {"seat": 1, "legs": 1, "back": 0}, "D02": {"seat": 0, "legs": 1, "back": 1}}
    c2 = {"D02": {"back": 1, "legs": 1, "seat": 0}, "D01": {"back": 0, "seat": 1, "legs": 1}}
    assert pt.codes_hash(c1) == pt.codes_hash(c2) and len(pt.codes_hash(c1)) == 64
    c2["D01"]["back"] = 1
    assert pt.codes_hash(c1) != pt.codes_hash(c2)


def test_validate_codes():
    ok = {"C1": {"face": 1, "hands": 1, "time": "11:10"}}
    assert pt.validate_codes(ok, ["C1"], pt.CLOCK_CODE_KEYS, "clock") == []
    assert pt.validate_codes({"C1": {"face": 1, "hands": 2, "time": "11:10"}}, ["C1"], pt.CLOCK_CODE_KEYS, "clock")
    assert pt.validate_codes({"C1": {"face": 1, "hands": 1, "time": "noon"}}, ["C1"], pt.CLOCK_CODE_KEYS, "clock")
    assert pt.validate_codes(ok, ["C1", "C2"], pt.CLOCK_CODE_KEYS, "clock")
    assert pt.validate_codes({"D1": {"seat": 1}}, ["D1"], pt.DESC_CODE_KEYS, "describe")


def test_kappa():
    assert pt.cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1.0)
    assert pt.cohen_kappa([1, 1, 1], [1, 1, 1]) is None  # all one value: chance agreement is total
    assert pt.cohen_kappa([1, 0, 1, 0], [0, 1, 0, 1]) == pytest.approx(-1.0)


# ---------- verdicts ----------

def test_boot_diff_and_verdicts():
    text, vision = np.zeros(12), np.r_[np.ones(6), np.zeros(6)]
    d = pt.boot_diff(text, vision)
    lo, hi = pt.pct_ci(d)
    assert 0 < lo < 0.5 < hi <= 1 and pt.size_verdict([lo, hi]) == "supported"
    assert pt.size_verdict(pt.pct_ci(pt.boot_diff(text, np.r_[1, np.zeros(11)]))) == "unclear"
    assert pt.size_verdict([-0.6, -0.1]) == "contradicted"
    assert pt.overall_verdict({"7B": "supported", "32B": "supported"}) == "supported"
    assert pt.overall_verdict({"7B": "supported", "32B": "unclear"}) == "partly supported"
    assert pt.overall_verdict({"7B": "supported", "32B": "contradicted"}) == "contradicted"
    assert pt.overall_verdict({"7B": "unclear", "32B": "unclear"}) == "unclear"


def test_describe_verdict():
    assert pt.describe_verdict(2.9, 2.8, [-0.3, 0.2]) == "supported"
    assert pt.describe_verdict(2.9, 2.0, [-1.2, -0.5]) == "unclear"
    assert pt.describe_verdict(1.5, 2.8, [0.9, 1.6]) == "not supported"


# ---------- the public file ----------

def test_validate_public_rejects_per_sample_data():
    good = {k: [] for k in pt.PUBLIC_KEYS}
    assert pt.validate_public(good) == []
    bad = {**good, "rows": [{"key": "x", "task": "chair", "svg": "<svg></svg>"}]}
    errs = pt.validate_public(bad)
    assert any("svg" in e for e in errs) and any("lacks" in e for e in errs)
    assert pt.validate_public({**good, "about": float("nan")})


def test_public_file_if_written():
    p = ROOT / "public_data" / "plato_twins.json"
    if not p.exists():
        pytest.skip("public_data/plato_twins.json not written yet")
    d = json.loads(p.read_text())
    assert pt.validate_public(d) == []
    assert {q["key"] for q in d["quotes"]} == set(pt.BY_KEY)


# ---------- the section (/plato/scale#twins) and the link from /plato/cave ----------

PUBLIC = ROOT / "public_data" / "plato_twins.json"


@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_twins.json not written yet")
def test_section_and_api_render():
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_twins_routes as R

    R._cache.clear()
    c = TestClient(web.app_for("plato"))
    page = c.get("/plato/scale").text
    assert 'id="twins"' in page and 'id="twins-body"' in page and "Prisoners of the cave" in page
    assert "/static/js/plato_twins.js" in page and "/static/css/plato_twins.css" in page
    d = c.get("/api/plato/twins").json()
    assert {"rows", "pairs", "predictions", "quotes", "wall"} <= set(d)
    assert set(d["predictions"]) == {"P1", "P2"}
    for task in ("chair", "clock"):
        rows = d["wall"]["walls"][task]
        assert [(r["size"], r["arm"]) for r in rows] == [("7B", "text"), ("7B", "vision"), ("32B", "text"), ("32B", "vision")]
        assert all(len(r["tiles"]) == pt.N and len(r["read"]) == pt.N for r in rows)
    for path in ["/static/js/plato_twins.js", "/static/css/plato_twins.css", "/static/img/plato_twins/wall_chair.webp",
                 "/static/img/plato_twins/wall_clock.webp"]:
        assert c.get(path).status_code == 200, path


def test_api_reports_missing_data(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_twins_routes as R

    monkeypatch.setattr(R, "DATA", tmp_path / "missing.json")
    R._cache.clear()
    assert TestClient(web.app_for("plato")).get("/api/plato/twins").status_code == 503
    R._cache.clear()


def test_cave_page_links_to_the_twins():
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web

    page = TestClient(web.app_for("plato")).get("/plato/cave").text
    assert 'href="/plato/scale#twins"' in page and "models that only read vs models that have seen pictures" in page


def test_registered_in_the_plato_site_only():
    from metalesionlab.web import app as web

    assert web.SITE_ROUTERS["plato"].count("plato_twins_routes") == 1
    assert "plato_twins_routes" not in web.SITE_ROUTERS["lingua"]


def test_section_files_stay_small():
    from metalesionlab.web import app as web

    imgs = list((web.HERE / "static" / "img" / "plato_twins").glob("*"))
    files = [web.HERE / "static" / "js" / "plato_twins.js", web.HERE / "static" / "css" / "plato_twins.css", *imgs]
    assert sum(f.stat().st_size for f in files if f.exists()) < 400 * 1024
    assert all(f.suffix in (".webp", ".json") for f in imgs)

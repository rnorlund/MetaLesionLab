"""An AI growing up (docs/plato_scale_plan.md): SVG extraction, rendering and failure counting, the design, and the
public file's schema."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from metalesionlab import plato_scale as ps

ROOT = Path(__file__).resolve().parents[1]
CHAIR = ('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">'
         '<path d="M80 40 V200 M80 130 H170 V200 M170 130 V60" stroke="black" stroke-width="4" fill="none"/></svg>')


# ---------- extraction ----------

def test_extract_from_fenced_answer_with_prose():
    text = f"Here is a chair:\n```xml\n{CHAIR}\n```\nEnjoy!"
    assert ps.extract_svg(text) == CHAIR


def test_extract_first_of_two_and_case_insensitive():
    two = "<SVG width='1' height='1'><rect/></SVG> then <svg><circle/></svg>"
    assert ps.extract_svg(two) == "<SVG width='1' height='1'><rect/></SVG>"


@pytest.mark.parametrize("text", [None, "", "no drawing here", "<svg width='256'><line x1='0'", "<chair></chair>"])
def test_extract_none_without_a_complete_svg(text):
    assert ps.extract_svg(text) is None


def test_namespace_added_only_when_missing():
    assert ps._ensure_namespace("<svg width='2'></svg>").startswith('<svg xmlns="http://www.w3.org/2000/svg" width')
    assert ps._ensure_namespace(CHAIR) == CHAIR


# ---------- rendering ----------

def test_render_is_square_gray_and_keeps_aspect():
    wide = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
            '<rect x="0" y="0" width="100" height="50" fill="black"/></svg>')
    img = ps.render_svg(wide)
    a = np.asarray(img)
    assert img.size == (256, 256) and img.mode == "L"
    # 100 x 50 scaled to 256 x 128, centred: ink rows 64..191 only
    rows = np.where((a < 200).any(1))[0]
    assert abs(rows.min() - 64) <= 1 and abs(rows.max() - 191) <= 1
    assert (a[:, :] < 200).any(0).all()  # full width


def test_render_without_size_and_without_namespace():
    img = ps.render_svg("<svg><line x1='0' y1='0' x2='300' y2='150' stroke='black' stroke-width='5'/></svg>")
    assert img.size == (256, 256) and ps.ink_fraction(img) > 0.005


def test_render_ignores_external_files(tmp_path):
    secret = tmp_path / "secret.png"
    from PIL import Image

    Image.new("RGB", (8, 8), "black").save(secret)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="256" '
           f'height="256"><image href="file://{secret}" width="256" height="256"/></svg>')
    assert ps.ink_fraction(ps.render_svg(svg)) == 0.0  # the local file is never loaded


def test_render_refuses_huge_svg():
    with pytest.raises(ValueError):
        ps.render_svg("<svg>" + " " * (ps.MAX_SVG_BYTES + 1) + "</svg>")


def test_touches_all_edges():
    framed = ('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect x="1" y="1" width="254" '
              'height="254" stroke="black" stroke-width="2" fill="none"/></svg>')
    assert ps.touches_all_edges(ps.render_svg(framed))
    assert not ps.touches_all_edges(ps.render_svg(CHAIR))


# ---------- classification and counting ----------

@pytest.mark.parametrize("text,reason", [
    (CHAIR, None),
    ("Sorry, I can't draw.", "no_svg"),
    ("<svg width='256' height='256'><path d='M0 0 L", "no_svg"),  # cut off at the token limit
    ('<svg width="256" height="256" a="1" a="2"></svg>', "render_error"),  # duplicate attribute: not XML
    ('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" '
     'fill="white"/></svg>', "blank"),
    ('<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" '
     'fill="black"/></svg>', "flooded"),
])
def test_classify(text, reason):
    c = ps.classify(text)
    assert c["reason"] == reason
    assert c["ok"] is (reason is None)
    if reason in (None, "blank", "flooded"):
        assert c["image"].size == (256, 256)


def test_failure_counts():
    fc = ps.failure_counts([None, "no_svg", "blank", None, "flooded", "render_error", "blank"])
    assert fc == {"no_svg": 1, "render_error": 1, "blank": 2, "flooded": 1, "n": 7, "failed": 5, "rendered": 2,
                  "rate": 5 / 7}
    assert ps.failure_counts([None] * 12)["rate"] == 0
    with pytest.raises(ValueError):
        ps.failure_counts(["oops"])


def test_wilson():
    lo, hi = ps.wilson(0, 12)
    assert lo == 0 and 0.24 < hi < 0.25
    lo, hi = ps.wilson(12, 12)
    assert 0.75 < lo < 0.76 and hi == 1
    lo, hi = ps.wilson(6, 12)
    assert math.isclose(lo + hi, 1.0, abs_tol=1e-9) and 0.25 < lo < 0.26
    assert all(math.isnan(v) for v in ps.wilson(0, 0))


# ---------- design ----------

def test_models_are_pinned_apache_and_sized():
    for m in ps.MODELS:
        if m.kind == "open":
            assert m.licence == "Apache-2.0" and len(m.revision) == 40 and m.params_b > 0
        else:
            assert math.isnan(m.params_b) and m.revision == ""  # API: size undisclosed, never guessed
    for fam in ps.FAMILIES:
        sizes = [m.params_b for m in ps.family_models(fam)]
        assert sizes == sorted(sizes) and len(sizes) >= 4
    assert {m.key for m in ps.MODELS if m.family == "Muse"} == {"glimmer", "spark", "wonder"}
    assert all("enable_thinking" in dict(m.chat_kwargs) for m in ps.family_models("Qwen3"))
    assert ps.gen_seed(1.0) == 20261128 and ps.gen_seed(0.7) == 20261098


def test_size_band():
    assert ps.size_band(0.494) == "<=2B" and ps.size_band(2.03) == "<=2B"
    assert ps.size_band(7.6) == "4-8B" and ps.size_band(4.02) == "4-8B"
    assert ps.size_band(13.7) == "13-15B" and ps.size_band(32.76) == "30-33B" and ps.size_band(29.78) == "30-33B"
    assert ps.size_band(float("nan")) is None and ps.size_band(70) is None


def test_nested_subsets():
    a = [set(ps.nested_subset(1, 20000, n)) for n in ps.SIZES]
    assert all(x < y for x, y in zip(a, a[1:]))  # strictly nested
    assert len(a[-1]) == 20000
    assert np.array_equal(ps.nested_subset(2, 20000, 100), ps.nested_subset(2, 20000, 100))
    assert not np.array_equal(ps.nested_subset(1, 20000, 100), ps.nested_subset(2, 20000, 100))
    with pytest.raises(ValueError):
        ps.nested_subset(1, 50, 100)


def test_best_checkpoint():
    assert ps.best_checkpoint({"0": 3.0, "100": 1.0, "200": 2.0}) == 100
    assert ps.best_checkpoint({"0": 3.0, "400": 1.0, "100": 1.0}) == 100  # tie: earliest
    assert ps.best_checkpoint({"0": float("nan"), "50": 2.0}) == 50
    with pytest.raises(ValueError):
        ps.best_checkpoint({"0": float("nan")})


@pytest.mark.parametrize("ci,sign,pred,out", [
    ([0.1, 0.3], 1, 1, "supported"), ([0.1, 0.3], -1, 1, "unclear"), ([-0.3, -0.1], 1, 1, "contradicted"),
    ([-0.1, 0.2], 1, 1, "unclear"), ([-0.3, -0.1], -1, -1, "supported"), ([0.1, 0.2], -1, -1, "contradicted"),
    ([float("nan"), float("nan")], 1, 1, "not testable"),
])
def test_verdict(ci, sign, pred, out):
    assert ps.verdict(ci, sign, pred) == out


def test_boot_mean():
    rng = np.random.default_rng(0)
    b = ps.boot_mean([1.0, 1.0, 1.0], 50, rng)
    assert b.shape == (50,) and np.all(b == 1)
    assert np.isnan(ps.boot_mean([], 5, rng)).all()


# ---------- the public file ----------

def _minimal():
    row_b = {k: 0.0 for k in ps.ARM_B_ROW} | {"key": "x", "label": "x", "family": "Qwen2.5", "kind": "open",
                                             "failures": {}, "failure_ci95": [0, 1], "spread_ci95": None}
    row_a = {k: 0.0 for k in ps.ARM_A_ROW}
    return {"about": "", "credits": [], "prompt": ps.PROMPT, "models": [], "skipped": ps.SKIPPED,
            "arm_b": {"rows": [row_b]}, "arm_a": {"rows": [row_a]}, "predictions": {}, "cost": {}}


def test_validate_public_accepts_statistics_only():
    assert ps.validate_public(_minimal()) == []


def test_validate_public_rejects_samples_nan_and_missing_keys():
    d = _minimal()
    d["arm_b"]["rows"][0]["note"] = "<svg><path/></svg>"
    d["arm_b"]["rows"][0]["spread"] = float("nan")
    d["arm_a"]["rows"][0]["drawings"] = [[1, 2]]
    del d["cost"]
    errs = " ".join(ps.validate_public(d))
    assert "SVG text" in errs and "NaN" in errs and "per-sample" in errs and "missing keys" in errs


def test_public_file_if_written():
    p = ROOT / "public_data" / "plato_scale.json"
    if not p.exists():
        pytest.skip("public_data/plato_scale.json not written yet")
    assert ps.validate_public(json.loads(p.read_text())) == []


# ---------- the page (/plato/scale) ----------

PUBLIC = ROOT / "public_data" / "plato_scale.json"


@pytest.mark.skipif(not PUBLIC.exists(), reason="public_data/plato_scale.json not written yet")
def test_page_and_api_render():
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_scale_routes as R

    R._cache.clear()
    c = TestClient(web.app_for("plato"))
    r = c.get("/plato/scale")
    assert r.status_code == 200 and "An AI growing up" in r.text and 'id="wall-models"' in r.text
    assert "{{BRAND}}" not in r.text and "<!--" not in r.text.split("<body", 1)[1]  # every placeholder filled
    d = c.get("/api/plato/scale").json()
    assert {"arm_a", "arm_b", "wall", "predictions"} <= set(d)
    keys = [m["key"] for m in d["wall"]["models"]]
    assert keys[-2:] == ["spark", "wonder"]  # the API models at the end
    assert all(m["params_b"] is None for m in d["wall"]["models"] if m["kind"] == "api")  # size undisclosed, never guessed
    assert all(len(m["tiles"]) == ps.N_B for m in d["wall"]["models"])
    for path in ["/static/js/plato_scale.js", "/static/css/plato_scale.css", "/static/img/plato_scale/wall_models.webp",
                 "/static/img/plato_scale/wall_data.webp"]:
        assert c.get(path).status_code == 200, path


def test_api_reports_missing_data(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from metalesionlab.web import app as web
    from metalesionlab.web import plato_scale_routes as R

    monkeypatch.setattr(R, "DATA", tmp_path / "missing.json")
    R._cache.clear()
    assert TestClient(web.app_for("plato")).get("/api/plato/scale").status_code == 503


def test_page_static_files_stay_small():
    from metalesionlab.web import app as web

    imgs = list((web.HERE / "static" / "img" / "plato_scale").glob("*"))
    files = [web.HERE / "static" / "js" / "plato_scale.js", web.HERE / "static" / "css" / "plato_scale.css", *imgs]
    assert sum(f.stat().st_size for f in files if f.exists()) < 1.5 * 1024 * 1024
    assert all(f.suffix in (".webp", ".json") for f in imgs)


def test_registered_in_the_plato_site_only():
    from metalesionlab.web import app as web
    from metalesionlab.web import site

    assert "plato_scale_routes" in web.SITE_ROUTERS["plato"]
    assert "plato_scale_routes" not in web.SITE_ROUTERS["lingua"]
    assert any(s["path"] == "/plato/scale" and s["slug"] == "scale" for s in site.SERIES)

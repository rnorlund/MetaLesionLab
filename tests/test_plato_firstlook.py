"""First look (static/js/plato_firstlook.js, static/css/plato_firstlook.css): the first screen of /plato/inside,
/plato/forms, /plato/atlas and /plato/scale. Each page leads with its question, one picture of its own material, a
one-sentence answer and at most three numbers drawn as small graphics. The graphics are rendered here under node
from the JSON each page's /api route returns, so a number on the page can't drift from the data. Offline."""
import html
import json
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web

JS = web.HERE / "static" / "js" / "plato_firstlook.js"
CSS = web.HERE / "static" / "css" / "plato_firstlook.css"
NODE = shutil.which("node")
PAGES = {"inside": "plato_inside.html", "forms": "plato_forms.html", "atlas": "plato_atlas.html", "scale": "plato_scale.html"}
needs_node = pytest.mark.skipif(not NODE, reason="node is not installed")


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app)


def lead(client, page: str, tmp_path) -> tuple[dict, dict, list[str]]:
    """The page's API data, FirstLook's {stats, note} for it (with "how": the "How we know" list FirstLook.how builds
    from it), and each stat's rendered <figure>."""
    data = client.get(f"/api/plato/{page}").json()
    src = tmp_path / f"{page}.json"
    src.write_text(json.dumps(data))
    code = (f"const F = require({json.dumps(str(JS))}); const d = JSON.parse(require('fs').readFileSync({json.dumps(str(src))}, 'utf8'));"
            f"const L = F[{json.dumps(page)}](d); console.log(JSON.stringify({{lead: L, how: F.how(L), html: L.stats.map(F.figure)}}));")
    run = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    out["lead"]["how"] = out["how"]
    return data, out["lead"], out["html"]


def num(fig: str) -> str:
    return "".join(re.findall(r'<span class="sv-(?:num|unit)">([^<]*)</span>', fig))


def plain(h: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def words(s: str) -> int:
    return len(re.findall(r"[A-Za-z][\w’'-]*", s))


def check_common(out: dict, figs: list[str]):
    assert 1 <= len(out["stats"]) <= 3  # at most three headline numbers
    how = plain(out["how"])
    for spec, fig in zip(out["stats"], figs):
        assert re.search(r'<svg[^>]+role="img" aria-label="[^"]+"|class="sv-(?:bars|pair)" role="img" aria-label="[^"]+"', fig), spec["kind"]
        assert '<p class="sv-cap">' in fig and "ERROR" not in fig
        # the first screen is short: a label of at most ten words under the number, and at most one verdict after it
        cap = plain(re.search(r'<p class="sv-cap">(.*?)</p>', fig, re.S).group(1))
        assert words(cap) <= 10, cap
        if spec.get("verdict"):
            assert re.search(r'<figcaption class="fl-q"><span class="fl-verdict (yes|no|part)">[^<]{1,24}</span></figcaption>', fig), fig
        else:
            assert "fl-q" not in fig
        # every qualifier is kept, in the "How we know" disclosure under the numbers
        assert spec["q"] and spec["q"] in how, spec["q"]
    assert out["note"] and out["note"] in how


# --- each page's numbers, from its data ---------------------------------------------------------------------

@needs_node
def test_inside_numbers_render_from_the_data(client, tmp_path):
    d, out, figs = lead(client, "inside", tmp_path)
    check_common(out, figs)
    sm, ms = d["summary"], d["summary"]["mean_spread"]
    at, lo, hi = int(sm["median_collapse_layer"]), sm["earliest_collapse"], sm["latest_collapse"]
    layers, spread, dots = figs
    # 52 segments, filled from the median collapse layer to the last, the range as a band, a marker
    assert layers.count('class="sv-on sv-blue"') == 52 - at + 1 and layers.count('class="sv-off-fill"') == at - 1
    assert 'class="fl-band"' in layers and f">{lo}–{hi}</span>" in layers and 'class="sv-mark"' in layers
    assert num(layers) == f"{at}of 52 stages"  # "stage", the plain word for a layer
    # people's doodles against Muse's at the last layer: two clusters and the rounded ratio
    ratio = ms["people"][-1] / ms["muse"][-1]
    assert num(spread) == f"{round(ratio)}×" and f"Muse Image <b>{ms['muse'][-1]:.2f}</b>" in spread
    assert f"People <b>{ms['people'][-1]:.2f}</b>" in spread
    # things that collapse at or before the name: one filled dot each
    assert dots.count("sv-on sv-blue") == sm["collapse_at_or_before_name"]
    assert dots.count('class="sv-off"') == sm["n_with_both"] - sm["collapse_at_or_before_name"]
    assert "never filed in one place" in out["stats"][0]["q"] and "chose after seeing the data" in out["note"]


@needs_node
def test_forms_numbers_render_from_the_data(client, tmp_path):
    d, out, figs = lead(client, "forms", tmp_path)
    check_common(out, figs)
    g, eye = d["clock"]["groups"], d["clock"]["byeye_no_time"]["muse_doodle_default"]
    muse, people, asked = figs
    assert muse.count("sv-on sv-blue") == eye["sure"] and muse.count('class="sv-off"') == eye["n"] - eye["sure"]
    assert num(muse) == f"{eye['sure']} of {eye['n']}"
    assert people.count("sv-on sv-orange") == g["people"]["ten_ten"]["k"] and people.count("<circle") == g["people"]["n"]
    assert num(people) == f"{round(g['people']['ten_ten']['share'] * 100)}%"
    a = g["muse_doodle_asked"]
    assert asked.count("sv-on sv-blue") == a["ten_ten"]["k"] and asked.count("<circle") == a["n"]
    assert f"counted {g['muse_doodle_default']['ten_ten']['k']}" in out["stats"][0]["q"]  # the reader's count stays beside the eye's
    assert f"{round(d['clock']['chance_ten_ten'] * 1000) / 10}% would count" in out["stats"][1]["q"]


@needs_node
def test_atlas_numbers_render_from_the_data(client, tmp_path):
    d, out, figs = lead(client, "atlas", tmp_path)
    check_common(out, figs)
    a, new, sdxl = d["summary"]["all"], d["summary"]["new"], d["summary"]["sdxl"]["all"]
    below, bars, test = figs
    assert below.count("sv-on sv-blue") == a["below_1"] and below.count("<circle") == d["summary"]["n_concepts"]
    assert re.findall(r'style="width:([\d.]+)%', bars) == [str(round(a["median"] * 100, 1)), "100"]
    assert num(bars) == f"{round(a['median'] * 100)}%"
    assert test.count("sv-on sv-blue") == new["below_1"] and test.count("<circle") == new["n"]
    assert f"{sdxl['median']:.2f}" in out["note"] and f"{sdxl['below_1']} of {sdxl['n']}" in out["note"]  # SDXL's numbers kept


@needs_node
def test_scale_numbers_render_from_the_data(client, tmp_path):
    d, out, figs = lead(client, "scale", tmp_path)
    check_common(out, figs)
    wall = {m["key"]: m for m in d["wall"]["models"]}
    small, big = wall["qwen25_0.5b"], wall["qwen25_32b"]
    fails, ratio, bars = figs
    assert num(fails) == f"{small['failed']} → {big['failed']}failures in 12"
    assert fails.count("sv-on sv-muted") == small["failed"] + big["failed"] and fails.count("<rect") == 24
    wonder = next(r for r in d["arm_b"]["rows"] if r["key"] == "wonder" and r["temp"] == 1)
    assert num(ratio) == f"{wonder['spread_ratio']:.2f}×as varied as people’s" and 'class="fl-rs-people"' in ratio
    assert ratio.count('class="sv-on sv-muted"') == 3 and 'class="fl-rs-ring"' in ratio  # the three 32B open models, Muse Image's mark
    final = sorted((r for r in d["arm_a"]["rows"] if r["temp"] == 1 and r["checkpoint"] == "final"), key=lambda r: r["size"])
    assert num(bars) == f"{round(final[0]['recog']['mean'] * 100)}% → {round(final[-1]['recog']['mean'] * 100)}%"
    p3 = d["predictions"]["P3"]["model_size"]
    lo, hi = round(-p3["ci95"][1] * 12), round(-p3["ci95"][0] * 12)
    assert f"{round(-p3['contrast'] * 12)} fewer failures in 12 (probably between {lo} and {hi} fewer)" in out["stats"][0]["q"]
    # each planned prediction's verdict, as it came out, in the chip beside it
    assert p3["primary"] == "supported" and '<span class="fl-verdict yes">As predicted</span>' in fails
    assert d["predictions"]["P2"]["model_size"]["primary"] == "unclear" and '<span class="fl-verdict part">Unclear</span>' in ratio
    assert "Too close to call" in out["stats"][1]["q"]  # no convergence with size
    p1 = d["predictions"]["P1"]["data_size"]
    assert p1["primary"] == "supported" and '<span class="fl-verdict yes">As predicted</span>' in bars
    assert f"up {round(p1['contrast'] * 100)} points" in out["stats"][2]["q"]


# --- the pages ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("page", PAGES)
def test_first_screen_leads_with_question_picture_answer_numbers(client, page):
    html = (web.HERE / "pages" / PAGES[page]).read_text()
    hero = re.search(r'<section class="fl [^"]*"[^>]*>(.*?)</section>', html, re.S).group(1)
    assert "What would Plato ask an AI?" in hero and 'class="kicker-q"' in hero and "<h1" in hero
    for part in ('class="fl-answer"', 'class="fl-visual', 'class="fl-stats"', 'class="fl-note"'):
        assert part in hero, (page, part)
    answer = re.search(r'<p class="fl-answer"[^>]*>(.*?)</p>', hero, re.S).group(1)
    assert len(re.findall(r"[.?!](?:\s|$)", answer)) == 1  # one sentence
    for ref in ("/static/css/statviz.css", "/static/css/plato_firstlook.css", "/static/js/statviz.js", "/static/js/plato_firstlook.js"):
        assert ref in html, (page, ref)
    assert html.index("statviz.js") < html.index("plato_firstlook.js") < html.index(f"/static/js/plato_{page}.js")
    r = client.get(f"/plato/{page}")
    assert r.status_code == 200 and 'class="fl-stats"' in r.text


def test_inside_picture_is_the_chair_at_three_layers():
    script = (web.HERE / "static" / "js" / "plato_inside.js").read_text()
    assert "var TRIP = [1, 26, 52];" in script and "x.key === 'chair'" in script
    assert "prefers-reduced-motion" in script  # the triptych is still; the explorer keeps its motion rule


def test_scale_picture_rows_are_real_models():
    script = (web.HERE / "static" / "js" / "plato_scale.js").read_text()
    wall = json.loads((web.HERE / "static" / "img" / "plato_scale" / "wall.json").read_text())
    keys = {m["key"] for m in wall["models"]}
    rows = re.findall(r"\['([\w.]+)'", re.search(r"var LEAD = (\[.*?\]);", script).group(1))
    assert rows and set(rows) <= keys


def test_first_look_uses_colour_tokens_only():
    css = CSS.read_text()
    hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", css)
    assert hexes == ["#fbfaf5", "#1f2328"]  # line art on paper: the only hex are the paper tokens' fallbacks
    assert "var(--paper, #fbfaf5)" in css and "var(--paper-ink, #1f2328)" in css
    assert not re.findall(r"\brgba?\(", css)
    script = JS.read_text()
    assert not re.findall(r"['\"]#[0-9a-fA-F]{3,8}['\"]", script)
    inside = (web.HERE / "static" / "css" / "plato_inside.css").read_text()
    trip = inside[inside.index("/* first look"):inside.index("/* explorer */")]  # the chair at three layers, on paper
    assert "var(--fl-paper)" in trip and not re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(", trip)


def test_epigraph_and_introduction_are_kept_below_the_numbers():
    css = CSS.read_text()
    assert '"stats stats" "note note" "quote ctx"' in css  # wide: the epigraph and the introduction after the numbers
    for page in ("plato_inside.html", "plato_forms.html", "plato_atlas.html"):
        html = (web.HERE / "pages" / page).read_text()
        assert html.count("<!--#epigraph:") == 1 and '<div class="fl-ctx">' in html

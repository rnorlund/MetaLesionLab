"""Take-homes (/takehomes): three panels, the God panel covered by default, numbers from the data files, the starred nav item.

Message 2 is Meta's open AI, Muse Glimmer: one chair at each of six steps of damage (least at the left), with the drawings
named and the descriptions right, pooled over a chair, a clock and God, all computed from data/plato_glimmer.json."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web

DATA = web.HERE / "data"
WEB_STATIC = web.HERE / "static"


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


def test_route_and_three_panels(client):
    r = client.get("/takehomes")
    assert r.status_code == 200
    assert len(re.findall(r'<section class="th-panel"', r.text)) == 3
    for h in ("Meta’s AI has one idea of a chair.", "Damage Meta’s open AI, and its drawings go before its words.",
              "Ask Meta’s AI to draw God."):
        assert h in r.text
    assert [m for m in re.findall(r'class="th-link" href="([^"]+)"', r.text)] == ["/plato", "/plato/glimmer", "/plato/ideas"]
    assert 'id="drawing-first"' in r.text and "words-first" not in r.text
    assert "rocking" not in r.text and "plato_damage" not in r.text  # the Stable Diffusion XL row is gone


def test_god_panel_is_covered_by_default(client):
    t = client.get("/takehomes").text
    assert 'id="god" data-state="covered"' in t
    assert "Draw yours first, then see Meta’s AI’s" in t and 'href="/draw?thing=god"' in t and "Show me now" in t
    assert re.search(r'id="god-grid" hidden', t)  # the drawings stay out of sight until revealed
    assert re.search(r'th-god-after" hidden>16 of 16: the same bearded man with long hair and a halo, as in Western religious art\.', t)
    js = (web.HERE / "static" / "js" / "takehomes.js").read_text()
    assert "tot-draw-seen" in js


def test_numbers_match_data(client):
    t = client.get("/takehomes").text
    chair = next(h for h in json.loads((DATA / "plato.json").read_text())["hero"] if h["key"] == "chair")
    god = next(i for i in json.loads((DATA / "plato_ideas.json").read_text())["ideas"] if i["key"] == "god")
    assert f'<b>{chair["ai_spread"]:.2f}</b>' in t and f'<b>{chair["human_spread"]:.2f}</b>' in t
    assert f'{god["top"]["n"]} of {god["n"]}' in t
    assert "{{" not in t


def test_nav_has_starred_takehomes_first_after_home(client):
    nav = re.search(r'<nav class="topnav" aria-label="Main">(.*?)<details', client.get("/takehomes").text, re.S).group(1)
    links = re.findall(r"<a ([^>]*)>(.*?)</a>", nav, re.S)
    labels = [re.sub(r"<[^>]+>|↗", "", b).strip() for _, b in links]
    assert labels[:3] == ["Home", "Take-homes", "Draw"]
    attrs, body = links[1]
    assert 'href="/takehomes"' in attrs and "nav-star" in attrs and "<svg" in body


def test_drawing_first_panel_numbers_come_from_the_data_and_run_left_to_right(client):
    t = client.get("/takehomes").text
    g = json.loads((DATA / "plato_glimmer.json").read_text())
    steps = g["damage"][0]["steps"]
    assert len(steps) == 6

    def pooled(cond, key):
        return sum(c[key] for c in g["conditions"][cond].values())
    n = sum(c["n"] for c in g["conditions"][steps[4]["cond"]].values())
    right, named = pooled("all@0.2", "correct"), pooled("all@0.2", "named")
    assert (right, named, n) == (21, 1, 36)  # the figures the message quotes, checked once against the data
    assert (f"With a fifth of its neurons switched off, {right} of its {n} descriptions were still right. "
            f"Only {named} of its {n} drawings could still be named.") in t
    sec = t[t.index('id="drawing-first"'):t.index('<!-- 3.')]
    assert "Muse Glimmer, Meta’s open AI. Left to right: more of its neurons switched off, from none to 30%." in sec
    cols = re.findall(r"<li>(.*?)</li>", sec, re.S)
    assert len(cols) == 6
    labels = ["undamaged", "5% off", "10% off", "15% off", "20% off", "30% off"]
    for i, (col, label, st) in enumerate(zip(cols, labels, steps)):
        assert f"/static/img/plato_glimmer/steps/chair_{i}.webp" in col and f'<span class="th-lbl">{label}</span>' in col
        assert f'<b>{pooled(st["cond"], "named")} of {n}</b>' in col and f'<b>{pooled(st["cond"], "correct")} of {n}</b>' in col
        assert (WEB_STATIC / "img" / "plato_glimmer" / "steps" / f"chair_{i}.webp").is_file()
    assert "god" not in sec.lower().replace("and god", "")  # no God picture; the fig line names God only as one of three things
    assert 'class="th-legend"' in sec and sec.index("th-legend") < sec.index('class="th-row"')


def test_takehomes_css_uses_tokens_only():
    css = (WEB_STATIC / "css" / "takehomes.css").read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css) and not re.search(r"font-size:\s*\d", css)

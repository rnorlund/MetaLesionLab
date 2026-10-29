"""Take-homes (/takehomes): three panels, the God panel covered by default, numbers from the data files, the starred nav item."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web

DATA = web.HERE / "data"


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


def test_route_and_three_panels(client):
    r = client.get("/takehomes")
    assert r.status_code == 200
    assert len(re.findall(r'<section class="th-panel"', r.text)) == 3
    for h in ("Meta’s AI has one idea of a chair.", "Damage the part of an AI that reads words, and it forgets what it’s drawing.",
              "Ask Meta’s AI to draw God."):
        assert h in r.text
    assert [m for m in re.findall(r'class="th-link" href="([^"]+)"', r.text)] == ["/plato", "/damaged", "/plato/ideas"]
    assert len(re.findall(r"/static/img/plato_damage/dense/rocking_\d\.webp", r.text)) == 7


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

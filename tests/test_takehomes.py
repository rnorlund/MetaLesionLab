"""Take-homes (/takehomes): three panels (one chair, copies of copies, written words), numbers from the data files, the starred nav item."""
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
    for h in ("Meta’s AI has one idea of a chair.", "Copy a copy, and the idea gets lost.", "Written words lose what you meant."):
        assert h in r.text
    assert [m for m in re.findall(r'class="th-link" href="([^"]+)"', r.text)] == ["/plato", "/plato/telephone", "/plato/phaedrus"]
    assert re.findall(r'class="th-num">(\d)<', r.text) == ["1", "2", "3"]
    assert "words-first" not in r.text and 'id="god"' not in r.text


def test_data_ask_questions(client):
    t = client.get("/takehomes").text
    assert re.findall(r'data-ask="([^"]+)"', t) == ["What happens when you copy a copy?", "Can written words say what you meant?"]


def test_copies_pictures_exist_and_run_left_to_right(client):
    t = client.get("/takehomes").text
    row = re.search(r'<ol class="th-row th-scroll"[^>]*>(.*?)</ol>', t, re.S).group(1)
    idx = [int(i) for i in re.findall(r"telephone-beanbag-(\d+)\.webp", row)]
    assert idx == [0, 2, 3, 5, 7, 8, 10]
    assert re.findall(r'class="th-lbl">([^<]+)<', row) == ["start", "copy 2", "copy 3", "copy 5", "copy 7", "copy 8", "copy 10"]
    for i in idx:
        assert client.get(f"/static/img/gallery/telephone-beanbag-{i}.webp").status_code == 200
    assert all(a.strip() for a in re.findall(r'alt="([^"]*)"', row)) and len(re.findall(r'alt="', row)) == 7


def test_phaedrus_numbers_match_data(client):
    t = client.get("/takehomes").text
    d = json.loads((DATA / "plato_phaedrus.json").read_text())
    ks, kr, n = d["spark"]["transcript"]["k"], d["reader"]["k"], d["reader"]["n"]
    assert f"Meta’s AI, reading the words: <b>{ks} of {n}</b>" in t
    assert f"A simple program, listening to the sound: <b>{kr} of {n}</b>" in t
    assert f"got the meaning {ks} times in {n}" in t and f"listening to the sound got {kr}." in t
    assert "guessing: 1 in 7" in t


def test_play_buttons_labelled_and_audio_served(client):
    t = client.get("/takehomes").text
    btns = re.findall(r'<button type="button" class="th-play" data-src="([^"]+)"[^>]*aria-label="([^"]+)"', t)
    assert len(btns) == 7
    assert btns[0][1] == "Play: I never said she stole my money."
    assert [re.search(r"\b[A-Z]{2,}\b", a).group(0) for _, a in btns[1:]] == ["NEVER", "SAID", "SHE", "STOLE", "MY", "MONEY"]
    assert all(a.startswith("Play: ") for _, a in btns)
    for src, _ in btns:
        assert client.get(src).status_code == 200
    assert "{{" not in t


def test_numbers_match_data(client):
    t = client.get("/takehomes").text
    chair = next(h for h in json.loads((DATA / "plato.json").read_text())["hero"] if h["key"] == "chair")
    assert f'<b>{chair["ai_spread"]:.2f}</b>' in t and f'<b>{chair["human_spread"]:.2f}</b>' in t


def test_nav_has_starred_takehomes_first_after_home(client):
    nav = re.search(r'<nav class="topnav" aria-label="Main">(.*?)<details', client.get("/takehomes").text, re.S).group(1)
    links = re.findall(r"<a ([^>]*)>(.*?)</a>", nav, re.S)
    labels = [re.sub(r"<[^>]+>|↗", "", b).strip() for _, b in links]
    assert labels[:3] == ["Home", "Take-homes", "Draw"]
    attrs, body = links[1]
    assert 'href="/takehomes"' in attrs and "nav-star" in attrs and "<svg" in body

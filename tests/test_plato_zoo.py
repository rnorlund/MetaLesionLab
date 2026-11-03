"""The damage zoo page (/plato/zoo, web/plato_zoo_routes.py, static/js/plato_zoo.js): its data file matches the
script's damage ranges, every strip it names exists, the page is served under Damaged AI with a card on the hub, and
the card shows no AI's God."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web
from metalesionlab.web import damaged_routes, plato_zoo_routes, site

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import damage_zoo as Z  # noqa: E402

DATA = json.loads(plato_zoo_routes.DATA.read_text())
STATIC = REPO / "metalesionlab" / "web" / "static"
JS = (STATIC / "js" / "plato_zoo.js").read_text()


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


def test_every_model_steps_from_intact_to_its_chosen_end_in_eleven_pictures():
    assert DATA["steps"] == Z.FINE_STEPS + 1 and DATA["things"] == Z.THINGS and DATA["parts"] == list(Z.PARTS)
    assert len(DATA["models"]) >= 4
    for m in DATA["models"]:
        for part in Z.PARTS:
            doses = m["doses"][part]
            assert doses == Z.fine_doses(m["key"], part) and doses[0] == 0 and doses == sorted(doses), (m["key"], part)
            assert m["captions"][part], f"{m['key']} {part}: write how its pictures fail (damage_zoo.CAPTIONS)"
        assert m["license"] and "check" not in m["license"].lower() and m["name"] and m["maker"] and m["reads_with"]


def test_every_strip_the_page_names_exists():
    from PIL import Image

    for m in DATA["models"]:
        for part in Z.PARTS:
            for thing in Z.THINGS:
                strip = STATIC / "img" / "zoo" / f"{m['key']}-{part}-{thing}.webp"
                assert Image.open(strip).size == (DATA["frame"] * DATA["steps"], DATA["frame"]), strip.name
    assert "/static/img/zoo/" in JS and "/api/plato/zoo" in JS


def test_the_page_is_served_under_damaged_ai_with_a_card_on_the_hub(client):
    page = client.get("/plato/zoo")
    assert page.status_code == 200 and "/static/js/plato_zoo.js" in page.text and "The damage zoo" in page.text
    api = client.get("/api/plato/zoo").json()
    assert [m["key"] for m in api["models"]] == [m["key"] for m in DATA["models"]]
    assert "/plato/zoo" in site.DAMAGED_PAGES and 'href="/plato/zoo"' in client.get("/damaged").text
    card = next(c for c in damaged_routes.CARDS if c["path"] == "/plato/zoo")
    assert (STATIC / "img" / "plato" / "hub" / f"{card['slug']}.webp").exists()


def test_the_hub_card_shows_chairs_never_god():
    assert all(len(p) == 3 for p in Z.HUB_PICKS)
    src = (REPO / "scripts" / "damage_zoo.py").read_text()
    hub = src[src.index("def hub_card"):src.index("def cmd_web")]
    assert '"chair"' in hub and "god" not in hub.lower()

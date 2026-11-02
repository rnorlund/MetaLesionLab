"""Draw it again, live (web/plato_redraw_routes.py): 8 new Muse Image pictures with the experiment's prompt, measured
against the published numbers; one free try per address a day on the demo's budget, more on a visitor's own key."""
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from metalesionlab import meta_api
from metalesionlab.plato import BY_KEY, prompt_for
from metalesionlab.web import app as web
from metalesionlab.web import plato_redraw_routes as R

KEY = "LLM|judge_key_1234567890abcdef"


def png() -> bytes:
    im = Image.new("RGB", (64, 64), "white")
    ImageDraw.Draw(im).rectangle((16, 16, 48, 48), outline="black", width=3)
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


class FakeAPI:
    def __init__(self, metered=True):
        self.metered, self.prompts = metered, []

    def generate_images(self, prompt, n=1, ledger_tag=None, **kw):
        self.prompts.append(prompt)
        return [png() for _ in range(n)]


@pytest.fixture
def client(monkeypatch):
    site = FakeAPI()
    monkeypatch.setattr(web, "get_api", lambda: site)
    monkeypatch.setattr(web, "api_key_present", lambda: True)
    rng = np.random.default_rng(0)
    monkeypatch.setattr(R, "embed_all", lambda pics: rng.normal(size=(len(pics), 768)))
    R.free_tries.clear()
    R.own_tries.clear()
    c = TestClient(web.app_for("plato"))
    c.site = site
    return c


def test_status_lists_the_measurable_things(client):
    s = client.get("/api/plato/redraw/status").json()
    assert "chair" in s["keys"] and s["n"] == 8 and s["tries_left_today"] == 1 and not s["own_key"]
    assert client.get("/api/plato/redraw/status", headers={"X-Meta-Key": KEY}).json()["own_key"]


def test_one_free_try_with_the_experiments_prompt_then_an_invitation_to_use_a_key(client):
    r = client.post("/api/plato/redraw", json={"key": "chair"})
    assert r.status_code == 200
    d = r.json()
    assert d["n"] == 8 and len(d["images"]) == 8 and all(u.startswith("data:image/webp;base64,") for u in d["images"])
    assert set(client.site.prompts) == {prompt_for(BY_KEY["chair"], "doodle")}
    assert {"new_spread", "ai_spread", "human_spread", "people_farther_pct"} <= set(d)
    again = client.post("/api/plato/redraw", json={"key": "chair"})
    assert again.status_code == 429 and "your own Meta API key" in again.json()["detail"]


def test_an_own_key_draws_again_on_its_own_account(client, monkeypatch):
    client.post("/api/plato/redraw", json={"key": "chair"})  # the free try is used
    mine = FakeAPI(metered=False)
    monkeypatch.setattr(R.own_key, "api_for", lambda request: mine if request.headers.get("x-meta-key") else None)
    r = client.post("/api/plato/redraw", json={"key": "boat"}, headers={"X-Meta-Key": KEY})
    assert r.status_code == 200 and r.json()["key"] == "sailboat" and mine.prompts and not client.site.prompts[2:]


def test_unknown_things_and_a_spent_budget_are_plain_answers(client, monkeypatch):
    assert client.post("/api/plato/redraw", json={"key": "person"}).status_code == 422

    def broke(*a, **k):
        raise meta_api.BudgetExceeded("spent")
    monkeypatch.setattr(client.site, "generate_images", broke)
    r = client.post("/api/plato/redraw", json={"key": "chair"})
    assert r.status_code == 503 and "own Meta API key" in r.json()["detail"]

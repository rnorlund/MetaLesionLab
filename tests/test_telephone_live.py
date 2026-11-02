"""Play telephone with your own drawing (web/plato_telephone_live_routes.py): only on a visitor's own key, streamed,
nothing stored, the key never in a response."""
import base64
import io
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab.web import app as web
from metalesionlab.web import own_key
from metalesionlab.web import plato_telephone_live_routes as R

KEY = "LLM|judge_key_1234567890abcdef"
URL = "/api/plato/telephone/play"


def _png(size=(300, 200), color=(30, 30, 30, 255), mode="RGBA") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color if mode == "RGBA" else color[:3]).save(buf, "PNG")
    return buf.getvalue()


def _url(raw: bytes, mime="png") -> str:
    return f"data:image/{mime};base64," + base64.b64encode(raw).decode()


class FakeAPI:
    def __init__(self):
        self.chats = []
        self.prompts = []

    def chat(self, messages, **kw):
        self.chats.append((messages, kw))
        msg = SimpleNamespace(content=f"A drawing, number {len(self.chats)}.")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)

    def generate_images(self, prompt, n=1):
        self.prompts.append(prompt)
        return [_png((1024, 1024), (200, 120, 40, 255))]


@pytest.fixture
def client(monkeypatch):
    R._games.clear()
    c = TestClient(web.create_app("plato"))
    c.fake = FakeAPI()
    monkeypatch.setattr(own_key, "api_for", lambda request: c.fake if request.headers.get("x-meta-key") else None)
    return c


def _lines(r):
    return [json.loads(x) for x in r.text.splitlines() if x.strip()]


def _post(client, body, key=KEY):
    return client.post(URL, json=body, headers={"X-Meta-Key": key} if key else {})


def test_no_key_is_refused_plainly(client):
    r = _post(client, {"image": _url(_png())}, key=None)
    assert r.status_code == 403 and "your own Meta API key" in r.json()["detail"]
    assert not client.fake.chats


def test_a_game_streams_start_rounds_done(client):
    r = _post(client, {"image": _url(_png()), "rounds": 3})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    ev = _lines(r)
    assert ev[0] == {"type": "start", "rounds": 3} and ev[-1] == {"type": "done"}
    rounds = ev[1:-1]
    assert [e["n"] for e in rounds] == [1, 2, 3]
    for e in rounds:
        assert e["type"] == "round" and e["description"].startswith("A drawing")
        assert e["image"].startswith("data:image/webp;base64,")
        im = Image.open(io.BytesIO(base64.b64decode(e["image"].split(",", 1)[1])))
        assert im.format == "WEBP" and max(im.size) <= 512
    assert len(client.fake.chats) == 3 and len(client.fake.prompts) == 3
    first = client.fake.chats[0][0][0]["content"]  # Spark gets the picture and the experiment's prompt
    assert first[0]["image_url"]["url"].startswith("data:image/png;base64,") and first[1]["text"]
    assert KEY not in r.text


def test_default_is_five_rounds(client):
    ev = _lines(_post(client, {"image": _url(_png(), "png")}))
    assert ev[0]["rounds"] == 5 and len(ev) == 7


def test_bad_pictures_and_rounds_are_422(client):
    for body in ({"image": "nope"}, {"image": _url(b"not a picture")}, {"image": _url(_png((10, 10)))},
                 {"image": _url(_png(), "gif")}, {}, {"image": _url(_png()), "rounds": 0},
                 {"image": _url(_png()), "rounds": 7}, {"image": _url(_png()), "rounds": "5"},
                 {"image": "data:image/png;base64,@@@@"}):
        r = _post(client, body)
        assert r.status_code == 422, body
        assert KEY not in r.text
    assert _post(client, {"image": _url(_png() + b"\0" * 1_600_000)}).status_code == 422  # over 1.5 MB decoded
    assert not client.fake.chats


def test_a_transparent_drawing_goes_out_on_white(client):
    _post(client, {"image": _url(_png((64, 64), (0, 0, 0, 0))), "rounds": 1})
    url = client.fake.chats[0][0][0]["content"][0]["image_url"]["url"]
    im = Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))
    assert im.mode == "RGB" and im.getpixel((5, 5)) == (255, 255, 255)


def test_a_failing_key_ends_the_stream_with_the_error_type_only(client):
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("secret " + KEY)
    client.fake.chat = boom
    ev = _lines(_post(client, {"image": _url(_png()), "rounds": 2}))
    assert ev[0]["type"] == "start" and ev[-1]["type"] == "error" and len(ev) == 2
    assert "ConnectError" in ev[-1]["message"] and KEY not in json.dumps(ev)


def test_daily_limit_per_address(client):
    for _ in range(R.GAMES_A_DAY):
        assert _post(client, {"image": _url(_png()), "rounds": 1}).status_code == 200
    r = _post(client, {"image": _url(_png()), "rounds": 1})
    assert r.status_code == 429 and "limit" in r.json()["detail"]

"""What damage does to an AI's chair (/draw): the SDXL strips' data and pictures, and the rule that the strip
is about the model only. It is never placed, compared, scored or matched against a visitor's drawing."""
import json
import re

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab.plato import BY_KEY as PLATO, STYLES, prompt_for
from metalesionlab.web import app as web

IMG = web.HERE / "static" / "img" / "draw_damage"
DATA = IMG / "draw_damage.json"
JS = web.HERE / "static" / "js" / "draw.js"
BUDGET = 1_500_000
STRIP_START, STRIP_END = "// ---------- what damage does to an AI", "// ---------- the component"


@pytest.fixture(scope="module")
def dmg():
    return json.loads(DATA.read_text())


def static_file(url: str):
    assert url.startswith("/static/img/draw_damage/"), url
    return web.HERE / url.lstrip("/")


def strip_code() -> str:
    js = JS.read_text()
    return js[js.index(STRIP_START):js.index(STRIP_END)]


def all_keys(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k
            yield from all_keys(v)
    elif isinstance(x, list):
        for v in x:
            yield from all_keys(v)


def test_schema(dmg):
    assert dmg["model"] == "stabilityai/stable-diffusion-xl-base-1.0"
    assert "Stability AI" in dmg["credit"] and "CreativeML OpenRAIL++-M" in dmg["credit"]
    assert dmg["prompt_template"] == STYLES["doodle"] and dmg["more"] == "/plato/damage"
    rows = dmg["rows"]
    assert list(rows) == ["language", "drawing"]
    assert (rows["language"]["family"], rows["language"]["site"]) == ("text-noise", "text")
    assert (rows["drawing"]["family"], rows["drawing"]["site"]) == ("unet-noise", "unet")
    for r in rows.values():
        doses = r["doses"]
        assert len(doses) == 5 and doses == sorted(set(doses)) and doses[0] > 0
        assert r["conditions"] == [f"{r['family']}@{d:g}" for d in doses]
    seeds = [t["seed"] for t in dmg["things"]]
    assert all(isinstance(s, int) for s in seeds) and len(set(seeds)) == len(seeds)
    for t in dmg["things"]:
        assert t["prompt"] == prompt_for(PLATO[t["key"]], "doodle")  # the doodle prompt Muse Image was given
        assert isinstance(t["intact"], str)
        for row in rows:
            assert len(t[row]) == len(rows[row]["doses"])
    assert dmg["total_bytes"] == sum(f.stat().st_size for f in IMG.glob("*.webp"))


def test_levels_match_the_damage_page(dmg):
    """The strip's doses are the damage experiment's noise doses (every /plato/damage slider level is there)
    and stay inside that experiment's range."""
    slider = json.loads((web.HERE / "data" / "plato_damage.json").read_text())["slider"]["levels"]
    for row in dmg["rows"].values():
        page = [float(lv["cond"].split("@")[1]) for lv in slider[row["family"]] if lv["cond"] != "intact"]
        assert set(page) <= set(row["doses"])
        assert min(page) <= min(row["doses"]) and max(row["doses"]) <= max(page)


def test_every_thing_has_its_pictures(dmg):
    concepts = json.loads((web.HERE / "data" / "draw.json").read_text())["concepts"]
    assert [t["key"] for t in dmg["things"]] == [c["key"] for c in concepts]  # all 10 things, same order
    labels = {c["key"]: c["label"] for c in concepts}
    used = set()
    for t in dmg["things"]:
        assert t["label"] == labels[t["key"]]
        for url in [t["intact"]] + t["language"] + t["drawing"]:
            path = static_file(url)
            assert path.is_file(), url
            with Image.open(path) as im:
                assert im.format == "WEBP" and im.size[0] == im.size[1] and 128 <= im.size[0] <= 256
            used.add(path.name)
        assert len({t["intact"], *t["language"], *t["drawing"]}) == 11
    assert {p.name for p in IMG.iterdir()} == used | {DATA.name}  # nothing else in the folder
    assert sum(p.stat().st_size for p in IMG.iterdir()) < BUDGET


def test_the_strip_is_never_compared_with_a_drawing(dmg):
    """No code path compares the visitor's drawing (or its embedding) with the damage pictures."""
    # The data holds pictures and settings only: no embeddings, distances or scores to compare with.
    assert not [k for k in all_keys(dmg) if re.search(r"vec|emb|dist|score|near|^d_|^xy$|cls|percent", k, re.I)]
    # The server's scoring never loads it, and no shipped data file refers to it.
    for f in [web.HERE.parent / "draw.py", web.HERE / "draw_routes.py", *(web.HERE / "data").glob("**/*.json")]:
        assert "draw_damage" not in f.read_text(), f
    # In the page script, the strip's code knows the thing's key and nothing about the visitor.
    code = strip_code()
    for word in ("result", "strokes", "originality", "d_ai", "d_human", "xy", "nearest", "S.", "score", "embed",
                 "/api/draw", "sent", "upload", "canvas", "your"):
        assert word not in code, word
    js = JS.read_text()
    calls = re.findall(r"renderDamage\(([^)]*)\)", js)
    assert len(calls) >= 2 and all(re.fullmatch(r"\s*\w+\s*,\s*(S\.key|key)\s*", c) for c in calls), calls


def test_the_strip_is_about_the_ai_only():
    code = strip_code()
    for line in ("Meta’s Muse Image can’t be opened up, so this uses an open image model (Stable Diffusion XL) "
                 "that we damaged on purpose.",
                 "Top row: damage to the part that handles words, so the idea wanders off.",
                 "Bottom row: damage to the part that draws, so the lines dissolve.",
                 "This shows what happens to an AI. It says nothing about the person drawing.",
                 "More: Damage the painter", "/plato/damage", "What damage does to an AI’s "):
        assert line in code, line
    text = (code + DATA.read_text()).lower()
    for word in ("diagnos", "screen", "impair", "decline", "dementia", "normal", "older", "elderly", "aging",
                 "cognit", "memory", "patient", "like level"):
        assert word not in text, word


def test_blind_until_the_reveal():
    """The strip is SDXL's picture of the thing, so like Muse Image's it waits until the visitor draws or skips."""
    c = TestClient(web.app)
    page = c.get("/draw").text
    assert "draw_damage" not in page[page.index("<main"):page.index("</main>")]
    js = JS.read_text()
    assert "draw_damage" not in js[js.index("var PAD_HTML"):js.index("var RESULTS_HTML")]
    landing = c.get("/").text
    assert "draw_damage" not in landing
    assert c.get("/static/img/draw_damage/draw_damage.json").status_code == 200

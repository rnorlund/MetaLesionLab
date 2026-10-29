"""The top pages lead with the result: /draw ("Draw anything", God first, a picker built from the data), /plato
(the chair result and the Experiments hub, no drawing pad), the gallery (real sequences and numbers drawn as
graphics), and the header's even-weighted nav buttons."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web
from metalesionlab.web import site

STATIC = web.HERE / "static"
DRAW_JS = STATIC / "js" / "draw.js"
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


def main_of(html: str) -> str:
    return html[html.index("<main"):html.index("</main>")]


def local(url: str) -> Path:
    assert url.startswith("/static/"), url
    return STATIC / url[len("/static/"):]


# --- /draw: Draw anything ---------------------------------------------------------------------------

def test_draw_starts_on_god(client):
    page = client.get("/draw").text
    assert "<title>Draw anything" in page
    mount = page[page.index("TOTDraw.mount("):]
    assert "concept: 'god'" in mount and "conceptLabel: 'God'" in mount and "conceptMode: 'ai_only'" in mount
    god = next(c for c in client.get("/api/draw/concepts").json()["concepts"] if c["key"] == "god")
    assert god["mode"] == "ai_only" and god["label"] == "God"
    # The home page keeps the chair, and its links to the invisible ideas still land on them.
    assert "concept: 'chair'" in (STATIC / "js" / "landing.js").read_text()
    landing = client.get("/").text
    assert re.findall(r'href="/draw\?thing=(\w+)"', landing)[:3] == ["god", "love", "time"]
    assert 'href="/draw?thing=chair">draw a chair' in landing  # "draw a chair" still means the chair
    js = DRAW_JS.read_text()
    assert "searchParams.get('thing')" in js and "url.searchParams.set('thing', key)" in js  # ?thing= deep links


def test_draw_first_screen_stays_blind(client):
    main = main_of(client.get("/draw").text)
    assert "_muse.webp" not in main and "plato_ideas/" not in main and "<img" not in main.split('id="how"')[0]
    stakes = main[main.index('id="dw-stakes"'):main.index("</section>", main.index('id="dw-stakes"'))]
    assert "Hidden until you draw" in stakes and "16" in stakes  # how many drawings wait, never what they show
    for spoiler in ("bearded", "heart", "clock", "16 times"):
        assert spoiler not in stakes, spoiler


def test_picker_is_built_from_the_data():
    js = DRAW_JS.read_text()
    picker = js[js.index("function pickerGroups(data)"):js.index("// ---------- sprites")]
    render = js[js.index("function renderChips()"):js.index("function choose(key)")]
    assert "pickerGroups(S.data)" in render
    keys = [c["key"] for c in TestClient(web.app).get("/api/draw/concepts").json()["concepts"]]
    for key in keys:  # no concept is named in the picker's code: every button comes from the data
        assert f"'{key}'" not in picker + render, key


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_new_concepts_and_groups_join_the_picker():
    """Verbs and adjectives joining as AI-only concepts get buttons without a code change, listed group or not."""
    data = {"groups": [{"id": "things", "label": "Or draw:"}, {"id": "ideas", "label": "Draw the invisible:"},
                       {"id": "verbs", "label": "Draw a verb:"}],
            "concepts": [{"key": "chair", "label": "chair"}, {"key": "god", "label": "God", "mode": "ai_only", "group": "ideas"},
                         {"key": "run", "label": "run", "mode": "ai_only", "group": "verbs"},
                         {"key": "tall", "label": "tall", "mode": "ai_only", "group": "adjectives"},
                         {"key": "love", "label": "love", "mode": "ai_only"}]}
    code = (f"global.window = {{ TOT: {{ h: function () {{}} }} }}; require({json.dumps(str(DRAW_JS))});"
            f"console.log(JSON.stringify(window.TOTDraw.pickerGroups({json.dumps(data)})));")
    run = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    groups = [(g["id"], g["title"], g["aiOnly"], [c["key"] for c in g["items"]]) for g in json.loads(run.stdout)]
    assert groups == [("things", "Things", False, ["chair"]), ("ideas", "The invisible", True, ["god", "love"]),
                      ("verbs", "Draw a verb", True, ["run"]), ("adjectives", "Adjectives", True, ["tall"])]


# --- /plato: the result first, then the Experiments hub ----------------------------------------------

def test_plato_has_no_pad_and_leads_with_the_result(client):
    page = client.get("/plato").text
    main = main_of(page)
    for pad in ("TOTDraw", "/static/js/draw.js", "draw-app", 'id="hero-draw"', "<canvas", "dw-canvas"):
        assert pad not in page, pad
    top = main[:main.index('id="experiments"')]
    assert 'id="chairs"' in top and 'id="stack-btn"' in top and "<h1" in top
    assert top.count('class="pc-chairs-grid"') == 2 and top.count("--c:") == 32  # 16 chairs a side
    assert 'href="/#hero-draw">Draw your own chair</a>' in top  # the pad lives on the home page
    assert len(re.findall(r'data-sv="(dots|spread|layers|bars)"', top)) == 3  # at most three numbers, all graphics
    assert "/static/js/statviz.js" in page and "/static/css/statviz.css" in page
    assert 'id="who-seg"' in main and main.index('id="experiments"') < main.index('id="hero"')  # the toggle, lower down


def test_plato_numbers_match_the_data(client):
    top = main_of(client.get("/plato").text).split('id="experiments"')[0]
    d = json.loads((web.HERE / "data" / "plato.json").read_text())
    chair = next(h for h in d["hero"] if h["key"] == "chair")
    assert f'data-values="{chair["ai_spread"]},{chair["human_spread"]}"' in top
    assert f'data-k="{d["core"]["below_1"]}" data-n="{d["core"]["n_concepts"]}"' in top
    inside = json.loads((web.HERE / "data" / "plato_inside.json").read_text())
    assert f'data-at="{int(inside["summary"]["median_collapse_layer"])}" data-n="{inside["n_layers"]}"' in top


def test_hub_is_one_even_grid_of_real_pictures(client):
    main = main_of(client.get("/plato").text)
    hub = main[main.index('id="experiments"'):main.index('id="hero"')]
    served = [s for s in client.get("/api/site").json()["series"] if s["path"] not in ("/plato", *site.DAMAGED_PAGES)]
    cards = re.findall(r'<a class="hub-card" href="([^"]+)">(.*?)</a></li>', hub, re.S)
    assert [href for href, _ in cards] == [s["path"] for s in served] and hub.count('class="hub-grid"') == 1
    # the damage experiments moved to the Damaged AI hub; /plato/ideas (God under damage is one of its sections) stays,
    # and so does /plato/inside, which also has its own nav button: this hub lists every non-damage question
    assert "/plato/damage" not in [href for href, _ in cards] and 'href="/plato/damage"' not in hub
    assert {"/plato/ideas", "/plato/inside"} <= {href for href, _ in cards}
    assert 'href="/damaged">Damaged AI</a>' in hub  # one line pointing to them
    for (href, card), s in zip(cards, served):
        img = re.search(r'<img src="([^"]+)"', card)
        assert img and local(img.group(1)).is_file(), href  # a real picture on every card
        assert s["question"] in card.replace("&#x27;", "'") or site._esc(s["question"]) in card, href
        answer = re.search(r'<span class="hub-a">([^<]+)</span>', card)
        assert answer and len(answer.group(1)) <= 110, href  # one line
    ideas = next((card for href, card in cards if href == "/plato/ideas"), None)
    if ideas:  # the invisible Forms card shows Plato, never Muse Image's drawings of God (the draw stays blind)
        src = re.search(r'<img src="([^"]+)"', ideas).group(1)
        assert src == "/static/img/plato/hub/ideas.webp" and "plato_ideas" not in ideas and "god" not in src


def test_hub_pictures_are_small_and_only_on_the_hub(client):
    pics = sorted((STATIC / "img" / "plato" / "hub").glob("*.webp"))
    assert pics and all(p.stat().st_size < 60_000 for p in pics)
    assert "/img/plato/hub/" not in client.get("/").text  # the landing page's series cards keep their own pictures
    assert set(site.HUB_ANSWERS) >= {s["slug"] for s in site.SERIES if s["slug"] != "phaedrus"}


# --- the gallery: real sequences, the answer, three numbers -----------------------------------------------

def test_gallery_leads_with_real_sequences_and_numbers(client):
    main = main_of(client.get("/plato/gallery").text)
    top = main[:main.index('class="gx-bar"')]
    items = {i["id"]: i for i in json.loads((web.HERE / "data" / "gallery.json").read_text())["items"]}
    films = re.findall(r'<a class="gx-film" href="#([\w-]+)">(.*?)</a>', top, re.S)
    assert len(films) == 2
    for item_id, film in films:
        frames = {f["src"] for f in items[item_id]["sequence"]["frames"]}
        srcs = re.findall(r'<img src="([^"]+)"', film)
        assert len(srcs) == 5 and set(srcs) <= frames and all(local(s).is_file() for s in srcs), item_id
    assert "<h1" in top and len(re.findall(r'data-sv="(dots|spread|layers|bars)"', top)) == 3
    captions = " ".join(i["caption"] for i in items.values())
    for fact in ("from 33% of clocks to 4%", "49 times in 50", "67 of 100"):  # each number is the gallery's own
        assert fact in captions, fact
    assert 'data-values="33,4"' in top and 'data-k="49" data-n="50"' in top and 'data-k="67" data-n="100"' in top


# --- the header: even-weighted buttons, Ask Socrates the accent ------------------------------------------

def test_nav_buttons_are_even_and_socrates_is_the_accent(client):
    nav = re.search(r'<nav class="topnav" aria-label="Main">(.*?)<details', client.get("/plato").text, re.S).group(1)
    links = re.findall(r'<a ([^>]*)>(.*?)</a>', nav, re.S)
    buttons = [(a, body) for a, body in links if "nav-btn" in a]
    assert [re.sub(r"<[^>]+>", "", body) for _, body in buttons] == ["Home", "Take-homes", "Draw", "Damaged AI", "Inside the model",
                                                                       "Experiments", "Gallery", "Ask Socrates"]
    assert all('<svg class="nav-ico"' in body and 'aria-hidden="true"' in body for _, body in buttons)
    assert [a for a, _ in links if "nav-accent" in a] == ['href="/socrates" class="nav-accent nav-btn"']
    assert all("nav-btn" not in a for a, body in links if "Code" in body)  # the external link stays plain
    lingua = TestClient(web.app_for("lingua")).get("/").text
    assert "nav-btn" not in lingua and "nav-ico" not in lingua

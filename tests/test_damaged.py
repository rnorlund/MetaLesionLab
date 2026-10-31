"""Damaged AI (/damaged, web/damaged_routes.py): the hub of the damage experiments, second in the nav after Draw.

Its first screen asks what happens to an AI's idea of a thing when it is damaged, shows the rocking chair that language
damage turns into a car and draws three numbers. The page's own scripts run under node in the small stand-in for the
browser (tests/firstscreen_dom.js), fed the real /api/plato/damage and /api/plato/ideas, and every picture, number and
verdict they draw is checked against that data here, so nothing on the first screen is typed in. Then one card per damage
result, each opening a section that exists. The Experiments hub on /plato no longer lists the damage experiments."""
import html
import json
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web
from metalesionlab.web import damaged_routes, site

NODE = shutil.which("node")
HARNESS = web.HERE.parents[1] / "tests" / "firstscreen_dom.js"
STATIC = web.HERE / "static"
APIS = ("/api/plato/damage", "/api/plato/ideas")


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


def main_of(html: str) -> str:
    return html[html.index("<main"):html.index("</main>")]


def hub_cards(html: str) -> list[tuple[str, str]]:
    return re.findall(r'<a class="hub-card" href="([^"]+)">(.*?)</a></li>', html, re.S)


# --- the nav ------------------------------------------------------------------------------------------------------

def test_nav_puts_damaged_ai_after_take_homes_and_draw(client):
    nav = re.search(r'<nav class="topnav" aria-label="Main">(.*?)<details', client.get("/damaged").text, re.S).group(1)
    links = re.findall(r'<a ([^>]*)>(.*?)</a>', nav, re.S)
    labels = [re.sub(r"<[^>]+>|↗", "", body).strip() for _, body in links]
    assert labels == ["Home", "Take-homes", "Draw", "Damaged AI", "Inside the model", "Experiments", "Gallery", "Ask Socrates", "Code"]
    attrs, body = links[3]
    assert 'href="/damaged"' in attrs and "nav-btn" in attrs and 'aria-current="page"' in attrs
    assert '<svg class="nav-ico"' in body and site.NAV_ICONS["damaged"] in body  # its own line icon, a cracked chip
    assert sum('aria-current="page"' in a for a, _ in links) == 1


def test_damaged_ai_is_only_on_the_plato_site():
    lingua = TestClient(web.app_for("lingua"))
    assert lingua.get("/damaged").status_code == 404 and 'href="/damaged"' not in lingua.get("/").text


# --- the first screen ---------------------------------------------------------------------------------------------

def test_first_screen_asks_the_question(client):
    page = client.get("/damaged").text
    main = main_of(page)
    hero = main[:main.index('id="results"')]
    assert "<h1" in hero and "What happens to an AI’s idea of a thing when we damage it?" in hero
    assert "Plato would ask:" in hero  # the series kicker (portraits.kicker_face): his face and these words
    # plain words: damage is said in full the first time, before the page uses the word on its own
    first = text(hero).index("damage")
    assert "switched off some of their artificial neurons, or added random noise to them" in text(hero)[:first + 200]
    assert 'data-passage="republic-596a"' in hero  # a verified epigraph: a common name and its idea or form
    assert 'class="fl-answer"' in hero and "<b>what</b>" in hero and "<b>how</b>" in hero
    assert "data-hero-carousel" in hero  # the picture area is the hero carousel (its first slide is written out)
    for i in ("hero-stats", "hero-qual"):
        assert f'id="{i}"' in hero, i
    assert "/static/js/plato_firstlook.js" in page and "/static/js/statviz.js" in page and "/static/js/plato_damaged.js" in page
    assert "It is a comparison, not a claim about people." in hero


def first_screen(client, tmp_path, ids):
    """Run /damaged's own scripts on the real data of both APIs; {id: outerHTML}, and the data."""
    if not NODE:
        pytest.skip("node is not installed")
    data = {}
    for api in APIS:
        r = client.get(api)
        if r.status_code != 200:
            pytest.skip(f"{api} has no data on this machine")
        data[api] = r.json()
        (tmp_path / f"{api.rsplit('/', 1)[1]}.json").write_text(json.dumps(data[api]))
    html = client.get("/damaged").text
    (tmp_path / "page.html").write_text(html)
    scripts = [str(STATIC / "js" / s) for s in re.findall(r'<script src="/static/js/([\w.-]+?\.js)', html)]
    cfg = {"html": str(tmp_path / "page.html"), "scripts": scripts, "ids": list(ids) + ["hero-how"],
           "api": {api: str(tmp_path / f"{api.rsplit('/', 1)[1]}.json") for api in APIS}}
    (tmp_path / "cfg.json").write_text(json.dumps(cfg))
    run = subprocess.run([NODE, str(HARNESS), str(tmp_path / "cfg.json")], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert not out["errors"], out["errors"]
    # the qualifiers live in the closed "How we know" disclosure under the numbers: read with them
    if "hero-stats" in ids and out["ids"].get("hero-how"):
        out["ids"]["hero-stats"] += out["ids"]["hero-how"]
    return out["ids"], data["/api/plato/damage"], data["/api/plato/ideas"]


def stats(html):
    """Each number block: its label (before any value) and its rows (name, value, units)."""
    out = []
    for it in re.findall(r'<figure class="fl-stat">(.*?)</figure>', html, re.S):
        ask = re.search(r'<p class="fl-ask">(.*?)</p>', it).group(1)
        assert it.index('class="fl-ask"') < it.index("sv-bar-v"), "the label comes before the values"
        assert len(ask.split()) <= 10
        rows = [(m[0], m[1], m[2].strip()) for m in re.findall(
            r'<span class="sv-bar-l">(.*?)</span>.*?<span class="sv-bar-v">([^<]*)(?:<span class="sv-bar-u">(.*?)</span>)?</span>', it, re.S)]
        out.append((ask, rows))
    return out


def text(html):
    return re.sub(r"<[^>]+>", "", html)


def test_numbers_and_verdicts_come_from_the_data(client, tmp_path):
    ids, d, ideas = first_screen(client, tmp_path, ("hero-stats", "hero-qual"))
    s = stats(ids["hero-stats"])
    assert len(s) == 3
    # 1. language damage loses the asked kind faster (the pre-registered primary test of /plato/damage)
    kc = d["matched"]["text-zero vs unet-zero"]["delta_correct"]
    assert [r[1:] for r in s[0][1]] == [(str(round(-kc["language"] * 100)), "of 100"), (str(round(-kc["drawing"] * 100)), "of 100")]
    assert [r[0] for r in s[0][1]] == ["Damaged the words part", "Damaged the painting part"]
    # 2. Stable Diffusion XL's God turns into an ordinary person under language damage, not drawing damage (D3)
    x = ideas["damage"]
    d3, n = x["tests"]["D3"], x["n_seeds"]
    lang, draw = round(d3["language_rise"] * n), round(d3["drawing_rise"] * n)
    assert [r[1:] for r in s[1][1]] == [(str(lang), f"of {n}"), (str(draw), f"of {n}")] and "ordinary person" in s[1][0]
    eye = x["tests"]["D3_eye"]
    assert f"Counted by eye instead: +{round(eye['language_rise'] * n)} vs +{round(eye['drawing_rise'] * n)}." in ids["hero-stats"]
    # 3. clocks with all 12 numbers in order: intact against the mildest drawing damage
    c = d["clocks"]
    fi = c["feature_names"].index("12 numbers in order")
    intact = next(r for r in c["features"] if r["cond"] == "intact")
    mild = min((r for r in c["features"] if r["cond"].startswith("unet-zero@")), key=lambda r: float(r["cond"].split("@")[1]))
    assert [r[1] for r in s[2][1]] == [str(round(intact["values"][fi] * 100)), str(round(mild["values"][fi] * 100))]
    assert [r[2] for r in s[2][1]] == ["%", "%"] or [r[2] for r in s[2][1]] == ["", ""]
    # the verdicts: each worked out from its test, the same way /plato/damage shows them
    def held(t):
        lo, hi = t["ci95"]
        return (lo > 0 or hi < 0) and (t["difference"] > 0) == (t["predicted_sign"] > 0)
    want = [("yes", "As predicted") if held(kc) else ("no", "Prediction reversed"),
            ("yes", "As predicted") if d3["passes"] else ("no", "Prediction failed")]
    assert re.findall(r'<span class="fl-verdict (\w+)">(.*?)</span>', ids["hero-stats"]) == want
    # and where predictions failed or held only in part, the note says so
    qual = text(ids["hero-qual"])
    assert qual.startswith("Partly supported.") and "but the opposite when we switched neurons off" in qual
    proto = d["matched"]["text-zero vs unet-zero"]["delta_d_proto"]  # predicted: back toward the plain chair
    assert not held(proto) and "drift back toward a plain, ordinary chair, as drawings do in semantic dementia" in qual
    assert "Prediction failed." in qual
    farther = d["pooled"]["text-zero"]["delta_d_proto"]["ci95"][0] > 0
    assert ("The chairs wandered farther from the plain chair instead" if farther else "The chairs came no closer to it") in qual
    assert 'href="/plato/damage#diss-h"' in ids["hero-qual"] and 'href="/plato/damage#proto-h"' in ids["hero-qual"]


def test_the_picture_is_a_carousel_that_starts_on_the_rocking_chair_that_becomes_a_car(client):
    page = client.get("/damaged").text
    cfg = json.loads(re.search(r'data-hero-carousel[^>]*>\s*<script type="application/json">(.*?)</script>', page, re.S).group(1))
    first = cfg["slides"][0]
    assert first["caption"] == "rocking chair \u2192 car" and len(cfg["slides"]) == 1  # the second example, under the God cube
    for sl in cfg["slides"]:
        assert len(sl["caption"].split()) <= 10
        for im in sl["images"]:
            assert (STATIC / im["src"][len("/static/"):]).is_file(), im["src"]
    assert "hc-static" in page and "dense/rocking_6.webp" in page  # the first slide shows without JavaScript


# --- the cards ----------------------------------------------------------------------------------------------------

def test_one_card_per_damage_result_each_opening_a_real_section(client):
    main = main_of(client.get("/damaged").text)
    cards = hub_cards(main[main.index('id="results"'):])
    assert [href for href, _ in cards] == [c["path"] for c in damaged_routes.CARDS]
    assert {href.split("#")[0] for href, _ in cards} >= {"/plato/damage", "/plato/ideas", "/draw"}
    for (href, card), c in zip(cards, damaged_routes.CARDS):
        path, _, anchor = href.partition("#")
        target = client.get(path)
        assert target.status_code == 200, href
        if anchor:  # the section it opens exists on that page
            assert re.search(rf'\sid="{re.escape(anchor)}"', target.text), href
        img = re.search(r'<img src="([^"]+)"', card).group(1)
        assert img == f"/static/img/plato/hub/{c['slug']}.webp", href
        pic = STATIC / img[len("/static/"):]
        assert pic.is_file() and pic.stat().st_size < 60_000, href
        assert site._esc(c["question"]) in card and site._esc(c["title"]) in card
        answer = re.search(r'<span class="hub-a">([^<]+)</span>', card).group(1)
        assert len(answer) <= 130, href  # a line or two
    ideas = client.get("/plato/ideas").text  # God under damage: the section on /plato/ideas, which stays on /plato's hub too
    assert re.search(r'<section class="iv-sec iv-dmg" id="damage"', ideas)


def test_cards_follow_the_routes(client, monkeypatch):
    monkeypatch.setattr(damaged_routes, "CARDS", damaged_routes.CARDS + [
        {"slug": "x", "path": "/plato/not-served#x", "title": "t", "question": "q?", "answer": "a."}])
    assert 'href="/plato/not-served#x"' not in client.get("/damaged").text


def test_experiments_hub_keeps_the_rest_and_points_to_damaged_ai(client):
    main = main_of(client.get("/plato").text)
    hub = main[main.index('id="experiments"'):main.index('id="hero"')]
    hrefs = [href for href, _ in hub_cards(hub)]
    assert not set(hrefs) & set(site.DAMAGED_PAGES) and "/plato/ideas" in hrefs
    assert 'href="/damaged">Damaged AI</a>' in hub
    damaged = main_of(client.get("/damaged").text)
    assert 'href="/plato#experiments"' in damaged  # and back again


# --- plain words (docs/style_plain_language.md) --------------------------------------------------------------------

JARGON = [r"\bSDXL\b", r"\bUNet\b", r"text encoder", r"\bCI\b", r"\bpts\b", r"[Pp]re-registered", r"\bintact\b", r"\bn\s*=",
          r"\blayers?\b", r"\bspread\b", r"\bseed\b", r"\bprompt\b", r"\bdose\b", r"\blanguage part\b"]


def test_the_hub_speaks_plain_words(client, tmp_path):
    """No unexplained jargon anywhere a visitor reads on the hub: the first screen as drawn, its alt texts, and the cards."""
    ids, _, _ = first_screen(client, tmp_path, ("hero-stats", "hero-qual"))
    main = main_of(client.get("/damaged").text)
    main = re.sub(r'<figure class="epigraph.*?</figure>', "", main, flags=re.S)  # Plato's words stay verbatim
    shown = text(main) + " ".join(text(v) for v in ids.values())
    shown += " ".join(re.findall(r'(?:alt|aria-label)="([^"]*)"', main + "".join(ids.values())))
    for word in JARGON:
        assert not re.search(word, shown), word
    # who's who: each AI named in full the first time
    for full in ("Stable Diffusion XL, an open image AI from Stability AI", "Meta’s open AI model, Muse Glimmer",
                 "Janus-Pro, an open AI from DeepSeek"):
        assert full in shown, full


def test_god_only_on_the_damage_cube(client):
    """/draw starts on a blind "Draw God". Roger chose (Oct 30) to put Stable Diffusion XL's God, turning on the damage
    cube, front and centre on /damaged; no card on either hub, and nothing on /plato, shows any AI's God."""
    pics = re.findall(r'<img src="([^"]+)"', main_of(client.get("/plato").text))
    assert pics and not [p for p in pics if "god" in p.lower()]
    page = main_of(client.get("/damaged").text)
    cube = re.search(r'<figure class="dcube" id="god-cube".*?</figure>', page, re.S).group(0)
    assert not [p for p in re.findall(r'<img src="([^"]+)"', page.replace(cube, "")) if "god" in p.lower()]
    card = dict(hub_cards(main_of(client.get("/damaged").text)))["/plato/ideas#damage"]
    assert '<img src="/static/img/plato/hub/damaged-ideas.webp"' in card and "death" in card


def test_god_turns_on_the_cube_first_then_the_car_left_to_right(client):
    page = client.get("/damaged").text
    m = re.search(r'<figure class="dcube" id="god-cube" data-damage-cube data-pattern="([^"]+)" data-labels="([^"]+)"', page)
    assert m, "the God cube"
    labels = html.unescape(m.group(2)).split("|")
    assert labels[0] == "undamaged" and len(labels) == 10
    for i in range(len(labels)):  # every step's picture is shipped
        assert (STATIC / m.group(1).replace("{i}", str(i))[len("/static/"):]).is_file()
    assert page.index('id="god-cube"') < page.index('class="dm-second"') < page.index('id="film"')  # the cube, then the car
    assert "/static/js/damage-cube.js" in page and "/static/css/damage-cube.css" in page
    js = (STATIC / "js" / "damage-cube.js").read_text()
    assert "prefers-reduced-motion: reduce" in js and "IntersectionObserver" in js  # no autoplay with reduced motion; only on screen

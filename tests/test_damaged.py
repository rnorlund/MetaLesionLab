"""Damaged AI (/damaged, web/damaged_routes.py): the hub of the damage experiments, second in the nav after Draw.

Its first screen asks what happens to an AI's idea of a thing when it is damaged and leads with the damage to Meta's own
open AI, Muse Glimmer (its drawings go first): six pictures of a chair and of a clock, two numbers. A second section
(#sdxl) shows Stable Diffusion XL: the rocking chair that language damage turns into a car, and three numbers. The page's
own scripts run under node in the small stand-in for the browser (tests/firstscreen_dom.js), fed the real
/api/plato/glimmer, /api/plato/damage and /api/plato/ideas, and every picture, number and verdict they draw is checked
against that data here, so nothing on the first screen is typed in. Then one card per damage
result, each opening a section that exists. The Experiments hub on /plato no longer lists the damage experiments."""
import json
import re
import shutil
import subprocess

import pytest
from PIL import Image
from fastapi.testclient import TestClient

from metalesionlab.web import app as web
from metalesionlab.web import damaged_routes, site

NODE = shutil.which("node")
HARNESS = web.HERE.parents[1] / "tests" / "firstscreen_dom.js"
STATIC = web.HERE / "static"
APIS = ("/api/plato/glimmer", "/api/plato/damage", "/api/plato/ideas")


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
    hero = main[:main.index('id="sdxl"')]
    assert "<h1" in hero and "What happens to an AI’s idea of" in hero and "when we damage it?" in hero
    assert 'data-words="a chair|a clock|God"' in hero
    assert "Plato would ask:" in hero  # the series kicker (portraits.kicker_face): his face and these words
    assert ("Damaged AI: we damaged AIs on purpose, starting with Meta’s own open model, Muse Glimmer. We switched off some of "
            "their artificial neurons, or added random noise to them.") in text(hero)
    assert 'data-passage="republic-596a"' in hero  # a verified epigraph: a common name and its idea or form
    assert re.search(r'<p class="fl-answer" id="hero-answer">Damage Meta’s open AI, and its drawings go first: it can still say '
                     r'what a chair is after it can no longer draw one\.</p>', hero)
    assert "data-hero-carousel" in hero  # the picture area is the hero carousel (its first slide is written out)
    for i in ("hero-stats", "hero-qual"):
        assert f'id="{i}"' in hero, i
    assert "/static/js/plato_firstlook.js" in page and "/static/js/statviz.js" in page and "/static/js/plato_damaged.js" in page
    assert "this is a comparison, not a claim about people." in text(hero)
    assert "We predicted before the run that the drawing would go first, and it did" in text(hero)
    assert 'href="/plato/glimmer"' in re.search(r'id="hero-qual">(.*?)</p>', hero, re.S).group(1)
    # the description and the share cards lead with Glimmer, then Stable Diffusion XL
    for pat in (r'<meta name="description" content="([^"]*)"', r'<meta property="og:description" content="([^"]*)"'):
        desc = re.search(pat, page).group(1)
        assert "Muse Glimmer" in desc and desc.index("Muse Glimmer") < desc.index("rocking chair"), pat


def glimmer_cfg(page):
    block = re.search(r'id="film" data-hero-carousel[^>]*>\s*<script type="application/json">(.*?)</script>', page, re.S)
    return json.loads(block.group(1))


def test_the_hero_carousel_is_muse_glimmers_chair_and_clock_least_damage_at_the_left(client):
    page = client.get("/damaged").text
    cfg = glimmer_cfg(page)
    g = json.loads((web.HERE / "data" / "plato_glimmer.json").read_text())
    assert [s["caption"] for s in cfg["slides"]] == ["Muse Glimmer’s chair", "Muse Glimmer’s clock"]
    labels = ["undamaged", "5% off", "10% off", "15% off", "20% off", "30% off"]
    for sl, thing in zip(cfg["slides"], ("chair", "clock")):
        assert sl["href"] == "/plato/glimmer"
        assert [im["label"] for im in sl["images"]] == labels  # 6 images, left to right, least damage first
        assert [im["src"] for im in sl["images"]] == [f"/static/img/plato_glimmer/steps/{thing}_{i}.webp" for i in range(6)]
        for i, im in enumerate(sl["images"]):
            f = STATIC / im["src"][len("/static/"):]
            assert f.is_file() and Image.open(f).size == (300, 300), im["src"]
            assert f"Muse Glimmer’s" in im["alt"] and thing in im["alt"]
            if i:
                assert f"{labels[i].split()[0]} of its neurons switched off" in im["alt"]
            # an answer with no drawing (a grey square in the picture, with words on it): the alt text says so, and only then
            drew = g["marks"][g["damage"][0]["steps"][i]["cond"]][thing]["drew"][g["featured"][thing]] == "1"
            assert ("no drawing came out" in im["alt"]) == (not drew), im["src"]
    # the page shows it without JavaScript: the chair slide, six pictures, same order
    static = re.search(r'<div class="hc-static">(.*?)</div><p class="hc-cap">', page, re.S).group(1)
    assert re.findall(r'<img src="([^"]+)"', static) == [im["src"] for im in cfg["slides"][0]["images"]]
    assert 'href="/plato/glimmer">Muse Glimmer’s chair</a>' in page


def test_no_ai_god_drawing_on_the_damaged_page(client):
    """/draw's "Draw God" must stay blind: only chair and clock steps are cut, and no picture on /damaged is a God."""
    steps = sorted(p.name for p in (STATIC / "img" / "plato_glimmer" / "steps").iterdir())
    assert steps == sorted(f"{t}_{i}.webp" for t in ("chair", "clock") for i in range(6))
    page = client.get("/damaged").text
    srcs = re.findall(r'(?:src|href)="(/static/img/[^"]+)"', page) + re.findall(r'"src":\s*"([^"]+)"', page)
    glimmer = [p for p in srcs if "plato_glimmer" in p]
    assert glimmer and all("/steps/" in p and "god" not in p.lower() for p in glimmer)  # never the sprite that holds God's column
    assert not [p for p in re.findall(r'<img src="([^"]+)"', main_of(page)) if "god" in p.lower()]  # no visible God picture


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
    cfg = {"html": str(tmp_path / "page.html"), "scripts": scripts, "ids": list(ids) + ["hero-how", "sdxl-how"],
           "api": {api: str(tmp_path / f"{api.rsplit('/', 1)[1]}.json") for api in APIS}}
    (tmp_path / "cfg.json").write_text(json.dumps(cfg))
    run = subprocess.run([NODE, str(HARNESS), str(tmp_path / "cfg.json")], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    assert not out["errors"], out["errors"]
    # the qualifiers live in the closed "How we know" disclosure under the numbers: read with them
    for box, how in (("hero-stats", "hero-how"), ("sdxl-stats", "sdxl-how")):
        if box in ids and out["ids"].get(how):
            out["ids"][box] += out["ids"][how]
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


def test_glimmer_numbers_come_from_the_data(client, tmp_path):
    ids, _, _ = first_screen(client, tmp_path, ("hero-stats", "hero-qual"))
    g = json.loads((web.HERE / "data" / "plato_glimmer.json").read_text())
    conds = [st["cond"] for st in g["damage"][0]["steps"]]
    assert conds == ["intact", "all@0.05", "all@0.1", "all@0.15", "all@0.2", "all@0.3"]

    def pooled(cond, key):  # pooled over the chair, the clock and God
        return sum(c[key] for c in g["conditions"][cond].values())
    n = sum(c["n"] for c in g["conditions"]["all@0.2"].values())
    assert n == 36
    s = stats(ids["hero-stats"])
    assert len(s) == 2
    assert s[0][0] == "With a fifth of its neurons switched off"
    assert s[0][1] == [("Drawings an AI could still name", str(pooled("all@0.2", "named")), f"of {n}"),
                       ("Descriptions still right", str(pooled("all@0.2", "correct")), f"of {n}")]
    assert s[1][0] == "At the heaviest damage (30% off)"
    assert s[1][1] == [("Proper sentences", str(pooled("all@0.3", "fluent")), f"of {n}"),
                       ("Right descriptions", str(pooled("all@0.3", "correct")), f"of {n}")]
    # the takes, and the verdict of the pre-registered prediction (the drawing goes first)
    assert "Its words outlasted its drawings." in ids["hero-stats"] and "Some proper sentences, almost no true ones." in ids["hero-stats"]
    assert g["verdict"]["types"]["all"]["verdict"] == "picture first"
    assert re.findall(r'<span class="fl-verdict (\w+)">(.*?)</span>', ids["hero-stats"]) == [("yes", "As predicted")]
    assert f"{n} answers: a chair, a clock and God, 12 each." in ids["hero-stats"]
    for i in (0, 1):
        assert s[i][0] and len(s[i][0].split()) <= 10


def test_numbers_and_verdicts_come_from_the_data(client, tmp_path):
    """Stable Diffusion XL, the second AI: its three numbers and verdicts (now in #sdxl-stats and #sdxl-qual)."""
    ids, d, ideas = first_screen(client, tmp_path, ("sdxl-stats", "sdxl-qual"))
    s = stats(ids["sdxl-stats"])
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
    assert f"Counted by eye instead: +{round(eye['language_rise'] * n)} vs +{round(eye['drawing_rise'] * n)}." in ids["sdxl-stats"]
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
    assert re.findall(r'<span class="fl-verdict (\w+)">(.*?)</span>', ids["sdxl-stats"]) == want
    # and where predictions failed or held only in part, the note says so
    qual = text(ids["sdxl-qual"])
    assert qual.startswith("Partly supported.") and "but the opposite when we switched neurons off" in qual
    proto = d["matched"]["text-zero vs unet-zero"]["delta_d_proto"]  # predicted: back toward the plain chair
    assert not held(proto) and "drift back toward a plain, ordinary chair, as drawings do in semantic dementia" in qual
    assert "Prediction failed." in qual
    farther = d["pooled"]["text-zero"]["delta_d_proto"]["ci95"][0] > 0
    assert ("The chairs wandered farther from the plain chair instead" if farther else "The chairs came no closer to it") in qual
    assert 'href="/plato/damage#diss-h"' in ids["sdxl-qual"] and 'href="/plato/damage#proto-h"' in ids["sdxl-qual"]


def test_the_second_ai_section_follows_the_hero_and_holds_the_sdxl_material(client):
    main = main_of(client.get("/damaged").text)
    assert main.index('id="hero-h"') < main.index('id="sdxl"') < main.index('id="results"')
    sec = main[main.index('id="sdxl"'):main.index('id="results"')]
    assert "<h2" in sec and "A second AI: damage the part that reads words, and a rocking chair becomes a car" in text(sec)
    assert ("Meta’s image AI, Muse Image, runs only on Meta’s servers, so we can’t damage it. Stable Diffusion XL is an open image "
            "AI with two parts, one that reads your words and one that paints the picture, so we damaged each part.") in text(sec)
    for i in ("sdxl-film", "damage-schematic", "sdxl-stats", "sdxl-qual"):
        assert f'id="{i}"' in sec, i
    for i in ("film", "hero-stats", "hero-qual"):
        assert f'id="{i}"' not in sec, i
    assert "How we know" in sec


def test_the_sdxl_picture_is_a_carousel_that_starts_on_the_rocking_chair_that_becomes_a_car(client):
    page = client.get("/damaged").text
    cfg = json.loads(re.search(r'id="sdxl-film" data-hero-carousel[^>]*>\s*<script type="application/json">(.*?)</script>', page, re.S).group(1))
    first = cfg["slides"][0]
    assert first["caption"] == "rocking chair \u2192 car" and len(cfg["slides"]) == 4
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
    assert damaged_routes.CARDS[0]["slug"] == "damaged-glimmer-draws" and cards[0][0] == "/plato/glimmer"  # Meta's own AI first
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
    ids, _, _ = first_screen(client, tmp_path, ("hero-stats", "hero-qual", "sdxl-stats", "sdxl-qual"))
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


def test_no_god_picture_on_either_hub(client):
    """/draw starts on a blind "Draw God", so neither hub shows any AI's picture of God (the ideas card shows death)."""
    for path in ("/damaged", "/plato"):
        pics = re.findall(r'<img src="([^"]+)"', main_of(client.get(path).text))
        assert pics and not [p for p in pics if "god" in p.lower()], path
    card = dict(hub_cards(main_of(client.get("/damaged").text)))["/plato/ideas#damage"]
    assert '<img src="/static/img/plato/hub/damaged-ideas.webp"' in card and "death" in card

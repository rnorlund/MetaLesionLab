"""The invisible Forms: the idea list and prompts, the emblem statistics, the draw pad's AI-only scoring (no
number about people may leak for an idea), the shipped data, the /plato/ideas page and its series card.
A fake embedder stands in for DINOv2, so nothing is downloaded."""
import json
import re

import numpy as np
import pytest
from fastapi.testclient import TestClient

from metalesionlab import draw, plato
from metalesionlab import plato_ideas as I
from metalesionlab.web import app as web
from metalesionlab.web import draw_routes, plato_ideas_routes, site
from metalesionlab.web.limits import DailyLimiter

DATA = web.HERE / "data"
HUMAN_FIELDS = {"d_human", "originality", "people_closer_to_muse", "nearest_human", "d_nearest_human", "looks_like",
                "own_rank", "d_doodle", "xy"}
HEART = [[[50 + 30 * np.sin(t) ** 3 for t in np.linspace(0, 2 * np.pi, 40)],
          [50 - (13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t)) * 2 for t in np.linspace(0, 2 * np.pi, 40)]]]


# --- the ideas and their prompts ------------------------------------------------------------------------

def test_eleven_ideas_god_first_with_the_things_prompt_word_for_word():
    assert [i.key for i in I.IDEAS][0] == "god" and len(I.IDEAS) == 11 and len(I.BY_KEY) == 11
    for idea in I.IDEAS:
        assert I.prompt_for(idea) == plato.STYLES["doodle"].format(phrase=idea.phrase)
        assert idea.predicted in [s for s, _ in idea.emblems]
    assert I.prompt_for(I.BY_KEY["god"]) == ("A quick simple doodle sketch of God, black marker on plain white, like a "
                                             "20-second drawing, no text, no shading.")
    assert {i.group for i in I.IDEAS} == set(I.GROUPS)
    assert {i.key for i in I.IDEAS if i.group == "plato"} == {"beauty", "justice", "the_good"}


def test_no_option_or_prompt_names_a_religion():
    words = " ".join([I.prompt_for(i) for i in I.IDEAS] + [t for i in I.IDEAS for _, t in i.emblems]).lower()
    for name in ("jesus", "christ", "allah", "buddha", "krishna", "vishnu", "shiva", "zeus", "cross", "crescent",
                 "church", "mosque", "temple", "cupid"):
        assert not re.search(rf"\b{name}\b", words), name


def test_options_keep_something_else_and_cant_tell_last():
    god = I.BY_KEY["god"]
    fwd, rev = I.options(god), I.options(god, reverse=True)
    assert fwd[-2:] == rev[-2:] == [I.SOMETHING_ELSE, I.CANT_TELL]
    back = I.reverse_index(len(god.emblems))
    assert [rev[j] for j in range(len(rev))] == [fwd[back[j]] for j in range(len(rev))]
    prompt = I.labeling_prompt(god, fwd)
    assert "A. a man with a beard" in prompt and prompt.endswith("Answer with the letter only.")
    assert len(I.short_names(god)) == len(fwd)


def test_concentration_counts_only_listed_emblems_over_all_pictures():
    em = ["heart", "couple"]
    c = I.concentration(["heart"] * 12 + ["couple"] * 2 + ["something else"] * 2, em)
    assert c["top"] == "heart" and c["top_n"] == 12 and c["share"] == 0.75 and c["distinct"] == 2
    assert I.concentration(["something else"] * 16, em)["share"] == 0.0  # never the top emblem
    assert I.concentration(["couple", "heart"], em)["top"] == "couple"  # ties: alphabetical
    boot = I.bootstrap_concentration(["heart"] * 16, em, 200)
    assert np.all(boot == 1.0)


def test_kappa_and_display():
    assert I.cohen_kappa(list("aabb"), list("aabb")) == 1.0
    assert I.cohen_kappa(list("abab"), list("baba")) < 0
    assert I.display("heart") == "a heart" and I.display("eye") == "an eye" and I.display("broken chains") == "broken chains"
    assert I.display("something else", "Jellyfish.") == "“jellyfish”" and I.display("can't tell", "") == "no clear symbol"


def test_median_difference_ci_and_permutation():
    rng = np.random.default_rng(0)
    hi = [rng.normal(0.4, 0.01, 200) for _ in range(8)]
    lo = [rng.normal(0.2, 0.01, 200) for _ in range(20)]
    _, ci = I.median_diff_ci(hi, lo, 500, rng)
    assert ci[0] > 0.15
    assert I.perm_p_median(np.full(8, 0.4), np.full(20, 0.2) + np.linspace(0, 0.01, 20), 500, rng) < 0.01


# --- AI-only scoring ------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ref():
    return draw.Reference.load(DATA / "draw.json")


def test_ideas_join_the_pad_as_ai_only(ref):
    ideas = [k for k in ref.entries if ref.ai_only(k)]
    assert ideas[0] == "god" and len(ideas) == 11 and not ref.ai_only("chair")
    for k in ideas:
        e = ref.entries[k]
        assert e["n_ai"] == 16 and len(e["ai_loo"]) == len(e["emblems"]) == e["sprites"]["muse"]["n"] == 16
        assert not {"n_human", "human_loo", "human_to_ai", "map", "stats"} & set(e)
        path = web.HERE / e["sprites"]["muse"]["src"].removeprefix("/")
        assert path.is_file() and path.stat().st_size < 120 * 1024
        assert sum(n for _, n in e["emblem_counts"]) == 16 and e["top"]["n"] == e["emblem_counts"][0][1]


def test_ai_only_score_carries_nothing_about_people(ref):
    for k in [k for k in ref.entries if ref.ai_only(k)]:
        c = ref.concept(k)
        assert isinstance(c, draw.IdeaConcept) and c.ai.shape == (16, 768)
        out = ref.score(k, c.ai[5])
        assert set(out) <= draw.AI_ONLY_FIELDS and not HUMAN_FIELDS & set(out), k
        assert out["mode"] == "ai_only" and out["nearest_ai"] == 5 and out["nearest_emblem"] == c.emblems[5]
        # the shipped leave-one-out distances are reproduced by the int8 vectors
        loo = 1 - (draw.unit((c.ai.sum(0) - c.ai) / 15) * c.ai).sum(1)
        assert np.abs(loo - c.ai_loo).max() < 0.01


def test_further_than_k_of_16(ref):
    c = ref.concept("love")
    far = ref.score("love", -c.ai_centroid)
    assert far["muse_closer_n"] == 16 and far["muse_closer"] == 100.0
    near = ref.score("love", c.ai_centroid)
    assert near["muse_closer_n"] == 0 and near["d_ai"] < 1e-6


def test_public_data_marks_ideas_and_keeps_vectors_server_side(ref):
    pub = ref.public()
    ideas = [c for c in pub["concepts"] if c.get("mode") == "ai_only"]
    assert len(ideas) == 11 and all(c["group"] == "ideas" and "vectors" not in c for c in ideas)
    assert [g["id"] for g in pub["groups"]] == ["things", "ideas"] and pub["groups"][1]["label"] == "Draw the invisible:"
    assert len(json.dumps(pub)) < 250_000


class Fake:
    backend = "fake"

    def __init__(self, vec):
        self.vec = vec

    def __call__(self, images):
        return np.stack([self.vec] * len(images))


@pytest.fixture
def client(monkeypatch, ref):
    fake = Fake(ref.concept("god").ai[0])
    monkeypatch.setattr(draw_routes, "embedder", draw.LazyEmbedder(lambda: fake))
    monkeypatch.setattr(draw_routes, "burst", DailyLimiter(window_s=60))
    monkeypatch.setattr(draw_routes, "limiter", DailyLimiter())
    monkeypatch.setattr(draw_routes, "_reference", None)
    c = TestClient(web.app)
    c.fake = fake
    return c


def test_route_scores_an_idea_with_ai_only_fields(client):
    r = client.post("/api/draw", json={"concept": "god", "strokes": HEART, "blind": True, "draw_ms": 5000})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "ai_only" and set(body) <= draw.AI_ONLY_FIELDS and not HUMAN_FIELDS & set(body)
    assert body["nearest_ai"] == 0 and body["nearest_emblem"] == "a bearded man" and body["muse_n"] == 16
    # a thing still gets the people's numbers
    chair = client.post("/api/draw", json={"concept": "chair", "strokes": HEART})
    assert chair.status_code == 200 and "originality" in chair.json() and "mode" not in chair.json()


def test_route_scores_an_uploaded_idea_without_people(client):
    from PIL import Image, ImageDraw
    import io

    img = Image.new("RGB", (600, 600), "white")
    ImageDraw.Draw(img).ellipse((150, 150, 450, 450), outline="black", width=6)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    r = client.post("/api/draw/upload?concept=love", content=buf.getvalue(), headers={"content-type": "image/jpeg"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "upload" and not HUMAN_FIELDS & set(body)
    assert set(body) <= draw.AI_ONLY_FIELDS | {"source", "picture"}


def test_concepts_api_lists_ideas_after_things(client):
    d = client.get("/api/draw/concepts").json()
    keys = [c["key"] for c in d["concepts"]]
    assert keys[0] == "chair" and keys.index("god") > keys.index("book")
    god = next(c for c in d["concepts"] if c["key"] == "god")
    assert god["mode"] == "ai_only" and god["label"] == "God" and god["phrase"] == "God" and "n_human" not in god


def test_pad_script_keeps_people_numbers_out_of_the_idea_view():
    js = (web.HERE / "static" / "js" / "draw.js").read_text()
    block = js[js.index("data-dw=\"idea-tiles\""):js.index("data-dw=\"people-tiles\"")]
    assert "orig-" not in block and "people" not in block.lower() and "human" not in block.lower()
    body = js[js.index("function showIdeaResults"):js.index("function renderEmblems")]
    for field in ("originality", "people_closer_to_muse", "d_human", "nearest_human", "human_loo", "looks_like"):
        assert field not in body, field
    assert "q('socrates-link').hidden = true" in body
    pad_html = js[js.index("var PAD_HTML"):js.index("var RESULTS_HTML")]
    assert "Muse" not in pad_html  # the pad stays blind


def test_draw_page_has_an_ai_only_how_it_works():
    page = TestClient(web.app).get("/draw").text
    main = page[page.index("<main"):page.index("</main>")]
    assert re.search(r'<section class="dw-sec" id="how-ideas"[^>]*hidden', main)
    how = main[main.index('id="how-ideas"'):]
    assert "AI only" in how and "bearded" not in how and "heart" not in how  # no spoiler before the reveal


def test_landing_invites_an_invisible_idea_and_keeps_the_chair():
    landing = TestClient(web.app).get("/").text
    hero = landing[landing.index('id="hero-draw"') - 200:landing.index('id="reveal"')]
    assert "Or draw something no one has seen" in hero
    links = re.findall(r'href="/draw\?thing=(\w+)"', hero)
    assert links[:3] == ["god", "love", "time"]
    assert "16" not in hero and "Is there one ideal chair?" in hero
    js = (web.HERE / "static" / "js" / "landing.js").read_text()
    assert "concept: 'chair'" in js


# --- the page and the series card -------------------------------------------------------------------------

def test_page_and_api_render():
    plato_ideas_routes_cache_clear()
    client = TestClient(web.app)
    r = client.get("/plato/ideas")
    assert r.status_code == 200 and 'id="god-grid"' in r.text and 'id="bars"' in r.text and 'id="spread-chart"' in r.text
    assert r.text.count('<header class="topbar site-head">') == 1 and "{{BRAND}}" not in r.text
    assert 'data-passage="republic-597b"' in r.text  # a verified epigraph
    assert r.text.index('id="god-grid"') < r.text.index('id="grid"')  # God first
    assert "makes no claim about God" in r.text and "We show none of their drawings" in r.text
    a = client.get("/api/plato/ideas").json()
    assert [x["key"] for x in a["ideas"]][0] == "god" and len(a["ideas"]) == 11
    assert a["summary"]["refused_attempts"] == 0 and a["summary"]["pictures"] == 176
    assert a["summary"]["H1"]["passes"] and not a["summary"]["H2"]["passes"] and not a["summary"]["H3_vs_atlas"]["passes"]
    god = a["ideas"][0]
    assert god["top"]["n"] == 16 and god["sprite"]["n"] == 16
    assert (web.HERE / god["sprite"]["src"].removeprefix("/")).is_file()


def plato_ideas_routes_cache_clear():
    from metalesionlab.web import plato_atlas_routes
    plato_atlas_routes._cache.clear()


def test_missing_data_is_a_friendly_503(monkeypatch, tmp_path):
    monkeypatch.setattr(plato_ideas_routes, "DATA", tmp_path / "none.json")
    client = TestClient(web.app)
    assert client.get("/api/plato/ideas").status_code == 503
    assert client.get("/plato/ideas").status_code == 200


def test_series_card_leads_with_god():
    items = {s["path"]: s for s in site.series(web.app)}
    card = items["/plato/ideas"]
    assert card["title"] == "The invisible Forms" and card["finding"].startswith("Asked to draw God")
    assert list(items)[:3] == ["/plato", "/plato/inside", "/plato/ideas"]  # in the first row of cards
    assert not card.get("image")  # the drawn icon: no drawing of God on the landing page before the blind draw
    assert json.loads((DATA / "series" / "ideas.json").read_text())["finding"] == card["finding"]
    landing = TestClient(web.app).get("/").text
    assert 'href="/plato/ideas"' in landing and "The invisible Forms" in landing


def test_public_data_is_statistics_only():
    pub = json.loads((web.HERE.parents[1] / "public_data" / "plato_ideas.json").read_text())
    assert len(pub["ideas"]) == 11 and "statistics only" in pub["license"]
    text = json.dumps(pub)
    assert "base64" not in text and "b64" not in text and ".png" not in text


def test_page_assets_stay_lean():
    html = (web.HERE / "pages" / "plato_ideas.html").read_text()
    script = (web.HERE / "static" / "js" / "plato_ideas.js").read_text()
    css = (web.HERE / "static" / "css" / "plato_ideas.css").read_text()
    assert len(html) + len(script) + len(css) < 100 * 1024
    assert "localStorage" not in script and "fetch(" not in script
    total = sum(p.stat().st_size for p in (web.HERE / "static" / "img" / "plato_ideas").glob("*.webp"))
    assert total < 1.2e6
    assert "clamp(" in css and "max-width: 560px" not in css  # fluid, no narrow fixed column

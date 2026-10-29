"""The clock test (/plato/clock), offline: the prompts fixed in the pre-registration, the persona ages, the MoCA's
three clock points from an eye score or Muse Spark's checklist, agreement, and the guard that keeps anything per
person out of what is published; the page's route, card and hub entry; that nothing shipped from the people's export
holds individual data; the draw pad's clock (mode "group"); and that the page's numbers are the data's and stats.json's."""
import io
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab import draw
from metalesionlab import plato_clock as C
from metalesionlab.plato_damage import CLOCK_KEYS
from metalesionlab.web import app as web
from metalesionlab.web import draw_routes, site
from metalesionlab.web import plato_clock_routes as R
from metalesionlab.web.limits import DailyLimiter

REPO = web.HERE.parents[1]
DATA = web.HERE / "data" / "plato_clock.json"
PAD = web.HERE / "data" / "draw_clock.json"
ABC_IMG = web.HERE / "static" / "img" / "plato_clock" / "abc"
NODE = shutil.which("node")


def test_prompts_keep_the_moca_words():
    moca = "Draw a clock. Put in all the numbers and set the time to 10 past 11."
    assert C.INSTRUCTION == moca
    assert C.IMAGE_PROMPT == moca + " Simple black pen drawing on white paper."
    assert C.SVG_PROMPT.startswith(moca)
    p = C.persona_prompt(34)
    assert p == "Drawn by a 34-year-old: " + C.IMAGE_PROMPT
    # the age and nothing else: no other trait slips into a persona
    assert p.replace("Drawn by a 34-year-old: ", "") == C.IMAGE_PROMPT
    plan = (C.Path(__file__).resolve().parents[1] / "docs" / "plato_clock_plan.md").read_text()
    for prompt in (C.IMAGE_PROMPT, C.SVG_PROMPT):
        assert prompt in plan.replace("*", "")


def test_persona_ages_even_without_the_export():
    ages, rule = C.persona_ages(None)
    assert rule == "even" and ages == list(range(20, 81, 4)) and len(ages) == 16


def test_persona_ages_follow_the_decades():
    decades = [{"lo": 20, "hi": 29, "n": 40}, {"lo": 30, "hi": 39, "n": 40}, {"lo": 40, "hi": 49, "n": 40},
               {"lo": 50, "hi": 59, "n": 120}, {"lo": 60, "hi": 69, "n": 80}, {"lo": 70, "hi": 80, "n": 20}]
    ages, rule = C.persona_ages(decades)
    assert rule == "stratified" and len(ages) == 16 and ages == sorted(ages)
    per = [sum(d["lo"] <= a <= d["hi"] for a in ages) for d in decades]
    assert min(per) >= 1 and per[3] == max(per)  # every decade has a place; the biggest has the most
    assert all(20 <= a <= 80 for a in ages)


@pytest.mark.parametrize("hands,h,m,label", [
    (2, 11, 2, "11:10"), (2, 10, 2, "10:10"), (2, 2, 11, "swapped"), (2, 3, 9, "other"), (1, 11, 2, "none"),
    (2, None, 2, "none"), (2, "11", "2", "11:10"), (2, 23, 14, "11:10"), (2, 0, 2, "other"), (3, 10, 2, "other"),
    (3, 11, 2, "other"),
])
def test_time_label(hands, h, m, label):
    assert C.time_label(hands, h, m) == label


def rubric(**kw):
    r = dict.fromkeys(CLOCK_KEYS)
    r.update(is_clock=True, contour=True, numbers_count=12, numbers_in_order=True, extra_or_wrong_numbers=False, hands=2,
             hour_hand_points_to=11, minute_hand_points_to=2)
    r.update(kw)
    return r


def test_spark_points_follow_the_moca_rules():
    assert C.spark_points(rubric()) == {"contour": True, "numbers": True, "hands": True, "total": 3, "time": "11:10",
                                        "read": True}
    ten = C.spark_points(rubric(hour_hand_points_to=10))
    assert ten["hands"] is False and ten["time"] == "10:10" and ten["total"] == 2
    assert C.spark_points(rubric(numbers_count=11))["numbers"] is False
    assert C.spark_points(rubric(extra_or_wrong_numbers=True))["numbers"] is False
    assert C.spark_points(rubric(numbers_in_order=False))["numbers"] is False
    assert C.spark_points(rubric(hands=3))["hands"] is False
    assert C.spark_points(None) == {"contour": False, "numbers": False, "hands": False, "total": 0, "time": "none",
                                    "read": False}


def test_eye_points_need_the_hands_at_11_and_2():
    e = {"contour": True, "numbers": False, "hands": True, "hands_n": 2, "hour_to": 11, "minute_to": 2, "note": ""}
    assert C.eye_points(e) == {"contour": True, "numbers": False, "hands": True, "total": 2, "time": "11:10"}
    with pytest.raises(ValueError):
        C.eye_points({**e, "hour_to": 10})
    with pytest.raises(ValueError):
        C.eye_points({**e, "contour": None})


def test_agreement_and_kappa():
    eye = [C.eye_points({"contour": True, "numbers": n, "hands": False, "hands_n": 2, "hour_to": 10, "minute_to": 2})
           for n in (True, True, False, False)]
    spark = [C.spark_points(rubric(numbers_count=12 if n else 9, hour_hand_points_to=10)) for n in (True, False, False, False)]
    a = C.agreement(eye, spark)
    assert a["contour"] == {"agree": 4, "n": 4, "kappa": None}  # all yes on both sides: kappa is undefined
    assert a["numbers"]["agree"] == 3 and a["numbers"]["kappa"] == pytest.approx(0.5)
    assert a["time"] == {"agree": 4, "n": 4}


def test_tally_counts_points_and_times():
    s = [C.spark_points(rubric()), C.spark_points(rubric(hour_hand_points_to=10)), C.spark_points(None)]
    t = C.tally(s)
    assert t["hands"]["k"] == 1 and t["contour"]["k"] == 2 and t["times"] == {"11:10": 1, "10:10": 1, "none": 1}
    assert t["all_three"] == 1 and t["mean_total"] == pytest.approx(5 / 3)


@pytest.mark.parametrize("ai,ci,people,verdict", [
    (0.1, [0.05, 0.15], 0.08, "matches"), (0.3, [0.2, 0.4], 0.05, "exaggerates"),
    (-0.1, [-0.2, -0.01], 0.05, "contradicts"), (0.1, [-0.02, 0.2], 0.05, "no clear change"),
])
def test_trend_verdict(ai, ci, people, verdict):
    assert C.trend_verdict(ai, ci, people) == verdict


def test_validate_public_refuses_anything_per_person():
    ok = {"n": 336, "decades": [{"label": "20s", "age_range": [20, 29], "n": 41, "mean_points": 2.6}],
          "quantiles": {"q": [10, 25, 50, 75, 90], "d": [0.1, 0.12, 0.15, 0.2, 0.25]}}
    assert C.validate_public(ok) == []
    bad = {"subject_ids": ["x"], "n": 12, "dob": "1960-01-02", "distances": list(range(300)),
           "groups": [{"participant": 1}], "visit": "3/14/2021"}
    problems = " ".join(C.validate_public(bad))
    for what in ("subject_ids", "a group of 12", "dob", "a list of 300 numbers", "participant", "visit", "looks like a date"):
        assert what in problems, what


# --- the page: route, card and hub entry -----------------------------------------------------------------------

@pytest.fixture(scope="module")
def data():
    return json.loads(DATA.read_text())


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app)


def test_route_serves_the_page_and_its_data(client, data):
    r = client.get("/plato/clock")
    assert r.status_code == 200
    assert 'data-passage="republic-597c"' in r.text and "a third would still appear behind them" in r.text
    assert "<h1 id=\"hero-h\">Would an AI pass the clock test?</h1>" in r.text
    assert client.get("/api/plato/clock").json() == data and R.usable(data)


def test_route_says_so_when_the_data_is_missing(client, monkeypatch, tmp_path):
    monkeypatch.setattr(R, "DATA", tmp_path / "none.json")
    assert client.get("/api/plato/clock").status_code == 503
    assert client.get("/plato/clock").status_code == 200


def test_card_and_hub_entry(client):
    entry = next(s for s in site.SERIES if s["slug"] == "clock")
    assert entry["path"] == "/plato/clock" and entry["question"] == "Would an AI pass the clock test?"
    assert "plato_clock_routes" in web.SITE_ROUTERS["plato"]
    hub = client.get("/plato").text
    card = re.search(r'<a class="hub-card" href="/plato/clock">(.*?)</a>', hub, re.S).group(1)
    assert '/static/img/plato/hub/clock.webp' in card and "Would an AI pass the clock test?" in card
    assert site._esc(site.HUB_ANSWERS["clock"]) in card
    assert (web.HERE / "static" / "img" / "plato" / "hub" / "clock.webp").is_file()
    assert "/plato/clock" in client.get("/plato/inside").text  # the series' More menu lists it


def test_page_says_what_it_is_and_isnt():
    html = (web.HERE / "pages" / "plato_clock.html").read_text()
    js = (web.HERE / "static" / "js" / "plato_clock.js").read_text()
    text = html + js
    assert "not a diagnosis" in text and "isn’t pen and paper" in (web.HERE / "static" / "js" / "draw.js").read_text()
    for banned in ("brain age", "clock age", "Brain age", "Clock age", "impair", "dementia", "abnormal"):
        assert banned not in text, banned
    # the life of a clock puts the AI's personas directly under the people's age groups
    assert html.index('id="decades"') < html.index('id="persona-h"') < html.index('id="personas"')
    order = [html.index(f'id="{s}"') for s in ("points", "form", "life", "draw")]
    assert order == sorted(order)


# --- nothing individual: what came from the people's export ----------------------------------------------------

def test_people_block_is_aggregate_only(data):
    assert C.validate_public(data["people"]) == []
    for d in data["people"]["decades"]:
        assert d["n"] >= C.MIN_GROUP
    for f in data["people"]["form"]:
        assert f["n"] >= C.MIN_GROUP
    for lv in data["people"]["levels"]:
        assert lv["n"] >= C.MIN_GROUP
    # the AI's own clocks may be listed one by one (they are pictures by Muse Image), people's never are
    assert "clocks" not in json.dumps(data["people"])


def test_shipped_averages_are_exactly_the_exports_group_images(data):
    """Only group averages came from the export: 5 steps of "the Form emerges", 6 age groups, 2 clock-point levels."""
    shipped = sorted(p.name for p in ABC_IMG.iterdir())
    used = sorted(Path(x["src"]).name for x in data["people"]["form"] + data["people"]["decades"] + data["people"]["levels"])
    assert shipped == used and len(shipped) == 13
    for p in ABC_IMG.iterdir():
        im = Image.open(p)
        assert im.size == (512, 512) and im.mode == "RGBA"  # an average, as exported: no photo, no crop of anyone's


def test_pad_reference_holds_only_two_centroids_and_quantiles():
    pad = json.loads(PAD.read_text())
    assert set(pad) == {"about", "model", "prep", "concepts", "credits"}
    (c,) = pad["concepts"]
    assert set(c["vectors"]) == {"people_centroid", "ai_centroid"}
    assert all(len(v) == 768 for v in c["vectors"].values())
    assert set(c["quantiles"]) == {"p5", "p10", "p25", "p50", "p75", "p90", "p95"}
    assert c["n_people"] >= C.MIN_GROUP and c["n_people_quantiles"] >= C.MIN_GROUP
    assert set(c["sprites"]) == {"muse"}  # the AI's 16 clocks: the only thumbnails, and none of people's
    rest = {k: v for k, v in c.items() if k not in ("vectors", "sprites")}
    assert C.validate_public(rest) == []
    # no list anywhere but the two 768-number directions is long enough to hold a value per person
    def lists(x):
        if isinstance(x, dict):
            return [y for v in x.values() for y in lists(v)]
        if isinstance(x, list):
            return [x] + [y for v in x for y in lists(v)]
        return []
    assert all(len(x) <= 16 for x in lists(rest))


def id_patterns() -> list[re.Pattern]:
    """The repository's private-data patterns (the main checkout's .githooks/private_patterns.txt, never committed),
    plus generic ones: dates and participant-style IDs."""
    out = [re.compile(r"\b(19|20)\d\d-\d\d-\d\d\b"), re.compile(r"\b(sub|subj|participant|pt)[-_ ]?\d{2,}\b", re.I),
           re.compile(r"\bABC[-_]?\d{2,}\b", re.I), re.compile(r"\bDOB\b")]
    for root in (REPO, REPO.parents[2] if REPO.parent.name == "worktrees" else REPO):
        p = root / ".githooks" / "private_patterns.txt"
        if p.is_file():
            out += [re.compile(line.strip()) for line in p.read_text().splitlines() if line.strip()]
            break
    return out


def test_shipped_clock_data_has_no_id_patterns():
    files = [DATA, PAD, REPO / "public_data" / "plato_clock_byeye.json", web.HERE / "data" / "series" / "clock.json"]
    for f in files:
        text = f.read_text()
        for pat in id_patterns():
            assert not pat.search(text), (f.name, pat.pattern)


# --- the draw pad's clock: mode "group" --------------------------------------------------------------------------

def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def group_concept():
    rng = np.random.default_rng(0)
    people, ai = unit(rng.normal(size=768)), unit(rng.normal(size=768))
    q = {"p5": 0.04, "p10": 0.05, "p25": 0.06, "p50": 0.08, "p75": 0.14, "p90": 0.24, "p95": 0.28}
    return draw.GroupConcept("clock", "clock", people, ai, q, 238)


def test_score_group_says_which_average_is_nearer_and_where():
    c = group_concept()
    near_people = unit(c.people_centroid + 0.05 * c.ai_centroid)
    r = draw.score_group(near_people, c)
    assert r["closer"] == "people" and r["d_people"] < r["d_ai"] and r["mode"] == "group"
    assert draw.score_group(unit(c.ai_centroid + 0.05 * c.people_centroid), c)["closer"] == "ai"
    # a near-tie names no winner
    assert draw.score_group(unit(c.ai_centroid + c.people_centroid), c)["closer"] == "both"
    assert set(r) == draw.GROUP_FIELDS


@pytest.mark.parametrize("d,band", [(0.01, [0, 5]), (0.07, [25, 50]), (0.2, [75, 90]), (0.5, [95, 100]), (0.08, [50, 75])])
def test_quantile_band(d, band):
    assert draw.quantile_band(d, group_concept().quantiles) == band


def test_reference_loads_the_clock_as_a_group():
    ref = draw.Reference.load()
    assert ref.group("clock") and not ref.ai_only("clock") and not ref.group("chair")
    pub = next(c for c in ref.public()["concepts"] if c["key"] == "clock")
    assert pub["mode"] == "group" and "vectors" not in pub and pub["instruction"] == C.INSTRUCTION
    assert "n_human" not in pub and "people" not in pub.get("sprites", {})  # no people's thumbnails
    c = ref.concept("clock")
    assert c.people_centroid.shape == (768,) and abs(np.linalg.norm(c.ai_centroid) - 1) < 1e-6


def test_face_normalise_centres_and_scales_the_face():
    img = Image.new("RGB", (400, 300), "white")
    from PIL import ImageDraw

    g = ImageDraw.Draw(img)
    g.ellipse((60, 40, 260, 240), outline="black", width=4)  # a face of radius 100 at (160, 140)
    g.line((160, 140, 120, 75), fill="black", width=4)
    g.line((160, 140, 230, 100), fill="black", width=4)
    out = C.face_normalise(img)
    a = np.asarray(out.convert("L")) < 128
    ys, xs = np.nonzero(a)
    assert out.size == (256, 256)
    assert abs((xs.min() + xs.max()) / 2 - 128) < 6 and abs((ys.min() + ys.max()) / 2 - 128) < 6
    assert abs((xs.max() - xs.min()) / 2 - 0.40 * 256) < 6  # the face's radius is 0.40 of the side


class Fake:
    backend = "fake"

    def __init__(self, vec):
        self.vec = vec

    def __call__(self, images):
        assert all(im.size == (256, 256) for im in images)
        return np.stack([self.vec] * len(images))


@pytest.fixture
def pad_client(monkeypatch):
    ref = draw.Reference.load()
    fake = Fake(ref.concept("clock").people_centroid)
    monkeypatch.setattr(draw_routes, "embedder", draw.LazyEmbedder(lambda: fake))
    monkeypatch.setattr(draw_routes, "burst", DailyLimiter(window_s=60))
    monkeypatch.setattr(draw_routes, "limiter", DailyLimiter())
    monkeypatch.setattr(draw_routes, "_reference", None)
    return TestClient(web.app)


def clock_strokes():
    circle = [[500 + 400 * math.cos(2 * math.pi * i / 60) for i in range(61)],
              [500 + 400 * math.sin(2 * math.pi * i / 60) for i in range(61)]]
    return [circle, [[500, 380], [500, 300]], [[500, 640], [500, 400]]]


def test_pad_route_scores_a_clock_with_group_fields_only(pad_client):
    r = pad_client.post("/api/draw", json={"concept": "clock", "strokes": clock_strokes(), "blind": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) <= draw.GROUP_FIELDS and body["closer"] == "people" and body["d_people"] < 1e-6
    assert body["band"] == [0, 5] and body["n_people"] == 238


def test_pad_route_scores_an_uploaded_clock(pad_client):
    img = Image.new("RGB", (600, 600), "white")
    from PIL import ImageDraw

    ImageDraw.Draw(img).ellipse((150, 150, 450, 450), outline="black", width=6)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    r = pad_client.post("/api/draw/upload?concept=clock", content=buf.getvalue(), headers={"content-type": "image/jpeg"})
    assert r.status_code == 200, r.text
    assert set(r.json()) <= draw.GROUP_FIELDS | {"source", "picture"}


def test_pad_script_keeps_the_clock_free_of_scores_and_people():
    js = (web.HERE / "static" / "js" / "draw.js").read_text()
    block = js[js.index('data-dw="group-tiles"'):js.index("<article class=\"dw-card dw-share\">")]
    for word in ("score", "%", "originality", "nearest_human"):
        assert word not in block, word
    body = js[js.index("function showGroupResults"):js.index("function groupChart")]
    for field in ("originality", "people_closer_to_muse", "nearest_human", "human_loo", "sprites.people"):
        assert field not in body, field
    assert "This is not a test, and drawing on a screen isn’t pen and paper." in body
    assert "q('socrates-link').hidden = true" in body
    assert "if (S.timerStart || isGroup(current())) return;" in js  # the clock test has no 20-second timer


# --- the numbers: the page's are the data's, and the data's are stats.json's --------------------------------------

def test_data_numbers_match_the_scores(data):
    eye = {k: v for k, v in json.loads((REPO / "public_data" / "plato_clock_byeye.json").read_text()).items()
           if not k.startswith("_")}
    for name, key in (("muse", "default"), ("persona", "persona")):
        scores = [C.eye_points(eye[f"{key}/{c['file']}"]) for c in data[name]["clocks"]]
        assert C.tally(scores)["hands"]["k"] == data[name]["eye"]["hands"]["k"]
        assert C.tally(scores)["times"] == data[name]["eye"]["times"]
    assert data["persona"]["ages"] == [c["age"] for c in data["persona"]["clocks"]]


def test_people_numbers_match_stats_json(data):
    stats = C.load_public()
    if not stats:
        pytest.skip("the private export isn't on this machine")
    P = data["people"]
    assert P["n_analysed"] == stats["n"]["baseline_analysed"] and P["n_images"] == stats["n"]["images"]
    assert P["full_points"]["k"] == stats["validation"]["distance_by_clock_points"]["3 (full)"]["n"]
    assert P["spread"] == stats["ai_and_public_clocks"]["human_moca_clocks"]["spread"]
    for d, s in zip(P["decades"], stats["by_decade"]):
        assert (d["age_range_years"], d["n"], d["share_full"], d["mean_points"], d["spread"], d["distance"]) == (
            s["age_range_years"], s["n"], s["share_full_clock_points"], s["mean_clock_points"], s["spread"],
            s["distance_to_typical"])
    assert P["age_trend"] == stats["age_trend"]
    ref = json.loads((C.PUBLIC_DIR / "drawing_pad_reference.json").read_text())
    pad = json.loads(PAD.read_text())["concepts"][0]
    assert np.allclose(pad["vectors"]["people_centroid"], unit(ref["centroid"]), atol=1e-5)
    assert pad["quantiles"] == {k: v for k, v in ref["distance_quantiles_all"].items() if k.startswith("p")}


def test_first_screen_numbers_come_from_the_data(data):
    """plato_clock.js's first screen, run under node on the real data: its numbers are the data's."""
    if not NODE:
        pytest.skip("node is not installed")
    script = web.HERE / "static" / "js" / "plato_clock.js"
    run = subprocess.run([NODE, "-e", f"const P=require({json.dumps(str(script))});"
                                      f"process.stdout.write(JSON.stringify(P.firstLook({json.dumps(data)})))"],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    fl = json.loads(run.stdout)
    full, M = data["people"]["full_points"], data["muse"]
    people, muse, points = fl["stats"]
    assert (people["o"]["k"], people["o"]["n"]) == (full["k"], full["n"]) and people["o"]["value"] == f"{round(100 * full['k'] / full['n'])}%"
    assert (muse["o"]["k"], muse["o"]["n"]) == (M["eye"]["times"].get("11:10", 0), M["n"])
    assert points["o"]["value"] == f"{M['eye']['contour']['k']} · {M['eye']['numbers']['k']} · {M['eye']['hands']['k']}"
    assert f"on {M['eye']['all_three']} of its {M['n']} clocks" in fl["answer"]
    assert "never the 10:10 of watch adverts" in fl["answer"] if not M["eye"]["times"].get("10:10") else "10:10 of watch adverts on" in fl["answer"]
    # plain language: what a visitor reads on the first screen carries no unexplained jargon
    shown = " ".join([fl["answer"], fl["note"]] + [s["q"] + " " + s["o"]["label"] for s in fl["stats"]])
    for word in JARGON:
        assert not re.search(word, shown), word
    assert str(M["agreement"]["hands"]["agree"]) in muse["q"] + points["q"]
    hub = site.HUB_ANSWERS["clock"]
    assert f"{M['eye']['times']['11:10']} of {M['n']}" in hub and str(data["people"]["n_analysed"]) in hub


# Words the plain-language guide (docs/style_plain_language.md) keeps out of what visitors read, unless explained.
JARGON = [r"\brho\b", r"\bCI\b", r"\bcentroid", r"\bembedding", r"\bSDXL\b", r"\bkappa\b", r"[Pp]re-registered", r"\bn = ",
          r"\bquantile", r"\bpercentile", r"\bcosine\b", r"\bp = ", r"\bcontour\b"]


def test_page_text_is_plain():
    """The page's visible words, outside the method notes (which define their terms), avoid the guide's jargon, and
    name Meta's models in full the first time."""
    html = (web.HERE / "pages" / "plato_clock.html").read_text()
    body = html[html.index("<main"):html.index('id="method"')]
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<!--.*?-->", " ", body, flags=re.S))
    for word in JARGON:
        assert not re.search(word, text), word
    assert "Meta’s image AI, Muse Image" in text and "Meta’s chat AI, Muse Spark" in text
    assert "Stable Diffusion XL, an open image AI from Stability AI" in text
    js = (web.HERE / "static" / "js" / "plato_clock.js").read_text()
    js = re.sub(r"/\*.*?\*/", " ", js, flags=re.S)
    js = re.sub(r"(?m)^\s*//.*$|\s//\s.*$", " ", js)  # comments aren't shown to anyone
    strings = " ".join(re.findall(r"'((?:[^'\\\n]|\\.)*)'", js))  # the script's quoted text
    for word in JARGON:
        assert not re.search(word, strings), word
    assert "Meta’s Muse Wonder, an AI that writes drawing code" in strings

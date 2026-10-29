"""The first screen of six series pages (/plato/cave, cratylus, bird, damage, telephone, lifespan): the question,
one striking picture, a one-sentence answer, and at most three headline numbers drawn as small graphics, each with its
qualifier and, for a planned prediction, how it came out. They share the card and the drawing helper of the first four
pages (plato_firstlook.css and FirstLook.render in plato_firstlook.js), so all ten read alike. Each page's scripts run under node in a small stand-in for the browser
(tests/firstscreen_dom.js), fed the real API response, and the numbers they draw are checked against the same data
here, so a headline can't drift from the results or be typed in by hand."""
import json
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web

NODE = shutil.which("node")
HARNESS = web.HERE.parents[1] / "tests" / "firstscreen_dom.js"
CSS = web.HERE / "static" / "css" / "plato_firstscreen.css"
PAGES = {"cave": "/api/plato/cave", "cratylus": "/api/plato/cratylus", "bird": "/api/plato/bird",
         "damage": "/api/plato/damage", "telephone": "/api/plato/telephone", "lifespan": "/api/plato/lifespan"}
EPIGRAPH = {"cave": "republic-518b", "cratylus": "cratylus-439b", "bird": "theaetetus-155d", "damage": "timaeus-28a",
            "telephone": "republic-597e", "lifespan": "meno-85c"}


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app)


def api_data(client, page):
    r = client.get(PAGES[page])
    if r.status_code != 200:
        pytest.skip(f"{PAGES[page]} has no data on this machine")
    return r.json()


def first_screen(client, page, tmp_path, ids=("hero-stats", "hero-answer", "hero-qual")):
    """Run the page's own scripts on its real data; {id: outerHTML} for the ids asked for."""
    if not NODE:
        pytest.skip("node is not installed")
    data = api_data(client, page)
    html = client.get(f"/plato/{page}").text
    scripts = [web.HERE / "static" / "js" / s for s in re.findall(r'<script src="/static/js/([\w.-]+?\.js)', html)]
    (tmp_path / "page.html").write_text(html)
    (tmp_path / "api.json").write_text(json.dumps(data))
    cfg = {"html": str(tmp_path / "page.html"), "scripts": [str(s) for s in scripts],
           "api": {PAGES[page]: str(tmp_path / "api.json")}, "ids": list(ids) + ["hero-how"]}
    (tmp_path / "cfg.json").write_text(json.dumps(cfg))
    run = subprocess.run([NODE, str(HARNESS), str(tmp_path / "cfg.json")], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    out = json.loads(run.stdout)
    for i in ids:
        assert out["ids"][i] is not None, (page, i, out["errors"])
    # the qualifiers live in the closed "How we know" disclosure under the numbers: read with them
    if "hero-stats" in ids and out["ids"].get("hero-how"):
        out["ids"]["hero-stats"] += out["ids"]["hero-how"]
    return out["ids"], data


def stats(html):
    """The headline graphics in #hero-stats: [(number, unit, caption, kind)]."""
    items = re.findall(r'<figure class="fl-stat">(.*?)</figure>', html, re.S)
    out = []
    for it in items:
        num = re.search(r'<span class="sv-num">(.*?)</span>', it)
        unit = re.search(r'<span class="sv-unit">(.*?)</span>', it)
        cap = re.search(r'<p class="sv-cap">(.*?)</p>', it)
        kind = re.search(r'class="sv sv-(\w+)', it)
        out.append((num and num.group(1), unit and unit.group(1).strip(), cap and cap.group(1), kind and kind.group(1)))
    return out


def text(html):
    return re.sub(r"<[^>]+>", "", html)


def verdicts(html):
    """How the planned predictions came out, in order: [(tone, words)]."""
    return re.findall(r'<span class="fl-verdict (\w+)">(.*?)</span>', html)


# --- the shape every first screen shares ------------------------------------------------------------------------

@pytest.mark.parametrize("page", sorted(PAGES))
def test_first_screen_leads_with_question_picture_answer_and_numbers(client, page):
    src = (web.HERE / "pages" / f"plato_{page}.html").read_text()
    hero = re.search(r'<section class="fl fl-side [\w-]+".*?</section>', src, re.S)
    assert hero, page
    h = hero.group(0)
    # the question, as before: the kicker and the page's question, then the verified epigraph right under it
    assert "What would Plato ask an AI?" in h and 'class="kicker-q"' in h
    assert re.search(r'<div class="title-pair">.*?</div>\s*<!--#epigraph:' + EPIGRAPH[page] + "-->", h, re.S)
    # then, as on the first four pages: the introduction, the answer, one picture, the numbers and the note
    order = [h.index(x) for x in ('class="fl-ctx"', 'class="fl-answer"', 'class="fl-visual', 'id="hero-stats"', 'class="fl-note"')]
    assert order == sorted(order)
    assert h.count('class="fl-answer"') == 1 and h.count('class="fl-visual') == 1
    # the graphics and the shared helper, linked before the page's own script; the card's sheet before this one
    js = [src.index(f"/static/js/{f}") for f in ("statviz.js", "plato_firstlook.js", f"plato_{page}.js")]
    assert js == sorted(js)
    assert src.index("/static/css/plato_firstlook.css") < src.index("/static/css/plato_firstscreen.css")
    assert "/static/css/statviz.css" in src


@pytest.mark.parametrize("page", sorted(PAGES))
def test_page_serves_its_first_screen_assets(client, page):
    html = client.get(f"/plato/{page}").text
    for path in re.findall(r'(?:href|src)="(/static/(?:css|js)/[\w.-]+)', html):
        assert client.get(path).status_code == 200, (page, path)


def test_first_screen_css_uses_colour_tokens_only():
    css = CSS.read_text()
    hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", css)
    assert set(hexes) <= {"#fbfaf5"}, hexes  # only the --paper fallback the dark theme may replace
    assert all(f"var(--paper, {h})" in css for h in hexes)
    assert not re.findall(r"\brgba?\(", css)
    lead = (web.HERE / "static" / "js" / "plato_lifespan_lead.js").read_text()
    assert not re.findall(r"#[0-9a-fA-F]{6}\b", lead)


# --- each page's headline numbers, drawn from its data -----------------------------------------------------------

def test_cave_first_screen(client, tmp_path):
    ids, d = first_screen(client, "cave", tmp_path, ("hero-stats", "hero-answer", "hero-qual", "hero-pairs"))
    sh = d["accuracy"]["shadow"]
    named = round(sh["accuracy"] * sh["n"])
    m, e, hs = d["medium_answers"]["shadow"], d["errors"]["shadow"], d["human"]["silhouette"]
    s = stats(ids["hero-stats"])
    assert len(s) == 3
    assert s[0][:2] == (str(named), f"of {sh['n']}") and s[0][3] == "dots"
    acc = d["accuracy"]  # planned: drawing > outline ≈ silhouette > shadow, silhouettes 15 points below the drawings
    o_, s_ = acc["outline"]["accuracy"], acc["silhouette"]["accuracy"]
    order = acc["original"]["accuracy"] >= max(o_, s_) and min(o_, s_) > sh["accuracy"]
    p1 = ("yes", "As predicted") if order and -acc["silhouette"]["diff_vs_original"] >= 0.15 else (
        ("part", "Partly as predicted") if order else ("no", "Prediction failed"))
    rho_held = d["human"]["silhouette"]["rho_correct"]["ci95"][0] > 0
    assert verdicts(ids["hero-stats"]) == [p1, ("yes", "As predicted") if rho_held else ("no", "Prediction failed")]
    assert s[1][:2] == (str(m["just_shadow"]), f"of {e['n_errors']}") and "Shadow" in s[1][2]
    assert s[2][0] == f"{round(hs['ai_accuracy_on_shared'] * 100)}%" and s[2][1] == f"vs {round(hs['people_mean_on_shared'] * 100)}%"
    assert ids["hero-stats"].count('class="sv-on sv-ink"') == named  # one filled dot per shadow it named
    # the answer names the AI in full: it is read before the introduction that would otherwise say who "it" is
    assert f"Meta’s open AI model, Muse Glimmer, named {named} of {sh['n']} shadows" in text(ids["hero-answer"])
    pairs = ids["hero-pairs"]  # shadows beside the drawings that cast them, with what the AI said
    assert pairs.count('class="cv-pair ') == 6 and pairs.count("/static/img/plato_cave/shadow_") == 6
    assert pairs.count("/static/img/plato_cave/original_") == 6 and "“" not in pairs.split("Glimmer: ")[0]
    rho = hs["rho_correct"]["rho"]  # the link between people's and the AI's hard shapes, in plain words, from the data
    assert f"{rho:.2f} on a scale from −1 to 1" in text(ids["hero-stats"]) and "Muse Spark" in text(ids["hero-qual"])  # qualifiers, from the data


def test_cratylus_first_screen(client, tmp_path):
    ids, d = first_screen(client, "cratylus", tmp_path)
    w = {x["word"]: x for x in d["words"]}
    corners = lambda k: round(w[k]["share_with_corners"] * w[k]["n"])
    s = stats(ids["hero-stats"])
    assert len(s) == 3
    assert s[0][:2] == (str(corners("kiki")), f"of {w['kiki']['n']}")
    assert s[1][:2] == (str(corners("keti") + corners("tepi")), f"of {w['keti']['n'] + w['tepi']['n']}")
    assert s[2][0] == f"{round(d['choice']['spark_both_match']['p'] * 100)}%"
    assert s[2][1] == f"vs {round(d['people']['both_trials_match'] * 100)}%"
    assert "no preference for “kiki”" in text(ids["hero-stats"])
    assert f"rests on {d['choice']['spark_both_match']['n']} paired answers" in text(ids["hero-qual"])
    # the verdicts of the pre-registered predictions ride with the numbers; keti and tepi broke one
    v = verdicts(ids["hero-stats"])
    assert v[0] == ("yes", "As predicted")
    assert v[1] == (("yes", "As predicted") if d["contrasts"]["spiky_vs_round_class"]["solidity"]["diff_ci"][0] > 0
                    else ("no", "Prediction failed"))
    assert v[2] == ("part", "Partly as predicted")  # Muse Spark matched both words as often as people; Glimmer didn't
    assert "Muse Spark, did. Meta’s open AI model, Glimmer, didn’t" in text(ids["hero-stats"])


def test_bird_first_screen(client, tmp_path):
    ids, d = first_screen(client, "bird", tmp_path, ("hero-stats", "hero-answer", "hero-qual", "hero-shares"))
    dom = d["summary"]["spark"]["dominance"]
    bird = next(c for c in d["categories"] if c["category"] == "bird")
    pic = d["pictures"]["bird"]["spark"]
    s = stats(ids["hero-stats"])
    assert len(s) == 3
    assert s[0][:2] == (f"{round(dom['ai_mean']['mean'] * 100)}%", f"vs {round(dom['human_mean']['mean'] * 100)}%")
    glim = d["summary"]["glimmer_T1.0"]["dominance"]  # Glimmer is not as narrow, and the verdict says so
    assert f'{round(glim["ai_mean"]["mean"] * 100)}</span>' in ids["hero-stats"]
    if dom["diff"]["ci95"][0] > 0 and glim["diff"]["ci95"][0] <= 0:
        assert verdicts(ids["hero-stats"])[0] == ("part", "Partly as predicted")
        # the sentence beside the verdict says what was predicted and which half held
        assert "We predicted both AIs would stick to one favourite more than people do. Muse Spark did." in text(ids["hero-stats"])
        assert "Muse Glimmer, at its standard randomness setting, was as varied as people." in text(ids["hero-stats"])
    assert s[1][:2] == (str(dom["n_ai_higher"]), f"of {dom['n']}")
    assert s[2][:2] == (str(pic["top_count"]), f"of {len(pic['labels'])}")
    top = bird["tables"]["spark"][0]
    assert f"“{top[0]}” {top[1]} times in" in text(ids["hero-answer"])
    assert f"named {bird['human']['distinct']} different birds" in text(ids["hero-answer"])
    shares = ids["hero-shares"]  # one bar per source, a piece per answer
    assert shares.count('class="pb-share ') == 3
    people = re.search(r'class="pb-share people".*?</div></div>', shares, re.S).group(0)
    assert people.count('class="pb-piece') == len(bird["tables"]["human_first"])


def test_damage_first_screen(client, tmp_path):
    ids, d = first_screen(client, "damage", tmp_path, ("hero-stats", "hero-answer", "hero-qual"))
    kc = d["matched"]["text-zero vs unet-zero"]["delta_correct"]
    s = stats(ids["hero-stats"])
    assert len(s) == 3
    assert s[0][:2] == (f"{round(-kc['language'] * 100)} vs {round(-kc['drawing'] * 100)}", "pts")
    pz = d["pooled"]["text-zero"]["delta_d_proto"]
    assert s[1][0] == ("Farther" if pz["ci95"][0] > 0 else "No closer")
    c = d["clocks"]
    fi = c["feature_names"].index("12 numbers in order")
    intact = next(r for r in c["features"] if r["cond"] == "intact")
    mild = min((r for r in c["features"] if r["cond"].startswith("unet-zero@")), key=lambda r: float(r["cond"].split("@")[1]))
    assert s[2][0] == f"{round(intact['values'][fi] * 100)}% → {round(mild['values'][fi] * 100)}%"
    # the verdicts are shown, and the failed prediction is not dressed up
    assert verdicts(ids["hero-stats"]) == [("yes", "As predicted"), ("no", "Prediction failed")]
    assert text(ids["hero-qual"]).startswith("Partly supported.") and "reversed for neurons switched off" in text(ids["hero-qual"])
    page = client.get("/plato/damage").text  # the picture area is the hero carousel; one of its slides is a clock losing its numbers
    assert "data-hero-carousel" in page and "clock_8_45_intact.webp" in page and "clock_8_45_unet-noise_3.webp" in page


def test_telephone_first_screen(client, tmp_path):
    ids, d = first_screen(client, "telephone", tmp_path, ("hero-stats", "hero-qual", "hero-chains"))
    seeds = {x["key"]: x for x in d["seeds"]}
    chairs = [c for c in d["chains"] if not seeds[c["seed"]]["control"]]
    away = sum(c["d_proto"][-1] > c["d_proto"][0] for c in chairs)
    t2, t3 = d["tests"]["P2_convergence"], d["tests"]["P3_kind_first"]
    s = stats(ids["hero-stats"])
    assert len(s) == 3
    assert s[0][:2] == (str(away), f"of {len(chairs)}")
    assert s[1][:2] == (f"{t2['g10']:.2f}", f"from {t2['g0']:.2f}")
    assert s[2][0] == f"{t3['first_loss_kind']['mean']:.1f} vs {t3['first_loss_category']['mean']:.1f}"
    hs = ids["hero-stats"]
    assert ("Prediction failed" in hs) == (not d["tests"]["P1_drift_to_form"]["supported"])
    chains = ids["hero-chains"]  # the two striking chains, start and every second copy, beside the textbook chair
    st = d["striking"]
    for pick in ("farthest_from_start", "most_drift_to_form"):
        assert d["sprites"][f"{st[pick]['seed']}_c{st[pick]['chain']}"] in chains
    assert len(re.findall(r'class="tp-drift-row(?: fell)?"', chains)) == 2 and chains.count("default_chair.webp") == 2
    assert chains.count('class="tp-drift-row fell"') == 1  # the high chair's chain ends at the textbook chair


def test_lifespan_first_screen(client, tmp_path):
    ids, d = first_screen(client, "lifespan", tmp_path)
    c, ad, ai = d["children"]["curves"], d["adults"]["mean_over_children_things"], d["ai"]["all"]
    s = stats(ids["hero-stats"])
    assert len(s) == 2
    r2, r10 = round(c["recog"]["mean"][0] * 100), round(c["recog"]["mean"][-1] * 100)
    assert s[0][0] == f"{r10}%" and s[0][1] == f"at 10, from {r2}% at 2"
    t = ai["tests"]["d_adult"]["last_minus_first"]
    clear = t["ci95"][0] > 0 or t["ci95"][1] < 0
    assert s[1][0] == ("No closer" if not clear else "Farther" if t["mean"] > 0 else "Closer")
    assert f"adults {round(ad['recog'] * 100)}%" in text(ids["hero-stats"])
    words = {True: ("yes", "As predicted"), False: ("no", "Prediction failed")}
    assert verdicts(ids["hero-stats"]) == [words[d["children"]["predictions"]["C1_recognizability_rises"]],
                                           words[ai["predictions"]["A3_d_adult_changes"]]]
    # beside each verdict, in plain words, what was predicted; the yearly gain with its range in words
    slope = d["children"]["tests"]["recog"]["linear"]
    hs = text(ids["hero-stats"])
    assert "We predicted children’s drawings would get easier to recognize with age" in hs
    assert f"up {slope['mean_slope'] * 100:.1f} points a year (probably between {slope['ci95'][0] * 100:.1f} and {slope['ci95'][1] * 100:.1f})" in hs
    assert "We predicted more training would change how far its pictures are from people’s drawings" in hs
    # still never a child's drawing on the first screen
    src = (web.HERE / "pages" / "plato_lifespan.html").read_text()
    hero = re.search(r'<section class="fl fl-side ls-hero".*?</section>', src, re.S).group(0)
    assert set(re.findall(r"/static/img/plato_lifespan/([\w.]+)", hero)) == {
        "chair_adults.webp", "chair_muse.webp", "chair_sd_v11.webp", "chair_sd_v15.webp"}

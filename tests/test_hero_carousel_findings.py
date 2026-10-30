"""The two shared page components, static/js/hero-carousel.js and static/js/findings.js (docs/components.md), and their pilots:
/plato/damage (the carousel plus five finding cards) and /damaged (the carousel).

Markup and no-JS contracts are read from the served pages. The behaviour (rendering from data, ARIA, one card open at a
time, the URL hash, reduced motion, the numbers on the page) runs in a real browser: system python3 with Playwright
against a local server; skipped where either is missing."""
import json
import re
import shutil
import socket
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web

STATIC = web.HERE / "static"
DATA = json.loads((web.HERE / "data" / "plato_damage.json").read_text())


@pytest.fixture(scope="module")
def client():
    return TestClient(web.app_for("plato"))


def carousel_cfg(page):
    """The Stable Diffusion XL carousel: /plato/damage's only one, and /damaged's #sdxl-film (its first screen now leads with
    Muse Glimmer's own two-slide carousel, #film, with 6 steps per slide: tests/test_damaged.py checks that one)."""
    sdxl = re.search(r'id="sdxl-film" data-hero-carousel[^>]*>\s*<script type="application/json">(.*?)</script>', page, re.S)
    return json.loads((sdxl or re.search(r'data-hero-carousel[^>]*>\s*<script type="application/json">(.*?)</script>', page, re.S)).group(1))


@pytest.mark.parametrize("path", ["/plato/damage", "/damaged"])
def test_the_carousel_data_is_complete_and_its_pictures_exist(client, path):
    page = client.get(path).text
    cfg = carousel_cfg(page)
    assert len(cfg["slides"]) == 4
    for s in cfg["slides"]:
        assert 0 < len(s["caption"].split()) <= 10
        assert len(s["images"]) >= 4
        for im in s["images"]:
            assert im["alt"] and (STATIC / im["src"][len("/static/"):]).is_file(), im["src"]
    assert [s["caption"] for s in cfg["slides"]][0] == "rocking chair → car"
    assert "/static/js/hero-carousel.js" in page and "/static/css/hero-carousel.css" in page


@pytest.mark.parametrize("path", ["/plato/damage", "/damaged"])
def test_the_row_slides_render_every_available_step(client, path):
    page = client.get(path).text
    assert re.search(r'data-hero-carousel data-layout="row"', page) and "fl-wide" in page
    steps = [len(s["images"]) for s in carousel_cfg(page)["slides"]]
    assert steps == [10, 10, 10, 10]  # each row: undamaged + 9 doses, same picture (docs/plato_damage.md, denser rows)
    start = page.index('id="sdxl-film"') if 'id="sdxl-film"' in page else 0
    first = re.search(r'<div class="hc-static">.*?</p></div>', page[start:], re.S).group(0)  # the no-JS first slide shows all of its steps
    assert first.count('class="hc-pic"') == steps[0] and f'--n:{steps[0]}' in first


def test_the_carousel_without_javascript_shows_its_first_slide(client):
    page = client.get("/plato/damage").text
    static = re.search(r'<div class="hc-static">.*?</p></div>', page, re.S).group(0)
    assert static.count("<img") == 10 and "rocking chair" in static and "hidden" not in static


def test_the_findings_are_in_the_page_each_with_its_h3_more_detail_and_the_old_sections(client):
    page = client.get("/plato/damage").text
    ids = re.findall(r'<article class="fd-item" id="finding-([a-z-]+)"', page)
    assert ids == ["words-or-painting", "plain-chair", "looks", "draws-and-reads", "clocks"]
    titles = re.findall(r'<article class="fd-item"[^>]* data-title="([^"]+)" data-line="([^"]+)"', page)
    assert [t for t, _ in titles] == ["Words part or painting part?", "Back to the plain chair?", "The AI that looks",
                                      "One AI that draws and reads", "Clocks"]
    for t, line in titles:
        assert len(t.split()) <= 6 and len(line.split()) <= 10, (t, line)
    assert page.count('class="how-we-know fd-more"') == 5
    for must in ('id="slider"', 'id="diss-charts"', 'id="proto"', 'id="glim"', 'id="janus"', 'id="clocks"', 'id="diss-caveat"',
                 'id="diss-h"', 'id="proto-h"', 'id="glim-h"', 'id="janus-h"', 'id="clock-h"', 'id="janus-sec"',
                 "Stable Diffusion XL base 1.0", "semantic dementia", "Muse Spark"):
        assert must in page, must
    for js in ("/static/js/findings.js", "/static/css/findings.css"):
        assert js in page


def test_the_usage_notes_and_the_components_doc_exist():
    for f in ("hero-carousel.js", "findings.js"):
        head = (STATIC / "js" / f).read_text()[:3500]
        assert "USAGE" in head and "BEHAVIOUR" in head
    doc = (web.HERE.parents[1] / "docs" / "components.md").read_text()
    assert "HeroCarousel.mount" in doc and "Findings.render" in doc


def test_the_stylesheets_use_colour_tokens_only():
    for f in ("hero-carousel.css", "findings.css"):
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", (STATIC / "css" / f).read_text()), f


# --- in a real browser ---------------------------------------------------------------------------------------------

BROWSER = r'''
import json, sys
from playwright.sync_api import sync_playwright
B = sys.argv[1]
out = {}
with sync_playwright() as p:
    br = p.chromium.launch()
    errs = []
    ctx = br.new_context(viewport={"width": 1280, "height": 800})
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(B + "/plato/damage?nosplash=1"); pg.wait_for_selector(".fd-card"); pg.wait_for_timeout(1500)
    out["carousel"] = pg.evaluate("""() => { const r = document.querySelector('.hc');
      return {role: r.getAttribute('role'), rd: r.getAttribute('aria-roledescription'), label: r.getAttribute('aria-label'),
        slides: [...r.querySelectorAll('.hc-slide')].map(s => [s.getAttribute('role'), s.getAttribute('aria-roledescription'), s.getAttribute('aria-label')]),
        dots: r.querySelectorAll('.hc-dot').length, dotLabel: r.querySelector('.hc-dot').getAttribute('aria-label'),
        buttons: [...r.querySelectorAll('button')].every(b => b.getAttribute('aria-label')), toggle: !!r.querySelector('.hc-toggle'),
        hiddenInert: [...r.querySelectorAll('.hc-slide:not(.is-active)')].every(s => s.getAttribute('aria-hidden') === 'true')}; }""")
    out["cards"] = pg.evaluate("""() => [...document.querySelectorAll('.fd-card')].map(b => [b.tagName, b.getAttribute('aria-expanded'),
      !!document.getElementById(b.getAttribute('aria-controls')), b.id])""")
    out["panel_region"] = pg.evaluate("""() => { const p = document.querySelector('.fd-item'); return [p.getAttribute('role'), p.getAttribute('aria-labelledby') === document.querySelector('.fd-card').id]; }""")
    out["badge_in_summary"] = pg.evaluate("document.querySelectorAll('.fd-more > summary .pt-aristotle').length")
    # one open at a time
    pg.click(".fd-card >> nth=0"); pg.click(".fd-card >> nth=2")
    out["open_after_two"] = pg.evaluate("[...document.querySelectorAll('.fd-card')].map(b => b.getAttribute('aria-expanded'))")
    out["hash"] = pg.evaluate("location.hash")
    pg.keyboard.press("Enter")  # the focused open card closes
    out["closed_by_key"] = pg.evaluate("document.querySelectorAll('.fd-card[aria-expanded=true]').length")
    # the numbers
    out["hero_stats"] = pg.inner_text("#hero-stats")
    out["card_nums"] = pg.evaluate("""() => ['diss','proto','clocks'].map(k => { const h = document.getElementById('fd-num-' + k);
      const l = h.querySelector('.fd-num-l'), v = h.querySelector('.fd-num-v');
      return [h.hidden, v.textContent, h.querySelector('.fd-verdict').textContent, l.textContent,
        !!(l.compareDocumentPosition(v) & Node.DOCUMENT_POSITION_FOLLOWING)]; })""")
    # pause on hover, and play/pause
    pg.hover(".hc"); out["held"] = pg.evaluate("document.querySelector('.hc').classList.contains('is-held')")
    pg.mouse.move(2, 2); pg.click(".hc-toggle"); out["stopped"] = pg.evaluate("document.querySelector('.hc').classList.contains('is-stopped')")
    pg.click(".hc-next"); out["after_next"] = pg.evaluate("[...document.querySelectorAll('.hc-dot')].findIndex(d => d.getAttribute('aria-current') === 'true')")
    # rendering from data, with the APIs
    out["api"] = pg.evaluate("""() => { const h = document.createElement('div'); document.body.appendChild(h);
      const c = HeroCarousel.mount(h, {slides: [{caption: 'a \\u2192 b', images: [{src: '/static/img/favicon.svg', alt: 'x', label: 'one'}]},
        {caption: 'c', images: [{src: '/static/img/favicon.svg', alt: 'y'}]}]});
      const g = document.createElement('div'); document.body.appendChild(g);
      const f = Findings.render(g, [{id: 't1', title: 'One', line: 'Line one.', img: '', h3: 'One', text: ['A.', 'B.'], number: {value: '5', label: 'things', verdict: {tone: 'yes', text: 'As predicted'}}, extra: '<p id=\\"zz\\">chart</p>', more: '<p>method</p>'},
        {id: 't2', title: 'Two', line: 'Line two.', img: '', text: ['C.']}]);
      f.open('t2');
      return {slides: h.querySelectorAll('.hc-slide').length, cap: h.querySelector('.hc-cap').textContent, goes: (c.go(1), h.querySelectorAll('.hc-slide')[1].classList.contains('is-active')),
        cards: g.querySelectorAll('.fd-card').length, open: f.current(), t2: g.querySelector('#finding-t2').getAttribute('aria-hidden'), t1: g.querySelector('#finding-t1').getAttribute('aria-hidden'),
        num: g.querySelector('.fd-num-v').textContent, more: g.querySelectorAll('.fd-more > summary .pt-aristotle').length}; }""")
    out["errors"] = errs
    # hash opens a card
    p2 = ctx.new_page(); p2.goto(B + "/plato/damage?nosplash=1#finding-clocks"); p2.wait_for_selector(".fd-card"); p2.wait_for_timeout(500)
    out["hash_open"] = p2.evaluate("document.getElementById('finding-clocks').classList.contains('is-open')")
    p3 = ctx.new_page(); p3.goto(B + "/plato/damage?nosplash=1#diss-h"); p3.wait_for_selector(".fd-card"); p3.wait_for_timeout(500)
    out["inner_hash_open"] = p3.evaluate("document.getElementById('finding-words-or-painting').classList.contains('is-open')")
    # no JavaScript
    nj = br.new_context(java_script_enabled=False, viewport={"width": 1280, "height": 800}).new_page()
    nj.goto(B + "/plato/damage?nosplash=1")
    out["nojs"] = nj.evaluate("""() => ({static: getComputedStyle(document.querySelector('.hc-static')).display !== 'none', imgs: document.querySelectorAll('.hc-static img').length,
      cards: document.querySelectorAll('.fd-card').length, panels: [...document.querySelectorAll('.fd-item')].every(e => e.getBoundingClientRect().height > 40 && getComputedStyle(e).visibility === 'visible')})""")
    # reduced motion
    rm = br.new_context(reduced_motion="reduce", viewport={"width": 1280, "height": 800}).new_page()
    rm.goto(B + "/plato/damage?nosplash=1"); rm.wait_for_selector(".hc-dot"); rm.wait_for_timeout(8500)
    out["reduced"] = rm.evaluate("""() => [document.querySelectorAll('.hc-toggle').length, [...document.querySelectorAll('.hc-dot')].findIndex(d => d.getAttribute('aria-current') === 'true'),
      getComputedStyle(document.querySelector('.hc-slide')).transitionDuration, getComputedStyle(document.querySelector('.fd-item')).transitionDuration]""")
    # the hub
    hub = ctx.new_page(); hub.goto(B + "/damaged?nosplash=1"); hub.wait_for_selector(".hc-dot"); hub.wait_for_timeout(500)
    out["hub"] = hub.evaluate("[document.querySelectorAll('.hc-slide').length, document.querySelectorAll('.dm-hub a').length > 3]")  # Glimmer's 2 slides + Stable Diffusion XL's 4
    br.close()
print(json.dumps(out))
'''


@pytest.fixture(scope="module")
def browser_run(tmp_path_factory):
    py = shutil.which("python3")
    if not py:
        pytest.skip("no system python3")
    if subprocess.run([py, "-c", "import playwright"], capture_output=True).returncode:
        pytest.skip("playwright is not installed for the system python3")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "metalesionlab.web.app:app", "--port", str(port), "--log-level", "warning"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                break
            except OSError:
                time.sleep(0.25)
        script = tmp_path_factory.mktemp("br") / "run.py"
        script.write_text(BROWSER)
        r = subprocess.run([py, str(script), f"http://127.0.0.1:{port}"], capture_output=True, text=True, timeout=180)
        if r.returncode:
            pytest.skip("the browser could not run: " + r.stderr[-300:])
        yield json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        srv.terminate()


def test_browser_carousel_aria_and_controls(browser_run):
    c = browser_run["carousel"]
    assert (c["role"], c["rd"]) == ("region", "carousel") and c["label"]
    assert c["slides"][0] == ["group", "slide", "1 of 4"] and len(c["slides"]) == 4
    assert c["dots"] == 4 and c["dotLabel"] == "Slide 1 of 4" and c["buttons"] and c["toggle"] and c["hiddenInert"]
    assert browser_run["held"] is True and browser_run["stopped"] is True and browser_run["after_next"] == 1


def test_browser_cards_aria_one_open_hash_and_keyboard(browser_run):
    assert len(browser_run["cards"]) == 5
    assert all(t == "BUTTON" and e == "false" and ok for t, e, ok, _ in browser_run["cards"])
    assert browser_run["panel_region"] == ["region", True]
    assert browser_run["badge_in_summary"] == 5
    assert browser_run["open_after_two"] == ["false", "false", "true", "false", "false"] and browser_run["hash"] == "#finding-looks"
    assert browser_run["closed_by_key"] == 0
    assert browser_run["hash_open"] is True and browser_run["inner_hash_open"] is True


def test_browser_the_components_render_from_data(browser_run):
    a = browser_run["api"]
    assert a == {"slides": 2, "cap": "a → b", "goes": True, "cards": 2, "open": "t2", "t2": "false", "t1": "true", "num": "5", "more": 1}


def test_browser_without_javascript_everything_shows(browser_run):
    n = browser_run["nojs"]
    assert n == {"static": True, "imgs": 10, "cards": 0, "panels": True}


def test_browser_reduced_motion_never_moves_or_animates(browser_run):
    n, idx, d1, d2 = browser_run["reduced"]
    assert n == 0 and idx == 0 and d1 == "0s" and d2 == "0s"


def test_browser_no_console_errors_and_the_hub_has_the_carousel_and_its_cards(browser_run):
    assert browser_run["errors"] == []
    assert browser_run["hub"] == [6, True]


def test_browser_the_key_numbers_from_the_data_are_on_the_page(browser_run):
    kc = DATA["matched"]["text-zero vs unet-zero"]["delta_correct"]
    want = f"{round(-kc['language'] * 100)} pts"
    assert want in browser_run["hero_stats"] and f"{round(-kc['drawing'] * 100)} pts" in browser_run["hero_stats"]
    diss, proto, clocks = browser_run["card_nums"]
    assert diss[0] is False and want in diss[1] and diss[2] == "As predicted"
    assert all(c[3] and c[4] for c in (diss, proto, clocks)), "each card names what was measured before its value"
    pz = DATA["pooled"]["text-zero"]["delta_d_proto"]
    assert f"{DATA['pooled']['text-zero']['delta_d_proto']['mean']:.2f}" in proto[1]
    c = DATA["clocks"]
    fi = c["feature_names"].index("12 numbers in order")
    intact = next(r for r in c["features"] if r["cond"] == "intact")
    mild = min((r for r in c["features"] if r["cond"].startswith("unet-zero@")), key=lambda r: float(r["cond"].split("@")[1]))
    assert f"{round(intact['values'][fi] * 100)}%" in clocks[1] and f"{round(mild['values'][fi] * 100)}%" in clocks[1]

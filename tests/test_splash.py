"""The opening animation (static/js/splash.js, static/css/splash.css) and the Replay intro control on the landing page:
captions are held for their reading time, the style param picks one of three styles (default one constant), the replay
control is in the markup near the top (not in the hidden hero links), and reduced motion never autoplays."""
import json
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web

STATIC = web.HERE / "static"
JS = (STATIC / "js" / "splash.js").read_text()
CSS = (STATIC / "css" / "splash.css").read_text()
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def home():
    return TestClient(web.app_for("plato")).get("/").text


def _read_ms(text: str) -> int:
    code = re.search(r"function words\(.*?\n  function readMs\(.*?\n", JS, re.S).group(0)
    out = subprocess.run([NODE, "-e", code + f"console.log(readMs({json.dumps(text)}))"], capture_output=True, text=True, check=True)
    return int(out.stdout)


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_reading_time_is_the_longer_of_2_5_s_and_0_4_s_a_word_plus_1_2_s():
    assert _read_ms("One ideal chair?") == 2500  # 3 words: 2.4 s, so the floor
    assert _read_ms("a b c d e f g h i j") == 5200  # 10 words
    assert _read_ms("a b c<cite>Plato, Republic 515c</cite>") == 2500  # the citation is not read
    q = re.search(r"var Q515 = '(.*?)' \+\n\s+'(<cite>.*?)';", JS, re.S)
    assert _read_ms(q.group(1) + q.group(2)) == 400 * 16 + 1200


def test_every_caption_hold_waits_at_least_its_reading_time():
    assert "function hold(id, html, mode, veil, ms) { say(html, mode, veil); return wait(300 + (ms || readMs(html)), id); }" in JS
    assert "TIME" not in JS  # the old 0.8 speed-up is gone
    assert "var TIME" not in JS and "ms * TIME" not in JS
    # style c's short lines are held 2.5-3.05 s; everything else uses hold() with no override
    for ms in re.findall(r"hold\(id, C\d, '\w+', \w+, (\d+)\)", JS):
        assert 2500 <= int(ms) <= 3000


def test_the_style_param_and_one_default_constant():
    assert re.search(r"var DEFAULT_STYLE = '[abc]';", JS)
    assert "style=([abc])" in JS
    for fn in ("playA", "playB", "playC"):
        assert f"function {fn}(id)" in JS
    assert "STYLE === 'b' ? playB : STYLE === 'c' ? playC : playA" in JS
    assert DEFAULT_IS_A()


def DEFAULT_IS_A():
    return "var DEFAULT_STYLE = 'a';" in JS


def test_style_c_lines_and_verified_quotes():
    for line in ("Plato said every chair is a copy of one ideal chair.", "We only ever see the shadows.", "What would Plato ask an AI?"):
        assert line in JS
    # the two quotes are the verified Jowett wording, untouched
    assert "the truth would be literally nothing but the shadows of the images" in JS
    assert "Whenever a number of individuals have a common name, we assume them to have also a corresponding idea or form" in JS


def test_skip_esc_click_and_reduced_motion():
    assert "Skip intro" in JS and "e.key === 'Escape'" in JS and "stage.addEventListener('click'" in JS
    assert "sp-continue" in JS and ".sp-continue" in CSS and ".splash.static" in CSS


def test_the_replay_control_is_in_the_markup_near_the_top(home):
    m = re.search(r'<a class="replay-intro" href="/\?splash=1" data-replay>', home)
    assert m and "Replay intro" in home[m.end():m.end() + 300]
    assert m.start() < home.index('class="hero hero-draw"')  # before the hero, not among the hero links
    assert "hero-replay" not in home  # the old, buried link is gone
    assert not re.search(r"\.replay-intro[^{]*\{[^}]*display:\s*none", (STATIC / "css" / "landing.css").read_text())


def test_the_head_script_never_autoplays_with_reduced_motion(home):
    head = home[:home.index("</head>")]
    assert "(still && !asked)) return" in head
    assert "splash-static" in head


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_shadow_projection_leans_away_from_the_light():
    code = re.search(r"  function projectShadow\(.*?\n  \}\n", JS, re.S).group(0)
    out = subprocess.run([NODE, "-e", code + "const W=1000,lx=920,d=600,f=x=>projectShadow(x,lx,d,W);"
                          "console.log(JSON.stringify([f(lx),f(800),f(500),f(-250),f(lx+80)]))"], capture_output=True, text=True, check=True)
    at, mid, far, edge, right = json.loads(out.stdout)
    assert at["skew"] == 0 and at["blur"] > far["blur"] and at["scale"] > far["scale"]
    assert 0 < mid["skew"] < far["skew"] <= 25 and edge["skew"] <= 25 and right["skew"] < 0
    assert abs(far["x"] - 920) > abs(500 - 920)  # the shadow runs faster than its object

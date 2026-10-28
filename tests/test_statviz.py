"""statviz (static/js/statviz.js and static/css/statviz.css): the headline-number graphics. The markup is built
by pure string functions, so node can render every kind here without a browser; the CSS may use the site's colour
tokens only (a dark theme redefines the tokens)."""
import json
import re
import shutil
import subprocess

import pytest

from metalesionlab.web import app as web

JS = web.HERE / "static" / "js" / "statviz.js"
CSS = web.HERE / "static" / "css" / "statviz.css"
NODE = shutil.which("node")


def render(calls: dict) -> dict:
    """{name: [kind, opts]} -> {name: html}, rendered by statviz.js under node."""
    code = (f"const S = require({json.dumps(str(JS))}); const calls = {json.dumps(calls)}; const out = {{}};"
            "for (const [k, [kind, o]] of Object.entries(calls)) {"
            "  try { out[k] = S.html(kind, o); } catch (e) { out[k] = 'ERROR: ' + e.message; } }"
            "out.kinds = S.kinds; console.log(JSON.stringify(out));")
    run = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_usage_note_heads_the_file():
    head = JS.read_text()[:4000]
    assert head.startswith("/* statviz")
    for word in ('data-sv="dots"', 'data-sv="spread"', 'data-sv="layers"', 'data-sv="bars"', "StatViz.render",
                 "StatViz.html", "statviz.css"):
        assert word in head, word


def test_css_uses_colour_tokens_only():
    css = CSS.read_text()
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", css), "statviz.css: use the colour tokens, not hex"
    assert not re.findall(r"\brgba?\(", css)
    assert "prefers-reduced-motion: no-preference" in css  # the entrance plays only when motion is welcome
    for token in ("var(--blue)", "var(--orange)", "var(--ink)", "var(--line-2)"):
        assert token in css


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_every_kind_renders_from_its_data():
    out = render({
        "dots": ["dots", {"k": "34", "n": "35", "label": "things drawn more alike"}],
        "spread": ["spread", {"a": "0.09", "b": "0.54", "aLabel": "Muse Image", "bLabel": "People"}],
        "layers": ["layers", {"at": "36", "n": "52"}],
        "one": ["layers", {"at": "3", "n": "11", "mode": "one", "tone": "orange"}],
        "bars": ["bars", {"values": "0.13,0.36", "labels": "Muse Image,People", "digits": "2"}],
        "custom": ["dots", {"k": 83, "n": 100, "value": "83%"}],
        "hidden": ["dots", {"k": 2, "n": 4, "value": ""}],
        "bad": ["pie", {}],
    })
    assert out["kinds"] == ["dots", "spread", "layers", "bars"]

    dots = out["dots"]  # 34 filled dots and one ring, the number and the caption
    assert len(re.findall(r'class="sv-on sv-blue"', dots)) == 34 and dots.count('class="sv-off"') == 1
    assert '<span class="sv-num">34</span><span class="sv-unit"> of 35</span>' in dots
    assert 'aria-label="34 of 35 things drawn more alike"' in dots and '<p class="sv-cap">things drawn more alike</p>' in dots

    spread = out["spread"]  # two clusters of 16; people's ring 6 times the radius of Muse Image's
    assert spread.count("sv-on sv-blue") == 16 and spread.count("sv-on sv-orange") == 16
    assert '<span class="sv-num">6×</span>' in spread
    rings = [float(r) for r in re.findall(r'class="sv-ring" cx="50" cy="50" r="([\d.]+)"', spread)]
    assert len(rings) == 2 and rings[0] < rings[1]
    assert "Muse Image <b>0.09</b>" in spread and "People <b>0.54</b>" in spread

    layers = out["layers"]  # 52 segments, 36 to 52 filled, a marker, the ends labelled
    assert layers.count("<rect") == 52 and layers.count("sv-on sv-blue") == 17
    assert 'class="sv-mark"' in layers and "<span>1</span><span>52</span>" in layers
    assert '<span class="sv-num">36</span><span class="sv-unit"> of 52</span>' in layers
    assert out["one"].count("sv-on sv-orange") == 1 and out["one"].count("<rect") == 11

    bars = out["bars"]  # one scale: the larger bar is full
    assert re.findall(r'style="width:([\d.]+)%', bars) == ["36.1", "100"]
    assert '<span class="sv-num">2.8×</span>' in bars and bars.count('class="sv-bar"') == 2

    assert '<span class="sv-num">83%</span>' in out["custom"] and "sv-unit" not in out["custom"]
    assert "sv-val" not in out["hidden"]
    assert out["bad"].startswith("ERROR: statviz: unknown kind")


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_text_is_escaped():
    out = render({"x": ["dots", {"k": 1, "n": 2, "label": '<b>"x"</b>'}]})["x"]
    assert "<b>" not in out and "&lt;b&gt;&quot;x&quot;&lt;/b&gt;" in out

"""The colour theme: Plato's Chair is dark by default with a sun/moon switch in its header (light is one press
away, kept in localStorage); the Lingua site stays light with no switch. Colours are tokens (app.css), so the
Plato site's own stylesheets carry no hex colours, and its charts take their colours from the tokens too."""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from metalesionlab.web import app as web
from metalesionlab.web import site

STATIC = Path(web.__file__).resolve().parent / "static"
CSS = STATIC / "css"
JS = STATIC / "js"

PLATO_PAGES = ["/", "/draw", "/plato", "/plato/inside", "/plato/damage", "/plato/cave", "/plato/gallery", "/socrates"]
LINGUA_PAGES = ["/", "/take", "/scorer", "/lab", "/ask"]

# Every stylesheet the Plato site uses besides the shared app.css (which holds the token definitions).
PLATO_CSS = sorted({p.name for p in CSS.glob("plato*.css")} | {
    "landing.css", "draw.css", "tour.css", "splash.css", "portraits.css", "epigraph.css", "gallery-strip.css", "socrates.css",
    "statviz.css", "quote-carousel.css"} & {p.name for p in CSS.glob("*.css")})
# Charts and pictures drawn by the Plato site's scripts. Hex colours are allowed only where a picture is
# meant to look the same in every theme: the drawing pad and the share card (paper and ink, draw.js) and the
# opening animation's chair (splash.js), which is drawn on paper.
PLATO_JS = sorted({p.name for p in JS.glob("plato*.js")} | {"draw.js", "landing.js", "gallery-strip.js", "splash.js", "statviz.js",
                                                             "quote-carousel.js"}
                  & {p.name for p in JS.glob("*.js")})
JS_ALLOW = {
    "draw.js": {"#FFFFFF", "#111827", "#374151", "#4B5563", "#F7F6F1", "#9A3412", "#C2410C", "#1D4ED8", "#0D9488"},
    "splash.js": {"#141a26", "#F9FAFB", "#C2410C"},
}

HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b(?![\w-])")  # not an id selector such as #bed-table
RGB = re.compile(r"rgba?\(([^)]*)\)")
NEUTRAL_RGB = re.compile(r"^\s*(0,\s*0,\s*0|255,\s*255,\s*255)\s*(,\s*[\d.]+\s*)?$")  # black or white, any alpha


def _strip_css(text: str) -> str:
    """A stylesheet without comments, custom-property definitions (the tokens) or a token's fallback
    (var(--paper, #fbfaf5) uses the token; the fallback only matters where app.css is missing)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"var\((--[\w-]+)\s*,[^()]*\)", r"var(\1)", text)
    return re.sub(r"--[\w-]+\s*:[^;{}]*;?", "", text)


@pytest.fixture(scope="module")
def plato():
    return TestClient(web.app_for("plato"))


@pytest.fixture(scope="module")
def lingua():
    return TestClient(web.app_for("lingua"))


@pytest.mark.parametrize("path", PLATO_PAGES)
def test_plato_site_is_dark_by_default(plato, path):
    page = plato.get(path).text
    assert re.search(r'<html[^>]* data-theme="dark"', page), path
    head = page[page.index("<head"):page.index("</head>")]
    # the stored choice is applied in <head>, before any stylesheet, so there is no flash of the other theme
    assert site.THEME_SCRIPT in head
    assert head.index(site.THEME_SCRIPT) < head.index("stylesheet")


@pytest.mark.parametrize("path", PLATO_PAGES)
def test_plato_header_has_a_labelled_theme_switch(plato, path):
    page = plato.get(path).text
    head = re.search(r'<header class="topbar site-head">.*?</header>', page, re.S).group(0)
    buttons = re.findall(r"<button[^>]*data-theme-toggle[^>]*>", head)
    # one in the bar, and the same switch as a row of the phone menu (shown where the bar has no room)
    assert [re.search(r'class="([^"]+)"', b).group(1) for b in buttons] == ["nav-theme", "theme-toggle"], path
    for button in buttons:
        assert 'type="button"' in button
        assert re.search(r'aria-label="Switch to (light|dark) theme"', button)


def test_theme_script_survives_without_storage():
    """Every storage access is guarded, and the switch fires an event charts can listen for."""
    script = site.THEME_SCRIPT
    assert script.count("localStorage") == 2
    assert script.count("try{") >= 3
    for access in re.findall(r"localStorage\.\w+\([^)]*\)", script):
        before = script[:script.index(access)]
        assert before.rfind("try{") > before.rfind("}catch"), access
    assert "themechange" in script and site.THEME_KEY in script


@pytest.mark.parametrize("path", LINGUA_PAGES)
def test_lingua_site_stays_light_without_a_switch(lingua, path):
    page = lingua.get(path).text
    assert re.search(r'<html[^>]* data-theme="light"', page), path
    assert "data-theme-toggle" not in page
    assert site.THEME_SCRIPT not in page


def test_each_page_gets_one_theme_attribute(plato):
    page = plato.get("/plato").text
    assert len(re.findall(r'data-theme="(?:dark|light)"', page.split("</head>")[0])) == 1


def test_app_css_defines_both_themes():
    css = (CSS / "app.css").read_text()
    light = re.search(r':root, :root\[data-theme="light"\] \{(.*?)\n\}', css, re.S).group(1)
    dark = re.search(r':root\[data-theme="dark"\] \{(.*?)\n\}', css, re.S).group(1)
    names = lambda block: set(re.findall(r"(--[\w-]+)\s*:", block))
    portrait = {n for n in names(dark) if n.startswith("--portrait-")}
    assert names(light) == names(dark) - portrait, "every colour token needs a light and a dark value"
    for token in ("--paper", "--paper-ink", "--chart-bg", "--chart-grid", "--ground-warm", "--on-ink", "--bar", "--tip"):
        assert token in names(light)
    # outside the token blocks, app.css uses no hex colours either
    rules = _strip_css(css)
    assert not HEX.findall(rules), HEX.findall(rules)


@pytest.mark.parametrize("name", PLATO_CSS)
def test_plato_stylesheets_use_tokens_not_hex(name):
    rules = _strip_css((CSS / name).read_text())
    assert not HEX.findall(rules), f"{name}: {sorted(set(HEX.findall(rules)))}"
    tinted = [m for m in RGB.findall(rules) if not NEUTRAL_RGB.match(m)]
    assert not tinted, f"{name}: rgb() colours should be tokens: {tinted}"


@pytest.mark.parametrize("name", PLATO_JS)
def test_plato_charts_read_colours_from_tokens(name):
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", (JS / name).read_text(), flags=re.S)
    found = set(m for m in re.findall(r"['\"](#[0-9A-Fa-f]{3,8})['\"]", text))
    extra = found - JS_ALLOW.get(name, set())
    assert not extra, f"{name}: hex colours {sorted(extra)}; use 'var(--token)' (or a class)"

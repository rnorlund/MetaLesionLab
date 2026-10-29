"""The shared motion layer (static/css/motion.css, static/js/motion.js, added to every Plato page by site.py) and the
animate-on-view hook in statviz.js. What is checked here: the layer is on every Plato page and on no Lingua page; it
hides nothing unless a script has said motion is welcome (no script, or prefers-reduced-motion, shows every page as it
was); the reduced-motion path exists; colours are tokens; statviz still draws its final values with no animation at
all; and the hover previews' strips match the frame counts the stylesheet steps through."""
import json
import re
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from metalesionlab.web import app as web
from metalesionlab.web import site

STATIC = web.HERE / "static"
CSS = STATIC / "css" / "motion.css"
JS = STATIC / "js" / "motion.js"
SV = STATIC / "js" / "statviz.js"
SV_CSS = STATIC / "css" / "statviz.css"
NODE = shutil.which("node")

PLATO_PAGES = ["/", "/draw", "/plato", "/plato/inside", "/plato/damage", "/plato/cave", "/plato/gallery", "/socrates"]
LINGUA_PAGES = ["/", "/take", "/lab"]


@pytest.fixture(scope="module")
def plato():
    return TestClient(web.app_for("plato"))


@pytest.fixture(scope="module")
def lingua():
    return TestClient(web.app_for("lingua"))


def _strip(css: str) -> str:
    """Comments and custom-property definitions out, as tests/test_theme.py does."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"var\((--[\w-]+)\s*,[^()]*\)", r"var(\1)", css)
    return re.sub(r"--[\w-]+\s*:[^;{}]*;?", "", css)


def _rules(css: str):
    """(selector, body) for every innermost rule, keyframe steps left out."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"@keyframes[^{]*\{(?:[^{}]*\{[^{}]*\})*\s*\}", "", css)
    return [(s.strip(), b) for s, b in re.findall(r"([^{}@;]+)\{([^{}]*)\}", css)]


# --- the layer is on every Plato page, before anything else could hide ---------------------------------------------

@pytest.mark.parametrize("path", PLATO_PAGES)
def test_every_plato_page_loads_the_motion_layer(plato, path):
    r = plato.get(path)
    assert r.status_code == 200, path
    head = r.text[:r.text.index("</head>")]
    assert re.search(r'<link rel="stylesheet" href="/static/css/motion\.css\?v=\d+">', head), path
    assert re.search(r'<script src="/static/js/motion\.js\?v=\d+" defer></script>', head), path
    assert site.MOTION_BOOT in head and head.index(site.MOTION_BOOT) < head.index("/static/js/motion.js"), path
    assert head.count("/static/js/motion.js") == 1, path
    # the theme still comes first, so there is no flash of the other theme
    assert head.index(site.THEME_SCRIPT) < head.index("motion.css")


@pytest.mark.parametrize("path", LINGUA_PAGES)
def test_the_lingua_site_has_no_motion_layer(lingua, path):
    page = lingua.get(path).text
    assert "motion.css" not in page and "motion.js" not in page and site.MOTION_BOOT not in page


def test_the_motion_assets_are_served(plato):
    for path in ("/static/css/motion.css", "/static/js/motion.js"):
        assert plato.get(path).status_code == 200, path


# --- nothing hidden without the script, and nothing moves with reduced motion -------------------------------------

@pytest.mark.parametrize("path", PLATO_PAGES)
def test_served_pages_carry_no_hidden_state(plato, path):
    """The no-JS page: no motion class in the markup itself, so every block is visible as served."""
    page = plato.get(path).text
    html_tag = re.search(r"<html\b[^>]*>", page).group(0)
    assert "mo" not in re.findall(r'class="([^"]*)"', html_tag + " ")[:1], path
    body = page[page.index("<body"):]
    for cls in ("mo-r", "mo-in", "mo-boot", "mo-prefly", "sv-wait"):
        assert not re.search(r'class="[^"]*\b%s\b' % cls, body), (path, cls)


def test_hiding_needs_the_class_a_script_adds():
    """Every rule in motion.css that makes content transparent hangs off html.mo or html.mo-boot (set by the boot
    script only when motion is welcome), or is a decoration of its own (a preview or a pulse, ::before/::after)."""
    hiding = [(s, b) for s, b in _rules(CSS.read_text()) if re.search(r"(?<![\w-])opacity:\s*0(?![.\d])", b)]
    assert hiding
    for sel, _ in hiding:
        parts, depth, cur = [], 0, ""
        for ch in sel:  # the selector list's own commas, not those inside :is(...)
            depth += (ch == "(") - (ch == ")")
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        for part in parts + [cur]:
            part = part.strip()
            assert part.startswith(("html.mo", "html.mo-boot")) or "::after" in part or "::before" in part, part


def test_the_boot_script_waits_for_permission_and_gives_up_safely():
    boot = site.MOTION_BOOT
    assert "prefers-reduced-motion: reduce" in boot and "IntersectionObserver" in boot and "motion=0" in boot
    # the classes are added only after those checks, and removed again if motion.js never runs
    assert boot.index("prefers-reduced-motion") < boot.index("classList.add('mo','mo-boot')")
    assert re.search(r"setTimeout\(function\(\)\{if\(!window\.PCMotion\)d\.classList\.remove\('mo','mo-boot'\);\},\d+\)", boot)
    js = JS.read_text()
    assert "if (!html.classList.contains('mo')) return;" in js  # no boot class: motion.js does nothing at all
    assert "function fail(" in js and "off();" in js  # an error shows everything again


def test_reduced_motion_path_exists():
    css = CSS.read_text()
    reduce = css[css.index("@media (prefers-reduced-motion: reduce)"):]
    assert "animation: none !important" in reduce and ".mo-r { opacity: 1 !important; }" in reduce
    # every looping or entrance animation outside html.mo sits behind prefers-reduced-motion: no-preference
    for sel, body in _rules(css):
        if "animation" in body and "animation: none" not in body and not sel.startswith("html.mo"):
            at = css.index(body)
            opened = css.rfind("@media (prefers-reduced-motion: no-preference)", 0, at)
            assert opened >= 0 and css.count("{", opened, at) > css.count("}", opened, at), sel
    assert "prefers-reduced-motion: no-preference" in SV_CSS.read_text()
    assert re.search(r"@media print \{[^}]*\.mo-r \{ opacity: 1 !important", css)  # a printout shows everything


def test_the_tour_sees_every_block():
    css = CSS.read_text()
    assert "html.tour-on .mo-r { opacity: 1 !important; animation: none !important; }" in css


# --- colours, and what moves -----------------------------------------------------------------------------------------

def test_motion_uses_colour_tokens_only():
    rules = _strip(CSS.read_text())
    assert not re.findall(r"#[0-9A-Fa-f]{3,8}\b(?![\w-])", rules)
    assert not re.findall(r"\brgba?\(", rules)
    js = re.sub(r"/\*.*?\*/|//[^\n]*", "", JS.read_text(), flags=re.S)
    assert not re.findall(r"['\"]#[0-9A-Fa-f]{3,8}['\"]", js)
    assert "getPropertyValue('--blue-fill')" not in js or "token('--blue-fill'" in js  # the pen's glow is a token


def test_motion_moves_only_transforms_and_opacity():
    """Keyframes animate opacity, transform, translate, scale or a sprite's background-position, never layout."""
    for name, body in re.findall(r"@keyframes ([\w-]+)\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}", CSS.read_text()):
        props = set(re.findall(r"([\w-]+)\s*:", re.sub(r"[\w%,\s]+\{", "{", body)))
        assert props <= {"opacity", "transform", "translate", "scale", "background-position"}, (name, props)


# --- the hub previews ---------------------------------------------------------------------------------------------

def test_hub_preview_strips_match_their_frame_counts():
    css = CSS.read_text()
    strips = re.findall(r'\[href="(/plato/\w+)"\][^{]*\{ --mo-strip: url\((/static/img/plato/hub/preview-\w+\.webp)\); --mo-n: (\d+); \}', css)
    assert len(strips) >= 3
    import importlib.util
    spec = importlib.util.spec_from_file_location("previews", web.HERE.parents[1] / "scripts" / "plato_hub_previews.py")
    previews = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previews)
    for href, url, n in strips:
        img = Image.open(STATIC / url[len("/static/"):])
        assert img.width == int(n) * previews.W and img.height == previews.H, url
        assert len(previews.FRAMES[href.rsplit("/", 1)[1]][0]) == int(n), href


# --- statviz: the same final drawing with or without the hook -----------------------------------------------------

def _node(code: str) -> dict:
    run = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@pytest.mark.skipif(not NODE, reason="node is not installed")
def test_statviz_markup_carries_final_values_and_entrance_offsets():
    out = _node(f"const S = require({json.dumps(str(SV))});"
                "console.log(JSON.stringify({spread: S.html('spread', {a: 0.09, b: 0.54}), layers: S.html('layers', {at: 36, n: 52}),"
                "dots: S.html('dots', {k: 34, n: 35}), api: Object.keys(S)}));")
    # the final values are in the markup itself; the animation only starts from elsewhere
    assert '<span class="sv-num">6×</span>' in out["spread"] and "<b>0.09</b>" in out["spread"]
    assert '<span class="sv-num">34</span>' in out["dots"] and '<span class="sv-num">36</span>' in out["layers"]
    dots = re.findall(r'<circle class="sv-on sv-\w+" cx="([\d.]+)" cy="([\d.]+)" r="3.4" style="--d:\d+ms;--dx:(-?[\d.]+)px;--dy:(-?[\d.]+)px"', out["spread"])
    assert len(dots) == 32
    # both clusters drift in from the same wide cloud: start = final + offset is the same point for dot i of each side
    a = [(float(x) + float(dx), float(y) + float(dy)) for x, y, dx, dy in dots[:16]]
    b = [(float(x) + float(dx), float(y) + float(dy)) for x, y, dx, dy in dots[16:]]
    assert all(abs(p[0] - q[0]) < 0.2 and abs(p[1] - q[1]) < 0.2 for p, q in zip(a, b))
    assert 'class="sv-mark" d="M' in out["layers"] and 'style="--mx:-280px"' in out["layers"]  # from layer 1 to 36
    for name in ("html", "render", "renderAll", "kinds", "tones", "watch", "watchAll", "countUp"):
        assert name in out["api"], name


@pytest.mark.skipif(not NODE, reason="node is not installed")
@pytest.mark.parametrize("reduce,observer,waits", [(False, True, True), (True, True, False), (False, False, False)])
def test_statviz_waits_only_when_motion_is_welcome(reduce, observer, waits):
    """render() marks a graphic sv-wait (its entrance held until it is in view) only with an IntersectionObserver
    and without prefers-reduced-motion; otherwise it is drawn complete at once, exactly as before."""
    code = f"""
      const vm = require('vm'), fs = require('fs');
      const cls = new Set(), attrs = {{'data-sv': 'dots'}}, observed = [];
      const el = {{ dataset: {{k: '3', n: '4'}}, innerHTML: '', classList: {{ add: (...c) => c.forEach(x => cls.add(x)),
        remove: (...c) => c.forEach(x => cls.delete(x)), contains: c => cls.has(c) }},
        getAttribute: k => attrs[k] == null ? null : attrs[k], setAttribute: (k, v) => {{ attrs[k] = v; }} }};
      const win = {{ document: {{ readyState: 'loading', addEventListener() {{}}, querySelectorAll: () => [] }},
        matchMedia: q => ({{ matches: {str(reduce).lower()} && /reduce/.test(q) }}), console }};
      if ({str(observer).lower()}) win.IntersectionObserver = function () {{ return {{ observe: e => observed.push(e), unobserve() {{}} }}; }};
      win.window = win;
      vm.createContext(win);
      vm.runInContext(fs.readFileSync({json.dumps(str(SV))}, 'utf8'), win);
      win.StatViz.render(el);
      console.log(JSON.stringify({{ cls: [...cls], observed: observed.length, html: el.innerHTML }}));
    """
    out = _node(code)
    assert ("sv-wait" in out["cls"]) is waits and (out["observed"] == 1) is waits
    assert "sv-dots" in out["cls"] and '<span class="sv-num">3</span>' in out["html"]
    assert out["html"].count('class="sv-on sv-blue"') == 3


def test_statviz_holds_its_entrance_only_while_waiting():
    css = SV_CSS.read_text()
    block = css[css.index("@media (prefers-reduced-motion: no-preference)"):]
    assert ".sv.sv-wait .sv-on, .sv.sv-wait .sv-ring, .sv.sv-wait .sv-mark, .sv.sv-wait .sv-fill { animation-play-state: paused; }" in block
    assert re.search(r"@media print \{\s*\.sv \.sv-on, \.sv \.sv-ring, \.sv \.sv-mark, \.sv \.sv-fill \{ animation: none !important; \}", css)
    fl = (STATIC / "js" / "plato_firstlook.js").read_text()
    assert "SV.watchAll(box)" in fl  # the first screens' own graphics play on view too

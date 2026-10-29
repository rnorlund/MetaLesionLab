"""The type scale (static/css/app.css, "Big and quiet"): the Plato site's page stylesheets take every font-size from a
--fs-* token. No raw px, rem or clamp() sizes, except text inside an SVG chart (a rule that sets `fill`, drawn in
the chart's viewBox units, not CSS pixels) and the epigraph's own --ep-size family."""
import re
from pathlib import Path

import pytest

from metalesionlab.web import app as web

CSS = Path(web.__file__).resolve().parent / "static" / "css"
LINGUA = {"ask", "assess", "bilingual", "challenge", "cut", "lab", "lingua", "scorer", "studio", "app", "motion"}
PAGE_CSS = sorted(p.name for p in CSS.glob("*.css") if p.stem not in LINGUA)
TOKENS = ("display", "h2", "lead", "h3", "intro", "body", "small", "label", "number", "number-sm", "brand")
RAW = re.compile(r"font-size\s*:\s*([^;}]+)|(?<![\w-])font\s*:\s*([^;}]+)")


def _rules(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        yield m.group(1).strip(), m.group(2)


def test_scale_is_defined_for_every_role():
    app = (CSS / "app.css").read_text()
    for t in TOKENS:
        assert re.search(rf"--fs-{t}:\s*clamp\(|--fs-{t}:\s*var\(", app), t
    for t in ("--fw-display", "--lh-display", "--ls-display", "--fw-lead", "--fw-number", "--space-sec"):
        assert t + ":" in app


@pytest.mark.parametrize("name", PAGE_CSS)
def test_page_css_uses_font_size_tokens(name):
    bad = []
    for sel, body in _rules((CSS / name).read_text()):
        if re.search(r"(?<![\w-])fill\s*:", body) or "--ep-size" in body:
            continue
        for m in RAW.finditer(body):
            val = (m.group(1) or m.group(2)).strip()
            val = re.sub(r"\s*!important", "", val)
            if val in ("inherit", "initial", "unset") or re.fullmatch(r"[\d.]+(em|%)", val):
                continue
            if m.group(2):  # the font shorthand: its size comes before a slash or the family
                val = re.split(r"/", re.sub(r"^[\d]{3}\s+|^(italic|normal)\s+", "", val))[0]
                if val.startswith("inherit"):
                    continue
            if not re.match(r"var\(--fs-[\w-]+\)", val):
                bad.append(f"{sel[:50]}: {val[:50]}")
    assert not bad, f"{name}: use a --fs-* token: {bad}"

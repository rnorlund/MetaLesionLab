"""The two sites this codebase serves, and their names, in one place. Renaming a site is a change here.

One switch picks the site a server runs: MLL_SITE=plato (the default) or MLL_SITE=lingua.

- plato:  Plato's Chair, the hackathon entry: "What would Plato ask an AI?" (the landing page with the
          drawing pad, /draw, /plato and its series, /socrates).
- lingua: Tippa Lingua, the sister project: picture-naming tests for people and an LLM lesion lab
          (/take, /assess, /scorer, /studio, /lab, /lab/cut, /lab/bilingual, /ask, /challenge).

Pages get the name through the {{BRAND}} placeholder (metalesionlab/web/site.py fills it in from the
serving app's site), the browser through window.TOT.BRAND (common.js reads it from the page), and
Python code by importing it: BRAND and TAGLINE are the running site's; PLATO and LINGUA are each
site's own, for code that only ever runs on one of them (the Lingua PDF reports, Ask Socrates).
MLL_SISTER_URL is the other site's address, for the "Sister project" link (no link when it's unset).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Brand:
    site: str  # "plato" or "lingua": the value of MLL_SITE
    name: str
    tagline: str  # one line under the name in the site header, and the default share text


PLATO = Brand("plato", "Plato’s Chair", "What would Plato ask an AI?")
LINGUA = Brand("lingua", "Tippa Lingua", "Picture-naming tests for people and AI")
SITES = {b.site: b for b in (PLATO, LINGUA)}
DEFAULT_SITE = PLATO.site


def site_key(value: str | None = None) -> str:
    """The site to serve: `value`, else MLL_SITE, else plato. A typo is an error, not a silent default."""
    raw = os.environ.get("MLL_SITE", "") if value is None else value
    key = raw.strip().lower() or DEFAULT_SITE
    if key not in SITES:
        raise ValueError(f"MLL_SITE={raw!r} isn't a site; use one of: {', '.join(SITES)}")
    return key


def brand_for(site: str | None = None) -> Brand:
    return SITES[site_key(site)]


def sister_of(site: str | None = None) -> Brand:
    """The other site."""
    key = site_key(site)
    return next(b for k, b in SITES.items() if k != key)


def sister_url() -> str:
    """Where the other site lives (MLL_SISTER_URL), or "" when it isn't set."""
    return os.environ.get("MLL_SISTER_URL", "").strip().rstrip("/")


SITE = site_key()
BRAND = SITES[SITE].name
TAGLINE = SITES[SITE].tagline

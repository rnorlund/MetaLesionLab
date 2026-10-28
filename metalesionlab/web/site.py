"""One header for every page, each site's name in one place, share tags, and the Plato series cards.

One codebase serves two sites (MLL_SITE, metalesionlab/brand.py): plato and lingua. The
serving app's site is app.state.site (app.py sets it); everything here follows it, so a test process
can render both.

app.py installs SiteMiddleware with one line. Every HTML page the app serves (whichever router serves
it) passes through it, and it:
- fills {{BRAND}}, {{TAGLINE}} and {{ORIGIN}} (scheme and host, for share-card URLs) with the site's;
- replaces the page's <header class="topbar">…</header>, whatever it holds, with the site header built
  from the site's NAV and MORE below, so the nav is the same on every page of a site (model chips such
  as #sample-chip are kept). The Plato site's brand slot holds its logo, the Form chair (FORM_CHAIR);
- fills <!--#series--> (every Plato series card) and <!--#series:sub--> (the series without /plato);
- fills <!--#epigraph:ID--> with that verified passage as an epigraph (epigraph.py);
- keeps <!--#if /path-->…<!--#else-->…<!--#endif--> blocks by whether the app serves /path
  (<!--#if series--> asks whether any experiment of the series besides /plato is served);
- fills <!--#sister--> with the "Sister project" link (MLL_SISTER_URL), or adds that link at the foot
  of a page without the mark; no link when MLL_SISTER_URL is unset;
- points <link rel="icon"> at the site's favicon;
- adds <meta name="application-name"> and a #site-data JSON blob for common.js (window.TOT.BRAND,
  TOT.site.pages), and default share tags (og:*, twitter:card) to pages that have no og:image.

Sub-pages are discovered, not hard-wired: a card or a nav link appears only when the app has a route
for its path (has_page). An experiment page joins the series by registering its route; its card text
lives in SERIES, and data/series/<slug>.json can override any field (for example "finding" once the
results are in). A picture at static/img/plato/series/<slug>.webp replaces the drawn icon.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

from starlette.datastructures import Headers, MutableHeaders
from starlette.routing import Match

from metalesionlab import brand as brands

HERE = Path(__file__).resolve().parent
SERIES_DIR = HERE / "data" / "series"
SERIES_IMG = HERE / "static" / "img" / "plato" / "series"
GITHUB = "https://github.com/rnorlund/MetaLesionLab"
SITE_URL = os.environ.get("TIPPA_SITE_URL", "").rstrip("/")  # e.g. https://example.org; else from the request
TRUST_PROXY = os.environ.get("TOT_TRUST_PROXY") == "1"

# --- the nav: one list per site --------------------------------------------------------------
# "needs": shown only when the app serves that path ("unless": hidden when it serves this one). "current": path
# prefixes that mark it as the page ("not_current": paths it is not current on)
# ("exact": the path itself only). Everything else the site has goes under "More" (MORE, and the series).
NAV = {
    "plato": [
        {"href": "/", "label": "Home", "current": ["/"]},
        {"href": "/draw", "label": "Draw", "needs": "/draw", "current": ["/draw"]},
        {"href": "/plato", "label": "Experiments", "needs": "/plato", "current": ["/plato"], "not_current": ["/plato/inside", "/plato/gallery"]},
        {"href": "/plato/gallery", "label": "Gallery", "needs": "/plato/gallery", "current": ["/plato/gallery"]},
        # its own page once /plato/inside is served, else the section on /plato
        {"href": "/plato/inside", "label": "Inside the model", "needs": "/plato/inside", "current": ["/plato/inside"]},
        {"href": "/plato#inside", "label": "Inside the model", "needs": "/plato", "unless": "/plato/inside"},
        {"href": "/socrates", "label": "Ask Socrates", "needs": "/socrates", "current": ["/socrates"], "accent": True},
        {"href": GITHUB, "label": "Code", "external": True},
    ],
    "lingua": [
        {"href": "/", "label": "Home", "current": ["/"]},
        {"href": "/take", "label": "Take the test", "needs": "/take", "current": ["/take"]},
        {"href": "/scorer", "label": "Scorer", "needs": "/scorer", "current": ["/scorer"]},
        {"href": "/studio", "label": "Test Studio", "needs": "/studio", "current": ["/studio"]},
        {"href": "/lab", "label": "Model Lab", "needs": "/lab", "current": ["/lab"], "exact": True},
        {"href": "/ask", "label": "Ask the Lab", "needs": "/ask", "current": ["/ask"], "accent": True},
        {"href": GITHUB, "label": "Code", "external": True},
    ],
}
# Under "More": everything else the site has, so every page stays one click from every other. On the
# Plato site that is the series (SERIES, discovered from the routes).
MORE = {
    "plato": [],
    "lingua": [
        {"href": "/assess", "label": "Naming Assessment", "note": "for clinicians and researchers"},
        {"href": "/challenge", "label": "You vs. the AI", "note": "name 10 pictures"},
        {"href": "/lab/bilingual", "label": "Second language", "note": "damage hits Spanish harder than English"},
        {"href": "/lab/cut", "label": "What can I cut?", "note": "remove layers, keep the tests passing"},
    ],
}
FAVICON = {"plato": "/static/img/favicon-plato.svg", "lingua": "/static/img/favicon.svg"}
SHARE_IMAGE = {"plato": "/static/img/og-plato-chair.png", "lingua": "/static/img/og-tippa-lingua.jpg"}  # 1200 x 630

# The Plato site's logo: the geometric "Form" chair, drawn in a 64-unit box. The header's brand slot
# holds it; the landing page's opening animation (static/js/splash.js) clones it, draws it stroke by
# stroke and flies it into this slot, so the path data lives only here.
FORM_CHAIR = ('<svg class="brand-logo" viewBox="0 0 64 64" width="38" height="38" aria-hidden="true" focusable="false">'
              '<g fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M21 33L21 7L43 7L43 33"/><path d="M21 15L43 15"/><path d="M29 7L29 15"/><path d="M35 7L35 15"/>'
              '<path class="seat" d="M21 33L16 40L48 40L43 33Z"/><path d="M16 40L16 58"/><path d="M48 40L48 58"/>'
              '<path d="M21 33L21 51"/><path d="M43 33L43 51"/></g></svg>')
LOGO = {"plato": FORM_CHAIR, "lingua": ""}

# --- the Plato series: "What would Plato ask an AI?" ------------------------------------------
# Question first, then where Plato asks it, then what we found (or a link while results are new).
SERIES = [
    {"path": "/plato", "slug": "chair", "question": "Is there one ideal chair?", "source": "Republic X · the Forms",
     "title": "Plato’s Chair",
     "finding": "Muse Image drew the same chair 16 times, and drew 34 of 35 things more alike than people do."},
    {"path": "/plato/inside", "slug": "inside", "question": "What happens to a drawing inside the machine?",
     "source": "Republic VII · out of the cave", "title": "Inside the model",
     "finding": "From about layer 36 of 52 (the median), Muse Glimmer holds Muse Image’s doodles of a thing together; "
                "at the last layer, people’s are about 6 times as spread out."},
    {"path": "/plato/forms", "slug": "forms", "question": "Is there one ideal clock, bed or table?",
     "source": "Republic X · Plato’s own bed and table", "title": "The Platonic clock", "finding": None},
    {"path": "/plato/cave", "slug": "cave", "question": "Can you know a thing from its shadow?",
     "source": "Republic VII · the Cave", "title": "Name the shadow", "finding": None},
    {"path": "/plato/cratylus", "slug": "cratylus", "question": "Do names fit things by nature?",
     "source": "Cratylus", "title": "Bouba and kiki", "finding": None},
    {"path": "/plato/bird", "slug": "bird", "question": "Is there one best example of a kind?",
     "source": "the Forms · Wittgenstein · Rosch", "title": "Name a bird", "finding": None},
    {"path": "/plato/damage", "slug": "damage", "question": "What happens to the Form when the mind is damaged?",
     "source": "Our own question", "title": "Damage the painter", "finding": None},
    # its picture shows Muse Image's chair, so on the landing page it waits for the blind draw ("blind_art")
    {"path": "/plato/lifespan", "slug": "lifespan", "question": "Is learning remembering the Forms?",
     "source": "Meno · children, adults and a model in training", "title": "The life of a chair", "finding": None,
     "blind_art": True},
    {"path": "/plato/atlas", "slug": "atlas", "question": "Is every thing one Form, or only some?",
     "source": "Republic X", "title": "The Atlas of Forms", "finding": None},
    {"path": "/plato/telephone", "slug": "telephone", "question": "What survives a copy of a copy?",
     "source": "Republic X · the painter’s copy", "title": "Plato’s Telephone", "finding": None},
]

# Small line drawings for cards that have no picture yet (stroke = currentColor).
_ART = {
    "chair": '<path d="M44 14v40M76 14v40M44 16h32M44 26h32M44 36h32M40 54h44l-4 8H44zM44 62v18M80 62v18M48 62l-2 14M76 62l2 14"/>',
    "forms": '<circle cx="60" cy="45" r="30"/><path d="M60 45l-13-9M60 45l13-9"/><circle cx="60" cy="45" r="2.5" fill="currentColor"/>'
             '<path d="M60 19v5M60 66v5M34 45h5M81 45h5"/>',
    "cave": '<path d="M8 84C10 36 32 8 60 8s50 28 52 76M8 84h104"/>'
            '<path d="M40 28v28M58 28v28M40 32h18M40 41h18M37 56h24v5H37zM40 61v13M58 61v13" stroke-opacity="0.35" stroke-width="4"/>'
            '<path d="M88 82c-7-3-8-12-1-19c0 6 6 7 4 13c4-2 5-6 4-9c5 6 3 13-4 15"/>',
    "cratylus": '<path d="M18 46c0-14 8-22 18-20c8-8 20-4 22 6c10 2 12 16 4 22c2 12-12 18-20 12c-10 6-24 0-24-20z"/>'
                '<path d="M86 20l4 18 14-10-8 16 16 4-16 4 8 16-14-10-4 18-4-18-14 10 8-16-16-4 16-4-8-16 14 10z"/>',
    "bird": '<path d="M26 52c6-16 22-24 38-20c6-10 18-10 22-2l8 2-8 4c2 14-8 26-24 28c-14 2-28-2-36-12z"/>'
            '<circle cx="80" cy="34" r="1.8" fill="currentColor"/><path d="M48 46c6 6 16 6 22 0M54 70l-2 10M64 70l2 10"/>',
    "lifespan": '<path d="M14 60v14M26 60v14M14 62h12M12 74h16M14 74v8M26 74v8"/>'
                '<path d="M44 44v22M64 44v22M44 47h20M44 54h20M42 66h24M44 66v14M64 66v14"/>'
                '<path d="M84 22v38M108 22v38M84 26h24M84 36h24M84 46h24M82 60h28l-3 6H85zM85 66v16M107 66v16"/>',
    "damage": '<path d="M44 14v40M76 14v18M76 40v14M44 16h32M44 26h14M64 26h12M44 36h32M40 54h44l-4 8H44z'
              'M44 62v18M80 62v8M80 74v6M48 62l-2 14"/><path d="M70 30l6 4 6-6" stroke-dasharray="2 4"/>',
    "inside": '<path d="M20 22h80M20 36h80M20 50h80M20 64h80" stroke-opacity="0.35"/>'
              '<circle cx="30" cy="22" r="3"/><circle cx="62" cy="22" r="3"/><circle cx="92" cy="22" r="3"/>'
              '<circle cx="42" cy="36" r="3"/><circle cx="74" cy="36" r="3"/><circle cx="52" cy="50" r="3"/>'
              '<circle cx="66" cy="50" r="3"/><circle cx="60" cy="64" r="4" fill="currentColor"/>',
    "atlas": '<rect x="14" y="12" width="26" height="20" rx="3"/><rect x="47" y="12" width="26" height="20" rx="3"/>'
             '<rect x="80" y="12" width="26" height="20" rx="3"/><rect x="14" y="38" width="26" height="20" rx="3"/>'
             '<rect x="47" y="38" width="26" height="20" rx="3"/><rect x="80" y="38" width="26" height="20" rx="3"/>'
             '<rect x="14" y="64" width="26" height="20" rx="3"/><rect x="47" y="64" width="26" height="20" rx="3"/>'
             '<rect x="80" y="64" width="26" height="20" rx="3"/>',
    "telephone": '<path d="M14 30v22M30 30v22M14 33h16M12 52h20M14 52v12M30 52v12"/>'
                 '<path d="M52 32v20M68 34v18M52 35h16M50 52h20M53 52v11M67 52v12" stroke-dasharray="5 2"/>'
                 '<path d="M90 36v16M104 38v14M90 40h14M88 52h18M92 52v10M103 52v9" stroke-dasharray="3 3"/>'
                 '<path d="M36 44h8M74 44h8M41 40l4 4-4 4M79 40l4 4-4 4"/>',
}


# --- which site, which pages ---------------------------------------------------------------------

def site_of(app) -> str:
    """The app's site: app.state.site (set by app.create_app), else MLL_SITE."""
    return getattr(getattr(app, "state", None), "site", None) or brands.SITE


def brand_of(app) -> brands.Brand:
    return brands.SITES[site_of(app)]


def has_page(app, path: str) -> bool:
    """True when the app answers GET path with a route (included routers count too)."""
    path = path.split("#", 1)[0] or "/"
    scope = {"type": "http", "path": path, "method": "GET", "root_path": "", "headers": [], "query_string": b""}
    for route in app.routes:
        if getattr(route, "path", None) == "/static":  # the static mount matches every prefix
            continue
        try:
            if route.matches(scope)[0] == Match.FULL:
                return True
        except Exception:  # a route type that can't match a bare scope
            continue
    return False


def series(app) -> list[dict]:
    """The Plato series entries whose pages exist, each with its overrides from data/series/<slug>.json."""
    out = []
    for entry in SERIES:
        if not has_page(app, entry["path"]):
            continue
        item = dict(entry)
        extra = SERIES_DIR / f"{entry['slug']}.json"
        if extra.is_file():
            try:
                item.update({k: v for k, v in json.loads(extra.read_text()).items() if k in entry or k == "image"})
            except ValueError:
                pass
        if not item.get("image"):
            for ext in ("webp", "png", "jpg"):
                if (SERIES_IMG / f"{entry['slug']}.{ext}").is_file():
                    item["image"] = f"/static/img/plato/series/{entry['slug']}.{ext}"
                    break
        out.append(item)
    return out


def pages_flags(app) -> dict:
    """Every page either site can link to, and whether this app serves it (common.js: TOT.hasPage)."""
    paths = [n["href"] for nav in NAV.values() for n in nav if n.get("needs")]
    paths += [m["href"] for more in MORE.values() for m in more] + [s["path"] for s in SERIES]
    return {p: has_page(app, p) for p in dict.fromkeys(paths)}


def sister(app) -> dict | None:
    """The other site, when MLL_SISTER_URL says where it is."""
    url = brands.sister_url()
    if not url:
        return None
    other = brands.sister_of(site_of(app))
    return {"name": other.name, "tagline": other.tagline, "url": url}


# --- rendering ------------------------------------------------------------------------------------

def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def _is_current(item: dict, path: str) -> bool:
    if path in item.get("not_current", []):
        return False
    for prefix in item.get("current", []):
        if path == prefix or (prefix != "/" and not item.get("exact") and path.startswith(prefix + "/")):
            return True
    return False


def _link(item: dict, path: str, cls: str = "") -> str:
    attrs = [f'href="{_esc(item["href"])}"']
    if cls:
        attrs.append(f'class="{cls}"')
    if _is_current(item, path) or (not item.get("current") and item["href"] == path):
        attrs.append('aria-current="page"')
    if item.get("external"):
        attrs.append('rel="noopener"')
    label = _esc(item["label"]) + (' <span class="ext" aria-hidden="true">↗</span>' if item.get("external") else "")
    return f"<a {' '.join(attrs)}>{label}</a>"


def render_header(app, path: str, chips: str = "", tour: bool = False) -> str:
    site, b = site_of(app), brand_of(app)
    flags = pages_flags(app)
    main = [n for n in NAV[site] if (not n.get("needs") or flags.get(n["needs"]))
            and not (n.get("unless") and flags.get(n["unless"]))]
    more = [m for m in MORE[site] if flags.get(m["href"])]
    inline_hrefs = {n["href"] for n in main}  # a series page with its own nav item (/plato/inside) isn't repeated
    subs = [s for s in SERIES if s["path"] != "/plato" and flags.get(s["path"]) and s["path"] not in inline_hrefs]

    def more_list() -> str:
        parts = []
        if subs:
            parts.append('<p class="nav-group">The Plato series</p>')
            parts += [_link({"href": s["path"], "label": s["title"]}, path) for s in subs]
            if more:
                parts.append('<p class="nav-group">More from the lab</p>')
        parts += [_link(m, path) for m in more]  # exact match only: /lab is not current on /lab/cut
        return "".join(parts)

    inline = "".join(_link(n, path, "nav-accent" if n.get("accent") else "") for n in main)
    extra = more_list()
    more_current = any(path == m["href"] for m in more) or any(path == s["path"] for s in subs)
    more_menu = (f'<details class="nav-more{" is-current" if more_current else ""}"><summary>More</summary>'
                 f'<div class="nav-panel">{extra}</div></details>') if extra else ""
    tour_btn = ('<button type="button" class="demo-btn" data-tour-start><svg viewBox="0 0 10 10" aria-hidden="true">'
                '<path d="M1 0l9 5-9 5z" fill="currentColor"/></svg>Tour</button>') if tour else ""
    logo = LOGO.get(site, "")
    return (
        '<header class="topbar site-head">'
        f'<a class="brand{" has-logo" if logo else ""}" href="/">{logo}'
        f'<span class="brand-name"><b>{_esc(b.name)}</b><span class="brand-tag">{_esc(b.tagline)}</span></span></a>'
        f'<nav class="topnav" aria-label="Main">{inline}{more_menu}</nav>'
        '<details class="nav-menu"><summary><span class="nav-burger" aria-hidden="true"></span>Menu</summary>'
        f'<div class="nav-panel">{"".join(_link(n, path) for n in main)}{extra}</div></details>'
        f'{tour_btn}{chips}</header>'
    )


def render_sister(app) -> str:
    """The "Sister project" link, or "" when MLL_SISTER_URL isn't set."""
    s = sister(app)
    if not s:
        return ""
    return (f'<a class="sister-link" href="{_esc(s["url"])}/" rel="noopener">Sister project: {_esc(s["name"])}'
            f' <span aria-hidden="true">↗</span></a><span class="sister-tag">{_esc(s["tagline"])}</span>')


def render_series(items: list[dict]) -> str:
    cards = []
    for s in items:
        icon = (f'<svg viewBox="0 0 120 90" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.5" '
                f'stroke-linecap="round" stroke-linejoin="round">{_ART.get(s["slug"], _ART["chair"])}</svg>')
        art_class = "series-art"
        if s.get("image"):
            art = f'<img src="{_esc(s["image"])}" alt="" loading="lazy">'
            if s.get("blind_art"):  # a picture with Muse Image's chairs: the landing page shows the icon until the reveal
                art, art_class = icon + art, "series-art series-art-blind"
        else:
            art = icon
        finding = s.get("finding")
        status = (f'<span class="series-finding">{_esc(finding)}</span>' if finding
                  else '<span class="series-finding series-new">New: see what we found</span>')
        cards.append(
            f'<a class="series-card" href="{_esc(s["path"])}"><span class="{art_class}">{art}</span>'
            f'<span class="series-body"><span class="series-q">{_esc(s["question"])}</span>'
            f'<span class="series-src">{_esc(s["source"])} · {_esc(s["title"])}</span>{status}'
            '<span class="series-go" aria-hidden="true">→</span></span></a>')
    return f'<div class="series-grid">{"".join(cards)}</div>' if cards else ""


_IF = re.compile(r"<!--#if (\S+?)-->(.*?)(?:<!--#else-->(.*?))?<!--#endif-->", re.S)
_HEADER = re.compile(r'<header class="topbar[^"]*"[^>]*>.*?</header>', re.S)
_CHIPS = re.compile(r'<div class="chips"[^>]*>.*?</div>', re.S)
_ICON = re.compile(r'<link rel="icon"[^>]*>')


def origin(scope) -> str:
    if SITE_URL:
        return SITE_URL
    h = Headers(scope=scope)
    scheme = (h.get("x-forwarded-proto") if TRUST_PROXY else None) or scope.get("scheme", "http")
    host = (h.get("x-forwarded-host") if TRUST_PROXY else None) or h.get("host") or "localhost"
    return f"{scheme.split(',')[0].strip()}://{host.split(',')[0].strip()}"


def _attr(page: str, pattern: str) -> str | None:
    m = re.search(pattern, page, re.S | re.I)
    return html.unescape(m.group(1)).strip() if m else None


def share_tags(page: str, origin_url: str, path: str, site: str | None = None) -> str:
    """Default og/twitter tags for a page that has none, from its <title> and description."""
    b = brands.SITES[site or brands.SITE]
    title = _attr(page, r"<title>(.*?)</title>") or b.name
    desc = _attr(page, r'<meta name="description" content="([^"]*)"') or b.tagline
    image = origin_url + SHARE_IMAGE[b.site]
    tags = [("property", "og:type", "website"), ("property", "og:site_name", b.name), ("property", "og:title", title),
            ("property", "og:description", desc), ("property", "og:url", origin_url + path),
            ("property", "og:image", image), ("property", "og:image:width", "1200"), ("property", "og:image:height", "630"),
            ("name", "twitter:card", "summary_large_image")]
    have = set(re.findall(r'(?:property|name)="((?:og|twitter):[\w:]+)"', page))
    return "".join(f'<meta {k}="{v}" content="{_esc(c)}">' for k, v, c in tags if v not in have)


def _foot(page: str, block: str) -> str:
    """Put a footer block after the page's content: before the first script after </main>, else before </body>."""
    main = page.rfind("</main>")
    at = page.find("<script", main) if main >= 0 else -1
    if at < 0:
        at = page.rfind("</body>")
    return page[:at] + block + page[at:] if at >= 0 else page + block


def render_page(page: str, app, path: str, origin_url: str) -> str:
    """Everything the middleware does to one HTML page."""
    site, b = site_of(app), brand_of(app)
    page = page.replace("{{BRAND}}", _esc(b.name)).replace("{{TAGLINE}}", _esc(b.tagline)).replace("{{ORIGIN}}", origin_url)

    def served(token: str) -> bool:  # "series": any experiment of the series besides /plato itself
        if token == "series":
            return any(has_page(app, s["path"]) for s in SERIES if s["path"] != "/plato")
        return has_page(app, token)
    page = _IF.sub(lambda m: m.group(2) if served(m.group(1)) else (m.group(3) or ""), page)

    def header(m: re.Match) -> str:
        chips = _CHIPS.search(m.group(0))
        # The guided tour is Plato's Chair's: only where /plato is served.
        tour = "/static/js/tour.js" in page and has_page(app, "/plato")
        return render_header(app, path, chips.group(0) if chips else "", tour=tour)
    page = _HEADER.sub(header, page, count=1)
    if "<!--#series" in page:
        items = series(app)
        page = page.replace("<!--#series:sub-->", render_series([s for s in items if s["path"] != "/plato"]))
        page = page.replace("<!--#series-->", render_series(items))
    if "<!--#epigraph:" in page:
        from metalesionlab.web import epigraph  # verified quotations, from public_data/plato_passages.json
        page = epigraph.fill(page)
    if site == "plato" and path != "/plato/gallery" and has_page(app, "/plato/gallery"):
        from metalesionlab.web.plato_gallery_routes import add_strip  # "From the lab", above the footer
        page = add_strip(page)
    link = render_sister(app)
    if "<!--#sister-->" in page:
        page = page.replace("<!--#sister-->", link)
    elif link:
        page = _foot(page, f'<footer class="site-foot"><p>{link}</p></footer>')
    page = _ICON.sub(f'<link rel="icon" href="{FAVICON[site]}" type="image/svg+xml">', page, count=1)
    data = json.dumps({"site": site, "brand": b.name, "tagline": b.tagline, "pages": pages_flags(app),
                       "sister": sister(app)}).replace("</", "<\\/")
    head = (f'<meta name="application-name" content="{_esc(b.name)}">'
            f'<script type="application/json" id="site-data">{data}</script>')
    if "og:image" not in page:
        head += share_tags(page, origin_url, path, site)
    page = _ASSET.sub(_versioned, page)
    at = page.find("</head>")
    return page[:at] + head + page[at:] if at >= 0 else head + page


# Every stylesheet and script link carries the file's modification time (?v=…), so a browser that cached
# an older copy fetches the new one after a change instead of pairing new pages with old styles.
_ASSET = re.compile(r'((?:href|src)=")(/static/[^"?#]+\.(?:css|js))(")')
_STATIC = Path(__file__).resolve().parent / "static"


def _versioned(m: re.Match) -> str:
    try:
        v = int((_STATIC / m.group(2)[len("/static/"):]).stat().st_mtime)
    except OSError:
        return m.group(0)
    return f"{m.group(1)}{m.group(2)}?v={v}{m.group(3)}"


# --- middleware -----------------------------------------------------------------------------------

class SiteMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope.get("method") != "GET"
                or scope["path"].startswith(("/static/", "/api/", "/media/"))):
            return await self.app(scope, receive, send)
        ext = {k: v for k, v in (scope.get("extensions") or {}).items() if k != "http.response.pathsend"}
        scope = {**scope, "extensions": ext}  # so FileResponse sends the body through us
        state: dict = {"start": None, "chunks": []}

        async def wrapped(message):
            if message["type"] == "http.response.start":
                ctype = Headers(raw=message["headers"]).get("content-type", "")
                if message.get("status") == 200 and ctype.startswith("text/html"):
                    state["start"] = message
                    return
            elif message["type"] == "http.response.body" and state["start"] is not None:
                state["chunks"].append(message.get("body", b""))
                if message.get("more_body"):
                    return
                text = b"".join(state["chunks"]).decode("utf-8")
                body = render_page(text, scope["app"], scope["path"], origin(scope)).encode("utf-8")
                headers = MutableHeaders(raw=list(state["start"]["headers"]))
                headers["content-length"] = str(len(body))
                for stale in ("etag", "last-modified"):
                    if stale in headers:
                        del headers[stale]
                await send({**state["start"], "headers": headers.raw})
                await send({"type": "http.response.body", "body": body, "more_body": False})
                return
            await send(message)

        await self.app(scope, receive, wrapped)


def install(app) -> None:
    """Called once per site by app.py: the middleware, and GET /api/site (name, nav pages, series) for scripts."""
    app.add_middleware(SiteMiddleware)

    def site_info():
        b = brand_of(app)
        return {"site": site_of(app), "brand": b.name, "tagline": b.tagline, "pages": pages_flags(app),
                "sister": sister(app), "series": [{k: v for k, v in s.items()} for s in series(app)]}
    app.add_api_route("/api/site", site_info, methods=["GET"], include_in_schema=False)

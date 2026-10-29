"""Plato, Socrates and Aristotle on the pages: marker doodles drawn by Meta's Muse Image.

The doodles share one prompt template with the Socrates portraits the tour uses ("A quick simple doodle sketch of
the marble bust of the philosopher …, black marker on plain white, no text, no shading."), were picked by eye
from four candidates per pose, and were ink-cropped to small WebPs in static/img/portraits/ (the Socrates ones
stay in static/img/socrates/). Every page that shows one credits it: "drawn by Meta's Muse Image".

- face(): the speaker's face beside an epigraph (epigraph.py): Plato, Socrates or Aristotle; anyone else, none.
- decorate(): what SiteMiddleware (site.py) adds to a page of the Plato site: the portraits stylesheet, a small
  Plato beside "What would Plato ask an AI?" on the series pages, Socrates as a floating guide on them ("Ask
  Socrates"), and the credit line in the page's footnote for every portrait the page shows.
"""
from __future__ import annotations

import html
import re

IMG = "/static/img/portraits/"
CREDIT = "drawn by Meta’s Muse Image"
STYLESHEET = '<link rel="stylesheet" href="/static/css/portraits.css">'

# The face beside a quotation, by the name the citation gives (epigraph.speaker()).
FACES = {
    "Plato": IMG + "plato-neutral.webp",
    "Socrates": "/static/img/socrates/socrates-neutral.webp",
    "Aristotle": IMG + "aristotle-neutral.webp",
}
LOOKS = {  # what each face looks like, for the alt text
    "Plato": "long full beard, wavy hair, broad brow",
    "Socrates": "bald, curly beard",
    "Aristotle": "short beard, short hair",
}
THINKING = IMG + "plato-thinking.webp"  # Plato asks: beside "What would Plato ask an AI?" on the series pages
GUIDE = "/static/img/socrates/socrates-questioning.webp"


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def name_label(name: str) -> str:
    """A portrait's name in the one name-label style (portraits.css .pt-name). The picture's alt text or the words
    beside it already name the person, so screen readers skip the label."""
    return f'<span class="pt-name" aria-hidden="true">{_e(name)}</span>'


def face(name: str, cls: str = "epigraph-face", named: bool = False) -> str:
    """The speaker's face as an <img>, or "" for anyone but Plato, Socrates and Aristotle. named: the face and its
    name label together (<span class="pt-who">), as beside an epigraph."""
    src = FACES.get(name)
    if not src:
        return ""
    alt = f"{name} ({LOOKS[name]}), a marker doodle {CREDIT}"
    img = (f'<img class="{_e(cls)}" src="{src}" width="256" height="256" loading="lazy" decoding="async" '
           f'alt="{_e(alt)}" title="{_e(name)}, {CREDIT}">')
    return f'<span class="pt-who">{img}{name_label(name)}</span>' if named else img


# Aristotle checks the evidence: the badge on a "How we know" disclosure (plato_firstlook.js) and a findings card's
# "More detail" (findings.js). The scripts build the same markup; portraits.css documents it.
ARISTOTLE_BADGE = ('<span class="pt-badge pt-aristotle"><img class="pt-badge-face" src="' + IMG + 'aristotle-neutral.webp" '
                   'width="256" height="256" alt="" loading="lazy" decoding="async" title="Aristotle, ' + CREDIT + '">'
                   '<span class="pt-badge-text">Aristotle checks the evidence</span></span>')


# --- what the middleware adds -------------------------------------------------------------------------

_KICKER = re.compile(r'<p class="title-kicker">(What would Plato ask an AI\?)')
ASKS = "Plato would ask:"  # the kicker's words on the series pages and hubs, beside his face
_HERO_CAP = re.compile(r'(<figure class="hero-plato">.*?<figcaption>)', re.S)
_ATHENS = re.compile(r'(<img class="pt-athens-(plato|aristotle)"[^>]*>)')
_FOOTNOTE = re.compile(r'(<p class="(?:footnote|lfoot-credit)"[^>]*>)(.*?)(</p>)', re.S)
_SHOWN = {  # a portrait's file -> whose it is (for the credit line)
    "/static/img/portraits/plato-": ("Plato",),
    "/static/img/portraits/aristotle-": ("Aristotle",),
    "/static/img/portraits/socrates-and-plato": ("Socrates", "Plato"),
    "/static/img/socrates/socrates-": ("Socrates",),
}


def is_series(path: str) -> bool:
    """The series pages, and the Damaged AI hub (/damaged), which asks the series' damage question."""
    return path in ("/plato", "/damaged") or path.startswith("/plato/")


def kicker_face(page: str) -> str:
    """Plato asks: his face, thinking, and "Plato would ask:" in place of the series line "What would Plato ask an
    AI?" (the first one on the page), so the page's question (its h1) reads as his."""
    img = (f'<img class="kicker-face" src="{THINKING}" width="256" height="256" decoding="async" '
           f'alt="Plato, thinking (a marker doodle {CREDIT})" title="Plato asks. Drawn by Meta’s Muse Image">')
    return _KICKER.sub(lambda m: f'<p class="title-kicker has-face">{img}<span class="kicker-who">{ASKS}</span>', page, count=1)


def name_faces(page: str) -> str:
    """Every whole-figure portrait gets its name: Plato pointing up in the landing hero, and the pair of
    gestures in /plato's Aristotle's reply."""
    page = _HERO_CAP.sub(lambda m: m.group(1) + name_label("Plato") + " ", page, count=1)
    return _ATHENS.sub(lambda m: f'<span class="pt-who">{m.group(1)}{name_label(m.group(2).title())}</span>', page)


def guide() -> str:
    """Socrates, floating at the foot of the window: his face and "Ask Socrates", a link to /socrates."""
    return ('<a class="pt-guide" href="/socrates" title="Ask Socrates about these experiments">'
            f'<img src="{GUIDE}" width="256" height="256" alt="" decoding="async">'
            '<span class="pt-guide-text"><b>Ask Socrates</b><small>about the experiments</small></span></a>')


def shown(page: str) -> list[str]:
    """Whose portraits the page shows, in a fixed order."""
    names = {who for prefix, whom in _SHOWN.items() if prefix in page for who in whom}
    return [n for n in ("Plato", "Socrates", "Aristotle") if n in names]


def credit_line(names: list[str]) -> str:
    if not names:
        return ""
    who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return f'<span class="pt-credit">Portraits of {who}: marker doodles {CREDIT}.</span>'


def add_credit(page: str) -> str:
    """The credit in the page's footnote (or the landing page's credit line), else just after </main>. A footnote
    that already credits them (/socrates writes its own) is left as it is."""
    line = credit_line(shown(page))
    if not line or 'class="pt-credit"' in page:
        return page
    m = None
    for m in _FOOTNOTE.finditer(page):
        pass  # the last one: the page's own footnote, after its content
    if m:
        if CREDIT in m.group(2):
            return page
        return page[:m.end(2)] + " " + line + page[m.end(2):]
    at = page.rfind("</main>")
    if at < 0:
        return page
    at += len("</main>")
    return page[:at] + f'<p class="pt-credit-row">{line}</p>' + page[at:]


def link_css(page: str) -> str:
    if STYLESHEET in page:
        return page
    head = page.find("</head>")
    return page[:head] + STYLESHEET + page[head:] if head >= 0 else page


def decorate(page: str, path: str, socrates: bool) -> str:
    """The portraits a Plato-site page gets; socrates: whether the app serves /socrates (the guide's link)."""
    page = name_faces(page)
    if is_series(path):
        page = kicker_face(page)
        if socrates and 'class="pt-guide"' not in page:
            at = page.rfind("</body>")
            if at >= 0:
                page = page[:at] + guide() + page[at:]
    if shown(page):
        page = link_css(page)
    return add_credit(page)

"""Epigraphs: one short verified quotation with who said it, the reference number and the translator.

A page asks for one with a marker where it should stand:

    <!--#epigraph:theaetetus-155d-->            a page's epigraph, near the top
    <!--#epigraph:metaphysics-981a5 inline-->   smaller, inside a box (no outer margins)
    <!--#epigraph:apology-38a band-->           one of several in a row (a quote band)

SiteMiddleware (site.py) fills every marker from public_data/plato_passages.json, the file that
scripts/verify_passages.py checks word for word against its public-domain sources, so a page's epigraph can't
drift from the verified text, and links the stylesheet (static/css/epigraph.css) and the serif it uses. An
unknown id renders nothing: the site never shows a quotation that isn't in the file.

The words are the passage's, exactly. The renderer only adds quotation marks, and an ellipsis where the
passage starts or ends mid-sentence. The citation names the speaker when it is Socrates ("Socrates, in
Plato's Theaetetus 155d"), otherwise the author ("Plato, Timaeus 28a"; "Aristotle, Metaphysics I.1,
980a21–24"), and links the translator's credit to the source text. Beside the words is the face of whoever the
citation names (speaker()): Plato, Socrates or Aristotle, a marker doodle drawn by Meta's Muse Image
(portraits.py); a passage by anyone else gets no face.
"""
from __future__ import annotations

import html
import json
import re

from metalesionlab import meta_api
from metalesionlab.web import portraits

PASSAGES = meta_api.REPO_ROOT / "public_data" / "plato_passages.json"
VARIANTS = ("inline", "band")
MARKER = re.compile(r"<!--#epigraph:([\w-]+?)(?:\s+(\w+))?\s*-->")
FONT = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:ital,wght@1,300;1,400'
        '&display=swap">')
STYLESHEET = '<link rel="stylesheet" href="/static/css/epigraph.css">'
TRANSLATOR = {"Plato": "Jowett", "Aristotle": "W. D. Ross"}
_cache: dict = {}


def passages() -> dict[str, dict]:
    """The verified passages by id, re-read when the file changes; {} if it's missing or unreadable."""
    try:
        stamp = PASSAGES.stat().st_mtime_ns
    except OSError:
        return {}
    if _cache.get("stamp") != stamp:
        try:
            data = json.loads(PASSAGES.read_text(encoding="utf-8"))
            _cache.update(stamp=stamp, by_id={p["id"]: p for p in data.get("passages", [])})
        except (OSError, ValueError, KeyError, TypeError):
            return {}
    return _cache["by_id"]


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def words(p: dict) -> str:
    """The passage in quotation marks, with an ellipsis where it starts or ends mid-sentence."""
    text = p["text"]
    if text[:1].islower():
        text = "…" + text
    if not re.search(r"[.?!]['’”)]?$", text):
        text += "…"
    return f"“{text}”"


def speaker(p: dict) -> str:
    """Whom the citation names: Socrates when he speaks in Plato's dialogue, otherwise the author."""
    author = p.get("author", "Plato")
    if author == "Plato" and str(p.get("speaker", "")).startswith("Socrates"):
        return "Socrates"
    return author


def citation(p: dict) -> str:
    """'Socrates, in Plato's Theaetetus 155d', 'Plato, Republic VII, 518b–c', 'Aristotle, Metaphysics I.1, 980a21–24'."""
    author = p.get("author", "Plato")
    work = f"<cite>{_e(p['work'])}</cite>"
    if author == "Aristotle":
        where = f"{work} {_e(p['book'])}.{_e(p['chapter'])}," if p.get("chapter") else work
        ref = p["bekker"]
    else:
        where = f"{work} {_e(p['book'])}," if p.get("book") else work
        ref = p["stephanus"]
    lead = "Socrates, in Plato’s" if speaker(p) == "Socrates" else _e(author) + ","
    # The dot keeps to the reference (a no-break space), so a long citation wraps after it, never before it.
    return (f'<span class="epigraph-who">{lead}</span> {where} <span class="epigraph-ref">{_e(ref)}</span>'
            f' · <span class="epigraph-tr"><a href="{_e(p["source_url"])}" rel="noopener" '
            f'title="{_e(p["translation"])}">tr. {_e(TRANSLATOR.get(author, ""))}</a></span>')


def render(pid: str, variant: str | None = None) -> str:
    """One epigraph's HTML, or "" when the id isn't a verified passage."""
    p = passages().get(pid)
    if not p:
        return ""
    cls = "epigraph" + (f" epigraph--{variant}" if variant in VARIANTS else "")
    who = speaker(p)
    face = portraits.face(who)
    speaks = f' data-speaker="{_e(who.lower())}"' if face else ""
    return (f'<figure class="{cls}" data-passage="{_e(pid)}"{speaks}>{face}'
            f'<blockquote cite="{_e(p["source_url"])}"><p>{_e(words(p))}</p></blockquote>'
            f'<figcaption>{citation(p)}</figcaption></figure>')


def fill(page: str) -> str:
    """Every epigraph marker in a page rendered, and the stylesheet and font linked once."""
    if "<!--#epigraph:" not in page:
        return page
    page = MARKER.sub(lambda m: render(m.group(1), m.group(2)), page)
    if STYLESHEET not in page:
        head = page.find("</head>")
        if head >= 0:
            page = page[:head] + FONT + STYLESHEET + page[head:]
    if 'class="epigraph-face"' in page:  # the faces' styles (and their colours) live with the other portraits
        page = portraits.link_css(page)
    return page

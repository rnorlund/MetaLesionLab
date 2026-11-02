"""A visitor's own Meta Model API key, for judges who want to try the live features beyond the demo's daily budget.

The browser keeps the key in sessionStorage (static/js/ownkey.js: More → Use your own API key) and sends it in the
X-Meta-Key header with the paid requests only: Ask Socrates (/api/socrates…) and the voice test
(/api/phaedrus/read). Here it builds a MetaAPI for that one request (metered=False: the calls bill the visitor's
account, so they skip this site's caps and ledger). The key is never stored, logged or echoed back; an error from
the Meta API is reported by its type only. The guard's per-visitor rate limits still apply.
"""
from __future__ import annotations

import re

from metalesionlab.meta_api import MetaAPI

HEADER = "x-meta-key"
_SHAPE = re.compile(r"[A-Za-z0-9._:|+/=\-]{20,400}")  # a token, nothing else: no spaces, quotes or control characters


def key_of(headers) -> str | None:
    """The visitor's key from the request headers, or None (missing or not shaped like a key)."""
    raw = (headers.get(HEADER) or "").strip()
    return raw if _SHAPE.fullmatch(raw) else None


def api_for(request) -> MetaAPI | None:
    """A MetaAPI on the visitor's own key for this request, or None to use the site's."""
    key = key_of(request.headers)
    return MetaAPI(api_key=key, metered=False) if key else None


OWN_KEY_ERROR = ("Your own Meta API key didn't work ({kind}). Check it under More → Use your own API key, "
                 "or remove it to use the demo's shared budget.")

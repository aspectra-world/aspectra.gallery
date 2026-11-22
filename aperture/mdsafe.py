# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright © 2026 lucya.systems — https://lucya.systems
"""Markdown for text that ends up on the public gallery, without markup.

python-markdown passes raw HTML straight through, and `extra`'s attr_list
lets `{: onclick="…" }` put any attribute on any element. An album
description is printed `| safe` on the album page and handed out by /api
with CORS `*` -- on someone else's page, where no CSP of ours stands in
front of it. So here:

  * raw HTML is not recognised at all -- it comes out escaped, as text;
  * every attribute not on a short list is dropped, whatever put it there;
  * a link or an image may point at http(s), mailto, a fragment or a path on
    this site, and nowhere else (no javascript:, data:, vbscript:, …).

No new dependency: the Markdown instance is configured, and one tree
processor walks the result before it is serialised.
"""

from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

import markdown
from markdown.treeprocessors import Treeprocessor

# The attributes markdown itself produces for the elements it emits, and
# nothing that can run or restyle anything. `id`/`class` are what footnotes,
# abbreviations and fenced code carry; `colspan`/`align` are tables'.
ALLOWED_ATTRS = frozenset({"href", "src", "alt", "title", "id", "class",
                           "colspan", "rowspan", "align", "start", "rel"})
URL_ATTRS = frozenset({"href", "src"})
SAFE_SCHEMES = frozenset({"http", "https", "mailto"})

# A browser ignores tabs, newlines and other control characters inside a
# scheme ("java\tscript:"), so they are removed before the scheme is read.
_CONTROL = re.compile(r"[\x00-\x20\x7f]+")


def safe_url(value: str) -> bool:
    url = _CONTROL.sub("", html.unescape(value or ""))
    if url.startswith(("#", "/")) and not url.startswith("//"):
        return True
    try:
        scheme = urlsplit(url).scheme.lower()
    except ValueError:
        return False
    if not scheme:
        # relative ("photo.jpg", "../x") -- but not something whose colon a
        # browser would still read as a scheme
        return ":" not in url.split("/", 1)[0]
    return scheme in SAFE_SCHEMES


class _Scrub(Treeprocessor):
    def run(self, root):
        for el in root.iter():
            for name in list(el.attrib):
                low = name.lower()
                if low not in ALLOWED_ATTRS or (low in URL_ATTRS and not safe_url(el.attrib[name])):
                    del el.attrib[name]
        return None


def _md() -> markdown.Markdown:
    md = markdown.Markdown(extensions=["extra", "sane_lists"], output_format="html5")
    # Raw HTML, block and inline: without these two the source's tags are
    # escaped like any other text.
    md.preprocessors.deregister("html_block")
    md.inlinePatterns.deregister("html")
    # Last of the tree processors, so it sees what attr_list and the others
    # have added.
    md.treeprocessors.register(_Scrub(md), "aperture_scrub", 0)
    return md


def render(text: str) -> str:
    return _md().convert(text or "")

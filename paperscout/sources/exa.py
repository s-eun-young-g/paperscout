"""Exa publications-search adapter: semantic discovery over Exa's ~350M-paper index.

Exa finds the *right* papers from a natural-language query, but returns only *discovery
stubs* - title, url, a free-text author string, a date, and a text snippet - NOT the
structured authorship / institution / citation / topic metadata the research-group
rollup joins on. So this source is deliberately paired with an OpenAlex hydration step
(see ``outreach.scraper.fetch``): Exa decides *which* papers enter the corpus, OpenAlex
supplies the join keys. Uses the shared cached ``Client`` (POST), so reruns stay offline.

Docs: https://exa.ai/blog/publications-search
"""

from __future__ import annotations

import re
from typing import Optional

from ..http import Client
from ..models import Author, Paper

BASE = "https://api.exa.ai/search"
# Exa's dedicated publications index. If a given key expects the older long-form
# category ("research paper"), flip this one constant.
DEFAULT_CATEGORY = "publication"
MAX_RESULTS = 100  # Exa /search caps numResults per request.

# A DOI embedded anywhere in a URL. Exa returns publisher landing pages
# (link.springer.com/article/10.1038/..., doi.org/10.1101/..., wiley.com/doi/10.1002/...),
# and nearly all carry the DOI in the path - the reliable hydration join key - so we scan
# the whole URL rather than only matching a doi.org prefix.
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"'<>?#&]+", re.I)


def _doi_from_url(url: Optional[str]) -> Optional[str]:
    """Extract a DOI from anywhere in a URL (publisher page or doi.org), else None."""
    if not url:
        return None
    m = _DOI_RE.search(url)
    if not m:
        return None
    return m.group(0).rstrip("/.") or None


def _year(published_date: Optional[str]) -> Optional[int]:
    """ISO date string ('2022-03-01T...') -> 2022, or None if unparseable."""
    if not published_date or len(published_date) < 4 or not published_date[:4].isdigit():
        return None
    return int(published_date[:4])


def _snippet(res: dict) -> str:
    """Best available text for scoring: summary, else highlights, else raw text."""
    if res.get("summary"):
        return res["summary"]
    highlights = res.get("highlights")
    if highlights:
        return " ".join(h for h in highlights if h)
    return res.get("text") or ""


def _result_to_stub(res: dict) -> Paper:
    """One Exa result -> an un-hydrated Paper (no author_id / institutions / citations)."""
    author_name = (res.get("author") or "").strip()
    url = res.get("url")
    return Paper(
        title=res.get("title") or "(untitled)",
        abstract=_snippet(res),
        authors=[Author(name=author_name)] if author_name else [],
        year=_year(res.get("publishedDate")),
        url=url,
        doi=_doi_from_url(url),
        source="exa",
    )


class Exa:
    """Semantic publications search. Returns un-hydrated discovery stubs."""

    def __init__(self, client: Client, api_key: str, category: str = DEFAULT_CATEGORY):
        self.client = client
        self.api_key = api_key
        self.category = category

    def search(self, query: str, *, limit: int = 100,
               since_year: Optional[int] = None, **kw) -> list[Paper]:
        """Return up to ``limit`` (capped at 100) publication stubs for ``query``."""
        payload: dict = {
            "query": query,
            "category": self.category,
            "numResults": min(MAX_RESULTS, limit),
            "contents": {"summary": True, "highlights": True},
        }
        if since_year:
            payload["startPublishedDate"] = f"{since_year}-01-01"
        data = self.client.post_json(
            BASE, payload, headers={"x-api-key": self.api_key}, **kw)
        results = (data or {}).get("results") or []
        return [_result_to_stub(r) for r in results]

"""OpenAlex adapter, the field-agnostic backbone (no API key needed).

Used by the radar to pull papers by topic query or by venue+year, with abstracts
(reconstructed from OpenAlex's inverted index) and authoritative author
affiliations.
"""

from __future__ import annotations

from typing import Optional

from ..http import Client
from ..models import Author, Paper

BASE = "https://api.openalex.org/works"


def reconstruct_abstract(inverted_index: Optional[dict]) -> str:
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(word for _, word in positions)


def _work_to_paper(w: dict) -> Paper:
    authors = []
    for a in w.get("authorships", []):
        insts = a.get("institutions") or []
        aff = insts[0]["display_name"] if insts else None
        authors.append(Author(name=a["author"]["display_name"], affiliation=aff))
    src = ((w.get("primary_location") or {}).get("source") or {})
    return Paper(
        title=w.get("title") or "(untitled)",
        abstract=reconstruct_abstract(w.get("abstract_inverted_index")),
        authors=authors,
        year=w.get("publication_year"),
        venue=src.get("display_name"),
        url=(w.get("primary_location") or {}).get("landing_page_url") or w.get("id"),
        doi=w.get("doi"),
        citations=w.get("cited_by_count"),
        source="openalex",
    )


class OpenAlex:
    def __init__(self, client: Client, mailto: str = ""):
        self.client = client
        self.mailto = mailto

    def _page(self, params: dict, **kw) -> dict:
        if self.mailto:
            params = {**params, "mailto": self.mailto}
        return self.client.get_json(BASE, params, **kw)

    def search(self, query: Optional[str] = None, *, venue: Optional[str] = None,
               year: Optional[int] = None, limit: int = 100,
               require_abstract: bool = True, **kw) -> list[Paper]:
        """Fetch up to ``limit`` works matching a topic query and/or venue+year."""
        filters = []
        if venue:
            filters.append(f"primary_location.source.display_name.search:{venue}")
        if year:
            filters.append(f"publication_year:{year}")
        per_page = min(200, limit)
        params = {"per-page": per_page}
        if query:
            params["search"] = query
        if filters:
            params["filter"] = ",".join(filters)

        papers: list[Paper] = []
        cursor = "*"
        while len(papers) < limit:
            page_params = {**params, "cursor": cursor}
            data = self._page(page_params, **kw)
            for w in data.get("results", []):
                p = _work_to_paper(w)
                if require_abstract and not p.abstract:
                    continue
                papers.append(p)
                if len(papers) >= limit:
                    break
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not cursor or not data.get("results"):
                break
        return papers

    def best_affiliation(self, author_name: str, **kw) -> Optional[str]:
        """Look up a likely current affiliation for an author by name."""
        data = self.client.get_json(
            "https://api.openalex.org/authors",
            {"search": author_name, "per-page": 1,
             **({"mailto": self.mailto} if self.mailto else {})}, **kw)
        results = data.get("results") or []
        if not results:
            return None
        last = results[0].get("last_known_institutions") or []
        return last[0]["display_name"] if last else None

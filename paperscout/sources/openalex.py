"""OpenAlex adapter, the field-agnostic backbone (no API key needed).

Used by the radar to pull papers by topic query or by venue+year, with abstracts
(reconstructed from OpenAlex's inverted index) and authoritative author
affiliations.
"""

from __future__ import annotations

from typing import Optional

from ..http import Client
from ..models import Author, Institution, Paper

BASE = "https://api.openalex.org/works"
AUTHORS = "https://api.openalex.org/authors"


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


def _institution(inst: dict) -> Institution:
    return Institution(
        name=inst.get("display_name") or "(unknown)",
        id=inst.get("id"),
        ror=inst.get("ror"),
        country=inst.get("country_code"),
        type=inst.get("type"),
    )


def _work_to_paper(w: dict) -> Paper:
    authors = []
    for a in w.get("authorships", []):
        insts = [_institution(i) for i in (a.get("institutions") or [])]
        author = a.get("author") or {}
        authors.append(Author(
            name=author.get("display_name") or "(unknown)",
            affiliation=insts[0].name if insts else None,
            author_id=author.get("id"),
            orcid=author.get("orcid"),
            position=a.get("author_position"),
            is_corresponding=bool(a.get("is_corresponding")),
            institutions=insts,
        ))
    src = ((w.get("primary_location") or {}).get("source") or {})
    topics = [t.get("display_name") for t in (w.get("topics") or []) if t.get("display_name")]
    return Paper(
        title=w.get("title") or "(untitled)",
        abstract=reconstruct_abstract(w.get("abstract_inverted_index")),
        authors=authors,
        year=w.get("publication_year"),
        venue=src.get("display_name"),
        url=(w.get("primary_location") or {}).get("landing_page_url") or w.get("id"),
        doi=w.get("doi"),
        citations=w.get("cited_by_count"),
        openalex_id=w.get("id"),
        topics=topics,
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

    def by_doi(self, doi: str, **kw) -> Optional[Paper]:
        """Fetch the single OpenAlex work with this DOI, fully hydrated, or None.

        The reliable join for hydrating a paper discovered elsewhere (e.g. an Exa
        publications hit) back into structured authorship/institution metadata.
        `doi` may be a bare DOI or a doi.org URL; OpenAlex's `doi:` filter accepts both.
        """
        if not doi:
            return None
        data = self._page({"filter": f"doi:{doi}", "per-page": 1}, **kw)
        results = data.get("results") or []
        return _work_to_paper(results[0]) if results else None

    def best_affiliation(self, author_name: str, **kw) -> Optional[str]:
        """Look up a likely current affiliation for an author by name."""
        data = self.client.get_json(
            AUTHORS,
            {"search": author_name, "per-page": 1,
             **({"mailto": self.mailto} if self.mailto else {})}, **kw)
        results = data.get("results") or []
        if not results:
            return None
        last = results[0].get("last_known_institutions") or []
        return last[0]["display_name"] if last else None

    def fetch_author(self, author_id: str, **kw) -> Optional[dict]:
        """Fetch an OpenAlex author record by id (career totals + topic profile).

        Returns the trimmed fields Layer 1/2 use, or None if the id won't resolve.
        `author_id` may be a full OpenAlex URL or a bare id (A...).
        """
        aid = author_id.rsplit("/", 1)[-1] if author_id else ""
        if not aid:
            return None
        data = self.client.get_json(
            f"{AUTHORS}/{aid}",
            {**({"mailto": self.mailto} if self.mailto else {})}, **kw)
        if not data or not data.get("id"):
            return None
        stats = data.get("summary_stats") or {}
        last = data.get("last_known_institutions") or []
        return {
            "author_id": data.get("id"),
            "name": data.get("display_name"),
            "orcid": data.get("orcid"),
            "works_count": data.get("works_count"),
            "cited_by_count": data.get("cited_by_count"),
            "h_index": stats.get("h_index"),
            "i10_index": stats.get("i10_index"),
            "last_institution": (last[0].get("display_name") if last else None),
            "topics": [c.get("display_name") for c in (data.get("x_concepts") or [])[:8]
                       if c.get("display_name")],
            "counts_by_year": [{"year": c.get("year"), "works_count": c.get("works_count")}
                               for c in (data.get("counts_by_year") or [])],
        }

    def author_works(self, author_id: str, *, sort: str = "cited_by_count:desc",
                     per_page: int = 5, **kw) -> list[Paper]:
        """Fetch an author's works, ordered by `sort` (an OpenAlex sort clause)."""
        aid = author_id.rsplit("/", 1)[-1] if author_id else ""
        if not aid:
            return []
        data = self.client.get_json(
            BASE,
            {"filter": f"author.id:{aid}", "sort": sort, "per-page": per_page,
             **({"mailto": self.mailto} if self.mailto else {})}, **kw)
        return [_work_to_paper(w) for w in (data.get("results") or [])]

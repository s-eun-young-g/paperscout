"""Europe PMC adapter — abstracts/sentences for biomedical relation mining (no key)."""

from __future__ import annotations

from typing import Optional

from ..http import Client

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePMC:
    def __init__(self, client: Client):
        self.client = client

    def search(self, query: str, *, limit: int = 100, **kw) -> list[dict]:
        """Return article records (with abstractText where available)."""
        results: list[dict] = []
        cursor = "*"
        while len(results) < limit:
            data = self.client.get_json(
                BASE,
                {"query": query, "format": "json", "resultType": "core",
                 "pageSize": min(100, limit), "cursorMark": cursor}, **kw)
            batch = (data.get("resultList") or {}).get("result") or []
            if not batch:
                break
            results.extend(batch)
            nxt = data.get("nextCursorMark")
            if not nxt or nxt == cursor:
                break
            cursor = nxt
        return results[:limit]

    @staticmethod
    def to_records(articles: list[dict]) -> list[tuple[Optional[str], str]]:
        """(pmid, abstract_text) for articles that have an abstract."""
        out = []
        for a in articles:
            abs = a.get("abstractText")
            if abs:
                out.append((a.get("pmid") or a.get("id"), abs))
        return out

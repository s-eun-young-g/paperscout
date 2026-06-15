"""Europe PMC adapter, abstracts/sentences for biomedical relation mining (no key)."""

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

    @staticmethod
    def _best_url(article: dict) -> Optional[str]:
        """Prefer an open-access full-text link, falling back to the PMC article page."""
        urls = ((article.get("fullTextUrlList") or {}).get("fullTextUrl")) or []

        def rank(u: dict) -> int:
            score = 0
            if u.get("availabilityCode") == "OA":
                score += 2
            if u.get("site") in ("Europe_PMC", "PubMedCentral"):
                score += 1
            return score

        if urls:
            best = max(urls, key=rank)
            if best.get("url"):
                return best["url"]
        pmcid = article.get("pmcid")
        if pmcid:
            return f"https://europepmc.org/article/PMC/{pmcid}"
        return None

    @staticmethod
    def meta_map(articles: list[dict]) -> dict[str, dict]:
        """pmid -> bibliographic metadata, for enriching extracted evidence."""
        out: dict[str, dict] = {}
        for a in articles:
            pmid = a.get("pmid") or a.get("id")
            if not pmid:
                continue
            ji = a.get("journalInfo") or {}
            journal = (ji.get("journal") or {})
            types = [str(t).lower() for t in (a.get("pubTypeList") or {}).get("pubType", [])]
            out[str(pmid)] = {
                "title": a.get("title"),
                "authors": a.get("authorString"),
                "journal": journal.get("medlineAbbreviation") or journal.get("title"),
                "year": a.get("pubYear") or ji.get("yearOfPublication"),
                "url": EuropePMC._best_url(a),
                "doi": a.get("doi"),
                "cited_by": a.get("citedByCount") or 0,
                "is_review": any("review" in t for t in types),
            }
        return out

"""PubMed (NCBI E-utilities) adapter: a title -> DOI *resolver*, not a metadata source.

Exa frequently returns a PubMed / PMC landing page whose URL carries no DOI, and
OpenAlex's free-text search can miss the exact work. PubMed title search is precise and
its records carry the DOI - so we use it purely to *recover an identifier*, then hand
that DOI back to OpenAlex (primary) or Crossref (fallback) for the actual metadata. This
lets a no-DOI hit still land as an OpenAlex-grade row rather than being dropped.

Keyless; E-utilities just want tool + email params for the polite pool.
Docs: https://www.ncbi.nlm.nih.gov/books/NBK25501/
"""

from __future__ import annotations

from typing import Optional

from ..http import Client

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


class PubMed:
    """Title -> (DOI, title) lookups. The caller verifies the returned title before use."""

    def __init__(self, client: Client, email: str = "", tool: str = "paperscout"):
        self.client = client
        self.email = email
        self.tool = tool

    def _common(self) -> dict:
        p = {"tool": self.tool}
        if self.email:
            p["email"] = self.email
        return p

    def resolve_title(self, title: str, **kw) -> Optional[tuple[str, str]]:
        """Search PubMed by title; return (doi, pubmed_title) for the top hit, or None.

        Returns the record's own title so the caller can confirm the match (via the same
        overlap check used elsewhere) before trusting the recovered DOI.
        """
        if not title:
            return None
        data = self.client.get_json(ESEARCH, {
            **self._common(), "db": "pubmed", "retmode": "json",
            "retmax": 1, "term": f"{title}[Title]"}, **kw)
        ids = (((data or {}).get("esearchresult") or {}).get("idlist")) or []
        if not ids:
            return None
        pmid = ids[0]
        summ = self.client.get_json(ESUMMARY, {
            **self._common(), "db": "pubmed", "retmode": "json", "id": pmid}, **kw)
        rec = ((summ or {}).get("result") or {}).get(pmid) or {}
        pm_title = rec.get("title") or ""
        for aid in (rec.get("articleids") or []):
            if (aid.get("idtype") or "").lower() == "doi" and aid.get("value"):
                return (aid["value"], pm_title)
        return None

"""Crossref adapter: DOI-keyed metadata, the rate-limit / coverage fallback for hydration.

OpenAlex is the *primary* hydration source - it alone carries normalized institution ids
and disambiguated author ids, which the research-group rollup joins on. Crossref is the
backstop: when OpenAlex 429s or doesn't know a DOI, Crossref still yields author names,
affiliation strings (with a ROR id when the record has one), and a citation count - enough
to roll a paper up into a group keyed by PI *name* rather than dropping it.

Papers hydrated here are tagged ``source="crossref"`` so downstream can tell OpenAlex-grade
rows (full institution/author ids) from fallback-grade ones. Crossref is keyless; the polite
pool just wants a mailto. Docs: https://api.crossref.org/swagger-ui/index.html
"""

from __future__ import annotations

import re
from typing import Optional

from ..http import Client
from ..models import Author, Institution, Paper

BASE = "https://api.crossref.org/works"
_TAG_RE = re.compile(r"<[^>]+>")  # Crossref abstracts are JATS XML; strip tags for scoring.


def _strip(text: Optional[str]) -> str:
    return _TAG_RE.sub(" ", text).strip() if text else ""


def _affiliation(aff: dict) -> Institution:
    ror = None
    for ident in (aff.get("id") or []):
        if (ident.get("id-type") or "").upper() == "ROR" and ident.get("id"):
            ror = ident["id"]
            break
    return Institution(name=aff.get("name") or "(unknown)", ror=ror)


def _authors(raw: list[dict]) -> list[Author]:
    n = len(raw)
    authors: list[Author] = []
    for i, a in enumerate(raw):
        name = " ".join(x for x in (a.get("given"), a.get("family")) if x) \
            or a.get("name") or "(unknown)"
        insts = [_affiliation(af) for af in (a.get("affiliation") or []) if af.get("name")]
        # Crossref has no "last" marker; derive position from list order (last = PI proxy).
        position = "first" if i == 0 else ("last" if i == n - 1 else "middle")
        authors.append(Author(
            name=name,
            affiliation=insts[0].name if insts else None,
            orcid=a.get("ORCID"),
            position=position,
            institutions=insts,
        ))
    return authors


def _year(msg: dict) -> Optional[int]:
    for key in ("published", "published-print", "published-online", "issued"):
        parts = (msg.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def _message_to_paper(msg: dict) -> Paper:
    titles = msg.get("title") or []
    containers = msg.get("container-title") or []
    return Paper(
        title=titles[0] if titles else "(untitled)",
        abstract=_strip(msg.get("abstract")),
        authors=_authors(msg.get("author") or []),
        year=_year(msg),
        venue=containers[0] if containers else None,
        url=msg.get("URL"),
        doi=msg.get("DOI"),
        citations=msg.get("is-referenced-by-count"),
        source="crossref",
    )


class Crossref:
    """DOI-keyed lookups against Crossref. No institution/author ids (name-level only)."""

    def __init__(self, client: Client, mailto: str = ""):
        self.client = client
        self.mailto = mailto

    def by_doi(self, doi: str, **kw) -> Optional[Paper]:
        """Fetch the Crossref record for a DOI as a Paper (source='crossref'), or None."""
        if not doi:
            return None
        params = {"mailto": self.mailto} if self.mailto else {}
        data = self.client.get_json(f"{BASE}/{doi}", params, **kw)
        msg = (data or {}).get("message")
        return _message_to_paper(msg) if msg else None

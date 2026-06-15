"""OpenReview adapter (best-effort) for venues that publish there (ICLR, NeurIPS…).

Pass an OpenReview ``venueid`` such as ``ICLR.cc/2024/Conference``. Accepted papers
carry that as ``content.venueid``. OpenReview's schema shifts between venues, so this
is intentionally defensive and may need the exact venueid for a given year.
"""

from __future__ import annotations

from typing import Optional

from ..http import Client
from ..models import Author, Paper

BASE = "https://api2.openreview.net/notes"


def _content_value(content: dict, key: str):
    v = content.get(key)
    if isinstance(v, dict):       # API v2 wraps values: {"value": ...}
        return v.get("value")
    return v


def _note_to_paper(note: dict, venue_hint: Optional[str]) -> Optional[Paper]:
    content = note.get("content") or {}
    title = _content_value(content, "title")
    if not title:
        return None
    authors_raw = _content_value(content, "authors") or []
    authors = [Author(name=a) for a in authors_raw] if isinstance(authors_raw, list) else []
    return Paper(
        title=str(title).strip(),
        abstract=str(_content_value(content, "abstract") or "").strip(),
        authors=authors,
        venue=_content_value(content, "venue") or venue_hint,
        url=f"https://openreview.net/forum?id={note.get('id')}",
        source="openreview",
    )


class OpenReview:
    def __init__(self, client: Client):
        self.client = client

    def venue_papers(self, venueid: str, limit: int = 1000, **kw) -> list[Paper]:
        papers: list[Paper] = []
        offset = 0
        page = min(1000, limit)
        while len(papers) < limit:
            data = self.client.get_json(
                BASE,
                {"content.venueid": venueid, "limit": page, "offset": offset}, **kw)
            notes = data.get("notes") or []
            if not notes:
                break
            for n in notes:
                p = _note_to_paper(n, venueid)
                if p and p.abstract:
                    papers.append(p)
                    if len(papers) >= limit:
                        break
            offset += len(notes)
            if len(notes) < page:
                break
        return papers

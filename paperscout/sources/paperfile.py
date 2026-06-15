"""Ingest papers from a local CSV or JSON dump.

This is the adapter for upcoming conferences (e.g. ICML 2026) whose accepted lists
aren't indexed by OpenAlex yet — feed the scraped/exported dump directly.

CSV: columns ``title``, ``abstract``, and ``authors`` (authors separated by ``;``,
each optionally ``Name (Affiliation)``).
JSON: a list of ``{"title", "abstract", "authors": [{"name", "affiliation"}], ...}``
or the same with ``authors`` as a list of strings.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from ..models import Author, Paper

_AFF_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<aff>.+)\)\s*$")


def _parse_author(item) -> Author:
    if isinstance(item, dict):
        return Author(name=item.get("name", "").strip(),
                      affiliation=(item.get("affiliation") or None))
    m = _AFF_RE.match(str(item).strip())
    if m:
        return Author(name=m.group("name").strip(), affiliation=m.group("aff").strip())
    return Author(name=str(item).strip())


def _split_authors(value) -> list[Author]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_parse_author(a) for a in value if a]
    return [_parse_author(a) for a in str(value).split(";") if a.strip()]


def load(path: str | Path) -> list[Paper]:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return _load_json(path)
    return _load_csv(path)


def _load_json(path: Path) -> list[Paper]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("results") or data.get("papers") or []
    papers = []
    for row in data:
        papers.append(Paper(
            title=row.get("title", "").strip(),
            abstract=(row.get("abstract") or "").strip(),
            authors=_split_authors(row.get("authors")),
            year=row.get("year"),
            venue=row.get("venue"),
            url=row.get("url"),
            doi=row.get("doi"),
            source="file",
        ))
    return [p for p in papers if p.title]


def _load_csv(path: Path) -> list[Paper]:
    papers = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        lower = {f.lower(): f for f in (reader.fieldnames or [])}

        def col(row, *names):
            for n in names:
                if n in lower:
                    return row.get(lower[n])
            return None

        for row in reader:
            title = (col(row, "title") or "").strip()
            if not title:
                continue
            papers.append(Paper(
                title=title,
                abstract=(col(row, "abstract", "summary") or "").strip(),
                authors=_split_authors(col(row, "authors", "author")),
                venue=col(row, "venue"),
                url=col(row, "url", "link"),
                doi=col(row, "doi"),
                source="file",
            ))
    return papers

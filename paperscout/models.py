"""Normalized data models shared across sources and analyses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Institution:
    """A normalized affiliation with the stable ids downstream joins need."""

    name: str
    id: Optional[str] = None        # OpenAlex institution id (https://openalex.org/I...)
    ror: Optional[str] = None       # ROR id
    country: Optional[str] = None   # ISO 2-letter country code
    type: Optional[str] = None      # education | healthcare | company | ...


@dataclass
class Author:
    name: str
    affiliation: Optional[str] = None            # primary institution display name (back-compat)
    author_id: Optional[str] = None              # OpenAlex author id, the stable join key
    orcid: Optional[str] = None
    position: Optional[str] = None               # "first" | "middle" | "last"
    is_corresponding: bool = False
    institutions: list[Institution] = field(default_factory=list)

    @property
    def primary_institution(self) -> Optional[Institution]:
        return self.institutions[0] if self.institutions else None


@dataclass
class Paper:
    """A normalized paper from any source (OpenAlex, OpenReview, file, ...)."""

    title: str
    abstract: str = ""
    authors: list[Author] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    source: Optional[str] = None  # which adapter produced it
    citations: Optional[int] = None
    openalex_id: Optional[str] = None                  # the work id
    topics: list[str] = field(default_factory=list)    # OpenAlex topic display names

    @property
    def text(self) -> str:
        return f"{self.title}. {self.abstract}".strip()

    @property
    def first_author(self) -> Optional[Author]:
        return self.authors[0] if self.authors else None

    @property
    def last_author(self) -> Optional[Author]:
        """Senior-author proxy: the one tagged position 'last', else the last listed."""
        for a in self.authors:
            if a.position == "last":
                return a
        return self.authors[-1] if self.authors else None

    @property
    def corresponding_authors(self) -> list[Author]:
        return [a for a in self.authors if a.is_corresponding]

    @property
    def lead_affiliation(self) -> Optional[str]:
        for a in self.authors:
            if a.affiliation:
                return a.affiliation
        return None


@dataclass
class ScoredPaper:
    paper: Paper
    score: float
    tier: int                       # 1 (strongest) .. 3, or 0 = below cut
    pillars: list[str] = field(default_factory=list)   # matched pillar keys
    reason: str = ""


@dataclass
class Evidence:
    pmid: Optional[str]
    sentence: str
    source: str


@dataclass
class Triple:
    """A drug -> (target) -> readout relation with a direction (up/down)."""

    drug: str
    readout: str
    direction: str                  # "up" | "down" | "changes"
    target: Optional[str] = None
    evidence: list[Evidence] = field(default_factory=list)
    targets_from_db: list[str] = field(default_factory=list)  # Open Targets MoA targets

    @property
    def n_evidence(self) -> int:
        return len(self.evidence)

    @property
    def key(self) -> tuple:
        return (self.drug.lower(), self.readout.lower(), self.direction)

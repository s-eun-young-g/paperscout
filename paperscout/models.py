"""Normalized data models shared across sources and analyses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Author:
    name: str
    affiliation: Optional[str] = None


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

    @property
    def text(self) -> str:
        return f"{self.title}. {self.abstract}".strip()

    @property
    def first_author(self) -> Optional[Author]:
        return self.authors[0] if self.authors else None

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
    # bibliographic metadata (populated when available, e.g. from Europe PMC core)
    title: Optional[str] = None
    authors: Optional[str] = None      # raw author string, e.g. "Zhai Y, Yu Y, ..."
    journal: Optional[str] = None      # short journal abbreviation
    year: Optional[str] = None
    url: Optional[str] = None          # best full-text / source link
    doi: Optional[str] = None
    cited_by: int = 0
    is_review: bool = False

    @property
    def first_author(self) -> Optional[str]:
        if not self.authors:
            return None
        return self.authors.split(",")[0].strip().rstrip(".") or None

    @property
    def citation(self) -> str:
        """Short human citation, e.g. 'Zhai Y et al., Cancer Immunol Immunother 2026'."""
        fa = self.first_author
        author = (f"{fa} et al." if "," in (self.authors or "") else fa) if fa else None
        venue = " ".join(p for p in (self.journal, str(self.year) if self.year else None) if p)
        parts = [p for p in (author, venue) if p]
        if parts:
            return ", ".join(parts)
        return f"PMID:{self.pmid}" if self.pmid else self.source

    @property
    def link(self) -> Optional[str]:
        """Best click-through URL: source full text, else PubMed, else DOI."""
        if self.url:
            return self.url
        if self.pmid:
            return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"
        if self.doi:
            return f"https://doi.org/{self.doi}"
        return None


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

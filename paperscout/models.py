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

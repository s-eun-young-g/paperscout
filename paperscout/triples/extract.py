"""Sentence-level extraction of drug -> readout direction from abstracts.

Deliberately simple and transparent (no ML model needed): find sentences that
co-mention the drug and a plasma readout, then classify the direction from lexical
cues. Aggregated over many abstracts, the majority direction + evidence count is a
strong candidate signal for a relation. An optional LLM pass can refine this, but
the heuristic stands alone and is fully offline once abstracts are cached.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable, Optional

from ..models import Evidence, Triple

# Common plasma/serum readouts (extend freely). Each maps display -> match patterns.
READOUTS: dict[str, tuple[str, ...]] = {
    "CRP": ("c-reactive protein", "crp", "hscrp", "hs-crp"),
    "IL-6": ("interleukin-6", "interleukin 6", "il-6", "il6"),
    "TNF-alpha": ("tnf-alpha", "tnf-α", "tumor necrosis factor"),
    "LDL": ("ldl cholesterol", "ldl-c", "low-density lipoprotein", "ldl"),
    "HDL": ("hdl cholesterol", "hdl-c", "high-density lipoprotein", "hdl"),
    "triglycerides": ("triglyceride", "triglycerides"),
    "HbA1c": ("hba1c", "glycated hemoglobin", "hemoglobin a1c"),
    "glucose": ("fasting glucose", "blood glucose", "plasma glucose"),
    "SHBG": ("sex hormone-binding globulin", "sex hormone binding globulin", "shbg"),
    "IGF-1": ("igf-1", "igf-i", "insulin-like growth factor"),
    "LH": ("luteinizing hormone", "lh "),
    "FSH": ("follicle-stimulating hormone", "fsh"),
    "CCL17": ("ccl17", "tarc", "thymus and activation-regulated chemokine"),
    "testosterone": ("testosterone",),
    "estradiol": ("estradiol", "oestradiol"),
    "fibrinogen": ("fibrinogen",),
    "ferritin": ("ferritin",),
    "albumin": ("serum albumin", "albumin"),
}

# Only unambiguous morphological stems, comparative words like "higher"/"greater"
# and direction-ambiguous ones like "improve"/"normalize" are deliberately excluded
# to keep precision high (a noisy cue flips the aggregated direction).
_UP = ("increas", "elevat", "upregulat", "up-regulat", "induc", "augment")
_DOWN = ("decreas", "reduc", "lower", "suppress", "downregulat", "down-regulat",
         "inhibit", "attenuat", "declin")

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
# Match real HTML tags only: require a letter (or /) after '<' so statistical
# comparison operators like "P<0.05" / "P > 0.05" are left intact.
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def _clean(text: str) -> str:
    """Strip inline markup (Europe PMC abstracts carry <h4>...</h4> section labels)
    and collapse whitespace, so evidence quotes are clean prose."""
    return re.sub(r"\s+", " ", _TAG.sub(" ", text)).strip()


def _sentences(text: str) -> list[str]:
    return _SENT_SPLIT.split(text)


def _direction(sentence_lower: str) -> Optional[str]:
    up = sum(sentence_lower.count(c) for c in _UP)
    down = sum(sentence_lower.count(c) for c in _DOWN)
    if up == 0 and down == 0:
        return None
    if up > down:
        return "up"
    if down > up:
        return "down"
    return "changes"


def _mentions(text_lower: str, patterns: Iterable[str]) -> bool:
    return any(p in text_lower for p in patterns)


def commit_direction(n_up: int, n_down: int, *, unanimity_threshold: float = 0.25,
                     min_evidence: int = 1) -> tuple[str, bool]:
    """Decide a triple's committed direction from its vote tally.

    Returns (direction, disagreement). Abstain ("unclear") rather than emit a
    coin-flip: commit a signed direction only when there are at least
    ``min_evidence`` signed votes AND the minority fraction is within
    ``unanimity_threshold``. A split above the threshold sets disagreement=True
    and abstains (the damaging confident-wrong-direction case the oracle must
    avoid). Too few votes also abstains, but is not flagged as disagreement.
    """
    signed = n_up + n_down
    if signed < min_evidence or signed == 0:
        return "unclear", False
    minority = min(n_up, n_down)
    if minority / signed > unanimity_threshold:
        return "unclear", True
    return ("up" if n_up >= n_down else "down"), False


def extract_triples(
    drug: str,
    records: list[tuple[Optional[str], str]],
    *,
    drug_aliases: Iterable[str] = (),
    readouts: Optional[dict[str, tuple[str, ...]]] = None,
    meta: Optional[dict[str, dict]] = None,
    unanimity_threshold: float = 0.25,
    min_evidence: int = 1,
) -> list[Triple]:
    """Aggregate one (drug -> readout) triple per readout, with a direction vote.

    Each supporting abstract sentence casts an up/down vote; the committed
    direction is decided by ``commit_direction`` (abstain on insufficient or
    split evidence). ``meta`` maps pmid -> bibliographic fields so each Evidence
    can cite a real paper and link to the source.
    """
    readouts = readouts or READOUTS
    meta = meta or {}
    drug_terms = [drug.lower(), *[a.lower() for a in drug_aliases]]
    # readout -> list[Evidence] (each Evidence carries its own sentence direction)
    buckets: dict[str, list[Evidence]] = defaultdict(list)

    for pmid, text in records:
        for sent in _sentences(_clean(text)):
            low = sent.lower()
            if not any(d in low for d in drug_terms):
                continue
            for readout, patterns in readouts.items():
                if not _mentions(low, patterns):
                    continue
                direction = _direction(low)
                if direction is None:
                    continue
                ev = Evidence(pmid=pmid, sentence=sent.strip(), source="europepmc",
                              direction=direction)
                m = meta.get(str(pmid)) if pmid is not None else None
                if m:
                    ev.title = m.get("title")
                    ev.authors = m.get("authors")
                    ev.journal = m.get("journal")
                    ev.year = m.get("year")
                    ev.url = m.get("url")
                    ev.doi = m.get("doi")
                    ev.cited_by = m.get("cited_by") or 0
                    ev.is_review = bool(m.get("is_review"))
                buckets[readout].append(ev)

    triples = []
    for readout, ev in buckets.items():
        n_up = sum(1 for e in ev if e.direction == "up")
        n_down = sum(1 for e in ev if e.direction == "down")
        direction, disagreement = commit_direction(
            n_up, n_down, unanimity_threshold=unanimity_threshold,
            min_evidence=min_evidence)
        # most authoritative evidence first (reviews, then citation count)
        ev.sort(key=lambda e: (e.is_review, e.cited_by), reverse=True)
        triples.append(Triple(drug=drug, readout=readout, direction=direction,
                              n_up=n_up, n_down=n_down, disagreement=disagreement,
                              evidence=ev))
    # surface the best-supported relations first
    triples.sort(key=lambda t: (t.committed, t.n_evidence), reverse=True)
    return triples

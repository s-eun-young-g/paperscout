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
# Match real HTML tags only — require a letter (or /) after '<' so statistical
# comparison operators like "P<0.05" / "P > 0.05" are left intact.
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def _clean(text: str) -> str:
    """Strip inline markup (Europe PMC abstracts carry <h4>…</h4> section labels)
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


def extract_triples(
    drug: str,
    records: list[tuple[Optional[str], str]],
    *,
    drug_aliases: Iterable[str] = (),
    readouts: Optional[dict[str, tuple[str, ...]]] = None,
    meta: Optional[dict[str, dict]] = None,
) -> list[Triple]:
    """Aggregate (drug, readout, direction) candidates with evidence over abstracts.

    ``meta`` maps pmid -> bibliographic fields (title/authors/journal/year/url/doi/
    cited_by/is_review); when present, each Evidence is enriched so the report can
    cite a real paper and link to the source instead of a bare PMID.
    """
    readouts = readouts or READOUTS
    meta = meta or {}
    drug_terms = [drug.lower(), *[a.lower() for a in drug_aliases]]
    # (readout, direction) -> list[Evidence]
    buckets: dict[tuple[str, str], list[Evidence]] = defaultdict(list)

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
                ev = Evidence(pmid=pmid, sentence=sent.strip(), source="europepmc")
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
                buckets[(readout, direction)].append(ev)

    # most authoritative evidence first (reviews, then citation count) so the
    # report surfaces the canonical paper rather than an arbitrary abstract.
    triples = []
    for (readout, direction), ev in buckets.items():
        ev.sort(key=lambda e: (e.is_review, e.cited_by), reverse=True)
        triples.append(Triple(drug=drug, readout=readout, direction=direction, evidence=ev))
    triples.sort(key=lambda t: -t.n_evidence)
    return triples

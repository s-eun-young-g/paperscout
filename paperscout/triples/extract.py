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
from .confidence import score_triple

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
    # --- 2.2 readout-vocab expansion: Olink-panel secreted proteins, prioritized by manifold factor.
    # Lead with full names; avoid bare ambiguous short symbols (see vocab_expansion_spec.md s3).
    "adiponectin": ("adiponectin", "adipoq"),                                          # PC4 metabolic
    "leptin": ("leptin",),                                                             # PC4 metabolic
    "PCSK9": ("pcsk9", "proprotein convertase subtilisin/kexin type 9",
              "proprotein convertase subtilisin kexin 9"),                             # LDL axis
    "GDF15": ("gdf15", "gdf-15", "growth differentiation factor 15",
              "growth/differentiation factor 15"),                                     # TNF-superfamily/stress
    "cystatin C": ("cystatin c", "cystatin-c", "cst3"),                                # PC1/renal
    "PAI-1": ("pai-1", "plasminogen activator inhibitor-1",
              "plasminogen activator inhibitor 1"),                                    # PC2 platelet/GF
    "MMP-9": ("mmp-9", "mmp9", "matrix metalloproteinase-9",
              "matrix metalloproteinase 9", "gelatinase b"),                           # neutrophil sub-factor
    "sCD163": ("scd163", "soluble cd163", "cd163"),                                    # macrophage sub-factor
    "RANKL": ("rankl", "rank ligand",
              "receptor activator of nuclear factor kappa-b ligand"),                  # TNF-superfamily
    # --- 2.2 Tier-B: push the thin manifold factors (PC2/PC3/neutrophil/macrophage/
    # TNF-superfamily) toward breadth >= 3. Full names lead; bare ambiguous short
    # complement symbols (c3/c5) deliberately omitted for precision.
    "complement C3": ("complement c3", "complement component 3"),                      # PC3 complement
    "complement C5": ("complement c5", "complement component 5"),                      # PC3 complement
    "myeloperoxidase": ("myeloperoxidase", "mpo"),                                     # neutrophil
    "NGAL": ("ngal", "lipocalin-2", "lipocalin 2",
             "neutrophil gelatinase-associated lipocalin"),                            # neutrophil
    "YKL-40": ("ykl-40", "chi3l1", "chitinase-3-like protein 1"),                      # macrophage
    "sCD14": ("soluble cd14", "scd14", "cd14"),                                        # macrophage
    "sCD40L": ("soluble cd40 ligand", "scd40l", "cd40 ligand", "cd40l"),               # PC2 platelet
    "osteoprotegerin": ("osteoprotegerin", "tnfrsf11b", "opg"),                        # TNF-superfamily
}

# Only unambiguous morphological stems, comparative words like "higher"/"greater"
# and direction-ambiguous ones like "improve"/"normalize" are deliberately excluded
# to keep precision high (a noisy cue flips the aggregated direction).
# "induc" deliberately excluded: it matches non-directional "X-induced" phrasing
# ("stasis-induced", "exercise-induced") far more than a real "induced an increase",
# and a genuine increase is already caught by "increas".
_UP = ("increas", "elevat", "upregulat", "up-regulat", "augment")
_DOWN = ("decreas", "reduc", "lower", "suppress", "downregulat", "down-regulat",
         "inhibit", "attenuat", "declin")

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
# Match real HTML tags only: require a letter (or /) after '<' so statistical
# comparison operators like "P<0.05" / "P > 0.05" are left intact.
_TAG = re.compile(r"</?[a-zA-Z][^>]*>")

# Split a sentence into conjuncts on coordinating boundaries so a cue is
# attributed to the analyte in its own clause, not a neighbour. Deliberately NOT
# splitting on commas, nor on a list-terminating ", and": that would break list
# reporting ("decrease in NLR, PLR, SII, and CRP" / "reduced CRP, IL-6 and
# TNF-alpha"), where one verb governs a comma-separated analyte list. Only a
# clause-joining " and " (not preceded by a comma) is treated as a boundary.
_CLAUSE_SPLIT = re.compile(
    r";|\s+(?:but|whereas|while|although|whilst)\s+|(?<!,)\s+and\s+", re.I)

# Cohort/baseline descriptors where a directional word characterises the study
# population rather than the drug effect ("patients with elevated CRP",
# "subjects with reduced X at baseline"). Neutralise the cue, keep the clause.
_COHORT_CUE = re.compile(
    r"\bwith\s+(?:elevated|raised|high|low|reduced|increased|decreased|impaired)\b"
    r"|\b(?:elevated|raised|high|low|reduced|increased|decreased)\b[\w\s-]{0,30}?\bat baseline\b",
    re.I)

# A clause that has its own explicit trial-arm / agent subject (e.g. "gemfibrozil
# therapy increased ...", "the placebo group"). Used only to detect a COMPARATOR
# clause: when the queried drug is absent from such a clause, its cue belongs to the
# other agent, not the queried drug. Deliberately narrow - matching merely "lacks the
# drug name" is too aggressive (it strips the drug's own effect when the drug is the
# subject of a sibling clause, as in "growth hormone ... consequent elevation of IGF-1").
_COMPARATOR_SUBJECT = re.compile(
    r"\b(?:therapy|treatment|administration|regimen|infusion|supplementation|group|arm)\b", re.I)


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


def _direction_for_readout(
    sentence_lower: str, patterns: "tuple[str, ...]",
    drug_terms: "Iterable[str]" = ()) -> Optional[str]:
    """Direction attributed to a specific readout, counting cues only in the
    conjunct(s) that mention it and ignoring cohort-descriptor cues.

    This kills two confounds, the highest validity risk for the prediction oracle:
    - cross-analyte: a cue describing a neighbouring analyte ("reduced triglycerides
      and increased ApoA-I in HDL"), handled by per-clause attribution.
    - cross-drug: a comparator drug's cue in a comparative sentence ("ciprofibrate
      reduced and gemfibrozil increased fibrinogen"). When ``drug_terms`` is given and
      the queried drug is named in the sentence but NOT in this readout-bearing clause,
      the clause belongs to a different subject, so its cue is not attributed here.
    """
    drug_terms = list(drug_terms)
    clauses = _CLAUSE_SPLIT.split(sentence_lower)
    drug_in_a_clause = bool(drug_terms) and any(_mentions(c, drug_terms) for c in clauses)
    up = down = 0
    seen = False
    for clause in clauses:
        if not _mentions(clause, patterns):
            continue
        # cross-drug gate: skip a readout clause only when it is a COMPARATOR clause -
        # i.e. it has its own trial-arm subject but does NOT name the queried drug,
        # while the queried drug is named in some other clause. This drops
        # "...and gemfibrozil therapy increased fibrinogen" without dropping the drug's
        # own effect phrased subject-less ("consequent elevation of IGF-1").
        if (drug_in_a_clause and not _mentions(clause, drug_terms)
                and _COMPARATOR_SUBJECT.search(clause)):
            continue
        seen = True
        c = _COHORT_CUE.sub(" ", clause)
        up += sum(c.count(x) for x in _UP)
        down += sum(c.count(x) for x in _DOWN)
    if not seen or (up == 0 and down == 0):
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
                direction = _direction_for_readout(low, patterns, drug_terms)
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
        t = Triple(drug=drug, readout=readout, direction=direction,
                   n_up=n_up, n_down=n_down, disagreement=disagreement, evidence=ev)
        # Confidence is computed strictly after the direction is committed above,
        # so it can never influence the sign or the abstain decision.
        t.confidence = score_triple(t)
        triples.append(t)
    # surface the best-supported relations first
    triples.sort(key=lambda t: (t.committed, t.n_evidence), reverse=True)
    return triples

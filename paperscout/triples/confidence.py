"""Calibrated confidence for a committed drug -> readout prediction.

This layer sits strictly AFTER sign generation. It never changes the committed
direction and never touches the firewall or ``commit_direction``: a prediction is
signed (or abstained) exactly as before, and confidence only exposes the
uncertainty already present in the literature so downstream coupling can weight
stronger predictions more heavily.

The score in [0, 1] is a transparent, deterministic blend of three families of
signal, all already captured by the miner (no ML, no extra network):

1. Quantity   - how many signed abstracts support the call (saturating).
2. Consistency- the directional agreement among them (21 down / 0 up beats
                3 down / 1 up even though both commit "down").
3. Quality    - the strength of the evidence: study model (human trial >
                human observational > animal > in vitro), recency, cohort size,
                citations, and review status.

Study model and cohort size are derived heuristically from the evidence text
(in the same transparent, lexical-cue spirit as direction extraction). Year,
citation count, and review status come straight off the Evidence metadata.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Optional

from ..models import Evidence, Triple

# --- study-model weights (the "MODEL used" axis) -------------------------------
# A human randomized trial is the strongest single piece of evidence for a real
# drug effect; an in-vitro dish is the weakest. Unknown sits mid-low (neutral).
MODEL_WEIGHTS: dict[str, float] = {
    "human_trial": 1.00,
    "human_observational": 0.80,
    "animal": 0.50,
    "in_vitro": 0.35,
    "unknown": 0.60,
}
# Priority order when a single abstract carries cues for more than one model:
# a human-trial reading dominates a co-mentioned cell or animal arm.
_MODEL_PRIORITY = ("human_trial", "human_observational", "animal", "in_vitro")

_TRIAL_CUES = ("randomi", "double-blind", "double blind", "placebo-controlled",
               "placebo controlled", "clinical trial", "phase ii", "phase iii",
               "phase 2", "phase 3", " rct", "crossover trial")
_HUMAN_OBS_CUES = ("patients", "subjects", "participants", "individuals", "cohort",
                   "cross-sectional", "case-control", "case control", "observational",
                   "in humans", "men and women", "adults")
_ANIMAL_CUES = ("mice", "mouse", "murine", " rat", "rats", "rodent", "zebrafish",
                "porcine", "canine", "knockout", "wild-type", " in vivo")
_IN_VITRO_CUES = ("in vitro", "cell line", "cultured", "hepatocyte", "hepg2",
                  "thp-1", "thp1", "ex vivo", "cell culture", "cells were", "in cultured")

# cohort size: "n = 1,234", "1234 patients", "200 subjects/participants/individuals"
_COHORT_RE = re.compile(
    r"\bn\s*=\s*([0-9][0-9,]{0,6})\b"
    r"|\b([0-9][0-9,]{1,6})\s+(?:patients|subjects|participants|individuals|men|women)\b",
    re.I)

# How fast quantity saturates. n_signed = 2 -> 0.33, 5 -> 0.63, 10 -> 0.86, 21 -> 0.98.
_QUANTITY_TAU = 5.0


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def classify_model(ev: Evidence) -> str:
    """Best-guess study model for one piece of evidence, from its text.

    Heuristic and transparent: scans the sentence plus title for cue words and
    returns the highest-priority model whose cues appear (human trial > human
    observational > animal > in vitro), else 'unknown'.
    """
    # Pad with spaces so word-boundary cues (e.g. " rct", " in vivo") also match
    # at the very start or end of the text.
    text = f" {ev.sentence or ''} {ev.title or ''} ".lower()
    hits = {
        "human_trial": any(c in text for c in _TRIAL_CUES),
        "human_observational": any(c in text for c in _HUMAN_OBS_CUES),
        "animal": any(c in text for c in _ANIMAL_CUES),
        "in_vitro": any(c in text for c in _IN_VITRO_CUES),
    }
    for model in _MODEL_PRIORITY:
        if hits[model]:
            return model
    return "unknown"


def cohort_size(ev: Evidence) -> Optional[int]:
    """Extract a reported cohort size from the evidence text, if present."""
    m = _COHORT_RE.search(ev.sentence or "")
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    try:
        n = int(raw.replace(",", ""))
    except (TypeError, ValueError):
        return None
    return n if 1 < n < 10_000_000 else None


def _recency(year: Optional[int]) -> float:
    if year is None:
        return 0.85
    if year >= 2018:
        return 1.0
    if year >= 2010:
        return 0.9
    if year >= 2000:
        return 0.8
    return 0.7


def _cohort_factor(n: Optional[int]) -> float:
    """0 (no cohort reported) to 1 (large cohort), log-scaled: 10 -> .33, 1000 -> 1."""
    if not n:
        return 0.0
    return _clamp(math.log10(n) / 3.0)


@dataclass
class ConfidenceBreakdown:
    """Transparent confidence for a committed prediction (all parts exposed)."""

    score: float                 # 0..1, the headline confidence
    band: str                    # "high" | "moderate" | "low"
    quantity: float              # saturating function of n_signed
    consistency: float           # directional agreement, 0 (split) .. 1 (unanimous)
    quality: float               # evidence-strength blend (model/recency/cohort/citation)
    n_signed: int
    agreement: float             # majority / signed (0.5 .. 1.0)
    dominant_model: str          # strongest study model among the majority evidence
    model_mix: dict[str, int]    # count of evidence by model
    mean_year: Optional[int]
    max_cited_by: int
    n_reviews: int
    cohort_max: Optional[int]

    def as_dict(self) -> dict:
        return asdict(self)


def _band(score: float) -> str:
    if score >= 0.70:
        return "high"
    if score >= 0.45:
        return "moderate"
    return "low"


def score_triple(t: Triple) -> ConfidenceBreakdown:
    """Confidence for a triple. Read-only: does not alter the committed direction.

    Quality is computed over the evidence that voted with the committed (majority)
    direction, so dissenting abstracts do not inflate it.
    """
    majority = t.direction if t.committed else ("up" if t.n_up >= t.n_down else "down")
    maj_ev = [e for e in t.evidence if e.direction == majority] or list(t.evidence)

    # 1. quantity (saturating in the number of signed abstracts)
    quantity = 1.0 - math.exp(-t.n_signed / _QUANTITY_TAU) if t.n_signed else 0.0

    # 2. consistency (directional agreement, mapped so 0.5 -> 0, 1.0 -> 1)
    agreement = (max(t.n_up, t.n_down) / t.n_signed) if t.n_signed else 0.0
    consistency = _clamp((agreement - 0.5) / 0.5)

    # 3. quality of the majority evidence
    models = [classify_model(e) for e in maj_ev]
    model_mix: dict[str, int] = {}
    for m in models:
        model_mix[m] = model_mix.get(m, 0) + 1
    dominant_model = next((m for m in _MODEL_PRIORITY if m in model_mix), "unknown")
    model_w = MODEL_WEIGHTS[dominant_model]

    years = [int(e.year) for e in maj_ev if e.year and str(e.year).isdigit()]
    mean_year = round(sum(years) / len(years)) if years else None
    recency = _recency(max(years) if years else None)

    max_cited = max((e.cited_by or 0 for e in maj_ev), default=0)
    n_reviews = sum(1 for e in maj_ev if e.is_review)
    cohorts = [c for c in (cohort_size(e) for e in maj_ev) if c]
    cohort_max = max(cohorts) if cohorts else None

    citation_bump = _clamp(0.05 * math.log10(1 + max_cited) + (0.05 if n_reviews else 0.0), 0.0, 0.15)
    cohort_bump = 0.10 * _cohort_factor(cohort_max)
    quality = _clamp(model_w * recency + citation_bump + cohort_bump)

    # Combine. Quantity is the spine; consistency scales it (a near-split halves it);
    # quality modulates it within a floor (the sign is already committed, so quality
    # adjusts confidence, it never zeroes a committed call).
    score = quantity * (0.5 + 0.5 * consistency) * (0.6 + 0.4 * quality)
    score = round(_clamp(score), 3)

    return ConfidenceBreakdown(
        score=score, band=_band(score),
        quantity=round(quantity, 3), consistency=round(consistency, 3),
        quality=round(quality, 3), n_signed=t.n_signed, agreement=round(agreement, 3),
        dominant_model=dominant_model, model_mix=model_mix, mean_year=mean_year,
        max_cited_by=max_cited, n_reviews=n_reviews, cohort_max=cohort_max,
    )

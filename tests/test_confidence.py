"""Tests for the calibrated confidence layer.

The layer must (a) rank stronger evidence higher and (b) never change the
committed direction or the abstain decision (the firewall / sign generation is
untouched).
"""

from __future__ import annotations

from paperscout.models import Evidence, Triple
from paperscout.triples.confidence import (
    classify_model,
    cohort_size,
    score_triple,
)
from paperscout.triples.extract import commit_direction


def _ev(direction: str, *, sentence: str = "patients", year: int = 2020,
        cited: int = 10, review: bool = False) -> Evidence:
    return Evidence(pmid="1", sentence=sentence, source="t", direction=direction,
                    year=str(year), cited_by=cited, is_review=review, title="")


def _triple(n_down: int, n_up: int, *, sentence: str = "patients", year: int = 2020,
            cited: int = 10, review: bool = False) -> Triple:
    """Build a triple the way extract does: vote -> commit_direction -> score."""
    ev = [_ev("down", sentence=sentence, year=year, cited=cited, review=review)
          for _ in range(n_down)]
    ev += [_ev("up", sentence=sentence, year=year, cited=cited, review=review)
           for _ in range(n_up)]
    direction, disagreement = commit_direction(n_up, n_down, min_evidence=2)
    t = Triple(drug="d", readout="r", direction=direction, n_up=n_up, n_down=n_down,
               disagreement=disagreement, evidence=ev)
    t.confidence = score_triple(t)
    return t


# --- consistency: the spec's headline example ---------------------------------

def test_unanimous_beats_split_at_same_commit():
    strong = _triple(21, 0)   # 21 down / 0 up
    weak = _triple(3, 1)      # 3 down / 1 up
    assert strong.direction == "down" and weak.direction == "down"  # both commit down
    assert strong.confidence.score > weak.confidence.score
    assert strong.confidence.consistency == 1.0
    assert weak.confidence.consistency < 1.0


def test_consistency_is_monotonic():
    assert _triple(4, 0).confidence.consistency >= _triple(3, 1).confidence.consistency


# --- quantity: more supporting abstracts, higher confidence -------------------

def test_quantity_monotonic_at_equal_consistency():
    few = _triple(3, 0)
    many = _triple(20, 0)
    assert many.confidence.score > few.confidence.score
    assert many.confidence.quantity > few.confidence.quantity


# --- study model: human trial > observational > animal > in vitro -------------

def test_model_quality_ordering():
    trial = _triple(8, 0, sentence="a randomized double-blind placebo-controlled trial")
    obs = _triple(8, 0, sentence="in patients with the condition")
    animal = _triple(8, 0, sentence="in mice the drug")
    vitro = _triple(8, 0, sentence="in vitro in a hepg2 cell line")
    q = [t.confidence.quality for t in (trial, obs, animal, vitro)]
    assert q[0] >= q[1] >= q[2] >= q[3]
    # the strongest human-trial evidence scores higher overall than in-vitro-only
    assert trial.confidence.score > vitro.confidence.score


def test_classify_model():
    assert classify_model(_ev("down", sentence="a randomized controlled trial")) == "human_trial"
    assert classify_model(_ev("down", sentence="in 200 patients")) == "human_observational"
    assert classify_model(_ev("down", sentence="in murine models")) == "animal"
    assert classify_model(_ev("down", sentence="in vitro in cultured cells")) == "in_vitro"
    assert classify_model(_ev("down", sentence="the level changed")) == "unknown"
    # human trial cue dominates a co-mentioned cell arm
    assert classify_model(_ev("down", sentence="rct in patients, validated in vitro")) == "human_trial"


def test_cohort_size_extraction():
    assert cohort_size(_ev("down", sentence="n = 1,234 were enrolled")) == 1234
    assert cohort_size(_ev("down", sentence="200 patients received the drug")) == 200
    assert cohort_size(_ev("down", sentence="no count here")) is None


# --- bounds and bands ---------------------------------------------------------

def test_score_bounded_and_banded():
    for t in (_triple(2, 0), _triple(21, 0), _triple(3, 1)):
        assert 0.0 <= t.confidence.score <= 1.0
        assert t.confidence.band in ("high", "moderate", "low")
    strong = _triple(25, 0, sentence="a large randomized controlled trial", cited=300)
    assert strong.confidence.band == "high"


# --- the firewall / sign generation is never altered by confidence ------------

def test_confidence_does_not_change_direction():
    # a clean commit stays committed with the same sign after scoring
    t = _triple(10, 0)
    assert t.direction == "down"
    # a split abstains (unclear) regardless of how confidence would score it
    split = _triple(3, 3)
    assert split.direction == "unclear" and split.disagreement is True
    # scoring an abstained triple must not flip it to a signed direction
    split.confidence = score_triple(split)
    assert split.direction == "unclear"


def test_recency_raises_quality():
    old = _triple(8, 0, year=1998)
    new = _triple(8, 0, year=2022)
    assert new.confidence.quality >= old.confidence.quality

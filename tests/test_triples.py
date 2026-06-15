"""Tests for triple direction extraction (no network)."""

from paperscout.triples.extract import extract_triples


def test_direction_down():
    records = [
        ("111", "Tocilizumab markedly decreased CRP levels in plasma after treatment."),
        ("222", "Treatment with tocilizumab reduced C-reactive protein concentrations."),
    ]
    triples = extract_triples("tocilizumab", records)
    crp = [t for t in triples if t.readout == "CRP"]
    assert crp and crp[0].direction == "down"
    assert crp[0].n_evidence == 2


def test_direction_up():
    records = [("333", "Growth hormone therapy increased IGF-1 levels in serum.")]
    triples = extract_triples("growth hormone", records)
    igf = [t for t in triples if t.readout == "IGF-1"]
    assert igf and igf[0].direction == "up"


def test_requires_co_mention():
    # readout present but drug absent -> no triple
    records = [("444", "CRP decreased substantially over the study period.")]
    assert extract_triples("tocilizumab", records) == []


def test_no_direction_cue_skipped():
    records = [("555", "Tocilizumab was administered alongside CRP measurement.")]
    assert extract_triples("tocilizumab", records) == []

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


def test_html_stripped_from_quote():
    # Europe PMC abstracts carry <h4>…</h4> section labels; quotes must be clean prose.
    records = [("666", "<h4>Results</h4>Rosuvastatin reduced LDL cholesterol in plasma.")]
    triples = extract_triples("rosuvastatin", records)
    ldl = [t for t in triples if t.readout == "LDL"]
    assert ldl
    quote = ldl[0].evidence[0].sentence
    assert "<h4>" not in quote and "Results" in quote


def test_meta_enriches_citation():
    records = [("777", "Tocilizumab decreased CRP in serum.")]
    meta = {"777": {"authors": "Smith J, Doe A", "journal": "Lancet",
                    "year": "2020", "url": "https://europepmc.org/x", "cited_by": 42,
                    "is_review": True}}
    triples = extract_triples("tocilizumab", records, meta=meta)
    ev = [t for t in triples if t.readout == "CRP"][0].evidence[0]
    assert ev.citation == "Smith J et al., Lancet 2020"
    assert ev.link == "https://europepmc.org/x"
    assert ev.cited_by == 42 and ev.is_review is True


def test_evidence_sorted_by_authority():
    records = [
        ("low", "Rosuvastatin reduced LDL in plasma."),
        ("high", "Rosuvastatin reduced LDL in serum."),
    ]
    meta = {
        "low": {"cited_by": 1, "is_review": False},
        "high": {"cited_by": 500, "is_review": True},
    }
    triples = extract_triples("rosuvastatin", records, meta=meta)
    ldl = [t for t in triples if t.readout == "LDL"][0]
    assert ldl.evidence[0].pmid == "high"  # review / most-cited floats to the top

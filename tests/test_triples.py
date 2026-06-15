"""Tests for triple direction extraction (no network)."""

from paperscout.triples.extract import commit_direction, extract_triples


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
    # Europe PMC abstracts carry <h4>...</h4> section labels; quotes must be clean prose.
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


# --- 1.1 direction-vote tally + abstain policy ---

def test_commit_direction_policy():
    assert commit_direction(4, 0) == ("up", False)                       # unanimous up
    assert commit_direction(0, 4) == ("down", False)                     # unanimous down
    assert commit_direction(4, 1) == ("up", False)                       # minority 0.2 <= 0.25
    assert commit_direction(2, 2) == ("unclear", True)                   # tie -> abstain+flag
    assert commit_direction(3, 2) == ("unclear", True)                   # 0.4 split -> abstain
    assert commit_direction(0, 0) == ("unclear", False)                  # no signal, not a split
    assert commit_direction(0, 1, min_evidence=3) == ("unclear", False)  # below floor


def test_one_triple_per_readout_with_votes():
    records = [
        ("1", "DrugX increased CRP in plasma."),
        ("2", "DrugX reduced CRP in serum."),
        ("3", "DrugX reduced CRP levels in blood."),
        ("4", "DrugX lowered CRP in plasma."),
    ]
    triples = [t for t in extract_triples("drugx", records) if t.readout == "CRP"]
    assert len(triples) == 1                      # collapsed to one triple per readout
    t = triples[0]
    assert (t.n_up, t.n_down) == (1, 3)
    assert t.direction == "down" and t.disagreement is False  # minority 0.25, committed
    assert t.n_evidence == 4


def test_split_evidence_abstains_and_flags():
    records = [
        ("1", "DrugX increased CRP in plasma."),
        ("2", "DrugX elevated CRP in serum."),
        ("3", "DrugX reduced CRP in blood."),
        ("4", "DrugX lowered CRP in plasma."),
    ]
    t = [x for x in extract_triples("drugx", records) if x.readout == "CRP"][0]
    assert (t.n_up, t.n_down) == (2, 2)
    assert t.direction == "unclear" and t.disagreement is True
    assert t.committed is False


def test_min_evidence_floor_abstains():
    records = [("1", "DrugX reduced CRP in plasma.")]
    t = [x for x in extract_triples("drugx", records, min_evidence=3)
         if x.readout == "CRP"][0]
    assert t.direction == "unclear" and t.disagreement is False  # too few, not a split


# --- 1.2 clause-scoped attribution + cohort-descriptor neutralisation ---

def test_cue_attributed_to_readouts_own_clause():
    # real fenofibrate confound: "reduced" belongs to triglycerides, HDL is "increased"
    records = [("1", "Fenofibrate reduced triglyceride levels and increased "
                     "ApoA-I content in HDL fractions in serum.")]
    hdl = [t for t in extract_triples("fenofibrate", records) if t.readout == "HDL"]
    assert hdl and hdl[0].direction == "up"          # was wrongly "down" before 1.2


def test_cue_for_other_analyte_not_borrowed():
    # "reduced" describes macrophages, not HDL -> HDL gets no vote from this sentence
    records = [("1", "Fenofibrate restored HDL antioxidant function in plasma and "
                     "reduced macrophage activation.")]
    hdl = [t for t in extract_triples("fenofibrate", records) if t.readout == "HDL"]
    assert not hdl                                    # no directional vote -> no triple


def test_list_reporting_preserved():
    # comma list under one verb must still attribute "reduced" to each analyte
    records = [("1", "Tocilizumab reduced serum CRP, IL-6 and TNF-alpha.")]
    triples = {t.readout: t.direction for t in extract_triples("tocilizumab", records)}
    assert triples.get("CRP") == "down" and triples.get("IL-6") == "down"


def test_cohort_descriptor_cue_neutralised():
    # "with elevated CRP" describes the cohort, not an effect -> no vote
    records = [("1", "The drug was given to patients with elevated CRP in serum.")]
    assert not [t for t in extract_triples("the drug", records) if t.readout == "CRP"]


def test_real_effect_kept_despite_cohort_phrase():
    records = [("1", "In patients with elevated baseline CRP, drugx reduced CRP in plasma.")]
    crp = [t for t in extract_triples("drugx", records) if t.readout == "CRP"]
    assert crp and crp[0].direction == "down"        # the real "reduced CRP" survives

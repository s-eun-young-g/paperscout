"""Tests for benchmark scoring (pure, no network)."""

from paperscout.bench.run import load_gold
from paperscout.bench.score import score_drug, summarize
from paperscout.models import Triple


def _t(drug, readout, direction, n):
    return Triple(drug=drug, readout=readout, direction=direction,
                  evidence=[None] * n)  # n_evidence only counts length


def test_target_hit_case_insensitive():
    entry = {"drug": "rosuvastatin", "target": "HMGCR", "readouts": []}
    r = score_drug(entry, ["hmgcr"], [])
    assert r.target_hit is True


def test_target_miss_and_none():
    assert score_drug({"drug": "x", "target": "PCSK9", "readouts": []},
                      ["HMGCR"], []).target_hit is False
    assert score_drug({"drug": "metformin", "target": None, "readouts": []},
                      [], []).target_hit is None


def test_readout_direction_and_recall():
    entry = {"drug": "rosuvastatin", "target": "HMGCR", "readouts": [
        {"readout": "LDL", "direction": "down"},
        {"readout": "CRP", "direction": "down"},
        {"readout": "HDL", "direction": "up"},
    ]}
    triples = [
        _t("rosuvastatin", "LDL", "down", 5),   # correct
        _t("rosuvastatin", "CRP", "up", 2),     # found but wrong direction
        # HDL not found at all
    ]
    r = score_drug(entry, ["HMGCR"], triples)
    by = {rr.readout: rr for rr in r.readouts}
    assert by["LDL"].correct is True
    assert by["CRP"].found is True and by["CRP"].correct is False
    assert by["HDL"].found is False


def test_predicted_uses_highest_evidence():
    # conflicting directions for one readout -> the better-supported one wins
    entry = {"drug": "d", "target": None, "readouts": [{"readout": "LDL", "direction": "down"}]}
    triples = [_t("d", "LDL", "up", 1), _t("d", "LDL", "down", 9)]
    r = score_drug(entry, [], triples)
    assert r.readouts[0].predicted_dir == "down" and r.readouts[0].correct


def test_summarize_aggregates():
    results = [
        score_drug({"drug": "a", "target": "HMGCR", "readouts": [
            {"readout": "LDL", "direction": "down"}]}, ["HMGCR"],
            [_t("a", "LDL", "down", 3)]),                       # target hit, triple ok
        score_drug({"drug": "b", "target": "PCSK9", "readouts": [
            {"readout": "LDL", "direction": "down"}]}, ["WRONG"],
            [_t("b", "LDL", "up", 1)]),                         # target miss, dir wrong
        score_drug({"drug": "c", "target": None, "readouts": [
            {"readout": "CRP", "direction": "down"}]}, [], []),  # no target, readout missing
    ]
    m = summarize(results)
    assert m["targets_evaluated"] == 2 and m["target_accuracy"] == 0.5
    assert m["readouts_expected"] == 3 and m["readouts_found"] == 2
    assert m["readout_recall"] == round(2 / 3, 3)
    assert m["direction_accuracy"] == 0.5      # 1 correct of 2 found
    assert m["triple_accuracy"] == round(1 / 3, 3)


def test_gold_set_is_wellformed():
    gold = load_gold()
    assert len(gold) >= 15
    for e in gold:
        assert e["drug"] and "readouts" in e
        for r in e["readouts"]:
            assert r["direction"] in ("up", "down", "changes")

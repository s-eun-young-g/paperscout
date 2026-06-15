"""Tests for Open Targets alias cleaning (pure, no network)."""

from paperscout.sources.opentargets import clean_drug_aliases


def test_keeps_generic_class_names_drops_codes_and_brands():
    # real somatropin synonym list shape
    syns = ["CB-311", "DA-3002", "Genotonorm", "Growth hormone",
            "Growth hormone (human)", "Human growth hormone", "R-hgh",
            "Recombinant human growth hormone", "Somatotropin",
            "Somatropin (rdna origin)"]
    out = clean_drug_aliases("somatropin", syns)
    assert "Growth hormone" in out
    assert "Human growth hormone" in out
    assert "Somatotropin" in out
    # codes / digits dropped
    assert "CB-311" not in out and "DA-3002" not in out and "R-hgh" not in out
    # recombinant/origin formulation noise dropped
    assert "Recombinant human growth hormone" not in out
    assert "Somatropin (rdna origin)" not in out


def test_parenthetical_stripped_and_deduped():
    out = clean_drug_aliases("x", ["Growth hormone (human)", "Growth hormone"])
    assert out == ["Growth hormone"]  # paren-variant collapses onto the bare name


def test_drops_self_and_short_and_empty():
    out = clean_drug_aliases("aspirin", ["aspirin", "ASA", "", None, "acetylsalicylate"])
    assert "aspirin" not in [o.lower() for o in out]
    assert "ASA" not in out  # too short
    assert "acetylsalicylate" in out


def test_cap_respected():
    syns = [f"alphaname{chr(97 + i)}" for i in range(10)]  # ten letter-only aliases
    assert len(clean_drug_aliases("z", syns, cap=3)) == 3

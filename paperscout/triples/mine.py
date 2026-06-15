"""Orchestrate the triple miner: Open Targets (targets) + Europe PMC (direction)."""

from __future__ import annotations

from typing import Optional

from ..http import Client
from ..models import Triple
from ..sources.europepmc import EuropePMC
from ..sources.opentargets import OpenTargets
from .extract import READOUTS, extract_triples


def mine_drug(
    client: Client,
    drug: str,
    *,
    readout: Optional[str] = None,
    limit: int = 120,
    refresh: bool = False,
    offline: bool = False,
) -> tuple[list[Triple], list[str]]:
    """Return (triples, db_targets) for a drug.

    ``readout`` narrows mining to one analyte (e.g. CRP). ``db_targets`` is the
    Open Targets mechanism-of-action target list for the drug.
    """
    kw = dict(refresh=refresh, offline=offline)

    # 1. database-grounded targets (the triple's middle node)
    ot = OpenTargets(client)
    try:
        db_targets = ot.moa_targets(drug, **kw)
    except Exception:
        db_targets = []

    # 2. literature abstracts mentioning the drug + plasma/serum readouts
    readouts = None
    if readout:
        key = readout
        for k, pats in READOUTS.items():
            if k.lower() == readout.lower():
                key, pats = k, pats
                break
        else:
            pats = (readout.lower(),)
        readouts = {key: pats}

    analyte_clause = ("CRP OR interleukin OR cholesterol OR HbA1c OR glucose OR SHBG "
                      "OR IGF OR testosterone OR estradiol OR proteome")
    if readout:
        analyte_clause = readout
    query = f'("{drug}") AND ({analyte_clause}) AND (plasma OR serum OR blood)'

    epmc = EuropePMC(client)
    articles = epmc.search(query, limit=limit, **kw)
    records = epmc.to_records(articles)

    triples = extract_triples(drug, records, readouts=readouts)
    # attach db targets to each triple for context
    for t in triples:
        t.targets_from_db = db_targets
        if db_targets and t.target is None:
            t.target = ", ".join(db_targets[:3])
    return triples, db_targets

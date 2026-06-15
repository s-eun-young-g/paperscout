"""Orchestrate the triple miner: Open Targets (targets) + Europe PMC (direction)."""

from __future__ import annotations

from typing import Optional

from ..http import Client
from ..models import Triple
from ..sources.europepmc import EuropePMC
from ..sources.opentargets import OpenTargets
from .extract import READOUTS, extract_triples


def _analyte_clause(key: str, patterns: tuple[str, ...]) -> str:
    """Build a focused OR clause for one readout from its display name + patterns.

    ASCII-only and length-filtered so the Europe PMC query stays well-formed and
    does not match on noise like the 2-char 'lh'.
    """
    terms = {key, *patterns}
    quoted = sorted(
        {f'"{t.strip()}"' for t in terms
         if len(t.strip()) > 2 and t.isascii()},
        key=len, reverse=True)
    return " OR ".join(quoted)


def mine_drug(
    client: Client,
    drug: str,
    *,
    readout: Optional[str] = None,
    limit: int = 120,
    min_evidence: int = 2,
    refresh: bool = False,
    offline: bool = False,
) -> tuple[list[Triple], list[str]]:
    """Return (triples, db_targets) for a drug.

    ``readout`` narrows mining to one analyte (e.g. CRP). ``db_targets`` is the
    Open Targets mechanism-of-action target list for the drug. ``min_evidence``
    is the floor of signed abstracts required before a direction is committed
    (default 2: never sign a prediction on a single paper).
    """
    kw = dict(refresh=refresh, offline=offline)

    # 1. database-grounded targets (the triple's middle node) + drug aliases
    ot = OpenTargets(client)
    try:
        db_targets, aliases = ot.moa(drug, **kw)
    except Exception:
        db_targets, aliases = [], []

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

    # Retrieve per-readout so each analyte gets its own abstract budget. A single
    # broad "CRP OR interleukin OR ..." disjunction lets common analytes crowd out
    # the rarer ones within the top-N (e.g. biologics -> CRP went unfound), so we
    # issue one focused query per readout and merge (deduped by pmid).
    epmc = EuropePMC(client)
    drug_clause = " OR ".join(f'"{d}"' for d in (drug, *aliases))
    targets = readouts or READOUTS
    per_readout = min(limit, 30) if not readout else limit

    articles_by_pmid: dict = {}
    for key, patterns in targets.items():
        clause = _analyte_clause(key, patterns)
        if not clause:
            continue
        query = f'({drug_clause}) AND ({clause}) AND (plasma OR serum OR blood)'
        for a in epmc.search(query, limit=per_readout, **kw):
            articles_by_pmid[a.get("pmid") or a.get("id")] = a

    articles = list(articles_by_pmid.values())
    records = epmc.to_records(articles)
    meta = epmc.meta_map(articles)

    triples = extract_triples(drug, records, drug_aliases=aliases,
                              readouts=readouts, meta=meta, min_evidence=min_evidence)
    # attach db targets to each triple for context
    for t in triples:
        t.targets_from_db = db_targets
        if db_targets and t.target is None:
            t.target = ", ".join(db_targets[:3])
    return triples, db_targets

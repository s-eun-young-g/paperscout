"""Open Targets adapter, drug -> mechanism-of-action targets (GraphQL, no key).

Provides the database-grounded target(s) for a drug, anchoring the middle node of a
drug -> target -> readout triple.
"""

from __future__ import annotations

import re
from typing import Optional

from ..http import Client

GRAPHQL = "https://api.platform.opentargets.org/api/v4/graphql"

_SEARCH = """
query($q:String!){ search(queryString:$q, entityNames:["drug"]){ hits{ id name } } }
"""
_MOA = """
query($id:String!){
  drug(chemblId:$id){
    name
    synonyms
    mechanismsOfAction{ rows{ actionType targets{ approvedSymbol } } }
  }
}
"""

_HAS_DIGIT = re.compile(r"\d")
_PARENS = re.compile(r"\s*\(.*?\)")
# formulation/origin noise that makes a synonym a worse literature search term
_NOISE = ("rdna", "recombinant", "origin", "injection", "biopartners", "for ")


def clean_drug_aliases(name: str, synonyms: Optional[list[str]], *, cap: int = 6) -> list[str]:
    """Pick literature-friendly aliases from raw Open Targets synonyms.

    Keeps generic/class names (e.g. 'growth hormone', 'somatotropin') and drops
    research codes (CB-311), formulation variants, brand/abbreviation noise, and
    the drug's own name, so the aliases improve recall without flooding the query.
    """
    name_l = name.lower()
    out: list[str] = []
    seen = {name_l}
    for raw in synonyms or []:
        s = _PARENS.sub("", (raw or "")).strip()
        sl = s.lower()
        if not s or sl in seen:
            continue
        if _HAS_DIGIT.search(s) or len(sl) < 5:
            continue
        if " " not in sl and "-" in sl:  # single-token hyphenated codes (R-hgh, Hsb-hgh)
            continue
        if any(w in sl for w in _NOISE):
            continue
        seen.add(sl)
        out.append(s)
        if len(out) >= cap:
            break
    return out


class OpenTargets:
    def __init__(self, client: Client):
        self.client = client

    def resolve_drug(self, name: str, **kw) -> Optional[str]:
        data = self.client.post_json(
            GRAPHQL, {"query": _SEARCH, "variables": {"q": name}}, **kw)
        hits = (((data.get("data") or {}).get("search") or {}).get("hits")) or []
        return hits[0]["id"] if hits else None

    def moa(self, name: str, **kw) -> tuple[list[str], list[str]]:
        """Return (target_symbols, aliases) for a drug in a single lookup."""
        chembl = self.resolve_drug(name, **kw)
        if not chembl:
            return [], []
        data = self.client.post_json(
            GRAPHQL, {"query": _MOA, "variables": {"id": chembl}}, **kw)
        drug = (data.get("data") or {}).get("drug") or {}
        rows = ((drug.get("mechanismsOfAction") or {}).get("rows")) or []
        syms: list[str] = []
        for r in rows:
            for t in (r.get("targets") or []):
                s = t.get("approvedSymbol")
                if s and s not in syms:
                    syms.append(s)
        aliases = clean_drug_aliases(name, drug.get("synonyms"))
        return syms, aliases

    def moa_targets(self, name: str, **kw) -> list[str]:
        return self.moa(name, **kw)[0]

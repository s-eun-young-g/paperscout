"""Open Targets adapter, drug -> mechanism-of-action targets (GraphQL, no key).

Provides the database-grounded target(s) for a drug, anchoring the middle node of a
drug -> target -> readout triple.
"""

from __future__ import annotations

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
    mechanismsOfAction{ rows{ actionType targets{ approvedSymbol } } }
  }
}
"""


class OpenTargets:
    def __init__(self, client: Client):
        self.client = client

    def resolve_drug(self, name: str, **kw) -> Optional[str]:
        data = self.client.post_json(
            GRAPHQL, {"query": _SEARCH, "variables": {"q": name}}, **kw)
        hits = (((data.get("data") or {}).get("search") or {}).get("hits")) or []
        return hits[0]["id"] if hits else None

    def moa_targets(self, name: str, **kw) -> list[str]:
        chembl = self.resolve_drug(name, **kw)
        if not chembl:
            return []
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
        return syms

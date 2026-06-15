"""Score papers against the configured research pillars.

Two transparent, key-free signals combined per pillar:
- **TF-IDF cosine** between the paper (title+abstract) and the pillar's profile text.
- **Keyword hits** of the pillar's curated phrases in the paper text.

Papers are tiered relative to the scored set (so thresholds adapt to the corpus),
and only papers that match at least one pillar are kept. Tier 1 additionally requires
a match on a ``core`` pillar.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Optional

from ..models import Paper, ScoredPaper
from .pillars import Pillar, load_pillars

_TOKEN_RE = re.compile(r"[a-z0-9]+")

COSINE_W = 0.65
KEYWORD_W = 0.35
MATCH_THR = 0.05            # per-pillar score to count as a "match"


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _tfidf(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(tokens)
    vec = {}
    for term, count in tf.items():
        if term in idf:
            vec[term] = (1 + math.log(count)) * idf[term]
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {t: v / norm for t, v in vec.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def _build_idf(docs: list[list[str]]) -> dict[str, float]:
    n = len(docs)
    df: Counter = Counter()
    for d in docs:
        df.update(set(d))
    return {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}


def _keyword_score(text_lower: str, pillar: Pillar) -> tuple[float, list[str]]:
    if not pillar.terms:
        return 0.0, []
    hits = [t for t in pillar.terms if t in text_lower]
    score = min(1.0, len(hits) / math.sqrt(len(pillar.terms)))
    return score, hits


def score_papers(papers: Iterable[Paper],
                 pillars: Optional[list[Pillar]] = None) -> list[ScoredPaper]:
    papers = list(papers)
    pillars = pillars or load_pillars()
    if not papers or not pillars:
        return []
    core_keys = {p.key for p in pillars if p.core}

    paper_tokens = [_tokens(p.text) for p in papers]
    pillar_tokens = [_tokens(pl.profile) for pl in pillars]
    idf = _build_idf(paper_tokens + pillar_tokens)
    pillar_vecs = [_tfidf(t, idf) for t in pillar_tokens]

    scored: list[ScoredPaper] = []
    for paper, toks in zip(papers, paper_tokens):
        vec = _tfidf(toks, idf)
        text_lower = paper.text.lower()
        per_pillar: list[tuple[Pillar, float, list[str]]] = []
        for pl, pvec in zip(pillars, pillar_vecs):
            cos = _cosine(vec, pvec)
            kw, hits = _keyword_score(text_lower, pl)
            s = (COSINE_W * cos + KEYWORD_W * kw) * pl.weight
            per_pillar.append((pl, s, hits))

        per_pillar.sort(key=lambda x: -x[1])
        matched = [(pl, s, hits) for pl, s, hits in per_pillar if s >= MATCH_THR]
        if not matched:
            continue
        top = matched[0][1]
        overall = top + 0.25 * sum(s for _, s, _ in matched[1:])
        scored.append(ScoredPaper(
            paper=paper, score=round(overall, 4), tier=0,
            pillars=[pl.key for pl, _, _ in matched],
            reason=_reason(matched),
        ))

    _assign_tiers(scored, core_keys)
    scored.sort(key=lambda sp: (sp.tier, -sp.score))
    return scored


def _reason(matched) -> str:
    top_pl, _, top_hits = matched[0]
    parts = [f"[{top_pl.key}] {top_pl.name}"]
    if top_hits:
        parts.append("matched: " + ", ".join(top_hits[:5]))
    others = [pl.key for pl, _, _ in matched[1:3]]
    if others:
        parts.append("also " + ", ".join(others))
    return ", ".join(parts)


def _quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, int(q * len(sorted_vals)))
    return sorted_vals[idx]


def _assign_tiers(scored: list[ScoredPaper], core_keys: set[str]) -> None:
    """Tier relative to this corpus: q85/q60 of matched papers; Tier 1 needs a core pillar."""
    vals = sorted(sp.score for sp in scored)
    t1 = _quantile(vals, 0.85)
    t2 = _quantile(vals, 0.60)
    for sp in scored:
        has_core = any(p in core_keys for p in sp.pillars)
        if sp.score >= t1 and has_core:
            sp.tier = 1
        elif sp.score >= t2:
            sp.tier = 2
        else:
            sp.tier = 3

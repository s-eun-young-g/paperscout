"""Research-interest "pillars", the radar's notion of what counts as relevant.

paperscout ships a **generic example set** (broad ML areas) so the tool is runnable
out of the box. To tune it to *your* research program, point it at your own pillar
file instead of editing this one, keep that file out of version control:

    export PAPERSCOUT_PILLARS=~/.config/paperscout/pillars.local.json
    # or: paperscout radar --pillars pillars.local.json -q "..."

Pillar JSON schema (a list of objects):
    [{"key": "CAUSAL", "name": "...", "profile": "paragraph used for similarity",
      "terms": ["phrase", ...], "weight": 1.0, "core": true}]
``core`` pillars are the ones a paper must match to reach Tier 1.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Pillar:
    key: str
    name: str
    profile: str
    terms: tuple[str, ...] = field(default_factory=tuple)
    weight: float = 1.0
    core: bool = True


# --- generic, illustrative defaults (mainstream ML topics) -------------------
DEFAULT_PILLARS: list[Pillar] = [
    Pillar(
        key="CAUSAL", name="Causal inference & treatment effects",
        profile=(
            "Causal inference, conditional average treatment effects, counterfactual "
            "estimation, confounding, instrumental variables, sensitivity analysis, "
            "observational and randomized data, selection bias, time-varying effects."),
        terms=("causal inference", "treatment effect", "counterfactual", "confounding",
               "instrumental variable", "sensitivity analysis", "observational",
               "average treatment effect", "selection bias", "time-varying"),
    ),
    Pillar(
        key="GRAPH", name="Graph representation learning",
        profile=(
            "Graph neural networks, link prediction on relational graphs, knowledge "
            "graph embeddings, message passing, node and edge representation learning, "
            "graph attention networks."),
        terms=("graph neural network", "GNN", "link prediction", "knowledge graph",
               "message passing", "graph attention", "node embedding", "relational"),
    ),
    Pillar(
        key="DYNAMICS", name="Time-series & dynamical systems",
        profile=(
            "Neural ordinary differential equations, longitudinal trajectory modeling, "
            "irregular sampling, dynamical systems, continuous-time latent variable "
            "models, time series forecasting."),
        terms=("neural ODE", "ordinary differential equation", "trajectory", "longitudinal",
               "irregular sampling", "dynamical system", "continuous-time", "time series"),
    ),
    Pillar(
        key="ACTIVE", name="Active learning & experimental design",
        profile=(
            "Active learning, optimal experimental design, Bayesian optimization, "
            "acquisition functions, budgeted experimentation, sequential decision making "
            "for which experiment to run next."),
        terms=("active learning", "experimental design", "bayesian optimization",
               "acquisition function", "budget", "sequential design", "design of experiments"),
        core=False,
    ),
    Pillar(
        key="REPRESENTATION", name="Representation & multimodal learning",
        profile=(
            "Self-supervised and contrastive representation learning, multimodal and "
            "multi-view fusion, transfer learning, cold-start generalization to unseen "
            "entities, embeddings."),
        terms=("representation learning", "contrastive", "self-supervised", "multimodal",
               "multi-view", "transfer learning", "cold-start", "embedding"),
        core=False,
    ),
]


def load_pillars(path: Optional[str | Path] = None) -> list[Pillar]:
    """Load pillars from an explicit path, then ``PAPERSCOUT_PILLARS``, else defaults."""
    path = path or os.environ.get("PAPERSCOUT_PILLARS")
    if not path:
        return DEFAULT_PILLARS
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    pillars = []
    for d in data:
        pillars.append(Pillar(
            key=d["key"], name=d.get("name", d["key"]), profile=d.get("profile", ""),
            terms=tuple(d.get("terms", [])), weight=float(d.get("weight", 1.0)),
            core=bool(d.get("core", True)),
        ))
    return pillars

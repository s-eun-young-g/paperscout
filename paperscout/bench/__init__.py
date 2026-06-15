"""Triple-mining benchmark: score paperscout against a gold set of known triples."""

from .run import load_gold, render_markdown, render_terminal, run_benchmark  # noqa: F401
from .score import DrugResult, ReadoutResult, score_drug, summarize  # noqa: F401

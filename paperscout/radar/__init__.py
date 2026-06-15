"""Radar: score papers against configurable research pillars and tier them."""

from .pillars import DEFAULT_PILLARS, load_pillars  # noqa: F401
from .score import score_papers  # noqa: F401

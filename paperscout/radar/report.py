"""Render the radar's tiered list to terminal or Markdown.

A tiered list (TIER 1/2/3); each entry shows title, authors, lead affiliation/venue,
link, and a one-line `[PILLAR] why`.
"""

from __future__ import annotations

from rich.console import Console

from ..models import ScoredPaper

_TIER_LABEL = {
    1: "TIER 1, Highest priority (same problem / load-bearing)",
    2: "TIER 2, Relevant (clear connection to a pillar)",
    3: "TIER 3, Peripheral (one weaker match)",
}


def _authors_str(sp: ScoredPaper, n: int = 4) -> str:
    names = [a.name for a in sp.paper.authors[:n]]
    extra = len(sp.paper.authors) - n
    s = ", ".join(names)
    if extra > 0:
        s += f" (+{extra})"
    return s or "-"


def _context(sp: ScoredPaper) -> str:
    bits = []
    if sp.paper.lead_affiliation:
        bits.append(sp.paper.lead_affiliation)
    if sp.paper.venue:
        bits.append(sp.paper.venue)
    if sp.paper.year:
        bits.append(str(sp.paper.year))
    return ", ".join(bits)


def render_markdown(title: str, scored: list[ScoredPaper], min_tier: int = 3) -> str:
    out = [f"# {title}", "", f"*{len(scored)} matched papers (showing tiers 1-{min_tier})*", ""]
    for tier in (1, 2, 3):
        if tier > min_tier:
            break
        group = [s for s in scored if s.tier == tier]
        if not group:
            continue
        out.append(f"## {_TIER_LABEL[tier]}")
        out.append("")
        for sp in group:
            out.append(f"**{sp.paper.title}**  ")
            out.append(f"{_authors_str(sp)}  ")
            ctx = _context(sp)
            if ctx:
                out.append(f"*{ctx}*  ")
            out.append(f"{sp.reason}, score {sp.score}")
            if sp.paper.url:
                out.append(f"  \n<{sp.paper.url}>")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_terminal(title: str, scored: list[ScoredPaper], min_tier: int = 3,
                    console: Console | None = None) -> None:
    console = console or Console()
    console.print(f"\n[bold cyan]{title}[/]  ({len(scored)} matched papers)\n")
    for tier in (1, 2, 3):
        if tier > min_tier:
            break
        group = [s for s in scored if s.tier == tier]
        if not group:
            continue
        console.rule(f"[bold]{_TIER_LABEL[tier]}", style="cyan")
        for sp in group:
            console.print(f"[bold]{sp.paper.title}[/]")
            console.print(f"  {_authors_str(sp)}", style="white")
            ctx = _context(sp)
            if ctx:
                console.print(f"  {ctx}", style="dim")
            console.print(f"  [green]{sp.reason}[/], score {sp.score}")
            if sp.paper.url:
                console.print(f"  [blue underline]{sp.paper.url}[/]")
            console.print()

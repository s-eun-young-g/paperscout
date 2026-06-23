"""Render mined triples to terminal or Markdown."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ..models import Triple
from .confidence import classify_model

_ARROW = {"up": "up", "down": "down", "unclear": "unclear"}


def _dir_label(t: Triple) -> str:
    d = _ARROW.get(t.direction, t.direction)
    return f"{d} (disagree)" if t.disagreement else d


def _headline(drug: str, triples: list[Triple], db_targets: list[str]) -> str:
    tline = f"targets (Open Targets): {', '.join(db_targets)}" if db_targets else \
        "no database targets found"
    return f"{drug}: {len(triples)} candidate readout relations, {tline}"


def render_terminal(drug: str, triples: list[Triple], db_targets: list[str],
                    console: Console | None = None, max_evidence: int = 1) -> None:
    console = console or Console()
    console.print(f"\n[bold cyan]{_headline(drug, triples, db_targets)}[/]\n")
    if not triples:
        console.print("[yellow]No directional drug->readout statements found.[/]")
        return
    table = Table(header_style="bold magenta", box=None)
    for c in ("Triple", "Dir", "Votes", "Evidence", "Confidence", "Target(s)"):
        table.add_column(c)
    for t in triples:
        color = "white" if t.committed else "yellow"
        conf = (f"{t.confidence.score:.2f} ({t.confidence.band}, {t.confidence.dominant_model})"
                if t.confidence else "-")
        table.add_row(f"{t.drug} -> {t.readout}", f"[{color}]{_dir_label(t)}[/]",
                      t.votes, str(t.n_evidence), conf, t.target or "-")
    console.print(table)
    console.print("\n[dim]Top evidence sentences:[/]")
    for t in triples[:8]:
        ev = t.evidence[0]
        console.print(f"  [bold]{t.readout} {_dir_label(t)}[/] "
                      f"([italic]{ev.citation}[/]) {ev.sentence[:200]}")


def render_markdown(drug: str, triples: list[Triple], db_targets: list[str],
                    max_evidence: int = 2) -> str:
    out = [f"# Triples for {drug}", "", f"*{_headline(drug, triples, db_targets)}*", ""]
    out += ["| Triple | Direction | Votes (up/down) | Evidence | Confidence | Model | Target(s) |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for t in triples:
        conf = f"{t.confidence.score:.2f} ({t.confidence.band})" if t.confidence else "-"
        model = t.confidence.dominant_model if t.confidence else "-"
        out.append(f"| {t.drug} -> {t.readout} | {_dir_label(t)} "
                   f"| {t.n_up}/{t.n_down} | {t.n_evidence} | {conf} | {model} | {t.target or '-'} |")
    out.append("")
    out.append("## Evidence")
    out.append("")
    for t in triples:
        out.append(f"### {t.drug} -> {t.readout} ({_dir_label(t)})")
        for ev in t.evidence[:max_evidence]:
            link = ev.link
            label = f"[{ev.citation}]({link})" if link else ev.citation
            title = f" - *{ev.title}*" if ev.title else ""
            vote = f"[{ev.direction}] " if ev.direction else ""
            model = f"({classify_model(ev)}) " if ev.direction else ""
            out.append(f'- {vote}{model}{label}{title}: "{ev.sentence}"')
        out.append("")
    return "\n".join(out).rstrip() + "\n"

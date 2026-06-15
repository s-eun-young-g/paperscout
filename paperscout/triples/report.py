"""Render mined triples to terminal or Markdown."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from ..models import Triple

_ARROW = {"up": "up", "down": "down", "changes": "changes"}


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
    for c in ("Triple", "Dir", "Evidence", "Target(s)"):
        table.add_column(c)
    for t in triples:
        table.add_row(f"{t.drug} -> {t.readout}", _ARROW.get(t.direction, t.direction),
                      str(t.n_evidence), t.target or "-")
    console.print(table)
    console.print("\n[dim]Top evidence sentences:[/]")
    for t in triples[:8]:
        ev = t.evidence[0]
        pmid = f"PMID:{ev.pmid}" if ev.pmid else ev.source
        console.print(f"  [bold]{t.readout} {_ARROW.get(t.direction,'')}[/] ({pmid}) "
                      f"{ev.sentence[:200]}")


def render_markdown(drug: str, triples: list[Triple], db_targets: list[str],
                    max_evidence: int = 2) -> str:
    out = [f"# Triples for {drug}", "", f"*{_headline(drug, triples, db_targets)}*", ""]
    out += ["| Triple | Direction | Evidence | Target(s) |",
            "| --- | --- | --- | --- |"]
    for t in triples:
        out.append(f"| {t.drug} -> {t.readout} | {_ARROW.get(t.direction, t.direction)} "
                   f"| {t.n_evidence} | {t.target or '-'} |")
    out.append("")
    out.append("## Evidence")
    out.append("")
    for t in triples:
        out.append(f"### {t.drug} -> {t.readout} ({t.direction})")
        for ev in t.evidence[:max_evidence]:
            pmid = (f"[PMID:{ev.pmid}](https://pubmed.ncbi.nlm.nih.gov/{ev.pmid}/)"
                    if ev.pmid else ev.source)
            out.append(f"- {pmid}: {ev.sentence}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"

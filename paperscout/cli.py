"""paperscout command-line interface: `radar` and `triples`."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from .cache import Cache
from .config import settings
from .http import Client

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="A configurable literature radar + biomedical relation miner.")
console = Console()


def _client() -> Client:
    return Client(settings, Cache(settings.db_path))


@app.command()
def radar(
    query: Optional[str] = typer.Option(None, "--query", "-q", help="OpenAlex topic query"),
    venue: Optional[str] = typer.Option(None, help="Venue name (OpenAlex)"),
    year: Optional[int] = typer.Option(None, help="Publication year filter"),
    file: Optional[str] = typer.Option(None, "--file", help="Local CSV/JSON paper dump"),
    openreview: Optional[str] = typer.Option(
        None, "--openreview", help="OpenReview venueid, e.g. ICLR.cc/2024/Conference"),
    limit: int = typer.Option(150, help="Max papers to pull from a live source"),
    min_tier: int = typer.Option(3, "--min-tier", help="Show tiers 1..N (1=only strongest)"),
    fmt: str = typer.Option("terminal", "--format", "-f", help="terminal|md"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
    enrich: bool = typer.Option(False, help="Look up missing affiliations via OpenAlex"),
    pillars: Optional[str] = typer.Option(
        None, "--pillars", help="Path to a custom pillars JSON (else PAPERSCOUT_PILLARS / defaults)"),
    refresh: bool = typer.Option(False),
    offline: bool = typer.Option(False),
):
    """Score papers against your research pillars and print a tiered list."""
    from .radar.pillars import load_pillars
    from .radar.report import render_markdown, render_terminal
    from .radar.score import score_papers
    from .sources import paperfile
    from .sources.openalex import OpenAlex
    from .sources.openreview import OpenReview

    if not any([query, venue, file, openreview]):
        raise typer.BadParameter("Provide --query, --venue, --file, or --openreview.")

    client = _client()
    try:
        papers = []
        label = ""
        if file:
            papers = paperfile.load(file)
            label = f"file:{Path(file).name}"
        elif openreview:
            with console.status(f"Fetching OpenReview {openreview}..."):
                papers = OpenReview(client).venue_papers(
                    openreview, limit=limit, refresh=refresh, offline=offline)
            label = openreview
        else:
            with console.status("Querying OpenAlex..."):
                papers = OpenAlex(client, settings.mailto).search(
                    query, venue=venue, year=year, limit=limit,
                    refresh=refresh, offline=offline)
            label = query or f"{venue} {year or ''}".strip()

        if not papers:
            console.print("[yellow]No papers found.[/]")
            raise typer.Exit(0)

        if enrich:
            oa = OpenAlex(client, settings.mailto)
            with console.status("Enriching affiliations..."):
                for p in papers:
                    a = p.first_author
                    if a and not a.affiliation:
                        try:
                            a.affiliation = oa.best_affiliation(
                                a.name, refresh=refresh, offline=offline)
                        except Exception:
                            pass
    finally:
        client.close()

    scored = score_papers(papers, load_pillars(pillars))
    title = f"paperscout radar, {label}"
    if fmt == "md":
        text = render_markdown(title, scored, min_tier=min_tier)
        if output:
            Path(output).write_text(text)
            console.print(f"[green]Wrote[/] {output}")
        else:
            print(text)
    else:
        render_terminal(title, scored, min_tier=min_tier, console=console)
    console.print(f"[dim]{len(scored)}/{len(papers)} papers matched at least one pillar.[/]")


@app.command()
def triples(
    drug: str = typer.Option(..., "--drug", "-d", help="Drug or drug name"),
    readout: Optional[str] = typer.Option(None, "--readout", help="Focus one analyte, e.g. CRP"),
    limit: int = typer.Option(120, help="Max abstracts to mine"),
    min_evidence: int = typer.Option(
        2, "--min-evidence", help="Signed abstracts required to commit a direction"),
    fmt: str = typer.Option("terminal", "--format", "-f", help="terminal|md"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
    refresh: bool = typer.Option(False),
    offline: bool = typer.Option(False),
):
    """Mine drug -> target -> readout relations (with direction) from the literature."""
    from .triples.mine import mine_drug
    from .triples.report import render_markdown, render_terminal

    client = _client()
    try:
        with console.status(f"Mining literature for {drug}..."):
            mined, db_targets = mine_drug(
                client, drug, readout=readout, limit=limit,
                min_evidence=min_evidence, refresh=refresh, offline=offline)
    finally:
        client.close()

    if fmt == "md":
        text = render_markdown(drug, mined, db_targets)
        if output:
            Path(output).write_text(text)
            console.print(f"[green]Wrote[/] {output}")
        else:
            print(text)
    else:
        render_terminal(drug, mined, db_targets, console=console)


@app.command()
def bench(
    gold: Optional[str] = typer.Option(None, help="Path to a gold JSON (default: bundled set)"),
    drug: Optional[str] = typer.Option(None, "--drug", "-d", help="Benchmark only this drug"),
    limit: int = typer.Option(60, help="Max abstracts to mine per drug"),
    min_evidence: int = typer.Option(
        2, "--min-evidence", help="Signed abstracts required to commit a direction"),
    fmt: str = typer.Option("terminal", "--format", "-f", help="terminal|md"),
    output: Optional[str] = typer.Option(None, "--output", "-o"),
    refresh: bool = typer.Option(False),
    offline: bool = typer.Option(False),
):
    """Score the triple miner against a gold set of known drug->target->readout triples."""
    from .bench.run import load_gold, render_markdown, render_terminal, run_benchmark
    from .bench.score import summarize

    entries = load_gold(gold)
    if drug:
        entries = [e for e in entries if e["drug"].lower() == drug.lower()]
        if not entries:
            raise typer.BadParameter(f"{drug!r} is not in the gold set.")

    client = _client()
    try:
        results = run_benchmark(
            client, entries, limit=limit, min_evidence=min_evidence,
            refresh=refresh, offline=offline, console=console)
    finally:
        client.close()

    metrics = summarize(results)
    if fmt == "md":
        text = render_markdown(results, metrics)
        if output:
            Path(output).write_text(text)
            console.print(f"[green]Wrote[/] {output}")
        else:
            print(text)
    else:
        render_terminal(results, metrics, console=console)


if __name__ == "__main__":
    app()

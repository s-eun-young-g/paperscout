"""Run the triple-mining benchmark: mine each gold drug, score, report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from ..http import Client
from ..triples.mine import mine_drug
from .score import DrugResult, score_drug, summarize

GOLD_PATH = Path(__file__).parent / "gold.json"


def load_gold(path: Optional[str] = None) -> list[dict]:
    p = Path(path) if path else GOLD_PATH
    data = json.loads(p.read_text())
    return data["triples"] if isinstance(data, dict) else data


def run_benchmark(
    client: Client,
    entries: list[dict],
    *,
    limit: int = 60,
    refresh: bool = False,
    offline: bool = False,
    console: Optional[Console] = None,
) -> list[DrugResult]:
    results: list[DrugResult] = []
    for i, entry in enumerate(entries, 1):
        drug = entry["drug"]
        if console:
            console.print(f"[dim]({i}/{len(entries)}) mining {drug}...[/]")
        try:
            triples, db_targets = mine_drug(
                client, drug, limit=limit, refresh=refresh, offline=offline)
            results.append(score_drug(entry, db_targets, triples))
        except Exception as e:  # one drug failing must not sink the run
            results.append(score_drug(entry, [], [], error=f"{type(e).__name__}: {e}"))
    return results


def _rows(results: list[DrugResult]) -> list[tuple]:
    rows = []
    for r in results:
        tgt = "n/a" if r.expected_target is None else (
            "hit" if r.target_hit else "MISS")
        for rr in r.readouts:
            pred = rr.predicted_dir or "-"
            rows.append((r.drug, tgt, f"{r.expected_target or '-'} -> {rr.readout}",
                         rr.expected_dir, pred, str(rr.n_evidence), rr.verdict,
                         r.error or ""))
    return rows


def render_terminal(results: list[DrugResult], metrics: dict,
                    console: Optional[Console] = None) -> None:
    console = console or Console()
    table = Table(header_style="bold magenta", box=None)
    for c in ("Drug", "Target", "Triple", "Exp", "Pred", "Evid", "Verdict"):
        table.add_column(c)
    for drug, tgt, triple, exp, pred, evid, verdict, err in _rows(results):
        color = {"ok": "green", "dir": "red", "abstain": "yellow",
                 "MISS": "red"}.get(verdict, "white")
        table.add_row(drug, tgt, triple, exp, pred, evid,
                      f"[{color}]{verdict}[/]")
    console.print(table)
    errs = [r for r in results if r.error]
    if errs:
        console.print("\n[red]Errors:[/]")
        for r in errs:
            console.print(f"  {r.drug}: {r.error}")
    console.print("\n[bold cyan]Summary[/]")
    for k, v in metrics.items():
        console.print(f"  {k}: {v}")


def render_markdown(results: list[DrugResult], metrics: dict) -> str:
    out = ["# paperscout triple benchmark", "", "## Summary", ""]
    out += ["| Metric | Value |", "| --- | --- |"]
    for k, v in metrics.items():
        out.append(f"| {k} | {v} |")
    out += ["", "## Per-triple", "",
            "| Drug | Target | Triple | Expected | Predicted | Evidence | Verdict |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for drug, tgt, triple, exp, pred, evid, verdict, _ in _rows(results):
        out.append(f"| {drug} | {tgt} | {triple} | {exp} | {pred} | {evid} | {verdict} |")
    errs = [r for r in results if r.error]
    if errs:
        out += ["", "## Errors", ""]
        out += [f"- **{r.drug}**: {r.error}" for r in errs]
    return "\n".join(out).rstrip() + "\n"

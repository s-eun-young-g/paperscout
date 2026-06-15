"""Pure scoring for the triple-mining benchmark (no network).

Given a gold entry (drug, expected target, expected readout directions) and what the
miner actually returned (db_targets + Triples), produce per-drug and aggregate metrics.
Kept free of I/O so it can be unit-tested deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..models import Triple


@dataclass
class ReadoutResult:
    readout: str
    expected_dir: str
    found: bool
    predicted_dir: Optional[str]   # "up" | "down" | "unclear" | None (not found)
    n_evidence: int

    @property
    def committed(self) -> bool:
        """A signed prediction was emitted (not an abstention)."""
        return self.predicted_dir in ("up", "down")

    @property
    def abstained(self) -> bool:
        return self.found and not self.committed

    @property
    def correct(self) -> bool:
        return self.committed and self.predicted_dir == self.expected_dir

    @property
    def wrong_direction(self) -> bool:
        """Committed a signed direction that contradicts the gold (the unsafe case)."""
        return self.committed and self.predicted_dir != self.expected_dir

    @property
    def verdict(self) -> str:
        if not self.found:
            return "MISS"
        if self.abstained:
            return "abstain"
        return "ok" if self.correct else "dir"


@dataclass
class DrugResult:
    drug: str
    expected_target: Optional[str]
    db_targets: list[str]
    error: Optional[str] = None
    readouts: list[ReadoutResult] = field(default_factory=list)

    @property
    def target_hit(self) -> Optional[bool]:
        """True/False when a target is expected, None when none is expected."""
        if not self.expected_target:
            return None
        want = self.expected_target.lower()
        return any(t.lower() == want for t in self.db_targets)


def _predicted(readout: str, triples: list[Triple]) -> tuple[Optional[str], int]:
    """Committed direction for a readout (one triple per readout) and evidence count."""
    for t in triples:
        if t.readout.lower() == readout.lower():
            return t.direction, t.n_evidence
    return None, 0


def score_drug(entry: dict, db_targets: list[str], triples: list[Triple],
               error: Optional[str] = None) -> DrugResult:
    res = DrugResult(
        drug=entry["drug"],
        expected_target=entry.get("target"),
        db_targets=list(db_targets or []),
        error=error,
    )
    for r in entry.get("readouts", []):
        pdir, n = _predicted(r["readout"], triples)
        res.readouts.append(ReadoutResult(
            readout=r["readout"],
            expected_dir=r["direction"],
            found=pdir is not None,
            predicted_dir=pdir,
            n_evidence=n,
        ))
    return res


def summarize(results: list[DrugResult]) -> dict:
    """Aggregate metrics across drugs.

    For a prediction oracle the key safety metric is wrong_direction (a committed
    sign that contradicts the gold); abstentions are safe, not errors.

    - target_accuracy: of drugs with an expected target, fraction Open Targets hits.
    - readout_recall: fraction of expected readouts the miner found at all.
    - direction_accuracy: of readouts where a signed direction was COMMITTED,
      fraction correct (abstentions excluded from the denominator).
    - abstained: count of found readouts the oracle declined to sign.
    - wrong_direction: count of committed signs that contradict the gold.
    - triple_accuracy: fraction of expected readouts found AND correctly signed.
    """
    targets = [r.target_hit for r in results if r.target_hit is not None]
    readouts = [rr for r in results for rr in r.readouts]
    found = [rr for rr in readouts if rr.found]
    committed = [rr for rr in found if rr.committed]
    correct = [rr for rr in committed if rr.correct]
    wrong = [rr for rr in committed if rr.wrong_direction]
    abstained = [rr for rr in found if rr.abstained]

    def frac(num: int, den: int) -> Optional[float]:
        return round(num / den, 3) if den else None

    return {
        "drugs": len(results),
        "errors": sum(1 for r in results if r.error),
        "target_accuracy": frac(sum(targets), len(targets)),
        "targets_evaluated": len(targets),
        "readout_recall": frac(len(found), len(readouts)),
        "readouts_expected": len(readouts),
        "readouts_found": len(found),
        "committed": len(committed),
        "abstained": len(abstained),
        "direction_accuracy": frac(len(correct), len(committed)),
        "wrong_direction": len(wrong),
        "triple_accuracy": frac(len(correct), len(readouts)),
        "triples_correct": len(correct),
    }

"""Daily reconciliation auditor pattern.

After each session the deployed book is reconciled against an independent replay
of the same signal: did the broker hold what the strategy intended, and did each
logged decision match a re-derivation from the recorded inputs? Silent drift
between intent and fills is the failure mode this catches. Representative of the
production log auditor; it reports discrepancies rather than raising.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Discrepancy:
    kind: str
    detail: str


def reconcile_holdings(
    intended: str | None,
    actual: str | None,
) -> list[Discrepancy]:
    """Flag a mismatch between the intended and the actually-held fund."""
    if intended != actual:
        return [Discrepancy("holding_mismatch", f"intended={intended} actual={actual}")]
    return []


def reconcile_decisions(
    logged: list[tuple[str, str]],
    replayed: list[tuple[str, str]],
) -> list[Discrepancy]:
    """Compare logged ``(date, decision)`` pairs against a fresh replay.

    Both lists are aligned by date; any date whose logged decision differs from
    the replayed one is reported.
    """
    replay = dict(replayed)
    out: list[Discrepancy] = []
    for date, decision in logged:
        expected = replay.get(date)
        if expected is None:
            out.append(Discrepancy("missing_replay", f"{date}: no replayed decision"))
        elif expected != decision:
            out.append(
                Discrepancy("decision_mismatch", f"{date}: logged={decision} replay={expected}")
            )
    return out


def reconcile_weight(
    weight: float,
    target: float,
    tolerance: float,
) -> list[Discrepancy]:
    """Flag when the position weight drifts outside a tolerance band of target."""
    if abs(weight - target) > tolerance:
        return [
            Discrepancy("weight_drift", f"weight={weight:.4f} target={target:.4f} tol={tolerance}")
        ]
    return []

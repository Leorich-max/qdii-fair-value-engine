"""The transaction-cost ladder.

A single cost assumption is fragile: the true cost is uncertain, fund-specific,
and regime-dependent, and a strategy's reported edge can hinge entirely on it.
A *ladder* reports the result across a spectrum of assumptions -- from gross
(zero, an upper bound) through a data-implied Corwin-Schultz half-spread to a
deliberately conservative rung -- so a reader sees where the edge survives and
where it breaks, rather than trusting one number.

Costs are expressed per *swap* (a full rotation = sell one fund, buy another =
two legs). A per-leg half-spread of ``h`` bp therefore contributes ``2h`` bp per
swap.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CostRung:
    """One rung of the ladder: a per-swap cost and its fill assumption."""

    name: str
    bps_per_swap: float
    fill: str
    description: str


def standard_ladder(cs_half_spread_bps_per_leg: float | None = None) -> list[CostRung]:
    """Build the standard ladder, optionally appending a Corwin-Schultz rung.

    Parameters
    ----------
    cs_half_spread_bps_per_leg:
        If given, append a data-implied rung at ``2 x`` this half-spread (both
        legs), filled next session on the opponent side (bounce-free).
    """
    rungs = [
        CostRung("gross", 0.0, "next-session opponent", "no costs; upper bound on the signal"),
        CostRung("flat_1bp", 1.0, "next-session opponent", "token frictionless cost"),
        CostRung("realistic_12bp", 12.0, "next-session opponent", "central realistic assumption"),
        CostRung("conservative_20bp", 20.0, "next-session opponent", "stress rung"),
    ]
    if cs_half_spread_bps_per_leg is not None:
        rungs.append(
            CostRung(
                "corwin_schultz",
                2.0 * cs_half_spread_bps_per_leg,
                "next-session opponent",
                "data-implied per-leg half-spread, charged on both legs",
            )
        )
    return rungs


def apply_switch_cost(
    gross_period_return: pd.Series,
    switched: pd.Series,
    cost_bps_per_swap: float,
) -> pd.Series:
    """Subtract a per-swap cost from the period return on each switch period.

    Parameters
    ----------
    gross_period_return:
        Per-period strategy return before costs.
    switched:
        Boolean/0-1 series, true on periods where a rotation occurred.
    cost_bps_per_swap:
        Cost charged per rotation, in basis points.
    """
    cost = switched.astype(float) * (cost_bps_per_swap / 1e4)
    return (gross_period_return - cost).rename("net_return")


def breakeven_cost_bps(gross_excess_per_year: float, switches_per_year: float) -> float:
    """Per-swap cost (bp) that would erase the annual gross excess.

    A high break-even cost relative to the ladder's realistic rung is what makes
    an edge robust; a low one means the edge is really a cost assumption.
    """
    if switches_per_year <= 0:
        return float("inf")
    return gross_excess_per_year / switches_per_year * 1e4


def ladder_table(
    gross_excess_per_year: float,
    switches_per_year: float,
    rungs: list[CostRung],
) -> pd.DataFrame:
    """Net annual excess at each ladder rung, plus the break-even cost."""
    rows = []
    for rung in rungs:
        net = gross_excess_per_year - switches_per_year * (rung.bps_per_swap / 1e4)
        rows.append(
            {
                "rung": rung.name,
                "bps_per_swap": rung.bps_per_swap,
                "fill": rung.fill,
                "net_excess_per_year": net,
            }
        )
    table = pd.DataFrame(rows)
    table.attrs["breakeven_bps_per_swap"] = breakeven_cost_bps(
        gross_excess_per_year, switches_per_year
    )
    return table


def annualized_from_daily(daily_excess: pd.Series, periods_per_year: int = 244) -> float:
    """Annualise a mean daily (log) excess series by simple scaling."""
    return float(np.nanmean(daily_excess.to_numpy()) * periods_per_year)

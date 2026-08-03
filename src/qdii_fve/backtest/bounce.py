"""Bid-ask bounce decomposition.

A cross-sectional laggard signal can look far better than it is, because the
fund it flags as cheapest is often cheap *because of a downward bid-ask bounce*
that mean-reverts next bar. Filling at that same close books the reversion as
alpha. The honest, executable estimate fills the next session on the opponent
side (buy the ask, sell the bid), which forgoes the bounce and pays the spread.

The difference between the two is the bounce component. On the real study it was
about half the apparent edge (a same-bar upper bound around +16% p.a. dropping
to roughly +8% p.a. executable). This module reproduces the *method*; run it on
your own data to get the magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .engine import run_rotation

_TRADING_DAYS = 244


@dataclass(frozen=True)
class BounceResult:
    same_bar_excess: pd.Series  # cumulative excess, bounce-inflated upper bound
    executable_excess: pd.Series  # cumulative excess, next-session opponent fill
    same_bar_ann: float  # annualised excess, upper bound
    executable_ann: float  # annualised excess, executable
    bounce_fraction: float  # share of the gross edge that was bounce

    def summary(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "fill": ["same-bar close (upper bound)", "next-session opponent (executable)"],
                "annualised_excess": [self.same_bar_ann, self.executable_ann],
            }
        )


def decompose_bounce(
    dev: pd.DataFrame,
    close: pd.DataFrame,
    bid: pd.DataFrame,
    ask: pd.DataFrame,
    threshold_bps: float,
    trading_days: int = _TRADING_DAYS,
) -> BounceResult:
    """Compare a same-bar close fill against a next-session opponent-side fill."""
    upper = run_rotation(
        dev, close, sell_px=close, buy_px=close, threshold_bps=threshold_bps, fill_delay=0
    )
    executable = run_rotation(
        dev, close, sell_px=bid, buy_px=ask, threshold_bps=threshold_bps, fill_delay=1
    )
    same_bar_ann = float(upper.daily_excess.mean() * trading_days)
    executable_ann = float(executable.daily_excess.mean() * trading_days)
    bounce_fraction = (
        (same_bar_ann - executable_ann) / same_bar_ann if same_bar_ann else float("nan")
    )
    return BounceResult(
        same_bar_excess=upper.daily_excess.cumsum().rename("same_bar_excess"),
        executable_excess=executable.daily_excess.cumsum().rename("executable_excess"),
        same_bar_ann=same_bar_ann,
        executable_ann=executable_ann,
        bounce_fraction=bounce_fraction,
    )

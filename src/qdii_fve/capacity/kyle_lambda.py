"""Kyle's lambda price impact and the capacity it implies.

Kyle (1985): price moves linearly in signed order flow, ``dP/P = lambda * Q``.
We report ``lambda`` as **bp of price impact per 1M CNY of signed turnover**,
estimated per fund by regressing bar log-returns (bp) on signed turnover (M CNY);
order flow is signed with the tick rule (up-bar = buy-initiated).

Capacity follows from the impact budget. A rotation trades two legs (sell one
fund, buy another), so a book of ``S`` M CNY pays round-trip impact of about
``legs * lambda * S`` bp. The capacity at a tolerance is the ``S`` that exhausts
that budget. Because the rotation must sometimes hold *thin* funds, the binding
lambda is the thin-fund one -- capacity is set by the least liquid name you must
be able to trade, not the average.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class LambdaEstimate:
    lam_bps_per_million: float  # bp impact per 1M CNY of signed flow
    t_stat: float
    r_squared: float
    n: int


def signed_turnover_million(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Tick-rule signed turnover in millions of CNY (up-bar buy, down-bar sell)."""
    sign = np.sign(close.diff())
    turnover_m = close * volume / 1e6
    return (sign * turnover_m).rename("signed_turnover_m")


def estimate_lambda(returns_bps: pd.Series, signed_turnover_m: pd.Series) -> LambdaEstimate:
    """OLS of bar returns (bp) on signed turnover (M CNY); slope is lambda.

    Keeps an intercept and reports the slope, its t-statistic, and R^2.
    """
    frame = pd.concat({"y": returns_bps, "x": signed_turnover_m}, axis=1).dropna()
    frame = frame[frame["x"] != 0.0]
    x = frame["x"].to_numpy()
    y = frame["y"].to_numpy()
    n = len(x)
    if n < 3:
        raise ValueError("need at least 3 observations to estimate lambda")
    design = np.column_stack([np.ones_like(x), x])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    dof = n - 2
    var_x = np.sum((x - x.mean()) ** 2)
    se = np.sqrt(np.sum(resid**2) / dof / var_x) if var_x > 0 else float("nan")
    t_stat = beta[1] / se if se and np.isfinite(se) else float("nan")
    ss_tot = np.sum((y - y.mean()) ** 2)
    r_squared = 1.0 - np.sum(resid**2) / ss_tot if ss_tot > 0 else float("nan")
    return LambdaEstimate(
        lam_bps_per_million=float(beta[1]), t_stat=float(t_stat), r_squared=float(r_squared), n=n
    )


def capacity_at_impact(lam_bps_per_million: float, tolerance_bps: float, legs: int = 2) -> float:
    """Book size (M CNY) whose round-trip impact reaches ``tolerance_bps``."""
    if lam_bps_per_million <= 0:
        return float("inf")
    return tolerance_bps / (legs * lam_bps_per_million)


def participation_capacity(adv_cny: float, max_participation: float) -> float:
    """Book size (CNY) capped at a fraction of average daily volume."""
    return adv_cny * max_participation

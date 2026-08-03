"""Universe selection: information coefficient and out-of-sample discipline.

Narrowing the universe to the in-sample best subset almost always lifts the
backtest Sharpe -- and almost always overfits. The defensible check is whether
the wider universe carries *equal signal quality*: if the information
coefficient of the extra names is on par with the keepers, the wider, more
robust universe is the honest choice even at a lower in-sample Sharpe.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_TRADING_DAYS = 244


def rank_ic(signal: pd.DataFrame, forward_returns: pd.DataFrame) -> float:
    """Mean daily cross-sectional rank IC between cheapness and forward return.

    ``signal`` is the premium deviation (lower == cheaper), so we correlate
    ``-signal`` (cheapness) with the next-period return across funds each day and
    average the daily Spearman correlations.
    """
    cheap = -signal
    ics: list[float] = []
    for date in cheap.index:
        pair = pd.concat(
            {"cheap": cheap.loc[date], "fwd": forward_returns.loc[date]}, axis=1
        ).dropna()
        if len(pair) >= 3:
            ics.append(pair["cheap"].corr(pair["fwd"], method="spearman"))
    return float(np.nanmean(ics)) if ics else float("nan")


def annualized_sharpe(daily_excess: pd.Series, trading_days: int = _TRADING_DAYS) -> float:
    """Annualised Sharpe of a daily excess-return series."""
    x = daily_excess.dropna()
    sd = x.std()
    if sd == 0 or np.isnan(sd):
        return float("nan")
    return float(x.mean() * trading_days / (sd * np.sqrt(trading_days)))


def forward_returns(close: pd.DataFrame, horizon: int = 1) -> pd.DataFrame:
    """Cross-sectional forward log returns over ``horizon`` days (for IC)."""
    logc = np.log(close)
    return (logc.shift(-horizon) - logc).rename_axis(columns=close.columns.name)

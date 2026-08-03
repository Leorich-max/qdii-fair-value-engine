"""Corwin-Schultz (2012) bid-ask spread estimator from daily high/low.

For thinly-quoted ETFs the true spread is not in the trade tape, but it can be
estimated from the daily high-low range. Corwin & Schultz (2012, *Journal of
Finance*) show that over two consecutive days the high-low range reflects both
the price variance (which scales with the interval) and the bid-ask spread
(which does not), so the two can be separated.

We use the data-implied half-spread as the per-leg execution cost in the cost
ladder -- it is the microstructure-grounded alternative to guessing a flat bp
figure. On this universe the per-fund half-spread is roughly one price tick.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

_K = 3.0 - 2.0 * np.sqrt(2.0)  # constant in the Corwin-Schultz alpha


def corwin_schultz_spread(high: pd.Series, low: pd.Series) -> pd.Series:
    """Estimated proportional bid-ask spread from daily high/low.

    Each estimate uses a consecutive-day pair ``(t-1, t)`` and is indexed at the
    later day ``t`` (the first observation is therefore NaN). Negative estimates
    -- which the estimator can produce in noise -- are clamped to zero, the
    standard convention.

    Parameters
    ----------
    high, low:
        Daily high and low prices, aligned on the same ascending index.

    Returns
    -------
    pandas.Series
        Proportional spread ``S`` (e.g. 0.001 == 10 bp), named ``cs_spread``.
    """
    high = high.astype(float)
    low = low.astype(float)

    beta_single = np.log(high / low) ** 2
    beta = beta_single + beta_single.shift(1)  # sum over days t-1 and t

    high_2day = pd.concat([high, high.shift(1)], axis=1).max(axis=1)
    low_2day = pd.concat([low, low.shift(1)], axis=1).min(axis=1)
    gamma = np.log(high_2day / low_2day) ** 2

    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / _K - np.sqrt(gamma / _K)
    spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    return spread.clip(lower=0.0).rename("cs_spread")


def corwin_schultz_half_spread_bps(high: pd.Series, low: pd.Series) -> pd.Series:
    """Per-leg half-spread in basis points (``spread / 2``)."""
    return (corwin_schultz_spread(high, low) / 2.0 * 1e4).rename("cs_half_spread_bps")

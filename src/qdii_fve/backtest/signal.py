"""The relative-value signal (construction logic; parameters come from config).

The tradable quantity is how *cheap* a fund is versus fair value relative to its
peers and to its own recent norm -- a cross-sectional, mean-reverting premium
deviation. Concretely, per date:

1. ``premium``      : log premium of price to reconstructed fair value (bp).
2. ``spread``       : premium minus the cross-sectional mean (demean vs the basket).
3. ``norm``         : trailing mean of the spread over ``lookback`` days (lagged).
4. ``dev``          : ``spread - norm`` -- how cheap a fund is versus its own norm.

The rotation holds the fund with the lowest ``dev`` (the cheapest) and switches
when the held fund's ``dev`` exceeds the cheapest by more than a threshold. The
``lookback`` and threshold are calibrated values loaded from the gitignored
config, not hardcoded here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def observed_premium_bps(close: pd.DataFrame, fair_value: pd.DataFrame) -> pd.DataFrame:
    """Log premium (bp) of observed price to reconstructed fair value, per fund."""
    return np.log(close / fair_value) * 1e4


def cross_sectional_dev(premium_bps: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Cross-sectional, norm-relative premium deviation (bp); lower == cheaper.

    Parameters
    ----------
    premium_bps:
        Premium panel (dates x funds), in basis points.
    lookback:
        Trailing window (days) for each fund's norm. Lagged by one day so the
        signal on day ``t`` uses only information available before ``t``.
    """
    spread = premium_bps.sub(premium_bps.mean(axis=1), axis=0)
    norm = spread.rolling(lookback).mean().shift(1)
    return (spread - norm).rename_axis(columns=premium_bps.columns.name)

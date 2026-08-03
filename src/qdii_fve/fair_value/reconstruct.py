"""Real-time fair-value reconstruction for US-underlying QDII ETFs.

The problem
-----------
A China-listed ETF tracking a US index (here, the NASDAQ-100) publishes an
exchange IOPV that is **stale during A-share hours**: the US underlying is
closed, so the vendor IOPV simply carries the prior US close and does not move
with the fund's true economic value. Trading the premium against a stale IOPV
is trading against a number that is hours out of date.

The reconstruction
------------------
The fund's economic value at intraday time ``t`` is the last published NAV,
scaled by how far the underlying and the currency have moved since the NAV was
struck::

    FV(t) = NAV0 * (U(t) / U0) * (FX(t) / FX0)

where

* ``NAV0`` is the rolled-forward NAV (see :mod:`qdii_fve.fair_value.nav`),
* ``U`` is the NASDAQ-100 level -- NASDAQ-100 futures intraday, or the
  dividend-adjusted (QFQ) QQQ close for the NAV reference,
* ``FX`` is USDCNH, struck against the CFETS central parity on the NAV date.

Because the US market is closed during A-share hours, ``U(t)`` is effectively
the last US close and moves day-to-day rather than minute-to-minute; the live
variation intraday comes through futures and USDCNH. Validated against realised
next-day NAV, the residual standard deviation is on the order of a few bp (see
notebook ``01_fair_value_engine``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def reconstruct_fair_value(
    nav_value: float,
    nav_underlying: float,
    nav_fx: float,
    current_underlying: float,
    current_fx: float,
) -> float:
    """Roll a NAV forward to a fair value at the current underlying and FX.

    Parameters
    ----------
    nav_value:
        The (rolled-forward) NAV level ``NAV0``.
    nav_underlying, nav_fx:
        The underlying index level and USDCNH (vs CFETS parity) on the NAV date.
    current_underlying, current_fx:
        The underlying level and USDCNH at the valuation time ``t``.

    Returns
    -------
    float
        The reconstructed fair value ``FV(t)``.

    Raises
    ------
    ValueError
        If any NAV-date reference level is non-positive.
    """
    if nav_underlying <= 0 or nav_fx <= 0:
        raise ValueError("NAV-date underlying and FX levels must be positive")
    return nav_value * (current_underlying / nav_underlying) * (current_fx / nav_fx)


def reconstruct_series(
    nav_value: pd.Series,
    nav_underlying: pd.Series,
    nav_fx: pd.Series,
    current_underlying: pd.Series,
    current_fx: pd.Series,
) -> pd.Series:
    """Vectorised :func:`reconstruct_fair_value` over an aligned date index.

    All inputs share one index (the valuation dates/times). ``nav_*`` carry the
    applicable rolled-forward vintage per row; ``current_*`` carry the level at
    the valuation time.
    """
    frame = pd.concat(
        {
            "nav_value": nav_value,
            "nav_underlying": nav_underlying,
            "nav_fx": nav_fx,
            "current_underlying": current_underlying,
            "current_fx": current_fx,
        },
        axis=1,
    )
    if (frame[["nav_underlying", "nav_fx"]] <= 0).any().any():
        raise ValueError("NAV-date underlying and FX levels must be positive")
    fv = (
        frame["nav_value"]
        * (frame["current_underlying"] / frame["nav_underlying"])
        * (frame["current_fx"] / frame["nav_fx"])
    )
    return fv.rename("fair_value")


def validation_residuals_bps(
    computed_fair_value: pd.Series,
    realised_nav: pd.Series,
) -> pd.Series:
    """Residuals (in basis points) of computed fair value vs realised NAV.

    Once the fund publishes the NAV that the computed fair value was predicting,
    the difference measures the model error. Returned in bp of the realised NAV.
    """
    aligned = pd.concat({"fv": computed_fair_value, "nav": realised_nav}, axis=1).dropna()
    return (np.log(aligned["fv"] / aligned["nav"]) * 1e4).rename("residual_bps")

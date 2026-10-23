"""Premium/discount of market price to reconstructed fair value.

The quantity of interest is the ETF's premium to *reconstructed* fair value,
not to the exchange IOPV, which does not move while the US underlying is closed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def premium(price: float, fair_value: float) -> float:
    """Simple premium of ``price`` to ``fair_value`` (e.g. 0.03 == +3%)."""
    if fair_value <= 0:
        raise ValueError("fair_value must be positive")
    return price / fair_value - 1.0


def log_premium(price: float, fair_value: float) -> float:
    """Log premium ``ln(price / fair_value)``; additive and near-symmetric."""
    if price <= 0 or fair_value <= 0:
        raise ValueError("price and fair_value must be positive")
    return float(np.log(price / fair_value))


def premium_series(price: pd.Series, fair_value: pd.Series) -> pd.Series:
    """Log premium over an aligned index, returned in basis points."""
    aligned = pd.concat({"px": price, "fv": fair_value}, axis=1).dropna()
    if (aligned <= 0).any().any():
        raise ValueError("price and fair_value must be positive")
    return (np.log(aligned["px"] / aligned["fv"]) * 1e4).rename("premium_bps")


def premium_bps_panel(price: pd.DataFrame, fair_value: pd.DataFrame) -> pd.DataFrame:
    """Log premium in basis points for a dates x funds panel (NaN where either side is missing)."""
    if (price <= 0).any().any() or (fair_value <= 0).any().any():
        raise ValueError("price and fair_value must be positive")
    return np.log(price / fair_value) * 1e4

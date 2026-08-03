"""Deterministic synthetic data generator.

This produces **fake** data that reproduces the *mechanics* of the pipeline so
every notebook and the tests run end to end without any vendor data. It is not
calibrated to reproduce the real research figures; its outputs are illustrative.

The generator deliberately bakes in the structure each stage needs:

* a common underlying (NASDAQ-100 proxy) and USDCNH, so the fair-value engine
  has something to reconstruct;
* per-fund mean-reverting premia with a shared component, so the relative-value
  signal has cross-sectional dispersion to trade;
* a fund-specific bid-ask spread and an explicit **bid-ask bounce** in the
  observed close, so the bounce decomposition has real bounce to remove;
* liquidity that varies across funds (thin vs liquid), so the cost and capacity
  stages see a realistic spread of spreads and volumes.

All randomness flows from a single seed; the same seed yields identical output.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FUND_IDS = [f"ETF_{i:02d}" for i in range(1, 13)]


def _ou(
    rng: np.random.Generator, n: int, mu: float, kappa: float, sigma: float, x0: float
) -> np.ndarray:
    """One Ornstein-Uhlenbeck path (discrete mean-reversion)."""
    x = np.empty(n)
    x[0] = x0
    for t in range(1, n):
        x[t] = x[t - 1] + kappa * (mu - x[t - 1]) + sigma * rng.standard_normal()
    return x


def generate_sample(
    seed: int = 20260101,
    n_days: int = 260,
    fund_ids: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Generate the synthetic sample as a dict of tidy DataFrames.

    Returns keys ``daily_bars``, ``nav``, ``underlying``, ``usdcnh``.
    """
    rng = np.random.default_rng(seed)
    funds = list(fund_ids) if fund_ids is not None else list(FUND_IDS)
    n_funds = len(funds)
    dates = pd.bdate_range("2024-06-03", periods=n_days)

    # --- common drivers: NASDAQ-100 proxy and USDCNH (vs CFETS parity) ---
    u = 20000.0 * np.exp(np.cumsum(rng.normal(3e-4, 1.2e-2, n_days)))
    fx = 7.20 * np.exp(np.cumsum(rng.normal(0.0, 2.0e-3, n_days)))
    parity = fx * np.exp(rng.normal(0.0, 3e-4, n_days))
    u_rel = u / u[0]
    fx_rel = fx / fx[0]

    # --- complex-wide premium (shared mean-reverting component, ~5%) ---
    common_prem = _ou(rng, n_days, mu=0.05, kappa=0.03, sigma=4e-3, x0=0.05)

    # --- per-fund liquidity tiers: adv (M CNY) spanning thin -> liquid ---
    adv_m = np.geomspace(55.0, 1000.0, n_funds)
    rng.shuffle(adv_m)
    # half-spread (fraction) shrinks with liquidity: ~2bp liquid, ~8bp thin
    half_spread = 0.0002 + 0.0006 * (np.log(1000.0) - np.log(adv_m)) / (
        np.log(1000.0) - np.log(55.0)
    )

    bar_rows, nav_rows = [], []
    for j, fund in enumerate(funds):
        base = float(rng.uniform(1.5, 2.6))
        idio = _ou(rng, n_days, mu=0.0, kappa=0.08, sigma=rng.uniform(2e-3, 4e-3), x0=0.0)
        premium = common_prem + idio

        fair_value = base * u_rel * fx_rel
        nav_true = fair_value  # NAV struck at close == fair value in this toy model
        mid = fair_value * (1.0 + premium)

        hs = float(half_spread[j])
        bounce = rng.choice([-1.0, 1.0], size=n_days) * hs  # bid-ask bounce
        close = mid * (1.0 + bounce)
        intraday_range = hs + np.abs(rng.normal(0.0, 1.5e-3, n_days))
        high = mid * (1.0 + intraday_range)
        low = mid * (1.0 - intraday_range)
        open_ = mid * (1.0 + rng.normal(0.0, 1e-3, n_days))
        bid = mid * (1.0 - hs)
        ask = mid * (1.0 + hs)
        dollar_vol = adv_m[j] * 1e6 * np.exp(rng.normal(0.0, 0.35, n_days))
        volume = np.round(dollar_vol / close)

        bar_rows.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "etf_id": fund,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "bid": bid,
                    "ask": ask,
                    "volume": volume,
                }
            )
        )
        # published NAV lags one session (today's NAV is not known intraday)
        nav_pub = pd.Series(nav_true, index=dates).shift(1)
        nav_rows.append(
            pd.DataFrame({"date": dates, "etf_id": fund, "nav": nav_pub.to_numpy()}).dropna()
        )

    daily_bars = pd.concat(bar_rows, ignore_index=True).round(4)
    nav = pd.concat(nav_rows, ignore_index=True).round(4)
    underlying = pd.DataFrame({"date": dates, "close": np.round(u, 2)})
    usdcnh = pd.DataFrame(
        {"date": dates, "usdcnh": np.round(fx, 4), "cfets_parity": np.round(parity, 4)}
    )
    return {"daily_bars": daily_bars, "nav": nav, "underlying": underlying, "usdcnh": usdcnh}

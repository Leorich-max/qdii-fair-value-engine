"""Tests for the backtest module: signal, engine, bounce, universe."""

from __future__ import annotations

import numpy as np
import pandas as pd

from qdii_fve.backtest.bounce import decompose_bounce
from qdii_fve.backtest.engine import run_rotation
from qdii_fve.backtest.signal import cross_sectional_dev, observed_premium_bps
from qdii_fve.backtest.universe import annualized_sharpe, forward_returns, rank_ic
from qdii_fve.synthetic import generate_sample


# ------------------------------------------------------------------- signal
def test_cross_sectional_dev_demeans_and_subtracts_norm() -> None:
    idx = pd.date_range("2025-01-01", periods=4, freq="D")
    prem = pd.DataFrame({"A": [10.0, 20.0, 30.0, 40.0], "B": [0.0, 0.0, 0.0, 0.0]}, index=idx)
    dev = cross_sectional_dev(prem, lookback=2)
    # spread_A = prem_A - mean = +5, +10, +15, +20 ; norm at t=2 is mean(spread[0:2]) = 7.5
    spread_a = prem["A"] - prem.mean(axis=1)
    norm_a = spread_a.rolling(2).mean().shift(1)
    expected_a = (spread_a - norm_a).to_numpy()
    np.testing.assert_allclose(dev["A"].to_numpy(), expected_a, equal_nan=True)


def test_observed_premium_bps_sign() -> None:
    close = pd.DataFrame({"A": [2.02]})
    fv = pd.DataFrame({"A": [2.00]})
    prem = observed_premium_bps(close, fv)
    assert prem["A"].iloc[0] == np.log(2.02 / 2.00) * 1e4


# ------------------------------------------------------------------- engine
def test_engine_holds_cheapest_and_beats_basket() -> None:
    idx = pd.date_range("2025-01-01", periods=4, freq="D")
    dev = pd.DataFrame({"A": [0.0] * 4, "B": [-100.0] * 4}, index=idx)  # B always cheapest
    close = pd.DataFrame({"A": [1.0, 1.0, 1.0, 1.0], "B": [1.0, 1.1, 1.2, 1.3]}, index=idx)
    res = run_rotation(dev, close, close, close, threshold_bps=50, fill_delay=1)
    assert res.n_switches == 0  # only the initial entry, no rotations
    assert res.daily_excess.sum() > 0  # B outperforms the equal-weight basket


def test_engine_respects_threshold() -> None:
    idx = pd.date_range("2025-01-01", periods=4, freq="D")
    # Day 0 picks A (cheapest); then B is only 30bp cheaper -> below the 50bp threshold.
    dev = pd.DataFrame({"A": [0.0, 0.0, 0.0, 0.0], "B": [10.0, -30.0, -30.0, -30.0]}, index=idx)
    close = pd.DataFrame({"A": [1.0] * 4, "B": [1.0] * 4}, index=idx)
    res = run_rotation(dev, close, close, close, threshold_bps=50, fill_delay=1)
    assert res.n_switches == 0


def test_engine_switches_when_gap_exceeds_threshold() -> None:
    idx = pd.date_range("2025-01-01", periods=5, freq="D")
    dev = pd.DataFrame(
        {"A": [0.0, 0.0, 0.0, 0.0, 0.0], "B": [10.0, 10.0, -100.0, -100.0, -100.0]}, index=idx
    )
    close = pd.DataFrame({"A": [1.0] * 5, "B": [1.0] * 5}, index=idx)
    res = run_rotation(dev, close, close, close, threshold_bps=50, fill_delay=1)
    assert res.n_switches == 1  # A -> B once B is >50bp cheaper


# ------------------------------------------------------------------- bounce
def test_bounce_same_bar_exceeds_executable() -> None:
    # Signal from the OBSERVED close (which carries bounce) -> same-bar fill books
    # the bounce reversion; the next-session opponent fill does not.
    bars = generate_sample(seed=11, n_days=200)["daily_bars"]
    close = bars.pivot(index="date", columns="etf_id", values="close")
    bid = bars.pivot(index="date", columns="etf_id", values="bid")
    ask = bars.pivot(index="date", columns="etf_id", values="ask")
    prem = np.log(close).mul(1e4)  # observed-price relative-value proxy
    dev = cross_sectional_dev(prem, lookback=20)
    res = decompose_bounce(dev, close, bid, ask, threshold_bps=30)
    assert np.isfinite(res.same_bar_ann)
    assert np.isfinite(res.executable_ann)
    assert res.same_bar_ann > res.executable_ann  # bounce inflates the same-bar fill
    assert 0.0 < res.bounce_fraction <= 1.0


# ----------------------------------------------------------------- universe
def test_rank_ic_positive_when_cheapness_predicts() -> None:
    idx = pd.date_range("2025-01-01", periods=30, freq="D")
    rng = np.random.default_rng(0)
    # cheaper (more negative dev) -> higher forward return, plus noise
    dev = pd.DataFrame(rng.normal(size=(30, 5)), index=idx, columns=list("ABCDE"))
    fwd = -dev + rng.normal(scale=0.1, size=(30, 5))
    assert rank_ic(dev, fwd) > 0.5


def test_annualized_sharpe_of_constant_series() -> None:
    s = pd.Series([0.001, 0.001, 0.001, 0.001])
    assert np.isnan(annualized_sharpe(s))  # zero variance -> undefined


def test_forward_returns_shape() -> None:
    idx = pd.date_range("2025-01-01", periods=5, freq="D")
    close = pd.DataFrame({"A": [1.0, 1.1, 1.2, 1.3, 1.4]}, index=idx)
    fwd = forward_returns(close, horizon=1)
    assert np.isnan(fwd["A"].iloc[-1])  # last has no forward value
    assert fwd["A"].iloc[0] == np.log(1.1 / 1.0)

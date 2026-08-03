"""Unit tests for the transaction-cost model."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qdii_fve.costs.corwin_schultz import (
    corwin_schultz_half_spread_bps,
    corwin_schultz_spread,
)
from qdii_fve.costs.ladder import (
    apply_switch_cost,
    breakeven_cost_bps,
    ladder_table,
    standard_ladder,
)


# ----------------------------------------------------------- Corwin-Schultz
def test_cs_zero_when_no_intraday_range() -> None:
    # high == low every day -> no range -> spread estimate clamps to 0.
    px = pd.Series([10.0, 10.1, 9.9, 10.2])
    spread = corwin_schultz_spread(px, px)
    np.testing.assert_allclose(spread.dropna().to_numpy(), 0.0)


def test_cs_matches_independent_formula_for_one_pair() -> None:
    high = pd.Series([10.0, 10.6, 10.2])
    low = pd.Series([9.7, 10.0, 9.85])

    # Independent re-derivation of the estimator for the pair (day0, day1).
    k = 3.0 - 2.0 * np.sqrt(2.0)
    beta = np.log(10.0 / 9.7) ** 2 + np.log(10.6 / 10.0) ** 2
    gamma = np.log(max(10.0, 10.6) / min(9.7, 10.0)) ** 2
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    expected = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))

    got = corwin_schultz_spread(high, low).iloc[1]
    assert got == pytest.approx(max(expected, 0.0))


def test_cs_wider_range_gives_wider_spread() -> None:
    rng = np.random.default_rng(0)
    mid = 10.0 + np.cumsum(rng.normal(0, 0.01, 200))
    tight = pd.Series(mid)
    wide_hi = pd.Series(mid) * 1.004
    wide_lo = pd.Series(mid) * 0.996
    tight_spread = corwin_schultz_spread(tight * 1.0005, tight * 0.9995).median()
    wide_spread = corwin_schultz_spread(wide_hi, wide_lo).median()
    assert wide_spread > tight_spread


def test_cs_half_spread_is_half_and_in_bps() -> None:
    high = pd.Series([10.0, 10.6, 10.2])
    low = pd.Series([9.7, 10.0, 9.85])
    spread = corwin_schultz_spread(high, low)
    half_bps = corwin_schultz_half_spread_bps(high, low)
    np.testing.assert_allclose(half_bps.to_numpy(), (spread / 2 * 1e4).to_numpy(), equal_nan=True)


# -------------------------------------------------------------------- ladder
def test_standard_ladder_rungs() -> None:
    base = standard_ladder()
    assert [r.name for r in base] == ["gross", "flat_1bp", "realistic_12bp", "conservative_20bp"]
    assert base[0].bps_per_swap == 0.0

    with_cs = standard_ladder(cs_half_spread_bps_per_leg=6.0)
    assert with_cs[-1].name == "corwin_schultz"
    assert with_cs[-1].bps_per_swap == pytest.approx(12.0)  # both legs


def test_apply_switch_cost_charges_only_on_switch() -> None:
    gross = pd.Series([0.001, 0.001, 0.001, 0.001])
    switched = pd.Series([0, 1, 0, 1])
    net = apply_switch_cost(gross, switched, cost_bps_per_swap=12.0)
    np.testing.assert_allclose(net.to_numpy(), [0.001, 0.001 - 0.0012, 0.001, 0.001 - 0.0012])


def test_breakeven_cost() -> None:
    # +6%/yr gross over 12 swaps/yr -> 50 bp/swap zeroes it.
    assert breakeven_cost_bps(0.06, 12) == pytest.approx(50.0)
    assert breakeven_cost_bps(0.06, 0) == float("inf")


def test_ladder_table_net_and_breakeven() -> None:
    table = ladder_table(0.06, 12, standard_ladder())
    row = table.set_index("rung").loc["realistic_12bp"]
    assert row["net_excess_per_year"] == pytest.approx(0.06 - 12 * 0.0012)
    assert table.attrs["breakeven_bps_per_swap"] == pytest.approx(50.0)

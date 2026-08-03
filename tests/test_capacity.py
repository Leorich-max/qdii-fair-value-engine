"""Unit tests for the Kyle-lambda capacity model."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qdii_fve.capacity.kyle_lambda import (
    capacity_at_impact,
    estimate_lambda,
    participation_capacity,
    signed_turnover_million,
)


def test_estimate_lambda_recovers_known_slope() -> None:
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(size=2000))
    y = 2.0 * x + rng.normal(scale=0.01, size=2000)  # slope 2.0, tiny noise
    est = estimate_lambda(y, x)
    assert est.lam_bps_per_million == pytest.approx(2.0, abs=0.01)
    assert est.t_stat > 10
    assert est.r_squared > 0.99
    assert est.n == 2000


def test_estimate_lambda_needs_data() -> None:
    with pytest.raises(ValueError):
        estimate_lambda(pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0]))


def test_signed_turnover_sign_follows_tick_rule() -> None:
    close = pd.Series([1.00, 1.01, 1.00, 1.00])  # up, down, flat
    volume = pd.Series([100.0, 100.0, 100.0, 100.0])
    st = signed_turnover_million(close, volume)
    assert st.iloc[1] > 0  # up-bar -> buy-initiated
    assert st.iloc[2] < 0  # down-bar -> sell-initiated
    assert st.iloc[3] == 0.0  # flat -> unsigned


def test_capacity_at_impact_math() -> None:
    # lambda 2 bp/M, round trip (2 legs), 12 bp budget -> 12 / (2*2) = 3 M CNY.
    assert capacity_at_impact(2.0, 12.0, legs=2) == pytest.approx(3.0)
    assert capacity_at_impact(0.0, 12.0) == float("inf")


def test_participation_capacity() -> None:
    assert participation_capacity(200e6, 0.05) == pytest.approx(10e6)

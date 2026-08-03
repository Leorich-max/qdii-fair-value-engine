"""Unit tests for the fair-value engine."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qdii_fve.fair_value.nav import NavVintage, roll_forward_nav
from qdii_fve.fair_value.premium import log_premium, premium, premium_series
from qdii_fve.fair_value.reconstruct import (
    reconstruct_fair_value,
    reconstruct_series,
    validation_residuals_bps,
)


# ---------------------------------------------------------------- reconstruct
def test_flat_underlying_and_fx_returns_nav() -> None:
    # No move in underlying or FX -> fair value equals the NAV exactly.
    fv = reconstruct_fair_value(
        nav_value=2.000,
        nav_underlying=20000.0,
        nav_fx=7.20,
        current_underlying=20000.0,
        current_fx=7.20,
    )
    assert fv == pytest.approx(2.000)


def test_underlying_and_fx_scale_multiplicatively() -> None:
    # +1% underlying and +0.5% FX compound onto the NAV.
    fv = reconstruct_fair_value(
        nav_value=2.000,
        nav_underlying=20000.0,
        nav_fx=7.20,
        current_underlying=20200.0,
        current_fx=7.236,
    )
    assert fv == pytest.approx(2.000 * 1.01 * 1.005)


def test_reconstruct_rejects_nonpositive_reference() -> None:
    with pytest.raises(ValueError):
        reconstruct_fair_value(2.0, 0.0, 7.2, 20000.0, 7.2)


def test_reconstruct_series_matches_scalar() -> None:
    idx = pd.date_range("2025-01-02", periods=3, freq="D")
    fv = reconstruct_series(
        nav_value=pd.Series([2.0, 2.0, 2.0], index=idx),
        nav_underlying=pd.Series([20000.0] * 3, index=idx),
        nav_fx=pd.Series([7.2] * 3, index=idx),
        current_underlying=pd.Series([20000.0, 20200.0, 19800.0], index=idx),
        current_fx=pd.Series([7.2, 7.236, 7.164], index=idx),
    )
    expected = [
        reconstruct_fair_value(2.0, 20000.0, 7.2, u, f)
        for u, f in zip([20000.0, 20200.0, 19800.0], [7.2, 7.236, 7.164], strict=False)
    ]
    np.testing.assert_allclose(fv.to_numpy(), expected)


# ------------------------------------------------------------------------ nav
def _nav_series() -> pd.Series:
    idx = pd.to_datetime(["2025-01-02", "2025-01-03", "2025-01-06"])
    return pd.Series([1.990, 2.000, 2.010], index=idx)


def test_roll_forward_picks_latest_before_as_of() -> None:
    v = roll_forward_nav(_nav_series(), as_of="2025-01-07")
    assert isinstance(v, NavVintage)
    assert v.value == pytest.approx(2.010)
    assert v.date == pd.Timestamp("2025-01-06")


def test_roll_forward_excludes_same_day_nav() -> None:
    # On 2025-01-06 today's NAV is not yet published -> use 2025-01-03.
    v = roll_forward_nav(_nav_series(), as_of="2025-01-06")
    assert v.value == pytest.approx(2.000)
    assert v.date == pd.Timestamp("2025-01-03")


def test_roll_forward_raises_when_too_stale() -> None:
    with pytest.raises(ValueError, match="stale"):
        roll_forward_nav(_nav_series(), as_of="2025-02-01", max_staleness_days=5)


def test_roll_forward_raises_when_no_prior_nav() -> None:
    with pytest.raises(ValueError, match="no NAV"):
        roll_forward_nav(_nav_series(), as_of="2025-01-01")


# -------------------------------------------------------------------- premium
def test_premium_and_log_premium() -> None:
    assert premium(2.06, 2.00) == pytest.approx(0.03)
    assert log_premium(2.00, 2.00) == pytest.approx(0.0)
    assert log_premium(np.e * 2.0, 2.0) == pytest.approx(1.0)


def test_premium_rejects_nonpositive() -> None:
    with pytest.raises(ValueError):
        premium(2.0, 0.0)


def test_premium_series_in_bps() -> None:
    idx = pd.date_range("2025-01-02", periods=2, freq="D")
    out = premium_series(
        price=pd.Series([2.02, 2.00], index=idx),
        fair_value=pd.Series([2.00, 2.00], index=idx),
    )
    np.testing.assert_allclose(out.to_numpy(), [np.log(1.01) * 1e4, 0.0])


def test_validation_residuals_zero_when_exact() -> None:
    idx = pd.date_range("2025-01-02", periods=3, freq="D")
    fv = pd.Series([2.0, 2.01, 1.99], index=idx)
    res = validation_residuals_bps(fv, fv.copy())
    np.testing.assert_allclose(res.to_numpy(), [0.0, 0.0, 0.0], atol=1e-9)

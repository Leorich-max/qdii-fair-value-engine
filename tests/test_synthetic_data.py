"""Tests for the synthetic sample generator: determinism and schema sanity."""

from __future__ import annotations

import pandas as pd

from qdii_fve.synthetic import FUND_IDS, generate_sample


def test_deterministic_same_seed() -> None:
    a = generate_sample(seed=7, n_days=60)
    b = generate_sample(seed=7, n_days=60)
    for key in a:
        pd.testing.assert_frame_equal(a[key], b[key])


def test_different_seed_differs() -> None:
    a = generate_sample(seed=1, n_days=60)
    b = generate_sample(seed=2, n_days=60)
    assert not a["daily_bars"]["close"].equals(b["daily_bars"]["close"])


def test_schema() -> None:
    s = generate_sample(seed=0, n_days=40)
    assert list(s["daily_bars"].columns) == [
        "date",
        "etf_id",
        "open",
        "high",
        "low",
        "close",
        "bid",
        "ask",
        "volume",
    ]
    assert list(s["nav"].columns) == ["date", "etf_id", "nav"]
    assert list(s["underlying"].columns) == ["date", "close"]
    assert list(s["usdcnh"].columns) == ["date", "usdcnh", "cfets_parity"]
    assert set(s["daily_bars"]["etf_id"]) == set(FUND_IDS)


def test_value_sanity() -> None:
    s = generate_sample(seed=0, n_days=80)
    bars = s["daily_bars"]
    assert (bars["high"] >= bars["low"]).all()
    assert (bars["ask"] >= bars["bid"]).all()
    assert (bars["volume"] > 0).all()
    assert (bars[["open", "high", "low", "close"]] > 0).all().all()
    assert (s["nav"]["nav"] > 0).all()


def test_cross_sectional_dispersion_exists() -> None:
    # The relative-value signal needs the funds to differ from each other.
    bars = generate_sample(seed=0, n_days=120)["daily_bars"]
    wide = bars.pivot(index="date", columns="etf_id", values="close")
    daily_std = wide.pct_change().std(axis=1)
    assert daily_std.mean() > 0.0

"""Tests for the live-stack patterns: quotes, halts, guards, auditor."""

from __future__ import annotations

from qdii_fve.execution.auditor import (
    reconcile_decisions,
    reconcile_holdings,
    reconcile_weight,
)
from qdii_fve.execution.guards import GuardConfig, check_order
from qdii_fve.execution.halts import resolve_prices, tradable_candidates
from qdii_fve.execution.quotes import Quote, normalize, poll_once


# ------------------------------------------------------------------- quotes
def test_normalize_and_book_helpers() -> None:
    q = normalize({"code": "ETF_01", "last": 2.0, "bid1": 1.999, "ask1": 2.001})
    assert isinstance(q, Quote)
    assert q.has_book
    assert q.spread_frac == (2.001 - 1.999) / 2.0
    assert q.status == "TRADE"  # default


def test_poll_once_uses_injected_fetch() -> None:
    def fake_fetch(codes: list[str]) -> list[dict[str, object]]:
        return [{"code": c, "last": 2.0, "bid1": 1.99, "ask1": 2.01} for c in codes]

    quotes = poll_once(fake_fetch, ["ETF_01", "ETF_02"])
    assert set(quotes) == {"ETF_01", "ETF_02"}


# -------------------------------------------------------------------- halts
def test_resolve_prices_forward_fills_and_suspends() -> None:
    raw = {"ETF_01": 2.0, "ETF_02": None, "ETF_03": float("nan"), "ETF_04": 0.0}
    last_good = {"ETF_01": 1.9, "ETF_02": 2.5, "ETF_03": 3.1, "ETF_04": 1.5}
    res = resolve_prices(raw, last_good, min_live=2)
    assert res.prices["ETF_02"] == 2.5  # forward-filled
    assert res.suspended == {"ETF_02", "ETF_03", "ETF_04"}
    assert res.enough_live is False  # only ETF_01 is genuinely live (< 2)


def test_tradable_candidates_keeps_held_excludes_suspended() -> None:
    codes = ["ETF_01", "ETF_02", "ETF_03"]
    cands = tradable_candidates(codes, suspended={"ETF_02", "ETF_03"}, held="ETF_03")
    assert cands == ["ETF_01", "ETF_03"]  # held stays even if suspended


# ------------------------------------------------------------------- guards
def _q(**kw: object) -> Quote:
    base: dict[str, object] = {"code": "ETF_01", "last": 2.0, "bid1": 1.999, "ask1": 2.001}
    base.update(kw)
    return normalize(base)


def test_guard_passes_clean_book() -> None:
    ok, reason = check_order(_q(), is_buy=True)
    assert ok and reason == "ok"


def test_guard_blocks_halt_and_no_book_and_wide_spread() -> None:
    assert check_order(_q(status="HALT"), is_buy=True)[0] is False
    assert check_order(_q(bid1=0.0, ask1=0.0), is_buy=True)[0] is False
    wide = _q(bid1=1.90, ask1=2.10)  # ~10% spread
    assert check_order(wide, is_buy=True, cfg=GuardConfig(max_spread_frac=0.01))[0] is False


def test_guard_blocks_at_price_limits() -> None:
    at_up = _q(bid1=2.09, ask1=2.10, limit_up=2.10)
    assert check_order(at_up, is_buy=True)[1] == "at limit-up"
    at_down = _q(bid1=1.80, ask1=1.81, limit_down=1.80)
    assert check_order(at_down, is_buy=False)[1] == "at limit-down"


# ------------------------------------------------------------------ auditor
def test_reconcile_holdings() -> None:
    assert reconcile_holdings("ETF_01", "ETF_01") == []
    assert reconcile_holdings("ETF_01", "ETF_02")[0].kind == "holding_mismatch"


def test_reconcile_decisions_flags_mismatch_and_missing() -> None:
    logged = [("2025-01-02", "HOLD"), ("2025-01-03", "ROTATE")]
    replay = [("2025-01-02", "HOLD"), ("2025-01-03", "HOLD")]
    out = reconcile_decisions(logged, replay)
    assert len(out) == 1 and out[0].kind == "decision_mismatch"

    out2 = reconcile_decisions([("2025-01-04", "HOLD")], replay)
    assert out2[0].kind == "missing_replay"


def test_reconcile_weight_band() -> None:
    assert reconcile_weight(0.034, 0.033, tolerance=0.005) == []
    assert reconcile_weight(0.05, 0.033, tolerance=0.005)[0].kind == "weight_drift"

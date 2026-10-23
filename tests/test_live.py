"""Offline tests for the daily pipeline: parsers, model rules (hand-computed), fail-safe."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from qdii_fve.live import model, sources, update

# ---------------------------------------------------------------- parsers


def test_parse_tencent() -> None:
    text = json.dumps(
        {"data": {"sh513100": {"day": [["2026-10-21", "2.352", "2.311", "2.358", "2.308", "1"]]}}}
    )
    assert sources.parse_tencent(text, "sh513100") == {"2026-10-21": 2.311}  # close is column 2


def test_parse_lsjz_skips_blank_nav() -> None:
    text = json.dumps(
        {
            "Data": {
                "LSJZList": [
                    {"FSRQ": "2026-10-21", "DWJZ": "1.9960"},
                    {"FSRQ": "2026-10-20", "DWJZ": ""},
                ]
            }
        }
    )
    assert sources.parse_lsjz(text) == [("2026-10-21", 1.996)]


def test_parse_safe_finds_usd_column_from_header() -> None:
    html = (
        "<table><tr><th>日期</th><th>欧元</th><th>美元</th></tr>"
        "<tr><td>2026-10-23</td><td>751.4</td><td>671.8</td></tr></table>"
    )
    assert sources.parse_safe(html) == {"2026-10-23": pytest.approx(6.718)}


def test_parse_safe_real_layout_gbk_and_comments() -> None:
    # the real page: GBK-encoded, header cells padded with whitespace and template comments
    html = (
        '<meta http-equiv="Content-Type" content="text/html; charset=gbk">'
        "<table><tr><th>日期</th>"
        '<th>\r\n <!-- <s:property value="currency"/> -->\r\n 美元\r\n </th>'
        "<th>欧元</th></tr><tr><td>2026-10-23</td><td>671.8</td><td>751.4</td></tr></table>"
    )
    text = sources.decode(html.encode("gbk"))
    assert sources.parse_safe(text) == {"2026-10-23": pytest.approx(6.718)}


def test_parse_safe_without_usd_header_fails() -> None:
    with pytest.raises(sources.SourceError):
        sources.parse_safe("<table><tr><td>2026-10-23</td><td>671.8</td></tr></table>")


def test_parse_chinamoney() -> None:
    text = json.dumps({"records": [{"date": "2026-10-23", "values": ["6.7180", "7.80"]}]})
    assert sources.parse_chinamoney(text) == {"2026-10-23": 6.718}


def test_parse_yahoo_uses_us_trading_date_and_dividends() -> None:
    text = json.dumps({"chart": {"result": [{
        "timestamp": [1792589400, 1792675800],  # 2026-10-21 / 2026-10-22, 13:30 UTC (09:30 ET)
        "indicators": {"quote": [{"close": [725.2, None]}]},
        "events": {"dividends": {"1792589400": {"amount": 0.75, "date": 1792589400}}},
    }]}})  # fmt: skip
    px, divs = sources.parse_yahoo(text)
    assert px == {"2026-10-21": 725.2}  # a missing close is dropped, not zero-filled
    assert divs == {"2026-10-21": 0.75}


def test_parse_nasdaq() -> None:
    hist = json.dumps(
        {"data": {"tradesTable": {"rows": [{"date": "10/22/2026", "close": "704.47"}]}}}
    )
    div = json.dumps(
        {"data": {"dividends": {"rows": [{"exOrEffDate": "09/21/2026", "amount": "$0.75143"}]}}}
    )
    assert sources.parse_nasdaq(hist, div) == ({"2026-10-22": 704.47}, {"2026-09-21": 0.75143})


# ---------------------------------------------------------------- model


def test_total_return_index_adds_dividend_back() -> None:
    tr = model.total_return_index({"a": 100.0, "b": 99.0, "c": 99.0}, {"b": 1.0})
    # b: close falls 100 -> 99 on the ex-date but the 1.0 dividend is added back; c: flat
    assert tr == {"a": 1.0, "b": pytest.approx(1.0), "c": pytest.approx(1.0)}


def test_fair_value_uses_last_us_close_before_t_and_parity_of_t() -> None:
    # NAV valued Mon 10-19; t = Wed 10-21. QQQ: Mon 100, Tue 102; Wed's US session comes after
    # the A-share close, so it must not be used.
    navs = {"2026-10-19": 1.0}
    qtr = {"2026-10-19": 100.0, "2026-10-20": 102.0, "2026-10-21": 150.0}
    parity = {"2026-10-19": 7.0, "2026-10-21": 7.07}
    fv, d, nav = model.fair_value_at(
        "2026-10-21", model.Lookup(navs), model.Lookup(qtr), model.Lookup(parity)
    )
    assert (d, nav) == ("2026-10-19", 1.0)
    assert fv == pytest.approx(1.0 * 102 / 100 * 7.07 / 7.0)


def test_nav_date_on_us_holiday_uses_previous_us_close() -> None:
    navs = {"2026-11-26": 2.0}  # US Thanksgiving: no US close that day
    qtr = {"2026-11-25": 100.0, "2026-11-27": 101.0}
    parity = {"2026-11-26": 7.1, "2026-11-30": 7.1}
    fv, _, _ = model.fair_value_at(
        "2026-11-30", model.Lookup(navs), model.Lookup(qtr), model.Lookup(parity)
    )
    assert fv == pytest.approx(2.0 * 101 / 100)


def test_missing_parity_on_t_gives_a_gap() -> None:
    fv, d, _ = model.fair_value_at(
        "2026-10-21",
        model.Lookup({"2026-10-19": 1.0}),
        model.Lookup({"2026-10-19": 100.0, "2026-10-20": 101.0}),
        model.Lookup({"2026-10-19": 7.0}),
    )
    assert fv is None and d == "2026-10-19"


def test_fund_rows_premium() -> None:
    rows = model.fund_rows(
        {"2026-10-21": 1.05}, {"2026-10-19": 1.0}, {"2026-10-19": 100.0, "2026-10-20": 102.0},
        {"2026-10-19": 7.0, "2026-10-21": 7.07}, "2026-01-01",
    )  # fmt: skip
    fv = 102 / 100 * 7.07 / 7.0
    assert rows[0]["premium_bp"] == pytest.approx(math.log(1.05 / fv) * 1e4)


def test_nav_validation_residual() -> None:
    navs = {"2026-10-19": 1.0, "2026-10-20": 1.02}
    qtr = {"2026-10-19": 100.0, "2026-10-20": 101.0}
    parity = {"2026-10-19": 7.0, "2026-10-20": 7.07}
    ((d, r),) = model.nav_validation(navs, qtr, parity, "2026-01-01")
    expected = (math.log(1.02) - math.log(1.01) - math.log(7.07 / 7.0)) * 1e4
    assert d == "2026-10-20" and r == pytest.approx(expected)


# ---------------------------------------------------------------- merge + checks + fail-safe


def test_merge_navs_first_seen_and_revisions() -> None:
    old = [
        dict(
            code="513100", nav_date="2026-10-20", nav="1.9741", first_seen_utc="T0", revised_utc=""
        )
    ]
    rows, n_new, rev = update.merge_navs(
        old, {"513100": [("2026-10-21", 1.996), ("2026-10-20", 1.9750)]}, "T1"
    )
    by = {r["nav_date"]: r for r in rows}
    assert n_new == 1 and by["2026-10-21"]["first_seen_utc"] == "T1"
    assert by["2026-10-20"]["first_seen_utc"] == "T0" and by["2026-10-20"]["revised_utc"] == "T1"
    assert rev == [("513100", "2026-10-20", "1.9741", "1.9750")]


def test_check_flags_missing_close_and_stale_inputs() -> None:
    prices = {"513100": {"2026-10-23": 2.2}, "513300": {"2026-10-22": 2.1}}
    navs = [dict(code="513100", nav_date="2026-10-21"), dict(code="513300", nav_date="2026-10-01")]
    problems = update.check(prices, navs, {"2026-10-22": 6.7}, {"2026-10-10": 700.0})
    text = " | ".join(problems)
    assert "513300: no close" in text and "513300: newest NAV" in text
    assert "no CFETS parity for 2026-10-23" in text and "stale" in text


def test_failed_fetch_writes_nothing(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "data.js").write_text("OLD", encoding="utf-8")

    def broken(backfill=False):
        raise sources.SourceError("yahoo: blocked")

    with pytest.raises(update.UpdateError):
        update.run(root=tmp_path, fetch=broken)
    assert (tmp_path / "app" / "data.js").read_text(encoding="utf-8") == "OLD"
    assert not (tmp_path / "data").exists()


def test_failed_check_writes_nothing(tmp_path: Path) -> None:
    def stale(backfill=False):
        return dict(prices={"513100": {"2026-10-23": 2.2}}, navs={"513100": [("2026-09-01", 2.0)]},
                    parity={"2026-10-23": 6.7}, parity_src="SAFE", qqq_px={"2026-10-22": 700.0},
                    qqq_div={}, qqq_src="Yahoo")  # fmt: skip

    with pytest.raises(update.UpdateError, match="newest NAV"):
        update.run(root=tmp_path, fetch=stale)
    assert not (tmp_path / "app").exists() and not (tmp_path / "data").exists()


def test_backfilled_navs_are_not_publication_evidence() -> None:
    rows, _, _ = update.merge_navs([], {"513100": [("2026-10-21", 1.996)]}, "backfill", "T1")
    assert rows[0]["first_seen_utc"] == "backfill"

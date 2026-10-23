"""Pure model for the daily dashboard (no network): fair value at the A-share close, NAV checks.

Fair value of fund i at the A-share close of trading day t::

    FV(t) = NAV(D) x QQQ_TR(u_now) / QQQ_TR(u_ref) x PARITY(t) / PARITY(p_ref)

- D      = the latest NAV valuation date before t (a stated convention: when each NAV was really
           published is not in the source; the pipeline records when it first SEES each NAV);
- u_now  = the last US trading date before t (that session closed in the early Beijing morning of t;
           overnight QQQ and futures moves after it are NOT included);
- u_ref  = the last US trading date on or before D (covers US holidays);
- QQQ_TR = a total-return index built from closes and dividends, so a dividend is not a price drop;
- PARITY = the USD/CNY central parity (CFETS); p_ref = the last parity date on or before D.

Any missing input gives no value for that day (a gap), never a filled-in one.
"""

from __future__ import annotations

import bisect
import math
import statistics


def total_return_index(closes, dividends):
    """{date: index} with TR(t) = TR(t-1) x (close_t + dividend_t) / close_(t-1), starting at 1."""
    days = sorted(closes)
    out, prev = {}, None
    for d in days:
        if prev is None:
            out[d] = 1.0
        else:
            out[d] = out[prev] * (closes[d] + dividends.get(d, 0.0)) / closes[prev]
        prev = d
    return out


class Lookup:
    """Sorted-date lookups on a {date: value} mapping."""

    def __init__(self, series):
        self.series = series
        self.days = sorted(series)

    def on_or_before(self, d):
        i = bisect.bisect_right(self.days, d)
        return self.days[i - 1] if i else None

    def before(self, d):
        i = bisect.bisect_left(self.days, d)
        return self.days[i - 1] if i else None


def fair_value_at(t, navs: Lookup, qtr: Lookup, parity: Lookup):
    """(fv, nav_date, nav) at the A-share close of t; fv is None when an input is missing."""
    d = navs.before(t)
    if d is None:
        return None, None, None
    nav = navs.series[d]
    u_now, u_ref, p_ref = qtr.before(t), qtr.on_or_before(d), parity.on_or_before(d)
    if None in (u_now, u_ref, p_ref) or t not in parity.series:
        return None, d, nav
    fv = nav * (qtr.series[u_now] / qtr.series[u_ref]) * (parity.series[t] / parity.series[p_ref])
    return fv, d, nav


def fund_rows(closes, navs, qtr, parity, start):
    """Per trading day of one fund since ``start``: price, fair value, premium (bp), NAV used."""
    nl, ql, pl = Lookup(navs), Lookup(qtr), Lookup(parity)
    rows = []
    for t in sorted(d for d in closes if d >= start):
        fv, d, nav = fair_value_at(t, nl, ql, pl)
        prem = math.log(closes[t] / fv) * 1e4 if fv else None
        rows.append(dict(date=t, price=closes[t], fair=fv, premium_bp=prem, nav_date=d, nav=nav))
    return rows


def nav_validation(navs, qtr, parity, start):
    """Residual (bp) of each NAV return against the QQQ total return x parity mapping:

    resid = ln(NAV_1 / NAV_0) - ln(QQQ_TR(D_1) / QQQ_TR(D_0)) - ln(PARITY(D_1) / PARITY(D_0)),
    over consecutive valuation dates on or after ``start`` (dates looked up on or before each D).
    """
    ql, pl = Lookup(qtr), Lookup(parity)
    days = sorted(d for d in navs if d >= start)
    out = []
    for d0, d1 in zip(days, days[1:], strict=False):
        q0, q1, p0, p1 = (
            ql.on_or_before(d0),
            ql.on_or_before(d1),
            pl.on_or_before(d0),
            pl.on_or_before(d1),
        )
        if None in (q0, q1, p0, p1):
            continue
        model = math.log(qtr[q1] / qtr[q0]) + math.log(parity[p1] / parity[p0])
        out.append((d1, (math.log(navs[d1] / navs[d0]) - model) * 1e4))
    return out


def residual_stats(resid):
    vals = [r for _, r in resid]
    if len(vals) < 2:
        return dict(n=len(vals), std_bp=None, mae_bp=None)
    return dict(
        n=len(vals), std_bp=statistics.stdev(vals), mae_bp=statistics.fmean(abs(v) for v in vals)
    )

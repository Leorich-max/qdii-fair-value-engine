"""NAV vintage handling: roll a stale, lagged NAV forward to the trading day.

Fund NAVs are published with a lag (typically T-1, sometimes T-2). Intraday you
never have today's NAV, so the fair-value reconstruction starts from the most
recent *published* NAV and rolls it forward. Mixing vintages across funds is a
known source of error, so this module also enforces a staleness guard.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class NavVintage:
    """A published NAV together with the date it was struck."""

    value: float
    date: pd.Timestamp


def roll_forward_nav(
    nav: pd.Series,
    as_of: pd.Timestamp | str,
    max_staleness_days: int = 5,
) -> NavVintage:
    """Return the most recent NAV known at the *start* of ``as_of``.

    Parameters
    ----------
    nav:
        NAV levels indexed by the date each NAV was struck (ascending).
    as_of:
        The trading day for which fair value is being computed. Only NAVs
        struck *strictly before* ``as_of`` are eligible (today's NAV is not
        yet published intraday).
    max_staleness_days:
        Raise if the newest eligible NAV is older than this many calendar
        days. Guards against silently pricing off a holiday-stale vintage.

    Returns
    -------
    NavVintage
        The rolled-forward NAV value and the date it was struck.

    Raises
    ------
    ValueError
        If no NAV predates ``as_of``, or the newest one is too stale.
    """
    as_of = pd.Timestamp(as_of)
    eligible = nav.loc[nav.index < as_of].dropna()
    if eligible.empty:
        raise ValueError(f"no NAV published before {as_of.date()}")
    nav_date = eligible.index[-1]
    staleness = (as_of - nav_date).days
    if staleness > max_staleness_days:
        raise ValueError(
            f"newest NAV is {staleness}d stale (>{max_staleness_days}d) "
            f"as of {as_of.date()}; refusing to price off it"
        )
    return NavVintage(value=float(eligible.iloc[-1]), date=nav_date)

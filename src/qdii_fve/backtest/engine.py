"""Rotation engine: hold the cheapest fund, switch on a threshold, mark to close.

The engine is deliberately explicit about *fill prices* and *fill timing* so the
same code can express different execution assumptions -- in particular the two
fills the bounce decomposition compares:

* same-bar close fill  (``sell_px = buy_px = close``, ``fill_delay = 0``): an
  upper bound that transacts at the very close the signal just read; the close
  carries bid-ask bounce, so this over-states the edge.
* next-session opponent fill (``sell_px = bid``, ``buy_px = ask``,
  ``fill_delay = 1``): executable; you cross the spread the next session.

Equity is marked at the close each day; the benchmark is the equal-weight basket
marked the same way, so ``daily_excess`` is the excess return over the basket.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RotationResult:
    equity: pd.Series
    daily_excess: pd.Series
    switch_dates: list[pd.Timestamp]

    @property
    def n_switches(self) -> int:
        return len(self.switch_dates)


def run_rotation(
    dev: pd.DataFrame,
    close: pd.DataFrame,
    sell_px: pd.DataFrame,
    buy_px: pd.DataFrame,
    threshold_bps: float,
    fill_delay: int = 1,
) -> RotationResult:
    """Simulate the laggard-rotation with explicit fills; return excess vs basket.

    All panels are dates x funds on the same axes. ``dev`` (bp, lower == cheaper)
    drives selection; ``close`` marks equity and the basket; ``sell_px``/``buy_px``
    are the leg fill prices, taken at the fill bar (signal bar + ``fill_delay``).
    """
    funds = list(dev.columns)
    pos = {f: i for i, f in enumerate(funds)}
    dates = list(dev.index)
    n = len(dates)

    dev_v = dev.to_numpy()
    close_v = close[funds].to_numpy()
    sell_v = sell_px[funds].to_numpy()
    buy_v = buy_px[funds].to_numpy()

    cash = 1.0
    shares = 0.0
    held: str | None = None
    pending: str | None = None
    pending_bar = -1
    switch_dates: list[pd.Timestamp] = []
    equity = np.full(n, np.nan)

    for k in range(n):
        # 1) execute a fill scheduled for this bar
        if pending is not None and k >= pending_bar:
            if held is not None:
                cash += shares * sell_v[k, pos[held]]
                shares = 0.0
            shares = cash / buy_v[k, pos[pending]]
            cash -= shares * buy_v[k, pos[pending]]
            if held is not None:
                switch_dates.append(dates[k])
            held = pending
            pending = None

        # 2) decide a (new) target
        row = dev_v[k]
        if not np.all(np.isnan(row)):
            target = funds[int(np.nanargmin(row))]
            if pending is None:
                if held is None:
                    pending, pending_bar = target, min(k + fill_delay, n - 1)
                else:
                    gap = row[pos[held]] - np.nanmin(row)
                    if target != held and gap > threshold_bps:
                        pending, pending_bar = target, min(k + fill_delay, n - 1)

        # 3) mark to close
        equity[k] = shares * close_v[k, pos[held]] + cash if held is not None else cash

    eq = pd.Series(equity, index=dev.index, name="equity")
    strat_ret = np.log(eq / eq.shift(1))
    basket_ret = np.log(close[funds] / close[funds].shift(1)).mean(axis=1)
    daily_excess = (strat_ret - basket_ret).rename("daily_excess")
    return RotationResult(equity=eq, daily_excess=daily_excess, switch_dates=switch_dates)

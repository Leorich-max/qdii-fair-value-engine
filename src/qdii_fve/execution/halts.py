"""Trading-halt (临时停牌) handling.

High-premium NASDAQ-100 QDII ETFs are frequently halted for the first hour at
the open to cool an excessive premium. During a halt the quote feed returns no
price, which is easy to mistake for a data glitch. The correct handling, learned
the hard way, is:

* forward-fill the halted fund's price from its last good value (do not abandon
  the bar or retry the feed -- a halted fund has no price from any source);
* mark it suspended and exclude it from rotation candidates (you cannot trade
  into a halted fund);
* keep holding through if the *held* fund is the one halted;
* require a floor of live funds before trusting the cross-section at all.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def _is_missing(price: float | None) -> bool:
    return price is None or price == 0.0 or (isinstance(price, float) and math.isnan(price))


@dataclass
class ResolvedPrices:
    prices: dict[str, float]  # every code has a usable price (live or forward-filled)
    suspended: set[str] = field(default_factory=set)  # codes running on a stale price
    enough_live: bool = True  # False if fewer than the floor are actually live


def resolve_prices(
    raw_prices: dict[str, float | None],
    last_good: dict[str, float],
    min_live: int = 6,
) -> ResolvedPrices:
    """Forward-fill missing prices and flag the suspended funds.

    Parameters
    ----------
    raw_prices:
        Latest price per code; ``None``/``0``/``NaN`` means no live price.
    last_good:
        Last known good price per code, used to forward-fill.
    min_live:
        Minimum number of genuinely-live funds for the cross-section to be trusted.
    """
    prices: dict[str, float] = {}
    suspended: set[str] = set()
    live = 0
    for code, price in raw_prices.items():
        if _is_missing(price):
            if code in last_good:
                prices[code] = last_good[code]
                suspended.add(code)
        else:
            prices[code] = float(price)  # type: ignore[arg-type]
            live += 1
    return ResolvedPrices(prices=prices, suspended=suspended, enough_live=live >= min_live)


def tradable_candidates(codes: list[str], suspended: set[str], held: str | None) -> list[str]:
    """Rotation candidates: everything not suspended (the held fund always stays in)."""
    return [c for c in codes if c not in suspended or c == held]

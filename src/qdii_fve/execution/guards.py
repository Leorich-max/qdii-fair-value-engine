"""Pre-trade guards: only send an order when the book is safe to cross.

Each guard is a cheap veto that prevents a bad fill: no book, a halted status, a
spread too wide to cross without giving up the edge, or a price pinned at the
daily limit (where a marketable order can hang or fill far away). Thresholds are
conservative defaults and can be overridden from config.
"""

from __future__ import annotations

from dataclasses import dataclass

from .quotes import Quote


@dataclass(frozen=True)
class GuardConfig:
    max_spread_frac: float = 0.01  # skip if the quoted spread exceeds this fraction
    limit_tol_frac: float = 1e-4  # treat within this of the limit as "at the limit"


def check_order(quote: Quote, is_buy: bool, cfg: GuardConfig | None = None) -> tuple[bool, str]:
    """Return ``(ok, reason)``: whether it is safe to send this order, and why not.

    ``reason`` is ``"ok"`` when all guards pass; otherwise it names the failing guard.
    """
    cfg = cfg or GuardConfig()
    if quote.status != "TRADE":
        return False, f"status={quote.status}"
    if not quote.has_book:
        return False, "no book"
    if quote.spread_frac > cfg.max_spread_frac:
        return False, f"spread {quote.spread_frac:.4f} > {cfg.max_spread_frac}"
    if is_buy and quote.limit_up is not None:
        if quote.ask1 >= quote.limit_up * (1.0 - cfg.limit_tol_frac):
            return False, "at limit-up"
    if not is_buy and quote.limit_down is not None:
        if quote.bid1 <= quote.limit_down * (1.0 + cfg.limit_tol_frac):
            return False, "at limit-down"
    return True, "ok"

"""Quote polling pattern.

Representative of the live runner's quote loop, with the data source injected as
a callable so there is no hardcoded endpoint or credential. In production the
``fetch_fn`` wraps a public quote API; here it is any function returning raw
snapshots, which keeps the loop testable and provider-agnostic.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    """A normalised top-of-book snapshot for one instrument."""

    code: str
    last: float
    bid1: float
    ask1: float
    status: str  # e.g. "TRADE" | "HALT"
    limit_up: float | None = None
    limit_down: float | None = None

    @property
    def has_book(self) -> bool:
        return self.bid1 > 0 and self.ask1 > 0

    @property
    def spread_frac(self) -> float:
        if not self.has_book:
            return float("inf")
        mid = 0.5 * (self.bid1 + self.ask1)
        return (self.ask1 - self.bid1) / mid


def normalize(raw: dict[str, object]) -> Quote:
    """Normalise a provider snapshot dict into a :class:`Quote`."""
    return Quote(
        code=str(raw["code"]),
        last=float(raw.get("last", 0.0) or 0.0),
        bid1=float(raw.get("bid1", 0.0) or 0.0),
        ask1=float(raw.get("ask1", 0.0) or 0.0),
        status=str(raw.get("status", "TRADE")),
        limit_up=_opt_float(raw.get("limit_up")),
        limit_down=_opt_float(raw.get("limit_down")),
    )


def _opt_float(value: object) -> float | None:
    return None if value is None else float(value)  # type: ignore[arg-type]


def poll_once(
    fetch_fn: Callable[[Iterable[str]], list[dict[str, object]]],
    codes: Iterable[str],
) -> dict[str, Quote]:
    """Fetch one snapshot batch and return normalised quotes keyed by code."""
    codes = list(codes)
    return {q["code"]: normalize(q) for q in fetch_fn(codes) if str(q["code"]) in set(codes)}

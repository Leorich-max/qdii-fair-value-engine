"""Configuration loader — the mechanism that keeps real parameters out of git.

Calibrated parameters (lookback, switch threshold, sizing, the real universe)
live in ``config.yaml``, which is gitignored. If it is absent, this loader falls
back to ``config.example.yaml`` (placeholder values) so the notebooks still run.
``is_using_example`` lets callers warn the reader that the numbers are placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SignalParams:
    norm_lookback_days: int
    switch_threshold_bps: float
    rebalance_time: str


@dataclass(frozen=True)
class Config:
    etf_ids: list[str]
    signal: SignalParams
    ladder_bps: list[float]
    max_participation_of_adv: float
    data_source: str
    data_path: str
    raw: dict[str, Any]


def _resolve_path(explicit: str | Path | None) -> Path:
    if explicit is not None:
        return Path(explicit)
    real = _REPO_ROOT / "config.yaml"
    return real if real.exists() else _REPO_ROOT / "config.example.yaml"


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration, preferring ``config.yaml`` over the example."""
    cfg_path = _resolve_path(path)
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    sig = data["signal"]
    return Config(
        etf_ids=list(data["universe"]["etf_ids"]),
        signal=SignalParams(
            norm_lookback_days=int(sig["norm_lookback_days"]),
            switch_threshold_bps=float(sig["switch_threshold_bps"]),
            rebalance_time=str(sig["rebalance_time"]),
        ),
        ladder_bps=[float(x) for x in data["costs"]["ladder_bps"]],
        max_participation_of_adv=float(data["capacity"]["max_participation_of_adv"]),
        data_source=str(data["data"]["source"]),
        data_path=str(data["data"]["path"]),
        raw=data,
    )


def is_using_example(path: str | Path | None = None) -> bool:
    """True when the loader is falling back to the placeholder example config."""
    return _resolve_path(path).name == "config.example.yaml"

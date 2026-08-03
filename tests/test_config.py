"""Tests for the configuration loader / withholding mechanism."""

from __future__ import annotations

from pathlib import Path

from qdii_fve import config as cfgmod
from qdii_fve.config import is_using_example, load_config

EXAMPLE = Path(cfgmod.__file__).resolve().parents[2] / "config.example.yaml"


def test_example_config_values_are_placeholders() -> None:
    c = load_config(EXAMPLE)
    assert len(c.etf_ids) == 12
    assert c.etf_ids[0] == "ETF_01"  # anonymised, never a real ticker
    assert c.signal.norm_lookback_days == 45  # placeholder, not the deployed value
    assert c.signal.switch_threshold_bps == 50
    assert c.data_source == "synthetic"
    assert c.max_participation_of_adv == 0.05


def test_is_using_example_detects_by_name() -> None:
    assert is_using_example(EXAMPLE) is True
    assert is_using_example("/somewhere/config.yaml") is False

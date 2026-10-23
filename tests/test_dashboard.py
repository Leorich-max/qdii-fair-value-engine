"""Dashboard data and the in-page formula agree with the fair-value engine."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qdii_fve.dashboard import build_payload, compute, write_data_js
from qdii_fve.fair_value.premium import premium_bps_panel, premium_series
from qdii_fve.fair_value.reconstruct import reconstruct_fair_value

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"
FV_JS = ROOT / "app" / "fv.js"


def test_premium_bps_panel_matches_series() -> None:
    px = pd.DataFrame({"A": [1.01, 0.99], "B": [2.0, 2.1]})
    fv = pd.DataFrame({"A": [1.0, 1.0], "B": [2.0, 2.0]})
    panel = premium_bps_panel(px, fv)
    assert panel["A"].tolist() == pytest.approx(premium_series(px["A"], fv["A"]).tolist())
    assert panel.loc[0, "B"] == pytest.approx(0.0)


def test_premium_bps_panel_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        premium_bps_panel(pd.DataFrame({"A": [0.0]}), pd.DataFrame({"A": [1.0]}))


def test_payload_matches_engine_and_hand_formula() -> None:
    c = compute(SAMPLE)
    p = build_payload(SAMPLE)
    assert len(p["funds"]) == 12 and len(p["dates"]) == len(c["close"])
    f, k = "ETF_03", 40
    day, prev = c["close"].index[k], c["close"].index[k - 1]
    hand = reconstruct_fair_value(
        nav_value=float(c["nav"].loc[day, f]),
        nav_underlying=float(c["und"].loc[prev]),
        nav_fx=float(c["fx"].loc[prev, "cfets_parity"]),
        current_underlying=float(c["und"].loc[day]),
        current_fx=float(c["fx"].loc[day, "usdcnh"]),
    )
    assert p["funds"][f]["fair"][k] == pytest.approx(hand, abs=5e-5)  # payload rounds to 4 dp
    prem = math.log(float(c["close"].loc[day, f]) / hand) * 1e4
    assert p["funds"][f]["premium_bp"][k] == pytest.approx(prem, abs=0.05)
    # no NAV-date reference on the first day: shown as a gap, not a value
    assert p["funds"][f]["fair"][0] is None


def test_data_js_round_trip(tmp_path: Path) -> None:
    payload = build_payload(SAMPLE)
    out = write_data_js(payload, tmp_path / "data.js")
    text = out.read_text(encoding="utf-8")
    assert text.startswith("window.FV_DATA = ") and text.rstrip().endswith(";")
    assert json.loads(text[len("window.FV_DATA = ") : text.rstrip().rindex(";")]) == payload


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_formula_matches_python() -> None:
    rng = np.random.default_rng(1)
    cases = [
        [
            float(x)
            for x in (
                rng.uniform(1, 3),
                rng.uniform(1e4, 2e4),
                rng.uniform(1e4, 2e4),
                rng.uniform(6.8, 7.4),
                rng.uniform(6.8, 7.4),
                rng.uniform(1, 3),
            )
        ]
        for _ in range(20)
    ]
    script = (
        "const f = require(process.argv[1]); const cases = JSON.parse(process.argv[2]);"
        "console.log(JSON.stringify(cases.map(c => {"
        " const fv = f.fairValue(c[0], c[1], c[2], c[3], c[4]);"
        " return [fv, f.premiumBp(c[5], fv)]; })));"
    )
    out = subprocess.run(
        ["node", "-e", script, str(FV_JS), json.dumps(cases)],
        capture_output=True,
        text=True,
        check=True,
    )
    results = json.loads(out.stdout)
    for (nav, uref, unow, pref, fxnow, px), (fv_js, pb_js) in zip(cases, results, strict=True):
        fv_py = reconstruct_fair_value(nav, uref, pref, unow, fxnow)
        assert fv_js == pytest.approx(fv_py, rel=1e-12)
        assert pb_js == pytest.approx(math.log(px / fv_py) * 1e4, rel=1e-12)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_formula_rejects_non_positive_reference() -> None:
    script = (
        "const f = require(process.argv[1]);"
        " try { f.fairValue(1, 0, 1, 1, 1); console.log('no'); }"
        " catch (e) { console.log('raised'); }"
    )
    out = subprocess.run(
        ["node", "-e", script, str(FV_JS)], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "raised"

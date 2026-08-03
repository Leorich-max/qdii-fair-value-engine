# qdii-fair-value-engine

Relative-value research on **China-listed NASDAQ-100 QDII ETFs**: reconstruct a
real-time fair value the exchange doesn't provide, and trade the cross-sectional
premium to it.

> **Research artifact, not a product.** This repository documents the modelling
> and market-microstructure *methods* behind a live relative-value strategy. The
> calibrated parameters and the specific ETF universe are deliberately
> **withheld** ([why](#what-is-deliberately-withheld-and-why)). No real money is
> involved; no vendor data is redistributed.

---

## The inefficiency

A dozen China-listed ETFs track the NASDAQ-100. Because QDII (foreign-investment)
quotas are constrained, their creation/redemption arbitrage is throttled, so each
fund trades at a **premium to its true value that drifts and mean-reverts** — and
the premia move differently across funds. The exploitable edge is *relative*: hold
the fund that is cheapest versus fair value and its own norm, rotate as that
changes. The catch is that during A-share hours the US underlying is **closed**, so
the exchange's intraday IOPV is stale; the premium can only be measured against a
**reconstructed** fair value. Getting that reconstruction right is the whole game.

## If you read one thing

→ **[`02_bounce_decomposition`](notebooks/02_bounce_decomposition.ipynb)** — the
microstructure honesty check. A competing intraday signal looked like **+16.0%/yr**;
filling it the way you could actually trade it (next session, opponent side) left
**+7.9%/yr**. About **half the apparent alpha was bid-ask bounce, not edge.** That
decomposition — and the decision to report the executable number — is the single
best summary of how this research is done.

## Results

All performance is **excess return versus the 12-fund equal-weight basket** (not
versus QQQ), on ~2 years of data. Every figure is labelled and reproducible-in-method
from the linked notebook; the exact values were computed on licensed vendor data
that is **not** redistributed here, so the notebooks reproduce the *method* on
synthetic data whose outputs differ.

| What | Figure | Status | Where |
|---|---|---|---|
| Fair-value reconstruction error vs realised NAV | residual std **3.2 bp** (MAE 2.5 bp, corr 0.9975) | validated | [NB01](notebooks/01_fair_value_engine.ipynb) |
| Daily laggard rotation — excess vs basket @ 12 bp/swap | **+6.0%/yr**, Sharpe **1.16**, ~11 trades/yr, maxDD −3.1% | backtested (~2 yr) | [docs](docs/fair_value_derivation.md) |
| Intraday snapback — executable estimate | **+7.9%/yr** (next-session, Corwin-Schultz fills) | backtested · paper-only | [NB02](notebooks/02_bounce_decomposition.ipynb) |
| Bid-ask bounce decomposition | **+16.0% → +7.9%/yr** (~half the apparent edge was bounce) | backtested | [NB02](notebooks/02_bounce_decomposition.ipynb) |
| Universe choice (overfitting rejection) | 12-fund Sharpe **1.16** kept over in-sample 7-fund **1.56**; IC **+0.33 vs +0.32** | backtested | [NB03](notebooks/03_universe_selection_overfitting.ipynb) |
| Capacity (Kyle's λ price impact) | λ ≈ **0.5–3.9 bp per 1M CNY**; core capacity **~single-digit to ~15M CNY** | backtested | [docs](#capacity) |

Read the [caveats](#caveats) before any of these numbers — the sample carried a
premium-expansion tailwind, it is two years long, and nothing here is real-money.

## How it works

1. **Fair value** — reconstruct `FV = NAV × (index move) × (USDCNH move vs CFETS
   parity)` from the last published NAV; the exchange IOPV is stale intraday. Full
   derivation: [`docs/fair_value_derivation.md`](docs/fair_value_derivation.md).
2. **Signal (class, not constants)** — a cross-sectional, mean-reverting **premium
   deviation**: how cheap a fund is versus the basket and its own trailing norm.
   Hold the cheapest; rotate past a threshold. The lookback and threshold are
   withheld.
3. **Costs** — a Corwin-Schultz half-spread per leg, presented as a **ladder**
   (gross → realistic → conservative), not a point estimate, so you see where the
   edge survives.
4. **Capacity** — Kyle's λ from signed order flow bounds how much the edge absorbs.
5. **Execution** — a live stack with halt handling, pre-trade guards, and a daily
   reconciliation auditor: [`docs/architecture.md`](docs/architecture.md).

## Notebooks

Each runs top-to-bottom on the synthetic sample and tells one story.

- **[01 · Fair-value engine](notebooks/01_fair_value_engine.ipynb)** — reconstruct
  fair value, form the premium, validate against realised NAV.
- **[02 · Bounce decomposition](notebooks/02_bounce_decomposition.ipynb)** ⭐ — split
  a signal's apparent edge into bounce vs executable alpha.
- **[03 · Universe selection](notebooks/03_universe_selection_overfitting.ipynb)** —
  why the wider, lower-Sharpe universe is the disciplined choice.

## Capacity

Kyle's λ (bp of price impact per 1M CNY of signed order flow) is estimated per fund
by regressing bar returns on tick-rule-signed turnover. It runs **~0.5 bp/M** on the
liquid names and **~3.9 bp/M** on the thin ones. Because the rotation must sometimes
hold a thin fund, the binding constraint is the thin-fund λ, which puts the
practical capacity at **low single-digit to ~15M CNY** (an ADV-participation check
agrees, reaching the tens of millions only for the most liquid names). The method is
in [`src/qdii_fve/capacity`](src/qdii_fve/capacity).

## What is deliberately withheld, and why

The estimated capacity is **single-digit to low-double-digit millions of CNY**. A
strategy that small cannot absorb crowding, so publishing the exact recipe would
degrade it. Withheld:

- entry/exit thresholds, the norm lookback, and any z-score cutoffs;
- position-sizing coefficients and rebalance triggers;
- the specific ETF tickers and any weights (the code uses anonymised `ETF_01…12`);
- all credentials, account IDs, and API keys.

These load from a `config.yaml` that is **gitignored**; a
[`config.example.yaml`](config.example.yaml) ships placeholder values that are
plausible but **not** the deployed ones. The *class* of signal and its full
construction logic are described; the calibrated constants are not.

## Caveats

See **[LIMITATIONS.md](LIMITATIONS.md)** for the full list. In brief:

- **Premium-expansion tailwind.** Over the sample the whole complex's premium rose;
  part of the absolute return is that tailwind, not repeatable selection skill.
- **Two-year sample.** Short. The sub-period splits shown are *sub-periods of one
  sample*, not independent market regimes.
- **Paper / backtested, never real money.** A short forward paper-trading record
  exists but is too brief to headline; every figure above is backtested.
- **Capacity ceiling.** Single-digit to low-double-digit millions of CNY; the edge
  decays with size.

## Reproducing

```bash
pip install -e ".[dev,notebooks]"
python scripts/make_synthetic_sample.py     # deterministic synthetic sample
jupyter lab notebooks/                        # run any notebook top-to-bottom
```

The committed data under [`data/sample/`](data/sample) is **synthetic** and clearly
labelled; it reproduces the pipeline mechanics, not the real figures. To reproduce
the real figures, point the loaders at your own feed (fund NAVs, exchange quotes,
NASDAQ-100 futures / dividend-adjusted QQQ, and CFETS central parity — all public),
keeping the sample's column schema; see [`data/sample/README.md`](data/sample/README.md).
Exact reproduction also needs the same universe and window, and since the tickers
are withheld a reader reconstructs the universe themselves — so the **method and
ballpark** reproduce, not bit-exact figures.

## Engineering

- Type hints and docstrings throughout; deterministic seeds.
- **52 unit tests** (`pytest`), with coverage of the fair-value engine and the cost
  model in particular.
- `ruff` + `black`, enforced by pre-commit hooks and by GitHub Actions CI
  (lint + tests on every push).

## Repository layout

```
docs/            fair-value derivation, live-stack architecture
notebooks/       01 fair value · 02 bounce (hero) · 03 universe
src/qdii_fve/    fair_value · costs · backtest · capacity · execution · config
tests/           unit tests
data/sample/     synthetic sample only (no vendor data)
config.example.yaml   placeholder parameters (real config.yaml is gitignored)
```

## License

[MIT](LICENSE). The code is illustrative architecture; the strategy itself is not
open-sourced.

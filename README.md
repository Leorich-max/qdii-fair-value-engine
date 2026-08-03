# qdii-fair-value-engine

Fair-value engine and relative-value research toolkit for **China-listed
NASDAQ-100 QDII ETFs**.

> **Research artifact, not a product.** This repository documents the modelling
> and market-microstructure methods behind a relative-value strategy. The
> calibrated strategy parameters and the specific ETF universe are deliberately
> **withheld** (see *What is withheld* once the README is complete). No real
> money and no vendor data are involved.

---

🚧 **Scaffold in progress.** This commit sets up tooling only (packaging, lint,
tests, CI). Content lands in subsequent commits:

- `docs/` — fair-value derivation, live-stack architecture
- `notebooks/` — fair value, cost ladder, bounce decomposition, universe
  selection, capacity
- `src/qdii_fve/` — engine, cost model, backtest, execution patterns
- `data/sample/` — a small, clearly-labelled **synthetic** dataset so every
  notebook runs end to end

See `config.example.yaml` for the (placeholder) configuration surface.

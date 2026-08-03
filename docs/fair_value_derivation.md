# Fair-value reconstruction for US-underlying QDII ETFs

This is the modelling core of the project and is published in full: it is an
insight about *valuation*, not a trading rule. The exact validation figure is in
the top-level README results table; this note is the derivation.

## 1. The problem: a stale intraday IOPV

A China-listed ETF that tracks a US index (here the NASDAQ-100) trades on A-share
hours, roughly 09:30–15:00 Beijing, when the US market is **closed**. The vendor
IOPV (indicative optimised portfolio value) it disseminates intraday is built
from the last US close and does not move with the fund's true economic value
during the session. Any premium computed against that IOPV is a premium against
a number that is hours out of date — worse than useless for intraday trading,
because it moves for the wrong reasons (only FX and vendor refresh quirks).

The fix is to reconstruct the fair value ourselves, in real time.

## 2. Notation

| symbol | meaning |
|---|---|
| `NAV0` | the fund's most recent **published** net asset value |
| `d0` | the date `NAV0` was struck |
| `U(t)` | the NASDAQ-100 level at time `t` (futures intraday; div-adjusted QQQ for the NAV reference) |
| `FX(t)` | USDCNH at time `t` |
| `P(t)` | the ETF's traded price at time `t` |

## 3. The reconstruction

A QDII fund holds US equities valued in USD. Its per-share value in CNY is the
USD basket value times the exchange rate. Between the NAV strike and time `t`,
the only things that move the USD basket (to first order, for an index tracker)
are the index level and the currency. So the fair value rolls forward
multiplicatively:

```
FV(t) = NAV0 · ( U(t) / U(d0) ) · ( FX(t) / FX(d0) )
```

- `U(t) / U(d0)` captures the underlying index move since the NAV date.
- `FX(t) / FX(d0)` captures the CNY/USD move since the NAV date.

Both ratios are anchored at the NAV date `d0`, so the reconstruction is exact
whenever the fund is a faithful index tracker and the references are aligned.
Implemented in [`reconstruct.py`](../src/qdii_fve/fair_value/reconstruct.py).

## 4. NAV vintage and roll-forward

Fund NAVs are **published with a lag** (typically T-1, sometimes T-2). Intraday
you never have today's NAV, so `NAV0` is the most recent NAV struck strictly
before today, carried forward. Two subtleties matter:

- **Never mix vintages across funds.** If one fund is priced off a T-1 NAV and
  another off a T-2 NAV, their premia are not comparable and the cross-section
  is corrupted. The engine enforces a common, same-age vintage.
- **Staleness guard.** If the newest NAV is older than a few sessions (a holiday
  gap), refuse to price off it rather than roll a very stale value forward.

See [`nav.py`](../src/qdii_fve/fair_value/nav.py) (`roll_forward_nav`).

## 5. The reference details that actually bite

- **FX reference = CFETS central parity.** The NAV is struck against the CFETS
  central parity of its valuation date, not an arbitrary spot print. `FX(d0)`
  must be that parity for the ratio to be exact.
- **Underlying reference = dividend-adjusted (QFQ) QQQ closes.** For the NAV-date
  anchor, index closes must be dividend-adjusted; unadjusted closes inject a step
  at each ex-dividend date into the fair value.
- **Intraday driver = NASDAQ-100 futures.** With the US cash market closed,
  `U(t)` intraday is taken from the futures, which trade nearly around the clock;
  USDCNH continues to drift during A-share hours.

## 6. Validation

Once the fund publishes the NAV that a reconstruction was predicting, the
difference between the two is the model error. Aggregated over the sample, the
**standard deviation of that residual** (in bp of NAV) quantifies how good the
reconstruction is — it is small (a few bp; exact figure in the README results
table), which is what licenses trading the reconstructed premium.
[`validation_residuals_bps`](../src/qdii_fve/fair_value/reconstruct.py) computes
the residual series; notebook [`01_fair_value_engine`](../notebooks) walks it
through end to end on the synthetic sample.

## 7. Why this is the foundation

Every downstream stage — the relative-value signal, the basket demeaning, the
cost ladder, the capacity estimate — is built on the reconstructed premium. If
the fair value is wrong, everything above it is measuring noise. Getting this
one number right, and *validating* it against realised NAV, is what makes the
rest of the repository trustworthy.

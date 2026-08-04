# Limitations

The results in the README are honest but bounded. This is the specific list of
what could be wrong, weak, or non-repeatable — read it as part of the results.

## 1. A premium-expansion tailwind sits inside the sample

Over the ~2-year window the entire NASDAQ-100 QDII complex's premium **rose**.
Any absolute return (a fund's own P&L, or a comparison to QQQ) therefore embeds a
one-off tailwind that will not repeat and can reverse. This is why every headline
figure is quoted as **excess versus the 12-fund equal-weight basket**: demeaning
against the basket removes the common premium move and isolates *selection* skill.
Two consequences:

- The strategy is **not a QQQ substitute.** If the complex's premium deflates,
  the absolute return can be negative even while the excess-vs-basket edge holds.
- The excess-vs-basket edge is the defensible claim; the absolute/vs-QQQ numbers
  are not, and are deliberately kept out of the results table.

## 2. Two years is short, and it is one premium regime

The sample is a single ~2-year stretch. The sub-period splits shown in the
research are **sub-periods of one sample, not independent market regimes** — they
share funds, a data vendor, and one macro backdrop, so agreement across them is
weaker evidence than it looks. The premium was elevated for most of the window and
has recently been deflating; a genuinely different regime (a sustained discount, a
quota liberalisation) is simply not in the data.

## 3. Backtested and paper-traded — never real money

No figure here is realised P&L. The performance numbers are **backtested**. A live
**paper** record exists (an intraday runner and a broker-side paper book) but is
only weeks long — far too short to headline, and it is not the source of any
number in the README. Backtest execution is modelled at **next-session opponent
prices**; the naive "trade at the signal's own close" is not executable and is only
ever shown as a bounce-inflated upper bound (see the bounce notebook).

## 4. Capacity is low, and the edge decays with size

Kyle's-λ price impact puts practical capacity at **single-digit to ~15M CNY**,
bounded by the *thin* funds the rotation must sometimes hold. Beyond that, impact
consumes the per-rotation edge. λ is estimated from **tick-rule-signed** order flow
on bar data, not true trade-signed flow, so it is an approximation (a reasonable,
standard one, but an approximation). Capacity is a ceiling, not a target.

## 5. The fair-value model rests on assumptions

The reconstruction `FV = NAV × (index move) × (FX move)` and its ~3.2 bp validated
residual hold **under specific assumptions**:

- USDCNH is treated as roughly constant intraday (the US market is closed); large
  intraday FX moves would widen the residual.
- The intraday underlying is a **futures proxy** for the cash index; basis moves
  are unmodelled.
- NAVs are lagged (T-1/T-2) and must be same-vintage across funds; a mixed-vintage
  cross-section is corrupted, and the staleness guard is a blunt instrument.
- The residual is measured against *realised* NAV, which itself carries the fund's
  own tracking error.

The synthetic sample is **idealised** — it satisfies these assumptions by
construction, so the notebook's residual is near-zero. Real-world frictions that
produce the 3.2 bp are not in the sample.

## 6. Overfitting risk is acknowledged, not eliminated

Universe and parameter choices were stress-tested (the wider universe was kept over
a higher-Sharpe narrow one; parameter sweeps in the deployment's own frame showed
the higher-scoring cells were knife-edge and were rejected). Most of this was done
**in-sample**. A proper **walk-forward** — choose parameters on past data only,
score out-of-sample — *has now been run*: across ~7 anchored/rolling folds over a
~1.4-year blind span, the strategy retained an **efficiency ratio of 0.63–0.79** of
its in-sample ceiling, landed at **+6–8%/yr excess vs the basket, positive in every
fold**, and the blindly re-selected parameters clustered around the deployed choice.
That upgrades "the deployed parameters are robust" from a reasoned judgement toward a
tested one — but only within the single premium regime of item 2: it shows *not
overfit to the sample*, not *survives a premium deflation*.

## 7. Data and reproducibility

No vendor data is redistributed. The committed sample is **synthetic** and does not
reproduce the real figures — it reproduces the *method*. Exact reproduction needs
the real universe (withheld) and window, so a reader reproduces the method and
ballpark, not bit-exact numbers. Public sources exist for every input, but stitching
them into a clean, same-vintage panel is non-trivial and is left to the reader.

## 8. What is untested or unfinished

Stated plainly rather than implied away:

- Walk-forward / out-of-sample parameter validation **has now been run** (item 6); it
  retained ~0.63–0.79 of the in-sample edge and was positive in every fold, but is still
  confined to one premium regime.
- The live paper record is too short to draw conclusions from.
- Capacity λ uses tick-rule signing, not trade-level signing.
- Transaction costs are modelled (Corwin-Schultz + a ladder); they are not measured
  against a real fill log at scale.
- The scheduling/reliability layer is described in `docs/architecture.md` but the
  full production runner is not part of this repository.

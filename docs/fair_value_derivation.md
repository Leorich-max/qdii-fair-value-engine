# Fair value: QQQ, NAV vintage and currency alignment

This model estimates the economic value of a China-listed US-equity QDII ETF between published NAV observations. The current project uses QQQ, not NASDAQ-100 futures, for the underlying reference.

```text
FV(t) = NAV(D) × QQQ(t)/QQQ_reference(D)
               × USDCNH(t)/CFETS_parity(D)
```

`D` is the NAV valuation date, not its retrieval date. `QQQ_reference(D)` is the dividend-adjusted reference close for the corresponding US session. QQQ levels must be on a consistent share/corporate-action basis. The FX denominator is the CFETS central parity associated with the NAV valuation date.

The reconstruction is an approximation: fund tracking differences, cash, fees, FX conventions, quote availability and stale references can matter. A QQQ quote is not guaranteed to be current simply because the feed returns a number. The observed IOPV behaviour belongs to the feeds and funds studied; it is not a universal claim about every QDII product or vendor.

## What the 3.2 bp statistic measures

The historical daily check compares log NAV returns with the QQQ and parity-return mapping over 151 observations. Its residual standard deviation was 3.2 bp. This supports the reference-date/currency model in that sample. It is not a measurement of second-by-second ETF market price minus model value, nor independent evidence of trading profitability.

The public functions accept normalised reference levels and implement the multiplicative mechanics; synthetic notebook outputs differ from the historical study.

## Information availability

A NAV dated before a decision is not necessarily a NAV available at that decision. Store the valuation date, source and observation time, and check availability and vintage consistently across funds. Historical publication assumptions remain assumptions where point-in-time records are unavailable.

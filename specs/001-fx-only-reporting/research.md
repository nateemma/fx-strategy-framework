# Phase 0 Research: FX-Only Performance Reporting

**Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

Three unknowns had to be resolved before design: whether rebalance days are detectable from the
recorded history alone (FR-008 depends on it), how large the contamination actually is, and what
minimum sample makes a statistic honest.

---

## R1 — Rebalance days ARE detectable from the recorded history

**Decision**: Detect a contaminated observation as one where `stock_positions` exceeds the prevailing
ETF baseline, where the baseline is the mode of `stock_positions` over a trailing window.

**Rationale**: Every FX order creates a position that appears in the broker's position list from
execution until T+2 settlement — settled FX is cash, unsettled FX is a position. So on and just after
an FX rebalance, `stock_positions` = ETF holdings + unsettled FX orders.

Validated against the live history:

| Date | `stock_positions` | Event |
|---|---|---|
| 2026-08-02 … 08-09 | 13 | Quiet. 13 = basket 5 + ladder 6 + income 2. |
| 2026-08-12 | **20** | Rebalance placed **7 orders** (activity log). 13 + 7 = 20. ✓ |
| 2026-08-13 | **20** | Still unsettled. |
| 2026-08-14 | 13 | T+2 settled; back to ETF-only. ✓ |

The count matches the placed-order count exactly, on the one rebalance for which both records exist.
The signal is structural, not a heuristic.

**Alternatives considered and rejected**:

- **Jump in `fx_gross_base`.** Rejected: a rebalance is often a *rotation*. Gross exposure can be
  nearly unchanged while every leg is resized, so this misses real rebalances.
- **Change in `fx_legs`.** Rejected: only fires when a leg opens or closes. The 2026-08-12 rebalance
  resized seven existing legs; the leg count would not have moved.
- **Outlier detection on the P&L series** (drop unusually large daily moves). **Rejected on
  methodology grounds, not accuracy.** This would discard the tails of a strategy whose defining risk
  *is* fat left tails, biasing Sharpe upward — precisely the self-deception the project's evaluation
  discipline exists to prevent.
- **Parse the activity log.** Rejected: it is not versioned, so the correction could not be
  reproduced from a clone, and the report must work from recorded history alone (FR-011).
- **Write an explicit marker at rebalance time.** Deferred, not rejected. It is the most robust
  option and worth adding later, but it changes how snapshots are recorded, which this feature
  assumed unnecessary — and the detector above already works on existing data.

**Known limitation**: the baseline is ambiguous before the ETF sleeves stabilised. On 2026-07-17 the
count read 13 while no ETF sleeve existed yet — those 13 were unsettled FX legs from the initial
placement, and 13 later became the ETF baseline by coincidence. A trailing-window baseline resolves
this going forward; the earliest rows have no FX data anyway and are excluded regardless.

---

## R2 — Flow contamination is second-order, so exclusion is conservative

**Decision**: Still exclude contaminated observations per FR-008, but do not treat the correction as
load-bearing.

**Rationale**: The intuition that a rebalance injects flow equal to its turnover is **wrong for this
book**. The strategy is dollar-neutral by construction: target non-USD exposure sums to ~zero. A
rebalance redistributes among currencies but returns net exposure to ~zero, so the *net* flow is only
the residual non-neutrality — rounding, odd-lot skips, and min-order skips — not the gross turnover.

The live data confirms the book holds neutrality tightly:

```
fx_net_base   =        129
fx_gross_base =    996,532     →  net is 0.013% of gross
```

So `fx_net_base` is very nearly pure accumulated P&L, and the flow correction removes a small
residual. Excluding ~1 observation per month is cheap insurance rather than a critical adjustment.

**Consequence worth surfacing**: if `fx_net_base` is cumulative FX P&L since inception, then the FX
book has made **~+129 base in a month on ~1M gross** — essentially flat, against a walk-forward
expectation of ~3%/yr unlevered. Split: spot +970, carry accrual −841. This is exactly the question
the feature exists to answer, and it corroborates Backlog #4 (negative carry accrual). It is a
one-month sample and proves nothing yet; the report must not let it read as a verdict.

---

## R3 — Minimum sample for a statistic

**Decision**: Report raw cumulative P&L and its components from **2** FX observations; suppress
Sharpe, volatility, and annualised return until **20** daily FX observations.

**Rationale**: The existing whole-account report gates at 3 daily snapshots, which is too permissive
for a ratio statistic — an annualised Sharpe from 3 points is noise with a decimal point. Twenty
trading days is roughly one month, the natural cadence of this book, and the point at which a
volatility estimate stops being dominated by its own standard error. Below the threshold the useful
facts (P&L to date, carry vs spot) are still printed; only the ratios are withheld.

**Alternatives considered**: a confidence interval on Sharpe instead of a hard gate — more
informative but more machinery than a status report needs, and easy to add later; matching the
existing 3-point gate — rejected as actively misleading for ratios.

---

## R4 — Return basis and conventions

**Decision**: Per-period FX return = change in `fx_net_base` ÷ `fx_gross_base` at the start of the
period. Annualise on 252 trading days, matching the existing report.

**Rationale**: FR-009 fixes gross exposure as the base, so realised figures are quoted on the same
basis as the walk-forward expectation (the strategy's own capital at 1x gross). Using the *prior*
period's gross avoids dividing by a denominator the period's own P&L has already moved.

**Guards required**: gross exposure of zero (book fully closed) must yield no return rather than a
division error; and a gap in the daily curve must not have a multi-day move annualised as if it were
one day.

---

## Open items carried to implementation

1. The explicit rebalance marker (R1, deferred alternative) is the robust long-term fix. Worth a
   backlog entry once this feature lands.
2. Only one FX-bearing snapshot exists today, so end-to-end validation runs against constructed
   histories. The first meaningful live reading is several weeks out.

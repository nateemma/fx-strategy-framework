# FX Financing Spread — Findings (2026-08-16)

**Question (Backlog #3):** the deployed carry book accrues **−841 base** of interest. A carry strategy
exists to *earn* the interest differential. Why is it paying?

**Answer:** the account is paid far below benchmark on long currency balances while being charged at
or above benchmark on shorts. On a dollar-neutral book that spread is levied on both legs, and it is
large enough to invert the carry leg entirely.

**The caveat that governs everything below:** this is the **paper** account (DUQ218063), and
[`income-enhancements.md`](./income-enhancements.md) records that its cash interest is simulated.
This documents what the paper account does. It does **not** establish live IBKR economics.

---

## Method

For each currency leg, `accrued / balance = realised_rate × period`. The accrual period — time since
IBKR last posted interest to cash — is not observable from a single snapshot.

But **every currency in one snapshot shares the same period**. So dividing by each currency's
benchmark rate gives

```
(accrued / balance) / benchmark  =  (realised_rate / benchmark) × period
```

and if financing were at benchmark everywhere, every leg would show the *same* number — the period
itself. Divergence between currencies is a financing distortion, and the comparison is
**period-independent**. That is what makes the headline result robust to the one thing we cannot see.

Benchmark = FRED 3-month interbank (`IR3TIB01<CC>M156N`), which is exactly what the backtest's carry
signal uses (`forex/features/carry.py`). The comparison is against the model's own assumption.

Reproduce with `.venv/bin/python scripts/financing_report.py` (read-only; needs Gateway + `data_cache/`).

## Result

| | LONG median | SHORT median | Asymmetry |
|---|---|---|---|
| realised ÷ benchmark | **0.0121** | **0.0543** | **4.5×** |

If shorts are charged at roughly benchmark, the implied window is ~20 days — in which case **longs
earn about 22% of the benchmark rate** while shorts pay ~100% of it.

**Per-leg** (2026-08-16):

| ccy | side | USD exposure | accrued | benchmark | ratio |
|---|---|---|---|---|---|
| ZAR | LONG | 36,720 | **−2.60** | 7.11% | −0.0010 |
| NZD | LONG | 25,873 | **0.00** | 2.68% | 0.0000 |
| EUR | LONG | 109,156 | 9.09 | 2.03% | 0.0041 |
| HUF | LONG | 65,842 | 47.71 | 5.98% | 0.0121 |
| CAD | LONG | 85,940 | 23.67 | 2.27% | 0.0121 |
| NOK | LONG | 101,247 | 66.52 | 4.57% | 0.0144 |
| GBP | LONG | 73,974 | 73.74 | 3.71% | 0.0269 |
| CHF | SHORT | −98,589 | −38.84 | −0.04% | *excluded* |
| JPY | SHORT | −30,749 | +3.19 | 1.27% | −0.0081 |
| AUD | SHORT | −1,130 | −2.17 | 4.46% | 0.0430 |
| MXN | SHORT | −128,145 | −438.16 | 6.76% | 0.0506 |
| SEK | SHORT | −67,609 | −76.71 | 1.95% | 0.0581 |
| PLN | SHORT | −81,944 | −245.83 | 3.85% | 0.0779 |
| ILS | SHORT | −89,615 | −260.61 | 3.45% | 0.0844 |

Three legs make the pattern concrete without any arithmetic:

- **ZAR is long a 7.11% currency and accrues negative.** Holding the highest-yielding long in the
  book costs money.
- **NZD is long and accrues exactly zero** — a balance-threshold effect, not a rounding artifact.
- **CHF is short a currency with a *negative* benchmark rate and is still charged.** Borrowing a
  currency that pays −0.04% should earn; it costs 38.84.

## The drag

Benchmark carry on this book — what the backtest assumes it earns — is **+2,156/yr (+0.22% of
gross)**. Realised depends on the unobservable window:

| Assumed window | Realised | Gap vs backtest | as % of gross |
|---|---|---|---|
| 2 weeks | −21,926/yr | −24,082/yr | **−2.42%** |
| 3 weeks | −14,617/yr | −16,773/yr | **−1.68%** |
| 1 month | −10,232/yr | −12,388/yr | **−1.24%** |

So a **1.2–2.4%/yr** drag that no backtest in this program has ever charged.

## Why this matters

The walk-forward expectation for `carry_cot_mom` is **~3%/yr unlevered at ~2.6% vol (Sharpe 1.15)**.
A financing drag of 1.2–2.4%/yr removes **40–80% of that return** — and it is a *constant* cost, not
a volatility, so it comes almost entirely out of the Sharpe.

This is a different class of problem from execution cost. Trading cost is charged per rebalance and
the book already models it at 3–5bp. Financing is charged continuously on the whole gross position
for as long as it is held. A monthly-rebalanced book pays it every day.

It also cannot be diversified or overlaid away: it scales with gross exposure, which is exactly what
leverage increases. Levering the book to a 10% vol target multiplies the drag along with the return.

## What this does and does not establish

**Established:** the paper account's financing is asymmetric between long and short balances by ~4.5×
relative to benchmark, and that asymmetry is large enough to invert the book's carry.

**Not established:** that a funded account behaves the same way. Paper-account interest is simulated.
The direction is plausible — retail brokers genuinely do pay below and charge above benchmark — but
the *magnitude* here is not evidence about live economics.

**To confirm on a live account** you would need: a funded account holding a comparable book, one
month of daily `fx_accrued_base` recording spanning a posting, and the same ratio computation. The
recording is already in place (`scripts/snapshot_nav.py`), so the only missing input is a funded
account. Until then this is a flag, not a verdict.

**A cheaper partial check:** IBKR publishes its interest-rate schedule (benchmark ± tier spread) per
currency. Comparing the *published* long and short spreads against these measured ratios would show
whether the paper account is simulating the real schedule or something cruder. That is desk research,
not code, and it would materially raise or lower confidence before any funded test.

## Recommended follow-ups

1. **Do not re-baseline the strategy on this yet.** One paper snapshot is a flag. Treat the ~3%/yr
   expectation as intact-but-suspect until a live or published-schedule check lands.
2. **Check IBKR's published rate schedule** against these ratios (above) — cheapest way to raise
   confidence.
3. **Consider a financing term in the backtest.** If the drag survives checking, the honest model
   charges a per-currency spread on held balances, not just per-trade cost. That changes which books
   look deployable — a wider gross book gets penalised more, which may reorder the factor rankings.
4. **Watch the recorded series.** `fx_accrued_base` is now captured daily, so the accrual window
   becomes directly observable at the first posting event, collapsing the range in the drag table to
   a single number.

## Related

- `specs/002-financing-spread/` — spec, plan, tasks for this work.
- `forex/run/financing.py` — the measurement; `scripts/financing_report.py` — the diagnostic.
- Backlog #14 (explicit rebalance marker) would also make posting events unambiguous.

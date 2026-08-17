# FX Financing Spread — Findings (2026-08-16)

**Question (Backlog #3):** the deployed carry book accrues **−841 base** of interest. A carry strategy
exists to *earn* the interest differential. Why is it paying?

**Answer:** the account is paid far below benchmark on long currency balances while being charged at
or above benchmark on shorts. On a dollar-neutral book that spread is levied on both legs, and it is
large enough to invert the carry leg entirely.

**Confirmed against IBKR's published rate schedule (2026-08-16).** The initial measurement came from
the paper account, whose cash interest [`income-enhancements.md`](./income-enhancements.md) records as
simulated — so the first version of this document treated the result as a flag rather than a verdict.
It is now a verdict: the paper account reproduces IBKR's **published** tiers and benchmark rates
almost exactly, so the drag is contractual economics and not a simulation artifact. See
[Confirmation](#confirmation-against-the-published-schedule).

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

If shorts are charged at roughly benchmark, longs earn roughly a quarter of it. (The implied window is
confirmed below at ~13 days, from two independent sources.)

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

So a **1.2–2.4%/yr** drag that no backtest in this program has ever charged. The window ambiguity is
resolved in the next section, which replaces this range with a single figure derived from IBKR's
published rates: **−2.18% of gross per year**.

## Why this matters

The walk-forward expectation for `carry_cot_mom` is **~3%/yr unlevered at ~2.6% vol (Sharpe 1.15)**.
The confirmed drag of **2.18%/yr removes roughly three-quarters of that return** — and it is a
*constant* cost, not a volatility, so it comes almost entirely out of the Sharpe.

This is a different class of problem from execution cost. Trading cost is charged per rebalance and
the book already models it at 3–5bp. Financing is charged continuously on the whole gross position
for as long as it is held. A monthly-rebalanced book pays it every day.

It also cannot be diversified or overlaid away: it scales with gross exposure, which is exactly what
leverage increases. Levering the book to a 10% vol target multiplies the drag along with the return.

## Confirmation against the published schedule

The paper account's interest is simulated, so the measurement above could have been an artifact. It
is not. IBKR publishes its full schedule — a 0% tier on the first tranche of every currency, then
`BM − spread` on credit and `BM + spread` on debit, against its own Reference Benchmark Rates. Feeding
the actual balances through the **published** tiers predicts the **measured** accrual.

Sources (fetched 2026-08-16):
[interest rates](https://www.interactivebrokers.com/en/accounts/fees/pricing-interest-rates.php) ·
[margin rates](https://www.interactivebrokers.com/en/trading/margin-rates.php) ·
[benchmark rates](https://www.interactivebrokers.com/en/pricing/reference-benchmark-rates-int.php)

**The test.** Predicted annual interest per leg from the published schedule, divided into the measured
accrual, gives an implied accrual window. If the account follows the schedule, every leg implies the
*same* window. Splitting on whether the 2026-08-12 rebalance touched the leg:

| Group | Legs | Implied window | Spread |
|---|---|---|---|
| **Untouched by the rebalance** | AUD, GBP, HUF, ILS, MXN, NOK, SEK | **12.1 – 13.3 days** | **1.10×** |
| Traded on 2026-08-12 | CAD, CHF, EUR, JPY, PLN, ZAR | 2.0 – 16.1 days | 8.05× |

Every leg the rebalance left alone agrees to within 10% on a ~13-day window. That is the schedule
being implemented, not approximated.

The scatter in the traded group is expected and confirms rather than undermines the result: accrual
reflects the balance held *over* the window, but the prediction uses today's balance. EUR was bought
on 12 August, so it accrued on a much smaller balance for most of the window and implies a spuriously
short 2.0 days; JPY flipped from long to short and so shows the wrong sign. The four misfits are
exactly the four legs the rebalance moved most.

Two independent corroborations:

- **NZD publishes `0.000% (BM − 2.5%)`** — the credit spread exceeds the benchmark, and IBKR floors
  credit at zero. Measured accrual on the long NZD leg is **exactly 0.00**. The book holds a leg that
  is contractually guaranteed to earn nothing.
- **ILS publishes 0% credit on *all* balances**, and the debit side is `BM + 5%`. The strategy can
  only ever pay on ILS, never earn.

**The window is also independently pinned.** IBKR states interest "posts on a monthly basis on the
third business day of the following month". July's interest posted on Monday 3 August; the snapshot is
16 August. That is 13 days — matching the 12.1–13.3 implied from the schedule, from a completely
separate source.

### Restated with the schedule instead of an assumed window

Because the schedule is confirmed, the drag no longer needs a range. Computing directly from published
tiers and IBKR's own benchmark rates on the current book:

| | per year | % of gross |
|---|---|---|
| Carry at benchmark (what the backtest assumes) | **+2,138** | +0.21% |
| Carry under IBKR's published schedule | **−19,575** | **−1.96%** |
| **Financing spread cost** | **−21,712** | **−2.18%** |

## What this does and does not establish

**Established:** financing on this book costs **−2.18% of gross per year** relative to benchmark, and
that is enough to turn a **+0.21%** benchmark carry into a **−1.96%** realised one. The figure comes
from IBKR's *published* contractual rates, and the paper account reproduces them to within 10% across
every leg not disturbed by a recent trade. This is not a simulation artifact.

**Still not established:** that a *funded* account receives identical tiers. Credit tiering is
NAV-dependent (IBKR pays a reduced rate below USD 100,000 NAV; this book is ~1M, so full tier), and
debit spreads improve with size. The direction and rough magnitude are contractual; the exact number
for a real account of a given size would need re-deriving from the same published tables.

**Size dependence is real and works in your favour.** The 0% credit tranche is a fixed absolute amount
per currency, so it bites hardest on small books — ZAR's 150,000 threshold is 25% of the current ZAR
leg. Debit spreads also step down (USD `BM+1.5%` under 100k, `BM+0.75%` over 1M). A materially larger
book would see less drag, though not zero: the EM credit spreads (`BM−2%` to `BM−4%`) apply at every
tier.

## Recommended follow-ups

1. **Add a financing term to the backtest.** No longer conditional. The model charges 3–5bp per
   trade and nothing for holding, while the real cost is ~2%/yr on gross. Until that is modelled, every
   walk-forward number in this program overstates the deployable edge — including the 1.15 Sharpe the
   book was selected on.
2. **Expect the ranking to move.** A financing term penalises gross exposure, so it will hurt wide,
   diffuse books more than concentrated ones. The EM-inclusive universe was chosen partly *because*
   breadth improved cross-sectional selection; that trade-off now has a cost on the other side. The
   factor search was declared converged — this reopens the sizing question, not the factor question.
3. **Re-examine specific legs.** NZD (0% credit, contractually) and ILS (0% credit on all balances,
   `BM+5%` debit) can only ever cost. A universe filter that weighs a currency's *financing* terms
   alongside its rate differential is a cheap, concrete improvement.
4. **Watch the recorded series.** `fx_accrued_base` is captured daily now, so the next posting event
   (third business day of September) will confirm the window directly rather than by inference.

## Related

- `specs/002-financing-spread/` — spec, plan, tasks for this work.
- `forex/run/financing.py` — the measurement; `scripts/financing_report.py` — the diagnostic.
- Backlog #14 (explicit rebalance marker) would also make posting events unambiguous.

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


---

# Part 2 — Modelled in the backtest (2026-08-16)

Backlog #3 put the financing cost into the simulator
(`forex/backtest/financing.py`, spec `003-financing-in-backtest`) and re-ran the deployable book.

Run: `carry_cot_mom`, deliverable universe (G10 + MXN/ZAR/PLN/HUF/CZK/ILS), walk-forward 750/250,
5bp per-trade cost, 2015-10 → 2026-08.

| | Sharpe | ann return | vol | max DD | Calmar |
|---|---|---|---|---|---|
| Without financing | **1.15** | +3.03% | 2.64% | −2.94% | 1.03 |
| **With financing** | **0.17** | **+0.44%** | 2.64% | −6.87% | 0.06 |
| delta | **−0.98** | **−2.59%** | — | −3.93pp | — |

The unfinanced row reproduces the published figures exactly, which is the check that the flag is a
true no-op when off.

## The book does not clear its own financing cost

**Sharpe 1.15 → 0.17. Annual return +3.03% → +0.44%.**

Three things make this worse than it first looks:

1. **You cannot lever out of it.** The drag scales with gross exposure, and so does the return —
   Sharpe is scale-invariant. Targeting 10% vol multiplies both. A 0.17 Sharpe book is a 0.17 Sharpe
   book at any size.
2. **+0.44%/yr loses to cash.** SGOV yields ~4.3% for no risk and no work. The deployed cash sleeve
   (Backlog #5) would out-earn the FX strategy by roughly 10x.
3. **The drawdown more than doubles**, −2.94% → −6.87%, because a constant cost turns shallow
   drawdowns into long ones that no longer recover.

## Cross-check against the live account

| | of gross, per year |
|---|---|
| Modelled by the backtest | **−2.75%** |
| Independently measured on the live account | **−2.18%** |

Same direction, same order, ~26% apart. The gap is explained and is not a defect: the backtest reads
FRED interbank rates while the account is charged against IBKR's own benchmark, and FRED currently
runs higher for several currencies (NZD 2.68% vs 2.10%, NOK 4.57% vs 4.06%). A higher rate raises the
floored credit shortfall. Two independent routes to the same conclusion is the point; the second
decimal is not.

## What this does and does not kill

**It does not say the edge is fake.** In benchmark terms the book still earns +3.03%/yr at Sharpe
1.15 — the signal research stands, and the orthogonality conclusions in
`docs/strategy-research-backlog.md` are untouched. What it says is that **at IBKR retail financing
terms, a dollar-neutral FX carry book cannot keep what it earns.** The edge is real and someone
else's cost structure captures it.

**A different cost structure changes the answer.** Institutional prime-broker financing runs a small
fraction of retail spreads. The same book at, say, a quarter of these spreads would retain most of
its Sharpe. That is a real route, not a consolation — it just is not available at a retail account.

**Narrowing the universe is not the fix.** The obvious response is to drop the expensively-financed
legs. Tested:

| G10 only | Sharpe | ann return |
|---|---|---|
| Without financing | 0.33 | +0.86% |
| With financing | **−0.37** | **−0.96%** |

Dropping EM makes it *worse*, because EM is where the carry edge lives — the whole reason the
deliverable universe was broadened. The expensive legs and the profitable legs are the same legs.
Backlog item "filter the universe on financing terms" should be re-scoped or closed on this evidence.

## Recommendation

**Do not deploy `carry_cot_mom` with real money at IBKR retail terms.** The paper track can continue —
it costs nothing and now measures the right thing — but the live gate should stay shut on economics,
not just on caution.

Worth pursuing, in order:

1. **Price the alternative.** What financing terms would the book need to clear a Sharpe of ~0.8?
   Invert the model: it now runs both ways.
2. **Re-run the factor search with financing on.** Every comparison in the research arc was made
   without this cost. It penalises gross exposure, so it may reorder conclusions that were close —
   the vol-target overlay and the wide-universe choice are the obvious candidates.
3. **Reconsider what the account is for.** The ETF sleeves are financed completely differently
   (long-only, cash) and are unaffected by any of this. The diversified income book stands; it is the
   FX overlay specifically that does not pay for itself here.


---

# Part 3 — What terms would make it viable? (2026-08-16)

Backlog #3. Part 2 showed the book does not clear IBKR retail financing. This inverts the question:
what financing would it need? The model takes a schedule override, so the published spreads can be
scaled and the walk-forward re-run.

`carry_cot_mom`, deliverable universe, 750/250, 5bp. λ scales IBKR's published credit *and* debit
spreads; λ=0 is free financing, λ=1 is retail. "avg spread" is the mean all-in annual financing cost
across the book's legs.

| λ | avg spread | Sharpe | ann return | max DD |
|---|---|---|---|---|
| 0.00 | 0bp | 1.15 | +3.04% | −2.94% |
| 0.10 | 29bp | 1.04 | +2.76% | −3.00% |
| 0.20 | 58bp | 0.94 | +2.49% | −3.05% |
| **0.33** | **95bp** | **0.81** | **+2.14%** | — |
| 0.50 | 144bp | 0.65 | +1.71% | −4.25% |
| 0.75 | 216bp | 0.41 | +1.08% | −5.53% |
| **1.00** | **289bp** | **0.17** | **+0.46%** | −6.79% |

**The answer: about 95bp all-in — roughly one third of IBKR retail's 289bp — to clear a Sharpe of 0.8.**
At 50bp it runs Sharpe 0.97, essentially the unfinanced 1.15 minus a manageable haircut.

The relationship is close to linear, which is what you would expect from a constant cost on a
roughly constant gross exposure. There is no cliff to engineer around and no threshold effect to
exploit — every basis point of financing costs about 0.0034 of Sharpe.

## Two thirds of the cost is the borrowing side

| Which side is charged | avg spread | Sharpe | ann return |
|---|---|---|---|
| Both (retail) | 289bp | 0.17 | +0.46% |
| **Borrowing spread only** (paid full benchmark on longs) | 188bp | 0.55 | +1.46% |
| **Credit shortfall only** (borrow at benchmark) | 100bp | **0.76** | +2.02% |

Borrowing is **~65% of the total cost**. Fixing only that — borrowing at benchmark while still being
underpaid on long balances at retail terms — gets to **Sharpe 0.76**, near the 0.8 bar on its own.

That matters because the two sides are not equally negotiable. What a broker charges to lend you
money is the classic relationship lever; what it deigns to pay on your credit balances is usually
take-it-or-leave-it. **The expensive side is the negotiable side**, which is the most encouraging
thing in this analysis.

## A bigger IBKR account does not fix it

IBKR's debit spreads tier down with balance, so the obvious cheap move is to fund the account more.
It is not enough:

| USD debit tier | avg spread | Sharpe | ann return |
|---|---|---|---|
| BM+1.5% (tier 1, as modelled) | 289bp | 0.17 | +0.46% |
| BM+1.0% (>100k) | 264bp | 0.26 | +0.69% |
| BM+0.75% (>1M) | 251bp | 0.31 | +0.81% |

Even the best published USD tier leaves Sharpe at 0.31. The reason is that **EM debit spreads do not
tier at any plausible account size** — HUF's next tier begins at 4.5bn HUF (~$14M), CZK's at 400m CZK,
and both stay at BM+3% to BM+5% throughout. EM is where the carry lives, so the legs that cost the
most are precisely the ones size cannot help.

This also corrects an approximation flagged in Part 2: the model encodes tier-1 USD debit while the
deployed account is ~1M and would blend to roughly BM+1.1%. The correction is real but small, and the
conclusion survives it.

## What this means

**The strategy is viable at institutional financing and dead at retail.** That is a sharper statement
than "it does not work", and it points somewhere specific: the required ~95bp all-in is in the range
that a genuine prime-brokerage or institutional FX financing relationship prices at, and nowhere near
what a retail margin account offers.

Whether that is worth pursuing is a capital question, not a research one. Institutional financing
relationships carry minimums and operational overhead that a ~$1M account will not clear. **At current
capital the book is not deployable and no amount of strategy work changes that** — the constraint is
the financing relationship, not the signal.

Leverage does not rescue it and does not need to. The drag scales with gross and so does the return,
so Sharpe is invariant: at 50bp the book runs Sharpe 0.97, which levered to a 10% vol target is a
~10%/yr book. At retail's 0.17 the same leverage produces ~1.7%/yr at 10% vol — strictly worse than
cash, with all of the risk.

## Recommended position

1. **Do not deploy real money at retail terms.** Settled in Part 2, reinforced here.
2. **Do not spend more effort on the FX signal** while financing is the binding constraint. Improving
   Sharpe from 1.15 to 1.3 pre-financing moves the retail result from 0.17 to perhaps 0.3 — still
   nowhere. Backlog "re-run the factor search with financing on" is worth doing for *correctness of the
   record*, not because a better book is waiting to be found.
3. **Revisit if capital changes.** The number to remember is **95bp all-in**. If a financing
   relationship at or below that becomes available, the book becomes a Sharpe ~0.8 proposition and
   everything else in this repo is ready for it.
4. **The ETF sleeves are unaffected.** They are long-only and cash-financed. The diversified income
   book stands on its own; it is the FX overlay specifically that needs terms this account cannot get.

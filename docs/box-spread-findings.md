# Box-Spread Financing — Gate Findings (2026-08-19)

Backlog item: can borrowing via short SPX box spreads at roughly the risk-free rate, instead of IBKR
margin at BM+0.75–1.5%, rescue anything?

**Verdict: REJECT — it solves a problem this book does not have, and does not fix the one it does.**

---

## What a box spread is

A bull call spread plus a bear put spread at the same two strikes and expiry pays exactly
`(K₂ − K₁) × multiplier` at expiry, whatever the underlying does. Selling one is therefore a
synthetic fixed-rate loan: cash now, a known repayment later. On **European-style** index options
(SPX) there is no early-assignment risk, which is what made the 2021 retail losses on American-style
boxes possible.

Traders use them to borrow at close to the risk-free rate instead of broker margin.

## Test 1 — does it rescue the FX book? No

A box borrows **USD**. It cannot borrow HUF, MXN, PLN or ILS. So it can only replace the USD leg of
`carry_cot_mom`'s financing. Modelled by overriding the USD debit spread:

| USD borrowing | Sharpe | ann return |
|---|---|---|
| IBKR retail, BM+1.50% | 0.17 | +0.46% |
| IBKR >$1M tier, BM+0.75% | 0.31 | +0.81% |
| Box, BM+0.30% | 0.39 | +1.02% |
| Box, BM+0.10% | **0.42** | +1.11% |
| **Free USD (unreachable)** | **0.44** | +1.16% |

**The book needs ~0.80 to be viable.** Even *free* USD borrowing reaches only 0.44, because the cost
is dominated by the foreign legs — the credit shortfall on long HUF/ZAR/NOK balances and the BM+3% to
BM+5% debit on short MXN/PLN/HUF/ILS. A box touches none of that.

This confirms quantitatively what was previously only asserted: **box spreads do not revive FX carry.**

## Test 2 — does it make levering the ETF book attractive? No

| | ann | vol | Sharpe | maxDD |
|---|---|---|---|---|
| unlevered (1.0×) | +6.8% | 7.6% | **0.90** | −17.5% |
| 1.5× at IBKR margin | +7.3% | 11.4% | 0.68 | −26.5% |
| 1.5× at box rate | +7.8% | 11.4% | 0.71 | −26.3% |
| 2.0× at IBKR margin | +7.7% | 15.2% | 0.56 | −34.6% |
| 2.0× at box rate | +8.6% | 15.2% | 0.62 | −34.3% |
| 3.0× at box rate | +9.7% | 22.8% | 0.52 | −49.2% |

**Sharpe falls monotonically with leverage and drawdown roughly triples.** The basket earns ~6.8%
while borrowing costs 4.3–5.1%, so each additional unit of leverage buys ~2% of return for a full unit
of risk. Box financing makes a bad trade marginally less bad — it does not make it good.

## What it would actually save

The spread between IBKR margin and a box is about **0.80%/yr** on the borrowed amount:

| borrowed | saving |
|---|---|
| $100,000 | ~$800/yr |
| $300,000 | ~$2,400/yr |
| $600,000 | ~$4,800/yr |

Real money — but only if you want to borrow, and the analysis above says you should not.

## Why the book does not need it

- **ETF sleeves** are long-only and unlevered by design. Nothing borrowed.
- **The trend sleeve** uses futures, where leverage is already embedded in the basis at roughly the
  risk-free rate. A box would be redundant.
- **The FX book** borrows foreign currencies, which a box cannot supply.
- **The cash sleeve** is a lender, not a borrower.

Every place leverage appears in this book is either already cheaply financed or should not be levered
at all.

## When this would become relevant

Box financing earns its complexity only alongside **a high-Sharpe strategy in cash instruments that is
worth levering**. This book has no such thing: the highest-Sharpe cash strategy is the unlevered ETF
basket at 0.90, and levering it destroys that. If a genuinely high-Sharpe equity or ETF strategy ever
appears, revisit — the mechanism works, the economics just do not apply here yet.

## Not tested, because the economics rejected it first

- **The achievable rate.** ~risk-free + 10–30bp is assumed from general practice, not measured. IBKR
  returns no SPX option quotes without an options market-data subscription.
- **Margin treatment.** A short box is defined-risk and portfolio margin should treat it well;
  Reg-T may not. Unverified.
- **Execution and rolling.** Four legs traded as a combo, rolled at expiry, with spread cost on each
  round trip — a real operational burden that never got priced because the benefit was absent.

## Cost of this gate

An hour, no money, no code. It reused the financing model built for spec `003`, which is the second
time that model has answered a question it was not built for.

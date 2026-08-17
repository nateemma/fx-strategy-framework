# VIX Term-Structure Carry — Gate Findings (2026-08-17)

Backlog A1. Gated the way every prior idea was gated: cheap feasibility and signal checks **before**
any build.

**Verdict: CONDITIONAL PASS — as a small satellite sleeve (≤10%), not as a diversifying sleeve and
not as a standalone book.** The signal is real and robust; the instrument is financing-clean; but it
is equity crash risk wearing a different label, and the modern instrument has never been tested by
the tail that defines the strategy.

---

## 1. Data gate — passed, but not by the expected route

| Source | Result |
|---|---|
| CBOE free per-contract archive (`CFE_{month}{yy}_VX.csv`) | **Works, but stops mid-2018.** Unusable alone — this repo judges in the deployment regime. |
| IBKR historical VX futures | **Effectively unavailable.** 14 contracts are quotable, but the front month returns **7 daily bars** and CONTFUT returns 16 — the signature of no CFE market-data subscription. |
| FRED `VIXCLS` + `VXVCLS` (VIX, VIX3M) | **Free, current, long.** Gives the term-structure *signal*. |
| Yahoo `SVXY` / `VIXY` / `VXX` | **Free, current.** The ETPs are ordinary ETFs the account already trades through the existing execution path. |

So the strategy is testable **via ETPs**, not raw futures. That is a real simplification: no CFE
subscription, no contract rolling, and the existing `BasketExecution` engine already handles it.

> **Read-across to A2 (cross-asset managed futures):** IBKR will not backfill futures history without
> market-data subscriptions. A2 must plan on free continuous-futures data (Yahoo `=F`, as the earlier
> commodity gate used), not on the broker.

## 2. The signal is real

Contango — the front of the curve below the back — is not an occasional condition. It is the normal
state:

| Era | Days in contango | Mean depth (VIX3M/VIX − 1) |
|---|---|---|
| 2016–2019 | 91.5% | +14.7% |
| 2020–2022 | 90.7% | +11.9% |
| 2023–2026 | 94.7% | +12.5% |
| Full | 92.4% | +13.1% |

Gating a short-vol position on `VIX3M > VIX` (yesterday's curve, so causally clean) improves **every
era, on both instruments, in both Sharpe and drawdown**. It is one unoptimised rule, not a fitted
threshold — no parameter was searched.

## 3. But measure it on the instrument that exists today

SVXY changed from **−1x to −0.5x on 2018-02-28**, immediately after the blowup that terminated its
competitor XIV. Any test spanning that date is mixing two different instruments, which is why an
era-split flattered the result. Restricted to the current instrument:

| SVXY, 2018-03 onward | ann | vol | Sharpe | maxDD |
|---|---|---|---|---|
| always-on | +11.3% | 36.9% | 0.48 | −62.2% |
| **contango-gated** | **+15.1%** | 31.1% | **0.61** | **−34.2%** |

Sharpe **0.61**, not the 0.92 the naive era-split suggested. Still positive, still robust — but this
is not a standalone book by this program's standards (EM carry deployed at 0.68; the basket at 0.88).

## 4. It is not a diversifier

This is the finding that decides how it may be used.

| Correlation of gated short-vol to | |
|---|---|
| SPY | **+0.58** |
| DBC | +0.20 |
| GLD | +0.03 |
| IEF / TLT | −0.08 / −0.09 |
| The inverse-vol basket | +0.23 |

The +0.23 to the basket looks tolerable, but the average hides the structure — the correlation is
near zero in calm markets and strongly positive in crashes:

- On the basket's **20 worst days**, gated short-vol averages **−1.89%** and is positive **5%** of the
  time. The basket itself averages −1.74% on those days. **It loses slightly more than the thing it
  is supposed to diversify, on exactly the days that matter.**

This is the same conclusion the 2026-07 options-VRP assessment reached — "the vol premium *is* payment
for bearing crash risk; you can't collect it and avoid the tail" — arrived at independently, and now
quantified. Short-vol carry and put-writing are the same trade in different clothing.

For contrast, the FX carry sleeve's equity correlation is ~0.00–0.11, which is precisely why the
FX+basket combination worked. **Short-vol cannot fill that role.**

## 5. As a small satellite, it does improve the book

The fair test — does adding it help what already exists? (2018-03 onward, inverse-vol ETF basket.)

| | ann | Sharpe | maxDD | mean on basket's worst 20 days |
|---|---|---|---|---|
| basket alone | +6.6% | 0.88 | −17.6% | −1.74% |
| basket + 5% short-vol | +7.3% | 0.95 | −16.8% | −1.75% |
| **basket + 10% short-vol** | **+7.9%** | **0.97** | **−16.7%** | −1.76% |
| basket + 20% short-vol | +9.1% | 0.95 | −17.2% | −1.77% |

A 10% sleeve adds ~1.3%/yr and lifts Sharpe 0.88 → 0.97, with drawdown slightly *better*. That is a
genuine improvement, and it contradicts the rejection this analysis was heading toward.

But read the last column: the crash-day loss barely moves. **The improvement comes from return, not
from diversification.** It is return enhancement bolted onto equity beta, sized small enough that its
tail does not dominate.

## 6. Why it passes filter 5, unlike FX carry

Long SVXY is a **long-only cash ETF position**. No margin, no borrow, no per-currency credit/debit
spreads — so the ~2%/yr financing drag that destroyed `carry_cot_mom` does not apply at all.

That is exactly the property the universe survey predicted would matter, and it is the strongest
argument for this idea: a Sharpe-0.61 strategy you keep beats a Sharpe-1.15 strategy you don't.

## 7. The caveat that should govern any deployment

**The current instrument has never been tested by the event that defines the strategy.** SVXY at
−0.5x began on 2018-02-28 — *the week after* the blowup. The sample therefore starts immediately
after the tail event and excludes it. The prior instrument, at −1x, lost **83% in a single day**
(2018-02-06) and −95% peak-to-trough.

The contango gate would have been *out* for that specific day (the curve was already in backwardation,
−24.6%). But it was fully *in* for Brexit (2016-06-24, −26.4% in a day, prior-day contango +6.8%). So
the gate is a real improvement, **not** a reliable tail guard.

Sizing must be set by the tail the instrument has not yet seen, not by the 8.4 years of post-blowup
history that happen to be available.

## 8. Recommendation

1. **Do not build a standalone short-vol book.** Sharpe 0.61 with −34% drawdown does not clear the
   bar, and it is not the uncorrelated sleeve the book needs.
2. **A ≤10% satellite is defensible** and measurably improves the ETF track. If pursued, it belongs
   in the existing `BasketExecution` engine as a fifth sleeve — the plumbing already exists and the
   symbols stay disjoint.
3. **Size on the untested tail.** At 10% of the ETF book (~$100k) a repeat of a −1x-style event at
   −0.5x is roughly a −40% to −50% sleeve loss, i.e. ~4–5% of the book. That is survivable; 20%+ is
   not obviously so.
4. **Keep the contango gate.** It is free, unoptimised, and improves every era on both instruments.
   It is the reusable finding here even if the sleeve is never deployed.
5. **It does not replace the FX sleeve.** The book still lacks a genuinely equity-uncorrelated
   return source, and this is not one. That gap is what A2 (cross-asset managed futures) is for.

## Reproduce

Scratch scripts for this gate used FRED (`VIXCLS`, `VXVCLS`) and Yahoo daily adjusted closes for
SVXY/VIXY/SPY/TLT/IEF/GLD/DBC. Cost charged at 5bp on gate turnover. No broker connection needed
beyond the contract-availability probe.

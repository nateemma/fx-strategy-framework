# Standalone Long/Short Candidate Gates — Findings

**Spec `009-standalone-longshort-gates`. Completed 2026-10-15.**

Six candidates from [`investable-universe-survey.md`](./investable-universe-survey.md) §5 Tier A/B,
ranked in August 2026 and never gated. Each judged **standalone** — *would this be worth running on
its own capital?* — per Constitution 1.1.0's STANDALONE-FIRST rule, **not** by what it adds to the
ETF book. That distinction is why they were never gated: they were shelved under the lens the
constitution later corrected.

**No broker, no Gateway.** Every figure here comes from FRED and a free chart API. The paper track
has been stopped since 2026-10-14 and nothing in this work reconnects to it; a test
(`tests/test_no_broker.py`) asserts no module here can.

**The bar is comparative**: beat a named simpler alternative, net of cost and financing, in **two**
temporally distant eras. This repo's own history is why — the momentum basket died by losing to
equal-weight of its own names, RSP died by losing to SPY; neither by missing a threshold.

---

## Verdicts

| ID | Candidate | Verdict | Why |
|---|---|---|---|
| **A3** | Treasury curve 2s10s | **REJECT** | Gross Sharpe **+0.21** over 24 years — flat *before* any cost. Loses to cash in both eras. Reversed signal also negative |
| **B5** | TIPS breakeven | **REJECT** | Gross Sharpe **+0.28** (+1.06%/yr) does not survive 0.78%/yr turnover and 1.5%/yr financing. Loses to cash in both eras |
| **B4** | Equity-index futures basis | **REJECT — economics** | The basis prices financing at ≈ risk-free; retail borrows at benchmark **+1.5%**. Structurally negative, no history required |
| **B6** | Credit spread | **DEAD — data** | Free HY/IG spread history is a rolling **~3 years** (licence-limited). Cannot span two eras at any price |
| **B2** | CEF discount reversion | **DEAD — data** | Per-fund NAV history exists in neither free source |
| **B3** | Post-earnings drift | **DEAD — data** | Bulk earnings dates and surprise magnitudes exist in neither free source |

**Nothing passed.** Two were tested and lost; one is arithmetic; three cannot be tested free at all.
Four of the six closed in hours, which is what the spec predicted (SC-007) and what made six
candidates affordable.

### A note on how generously these were costed

Financing is charged as a **flat 1.5%/yr** — IBKR's published tier-1 USD debit spread — rather than
scaled by gross exposure, and **short-leg borrow cost is excluded entirely** because this repo holds
no equity-borrow data and inventing a constant would be a made-up number driving a verdict. Both
simplifications make the candidates look **better** than reality. A3 and B5 lose anyway, which is the
strongest form of rejection: they fail on costs that are understated.

That is also why neither could have *passed* here. An uncostable short leg caps a verdict at
`inconclusive` by a rule in `forex/backtest/gate.py` rather than a note someone has to remember.
Rejection is available on this evidence; acceptance was never going to be.

---

## A3 — Treasury curve 2s10s · **REJECT**

**Hypothesis**: the 2s10s slope is a slow, non-price-predictive signal, and a duration-neutral
steepener/flattener held in futures is financing-efficient.

**This was the best-placed of the six** and the one recommended first: a genuine two-leg long/short,
free and decades-deep signal data, financing-efficient in its deployment instrument, carry-shaped
rather than a price forecast. It is dead anyway.

**Construction**: signal is the slope's z-score against its own trailing 250-day window, clipped to
[−1, +1], no value until the window fills, positions lagged one day. Legs are **duration-neutral,
not dollar-neutral** — equal dollars in a 2-year and a 10-year instrument is a large net duration
bet with two legs, whose P&L is dominated by the level of rates rather than the slope. Screened SHY
(duration 1.9) against IEF (7.4), adjusted closes.

**6,045 aligned days, 2002-07-30 → 2026-10-13** (24.2 years). Era split `holdout_years=12`, chosen
as the midpoint of available history rather than the underlying default of 3, which would have split
24 years 3-versus-21.

| Era | From | To | Days | Sharpe net | Ann return | Max DD | Beats cash? |
|---|---|---|---|---|---|---|---|
| distant | 2003-07-30 | 2015-07-29 | 2998 | **−1.45** | −1.56% | −17.01% | No |
| recent | 2015-07-30 | 2026-10-13 | 2797 | **−1.73** | −1.59% | −16.29% | No |

### Why it fails — the part worth keeping

The interesting number is not the net one:

| | /yr |
|---|---|
| Gross return (no cost, no financing) | **+0.21%** (Sharpe +0.21) |
| Turnover cost (14.95 units/yr at 2bps) | −0.30% |
| Financing (flat 1.5%) | −1.50% |
| **Net** | **−1.59%** |

**Cost did not kill this candidate — there was nothing to kill.** That matters: a candidate killed by
cost might be revived by cheaper execution or a futures implementation, whereas a flat gross signal
will not be rescued by anything on the cost side.

And the obvious follow-up is closed: **reversing the signal is also negative** (gross Sharpe −0.22,
ann −0.22%). It is not a sign error. The 2s10s z-score carries no exploitable information about the
SHY/IEF spread return in either direction, over 24 years, in both halves.

**Closed**: the 2s10s z-score for a duration-neutral curve trade, screened in ETFs.
**Not closed, honestly**: the survey ranked A3 for *futures* deployment, and the A2 gate found
cross-asset trend "viable only in futures". A flat *gross* signal is construction-independent in a
way a cost failure would not be, so a futures version is very unlikely to differ — but it was not
tested, because IBKR retains ~2 years of micro history and a stitched series needs Databento.
Recorded as **rejected on signal, not on implementation**.

---

## B5 — TIPS breakeven · **REJECT**

**Hypothesis**: inflation expectations are slow and macro-driven, so a TIPS-versus-nominal spread is
a carry-like position rather than a price prediction.

**Construction**: z-score of the 10-year breakeven (`T10YIE`) on a 250-day trailing window drives a
dollar-neutral long TIP / short IEF pair, positions lagged one day.

**5,708 aligned days, 2003-12-05 → 2026-10-14** (22.9 years). Era split `holdout_years=11`.

| Era | From | To | Days | Sharpe net | Ann return | Max DD | Beats cash? |
|---|---|---|---|---|---|---|---|
| distant | 2004-12-07 | 2015-12-04 | 2748 | **−0.22** | −0.89% | −16.31% | No |
| recent | 2015-12-07 | 2026-10-14 | 2710 | **−0.42** | −1.55% | −22.44% | No |

### Why it fails — a different failure from A3, and the more interesting one

| | /yr |
|---|---|
| Gross return | **+1.06%** (Sharpe +0.28) |
| Turnover cost (39.05 units/yr at 2bps) | −0.78% |
| Financing (flat 1.5%) | −1.50% |
| **Net** | **≈ −1.2%** |

Unlike A3, **B5 has a real if thin gross edge — and the cost base eats it twice over.** Turnover is
2.6× A3's because the breakeven z-score flips more often, so the signal is not as slow as the
hypothesis assumed. It is a cost failure rather than a signal failure, which means in principle it
is the one candidate here that cheaper execution could revive.

It would need to get *much* cheaper. The gross edge is 1.06%/yr against 2.28%/yr of charges, so
execution and financing would both have to roughly halve — and the 1.5%/yr figure already excludes
short borrow, which would make the real hurdle higher, not lower. For a **+0.28 gross Sharpe**, that
is not a project worth starting.

---

## B4 — Equity-index futures basis · **REJECT (economics)**

**Hypothesis**: the spread between index futures and spot is harvestable and capital-efficient.

Killed on arithmetic in under an hour, without a model — which is what the kill criteria are for.

Measured `ES=F` against **`^GSPC`, the index itself**: median basis **−1bp** over 2000-09-18 →
2026-10-15 (6,556 days), **+16bp** since 2020. As a front-month spread at blended time-to-expiry
that is roughly one quarter's carry, so on the order of 60bp/yr.

Cash-and-carry harvests the gap between the financing rate **implied by the basis** and the rate you
**actually borrow at**. The basis is set by institutions funding near the risk-free rate; retail
borrows at benchmark **+1.5%**. So the retail version is structurally short roughly 150bp/yr before
commission. **No length of history changes that** — it is the same class of finding as the
contract-granularity arithmetic in the original survey.

> **A measurement error worth recording.** The first run of this probe compared `ES=F` to `SPY × 10`
> and reported a "+2416bp basis". That is not a basis — SPY pays its dividends out, so `SPY × 10`
> drifts ~24% below the index over two decades, and the number was measuring cumulative dividend
> drift. The verdict was unaffected (it rests on the financing argument, not the measurement), but
> the number was nonsense and would have gone into the record. Fixed to use the index itself. The
> proxy was the error, not the data.

---

## B6 — Credit spread · **DEAD ON DATA**

**Hypothesis**: the credit risk premium is harvestable long credit / short duration.

This is the candidate whose *original* gate asked **"does it add anything the basket does not
already have?"** — the portfolio-contribution question spec 009 exists to replace. So it was finally
asked to stand on its own, and it could not be asked at all.

The ETF legs are deep (HYG from 2007-04-11, 4,911 days). **The signal is the blocker.** FRED serves
the ICE BofA spread indices under a rolling licence window:

| Series | Obs | From |
|---|---|---|
| `BAMLH0A0HYM2` (high yield OAS) | 786 | **2023-10-16** |
| `BAMLC0A0CM` (investment grade OAS) | 785 | **2023-10-16** |
| `T10YIE` (breakeven, for contrast) | 5,950 | 2003-01-02 |
| `DGS2` (2-year yield, for contrast) | 12,588 | 1976-06-01 |

Two ICE BofA series starting on the *same* date while Treasury series go back decades is a licence
window, not an outage. **Three years cannot produce two temporally distant eras**, so FR-004 cannot
be satisfied at any level of modelling effort.

> **This one slipped through the cull and was caught by its own gate.** The feasibility probe
> originally checked only that a signal series *loaded*, not that it was deep enough, so B6 passed as
> `testable` and then returned from its gate with one usable window. The probe now checks signal
> depth, so the next candidate cannot slip the same way. Had the gate not enforced "two windows or
> inconclusive", this would have been reported as a one-era result instead of a data failure.

**To revisit**: a paid credit-spread history, or a construction whose signal comes from the ETFs
themselves. The latter would be a price-momentum signal rather than a macro spread — a different
idea, and one whose shape this repo has already rejected repeatedly.

---

## B2 — CEF discount mean-reversion · **DEAD ON DATA**

**Hypothesis**: closed-end funds trade at persistent, mean-reverting discounts to NAV; long-only,
cash-financed, low turnover — which would have dodged the short-borrow problem entirely.

Prices are free. **Per-fund NAV history is the binding input and it is not.** FRED carries macro
series only; the chart API returns prices with no NAV field. Obtaining it means a paid vendor or
scraping a site with no bulk history — a data-acquisition project, not an afternoon.

Worth noting what was lost: this was the only candidate that was both long-only *and* plausibly
uncorrelated, i.e. the one whose shape best fitted the account. It failed on plumbing rather than on
merit, which is a weaker form of closure than A3's.

---

## B3 — Post-earnings-announcement drift · **DEAD ON DATA**

**Hypothesis**: the most-replicated equity anomaly — prices drift in the direction of an earnings
surprise. Long-only implementable.

Same shape of failure as B2: **bulk earnings dates and surprise magnitudes** are in neither free
source. Also closed on plumbing rather than merit.

Had it been testable, the mandatory first comparison was equal-weight buy-and-hold of the same
names — the null that killed the momentum basket, where every lookback lost to passively holding the
identical universe.

---

## What this leaves

**Nothing to deploy, and the three macro spreads that could be tested all point the same way**: a
thin or absent gross edge against a retail cost base of roughly 2.3%/yr. That is the same wall the FX
book hit, reached from a different direction — and it is worth being explicit that the wall is the
*cost base*, not the ideas. Two of the three had a positive gross number.

The three data failures are more interesting than they look. None of them is "the idea is wrong";
all three are "the free-data tier does not reach". B2 and B3 in particular were the two long-only
candidates — the shape that actually suits unlevered retail capital — and both died on plumbing. If
this programme is ever restarted, **the highest-value purchase is not a better model or a better
broker; it is data**: credit-spread history, CEF NAV history, earnings-surprise history, and the
Databento futures series that already blocks the trend sleeve and commodity carry.

Method notes: era splits were chosen per candidate as the midpoint of available history, recorded
above; all figures are net of 2bps turnover and flat 1.5%/yr financing with short borrow excluded;
every verdict reproduces from the local cache with no network access.

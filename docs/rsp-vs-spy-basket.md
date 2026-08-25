# Gate — should the basket's equity leg be equal-weight (RSP) instead of cap-weight (SPY)? (2026-08-25)

**Verdict: no. Keep SPY.** The swap is a null (basket correlation **0.993**), slightly worse full-sample,
and costs 11bp/yr more in fees. The question arose from a survivorship-inflated observation that is
corrected below.

## Where the question came from

While testing momentum rotation over the 2000–2009 "lost decade", equal-weighting a hand-assembled
universe of 67 large caps returned **+11.0%/yr against SPY's −1.0%**, suggesting cap-weighting — not
equity — was what delivered nothing in the 2000s. If true, the basket's equity leg was the wrong index.

**That observation was inflated ~4× by my own survivorship bias.** The 67 names were selected for still
trading in 2026. The real, tradeable equal-weight fund (RSP, live since 2003-05, no backfill) shows a much
smaller effect:

| era | SPY ann / Sharpe | RSP ann / Sharpe |
|---|---|---|
| 2003–2009 | 5.0% / 0.33 | **8.2% / 0.45** |
| 2010–2015 | 12.9% / **0.85** | 13.4% / 0.82 |
| 2016–2020 | **15.1% / 0.84** | 12.7% / 0.69 |
| 2021–2026 | **15.1% / 0.92** | 12.1% / 0.80 |
| **full 2003–2026** | **11.6% / 0.68** | 11.4% / 0.65 |

The equal-weight premium was real in the 2000s at **+3.2pp/yr, not +12pp**, and has been absent-to-negative
since 2016 (the megacap era). Over 23 years the two are a wash, marginally favouring SPY.

## The basket test

Deployed construction, unchanged: quarterly-rebalanced inverse-60d-vol across five ETFs, long-only,
cash-financed, 5bp/turn, 2006-05 → 2026-08 (DBC constrains the start).

| era | SPY leg | RSP leg |
|---|---|---|
| **full** | 6.06% / **0.87** / −18.42% | 5.79% / 0.83 / −18.58% |
| 2006–2015 | 6.11% / 0.89 | 6.12% / 0.88 |
| 2016–2026 | 6.01% / **0.85** | 5.48% / 0.78 |
| GFC 2007–09 | 8.70% / 1.04 | 8.88% / **1.05** |
| 2020 COVID | 7.86% / **0.90** | 7.02% / 0.81 |
| 2022 | −11.76% / −1.06 | −10.80% / **−0.95** |
| 2025–2026 | 13.72% / 1.95 | 13.71% / 1.96 |

**Basket correlation SPY-leg vs RSP-leg: 0.993.** They are the same portfolio.

## Why the equity-level difference does not reach the basket

Inverse-vol weighting deliberately holds the *least* of the most volatile asset. Mean weights and risk
shares in the deployed sleeve:

| leg | weight | risk share |
|---|---|---|
| SPY | 16.1% | 20.0% |
| TLT | 17.5% | 20.0% |
| IEF | **37.7%** | 20.0% |
| GLD | 14.9% | 20.0% |
| DBC | 13.8% | 20.0% |

The equity leg carries **one fifth of the risk by construction**. Any equity-index choice is diluted 5:1
before it reaches the portfolio — which is the point of risk parity, and also why this question could not
have had a large answer.

## Reasons to keep SPY

1. **No measured gain.** Slightly worse full-sample, in-basket and standalone.
2. **Certain cost.** RSP charges 0.20% vs SPY 0.09% — 11bp/yr of guaranteed drag.
3. **It would be a timing bet.** The EW premium is regime-dependent (strong 2003–09, negative 2016–26), so
   switching is really a bet that market concentration reverses. This repo's recorded law is
   *"always-on beats timed"* — static exposure beat timing three separate times.
4. **It means a real trade** on a deployed sleeve for a third-decimal difference.

The honest case *for* RSP is that it was better in both stress windows (GFC 1.05 vs 1.04; 2022 −0.95 vs
−1.06). Real, but small, on a leg carrying 20% of risk, and paid for with 11bp/yr.

## What would reopen this

A structural view that index concentration is set to unwind. That is a macro call, not a systematic
signal, and it is not what this framework is for.

## Reproduction

`scratchpad/fetch_rsp.py`, `rsp_basket.py`. Data: Yahoo chart API, free.

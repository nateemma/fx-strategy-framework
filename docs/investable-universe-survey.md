# Investable Universe — Systematic Strategy Survey (2026-08-17)

The repo began as a yen-carry / FX investigation, grew a multi-sleeve ETF track, and now drives a
general guarded execution engine against an IBKR account. This is a deliberate step back: **what can
this account actually trade, and what is worth investigating in each of those, given everything the
program has already learned?**

Everything already investigated is included, with what was found. Shorting and leverage are permitted.

---

## 1. The filters

Five gates, in the order they kill things. The first four are this program's established method; the
fifth is new as of 2026-08-16 and re-ranks much of what came before.

1. **Free data, or it doesn't get built.** Every factor and the NLP idea were gated by a cheap
   feasibility check before any implementation. Paid-data ideas are recorded, not started.
2. **Judged in the deployment regime, era-split.** Full-history averages hide regimes that are
   structurally extinct. An edge must appear in ≥2 temporally distant windows.
3. **Cost- and liquidity-aware, always.** Gross-of-cost Sharpe is not evidence. Most intraday FX died
   here.
4. **Additive only if orthogonal.** Carry is the dominant axis in FX; correlated factors are it in
   disguise and dilute the book.
5. **🆕 Financing-aware.** Holding a position at IBKR retail costs ~2%/yr of gross exposure — paid
   below benchmark on longs, charged above it on shorts. This is charged *continuously*, not per
   trade, and it scales with leverage. It is what killed the deployable FX book
   ([`financing-spread-findings.md`](./financing-spread-findings.md)).

**Filter 5 is the important one for this survey.** It does not just penalise strategies uniformly — it
changes their *ranking*, because different instruments finance leverage in completely different ways.

---

## 2. The structural insight: where leverage is cheap

| How you get leverage | What it costs | Verdict |
|---|---|---|
| **Margin on cash positions** (stocks, ETFs, FX spot) | benchmark **+1.5% to +5%**, charged daily on gross | The trap. This is what killed FX carry. |
| **Futures** | leverage is embedded in the contract; the basis prices it at ~risk-free | **Structurally cheaper.** A levered futures position pays roughly the risk-free rate, not retail margin. |
| **Options** | premium embeds financing at ~risk-free; defined-risk positions need little capital | Cheap, but you buy convexity you may not want. |
| **Box spreads** (European index options, e.g. SPX) | synthetic zero-coupon loan at ≈ risk-free + a few bp | A direct attack on the constraint — borrow cheaply, deploy in cash instruments. |
| **Not levering at all** | nothing | Always available. The ETF sleeves live here. |

**The conclusion that should shape the next year of work:** at retail terms, prefer instruments with
*embedded* leverage over margin-financed cash positions. A strategy needing 3× gross is close to
unviable on margin and perfectly ordinary in futures.

This is also why the ETF sleeves are unaffected by the financing finding — they are long-only and cash
financed — while the FX book was destroyed by it.

---

## 3. What the account can actually trade

Confirmed against IBKR's own pricing pages, 2026-08-17.

| Asset class | Shortable | Leverage | Repo status |
|---|---|---|---|
| **Stocks / ETFs** (global) | Yes (borrow permitting) | Margin (expensive) | **Deployed** — 4 sleeves |
| **Options** (equity, index, futures) | Yes | Embedded / defined-risk | Partly assessed |
| **Futures** incl. micro/nano | Yes, natively | Embedded, ~risk-free | Partly assessed |
| **Spot FX + metals** | Yes, natively | Margin (expensive) | **Exhausted** |
| **Bonds** (Treasury, corp, muni) | Hard | Margin | **Deployed** — ladder |
| **Cryptocurrency** + nano perps | Perps only | Embedded (perps) | Closed negative |
| **Prediction markets** (ForecastEx) | Yes (both sides) | N/A — fully collateralised | **Never investigated** |
| **Mutual funds** | No | No | Not relevant |

---

## 4. Already investigated

### FX — exhausted, and now known to be financing-blocked

| Strategy | Finding |
|---|---|
| G10 carry | Real pre-2010, **dead since** — ZIRP compressed the differentials. Sharpe 0.82 → 0.07 → 0.006 by era. |
| EM carry (MXN/ZAR/PLN/HUF/CZK/ILS) | **Revived the modern edge.** 2018–26 Sharpe 0.68 vs 0.27 G10-only. |
| COT positioning (contrarian) | **Real, and the first non-price edge.** Modern Sharpe ~0.7, corr 0.09 to carry. |
| Carry-momentum (12m Δ differential) | **Additive**, corr 0.03 to carry. |
| `carry_cot_mom` (the blend) | WF Sharpe 1.15 — **and 0.17 after retail financing.** Viable only at ~95bp all-in. |
| Value / REER | Rejected — carry-redundant (0.39 corr to COT), dilutes modern Sharpe. |
| Yield-curve slope, skewness | Rejected — carry-redundant. |
| Regime conditioning | Rejected — de-risking cuts carry's best periods. |
| Central-bank NLP | Rejected — anticipated policy is already priced. |
| Learned vol forecasters (HAR, cross-asset, GBM) | **All lose to a one-parameter EWMA.** Always-on beats timed. |
| Trend as a carry-crash hedge | Real convexity, but the *static* blend captures it; the timed overlay loses. |
| All intraday (strength, vol-spike reversion, cointegration, breakout) | **Closed.** Every mechanism is sub-spread on liquid majors. |

### Other asset classes already gated

| Track | Finding |
|---|---|
| Crypto spot | No better than the prior freqtrade work; the old edge lived in illiquid alts absent here. |
| Crypto nano-perp funding | Real gross, **cost-dominated**, negative 2023–26. |
| Commodity trend + COT | Real historically, **decayed to flat/negative post-2018**. |
| Commodity carry (roll yield) | **Untestable on free data** — roll gaps *are* the signal with flipped sign. Needs paid roll-adjusted data. |
| Options VRP (put-write / buy-write) | ~7%/yr but **−40% drawdown, 0.85 equity correlation.** Equity-lite, not low-risk. |
| Risk-parity ETF basket | **PASS → deployed.** ~6–7%/yr, Sharpe 0.8, −21% DD, 0.48 equity corr. |
| Cross-asset trend (ETF proxies) | ~0% modern, −32% COVID whipsaw. |
| Equity style factors | Premia decayed; combo Sharpe 1.0 → 0.05. |
| Momentum rotation | Works (~6–7%) but does not beat the basket; frequent rebalancing *hurts* on liquid ETFs. |
| Securities lending (SYEP) | Net-negative here — general-collateral holdings, and PIL destroys qualified-dividend treatment. |
| **FX + basket combination** | **The actual answer so far:** two uncorrelated sleeves → ~10% CAGR at −8% DD, Sharpe ~1.5. Now weakened by the FX leg's financing problem. |

**The pattern across all of it:** every *directional price-prediction* idea died; everything that
survived was either cross-sectional and slow, non-price (COT), or diversification rather than alpha.

---

## 5. Candidates not yet investigated

Priority weighs edge plausibility × data availability × **financing efficiency**.

### Tier A — high priority, financing-efficient, plausibly free data

| # | Strategy | Why it's interesting | Data | Risk |
|---|---|---|---|---|
| **A1** | **VIX futures term-structure carry** | ⚠️ **GATED 2026-08-17 — conditional pass.** Signal real (contango 92% of days) and financing-clean, but +0.58 to SPY and it loses on the book's worst days: return enhancement, not diversification. ≤10% satellite at most. [`vix-carry-findings.md`](./vix-carry-findings.md) | FRED + ETPs (CBOE's free archive stops 2018; IBKR needs a CFE subscription) | Current instrument has never seen the tail that defines the strategy. |
| **A2** | **Cross-asset managed futures** | ✅ **GATED 2026-08-17 — PASS.** See [`cross-asset-trend-findings.md`](./cross-asset-trend-findings.md). *(This row originally claimed only the commodity leg had been tested. That was wrong — cross-asset TSMOM was tested in 2026-07 and failed on return while recording equity correlation −0.03. The re-test showed the failure was construction, not signal.)* | Free (ETF proxies used; futures data is the open problem) | Viable **only** in futures — every ETF implementation loses to cash. |
| **A3** | **Treasury futures curve trades** | 2s10s steepeners/flatteners are capital-efficient in futures, uncorrelated to both equity and FX carry, and the yield curve is a slow, non-price-prediction signal — the shape that has worked here. | Free (FRED + CME) | Duration-mismatch sizing is fiddly. |
| **A4** | **Box-spread financing** | Not a strategy — an *enabler*. Borrow at ≈ risk-free via SPX box spreads instead of margin at BM+1.5%. Directly attacks the constraint that killed the FX book, for any cash-instrument leverage. | Free (option chains) | European-style only; execution and roll risk; does **not** fix per-currency FX spreads. |

### Tier B — plausible, needs a data gate first

| # | Strategy | Why | Gate to run first |
|---|---|---|---|
| **B1** | Prediction markets (ForecastEx) | Genuinely novel, fully collateralised (no financing drag at all), and IBKR pays interest on the collateral. Systematic mispricing in event contracts is well documented in the literature. | Is there enough historical contract data to backtest anything? Likely the binding question. |
| **B2** | Closed-end fund discount mean-reversion | CEFs trade at persistent, mean-reverting discounts to NAV. Long-only, cash-financed, low turnover — everything filter 5 favours. | Is historical discount/NAV data obtainable free? |
| **B3** | Post-earnings-announcement drift | The most-replicated equity anomaly. Long-only implementable; modest turnover. | Needs earnings dates + surprise history. IBKR has fundamentals; is it extractable in bulk? |
| **B4** | Equity-index futures basis / cash-and-carry | Harvest the spread between index futures and spot. Very capital-efficient. | Is the basis wide enough net of commission at retail scale? Probably thin — cheap to check. |
| **B5** | TIPS breakeven trades | Inflation expectations are slow-moving and macro-driven — the right shape. | Liquidity of TIPS at retail; futures alternative? |
| **B6** | Corporate/credit spread capture via ETFs | LQD/HYG vs Treasuries; credit premium is real but equity-correlated. | Does it add anything the basket does not already have? Check correlation first. |

### Tier C — recorded, blocked or low expectation

| # | Strategy | Blocker |
|---|---|---|
| C1 | Commodity carry (roll yield) | Paid data (Norgate/Databento). The one commodity signal not yet falsified. |
| C2 | Macro-surprise nowcasting | Needs a consensus feed. |
| C3 | FX options VRP | IBKR FX-options history too thin to backtest. |
| C4 | Order-flow signals | No retail source. Genuine predictive content, permanently blocked. |
| C5 | Dispersion (index vs single-name vol) | Capital-intensive, many legs, commission-heavy at retail. |
| C6 | 0DTE systematic | No credible free history; path-dependent; the tail is the whole story. |
| C7 | Merger arbitrage | Deal data not free. Also capital-hungry and financing-sensitive. |
| C8 | Tax-loss harvesting | Not a return strategy but real after-tax value. Depends on account tax status — an accounting question, not a research one. |

---

## 6. Recommended sequence

1. **A1, VIX term-structure carry.** Best combination of documented edge, free data, and financing
   efficiency. It is the closest analogue to what already worked here — a slow carry harvested from a
   structural premium — but in an instrument where leverage is not punitively priced.
2. **A2, cross-asset managed futures.** The most likely source of a *second uncorrelated sleeve*, which
   is the mechanism that produced this program's best result. The commodity-only test that failed does
   not settle the cross-asset case.
3. **A4, box spreads.** Cheap to evaluate, and if it works it changes the economics of every
   cash-instrument strategy in the repo.
4. **B1, prediction markets** — but as a *data feasibility spike only*, an afternoon, not a build. It
   is the only genuinely unexplored asset class, and fully-collateralised contracts are immune to the
   financing problem.

**What I would not do next:** re-run the FX factor search. It is already downgraded, and this survey
reinforces why — the constraint is the financing relationship, not the signal, and no FX-side
improvement large enough to matter is plausible.

## Caveats on this document

- Data-availability claims in Tier A/B are **expectations, not verified facts.** Each needs the same
  cheap feasibility gate every prior idea got — that discipline is why the backlog is honest.
- Prior-probability judgements here are informed by this program's own results, which are a small
  sample of one operator's work. They are a sequencing aid, not evidence.
- The financing figure (~2%/yr of gross) is measured for the FX book's specific composition. Other
  strategies will carry different gross exposure and therefore different drag; it is a lens, not a
  constant.

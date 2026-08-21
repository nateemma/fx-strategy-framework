---
name: project_equity_ls_gated_negative
description: "Equity cross-sectional long/short (factor-ETFs AND stock momentum) gated NEGATIVE — factors dead/cost-dominated. Don't re-run. Shorting works on IBKR; just not for these."
metadata: 
  node_type: memory
  type: project
  originSessionId: e1399a6e-effc-415c-9b11-ad051d604f86
---

**Equity cross-sectional LONG/SHORT gated NEGATIVE (2026-08-14). Don't re-run these.**
Shorting stocks/ETFs on IBKR is fully available (margin acct; liquid ETFs/large-caps are
easy-to-borrow, cheap; shorts show as negative STK positions — no FX settlement quirk). But two
staged gates killed the equity cross-sectional idea:

- **Gate #1 — factor-ETF market-neutral** (long MTUM/VLUE/QUAL/USMV, short SPY, 2013-2026):
  COMPOSITE **−1.1% CAGR / Sharpe −0.29 / −24% DD**. Value/quality/min-vol all negative vs SPY in
  the mega-cap-growth regime; only MTUM marginally +ve (Sharpe 0.16). Never worked (early −0.05,
  late −0.43). ETF-minus-SPY is a diluted factor expression.
- **Gate #2 — cross-sectional stock momentum L/S** (Ken French WML daily, survivorship-free =
  UPPER bound): gross real but thin (Sharpe 0.26-0.30 recent); **net of ~3%/yr tradeable cost →
  Sharpe ~0.11, ~0.2% CAGR**, with a **−40% momentum-crash drawdown (2020-21)**, −63% historically.
  Large-cap tradeable version would be weaker. Uninvestable.

Both ~uncorrelated to the book (FX −0.07/−0.09, RP basket −0.08) — so the **market-neutral
machinery works**, but there's no positive-return equity cross-sectional signal to drive it. Matches
the prior finding that equity-style diversification does nothing (see [[project_ibkr_equity_options_track]]).

**Fix-oriented pivot (NOT yet gated):** the shorting capability is better spent on **cross-asset
TIME-SERIES trend / managed-futures** — long/short each asset (equities/bonds/commodities/gold/FX)
on its OWN trend. That's a real crisis-alpha diversifier and the natural complement to carry
(carry+trend ~doubled Sharpe in FX — see [[project_fx_trend_is_the_diversifier]] /
[[project_fx_trend_queued]]). Trend uses shorting productively where cross-sectional factors don't.

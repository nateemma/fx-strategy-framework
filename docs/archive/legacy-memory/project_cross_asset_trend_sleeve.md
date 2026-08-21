---
name: project_cross_asset_trend_sleeve
description: Cross-asset ETF time-series trend (long/short) gated PASS — modest standalone Sharpe but uncorrelated to carry + real crisis alpha (2008/2022). The productive use of shorting.
metadata: 
  node_type: memory
  type: project
  originSessionId: e1399a6e-effc-415c-9b11-ad051d604f86
---

**Cross-asset time-series TREND (managed-futures style) gated PASS (2026-08-14)** — the productive
long/short use of shorting, where equity cross-sectional factors failed ([[project_equity_ls_gated_negative]]).

Setup: 9 liquid ETFs (SPY/EFA/EEM/TLT/IEF/LQD/GLD/DBC/DBA), long OR short each on its own 12-month
trend sign, risk-parity sized, vol-targeted to 10%, monthly rebalance, net of ~10bp/turnover +
borrow. Window 2008-2026.

- **Net Sharpe 0.43 full / 0.61 early(08-15) / 0.31 late(16-26) / 0.50 recent(20-now)**;
  CAGR ~4%; maxDD −26%. Alive in BOTH distant windows (passes persistence).
- **Crisis alpha (the point):** 2008 **+1.8%** (SPY −37%), 2022 **+17%** (SPY −18%). Pays when
  equities/bonds trend DOWN together.
- **Weakness (be honest):** whipsawed by fast/V-shaped moves — flat 2020 COVID, **−14% in 2018**
  (choppy). Hedges SUSTAINED bears, not sharp reversals. Will have ugly years.
- **Correlation:** +0.03 to FX carry, +0.03 to SPY, +0.26 to RP basket → genuine diversifier
  (esp. to carry). Value is in the BLEND, not standalone — mirrors the FX finding that carry+trend
  ~doubled Sharpe ([[project_fx_trend_is_the_diversifier]]).

Distinct from the FX trend factor: this is a CROSS-ASSET ETF sleeve (tradeable long/short on IBKR,
liquid ETB names). Building it needs the long/short-capable executor (current BasketExecution is
long-only).

**BLEND result (carry+basket+trend, equal-risk, 2018-2026, run 2026-08-14):** trend adds only
MARGINALLY on the deployment window. Levered-10% Sharpe 1.14 (2-sleeve) → **1.16** (3-sleeve);
maxDD −14.1% → **−13.0%** (unlevered −10.2% → −8.2%). Its help is concentrated almost entirely in
**2022** (blend +3.7% → +11.9%, an ~8pp rescue); it DRAGS in bull/whipsaw years (2019/2020/2023).
Two reasons it understates: the common window is bounded by carry OOS (2018+) so it **EXCLUDES 2008**
(trend's best crisis), and **equal-⅓ over-weights the 0.38-Sharpe sleeve**. Equal-⅓ was OVER-allocating the 0.38-Sharpe sleeve.

**WEIGHT SWEEP (run 2026-08-14) FLIPS the read → BUILD.** carry:basket fixed 50:50, trend weight
swept, blend levered to 10% vol. Sharpe-optimal trend wt = **20%** (Sharpe 1.21); min-DD = 14%
(−10.9%). At the **~15% sweet spot** vs 0% baseline: Sharpe **1.14→1.20**, maxDD **−14.1%→−11.0%**,
CAGR **14.3%→15.1%** (return UP), 2022 crisis year **+3.7%→+7.4%** (~doubled), 2023 bull drag mild
(+21.2%→+19.1%). So at the RIGHT (light ~15%) weight trend is a **strict improvement on every axis** —
not marginal. Still conservative (window excludes 2008). **DECISION: build the long/short trend
sleeve at ~15% weight.** Build = extend BasketExecution to long/short (allow negative target weights,
sell-to-open, gross/margin guards, borrow-aware). Stocks/short shows cleanly as negative STK
positions (no FX settlement quirk). This is the next real build for the ETF book.

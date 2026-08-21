---
name: project_fx_momentum_verdict
description: "FX cross-sectional momentum on G10 spot is a valid but too-weak factor — benched, not productized; go to value/PPP"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

2026-07-12: Built + tested cross-sectional momentum (`momentum` / `momentum_voltarget`, ranks G10 by trailing spot return, dollar-neutral top-N/bottom-N basket via `basket_weights`). Diagnostic over G10 daily 1971–2026 (data_cache, 9 currencies):

**Findings:**
- Hyperopt (20 samples, daily-rebal walk-forward): best OOS Sharpe **0.032**, maxDD −63%, IS–OOS gap −0.017 (NOT overfit — the whole param space is barren).
- **Daily rebalance was self-harming:** turnover cost ≈ **−0.11 Sharpe** (default 63/3/3: cost-free +0.071 → 1bp-daily −0.041). **Monthly rebalance recovers ~all of it** (monthly-at-cost +0.072 ≈ daily-cost-free +0.071). maxDD stays ~−55%.
- Even fixed (monthly, symmetric 63/3/3): Sharpe **~0.07–0.09** — positive but too weak to trade standalone.
- **corr(momentum, carry) = −0.066** — genuinely uncorrelated (a real independent factor), BUT √(0.303²+0.072²)=0.311 ≈ carry alone (0.303): a 0.07-Sharpe factor adds ~nothing to the carry blend.
- **Hyperopt mis-specified the rebalance:** it optimized DAILY walk-forward and picked 90/2/4 (net-short daily-cost survivor), which is WORSE monthly (+0.034) than plain 63/3/3 monthly (+0.072).

**Why:** Confirms the literature — FX momentum is the weakest factor, and G10-majors + daily-rebalance is its most hostile setting. Too weak to matter in the blend even uncorrelated.

**How to apply:** Momentum STAYS in the codebase (valid uncorrelated factor; proved the second-factor path; may matter in an EM universe or a time-series/trend variant later) but is **benched — do NOT invest in productizing monthly rebalance.** Go to **value/PPP** (backlog #2): stronger standalone (~0.35) + low-corr to carry → carry+value ≈ √(0.303²+0.35²) ≈ 0.46, which actually moves toward the [[project_fx_return_bar]] 8–10%/Sharpe-0.8 bar. **Framework lesson:** hyperopt rebalance cadence should be in the search space or fixed to monthly, else the objective mis-specifies the strategy (daily-rebal walk-forward picked a config worse at the sane monthly cadence). Diagnostic method (monthly-step weights via `w.resample("MS").first().reindex(...ffill)` + `simulate`) is reusable — was a throwaway /tmp script, not committed.

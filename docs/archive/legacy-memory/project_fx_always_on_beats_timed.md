---
name: project_fx_always_on_beats_timed
description: "FX program's recurring law — always-on factor exposure beats state-timing/estimation (EWMA, crash overlay)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

Recurring, now-thrice-confirmed law in the FX factor program (`~/Documents/forex`): **always-on beats
timed / estimated.** On G10 spot, a static, zero-parameter exposure repeatedly beats any attempt to
time or forecast it:

1. **Vol sizing:** a 1-parameter EWMA beat every learned vol forecaster (HAR, macro-HAR, EWMA-anchored,
   nonlinear GBM) — see [[project_fx_ml_vol_overlay_exhausted]]. Optimal ML weight = 0.
2. **Crash hedging (2026-07-14):** trend IS a genuine convex carry-crash hedge (diagnostic: carry↔trend
   corr deepens −0.10→−0.30 in carry-down months; trend +0.48% mean in worst-decile carry months, +11%
   in 2008-10). But a **state-conditioned crash overlay** (`carry_trend_crash*` — tilt weight to trend
   when the carry factor is in drawdown) **LOST to the static carry+trend blend**: worse Calmar and
   *deeper* drawdown at defaults, and a Calmar hyperopt of (dd_threshold, tilt) walked tilt monotonically
   to ~0 (= static). The static blend holds trend *continuously* so it's positioned *before* a crash;
   the dynamic overlay detects carry drawdown and tilts in with a ~1-month resample lag, buying the hedge
   late and whipsawing into the carry recovery.

**Mechanism of the law:** estimating/timing adds variance and lag against a weak signal; the static
version has zero estimated parameters and no timing lag. Forecast-combination puzzle + factor-timing
overfit, same root.

**Implications:** don't propose dynamic factor-timing / regime-switched sizing / learned overlays for the
G10 book without a *very* strong prior — the default expectation is they lose to always-on. The
deployable book stays `carry_trend_voltarget` (static carry+trend, EWMA vol-target, target_vol=0.062,
cap=1.20). Crash/ML variants remain registered as documented negatives. Where ML/timing might still earn
its keep is **non-price data** (CFTC COT positioning #7, regime conditioning #5) — untested — not on
re-weighting the price factors. IBKR approved (awaiting fund transfer) → live is near; this result
confirms there's no crash-overlay improvement to add before deploying.

Related: [[project_fx_carry_value_blend]], [[project_fx_return_bar]], [[project_fx_ml_vol_overlay_exhausted]].

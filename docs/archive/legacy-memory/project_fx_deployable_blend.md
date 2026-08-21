---
name: project_fx_deployable_blend
description: "DEPLOYABLE = carry_trend_voltarget, OOS Sharpe 0.52 (walk-forward). Value dilutes the blend — drop it."
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

2026-07-13: Built + merged + pushed the combined multi-factor blend (`BlendStrategy`, risk-parity inverse-EWMA-vol; registered `carry_trend`/`carry_trend_value` + `_voltarget`, sub-params hyperopt-able with defaults = validated bests). Public repo nateemma/fx-strategy-framework now has the full stack (138 tests). This is the CAPSTONE result of the FX program.

**Walk-forward OOS (train 2520 / test 504, full G10 history):**
| strategy | Sharpe | ann_ret | ann_vol | maxDD | Calmar |
|---|---|---|---|---|---|
| carry | 0.320 | 2.44% | 7.6% | -27.4% | 0.089 |
| carry_trend | 0.504 | 2.26% | 4.5% | -11.8% | 0.192 |
| carry_trend_value | 0.273 | 0.75% | 2.8% | -9.4% | 0.080 |
| **carry_trend_voltarget** | **0.520** | **3.42%** | 6.6% | -17.3% | **0.197** |

**Verdict:**
- **DEPLOYABLE = `carry_trend_voltarget`: OOS Sharpe 0.520** (walk-forward, 55yr). The ~0.5 thesis CONFIRMED OOS — ~1.6x carry's risk-adjusted return, far lower DD, from two negatively-correlated factors (carry+trend) risk-parity-blended + vol-targeted. Vol-target lifts Sharpe 0.504->0.520 AND scales return up (2.26%->3.42%).
- **VALUE DILUTES THE BLEND OOS — drop it.** carry_trend_value Sharpe 0.273: risk-parity gives the weak value leg (standalone ~0.07, [[project_fx_carry_value_blend]]) a full 1/3 risk budget, dragging the strong pair. Value's DD-hedge role does NOT survive equal-risk weighting OOS. This REFINES the earlier full-sample diagnostic which didn't isolate carry+trend on that window. Value stays registered/available but benched in the blend.

**On the [[project_fx_return_bar]] 8-10% bar:** invariant is Sharpe ~0.52; vol/return/DD scale with leverage. Comfortable ~10-12% vol -> ~5-6% / ~25% DD; levered ~15-19% vol -> 8-10% / ~40-50% DD. CLEARS the bar at the aggressive-leverage end. Honest: a real ~0.5-Sharpe uncorrelated FX book, deployable at chosen risk level.

**How to apply:** `carry_trend_voltarget` is the production config (drop value). Trend (ema/108) was the breakthrough leg ([[project_fx_trend_is_the_diversifier]]). Remaining upside levers (all higher-effort): v2 non-price ML vol features ([[project_ml_vol_overlay_verdict]]), the crypto-derivatives second track ([[project_ibkr_crypto_derivatives_track]]), EM carry. To push return, raise the overlay target_vol/cap (levers leverage). Don't add more weak rank-factors to the blend — they dilute.

---
name: project_fx_ml_vol_overlay_exhausted
description: FX ML vol-forecasting overlay (HAR replacing EWMA for vol-targeting) exhausted end-to-end; EWMA wins
metadata: 
  node_type: memory
  type: project
  originSessionId: 8763b088-8df0-42fa-b565-1f51a17b1900
---

The ML vol-forecasting overlay track for the FX carry book (repo `~/Documents/forex`) is exhausted
end-to-end. The idea was to replace the plain **EWMA** vol estimate used for vol-targeting with a
**HAR-RV ridge forecaster** (trailing realized vol at 5/21/63d, log-vol space, ridge α=1.0). Three
variants all LOSE to EWMA on walk-forward (`--timerange 1997-01-01: --train-days 2520 --test-days 504`,
run 2026-07-14):

| variant | Sharpe | Calmar |
|---|---|---|
| EWMA (`carry_voltarget`) | **0.1227** | **0.0476** |
| price-only HAR (`carry_voltarget_ml`) | 0.0943 | 0.0320 |
| cross-asset macro HAR — VIX+BAA10Y credit+term (`carry_voltarget_xasset`) | 0.0846 | 0.0289 |
| EWMA-anchored macro HAR (`carry_voltarget_xasset_anchored`) | 0.0873 | 0.0300 |
| EWMA-anchored nonlinear GBM (`carry_voltarget_xasset_gbm`) | 0.0638 | 0.0248 |

**Why airtight:** the anchored variant nests `log(EWMA)` as a fixed offset, so its ONLY difference from
EWMA is the learned corrections — and those corrections cost ~29% of Sharpe OOS. The optimal weight on
the ML signal is **zero**; the only remaining knob (α→∞) just converges the model back to EWMA from
below, so it can never beat it. Classic forecast-combination puzzle: EWMA wins by having zero estimated
parameters. Performance is **monotone-decreasing in model capacity** (EWMA > linear ridge > nonlinear
GBM): every increment of flexibility costs OOS Sharpe — the binding constraint is estimation variance,
not capacity. **An MLX LSTM was proposed and SHELVED on this evidence** (strictly more capacity than the
GBM → predicted worse; its unique DoF, learned temporal memory, is what EWMA already is). The GBM was a
deliberate cheap nonlinearity *probe* run before committing to the LSTM build — it answered no.
**Don't re-propose HAR / macro / nonlinear / LSTM / non-price vol forecasting for G10 carry
vol-targeting.** EWMA stays the deployable default (`carry_trend_voltarget`). Rejected variants stay
registered as documented negatives. (sklearn is an optional `[probe]` dep for the GBM.)

**Data gotcha discovered here:** the ICE BofA HY OAS series `BAMLH0A0HYM2` downloads TRUNCATED from FRED
(~2023+ only, likely ICE historical-access restriction) → macro overlay silently fell back to EWMA. Use
`BAA10Y` (Moody's Baa − 10y, full history 1986+) for a full-history credit spread. `MACRO_SERIES` key is
now `credit` (source-agnostic), not `hy_oas`.

Related: [[project_fx_carry_value_blend]], [[project_fx_return_bar]].

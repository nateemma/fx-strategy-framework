# FX Carry Vol-Target Overlay — Design Spec

*Design spec. Status: approved 2026-07-11. Sub-project of the FX carry program
(`docs/superpowers/specs/2026-07-10-fx-carry-crash-overlay-design.md`). Builds on the merged bare
carry baseline. Next step: implementation plan (writing-plans).*

Wrap the bare G10 carry basket in a **volatility-targeting overlay**: forecast the basket's forward
realized volatility and scale exposure inversely to it (capped), so the strategy de-risks ahead of
high-vol (crash) regimes. Built staged — a simple EWMA vol forecast first, then a tabular ML model
that ships only if it beats the EWMA overlay out-of-sample. This is the flagship crash-avoidance
overlay from the parent design, made concrete.

## Baselines to beat (already built and merged)
- **Bare carry** (long top-3 / short bottom-3 carry, dollar-neutral): **Sharpe 0.34 / maxDD −27%**
  over the tradeable window 1982–2026 (`forex/research/carry_baseline.py`).
- **EWMA vol-target** (Stage A below) — the honest yardstick for the ML stage.

## 1. Goal & success criteria
Add the overlay and improve **risk-adjusted** return with **lower drawdown**, judged the program's
way — on out-of-sample P&L, on a temporally-distant era, never on model fit:
- The EWMA vol-target must beat bare carry OOS on Sharpe/Calmar and cut max drawdown.
- **The ML stage (Stage B) ships ONLY if it beats the EWMA vol-target OOS on a distant era.**
  Otherwise the EWMA overlay is the product.

## 2. The overlay mechanism (`forex/backtest/voltarget.py`)
Given the bare-carry daily returns and a forward-vol forecast `σ̂_t` (annualized):
- Scale factor `s_t = min(cap, target_vol / σ̂_t)`.
- Applied to the NEXT period to avoid lookahead: `overlay_ret_t = s_{t-1} · carry_ret_t − cost(Δs)`,
  where the cost charges incremental turnover when the leverage `s` changes.
- `s` is stepped at a **rebalance cadence** (monthly) so leverage does not churn daily; `σ̂` may be
  computed daily but `s` only updates at the cadence.

## 3. The forecaster — staged
- **Stage A — EWMA baseline** (`forex/features/volforecast.py`): annualized RiskMetrics EWMA
  (λ ≈ 0.94) of basket returns. Vol-target with this. This is the overlay baseline everything beats.
- **Stage B — ML** (`forex/models/vol_ml.py`): `sklearn.HistGradientBoostingRegressor` predicting
  forward H-day realized vol of the basket from the feature set below, trained with walk-forward CV.
  Ships only if it beats Stage A OOS on the distant era.

## 4. Features (free, point-in-time via existing `asof_join`)
- **Basket own:** trailing realized vol at multiple windows; trailing drawdown.
- **Cross-asset risk:** VIX (equity vol), MOVE (rate vol), HY credit spreads (e.g. BAML HY OAS) —
  from FRED.
- **Positioning:** CFTC COT net-speculative extremes for the G10 currency futures (weekly, lagged).
- **Rate environment:** short-rate level and its trailing volatility.
- All series are release-lagged through `asof_join`; new loaders for VIX/MOVE/credit (FRED) and
  COT (CFTC).

## 5. Architecture (new units; reuse the existing data/backtest layers)
- `forex/data/` — new loaders: VIX/MOVE/credit (FRED, reuse `load_series`), CFTC COT.
- `forex/features/volforecast.py` — EWMA/realized-vol forecaster (Stage A) + the feature builders
  for Stage B.
- `forex/models/vol_ml.py` — GBM wrapper + walk-forward CV (Stage B).
- `forex/backtest/voltarget.py` — apply a vol-scale series to a returns series (the mechanism), with
  no-lookahead and turnover cost.
- `forex/research/overlay.py` — wire baseline → EWMA vol-target → ML vol-target; report all three vs
  each other + the distant-window check.

Each unit has one responsibility and a clear interface; the forecaster is decoupled from the overlay
mechanism (the mechanism takes any `σ̂` series), so Stage A and Stage B plug into the same
`voltarget` code path.

## 6. Evaluation & testing
- Judge on **OOS Sharpe / Calmar / maxDD vs bare-carry AND the EWMA-target**, on a distant era;
  realistic turnover cost from changing leverage.
- **Judge the ML on the overlay's P&L improvement, not vol-forecast accuracy** — a better forecast
  that does not improve risk-adjusted return does not ship (the program's learnability ≠ edge lesson).
- Unit tests: vol-target scaling (no-lookahead + cap enforced), EWMA forecaster, feature
  point-in-time alignment, walk-forward CV wiring.

## 7. Risks & non-goals
- Vol-targeting can TRAIL bare carry in calm bull runs (you hold less when it is quiet) — that is the
  trade (lower drawdown for possibly lower raw return); judge risk-adjusted, not on raw return.
- **ML overfit on few high-vol regimes** — high-vol crash episodes are rare, so Stage B has few
  informative samples. The EWMA gate + distant-window validation are the guards; keep the feature set
  small (the program's "more capacity → worse OOS" lesson).
- Non-goal: predicting direction or exact crash timing. We predict volatility — a smoother, more
  predictable quantity — and let sizing do the de-risking.

## 8. v1 numeric defaults (confirmed)
- **Horizon H** = 21 trading days (~1 month) forward realized vol.
- **target_vol** = 10% annualized.
- **leverage cap** = 1.5×.
- **rebalance cadence** = monthly.

## Open items for the implementation plan
- Exact basket-return series the overlay consumes (reuse `simulate` output from `run_baseline`).
- Precise EWMA annualization and the forward-realized-vol label construction (H-day, non-overlapping
  vs rolling).
- The exact FRED series IDs for VIX / MOVE / HY-OAS, and the CFTC COT source + parsing + release lag.
- The walk-forward CV split parameters for Stage B and the distant-era holdout definition.
- The turnover-cost model for leverage changes (bp per unit Δs).

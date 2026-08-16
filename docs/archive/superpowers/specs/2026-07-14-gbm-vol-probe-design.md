# GBM Nonlinearity Probe (v4) — Design Spec

*Design spec. Status: approved 2026-07-14. A cheap falsification test before committing to an MLX LSTM.
The anchored-HAR result (v3) showed linear vol corrections are net-negative OOS; the open question is
whether **nonlinearity / feature interactions / regime-dependence** — which an LSTM could exploit but a
ridge cannot — carry any edge over EWMA. This probe answers that with gradient-boosted trees (hours, no
MLX): a flexible nonlinear learner on the same features, anchored to EWMA. If GBM can't beat EWMA OOS,
an LSTM almost certainly won't either, and the LSTM build is not worth it. If GBM shows signal, escalate
to the LSTM with evidence.*

## Goal & success criteria
- A `GBMVolForecaster` with the **same interface** as `HARVolForecaster`
  (`fit(returns, exog=None, anchor=None, horizon=21, alpha=1.0)` / `predict(returns, exog=None, anchor=None)`),
  backed by sklearn `HistGradientBoostingRegressor`, deterministic (`random_state=0`).
- A `carry_voltarget_xasset_gbm` variant (macro exog + EWMA anchor) for the A/B.
- Existing HAR variants (`carry_voltarget_ml` / `_xasset` / `_xasset_anchored`) **byte-identical**.
- **Gate:** GBM beats EWMA OOS on walk-forward → escalate to the LSTM. Otherwise record the negative
  ("nonlinearity/interactions add no OOS edge over EWMA either"); the LSTM is shelved.

## Dependency
sklearn is a **new, optional** dependency (the core repo is pandas/numpy/pyarrow/fredapi). Add it under
`[project.optional-dependencies]` as `probe = ["scikit-learn>=1.4"]`; import it **inside** `GBMVolForecaster`
methods (or a lazy module-level guard) so importing the core framework never requires sklearn.

## Components

### 1. `GBMVolForecaster` (`strategies/features/gbmvol.py`)
Mirrors the HAR forecaster's contract so it drops into the existing overlay unchanged.
- **Features** — richer than HAR to give the nonlinear learner a fair shot at multi-scale memory:
  log-RV at windows `(5, 10, 21, 42, 63)` (each `log(√(mean(r²)·252))`, clipped), joined with `exog`
  when provided. No standardization (trees are scale-invariant).
- **Target** — `log(fwd_rv)` at `horizon`; when `anchor` is given, the residual `log(fwd_rv) − anchor`
  (identical anchoring semantics to `HARVolForecaster`).
- **Model** — `HistGradientBoostingRegressor(random_state=0)` with conservative, small-data-safe
  regularization: `max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=50,
  l2_regularization=1.0, early_stopping=True`. `alpha` (the ridge knob) is accepted for interface
  parity and ignored.
- **Consistency contract** — enforced exactly like `HARVolForecaster`: store `self._anchored` in `fit`,
  raise `ValueError` in `predict` on presence mismatch. The anchor must cover the prediction index (an
  uncovered date → NaN forecast → overlay EWMA fallback).
- `fit` drops NaN rows (`dropna`) before training; `predict` returns `exp(model.predict(X) [+ anchor])`
  as a `pd.Series` named `vol_forecast`, with NaN rows (incomplete features) preserved as NaN.

### 2. Forecaster injection hook (`strategies/mloverlay.py`)
Add a `_make_forecaster(self)` method returning `HARVolForecaster()` and call it in `__init__`
(`self.forecaster = self._make_forecaster()`) — **byte-identical** for every existing variant. Add:
```python
class GBMVolTargetOverlay(MLVolTargetOverlay):
    def _make_forecaster(self):
        from strategies.features.gbmvol import GBMVolForecaster
        return GBMVolForecaster()
```
No other overlay logic changes — `fit` / `_vol_forecast` already thread `exog` + `anchor` generically.

### 3. Variant registration (`strategies/carry.py`)
```python
class CarryVolTargetXAssetGBM(GBMVolTargetOverlay):
    NAME = "carry_voltarget_xasset_gbm"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base), use_macro=True, anchor_ewma=True, **overlay)
```

### Causality
Identical to the HAR/anchored variants: trailing RV + as-of macro exog + trailing EWMA anchor; `fit`
freezes the tree ensemble, `predict` uses only trailing data. `carry_voltarget_xasset_gbm` must pass
`causal-check`.

## Testing (all offline, no network; requires sklearn in the dev venv)
- **`GBMVolForecaster`**: fits and produces finite forecasts that rise in a high-vol regime (mirror
  `test_har_forecaster_fits_and_tracks_vol_regime`); `anchor=None` vs anchored differ; consistency
  contract raises on mismatch; deterministic across two `predict` calls.
- **Overlay/variant**: `carry_voltarget_xasset_gbm` builds via discovery with `use_macro=True` and
  `anchor_ewma=True`; `_make_forecaster` returns a `GBMVolForecaster`; the HAR overlays' `_make_forecaster`
  returns a `HARVolForecaster` (byte-identical); `assert_causal` + finite backtest on the synthetic macro
  view; discovery count +1.
- Full suite green.

## Validation (post-merge) — RESULT: nonlinearity hurts; LSTM shelved
Walk-forward `--timerange 1997-01-01: --train-days 2520 --test-days 504` (run 2026-07-14):

| variant | Sharpe | maxDD | Calmar | total |
|---|---|---|---|---|
| `carry_voltarget` (EWMA, 0 params) | **0.1227** | −24.6% | **0.0476** | 23.3% |
| `carry_voltarget_xasset_anchored` (linear ridge) | 0.0873 | −31.0% | 0.0300 | 18.1% |
| `carry_voltarget_xasset_gbm` (nonlinear GBM) | 0.0638 | −27.8% | 0.0248 | 13.1% |

Performance is **monotone-decreasing in model capacity**: EWMA > linear ridge > nonlinear GBM. Adding
nonlinearity/interactions made it *worse*, not better — the classic weak-signal / small-data signature
where estimation variance, not capacity, is the binding constraint. **Decision: the LSTM is shelved.**
An LSTM is strictly more flexible than the GBM, so the monotone trend predicts it lands at/below the
GBM; and its one unique DoF (learned temporal memory) is exactly what EWMA already is (an
exponential-memory model with one parameter). The ML-vol-overlay track — linear HAR, macro HAR,
EWMA-anchored HAR, and now nonlinear GBM — is closed. EWMA stays the deployable default. Residual
caveat: the GBM had windowed (not recurrent) memory, so a thin "maybe the LSTM sees more" remains, but
the evidence weight is strongly against it.

## Out of scope (YAGNI)
- The MLX LSTM itself (this probe decides whether it's worth building).
- Feature/hyperparameter search on the GBM beyond the fixed small-data-safe defaults above (a tuned GBM
  that beats EWMA only after heavy search would itself be an overfitting red flag).
- A price-only GBM variant — the macro-anchored one is the fair test of the full hypothesis.

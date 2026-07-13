# ML Crash / Vol Overlay — Design Spec

*Design spec. Status: approved 2026-07-12 (user pre-authorized end-to-end build, no clarifying
questions). Flagship ML piece on the FX strategy framework
(`docs/superpowers/specs/2026-07-11-framework-architecture-design.md`). Tier-1 item #4 in
`docs/strategy-research-backlog.md`. Replaces the EWMA vol forecast in the vol-target overlay with a
learned forecaster of forward realised volatility — ships only if it beats EWMA out-of-sample.*

## Goal & success criteria
The vol-target overlay currently sizes leverage from an EWMA vol estimate (`ewma_vol`), which lifted
carry Sharpe 0.30→0.40. This adds a **learned** forecaster of the base strategy's **forward** realised
volatility, driving the same leverage rule. Principle (carried from the crypto program): **predict
volatility, not direction** — vol is predictable where direction is not, and de-risking ahead of
high-vol regimes is what cuts carry-crash drawdowns and enables safe leverage on the drawdown-hedged
carry+value core.

Success: `MLVolTargetOverlay` composes onto any base strategy exactly like `VolTargetOverlay`;
`carry_voltarget_ml` is registered; all units are unit-tested offline; and a walk-forward comparison
(`carry_voltarget_ml` vs `carry_voltarget` vs bare `carry`) can be run on the cached data to decide
ship/keep. The **ship gate is empirical**: keep the ML forecaster only if it beats EWMA OOS; if not,
the code stays as an evaluated option and EWMA remains the default. Reporting a clean "ML did not beat
EWMA" is a valid outcome.

## Design decisions (made autonomously; recorded here)
- **Model = HAR-RV log-space ridge regression.** The Heterogeneous AutoRegressive Realised Volatility
  model (Corsi 2009) — regress forward realised vol on trailing realised vol at multiple horizons — is
  the academic standard for vol forecasting and routinely matches gradient-boosted models on aggregate
  vol while being far more robust to overfitting (the crypto program's recurring failure mode). Fit by
  ridge in log-vol space (log-vol is ~Gaussian; ridge stabilises the small coefficient vector).
- **No new dependency.** Closed-form ridge in numpy (`(XᵀX + αI)⁻¹Xᵀy`). No scikit-learn. This keeps
  the framework's pandas/numpy/stdlib footprint.
- **Price-derived features only (v1).** Features come from the base strategy's own return series
  (trailing realised vol at 5/21/63 days). Cross-asset features (VIX `VIXCLS`, HY credit
  `BAMLH0A0HYM2`, term spread) and positioning (CFTC COT), and a gradient-boosted model, are
  **documented v2** — they need a FRED/CFTC fetch and more plumbing, and v1 must be self-contained and
  offline-validatable on the existing cache.
- **Subclass, don't duplicate.** Extract the one vol-forecast line of `VolTargetOverlay` into an
  overridable `_vol_forecast` method (default = `ewma_vol`, byte-identical behaviour for the existing
  `*_voltarget` strategies). `MLVolTargetOverlay` overrides it. The base never references the subclass
  (per AGENT_GUIDE).

## Components

### 1. `forex/features/mlvol.py` — `HARVolForecaster`
A small learned forecaster of forward annualised realised volatility.

```python
class HARVolForecaster:
    WINDOWS = (5, 21, 63)     # trailing realised-vol horizons (week / month / quarter)

    def __init__(self):
        self.coef_ = None
        self.fitted = False

    def _features(self, returns: pd.Series) -> pd.DataFrame:
        # log trailing annualised realised vol over each window (causal / backward-looking)
        feats = {}
        for w in self.WINDOWS:
            rv = (returns.pow(2).rolling(w).mean() * 252) ** 0.5
            feats[f"rv{w}"] = np.log(rv.clip(lower=1e-8))
        return pd.DataFrame(feats)

    def fit(self, returns: pd.Series, horizon: int = 21, alpha: float = 1.0) -> "HARVolForecaster":
        X = self._features(returns)
        fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5  # forward RV
        y = np.log(fwd.clip(lower=1e-8))
        d = X.assign(_y=y).dropna()                      # drops warm-up AND the last `horizon` rows
        Xm = np.column_stack([np.ones(len(d)), d[X.columns].values])
        A = Xm.T @ Xm + alpha * np.eye(Xm.shape[1])
        self.coef_ = np.linalg.solve(A, Xm.T @ d["_y"].values)
        self.fitted = True
        return self

    def predict(self, returns: pd.Series) -> pd.Series:
        X = self._features(returns)
        Xm = np.column_stack([np.ones(len(X)), X.values])
        return pd.Series(np.exp(Xm @ self.coef_), index=X.index, name="vol_forecast")
```

- **Causality:** `_features` is entirely trailing; `predict` uses only features → causal. The forward
  target is used **only in `fit`**, where the last `horizon` rows (whose target extends past the
  training data) become NaN and are dropped — so a model fit on `truncate(train_end)` never sees data
  beyond `train_end`. Standard supervised setup.
- **Determinism:** closed-form solve, no randomness.

### 2. `forex/strategies/overlay.py` — extract `_vol_forecast`
Refactor `VolTargetOverlay.target_weights` so the vol estimate goes through an overridable method;
behaviour for existing `carry_voltarget` / `momentum_voltarget` / `value_voltarget` is unchanged.
```python
    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import backtest
        w = self.base.target_weights(view)
        base_ret = backtest(self.base, view, cost_bps=self.cost_bps).returns
        vf = self._vol_forecast(base_ret).reindex(w.index).ffill()
        raw = (self.target_vol / vf).clip(upper=self.cap)
        L = raw.resample(self.cadence).first().reindex(w.index, method="ffill")
        return w.mul(L, axis=0)

    def _vol_forecast(self, base_ret: pd.Series) -> pd.Series:
        return ewma_vol(base_ret, lam=self.lam)
```
(This is a pure extract-method: the only change is the `vf =` line becoming a call to
`self._vol_forecast`.)

### 3. `forex/strategies/mloverlay.py` — `MLVolTargetOverlay`
```python
class MLVolTargetOverlay(VolTargetOverlay):
    def __init__(self, base, *, horizon: int = 21, ridge_alpha: float = 1.0, **kw):
        super().__init__(base, **kw)
        self.horizon = horizon
        self.ridge_alpha = ridge_alpha
        self.forecaster = HARVolForecaster()

    def fit(self, train: DataView) -> None:
        from forex.run.backtest import backtest
        self.base.fit(train)
        base_ret = backtest(self.base, train, cost_bps=self.cost_bps).returns
        self.forecaster.fit(base_ret, horizon=self.horizon, alpha=self.ridge_alpha)

    def _vol_forecast(self, base_ret: pd.Series) -> pd.Series:
        if not self.forecaster.fitted:                    # plain backtest path (no walk-forward fit)
            self.forecaster.fit(base_ret, horizon=self.horizon, alpha=self.ridge_alpha)
        return self.forecaster.predict(base_ret)

    def params(self) -> dict:
        return {**super().params(), "horizon": self.horizon, "ridge_alpha": self.ridge_alpha}

    def search_space(self) -> dict:
        from forex.core.space import Float, Int
        return {**super().search_space(), "horizon": Int(10, 42)}
```
- **Walk-forward (honest OOS):** `walk_forward` calls `fit(truncate(train_end))` → forecaster fit on
  train only → `target_weights(full_view)` predicts causally with fixed coefficients → only test-slice
  scored. This is the ship-decision path.
- **Plain backtest (convenience):** `fit` is not called, so `_vol_forecast` self-fits on the full
  available base returns — in-sample-optimistic by design; documented, and NOT the ship judge.

### 4. `forex/strategies/registry.py` — `carry_voltarget_ml`
Add a builder mirroring `carry_voltarget`, routing carry keys (`n_long`, `n_short`) to the base and the
rest (`target_vol`, `cap`, `horizon`, `ridge_alpha`, `cadence`, `lam`) to `MLVolTargetOverlay`.
```python
def _carry_voltarget_ml(p):
    base = CarryStrategy(**{k: p[k] for k in _BASE_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _BASE_KEYS}
    return MLVolTargetOverlay(base, **overlay)

_BUILDERS = {..., "carry_voltarget_ml": _carry_voltarget_ml}
```

## Testing (all offline, no network)
- **`HARVolForecaster`** — on a synthetic return series with a deliberate high-vol regime followed by
  a low-vol regime: `fit` then `predict` yields a higher forecast during/after the high-vol stretch
  than the low-vol stretch; the fitted `coef_` has the expected length (1 intercept + 3 windows);
  `predict` is deterministic (same input → same output); a currency date before the warm-up window is
  NaN. Also assert that a model fit on a truncated series does not error and that `fitted` flips True.
- **`VolTargetOverlay` extract — byte-identical** — the existing `tests/test_overlay*.py` must still
  pass unchanged (the refactor is behaviour-preserving). Add one test asserting `_vol_forecast` on a
  known return series equals `ewma_vol(base_ret, lam)`.
- **`MLVolTargetOverlay`** — `fit(train)` sets `forecaster.fitted`; `target_weights` returns weights
  whose per-row gross scales inversely with the forecast vol (higher forecast → lower leverage);
  `params`/`search_space` include `horizon`; `assert_causal` passes on a multi-year injected view;
  an integration `backtest` produces finite metrics. Also: `target_weights` without a prior `fit`
  still works (self-fit path) and produces finite weights.
- **Registry** — `build_strategy("carry_voltarget_ml", {...})` returns an `MLVolTargetOverlay` wrapping
  a `CarryStrategy` with base params routed correctly and overlay params (`target_vol`, `cap`,
  `horizon`) set; `available()` includes `carry_voltarget_ml`.

## Validation (post-merge, on the cached data — separate research step)
Run and record: `forex walkforward --strategy carry` vs `carry_voltarget` (EWMA) vs
`carry_voltarget_ml` (and the same on a carry+value base if convenient). Decide:
- If `carry_voltarget_ml` OOS Sharpe/Calmar **beats** `carry_voltarget` → the ML forecaster is the new
  preferred overlay; record the win.
- If **not** → record "HAR-ML did not beat EWMA OOS on G10"; EWMA stays the default; the code remains
  as an evaluated option and the v2 features (cross-asset, GBM) become the next thing to try.

## Out of scope (YAGNI / v2)
- Cross-asset & positioning features (VIX/MOVE/credit/term-spread/COT) — needs FRED/CFTC fetch + config
  plumbing; documented as the primary v2 lever.
- Gradient-boosted / neural models — HAR-ridge first; escalate only if it doesn't beat EWMA.
- Direct crash *classification* (a discrete risk-off signal) — v1 is a continuous vol forecast feeding
  the existing leverage rule.
- No change to `basket_weights`, the backtest, walk-forward, hyperopt, causal-check, or the CLI.

## References
- Corsi (2009), *A Simple Approximate Long-Memory Model of Realized Volatility* (HAR-RV).
- Menkhoff, Sarno, Schmeling, Schrimpf (2012), *Carry Trades and Global FX Volatility*.

# ML Crash / Vol Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the EWMA vol estimate in the vol-target overlay with a learned HAR-RV forecaster of forward realised volatility, composable as `carry_voltarget_ml`, shipping only if it beats EWMA out-of-sample.

**Architecture:** A numpy HAR-RV ridge forecaster (`HARVolForecaster`) with `fit`/`predict`. Extract the vol-forecast step of the working `VolTargetOverlay` into an overridable `_vol_forecast` method (byte-identical for existing variants); `MLVolTargetOverlay` subclasses it and fits the forecaster in `fit(train)`. Registry gains `carry_voltarget_ml`.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. No new dependencies.

## Global Constraints

- No new runtime dependencies; pandas + numpy + stdlib only (closed-form ridge in numpy — NO scikit-learn).
- The `VolTargetOverlay` refactor is a pure extract-method: behaviour for `carry_voltarget` / `momentum_voltarget` / `value_voltarget` must be byte-identical (existing overlay tests pass unchanged).
- HAR features are trailing realised vol over `WINDOWS = (5, 21, 63)`; the forward target is realised vol over the next `horizon` days; the model is ridge in **log-vol space**.
- Causality: `predict` uses only trailing features; the forward target is used ONLY in `fit`, where rows whose target extends past the training data are NaN and dropped.
- The base class never references the subclass (per AGENT_GUIDE).
- Search space uses `forex.core.space.Int`: add `horizon = Int(10, 42)` to the overlay's existing `target_vol`/`cap` space.
- Match the existing compact code style (see `forex/strategies/overlay.py`, `forex/features/volforecast.py`).
- Stage only the files each task touches — never `git add -A`.
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: `HARVolForecaster`

**Files:**
- Create: `forex/features/mlvol.py`
- Test: `tests/test_mlvol.py`

**Interfaces:**
- Produces: `HARVolForecaster` with `WINDOWS = (5, 21, 63)`, attributes `.coef_` (numpy array len 4) and `.fitted` (bool); `fit(returns, horizon=21, alpha=1.0) -> self`; `predict(returns) -> pd.Series` (annualised forward-vol forecast, NaN during warm-up, causal).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mlvol.py
import numpy as np, pandas as pd
from forex.features.mlvol import HARVolForecaster

def _regime_returns():
    idx = pd.date_range("2015-01-01", periods=1000, freq="B")
    rng = np.random.RandomState(0)
    r = np.concatenate([rng.normal(0, 0.003, 500), rng.normal(0, 0.02, 500)])  # low then high vol
    return pd.Series(r, index=idx)

def test_har_forecaster_fits_and_tracks_vol_regime():
    returns = _regime_returns()
    f = HARVolForecaster().fit(returns, horizon=21, alpha=1.0)
    assert f.fitted and len(f.coef_) == 4          # intercept + 3 windows
    pred = f.predict(returns)
    assert pred.iloc[:60].isna().all()             # warm-up before the 63-window is NaN
    assert pred.iloc[300:].notna().all()           # valid past warm-up
    assert pred.iloc[600:].mean() > pred.iloc[100:400].mean()   # higher forecast in high-vol regime

def test_har_predict_is_deterministic():
    returns = _regime_returns()
    f = HARVolForecaster().fit(returns)
    a = f.predict(returns)
    b = f.predict(returns)
    assert (a.dropna() == b.dropna()).all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mlvol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forex.features.mlvol'`.

- [ ] **Step 3: Write minimal implementation**

```python
# forex/features/mlvol.py
import numpy as np
import pandas as pd

class HARVolForecaster:
    """HAR-RV ridge forecaster of forward annualised realised volatility (log-vol space)."""
    WINDOWS = (5, 21, 63)

    def __init__(self):
        self.coef_ = None
        self.fitted = False

    def _features(self, returns: pd.Series) -> pd.DataFrame:
        feats = {}
        for w in self.WINDOWS:
            rv = (returns.pow(2).rolling(w).mean() * 252) ** 0.5
            feats[f"rv{w}"] = np.log(rv.clip(lower=1e-8))
        return pd.DataFrame(feats)

    def fit(self, returns: pd.Series, horizon: int = 21, alpha: float = 1.0) -> "HARVolForecaster":
        X = self._features(returns)
        fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
        y = np.log(fwd.clip(lower=1e-8))
        d = X.assign(_y=y).dropna()
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mlvol.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add forex/features/mlvol.py tests/test_mlvol.py
git commit -m "feat: HARVolForecaster (HAR-RV ridge forward-vol forecaster)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Extract `VolTargetOverlay._vol_forecast`

**Files:**
- Modify: `forex/strategies/overlay.py`
- Test: `tests/test_overlay_strategy.py`

**Interfaces:**
- Produces: `VolTargetOverlay._vol_forecast(base_ret: pd.Series) -> pd.Series` (default = `ewma_vol(base_ret, self.lam)`), called from `target_weights`. Behaviour of `target_weights` is unchanged.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_overlay_strategy.py`:
```python
def test_vol_forecast_defaults_to_ewma():
    from forex.strategies.overlay import VolTargetOverlay
    from forex.strategies.carry import CarryStrategy
    from forex.features.volforecast import ewma_vol
    idx = pd.date_range("2019-01-01", periods=300, freq="B")
    base_ret = pd.Series(np.random.RandomState(1).normal(0, 0.01, 300), index=idx)
    ov = VolTargetOverlay(CarryStrategy(1, 1), lam=0.94)
    assert (ov._vol_forecast(base_ret) == ewma_vol(base_ret, lam=0.94)).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_overlay_strategy.py -v`
Expected: FAIL with `AttributeError: 'VolTargetOverlay' object has no attribute '_vol_forecast'`.

- [ ] **Step 3: Write minimal implementation**

In `forex/strategies/overlay.py`, change the `vf =` line in `target_weights` to call the new method, and add the method. The updated `target_weights` plus the new method:
```python
    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import backtest
        w = self.base.target_weights(view)
        base_ret = backtest(self.base, view, cost_bps=self.cost_bps).returns
        vf = self._vol_forecast(base_ret).reindex(w.index).ffill()
        raw = (self.target_vol / vf).clip(upper=self.cap)
        L = raw.resample(self.cadence).first().reindex(w.index, method="ffill")
        return w.mul(L, axis=0)   # causal, NOT pre-shifted; backtest applies shift(1)

    def _vol_forecast(self, base_ret: pd.Series) -> pd.Series:
        return ewma_vol(base_ret, lam=self.lam)
```
Leave `__init__`, `fit`, `params`, `search_space`, and the `ewma_vol` import unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_overlay_strategy.py tests/test_overlay.py -v`
Expected: PASS (the new test AND the pre-existing overlay tests — behaviour is byte-identical).

- [ ] **Step 5: Commit**

```bash
git add forex/strategies/overlay.py tests/test_overlay_strategy.py
git commit -m "refactor: extract VolTargetOverlay._vol_forecast (default ewma)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `MLVolTargetOverlay`

**Files:**
- Create: `forex/strategies/mloverlay.py`
- Test: `tests/test_mloverlay.py`

**Interfaces:**
- Consumes: `VolTargetOverlay` and its `_vol_forecast` seam from Task 2; `HARVolForecaster` from Task 1; `backtest` from `forex.run.backtest`; `assert_causal` from `forex.diagnostics.causal`; `Int` from `forex.core.space`.
- Produces: `MLVolTargetOverlay(base, *, horizon=21, ridge_alpha=1.0, **kw)` with `.horizon`, `.ridge_alpha`, `.forecaster`; overrides `fit`, `_vol_forecast`, `params`, `search_space`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mloverlay.py
import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.core.space import Int
from forex.strategies.carry import CarryStrategy
from forex.strategies.mloverlay import MLVolTargetOverlay
from forex.diagnostics.causal import assert_causal
from forex.run.backtest import backtest
from forex.core.result import Result

def _view():
    idx = pd.date_range("2016-01-01", periods=700, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,700), "EUR": 1.1+np.zeros(700),
                         "SEK": 1.0+np.linspace(0,-0.1,700)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_fit_sets_forecaster_and_weights_preserve_shape_and_zeros():
    v = _view()
    base = CarryStrategy(1, 1)
    bw = base.target_weights(v)
    ov = MLVolTargetOverlay(base, target_vol=0.10, cap=1.5, cadence="D")
    ov.fit(v)
    assert ov.forecaster.fitted
    ow = ov.target_weights(v)
    assert ow.index.equals(bw.index) and list(ow.columns) == list(bw.columns)
    assert (ow.abs() <= 1.5 * bw.abs() + 1e-9).all().all()          # never exceeds cap
    assert (ow[bw == 0].fillna(0.0) == 0.0).all().all()             # zeros preserved

def test_target_weights_self_fits_without_prior_fit():
    v = _view()
    ov = MLVolTargetOverlay(CarryStrategy(1, 1), target_vol=0.10, cap=1.5, cadence="D")
    ow = ov.target_weights(v)                                        # no fit() called
    assert ov.forecaster.fitted                                      # self-fit happened
    assert np.isfinite(ow.dropna(how="all").to_numpy()).all()

def test_params_and_search_space():
    ov = MLVolTargetOverlay(CarryStrategy(3, 3), horizon=21, ridge_alpha=1.0)
    p = ov.params()
    assert p["horizon"] == 21 and p["ridge_alpha"] == 1.0 and "target_vol" in p
    assert ov.search_space()["horizon"] == Int(10, 42)

def test_ml_overlay_is_causal():
    v = _view()
    ov = MLVolTargetOverlay(CarryStrategy(1, 1), cadence="D")
    ov.fit(v)                                     # fix coefficients; predict must be truncation-invariant
    assert_causal(ov, v, v.calendar[[200, 400, 699]])

def test_backtest_produces_finite_result():
    r = backtest(MLVolTargetOverlay(CarryStrategy(1, 1), cadence="D"), _view(), cost_bps=1.0)
    assert isinstance(r, Result)
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mloverlay.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forex.strategies.mloverlay'`.

- [ ] **Step 3: Write minimal implementation**

```python
# forex/strategies/mloverlay.py
import pandas as pd
from forex.core.dataview import DataView
from forex.strategies.overlay import VolTargetOverlay
from forex.features.mlvol import HARVolForecaster

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
        if not self.forecaster.fitted:
            self.forecaster.fit(base_ret, horizon=self.horizon, alpha=self.ridge_alpha)
        return self.forecaster.predict(base_ret)

    def params(self) -> dict:
        return {**super().params(), "horizon": self.horizon, "ridge_alpha": self.ridge_alpha}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {**super().search_space(), "horizon": Int(10, 42)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_mloverlay.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add forex/strategies/mloverlay.py tests/test_mloverlay.py
git commit -m "feat: MLVolTargetOverlay (HAR-ML forecast drives vol-target leverage)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Registry entry `carry_voltarget_ml`

**Files:**
- Modify: `forex/strategies/registry.py`
- Modify: `tests/test_registry.py`

**Interfaces:**
- Consumes: `MLVolTargetOverlay` from Task 3; `CarryStrategy` (already imported).
- Produces: registry name `carry_voltarget_ml` (builds `MLVolTargetOverlay` wrapping a `CarryStrategy`, routing `n_long/n_short` to the base and the rest to the overlay). `available()` includes it.

- [ ] **Step 1: Update the failing tests**

In `tests/test_registry.py`, add the import and a test, and update the `available()` assertion.

Add near the top imports:
```python
from forex.strategies.mloverlay import MLVolTargetOverlay
```

Append this test:
```python
def test_build_carry_voltarget_ml_splits_params():
    s = build_strategy("carry_voltarget_ml",
                       {"n_long": 1, "n_short": 1, "target_vol": 0.10, "cap": 1.5, "horizon": 21})
    assert isinstance(s, MLVolTargetOverlay)
    assert isinstance(s.base, CarryStrategy) and s.base.n_long == 1
    assert s.target_vol == 0.10 and s.horizon == 21
```

Update the `available()` assertion inside `test_unknown_raises_and_available_lists` to add the new name:
```python
    assert set(available()) == {"carry", "carry_voltarget", "carry_voltarget_ml",
                                "momentum", "momentum_voltarget", "value", "value_voltarget"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL — `test_build_carry_voltarget_ml_splits_params` with `KeyError: "unknown strategy 'carry_voltarget_ml'"`, and the `available()` set assertion fails.

- [ ] **Step 3: Write minimal implementation**

In `forex/strategies/registry.py`, add the import, the builder, and extend `_BUILDERS`:
```python
from forex.strategies.mloverlay import MLVolTargetOverlay

def _carry_voltarget_ml(p: dict):
    base = CarryStrategy(**{k: p[k] for k in _BASE_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _BASE_KEYS}
    return MLVolTargetOverlay(base, **overlay)
```
Add `"carry_voltarget_ml": _carry_voltarget_ml,` to the `_BUILDERS` dict. Leave `build_strategy` and `available` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (whole suite green). If any pre-existing test fails, STOP and report BLOCKED with the failure — do not commit a red suite.

- [ ] **Step 6: Commit**

```bash
git add forex/strategies/registry.py tests/test_registry.py
git commit -m "feat: register carry_voltarget_ml strategy

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- The `VolTargetOverlay` change (Task 2) is a pure extract-method — do not alter the leverage/cadence math; the existing overlay tests are the guard.
- `MLVolTargetOverlay` inherits `target_weights` from `VolTargetOverlay` unchanged; it only overrides the vol-forecast source (plus `fit`/`params`/`search_space`).
- The self-fit path in `_vol_forecast` is for the plain-backtest convenience run; the honest OOS judge is walk-forward (which calls `fit(train)` per fold). Do not remove the self-fit guard.
- `ridge_alpha` is a param but intentionally NOT in the search space (kept fixed to limit overfitting); `horizon` is searchable.
- Do not touch `basket_weights`, the backtest, walk-forward, hyperopt, causal-check, or the CLI.

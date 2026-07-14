# GBM Nonlinearity Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `GBMVolForecaster` (sklearn gradient-boosted trees, anchored to EWMA) and a `carry_voltarget_xasset_gbm` variant, to test whether nonlinearity/interactions beat EWMA before building an MLX LSTM.

**Architecture:** `GBMVolForecaster` mirrors `HARVolForecaster`'s `fit/predict(returns, exog, anchor, ...)` interface so it drops into the existing overlay via a new `_make_forecaster()` hook; sklearn is an isolated optional dependency.

**Tech Stack:** pandas, numpy, sklearn `HistGradientBoostingRegressor` (optional dep).

## Global Constraints
- `GBMVolForecaster` must expose the exact interface `fit(returns, exog=None, anchor=None, horizon=21, alpha=1.0)` and `predict(returns, exog=None, anchor=None)`; `alpha` is accepted and ignored.
- Anchoring semantics identical to `HARVolForecaster`: anchored target = `log(fwd_rv) − anchor`, anchored prediction = `exp(model.predict(X) + anchor)`; consistency contract enforced (store `self._anchored` in `fit`, raise `ValueError` in `predict` on presence mismatch).
- Every existing variant (`carry_voltarget`, `_ml`, `_xasset`, `_xasset_anchored`) stays **byte-identical** — the `_make_forecaster()` refactor must still return `HARVolForecaster()` for the base class.
- Determinism: `HistGradientBoostingRegressor(random_state=0, max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=50, l2_regularization=1.0, early_stopping=True)`.
- sklearn imported **inside** `gbmvol.py` (not at package top level); added to `[project.optional-dependencies]` as `probe`.
- Framework (`forex/`) imports zero concrete strategies (unchanged — only `strategies/` + `pyproject.toml`).
- Run `python -m pytest -q` before each commit; commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; stage only files each task touches (never `git add -A`).

---

### Task 1: GBMVolForecaster

**Files:**
- Create: `strategies/features/gbmvol.py`
- Test: `tests/test_gbmvol.py`
- Modify: `pyproject.toml` (add `probe` optional dep)

**Interfaces:**
- Produces: `GBMVolForecaster` with `fit(returns, exog=None, anchor=None, horizon=21, alpha=1.0) -> self`
  (sets `.fitted`, `._anchored`) and `predict(returns, exog=None, anchor=None) -> pd.Series`
  (`name="vol_forecast"`). `WINDOWS = (5, 10, 21, 42, 63)`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_gbmvol.py`:
```python
import numpy as np, pandas as pd, pytest
from strategies.features.gbmvol import GBMVolForecaster

def _regime_returns():
    idx = pd.date_range("2010-01-01", periods=1200, freq="B")
    rng = np.random.RandomState(0)
    r = np.concatenate([rng.normal(0, 0.003, 600), rng.normal(0, 0.02, 600)])  # low then high vol
    return pd.Series(r, index=idx)

def test_gbm_fits_and_tracks_vol_regime():
    r = _regime_returns()
    f = GBMVolForecaster().fit(r, horizon=21)
    assert f.fitted
    pred = f.predict(r)
    assert pred.iloc[700:].notna().all()
    assert pred.iloc[750:].mean() > pred.iloc[100:400].mean()   # higher forecast in high-vol regime

def test_gbm_predict_is_deterministic():
    r = _regime_returns()
    f = GBMVolForecaster().fit(r)
    assert (f.predict(r).dropna() == f.predict(r).dropna()).all()

def test_gbm_anchor_changes_forecast_and_enforces_contract():
    r = _regime_returns()
    anchor = pd.Series(np.log(0.12), index=r.index)
    fa = GBMVolForecaster().fit(r, anchor=anchor)
    with pytest.raises(ValueError):
        fa.predict(r)                                           # fit anchored, predict not
    fp = GBMVolForecaster().fit(r)
    with pytest.raises(ValueError):
        fp.predict(r, anchor=anchor)                           # fit plain, predict anchored
    assert not fa.predict(r, anchor=anchor).dropna().equals(fp.predict(r).dropna())
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_gbmvol.py -q`
Expected: FAIL (`No module named 'strategies.features.gbmvol'`).

- [ ] **Step 3: Implement `GBMVolForecaster`**

Create `strategies/features/gbmvol.py`:
```python
import numpy as np
import pandas as pd

class GBMVolForecaster:
    """Gradient-boosted-tree forecaster of forward annualised realised volatility (log-vol space),
    a nonlinear counterpart to HARVolForecaster with the same fit/predict interface. Optionally learns
    the residual over an anchor (log-vol offset). Consistency contract: predict must receive `anchor`
    iff fit did (enforced); the anchor must cover the prediction index."""
    WINDOWS = (5, 10, 21, 42, 63)

    def __init__(self):
        self.model = None
        self.fitted = False
        self._anchored = False

    def _features(self, returns, exog=None):
        feats = {}
        for w in self.WINDOWS:
            rv = (returns.pow(2).rolling(w).mean() * 252) ** 0.5
            feats[f"rv{w}"] = np.log(rv.clip(lower=1e-8))
        X = pd.DataFrame(feats)
        if exog is not None:
            X = X.join(exog)
        return X

    def fit(self, returns, exog=None, anchor=None, horizon: int = 21, alpha: float = 1.0):
        from sklearn.ensemble import HistGradientBoostingRegressor
        X = self._features(returns, exog)
        fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
        y = np.log(fwd.clip(lower=1e-8))
        if anchor is not None:
            y = y - anchor
        d = X.assign(_y=y).dropna()
        self.model = HistGradientBoostingRegressor(
            random_state=0, max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
            min_samples_leaf=50, l2_regularization=1.0, early_stopping=True)
        self.model.fit(d[X.columns].values, d["_y"].values)
        self.fitted = True
        self._anchored = anchor is not None
        return self

    def predict(self, returns, exog=None, anchor=None):
        if (anchor is not None) != self._anchored:
            raise ValueError("predict must receive `anchor` iff fit did")
        X = self._features(returns, exog)
        valid = X.notna().all(axis=1)
        pred = pd.Series(np.nan, index=X.index, name="vol_forecast")
        if valid.any():
            p = self.model.predict(X[valid].values)
            if anchor is not None:
                p = p + anchor.reindex(X.index)[valid].values
            pred.loc[valid] = np.exp(p)
        return pred
```

- [ ] **Step 4: Add the optional dependency**

In `pyproject.toml`, add after the `dependencies = [...]` line:
```toml
[project.optional-dependencies]
probe = ["scikit-learn>=1.4"]
```
(If an `[project.optional-dependencies]` table already exists, add the `probe` key to it instead.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_gbmvol.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add strategies/features/gbmvol.py tests/test_gbmvol.py pyproject.toml
git commit -m "feat: GBMVolForecaster (gradient-boosted-tree vol forecaster, anchored)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Overlay hook + GBM variant

**Files:**
- Modify: `strategies/mloverlay.py` (add `_make_forecaster`; new `GBMVolTargetOverlay`)
- Modify: `strategies/carry.py` (register `CarryVolTargetXAssetGBM`)
- Test: `tests/test_mloverlay.py`, `tests/test_discovery.py` (count +1)

**Interfaces:**
- Consumes: Task 1's `GBMVolForecaster`; existing `MLVolTargetOverlay` (`fit`, `_vol_forecast`,
  `_anchor`, `use_macro`, `anchor_ewma`); `split_params` (already imported in `carry.py`).
- Produces: `MLVolTargetOverlay._make_forecaster()` (returns `HARVolForecaster()`), `GBMVolTargetOverlay`
  (overrides it), and discoverable `carry_voltarget_xasset_gbm`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mloverlay.py`:
```python
def test_gbm_variant_builds_and_uses_gbm_forecaster():
    from forex.core.discovery import build_strategy
    from strategies.features.gbmvol import GBMVolForecaster
    from strategies.features.mlvol import HARVolForecaster
    ov = build_strategy("carry_voltarget_xasset_gbm", package="strategies")
    assert ov.use_macro is True and ov.anchor_ewma is True
    assert isinstance(ov.forecaster, GBMVolForecaster)
    # base/HAR variants unchanged
    assert isinstance(build_strategy("carry_voltarget_ml", package="strategies").forecaster, HARVolForecaster)

def test_gbm_xasset_is_causal_and_finite():
    from strategies.mloverlay import GBMVolTargetOverlay
    from strategies.carry import CarryStrategy
    from forex.run.backtest import backtest
    from forex.core.result import Result
    v = _macro_view()
    ov = GBMVolTargetOverlay(CarryStrategy(1, 1), use_macro=True, anchor_ewma=True, cadence="D")
    ov.fit(v)
    assert_causal(ov, v, v.calendar[[200, 400, 699]])
    r = backtest(ov, v, cost_bps=1.0)
    assert isinstance(r, Result) and np.isfinite(r.metrics["sharpe"])
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_mloverlay.py -k "gbm" -q`
Expected: FAIL (unknown strategy / no `GBMVolTargetOverlay`).

- [ ] **Step 3: Add the forecaster hook + GBM overlay**

In `strategies/mloverlay.py`, replace the `__init__` line `self.forecaster = HARVolForecaster()` with
`self.forecaster = self._make_forecaster()` and add the method + subclass:
```python
    def _make_forecaster(self):
        return HARVolForecaster()

class GBMVolTargetOverlay(MLVolTargetOverlay):
    def _make_forecaster(self):
        from strategies.features.gbmvol import GBMVolForecaster
        return GBMVolForecaster()
```
(Place `_make_forecaster` as a method of `MLVolTargetOverlay`; put `GBMVolTargetOverlay` after the class.)

- [ ] **Step 4: Register the variant**

In `strategies/carry.py`, import `GBMVolTargetOverlay` alongside the existing overlay imports, and after
`CarryVolTargetXAssetAnchored` add:
```python
class CarryVolTargetXAssetGBM(GBMVolTargetOverlay):
    NAME = "carry_voltarget_xasset_gbm"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base), use_macro=True, anchor_ewma=True, **overlay)
```

- [ ] **Step 5: Update discovery count + run full suite**

Update the strategy-count assertion in `tests/test_discovery.py` (+1, and add
`carry_voltarget_xasset_gbm` to any explicit name set / parametrize list there — match the pattern used
for the prior variants).
Run: `python -m pytest -q`
Expected: PASS (existing HAR/anchored variants unchanged; new tests green).

- [ ] **Step 6: Commit**

```bash
git add strategies/mloverlay.py strategies/carry.py tests/test_mloverlay.py tests/test_discovery.py
git commit -m "feat: carry_voltarget_xasset_gbm (nonlinear anchored vol probe)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review
- **Spec coverage:** GBMVolForecaster + interface parity (Task 1) ✓; anchoring + contract (Task 1 tests) ✓;
  optional dep (Task 1 Step 4) ✓; `_make_forecaster` hook + byte-identical HAR (Task 2 Step 3 + test) ✓;
  variant registration (Task 2) ✓; causality/finite (Task 2 test) ✓; discovery count (Task 2 Step 5) ✓.
- **Placeholder scan:** none — all steps carry concrete code/commands.
- **Type consistency:** `anchor` is a pandas Series (log-vol) throughout; `predict` returns a
  `vol_forecast` Series with NaN for incomplete-feature rows; `_make_forecaster` returns a forecaster
  object with the shared `fit`/`predict` contract; `carry_voltarget_xasset_gbm` NAME consistent.

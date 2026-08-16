# EWMA-Anchored HAR Vol Forecaster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nest EWMA inside the HAR vol forecaster as a fixed offset (anchor), so the model learns only the residual EWMA misses; register a `carry_voltarget_xasset_anchored` variant for the A/B.

**Architecture:** Additive `anchor` parameter on `HARVolForecaster.fit`/`predict` (target `log(fwd_rv) − anchor`, prediction `exp(Xβ + anchor)`), byte-identical when `anchor=None`; a structural `anchor_ewma` flag on `MLVolTargetOverlay` that supplies `log(EWMA(base_ret, lam))`.

**Tech Stack:** numpy, pandas, ridge via `np.linalg.solve` (no new deps).

## Global Constraints
- `HARVolForecaster` with `anchor=None` must be **byte-identical** to the current implementation (v2 `carry_voltarget_ml` / `carry_voltarget_xasset` must not change numerically).
- `anchor_ewma` is a **structural** flag → NOT in `params()` / `search_space()` (same rule as `use_macro`).
- `alpha` stays at the family default `1.0`; the offset is the only intervention.
- Framework (`forex/`) imports zero concrete strategies (unchanged — this touches only `strategies/`).
- Consistency contract: `predict` receives `anchor` iff `fit` received `anchor`.
- Run the full suite (`python -m pytest -q`) before each commit; commit messages end with the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer; stage only files each task touches (never `git add -A`).

---

### Task 1: Forecaster anchor support

**Files:**
- Modify: `strategies/features/mlvol.py` (`HARVolForecaster.fit`, `.predict`)
- Test: `tests/test_mlvol.py`

**Interfaces:**
- Consumes: existing `HARVolForecaster` (`_features`, `WINDOWS`, ridge solve).
- Produces: `fit(returns, exog=None, anchor=None, horizon=21, alpha=1.0)` and
  `predict(returns, exog=None, anchor=None)`. `anchor` is a pandas Series on the returns index in
  log-vol space. Target when anchored: `log(fwd_rv) − anchor`; prediction when anchored:
  `exp(Xβ + anchor)`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mlvol.py`:
```python
import numpy as np, pandas as pd
from strategies.features.mlvol import HARVolForecaster

def _returns(n=800, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2000-01-01", periods=n, freq="B")
    return pd.Series(rng.normal(0, 0.01, n), index=idx)

def test_anchor_none_is_byte_identical():
    r = _returns()
    a = HARVolForecaster().fit(r)                       # baseline (no anchor)
    b = HARVolForecaster().fit(r, anchor=None)          # explicit None
    assert np.array_equal(a.coef_, b.coef_)
    pa, pb = a.predict(r), b.predict(r, anchor=None)
    assert pa.equals(pb)

def test_anchored_prediction_tracks_anchor():
    r = _returns()
    f = HARVolForecaster()
    anchor = pd.Series(np.log(0.12), index=r.index)     # constant log-vol anchor
    f.fit(r, anchor=anchor)
    pred = f.predict(r, anchor=anchor)
    plain = HARVolForecaster().fit(r).predict(r)
    assert not pred.dropna().equals(plain.dropna())     # anchoring changes the forecast
    # residual target is centered near 0 -> anchored forecast stays near exp(anchor)
    assert abs(np.log(pred.dropna()).mean() - np.log(0.12)) < abs(np.log(plain.dropna()).mean() - np.log(0.12))
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_mlvol.py -k "anchor" -q`
Expected: FAIL (`fit()`/`predict()` got unexpected keyword argument `anchor`).

- [ ] **Step 3: Implement the anchor**

In `strategies/features/mlvol.py`, update `fit` and `predict` (docstring: note the consistency
contract — predict must be given `anchor` iff fit was):
```python
def fit(self, returns, exog=None, anchor=None, horizon: int = 21, alpha: float = 1.0):
    X = self._features(returns, exog)
    fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
    y = np.log(fwd.clip(lower=1e-8))
    if anchor is not None:
        y = y - anchor
    d = X.assign(_y=y).dropna()
    Xv = d[X.columns].values
    if exog is not None:
        self.mean_ = Xv.mean(axis=0)
        self.std_ = Xv.std(axis=0)
        self.std_[self.std_ == 0] = 1.0
        Xv = (Xv - self.mean_) / self.std_
    else:
        self.mean_ = self.std_ = None
    Xm = np.column_stack([np.ones(len(d)), Xv])
    A = Xm.T @ Xm + alpha * np.eye(Xm.shape[1])
    self.coef_ = np.linalg.solve(A, Xm.T @ d["_y"].values)
    self.fitted = True
    return self

def predict(self, returns, exog=None, anchor=None):
    X = self._features(returns, exog)
    Xv = X.values
    if self.mean_ is not None:
        Xv = (Xv - self.mean_) / self.std_
    Xm = np.column_stack([np.ones(len(X)), Xv])
    pred = Xm @ self.coef_
    if anchor is not None:
        pred = pred + anchor.reindex(X.index).values
    return pd.Series(np.exp(pred), index=X.index, name="vol_forecast")
```

- [ ] **Step 4: Run tests (new + existing forecaster tests)**

Run: `python -m pytest tests/test_mlvol.py -q`
Expected: PASS (including the pre-existing `exog`/byte-identical tests).

- [ ] **Step 5: Commit**

```bash
git add strategies/features/mlvol.py tests/test_mlvol.py
git commit -m "feat: optional EWMA anchor (offset) on HARVolForecaster

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Overlay flag + anchored variant

**Files:**
- Modify: `strategies/mloverlay.py` (`MLVolTargetOverlay.__init__`, `fit`, `_vol_forecast`, add `_anchor`)
- Modify: `strategies/carry.py` (register `CarryVolTargetXAssetAnchored`)
- Test: `tests/test_mloverlay.py`

**Interfaces:**
- Consumes: Task 1's `HARVolForecaster.fit/predict(..., anchor=...)`; `ewma_vol` (already imported in
  `mloverlay.py`); `self.lam` from `VolTargetOverlay`; `split_params` (already imported in `carry.py`).
- Produces: `MLVolTargetOverlay(base, *, horizon=21, ridge_alpha=1.0, use_macro=False, anchor_ewma=False)`
  and a discoverable strategy `carry_voltarget_xasset_anchored`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mloverlay.py`. The module builds overlays directly (e.g.
`MLVolTargetOverlay(CarryStrategy(1, 1), use_macro=True, cadence="D")`) and uses the `_macro_view()`
helper (already defines `macro` with keys `vix`/`credit`/`term`) and `assert_causal`. Mirror the
existing `test_xasset_is_causal_and_finite` for the anchored path, plus a discovery + flag-visibility
check:
```python
def test_anchored_variant_builds_via_discovery_and_flag_hidden():
    from forex.core.discovery import build_strategy
    ov = build_strategy("carry_voltarget_xasset_anchored", package="strategies")
    assert ov.use_macro is True and ov.anchor_ewma is True
    assert "anchor_ewma" not in ov.params()          # structural, not tunable

def test_anchor_off_by_default():
    from strategies.mloverlay import MLVolTargetOverlay
    from strategies.carry import CarryStrategy
    ov = MLVolTargetOverlay(CarryStrategy(1, 1), use_macro=True, cadence="D")
    assert ov.anchor_ewma is False
    assert ov._anchor(pd.Series([0.01, -0.01, 0.02])) is None

def test_anchored_xasset_is_causal_and_finite():
    from strategies.mloverlay import MLVolTargetOverlay
    from strategies.carry import CarryStrategy
    from forex.run.backtest import backtest
    from forex.core.result import Result
    v = _macro_view()
    ov = MLVolTargetOverlay(CarryStrategy(1, 1), use_macro=True, anchor_ewma=True, cadence="D")
    ov.fit(v)
    assert_causal(ov, v, v.calendar[[200, 400, 699]])
    r = backtest(ov, v, cost_bps=1.0)
    assert isinstance(r, Result) and np.isfinite(r.metrics["sharpe"])
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_mloverlay.py -k "anchor" -q`
Expected: FAIL (unknown strategy `carry_voltarget_xasset_anchored` / no `anchor_ewma` attribute).

- [ ] **Step 3: Implement overlay flag + `_anchor`**

In `strategies/mloverlay.py`:
```python
def __init__(self, base, *, horizon: int = 21, ridge_alpha: float = 1.0,
             use_macro: bool = False, anchor_ewma: bool = False, **kw):
    super().__init__(base, **kw)
    self.horizon = horizon
    self.ridge_alpha = ridge_alpha
    self.use_macro = use_macro
    self.anchor_ewma = anchor_ewma
    self.forecaster = HARVolForecaster()

def _anchor(self, base_ret):
    if not self.anchor_ewma:
        return None
    return np.log(ewma_vol(base_ret, lam=self.lam).clip(lower=1e-8))

def fit(self, train: DataView) -> None:
    from forex.run.backtest import backtest
    self.base.fit(train)
    base_ret = backtest(self.base, train, cost_bps=self.cost_bps).returns
    exog = self._build_exog(train, base_ret.index) if self.use_macro else None
    anchor = self._anchor(base_ret)
    self.forecaster.fit(base_ret, exog=exog, anchor=anchor, horizon=self.horizon, alpha=self.ridge_alpha)

def _vol_forecast(self, base_ret, view):
    exog = self._build_exog(view, base_ret.index) if self.use_macro else None
    anchor = self._anchor(base_ret)
    if not self.forecaster.fitted:
        self.forecaster.fit(base_ret, exog=exog, anchor=anchor, horizon=self.horizon, alpha=self.ridge_alpha)
    har = self.forecaster.predict(base_ret, exog=exog, anchor=anchor)
    return har.fillna(ewma_vol(base_ret, lam=self.lam))
```
(`params()` / `search_space()` unchanged — `anchor_ewma` stays out of both.)

- [ ] **Step 4: Register the variant**

In `strategies/carry.py`, after `CarryVolTargetXAsset`:
```python
class CarryVolTargetXAssetAnchored(MLVolTargetOverlay):
    NAME = "carry_voltarget_xasset_anchored"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base), use_macro=True, anchor_ewma=True, **overlay)
```

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (new tests green; `carry_voltarget_xasset` and `carry_voltarget_ml` unchanged).

- [ ] **Step 6: Commit**

```bash
git add strategies/mloverlay.py strategies/carry.py tests/test_mloverlay.py
git commit -m "feat: carry_voltarget_xasset_anchored (EWMA-anchored macro HAR)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review
- **Spec coverage:** forecaster anchor (Task 1) ✓; overlay flag + `_anchor` (Task 2) ✓; variant
  registration (Task 2) ✓; byte-identical `anchor=None` (Task 1 test) ✓; structural-flag-hidden (Task 2
  test) ✓; causality (Task 2, via existing macro fixture) ✓.
- **Placeholder scan:** none — all steps carry concrete code/commands.
- **Type consistency:** `anchor` is a pandas Series (log-vol) in both tasks; `_anchor` returns
  `Series | None`; `carry_voltarget_xasset_anchored` NAME matches spec throughout.

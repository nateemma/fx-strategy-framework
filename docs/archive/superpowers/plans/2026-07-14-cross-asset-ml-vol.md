# Cross-Asset ML Vol Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add global risk-off features (VIX / HY credit / term spread) to the HAR vol forecaster via a new `DataView.macro` channel, registered as `carry_voltarget_xasset`, to test whether non-price data beats EWMA.

**Architecture:** A global `macro` dict on `DataView` (loaded from FRED); `HARVolForecaster` gains optional exogenous features + fit-window standardization (byte-identical when `exog=None`); `MLVolTargetOverlay(use_macro=True)` builds the macro exog from the view and threads it in.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. No new dependencies.

## Global Constraints

- `carry_voltarget_ml` (price-only) stays **byte-identical** — the exog path is additive and off by default; standardization only kicks in when `exog is not None`.
- Macro series are **global** (not per-currency): `MACRO_SERIES = {"vix": "VIXCLS", "hy_oas": "BAMLH0A0HYM2", "term": "T10Y2Y"}`.
- Macro exog is causal: as-of-aligned (`reindex(index, method="ffill")`) so a forecast at *t* uses only macro known by *t*. Transforms: `log(vix)`, `log(hy_oas)`, `term` raw.
- `use_macro` is a structural flag → NOT in `params()`/`search_space()`.
- No new dependencies. Match the existing compact style. Stage only the files each task touches — never `git add -A`.
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: Global `macro` data channel

**Files:**
- Modify: `forex/config.py`, `forex/core/dataview.py`, `forex/data/refresh.py`
- Test: `tests/test_config.py`, `tests/test_dataview.py`, `tests/test_refresh.py`, `tests/test_carry_baseline.py`, `tests/test_overlay.py`

**Interfaces:**
- Produces: `MACRO_SERIES` (dict); `DataView.macro: dict` (default empty, clipped by `truncate`, loaded by `from_fred`); `refresh_cache` includes the macro ids.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:
```python
def test_macro_series():
    from forex.config import MACRO_SERIES
    assert MACRO_SERIES == {"vix": "VIXCLS", "hy_oas": "BAMLH0A0HYM2", "term": "T10Y2Y"}
```

Append to `tests/test_dataview.py`:
```python
def test_macro_defaults_empty_and_truncate_clips_it():
    assert _view().macro == {}
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    spot = pd.DataFrame({"AUD": range(5)}, index=idx).astype(float)
    macro = {"vix": pd.Series([20.0]*5, index=idx)}
    v = DataView(spot=spot, rates={"USD": pd.Series([0.01]*5, index=idx)}, macro=macro)
    t = v.truncate("2020-01-03")
    assert t.macro["vix"].index.max() == pd.Timestamp("2020-01-03")

def test_from_fred_loads_macro(tmp_path):
    midx = pd.date_range("2015-01-01", periods=24, freq="MS")
    def fake_loader(series_id, *, cache_dir=None, **kw):
        return pd.Series(range(1, 25), index=midx, dtype="float64", name="value")
    v = DataView.from_fred(tmp_path, loader=fake_loader, codes=["AUD", "EUR"])
    assert set(v.macro) == {"vix", "hy_oas", "term"}
```

Append to `tests/test_refresh.py` `test_refresh_cache_forces_all_universe_series` (or a new test):
```python
def test_refresh_cache_includes_macro(tmp_path):
    from forex.config import MACRO_SERIES
    seen = []
    def loader(series_id, *, cache_dir, client=None, force=False):
        seen.append(series_id)
        return pd.Series([1.0], index=pd.to_datetime(["2020-01-01"]))
    ids = refresh_cache(tmp_path, codes=["AUD", "EUR"], loader=loader)
    assert all(sid in ids for sid in MACRO_SERIES.values())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py tests/test_dataview.py tests/test_refresh.py -v`
Expected: FAIL (`MACRO_SERIES` missing / `macro` attr missing).

- [ ] **Step 3: Write minimal implementation**

In `forex/config.py`, add after `CURRENCIES`:
```python
# Global (market-wide) risk-off series for the cross-asset ML vol overlay (FRED, daily).
MACRO_SERIES = {"vix": "VIXCLS", "hy_oas": "BAMLH0A0HYM2", "term": "T10Y2Y"}
```

In `forex/core/dataview.py`: add the field, clip it in `truncate`, load it in `from_fred`:
```python
@dataclass
class DataView:
    spot: pd.DataFrame
    rates: dict
    reer: dict = field(default_factory=dict)
    macro: dict = field(default_factory=dict)

    def truncate(self, asof) -> "DataView":
        asof = pd.Timestamp(asof)
        spot = self.spot.loc[:asof]
        rates = {k: v.loc[:asof] for k, v in self.rates.items()}
        reer = {k: v.loc[:asof] for k, v in self.reer.items()}
        macro = {k: v.loc[:asof] for k, v in self.macro.items()}
        return DataView(spot=spot, rates=rates, reer=reer, macro=macro)

    @classmethod
    def from_fred(cls, cache_dir, loader=None, codes=None) -> "DataView":
        from forex.config import CURRENCIES, MACRO_SERIES
        # ... (unchanged spot/rates/reer loading) ...
        macro = {name: loader(sid, cache_dir=cache_dir) for name, sid in MACRO_SERIES.items()}
        return cls(spot=spot, rates=rates, reer=reer, macro=macro)
```
(Keep the existing `spot`/`rates`/`reer` loading in `from_fred` exactly; only add the `macro` line and the `MACRO_SERIES` import and the `macro=macro` in the return.)

In `forex/data/refresh.py`:
```python
from forex.config import CURRENCIES, MACRO_SERIES
...
        if cur.reer_fred:
            ids.append(cur.reer_fred)
    ids += list(MACRO_SERIES.values())
    for sid in ids:
        loader(sid, cache_dir=cache_dir, force=True)
    return ids
```

In `tests/test_carry_baseline.py` (both `series = {...}` dicts) and `tests/test_overlay.py` (its `series` dict), add the 3 macro ids over that dict's own `dates` index (so `from_fred` doesn't KeyError):
```python
        "VIXCLS": pd.Series(20.0, index=dates, name="value"),
        "BAMLH0A0HYM2": pd.Series(4.0, index=dates, name="value"),
        "T10Y2Y": pd.Series(1.0, index=dates, name="value"),
```

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_config.py tests/test_dataview.py tests/test_refresh.py tests/test_carry_baseline.py tests/test_overlay.py -v && python -m pytest -q`
Expected: PASS (whole suite green; the loader fixes keep the research tests working).

- [ ] **Step 5: Commit**

```bash
git add forex/config.py forex/core/dataview.py forex/data/refresh.py tests/test_config.py tests/test_dataview.py tests/test_refresh.py tests/test_carry_baseline.py tests/test_overlay.py
git commit -m "feat: global DataView.macro channel (VIX/HY-OAS/term) + download

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `HARVolForecaster` exogenous features + standardization

**Files:**
- Modify: `strategies/features/mlvol.py`
- Test: `tests/test_mlvol.py`

**Interfaces:**
- Produces: `HARVolForecaster` with `_features(returns, exog=None)`, `fit(returns, exog=None, horizon=21, alpha=1.0)`, `predict(returns, exog=None)`, and `mean_`/`std_` state (set only when `exog` is present).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_mlvol.py` (it already has `_regime_returns()` and imports `HARVolForecaster`):
```python
def test_exog_none_is_byte_identical():
    r = _regime_returns()
    f = HARVolForecaster().fit(r, horizon=21, alpha=1.0)
    assert len(f.coef_) == 4 and f.mean_ is None       # no exog -> 4 coefs, no standardization

def test_exog_adds_features_and_standardizes():
    import numpy as np, pandas as pd
    r = _regime_returns()
    # an exog column that tracks the realized-vol regime (informative)
    ex = pd.DataFrame({"risk": (r.abs().rolling(21).mean() * 20).fillna(0.0)}, index=r.index)
    f = HARVolForecaster().fit(r, exog=ex, horizon=21, alpha=1.0)
    assert len(f.coef_) == 1 + 3 + 1                    # intercept + 3 RV + 1 exog
    assert f.mean_ is not None and f.std_ is not None    # standardization stored
    pred = f.predict(r, exog=ex)
    assert pred.iloc[300:].notna().any()                 # produces forecasts
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mlvol.py -v`
Expected: FAIL — `fit()` has no `exog` kwarg / `mean_` attr missing.

- [ ] **Step 3: Write minimal implementation**

Replace `strategies/features/mlvol.py` with (the `exog=None` paths reproduce the current behaviour exactly):
```python
import numpy as np
import pandas as pd

class HARVolForecaster:
    """HAR-RV ridge forecaster of forward annualised realised volatility (log-vol space).
    Optionally accepts exogenous features; standardizes the feature matrix when exog is present."""
    WINDOWS = (5, 21, 63)

    def __init__(self):
        self.coef_ = None
        self.fitted = False
        self.mean_ = None
        self.std_ = None

    def _features(self, returns, exog=None):
        feats = {}
        for w in self.WINDOWS:
            rv = (returns.pow(2).rolling(w).mean() * 252) ** 0.5
            feats[f"rv{w}"] = np.log(rv.clip(lower=1e-8))
        X = pd.DataFrame(feats)
        if exog is not None:
            X = X.join(exog)
        return X

    def fit(self, returns, exog=None, horizon: int = 21, alpha: float = 1.0):
        X = self._features(returns, exog)
        fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
        y = np.log(fwd.clip(lower=1e-8))
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

    def predict(self, returns, exog=None):
        X = self._features(returns, exog)
        Xv = X.values
        if self.mean_ is not None:
            Xv = (Xv - self.mean_) / self.std_
        Xm = np.column_stack([np.ones(len(X)), Xv])
        return pd.Series(np.exp(Xm @ self.coef_), index=X.index, name="vol_forecast")
```

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_mlvol.py -v && python -m pytest -q`
Expected: PASS — new tests + the pre-existing `test_har_*` tests (which use the no-exog path) + whole suite. If any existing `test_mlvol`/`test_mloverlay` result changed, STOP (the `exog=None` path must be byte-identical).

- [ ] **Step 5: Commit**

```bash
git add strategies/features/mlvol.py tests/test_mlvol.py
git commit -m "feat: HARVolForecaster exogenous features + fit-window standardization

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `MLVolTargetOverlay` macro wiring + `carry_voltarget_xasset`

**Files:**
- Modify: `strategies/overlay.py`, `strategies/mloverlay.py`, `strategies/carry.py`
- Test: `tests/test_overlay_strategy.py`, `tests/test_mloverlay.py`, `tests/test_discovery.py`

**Interfaces:**
- Consumes: `DataView.macro` (Task 1), `HARVolForecaster` exog (Task 2).
- Produces: `VolTargetOverlay._vol_forecast(base_ret, view)`; `MLVolTargetOverlay(base, …, use_macro=False)` with `_build_exog`; registry name `carry_voltarget_xasset`.

- [ ] **Step 1: Write / update the failing tests**

In `tests/test_overlay_strategy.py`, update `test_vol_forecast_defaults_to_ewma` — its call becomes `ov._vol_forecast(base_ret, None)` (the base ignores the new `view` arg).

Append to `tests/test_mloverlay.py` (it has a `_view()` helper — add a macro-carrying view):
```python
def _macro_view():
    v = _view()
    idx = v.calendar
    import numpy as np
    v.macro = {"vix": pd.Series(15.0 + 5*np.sin(np.arange(len(idx))/50), index=idx),
               "hy_oas": pd.Series(4.0 + np.linspace(0, 1, len(idx)), index=idx),
               "term": pd.Series(1.0 - np.linspace(0, 0.5, len(idx)), index=idx)}
    return v

def test_build_exog_has_three_columns():
    from strategies.mloverlay import MLVolTargetOverlay
    from strategies.carry import CarryStrategy
    v = _macro_view()
    ov = MLVolTargetOverlay(CarryStrategy(1, 1), use_macro=True, cadence="D")
    ex = ov._build_exog(v, v.calendar)
    assert list(ex.columns) == ["vix", "hy_oas", "term"] and len(ex) == len(v.calendar)

def test_xasset_is_causal_and_finite():
    from strategies.mloverlay import MLVolTargetOverlay
    from strategies.carry import CarryStrategy
    from forex.run.backtest import backtest
    from forex.core.result import Result
    v = _macro_view()
    ov = MLVolTargetOverlay(CarryStrategy(1, 1), use_macro=True, cadence="D")
    ov.fit(v)
    assert_causal(ov, v, v.calendar[[200, 400, 699]])
    r = backtest(ov, v, cost_bps=1.0)
    assert isinstance(r, Result) and np.isfinite(r.metrics["sharpe"])
```

Append to `tests/test_discovery.py`:
```python
def test_carry_voltarget_xasset_uses_macro():
    from strategies.mloverlay import MLVolTargetOverlay
    from strategies.carry import CarryStrategy
    s = build_strategy("carry_voltarget_xasset", {"n_long": 1, "n_short": 1, "target_vol": 0.1}, "strategies")
    assert isinstance(s, MLVolTargetOverlay) and s.use_macro is True
    assert isinstance(s.base, CarryStrategy) and s.base.n_long == 1 and s.target_vol == 0.1
```
Also add `"carry_voltarget_xasset"` to the `_ALL` list and the `available()` set assertion in `tests/test_discovery.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_overlay_strategy.py tests/test_mloverlay.py tests/test_discovery.py -v`
Expected: FAIL — `_vol_forecast` arity / `use_macro` / `_build_exog` / unknown `carry_voltarget_xasset`.

- [ ] **Step 3: Write minimal implementation**

In `strategies/overlay.py`, add the `view` param to `_vol_forecast` and pass it in `target_weights`:
```python
    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import returns_of
        w = self.base.target_weights(view)
        base_ret = returns_of(w, view, self.cost_bps)
        vf = self._vol_forecast(base_ret, view).reindex(w.index).ffill()
        raw = (self.target_vol / vf).clip(upper=self.cap)
        L = raw.resample(self.cadence).first().reindex(w.index, method="ffill")
        return w.mul(L, axis=0)

    def _vol_forecast(self, base_ret, view):
        return ewma_vol(base_ret, lam=self.lam)
```

Replace `strategies/mloverlay.py` with (add `numpy`, `use_macro`, `_build_exog`, thread exog):
```python
import numpy as np
import pandas as pd
from forex.core.dataview import DataView
from strategies.overlay import VolTargetOverlay
from strategies.features.mlvol import HARVolForecaster
from forex.features.volforecast import ewma_vol

class MLVolTargetOverlay(VolTargetOverlay):
    def __init__(self, base, *, horizon: int = 21, ridge_alpha: float = 1.0,
                 use_macro: bool = False, **kw):
        super().__init__(base, **kw)
        self.horizon = horizon
        self.ridge_alpha = ridge_alpha
        self.use_macro = use_macro
        self.forecaster = HARVolForecaster()

    def _build_exog(self, view, index):
        m = view.macro
        ex = pd.DataFrame(index=index)
        ex["vix"] = np.log(m["vix"].reindex(index, method="ffill"))
        ex["hy_oas"] = np.log(m["hy_oas"].reindex(index, method="ffill"))
        ex["term"] = m["term"].reindex(index, method="ffill")
        return ex

    def fit(self, train: DataView) -> None:
        from forex.run.backtest import backtest
        self.base.fit(train)
        base_ret = backtest(self.base, train, cost_bps=self.cost_bps).returns
        exog = self._build_exog(train, base_ret.index) if self.use_macro else None
        self.forecaster.fit(base_ret, exog=exog, horizon=self.horizon, alpha=self.ridge_alpha)

    def _vol_forecast(self, base_ret, view):
        exog = self._build_exog(view, base_ret.index) if self.use_macro else None
        if not self.forecaster.fitted:
            self.forecaster.fit(base_ret, exog=exog, horizon=self.horizon, alpha=self.ridge_alpha)
        har = self.forecaster.predict(base_ret, exog=exog)
        return har.fillna(ewma_vol(base_ret, lam=self.lam))

    def params(self) -> dict:
        return {**super().params(), "horizon": self.horizon, "ridge_alpha": self.ridge_alpha}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {**super().search_space(), "horizon": Int(10, 42)}
```

In `strategies/carry.py`, add the registered variant next to `CarryVolTargetML`:
```python
class CarryVolTargetXAsset(MLVolTargetOverlay):
    NAME = "carry_voltarget_xasset"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base), use_macro=True, **overlay)
```
(`carry.py` already imports `MLVolTargetOverlay` and `split_params`.)

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_overlay_strategy.py tests/test_mloverlay.py tests/test_discovery.py -v && python -m pytest -q`
Expected: PASS. The existing `carry_voltarget_ml` (use_macro=False) path is unchanged. If a pre-existing result changed (beyond the one-arg→two-arg `_vol_forecast` test update), STOP and report BLOCKED.

- [ ] **Step 5: Commit**

```bash
git add strategies/overlay.py strategies/mloverlay.py strategies/carry.py tests/test_overlay_strategy.py tests/test_mloverlay.py tests/test_discovery.py
git commit -m "feat: MLVolTargetOverlay macro wiring + carry_voltarget_xasset

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- `carry_voltarget_ml` must stay behaviourally identical (use_macro=False → exog=None → the forecaster's no-exog, no-standardization path). Only the `_vol_forecast` arity changes (a mechanical two-arg signature), which the base ignores.
- `_build_exog` uses `reindex(index, method="ffill")` (as-of ≤ date) for causality; keep the transforms exactly (`log` vix/hy_oas, raw term).
- Do not add `use_macro` to `params()`/`search_space()` — it's a structural variant flag.
- The macro history starts ~1997; pre-1997 exog is NaN and the `har.fillna(ewma_vol(...))` fallback covers it — do not add special-casing.

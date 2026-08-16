# Cross-Asset ML Vol Features (v2) — Design Spec

*Design spec. Status: approved 2026-07-14. The v2 lever for the ML vol overlay: add global risk-off
series (VIX, high-yield credit, term spread) as exogenous features to the HAR realised-vol forecaster,
on the hypothesis they carry carry-crash information the base strategy's own realised vol (and thus
EWMA) doesn't. Judged on the same ship gate as the original ML overlay: it beats EWMA on walk-forward
or it doesn't ship as the default.*

## Goal & success criteria
- A new global `DataView.macro` channel + the 3 FRED series; the HAR forecaster accepts exogenous
  features; `MLVolTargetOverlay` can wire the macro features in; a registered `carry_voltarget_xasset`
  for the A/B.
- **`carry_voltarget_ml` (price-only) stays byte-identical** — the exog path is additive and off by
  default.
- Success: full suite green (with synthetic macro in tests); a clean 3-way walk-forward comparison is
  runnable (`carry_voltarget` EWMA vs `carry_voltarget_ml` price-HAR vs `carry_voltarget_xasset`
  macro-HAR). **Ship gate:** keep the macro overlay as the preferred ML variant only if it beats EWMA
  OOS; otherwise record the negative result (EWMA/price-HAR stays).

## Feature set (decided)
The risk trio — global, daily, free on FRED:
| key | FRED id | transform |
|---|---|---|
| `vix` | `VIXCLS` (CBOE VIX) | `log` |
| `hy_oas` | `BAMLH0A0HYM2` (ICE BofA US HY OAS) | `log` |
| `term` | `T10Y2Y` (10y−2y Treasury) | raw |
History is bounded by HY OAS (~1997); before that the exog is NaN and the existing EWMA fallback covers
it, so the long carry history still runs.

## ⚠️ One-time re-download required
`from_fred` will load the macro series for every view (consistent with how `rates`/`reer` load). The
current `data_cache/` has no macro series, so **after this lands the user must run `forex download`
once** (which now includes the macro ids) before any live-data run. Tests are unaffected (they inject
loaders that provide the macro series).

## Components

### 1. Data plumbing
- **`forex/config.py`**: `MACRO_SERIES = {"vix": "VIXCLS", "hy_oas": "BAMLH0A0HYM2", "term": "T10Y2Y"}`
  (global — NOT per-currency, so not in `CURRENCIES`).
- **`forex/core/dataview.py`**: add `macro: dict = field(default_factory=dict)`; `truncate` clips it
  (`{k: v.loc[:asof] for k, v in self.macro.items()}`); `from_fred` loads it:
  `macro = {name: loader(sid, cache_dir=cache_dir) for name, sid in MACRO_SERIES.items()}`.
- **`forex/data/refresh.py`**: append `list(MACRO_SERIES.values())` to the refreshed ids so
  `forex download` fetches them.
- The restricted synthetic loaders in `tests/test_carry_baseline.py` and `tests/test_overlay.py` (which
  look up `series[series_id]`) need the 3 macro ids added, exactly like the earlier `reer` fix (else
  `from_fred` KeyErrors there).

### 2. Forecaster exog + standardization (`strategies/features/mlvol.py`)
```python
class HARVolForecaster:
    WINDOWS = (5, 21, 63)
    def __init__(self):
        self.coef_ = None; self.fitted = False; self.mean_ = None; self.std_ = None

    def _features(self, returns, exog=None):
        feats = {}
        for w in self.WINDOWS:
            rv = (returns.pow(2).rolling(w).mean() * 252) ** 0.5
            feats[f"rv{w}"] = np.log(rv.clip(lower=1e-8))
        X = pd.DataFrame(feats)
        if exog is not None:
            X = X.join(exog)                       # align on the return index
        return X

    def fit(self, returns, exog=None, horizon=21, alpha=1.0):
        X = self._features(returns, exog)
        fwd = (returns.pow(2).rolling(horizon).mean().shift(-horizon) * 252) ** 0.5
        y = np.log(fwd.clip(lower=1e-8))
        d = X.assign(_y=y).dropna()
        Xv = d[X.columns].values
        if exog is not None:                        # standardize only when exog present (mixed scales)
            self.mean_ = Xv.mean(axis=0); self.std_ = Xv.std(axis=0)
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
- **`exog=None` → byte-identical to today** (no join, no standardization) — `carry_voltarget_ml`
  unaffected.
- Standardization (store `mean_`/`std_` from the training features, apply in `predict`) makes the ridge
  scale-fair across the mixed-scale exog + RV features; it kicks in only when exog is present.
- NaN exog rows (pre-1997) drop out in `fit` and yield NaN in `predict` → handled by the overlay's
  existing EWMA fallback.

### 3. Overlay wiring (`strategies/overlay.py`, `strategies/mloverlay.py`, `strategies/carry.py`)
- **`VolTargetOverlay._vol_forecast` gains a `view` param** so an ML subclass can reach `view.macro`;
  the base ignores it. `target_weights` passes `view`:
  ```python
      vf = self._vol_forecast(base_ret, view).reindex(w.index).ffill()
      ...
      def _vol_forecast(self, base_ret, view):
          return ewma_vol(base_ret, lam=self.lam)
  ```
  (Update the existing `test_vol_forecast_defaults_to_ewma` to call `_vol_forecast(base_ret, None)`.)
- **`MLVolTargetOverlay`** gains `use_macro: bool = False`, a `_build_exog(view, index)`, and threads
  exog through `fit`/`_vol_forecast`:
  ```python
      def __init__(self, base, *, horizon=21, ridge_alpha=1.0, use_macro=False, **kw):
          super().__init__(base, **kw)
          self.horizon = horizon; self.ridge_alpha = ridge_alpha; self.use_macro = use_macro
          self.forecaster = HARVolForecaster()

      def _build_exog(self, view, index):
          m = view.macro
          ex = pd.DataFrame(index=index)
          ex["vix"] = np.log(m["vix"].reindex(index, method="ffill"))
          ex["hy_oas"] = np.log(m["hy_oas"].reindex(index, method="ffill"))
          ex["term"] = m["term"].reindex(index, method="ffill")
          return ex

      def fit(self, train):
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
  ```
  `use_macro` is a **structural** flag (it defines the strategy variant), so it is NOT in
  `params()`/`search_space()`.
- **`strategies/carry.py`**: register the A/B variant (co-located with `CarryVolTargetML`):
  ```python
  class CarryVolTargetXAsset(MLVolTargetOverlay):
      NAME = "carry_voltarget_xasset"
      @classmethod
      def build(cls, params):
          base, overlay = split_params(params, ("n_long", "n_short"))
          return cls(CarryStrategy(**base), use_macro=True, **overlay)
  ```

### Causality
`_build_exog` aligns each macro series **as-of ≤ each date** (`reindex(index, method="ffill")`), so the
forecast at *t* uses only macro known by *t* (daily closes) plus trailing RV — truncation-invariant.
`carry_voltarget_xasset` must pass `causal-check` (fit first, then the fixed coefficients + as-of exog).

## Testing (all offline, no network)
- **`DataView.macro`** — defaults empty; `truncate` clips it; `from_fred` (injected loader) populates
  `macro` with the 3 keys. (Update the two restricted synthetic loaders to include the macro ids.)
- **`MACRO_SERIES`** present with the 3 ids; **`refresh_cache`** includes them.
- **`HARVolForecaster` exog** — `fit(returns, exog=None)` is byte-identical to the old fit (no
  standardization, `coef_` length 4); with a synthetic exog whose column correlates with forward vol,
  `fit` sets `mean_`/`std_`, `coef_` length is `1 + 3 + n_exog`, and `predict` responds to the exog.
- **`MLVolTargetOverlay(use_macro=True)`** — `_build_exog` returns the 3 transformed columns aligned to
  the index; `carry_voltarget_xasset` builds via discovery with `use_macro=True`; `assert_causal`
  passes (fit first) on a synthetic view carrying `macro`; an integration backtest is finite; the
  `use_macro=False` path (existing `carry_voltarget_ml`) is unchanged.
- Full suite green.

## Validation (post-merge, user runs `forex download` first)
Walk-forward `carry_voltarget` vs `carry_voltarget_ml` vs `carry_voltarget_xasset` (train/test days as
before), on the macro-available window. Record: does the cross-asset HAR beat EWMA (and the price-only
HAR)? If yes → the new preferred ML overlay (and worth trying on the blend). If no → record "non-price
vol features don't beat EWMA on G10 either"; EWMA stays the default; the ML overlay track is exhausted.

## Out of scope (YAGNI)
- COT positioning / central-bank NLP features (a further data-plumbing project).
- A macro variant of the *blend* overlay — first prove it on carry (the original gate).
- Feature selection / z-scoring beyond the fit-window standardization above.
- Making `from_fred` tolerant of a missing macro series (the one-time re-download is the intended path).

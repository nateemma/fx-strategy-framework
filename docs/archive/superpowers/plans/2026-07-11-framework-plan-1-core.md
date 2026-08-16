# FX Framework — Plan 1: Core Abstractions + Strategy Refactor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the framework core — `DataView`, `Strategy`, `Result`, the `backtest` and `walk_forward` drivers, and `assert_causal` — and move the two existing strategies (bare carry, carry + vol-target) onto it, reimplementing `run_baseline`/`run_overlay` as thin delegators so all 27 existing tests stay green.

**Architecture:** The atom is `Strategy.target_weights(view) -> causal weight matrix`; drivers call it (backtest over history, walk_forward over rolling windows, assert_causal truncated-at-t). Strategies wrap the existing, unchanged signal functions (`carry_signal`, `basket_weights`, `ewma_vol`), so this is a repackaging + rewiring, not a signal rewrite.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. Reuses `forex.data.*`, `forex.features.*`, `forex.backtest.portfolio` (`simulate`, `metrics`).

## Global Constraints
- Project root `~/Documents/forex`; code under `forex/`, tests under `tests/`; venv `~/Documents/forex/.venv` (`.venv/bin/python -m pytest`).
- **No lookahead:** `target_weights` rows are causal (data through their own date); the backtester applies `weights.shift(1)` (do NOT pre-shift inside strategies).
- **Behavior-preserving:** the two existing research entrypoints keep their signatures and outputs. `run_baseline` must stay byte-identical. `run_overlay`'s *gross* return is identical; only the leverage-turnover cost accounting is unified (sub-1bp effect) — no existing test pins its exact numbers.
- Tests must not hit the network (inject loaders / build views directly). Commit after every task (conventional commits).

---

## File Structure
- `forex/core/dataview.py` — `DataView` dataclass (`spot`, `rates`) + `truncate` + `from_fred`.
- `forex/core/result.py` — `Result` dataclass.
- `forex/core/strategy.py` — `Strategy` ABC.
- `forex/strategies/carry.py` — `CarryStrategy`.
- `forex/strategies/overlay.py` — `VolTargetOverlay`.
- `forex/run/backtest.py` — `backtest`.
- `forex/run/walkforward.py` — `walk_forward`.
- `forex/diagnostics/causal.py` — `assert_causal`.
- `forex/research/carry_baseline.py`, `forex/research/overlay.py` — reimplemented delegators.
- new `__init__.py` for `forex/core`, `forex/strategies`, `forex/run`, `forex/diagnostics`.
- tests alongside each.

---

### Task 1: DataView

**Files:** Create `forex/core/__init__.py`, `forex/core/dataview.py`, `tests/test_dataview.py`

**Interfaces:**
- Produces: `DataView` dataclass with fields `spot: pd.DataFrame` (dates×non-USD codes, USD-per-foreign) and `rates: dict[str, pd.Series]` (code→annualized-decimal short rate, incl `"USD"`). Properties `codes` (list of spot columns) and `calendar` (spot index). `truncate(asof) -> DataView` clips `spot` and every `rates` series to index ≤ asof. Classmethod `from_fred(cache_dir, loader=load_series, codes=None) -> DataView` builds it (spot via `build_spot_panel`, rates via `load_series(...)/100.0`, USD included).

- [ ] **Step 1: Write the failing test**

`tests/test_dataview.py`:
```python
import pandas as pd
from forex.core.dataview import DataView

def _view():
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    spot = pd.DataFrame({"AUD": range(5), "EUR": range(5)}, index=idx).astype(float)
    rates = {"USD": pd.Series([0.01]*5, index=idx), "AUD": pd.Series([0.05]*5, index=idx),
             "EUR": pd.Series([0.0]*5, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_codes_and_calendar():
    v = _view()
    assert v.codes == ["AUD", "EUR"]
    assert len(v.calendar) == 5

def test_truncate_clips_spot_and_rates():
    v = _view().truncate("2020-01-03")
    assert v.spot.index.max() == pd.Timestamp("2020-01-03")
    assert v.rates["AUD"].index.max() == pd.Timestamp("2020-01-03")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dataview.py -v` → FAIL (`No module named 'forex.core.dataview'`).

- [ ] **Step 3: Write minimal implementation**

`forex/core/__init__.py`: (empty)

`forex/core/dataview.py`:
```python
from dataclasses import dataclass
import pandas as pd

@dataclass
class DataView:
    spot: pd.DataFrame
    rates: dict

    @property
    def codes(self) -> list:
        return list(self.spot.columns)

    @property
    def calendar(self) -> pd.DatetimeIndex:
        return self.spot.index

    def truncate(self, asof) -> "DataView":
        asof = pd.Timestamp(asof)
        spot = self.spot.loc[:asof]
        rates = {k: v.loc[:asof] for k, v in self.rates.items()}
        return DataView(spot=spot, rates=rates)

    @classmethod
    def from_fred(cls, cache_dir, loader=None, codes=None) -> "DataView":
        from forex.config import CURRENCIES
        from forex.data.prices import build_spot_panel
        from forex.data.fred import load_series
        if loader is None:
            loader = load_series
        if codes is None:
            codes = [c for c in CURRENCIES if c != "USD"]
        spot = build_spot_panel(cache_dir, loader=loader, codes=codes)
        rates = {"USD": loader(CURRENCIES["USD"].rate_fred, cache_dir=cache_dir) / 100.0}
        for c in codes:
            rates[c] = loader(CURRENCIES[c].rate_fred, cache_dir=cache_dir) / 100.0
        return cls(spot=spot, rates=rates)
```

- [ ] **Step 4: Run tests** → `.venv/bin/python -m pytest tests/test_dataview.py -v` → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/core/__init__.py forex/core/dataview.py tests/test_dataview.py
git commit -m "feat: DataView (point-in-time data bundle + truncate + from_fred)"
```

---

### Task 2: Strategy ABC + Result

**Files:** Create `forex/core/result.py`, `forex/core/strategy.py`, `tests/test_strategy_base.py`

**Interfaces:**
- Produces: `Result` dataclass (`returns: pd.Series`, `weights: pd.DataFrame`, `metrics: dict`).
  `Strategy` ABC: `fit(train: DataView) -> None` (default no-op), abstract `target_weights(view: DataView) -> pd.DataFrame`, `params() -> dict` (default `{}`), `search_space() -> dict` (default `{}`).

- [ ] **Step 1: Write the failing test**

`tests/test_strategy_base.py`:
```python
import pandas as pd
from forex.core.strategy import Strategy
from forex.core.result import Result
from forex.core.dataview import DataView

class _Const(Strategy):
    def target_weights(self, view):
        return pd.DataFrame(1.0, index=view.calendar, columns=view.codes)

def _view():
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    return DataView(spot=pd.DataFrame({"AUD": [1.0]*3}, index=idx), rates={"USD": pd.Series([0.0]*3, index=idx)})

def test_defaults():
    s = _Const()
    assert s.params() == {} and s.search_space() == {}
    assert s.fit(_view()) is None                       # no-op default
    w = s.target_weights(_view())
    assert list(w.columns) == ["AUD"] and (w == 1.0).all().all()

def test_result_holds_fields():
    r = Result(returns=pd.Series([0.1]), weights=pd.DataFrame({"AUD":[1.0]}), metrics={"sharpe": 1.0})
    assert r.metrics["sharpe"] == 1.0
```

- [ ] **Step 2: Run** → FAIL (`No module named 'forex.core.strategy'`).

- [ ] **Step 3: Write minimal implementation**

`forex/core/result.py`:
```python
from dataclasses import dataclass
import pandas as pd

@dataclass
class Result:
    returns: pd.Series
    weights: pd.DataFrame
    metrics: dict
```

`forex/core/strategy.py`:
```python
from abc import ABC, abstractmethod
import pandas as pd
from forex.core.dataview import DataView

class Strategy(ABC):
    def fit(self, train: DataView) -> None:
        return None

    @abstractmethod
    def target_weights(self, view: DataView) -> pd.DataFrame:
        ...

    def params(self) -> dict:
        return {}

    def search_space(self) -> dict:
        return {}
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/core/result.py forex/core/strategy.py tests/test_strategy_base.py
git commit -m "feat: Strategy ABC (fit/target_weights/params/search_space) + Result"
```

---

### Task 3: CarryStrategy

**Files:** Create `forex/strategies/__init__.py`, `forex/strategies/carry.py`, `tests/test_carry_strategy.py`

**Interfaces:**
- Consumes: `Strategy`, `DataView`, `carry_signal`, `basket_weights`.
- Produces: `CarryStrategy(n_long=3, n_short=3)`; `target_weights(view)` = `basket_weights(carry_signal(view.calendar, view.rates)[view.codes], n_long, n_short)`; `params()` = `{"n_long":…, "n_short":…}`.

- [ ] **Step 1: Write the failing test**

`tests/test_carry_strategy.py`:
```python
import pandas as pd
from forex.core.dataview import DataView
from forex.strategies.carry import CarryStrategy

def test_carry_strategy_weights_are_dollar_neutral():
    idx = pd.date_range("2020-01-01", periods=2, freq="D")
    spot = pd.DataFrame({"AUD":[1.0,1.0], "EUR":[1.1,1.1]}, index=idx)
    rates = {"USD": pd.Series([0.01,0.01], index=idx),
             "AUD": pd.Series([0.06,0.06], index=idx),   # high carry -> long
             "EUR": pd.Series([0.0,0.0], index=idx)}      # low carry -> short
    w = CarryStrategy(n_long=1, n_short=1).target_weights(DataView(spot=spot, rates=rates))
    assert w.loc[idx[0], "AUD"] == 1.0 and w.loc[idx[0], "EUR"] == -1.0
    assert abs(w.loc[idx[0]].sum()) < 1e-9
    assert CarryStrategy(2, 2).params() == {"n_long": 2, "n_short": 2}
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/strategies/__init__.py`: (empty)

`forex/strategies/carry.py`:
```python
import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.carry import carry_signal, basket_weights

class CarryStrategy(Strategy):
    def __init__(self, n_long: int = 3, n_short: int = 3):
        self.n_long = n_long
        self.n_short = n_short

    def target_weights(self, view: DataView) -> pd.DataFrame:
        signal = carry_signal(view.calendar, view.rates)
        return basket_weights(signal[view.codes], n_long=self.n_long, n_short=self.n_short)

    def params(self) -> dict:
        return {"n_long": self.n_long, "n_short": self.n_short}
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/strategies/__init__.py forex/strategies/carry.py tests/test_carry_strategy.py
git commit -m "feat: CarryStrategy on the Strategy interface"
```

---

### Task 4: backtest driver

**Files:** Create `forex/run/__init__.py`, `forex/run/backtest.py`, `tests/test_backtest_driver.py`

**Interfaces:**
- Consumes: `Strategy`, `DataView`, `Result`, `spot_returns`, `carry_signal`, `simulate`, `metrics`.
- Produces: `backtest(strategy, view, cost_bps=1.0) -> Result`. Computes `weights = strategy.target_weights(view)`, `rets = spot_returns(view.spot)`, `carry = carry_signal(view.calendar, view.rates)[weights.columns].fillna(0.0)`, `daily = simulate(weights, rets, carry, cost_bps)`, returns `Result(daily, weights, metrics(daily))`. Carry accrual comes from the view (a market fact), so `backtest` is strategy-agnostic.

- [ ] **Step 1: Write the failing test**

`tests/test_backtest_driver.py`:
```python
import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.strategies.carry import CarryStrategy
from forex.run.backtest import backtest
from forex.core.result import Result

def _view():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.2,300), "EUR": 1.1+np.zeros(300)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_backtest_returns_result_with_positive_carry():
    r = backtest(CarryStrategy(1,1), _view(), cost_bps=1.0)
    assert isinstance(r, Result)
    assert r.metrics["total_return"] > 0            # long high-carry rising AUD, short flat EUR
    assert len(r.returns) == len(r.weights)
    assert "sharpe" in r.metrics
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/run/__init__.py`: (empty)

`forex/run/backtest.py`:
```python
from forex.core.result import Result
from forex.data.prices import spot_returns
from forex.features.carry import carry_signal
from forex.backtest.portfolio import simulate, metrics

def backtest(strategy, view, cost_bps: float = 1.0) -> Result:
    weights = strategy.target_weights(view)
    rets = spot_returns(view.spot)
    carry = carry_signal(view.calendar, view.rates)[list(weights.columns)].fillna(0.0)
    daily = simulate(weights, rets, carry=carry, cost_bps=cost_bps)
    return Result(returns=daily, weights=weights, metrics=metrics(daily))
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/run/__init__.py forex/run/backtest.py tests/test_backtest_driver.py
git commit -m "feat: backtest driver (Strategy + DataView -> Result)"
```

---

### Task 5: Reimplement run_baseline on the framework (behavior-preserving)

**Files:** Modify `forex/research/carry_baseline.py` (the `run_baseline` function body only; leave `__main__`). Test: `tests/test_carry_baseline.py` (existing, must stay green) + add one equivalence test.

**Interfaces:**
- `run_baseline(cache_dir, loader=load_series, codes=None, n_long=3, n_short=3, cost_bps=1.0)` unchanged signature; now delegates to `DataView.from_fred` + `backtest(CarryStrategy(...))` and returns `(result.returns, result.metrics)` — the same `(daily, metrics)` tuple as before.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_carry_baseline.py`:
```python
def test_run_baseline_matches_backtest_of_carry_strategy():
    from forex.core.dataview import DataView
    from forex.strategies.carry import CarryStrategy
    from forex.run.backtest import backtest
    loader = _synthetic_loader()   # existing helper in this test file
    daily, m = run_baseline(cache_dir="unused", loader=loader, codes=["AUD","EUR"], n_long=1, n_short=1)
    view = DataView.from_fred("unused", loader=loader, codes=["AUD","EUR"])
    r = backtest(CarryStrategy(1,1), view, cost_bps=1.0)
    assert (daily.round(10) == r.returns.round(10)).all()     # byte-identical delegation
    assert m == r.metrics
```

- [ ] **Step 2: Run** → `.venv/bin/python -m pytest tests/test_carry_baseline.py -v` → the new test FAILS (run_baseline not yet delegating identically) or ERRORs; existing tests still pass.

- [ ] **Step 3: Rewrite `run_baseline`**

Replace the `run_baseline` function in `forex/research/carry_baseline.py` with:
```python
def run_baseline(cache_dir, loader=load_series, codes=None,
                 n_long=3, n_short=3, cost_bps=1.0):
    from forex.core.dataview import DataView
    from forex.strategies.carry import CarryStrategy
    from forex.run.backtest import backtest
    view = DataView.from_fred(cache_dir, loader=loader, codes=codes)
    r = backtest(CarryStrategy(n_long=n_long, n_short=n_short), view, cost_bps=cost_bps)
    return r.returns, r.metrics
```
Keep the existing top-of-file imports that `__main__` still uses; leave the `__main__` block unchanged.

- [ ] **Step 4: Run full suite** → `.venv/bin/python -m pytest -q` → ALL pass (the new equivalence test + all pre-existing tests, incl `test_carry_baseline` and the overlay tests that call `run_baseline`).

- [ ] **Step 5: Commit**
```bash
git add forex/research/carry_baseline.py tests/test_carry_baseline.py
git commit -m "refactor: run_baseline delegates to backtest(CarryStrategy) (behavior-preserving)"
```

---

### Task 6: VolTargetOverlay

**Files:** Create `forex/strategies/overlay.py`, `tests/test_overlay_strategy.py`

**Interfaces:**
- Consumes: `Strategy`, `DataView`, `ewma_vol`, `backtest`.
- Produces: `VolTargetOverlay(base: Strategy, target_vol=0.10, cap=1.5, cadence="MS", lam=0.94, cost_bps=1.0)`. `fit` delegates to `base.fit`. `target_weights(view)` = `base_weights · L`, where `L = clip(target_vol/ewma_vol(base_returns), upper=cap)` stepped at `cadence` and **NOT** pre-shifted (the backtester applies the single `shift(1)`); `base_returns = backtest(base, view, cost_bps).returns`. `params()` = the four knobs.

- [ ] **Step 1: Write the failing test**

`tests/test_overlay_strategy.py`:
```python
import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.strategies.carry import CarryStrategy
from forex.strategies.overlay import VolTargetOverlay

def _view():
    idx = pd.date_range("2019-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.zeros(400)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_overlay_scales_base_weights_within_cap_and_preserves_zeros():
    v = _view()
    base = CarryStrategy(1, 1)
    bw = base.target_weights(v)
    ow = VolTargetOverlay(base, target_vol=0.10, cap=1.5, cadence="D").target_weights(v)
    assert ow.index.equals(bw.index) and list(ow.columns) == list(bw.columns)
    # leverage never exceeds cap: |overlay| <= cap*|base| everywhere
    assert (ow.abs() <= 1.5 * bw.abs() + 1e-9).all().all()
    # zero base weight -> zero overlay weight
    assert (ow[bw == 0].fillna(0.0) == 0.0).all().all()
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/strategies/overlay.py`:
```python
import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.volforecast import ewma_vol

class VolTargetOverlay(Strategy):
    def __init__(self, base: Strategy, target_vol: float = 0.10, cap: float = 1.5,
                 cadence: str = "MS", lam: float = 0.94, cost_bps: float = 1.0):
        self.base = base
        self.target_vol = target_vol
        self.cap = cap
        self.cadence = cadence
        self.lam = lam
        self.cost_bps = cost_bps

    def fit(self, train: DataView) -> None:
        self.base.fit(train)

    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import backtest
        w = self.base.target_weights(view)
        base_ret = backtest(self.base, view, cost_bps=self.cost_bps).returns
        vf = ewma_vol(base_ret, lam=self.lam).reindex(w.index).ffill()
        raw = (self.target_vol / vf).clip(upper=self.cap)
        L = raw.resample(self.cadence).first().reindex(w.index, method="ffill")
        return w.mul(L, axis=0)   # causal, NOT pre-shifted; backtest applies shift(1)

    def params(self) -> dict:
        return {"target_vol": self.target_vol, "cap": self.cap,
                "cadence": self.cadence, "lam": self.lam}
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/strategies/overlay.py tests/test_overlay_strategy.py
git commit -m "feat: VolTargetOverlay as a composable Strategy (leverage-as-weight-scaler)"
```

---

### Task 7: Reimplement run_overlay on the framework

**Files:** Modify `forex/research/overlay.py` (`run_overlay` body only; leave `__main__`). Test: `tests/test_overlay.py` (existing structural test stays green) + one sanity test.

**Interfaces:**
- `run_overlay(cache_dir, loader=load_series, codes=None, n_long=3, n_short=3, cost_bps=1.0, target_vol=0.10, cap=1.5, cadence="MS", lam=0.94)` unchanged signature and unchanged return dict `{bare, overlay, metrics_bare, metrics_overlay}`; now delegates: `bare = backtest(CarryStrategy)`, `overlay = backtest(VolTargetOverlay(CarryStrategy))`. Gross returns identical to before; leverage-turnover cost now unified in the levered weights (sub-1bp).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_overlay.py`:
```python
def test_run_overlay_delegates_and_overlay_differs_from_bare():
    out = run_overlay(cache_dir="unused", loader=_synthetic_loader(),
                      codes=["AUD","EUR"], n_long=1, n_short=1, cadence="D")
    assert set(out) == {"bare","overlay","metrics_bare","metrics_overlay"}
    # overlay is a levered version -> its return series is not identical to bare
    assert not out["bare"].equals(out["overlay"])
    assert "sharpe" in out["metrics_overlay"]
```

- [ ] **Step 2: Run** → `.venv/bin/python -m pytest tests/test_overlay.py -v` → new test may pass or fail depending on current impl; existing structural test passes. (After Step 3 both pass via the new path.)

- [ ] **Step 3: Rewrite `run_overlay`**

Replace the `run_overlay` function in `forex/research/overlay.py` with:
```python
def run_overlay(cache_dir, loader=load_series, codes=None, n_long=3, n_short=3,
                cost_bps=1.0, target_vol=0.10, cap=1.5, cadence="MS", lam=0.94):
    from forex.core.dataview import DataView
    from forex.strategies.carry import CarryStrategy
    from forex.strategies.overlay import VolTargetOverlay
    from forex.run.backtest import backtest
    view = DataView.from_fred(cache_dir, loader=loader, codes=codes)
    base = CarryStrategy(n_long=n_long, n_short=n_short)
    ov = VolTargetOverlay(base, target_vol=target_vol, cap=cap, cadence=cadence,
                          lam=lam, cost_bps=cost_bps)
    r_bare = backtest(base, view, cost_bps=cost_bps)
    r_ov = backtest(ov, view, cost_bps=cost_bps)
    return {"bare": r_bare.returns, "overlay": r_ov.returns,
            "metrics_bare": r_bare.metrics, "metrics_overlay": r_ov.metrics}
```
Update the top-of-file imports so `load_series`, `CarryStrategy`, etc. resolve; leave the `__main__` block unchanged.

- [ ] **Step 4: Run full suite** → `.venv/bin/python -m pytest -q` → ALL pass.

- [ ] **Step 5: Commit**
```bash
git add forex/research/overlay.py tests/test_overlay.py
git commit -m "refactor: run_overlay delegates to backtest(VolTargetOverlay) (gross-identical)"
```

- [ ] **Step 6: Live sanity (manual)**

Run `.venv/bin/python -m forex.research.overlay` against the FRED cache; confirm the vol-target row is still ~+416% / Sharpe ~0.36 / maxDD ~−25% (gross identical to the pre-refactor numbers; any change is sub-1bp cost accounting). Record it.

---

### Task 8: walk_forward driver

**Files:** Create `forex/run/walkforward.py`, `tests/test_walkforward.py`

**Interfaces:**
- Consumes: `Strategy`, `DataView`, `Result`, `backtest`, `forex.backtest.validation.walk_forward` (the existing split generator — imported as `wf_splits`), `metrics`.
- Produces: `walk_forward(strategy_factory, view, train_days, test_days, cost_bps=1.0) -> Result`. For each (train, test) split of `view.calendar`: build a fresh `strategy = strategy_factory()`, `strategy.fit(view.truncate(<last train date>))`, `r = backtest(strategy, view)`, take the **test-slice** of `r.returns`/`r.weights`; concatenate the test slices across folds into one OOS `Result` (metrics recomputed on the stitched returns). `strategy_factory` is a zero-arg callable returning a `Strategy`.

- [ ] **Step 1: Write the failing test**

`tests/test_walkforward.py`:
```python
import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.strategies.carry import CarryStrategy
from forex.run.walkforward import walk_forward
from forex.run.backtest import backtest
from forex.core.result import Result

def _view():
    idx = pd.date_range("2018-01-01", periods=800, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.4,800), "EUR": 1.1+np.zeros(800)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_walk_forward_stitches_oos_and_is_subset_of_full():
    v = _view()
    r = walk_forward(lambda: CarryStrategy(1,1), v, train_days=250, test_days=125)
    assert isinstance(r, Result)
    # OOS series is a proper subset of the full-history backtest dates
    full = backtest(CarryStrategy(1,1), v)
    assert set(r.returns.index).issubset(set(full.returns.index))
    assert len(r.returns) > 0 and "sharpe" in r.metrics
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/run/walkforward.py`:
```python
import pandas as pd
from forex.core.result import Result
from forex.run.backtest import backtest
from forex.backtest.portfolio import metrics
from forex.backtest.validation import walk_forward as wf_splits

def walk_forward(strategy_factory, view, train_days, test_days, cost_bps: float = 1.0) -> Result:
    cal = view.calendar
    rets_parts, wt_parts = [], []
    for train_sl, test_sl in wf_splits(cal, train_days, test_days):
        strat = strategy_factory()
        strat.fit(view.truncate(cal[train_sl][-1]))
        r = backtest(strat, view, cost_bps=cost_bps)
        test_idx = cal[test_sl]
        rets_parts.append(r.returns.reindex(test_idx).dropna())
        wt_parts.append(r.weights.reindex(test_idx).dropna(how="all"))
    oos_rets = pd.concat(rets_parts) if rets_parts else pd.Series(dtype=float)
    oos_wts = pd.concat(wt_parts) if wt_parts else pd.DataFrame()
    return Result(returns=oos_rets, weights=oos_wts, metrics=metrics(oos_rets))
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/run/walkforward.py tests/test_walkforward.py
git commit -m "feat: walk_forward driver (fit/evaluate/roll, stitched OOS Result)"
```

---

### Task 9: assert_causal (lookahead check)

**Files:** Create `forex/diagnostics/__init__.py`, `forex/diagnostics/causal.py`, `tests/test_causal.py`

**Interfaces:**
- Consumes: `Strategy`, `DataView`.
- Produces: `assert_causal(strategy, view, sample_dates) -> None` — for each t in `sample_dates`, compares `strategy.target_weights(view)` at row t against `strategy.target_weights(view.truncate(t))` at row t; raises `AssertionError` listing any t where they differ. This bakes in the truncation-invariance test.

- [ ] **Step 1: Write the failing test**

`tests/test_causal.py`:
```python
import numpy as np, pandas as pd, pytest
from forex.core.dataview import DataView
from forex.core.strategy import Strategy
from forex.strategies.carry import CarryStrategy
from forex.diagnostics.causal import assert_causal

def _view():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.zeros(400),
                         "SEK": 1.0+np.linspace(0,-0.1,400)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

class _Leaky(Strategy):
    def target_weights(self, view):
        # BAD: uses the FULL-sample max (a future value) -> not causal
        m = view.spot.max()
        return (view.spot == m).astype(float)

def test_carry_strategy_is_causal():
    v = _view()
    assert_causal(CarryStrategy(1,1), v, v.calendar[[100, 200, 399]])   # no raise

def test_leaky_strategy_is_flagged():
    v = _view()
    with pytest.raises(AssertionError):
        assert_causal(_Leaky(), v, v.calendar[[100, 200]])
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/diagnostics/__init__.py`: (empty)

`forex/diagnostics/causal.py`:
```python
import pandas as pd

def assert_causal(strategy, view, sample_dates) -> None:
    """Truncation-invariance: weights at t on the full view must equal weights at t
    on the view truncated at t. Any difference is lookahead."""
    full = strategy.target_weights(view)
    bad = []
    for t in pd.DatetimeIndex(sample_dates):
        trunc = strategy.target_weights(view.truncate(t))
        if t not in trunc.index or t not in full.index:
            bad.append((t, "missing"))
            continue
        a = full.loc[t].reindex(sorted(full.columns)).fillna(0.0)
        b = trunc.loc[t].reindex(sorted(full.columns)).fillna(0.0)
        if not (a.round(10) == b.round(10)).all():
            bad.append((t, "differs"))
    if bad:
        raise AssertionError(f"lookahead detected at {bad}")
```

- [ ] **Step 4: Run** → PASS (carry causal; leaky flagged).

- [ ] **Step 5: Commit**
```bash
git add forex/diagnostics/__init__.py forex/diagnostics/causal.py tests/test_causal.py
git commit -m "feat: assert_causal (truncation-invariance lookahead check)"
```

- [ ] **Step 6: Full suite** → `.venv/bin/python -m pytest -q` → all green (the original 27 + the new tests).

---

## Self-Review

**1. Spec coverage.** DataView(+truncate, from_fred) → Task 1 ✓. Strategy ABC (fit/target_weights/params/search_space) + Result → Task 2 ✓. CarryStrategy → Task 3 ✓. backtest → Task 4 ✓. run_baseline behavior-preserving delegate → Task 5 ✓. VolTargetOverlay (leverage-as-weight-scaler, no pre-shift) → Task 6 ✓. run_overlay delegate → Task 7 ✓. walk_forward (fit/evaluate/roll, stitched OOS) → Task 8 ✓. assert_causal (truncation-invariance) → Task 9 ✓. Explicitly OUT of scope (later plans, per spec): RunConfig/EnvConfig/registry/CLI, Execution/LiveRunner seam, the hyperopt driver + Space types. `search_space()` hook is present (Task 2, default `{}`).

**2. Placeholder scan.** No TBD/TODO; every code step is complete; every test step asserts real behavior. The one manual step (Task 7 Step 6) is a live-cache sanity run, labeled.

**3. Type consistency.** `DataView(spot, rates)` + `.codes`/`.calendar`/`.truncate`/`.from_fred` consistent (Tasks 1,3,4,6,8,9). `Strategy.target_weights(view)`/`fit`/`params`/`search_space` consistent (2,3,6). `Result(returns, weights, metrics)` consistent (2,4,8). `backtest(strategy, view, cost_bps)->Result` consistent (4,6,7,8). `walk_forward(strategy_factory, view, train_days, test_days, cost_bps)` consistent (8). `assert_causal(strategy, view, sample_dates)` (9). Reuses the merged `carry_signal`, `basket_weights`, `spot_returns`, `simulate`, `metrics`, `ewma_vol`, and `validation.walk_forward` (imported as `wf_splits` to avoid the name clash with the driver) with their existing signatures.

---

## What the next plans cover (not this one)
- **Plan 2 — operational surface:** `RunConfig`/`EnvConfig` (+TOML), the strategy registry, the thin argparse CLI, and the `Execution` protocol + `SimExecution` + `LiveExecution`/`LiveRunner` seam.
- **Plan 3 — hyperopt:** `Space` types + the walk-forward-scored optimizer that outputs a `RunConfig`.

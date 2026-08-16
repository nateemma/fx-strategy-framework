# Time-Series Trend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-currency directional time-series trend strategy with three signal definitions (tsmom / ema / donchian) selectable by a hyperopt `Categorical`.

**Architecture:** A new `trend_signal` feature dispatches on `signal_type` to produce per-currency ±1 signals; `directional_weights` maps them to equal-weight ±1/N positions (NOT dollar-neutral, NOT `basket_weights`). `TrendStrategy` wraps them and exposes `signal_type` as a `Categorical` in its search space. Registry gains `trend` + `trend_voltarget`.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. No new dependencies.

## Global Constraints

- No new runtime dependencies; pandas + numpy + stdlib only.
- Trend is **directional** — `directional_weights(signal) = signal / n_currencies` (equal-weight ±1/N); the book is NOT dollar-neutral. Do NOT use `basket_weights`.
- Signals are ±1 (via `np.sign` / breakout), NaN during warm-up.
- Donchian must use `.mask(spot >= hi, 1.0).mask(spot <= lo, -1.0)` then `ffill` — during warm-up the rolling max/min are NaN so the comparisons are `False` and rows stay NaN (do NOT use `.where(spot < hi, ...)`, which fills warm-up spuriously).
- One `lookback` param drives all types; EMA fast window = `max(2, lookback // 4)`.
- Search space: `signal_type = Categorical(["tsmom", "ema", "donchian"])`, `lookback = Int(21, 252)`.
- Every signal branch is causal (trailing only); `trend` must pass `causal-check` for each signal type.
- Match the existing compact code style (see `forex/features/momentum.py`, `forex/strategies/momentum.py`).
- Stage only the files each task touches — never `git add -A`.
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: `trend_signal` + `directional_weights` feature

**Files:**
- Create: `forex/features/trend.py`
- Test: `tests/test_trend.py`

**Interfaces:**
- Produces: `trend_signal(spot, signal_type="tsmom", lookback=252) -> pd.DataFrame` (per-currency ±1, NaN warm-up; raises `ValueError` on unknown `signal_type`); `directional_weights(signal) -> pd.DataFrame` (`signal / n_currencies`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trend.py
import numpy as np, pandas as pd
import pytest
from forex.features.trend import trend_signal, directional_weights

def _panel():
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    return pd.DataFrame({"AUD": 1.0 + np.linspace(0, 0.4, 20),      # steadily rising
                         "SEK": 1.0 - np.linspace(0, 0.3, 20)},     # steadily falling
                        index=idx)

@pytest.mark.parametrize("stype", ["tsmom", "ema", "donchian"])
def test_signal_is_long_uptrend_short_downtrend(stype):
    spot = _panel()
    sig = trend_signal(spot, stype, lookback=5)
    last = sig.iloc[-1]
    assert last["AUD"] == 1.0     # rising -> long
    assert last["SEK"] == -1.0    # falling -> short

def test_tsmom_warmup_is_nan():
    sig = trend_signal(_panel(), "tsmom", lookback=5)
    assert sig.iloc[:5].isna().all().all()      # first `lookback` rows NaN

def test_unknown_signal_type_raises():
    with pytest.raises(ValueError):
        trend_signal(_panel(), "nope", lookback=5)

def test_directional_weights_equal_weight_signed():
    idx = pd.date_range("2020-01-01", periods=1, freq="B")
    sig = pd.DataFrame({"A": [1.0], "B": [1.0], "C": [-1.0]}, index=idx)
    w = directional_weights(sig)
    row = w.iloc[0]
    assert abs(row["A"] - 1/3) < 1e-9 and abs(row["B"] - 1/3) < 1e-9
    assert abs(row["C"] + 1/3) < 1e-9
    assert abs(row.sum() - 1/3) < 1e-9          # net = mean signal; gross = 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_trend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forex.features.trend'`.

- [ ] **Step 3: Write minimal implementation**

```python
# forex/features/trend.py
import numpy as np
import pandas as pd

def trend_signal(spot: pd.DataFrame, signal_type: str = "tsmom",
                 lookback: int = 252) -> pd.DataFrame:
    if signal_type == "tsmom":
        sig = np.sign(spot / spot.shift(lookback) - 1.0)
    elif signal_type == "ema":
        fast = max(2, lookback // 4)
        ef = spot.ewm(span=fast, min_periods=fast).mean()
        es = spot.ewm(span=lookback, min_periods=lookback).mean()
        sig = np.sign(ef - es)
    elif signal_type == "donchian":
        hi = spot.rolling(lookback).max()
        lo = spot.rolling(lookback).min()
        raw = pd.DataFrame(np.nan, index=spot.index, columns=spot.columns)
        raw = raw.mask(spot >= hi, 1.0).mask(spot <= lo, -1.0)
        sig = raw.ffill()
    else:
        raise ValueError(f"unknown signal_type '{signal_type}'")
    sig.index.name = "date"
    return sig

def directional_weights(signal: pd.DataFrame) -> pd.DataFrame:
    return signal / float(signal.shape[1])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_trend.py -v`
Expected: PASS (all parametrized + the rest).

- [ ] **Step 5: Commit**

```bash
git add forex/features/trend.py tests/test_trend.py
git commit -m "feat: trend_signal (tsmom/ema/donchian) + directional_weights

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `TrendStrategy`

**Files:**
- Create: `forex/strategies/trend.py`
- Test: `tests/test_trend_strategy.py`

**Interfaces:**
- Consumes: `trend_signal`, `directional_weights` from Task 1; `Strategy`, `DataView`; `Categorical`/`Int` from `forex.core.space`; `assert_causal`; `backtest`.
- Produces: `TrendStrategy(signal_type="tsmom", lookback=252)` with `.signal_type`, `.lookback`; `target_weights`, `params`, `search_space`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_trend_strategy.py
import numpy as np, pandas as pd
import pytest
from forex.core.dataview import DataView
from forex.core.space import Categorical, Int
from forex.strategies.trend import TrendStrategy
from forex.diagnostics.causal import assert_causal
from forex.run.backtest import backtest
from forex.core.result import Result

def _view():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.linspace(0,0.05,400),
                         "SEK": 1.0+np.linspace(0,-0.1,400)}, index=idx)   # EUR mild up so all 3 active
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_params_and_search_space():
    s = TrendStrategy("tsmom", 252)
    assert s.params() == {"signal_type": "tsmom", "lookback": 252}
    space = s.search_space()
    assert space["signal_type"] == Categorical(["tsmom", "ema", "donchian"])
    assert space["lookback"] == Int(21, 252)

def test_directional_weights_from_signal():
    v = _view()
    w = TrendStrategy("tsmom", 20).target_weights(v)
    last = w.loc[v.calendar[-1]]
    assert last["AUD"] > 0 and last["SEK"] < 0        # AUD up -> long, SEK down -> short
    assert abs(last.abs().sum() - 1.0) < 1e-9         # gross = 1 (all 3 active, equal 1/3)

@pytest.mark.parametrize("stype", ["tsmom", "ema", "donchian"])
def test_trend_is_causal(stype):
    v = _view()
    assert_causal(TrendStrategy(stype, 20), v, v.calendar[[100, 250, 399]])

@pytest.mark.parametrize("stype", ["tsmom", "ema", "donchian"])
def test_backtest_produces_finite_result(stype):
    r = backtest(TrendStrategy(stype, 20), _view(), cost_bps=1.0)
    assert isinstance(r, Result)
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trend_strategy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forex.strategies.trend'`.

- [ ] **Step 3: Write minimal implementation**

```python
# forex/strategies/trend.py
import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.trend import trend_signal, directional_weights

class TrendStrategy(Strategy):
    def __init__(self, signal_type: str = "tsmom", lookback: int = 252):
        self.signal_type = signal_type
        self.lookback = lookback

    def target_weights(self, view: DataView) -> pd.DataFrame:
        sig = trend_signal(view.spot[view.codes], self.signal_type, self.lookback)
        return directional_weights(sig)

    def params(self) -> dict:
        return {"signal_type": self.signal_type, "lookback": self.lookback}

    def search_space(self) -> dict:
        from forex.core.space import Categorical, Int
        return {"signal_type": Categorical(["tsmom", "ema", "donchian"]),
                "lookback": Int(21, 252)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_trend_strategy.py -v`
Expected: PASS (all parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add forex/strategies/trend.py tests/test_trend_strategy.py
git commit -m "feat: TrendStrategy (directional trend follower, signal_type Categorical)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Registry entries `trend` + `trend_voltarget`

**Files:**
- Modify: `forex/strategies/registry.py`
- Modify: `tests/test_registry.py`

**Interfaces:**
- Consumes: `TrendStrategy` from Task 2; `VolTargetOverlay` (already imported).
- Produces: registry names `trend` (builds `TrendStrategy`) and `trend_voltarget` (`VolTargetOverlay` wrapping a `TrendStrategy`, routing `signal_type/lookback` to the base and the rest to the overlay). `available()` includes both.

- [ ] **Step 1: Update the failing tests**

In `tests/test_registry.py`, add the import and two tests, and update the `available()` assertion.

Add near the top imports:
```python
from forex.strategies.trend import TrendStrategy
```

Append these two tests:
```python
def test_build_trend():
    s = build_strategy("trend", {"signal_type": "ema", "lookback": 60})
    assert isinstance(s, TrendStrategy) and s.signal_type == "ema" and s.lookback == 60

def test_build_trend_voltarget_splits_params():
    s = build_strategy("trend_voltarget",
                       {"signal_type": "donchian", "lookback": 60, "target_vol": 0.10, "cap": 1.5})
    assert isinstance(s, VolTargetOverlay)
    assert isinstance(s.base, TrendStrategy) and s.base.signal_type == "donchian"
    assert s.target_vol == 0.10 and s.cap == 1.5
```

Update the `available()` assertion inside `test_unknown_raises_and_available_lists` to add the two new names (the full set becomes):
```python
    assert set(available()) == {"carry", "carry_voltarget", "carry_voltarget_ml",
                                "momentum", "momentum_voltarget", "value", "value_voltarget",
                                "trend", "trend_voltarget"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL — `test_build_trend` / `test_build_trend_voltarget_splits_params` with `KeyError: "unknown strategy 'trend'"`, and the `available()` set assertion fails.

- [ ] **Step 3: Write minimal implementation**

In `forex/strategies/registry.py`, add the import, the trend base-keys tuple, the two builders, and extend `_BUILDERS`:
```python
from forex.strategies.trend import TrendStrategy

_TREND_KEYS = ("signal_type", "lookback")

def _trend(p: dict):
    return TrendStrategy(**p)

def _trend_voltarget(p: dict):
    base = TrendStrategy(**{k: p[k] for k in _TREND_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _TREND_KEYS}
    return VolTargetOverlay(base, **overlay)
```
Add `"trend": _trend,` and `"trend_voltarget": _trend_voltarget,` to the `_BUILDERS` dict. Leave `build_strategy` and `available` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (whole suite green). If any pre-existing test fails, STOP and report BLOCKED with the failure — do not commit a red suite.

- [ ] **Step 6: Commit**

```bash
git add forex/strategies/registry.py tests/test_registry.py
git commit -m "feat: register trend and trend_voltarget strategies

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- Trend is directional — `directional_weights` divides by the fixed currency count (`signal.shape[1]`), so gross ≤ 1 and net = mean signal. Do not "fix" it toward dollar-neutral.
- The Donchian branch's warm-up correctness depends on `.mask(spot >= hi, ...)` (NaN comparisons are False → rows stay NaN). Keep it exactly as written.
- `target_weights` selects `view.spot[view.codes]` before signalling (consistent with the other strategies).
- Do not touch `basket_weights`, the backtest, walk-forward, hyperopt, causal-check, or the CLI.

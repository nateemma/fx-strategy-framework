# Cross-Sectional Momentum Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cross-sectional momentum `Strategy` that ranks G10 currencies by trailing spot return and holds a dollar-neutral long-winners/short-losers basket, reusing the framework's existing basket construction, backtest, walk-forward, hyperopt, and causal-check.

**Architecture:** Mirror the carry strategy one-for-one, swapping only the ranking signal: a new `momentum_signal(spot, lookback)` feature feeds the existing `basket_weights`. A new `MomentumStrategy` wraps them, and the registry gains `momentum` (direct) plus `momentum_voltarget` (composed with the existing generic `VolTargetOverlay`, exactly like `carry_voltarget`).

**Tech Stack:** Python 3.11+, pandas, pytest. No new dependencies.

## Global Constraints

- No new runtime dependencies; pandas + stdlib only (matches the rest of `forex/`).
- Core stays strategy-agnostic: momentum code lives in `forex/features/` and `forex/strategies/`, never in `forex/core/`.
- Signal formula is exactly `spot / spot.shift(lookback) - 1`; default `lookback = 63`; **no skip parameter**.
- Basket construction reuses `forex.features.carry.basket_weights` unchanged — do not reimplement ranking.
- Search space uses `forex.core.space.Int`; ranges: `lookback = Int(21, 126)`, `n_long = Int(2, 4)`, `n_short = Int(2, 4)`.
- Match the existing compact code style (see `forex/strategies/carry.py`, `forex/features/carry.py`).
- Stage only the files each task touches — never `git add -A` (the repo may have concurrent edits).
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: `momentum_signal` feature

**Files:**
- Create: `forex/features/momentum.py`
- Test: `tests/test_momentum.py`

**Interfaces:**
- Consumes: nothing (pure pandas).
- Produces: `momentum_signal(spot: pd.DataFrame, lookback: int = 63) -> pd.DataFrame` — trailing return per currency column, indexed by date, with the first `lookback` rows NaN.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_momentum.py
import pandas as pd
from forex.features.momentum import momentum_signal

def test_signal_is_trailing_return_with_nan_warmup():
    idx = pd.date_range("2020-01-01", periods=4, freq="B")
    spot = pd.DataFrame(
        {"AUD": [1.0, 1.1, 1.2, 1.3], "EUR": [1.1, 1.1, 1.1, 1.1]},
        index=idx,
    )
    sig = momentum_signal(spot, lookback=2)
    # first `lookback` rows are warm-up NaN
    assert sig.iloc[0].isna().all()
    assert sig.iloc[1].isna().all()
    # row 2 = value/value[t-2] - 1
    assert round(sig.iloc[2]["AUD"], 4) == 0.2      # 1.2/1.0 - 1
    assert round(sig.iloc[2]["EUR"], 4) == 0.0      # flat
    assert sig.index.name == "date"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_momentum.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forex.features.momentum'`

- [ ] **Step 3: Write minimal implementation**

```python
# forex/features/momentum.py
import pandas as pd

def momentum_signal(spot: pd.DataFrame, lookback: int = 63) -> pd.DataFrame:
    out = spot / spot.shift(lookback) - 1.0
    out.index.name = "date"
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_momentum.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add forex/features/momentum.py tests/test_momentum.py
git commit -m "feat: momentum_signal trailing-return feature

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `MomentumStrategy`

**Files:**
- Create: `forex/strategies/momentum.py`
- Test: `tests/test_momentum_strategy.py`

**Interfaces:**
- Consumes: `momentum_signal(spot, lookback)` from Task 1; `basket_weights(signal, n_long, n_short)` from `forex.features.carry`; `Strategy` base from `forex.core.strategy`; `DataView` from `forex.core.dataview`; `Int` from `forex.core.space`; `assert_causal(strategy, view, dates)` from `forex.diagnostics.causal`; `backtest(strategy, view, cost_bps)` from `forex.run.backtest`.
- Produces: `MomentumStrategy(lookback: int = 63, n_long: int = 3, n_short: int = 3)` with `.lookback`, `.n_long`, `.n_short` attributes; `target_weights(view) -> pd.DataFrame`; `params() -> dict`; `search_space() -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_momentum_strategy.py
import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.core.space import Int
from forex.strategies.momentum import MomentumStrategy
from forex.diagnostics.causal import assert_causal
from forex.run.backtest import backtest
from forex.core.result import Result

def test_longs_winner_shorts_loser_dollar_neutral():
    idx = pd.date_range("2020-01-01", periods=4, freq="B")
    spot = pd.DataFrame(
        {"AUD": [1.0, 1.1, 1.2, 1.3],   # strictly rising -> top signal -> long
         "EUR": [1.1, 1.1, 1.1, 1.1],   # flat -> middle -> excluded
         "SEK": [1.0, 0.95, 0.9, 0.85]}, # strictly falling -> bottom -> short
        index=idx,
    )
    rates = {"USD": pd.Series(0.0, index=idx), "AUD": pd.Series(0.0, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.0, index=idx)}
    w = MomentumStrategy(lookback=2, n_long=1, n_short=1).target_weights(DataView(spot=spot, rates=rates))
    last = w.loc[idx[-1]]
    assert last["AUD"] == 1.0      # appreciating currency is longed (sign convention)
    assert last["SEK"] == -1.0     # depreciating currency is shorted
    assert last["EUR"] == 0.0
    assert abs(last.sum()) < 1e-9  # dollar-neutral

def test_params_and_search_space():
    s = MomentumStrategy(63, 3, 3)
    assert s.params() == {"lookback": 63, "n_long": 3, "n_short": 3}
    space = s.search_space()
    assert set(space) == {"lookback", "n_long", "n_short"}
    assert space["lookback"] == Int(21, 126)
    assert space["n_long"] == Int(2, 4) and space["n_short"] == Int(2, 4)

def _view():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.zeros(400),
                         "SEK": 1.0+np.linspace(0,-0.1,400)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_momentum_is_causal():
    v = _view()
    assert_causal(MomentumStrategy(63, 1, 1), v, v.calendar[[100, 200, 399]])  # no raise

def test_backtest_produces_finite_result():
    r = backtest(MomentumStrategy(63, 1, 1), _view(), cost_bps=1.0)
    assert isinstance(r, Result)
    assert len(r.returns) == len(r.weights)
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_momentum_strategy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forex.strategies.momentum'`

- [ ] **Step 3: Write minimal implementation**

```python
# forex/strategies/momentum.py
import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.momentum import momentum_signal
from forex.features.carry import basket_weights

class MomentumStrategy(Strategy):
    def __init__(self, lookback: int = 63, n_long: int = 3, n_short: int = 3):
        self.lookback = lookback
        self.n_long = n_long
        self.n_short = n_short

    def target_weights(self, view: DataView) -> pd.DataFrame:
        signal = momentum_signal(view.spot, self.lookback)
        return basket_weights(signal[view.codes], n_long=self.n_long, n_short=self.n_short)

    def params(self) -> dict:
        return {"lookback": self.lookback, "n_long": self.n_long, "n_short": self.n_short}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {"lookback": Int(21, 126), "n_long": Int(2, 4), "n_short": Int(2, 4)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_momentum_strategy.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add forex/strategies/momentum.py tests/test_momentum_strategy.py
git commit -m "feat: MomentumStrategy (trailing-return cross-sectional basket)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Registry entries `momentum` + `momentum_voltarget`

**Files:**
- Modify: `forex/strategies/registry.py`
- Modify: `tests/test_registry.py`

**Interfaces:**
- Consumes: `MomentumStrategy` from Task 2; `VolTargetOverlay` from `forex.strategies.overlay` (already imported in the registry).
- Produces: registry names `"momentum"` (builds `MomentumStrategy`) and `"momentum_voltarget"` (builds `VolTargetOverlay` wrapping a `MomentumStrategy`, routing `lookback/n_long/n_short` to the base and remaining params to the overlay). `available()` returns `["carry", "carry_voltarget", "momentum", "momentum_voltarget"]` (sorted).

- [ ] **Step 1: Update the failing tests**

In `tests/test_registry.py`, add the momentum import and two new tests, and update the `available()` assertion. The file currently ends with `test_unknown_raises_and_available_lists`; change that one assertion and append the two tests:

```python
# add near the top imports:
from forex.strategies.momentum import MomentumStrategy

# append these two tests:
def test_build_momentum():
    s = build_strategy("momentum", {"lookback": 30, "n_long": 2, "n_short": 2})
    assert isinstance(s, MomentumStrategy) and s.lookback == 30 and s.n_long == 2

def test_build_momentum_voltarget_splits_params():
    s = build_strategy("momentum_voltarget",
                       {"lookback": 30, "n_long": 1, "n_short": 1, "target_vol": 0.08, "cap": 2.0})
    assert isinstance(s, VolTargetOverlay)
    assert isinstance(s.base, MomentumStrategy) and s.base.lookback == 30 and s.base.n_long == 1
    assert s.target_vol == 0.08 and s.cap == 2.0
```

And change the existing `available()` assertion inside `test_unknown_raises_and_available_lists` from:

```python
    assert set(available()) == {"carry", "carry_voltarget"}
```
to:
```python
    assert set(available()) == {"carry", "carry_voltarget", "momentum", "momentum_voltarget"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL — `test_build_momentum` / `test_build_momentum_voltarget_splits_params` fail with `KeyError: "unknown strategy 'momentum'"`, and `test_unknown_raises_and_available_lists` fails on the new set assertion.

- [ ] **Step 3: Write minimal implementation**

Edit `forex/strategies/registry.py`. Add the import, the momentum base-keys tuple, the two builder functions, and extend `_BUILDERS`:

```python
from forex.strategies.carry import CarryStrategy
from forex.strategies.momentum import MomentumStrategy
from forex.strategies.overlay import VolTargetOverlay

_BASE_KEYS = ("n_long", "n_short")
_MOM_KEYS = ("lookback", "n_long", "n_short")

def _carry(p: dict):
    return CarryStrategy(**p)

def _carry_voltarget(p: dict):
    base = CarryStrategy(**{k: p[k] for k in _BASE_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _BASE_KEYS}
    return VolTargetOverlay(base, **overlay)

def _momentum(p: dict):
    return MomentumStrategy(**p)

def _momentum_voltarget(p: dict):
    base = MomentumStrategy(**{k: p[k] for k in _MOM_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _MOM_KEYS}
    return VolTargetOverlay(base, **overlay)

_BUILDERS = {
    "carry": _carry,
    "carry_voltarget": _carry_voltarget,
    "momentum": _momentum,
    "momentum_voltarget": _momentum_voltarget,
}
```

Leave `build_strategy` and `available` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS (all registry tests)

- [ ] **Step 5: Run the full suite + a live CLI smoke check**

Run: `python -m pytest -q`
Expected: PASS (whole suite green, including the pre-existing tests).

Run: `python -m forex causal-check --strategy momentum 2>&1 | tail -5 || true`
Expected: the causal-check runs and reports no lookahead for `momentum` (if it needs a data cache and none exists locally, a clean "no data" message is acceptable — the unit-level causal test in Task 2 is the binding check).

- [ ] **Step 6: Commit**

```bash
git add forex/strategies/registry.py tests/test_registry.py
git commit -m "feat: register momentum and momentum_voltarget strategies

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- The backtest driver (`forex/run/backtest.py`) always adds carry accrual from `view.rates` for whatever currencies are held — this is intentional and shared with carry. The Task 2 integration test therefore asserts only finiteness, not P&L sign.
- `basket_weights` already drops NaN per row and leaves rows flat when fewer than `n_long + n_short` valid names exist, so the momentum warm-up window needs no special handling.
- Do not touch the CLI, hyperopt, walk-forward, or `basket_weights` — momentum reaches all of them through the `Strategy` interface and the registry.

# `returns_of` Primitive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `returns_of(weights, view, cost_bps)` primitive and rewire the vol-target overlay and the risk-parity blend to reuse their already-computed weights instead of re-backtesting — a byte-identical speed refactor.

**Architecture:** `backtest` splits into `returns_of` (weights → return series) + `metrics`. `VolTargetOverlay` and `BlendStrategy` call `returns_of` on the weights they already hold, eliminating the redundant `target_weights` recomputation (sub-strategies ~4× → 1× for `carry_trend_voltarget`).

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. No new dependencies.

## Global Constraints

- **Byte-identical behaviour:** `returns_of(strategy.target_weights(view), view, c)` must equal `backtest(strategy, view, c).returns`. The full existing suite must pass unchanged — this is a pure speed refactor, no result changes.
- `returns_of` lives in `forex/run/backtest.py`; `backtest` delegates to it.
- Rewire only the two hot call sites: `VolTargetOverlay.target_weights` (base return) and `BlendStrategy.target_weights` (each sub return) — from `backtest(...).returns` to `returns_of(w, view, self.cost_bps)`.
- `MLVolTargetOverlay` inherits the overlay's `target_weights` (benefits automatically); do NOT touch its `fit()`.
- No new dependencies. Match the existing compact style. Stage only the files the task touches — never `git add -A`.
- End the commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: `returns_of` + rewire overlay/blend

**Files:**
- Modify: `forex/run/backtest.py`, `strategies/overlay.py`, `strategies/blend.py`
- Test: `tests/test_backtest_driver.py`

**Interfaces:**
- Produces: `returns_of(weights, view, cost_bps=1.0) -> pd.Series`; `backtest` unchanged in behaviour (now delegates); overlay/blend compute base/sub returns via `returns_of`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_backtest_driver.py` (it already defines `_view()` and imports `backtest`; add `from forex.run.backtest import returns_of` and any strategy imports needed):
```python
def test_returns_of_matches_backtest_returns():
    from forex.run.backtest import returns_of
    from strategies.carry import CarryStrategy
    from forex.core.discovery import build_strategy
    v = _view()
    for strat in (CarryStrategy(1, 1),
                  build_strategy("carry_trend", package="strategies"),
                  build_strategy("carry_trend_voltarget", package="strategies")):
        w = strat.target_weights(v)
        r = returns_of(w, v, 1.0)
        assert (r.round(12) == backtest(strat, v, 1.0).returns.round(12)).all()   # byte-identical
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backtest_driver.py -v`
Expected: FAIL (`cannot import name 'returns_of'`).

- [ ] **Step 3: Write the implementation**

In `forex/run/backtest.py`, add `returns_of` and refactor `backtest` to use it:
```python
from forex.core.result import Result
from forex.data.prices import spot_returns
from forex.features.carry import carry_signal
from forex.backtest.portfolio import simulate, metrics

def returns_of(weights, view, cost_bps: float = 1.0):
    rets = spot_returns(view.spot)
    carry = carry_signal(view.calendar, view.rates)[list(weights.columns)].fillna(0.0)
    return simulate(weights, rets, carry=carry, cost_bps=cost_bps)

def backtest(strategy, view, cost_bps: float = 1.0) -> Result:
    weights = strategy.target_weights(view)
    daily = returns_of(weights, view, cost_bps)
    return Result(returns=daily, weights=weights, metrics=metrics(daily))
```

In `strategies/overlay.py`, `VolTargetOverlay.target_weights`, replace the base-return line:
```python
    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import returns_of
        w = self.base.target_weights(view)
        base_ret = returns_of(w, view, self.cost_bps)
        vf = self._vol_forecast(base_ret).reindex(w.index).ffill()
        raw = (self.target_vol / vf).clip(upper=self.cap)
        L = raw.resample(self.cadence).first().reindex(w.index, method="ffill")
        return w.mul(L, axis=0)   # causal, NOT pre-shifted; backtest applies shift(1)
```

In `strategies/blend.py`, `BlendStrategy.target_weights`, replace the per-sub backtest with `returns_of` on the already-computed `sub_w` (iterate prefixes, not the strategy objects):
```python
    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import returns_of
        sub_w = {p: s.target_weights(view) for p, s in self.components.items()}
        any_w = next(iter(sub_w.values()))
        idx, cols = any_w.index, any_w.columns
        inv = {}
        for p in self.components:
            r = returns_of(sub_w[p], view, self.cost_bps)
            inv[p] = 1.0 / ewma_vol(r, lam=self.lam).reindex(idx).ffill()
        inv_df = pd.DataFrame(inv, index=idx)
        norm = inv_df.div(inv_df.sum(axis=1), axis=0)
        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        for p in self.components:
            out = out.add(sub_w[p].mul(norm[p], axis=0), fill_value=0.0)
        return out
```

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_backtest_driver.py -v && python -m pytest -q`
Expected: PASS — the new byte-identical test AND the whole suite unchanged (overlay/blend/backtest/discovery/causal tests all green). If ANY existing test's result changed, STOP and report BLOCKED — the refactor was not behaviour-preserving.

- [ ] **Step 5: Commit**

```bash
git add forex/run/backtest.py strategies/overlay.py strategies/blend.py tests/test_backtest_driver.py
git commit -m "perf: returns_of primitive; overlay/blend reuse weights (no re-backtest)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- The whole point is behaviour identity: `returns_of(strat.target_weights(view), view, c)` IS what `backtest(strat, view, c).returns` computes. If the byte-identical test or any existing test fails, something is wrong with the extraction — do not adjust tolerances to force it.
- The blend loop now iterates `self.components` (prefixes) since `sub_w[p]` is already computed — the strategy object `s` is no longer needed in that loop.
- Do not touch `MLVolTargetOverlay.fit` or `simulate`/`metrics`.

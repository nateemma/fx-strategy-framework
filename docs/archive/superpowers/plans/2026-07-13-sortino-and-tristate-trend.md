# Sortino Objective + Tri-State Trend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Sortino risk-adjusted metric (usable as a hyperopt objective) and a tri-state neutral band on the trend strategy (`band=0` = no-op), both hyperopt-tunable.

**Architecture:** `metrics()` gains a `sortino` key (downside-deviation-adjusted return), which `optimize` already picks up via `metrics.get(objective)`. `trend_signal` gains a `band` param that flattens weak-trend currencies; `TrendStrategy` exposes it (+ search space) and `TrendVolTarget` routes it to the base.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. No new dependencies.

## Global Constraints

- No new dependencies; pandas + numpy + stdlib only.
- Both features default to **no-ops**: `sortino` is purely additive; `band=0.0` makes trend byte-identical to today. The full suite must stay green.
- Sortino: `ann_return / (downside_dev · √252)` where `downside_dev = √(mean(min(r,0)²))`, MAR=0; `dd == 0 → sortino = 0.0` (mirrors the `sharpe` guard).
- Trend band gate: `sig = sig.mask((spot/spot.shift(lookback) - 1).abs() < band, 0.0)`, applied only when `band > 0`; uses `.mask` (not `.where`) so warm-up NaN rows are preserved.
- `TrendStrategy.search_space` adds `band = Float(0.0, 0.10)`; `TrendVolTarget.build` base keys become `("signal_type", "lookback", "band")`.
- The framework/strategies split from the prior refactor is in force: `metrics` is in `forex/backtest/portfolio.py`; `trend_signal` is in `strategies/features/trend.py`; `TrendStrategy`/`TrendVolTarget` in `strategies/trend.py`. Import `Float` from `forex.core.space`.
- Match the existing compact style. Stage only the files each task touches — never `git add -A`.
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: Sortino metric

**Files:**
- Modify: `forex/backtest/portfolio.py`
- Test: `tests/test_portfolio.py`

**Interfaces:**
- Produces: `metrics(returns)` return dict gains a `"sortino"` key (float).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_portfolio.py` (it already imports `metrics`; add `import numpy as np, pandas as pd` if not present):
```python
def test_sortino_present_and_downside_only():
    idx = pd.date_range("2020-01-01", periods=6, freq="B")
    r = pd.Series([0.01, -0.02, 0.01, -0.01, 0.02, 0.01], index=idx)
    m = metrics(r)
    assert "sortino" in m and np.isfinite(m["sortino"])
    # hand-computed downside deviation (MAR=0), annualized
    downside = r.clip(upper=0.0)
    dd = (downside.pow(2).mean() ** 0.5) * np.sqrt(252)
    assert abs(m["sortino"] - m["ann_return"] / dd) < 1e-9
    # right-skewed (mostly-up) series -> downside dev < total std -> sortino > sharpe
    assert m["sortino"] > m["sharpe"]

def test_sortino_zero_when_no_downside():
    idx = pd.date_range("2020-01-01", periods=4, freq="B")
    m = metrics(pd.Series([0.01, 0.02, 0.0, 0.01], index=idx))
    assert m["sortino"] == 0.0        # no negative returns -> dd == 0 -> guarded to 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_portfolio.py -v`
Expected: FAIL (`KeyError: 'sortino'`).

- [ ] **Step 3: Write minimal implementation**

In `forex/backtest/portfolio.py` `metrics()`, after `ann_vol` is computed and before the return dict, add the downside calc, and add the key to the returned dict:
```python
    downside = r.clip(upper=0.0)
    dd = (downside.pow(2).mean() ** 0.5) * np.sqrt(252) if len(r) else 0.0
    sortino = (ann_return / dd) if dd > 0 else 0.0
```
Add `"sortino": sortino,` to the dict returned by `metrics` (alongside `"sharpe"`).

- [ ] **Step 4: Run test + full suite**

Run: `python -m pytest tests/test_portfolio.py -v && python -m pytest -q`
Expected: PASS (new tests + whole suite green — additive).

- [ ] **Step 5: Commit**

```bash
git add forex/backtest/portfolio.py tests/test_portfolio.py
git commit -m "feat: Sortino metric (free hyperopt objective via --objective sortino)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Tri-state neutral band on trend

**Files:**
- Modify: `strategies/features/trend.py`, `strategies/trend.py`
- Test: `tests/test_trend.py`, `tests/test_trend_strategy.py`, `tests/test_discovery.py`

**Interfaces:**
- Produces: `trend_signal(spot, signal_type="tsmom", lookback=252, band=0.0)`; `TrendStrategy(signal_type="tsmom", lookback=252, band=0.0)` with `band` in `params()`/`search_space()`; `trend_voltarget` routes `band` to the base.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_trend.py`:
```python
def test_band_zeroes_weak_trends():
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    # AUD rises ~30% over the window (strong), TINY drifts ~1% (weak)
    spot = pd.DataFrame({"AUD": 1.0 + np.linspace(0, 0.3, 20),
                         "TINY": 1.0 + np.linspace(0, 0.01, 20)}, index=idx)
    s0 = trend_signal(spot, "tsmom", lookback=5, band=0.0)
    s = trend_signal(spot, "tsmom", lookback=5, band=0.05)   # 5% neutral band
    last0, last = s0.iloc[-1], s.iloc[-1]
    assert last0["AUD"] == 1.0 and last0["TINY"] == 1.0       # band=0: both long
    assert last["AUD"] == 1.0 and last["TINY"] == 0.0         # band=5%: AUD kept, TINY flat

def test_band_zero_is_noop():
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    spot = pd.DataFrame({"AUD": 1.0 + np.linspace(0, 0.3, 20)}, index=idx)
    a = trend_signal(spot, "ema", lookback=5, band=0.0)
    b = trend_signal(spot, "ema", lookback=5)                 # default band
    assert a.equals(b)
```

Append to `tests/test_trend_strategy.py` (it already defines `_view()` and imports `TrendStrategy`, `Float`? add `from forex.core.space import Float` if missing):
```python
def test_band_param_and_search_space():
    s = TrendStrategy("tsmom", 252, band=0.03)
    assert s.params() == {"signal_type": "tsmom", "lookback": 252, "band": 0.03}
    from forex.core.space import Float
    assert s.search_space()["band"] == Float(0.0, 0.10)

def test_band_still_causal():
    v = _view()
    assert_causal(TrendStrategy("tsmom", 20, band=0.02), v, v.calendar[[100, 250, 399]])
```

Append to `tests/test_discovery.py`:
```python
def test_trend_voltarget_routes_band():
    s = build_strategy("trend_voltarget", {"band": 0.05, "target_vol": 0.1}, "strategies")
    assert s.base.band == 0.05 and s.target_vol == 0.1      # band -> base, not overlay
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_trend.py tests/test_trend_strategy.py tests/test_discovery.py -v`
Expected: FAIL — `trend_signal()` has no `band` kwarg / `TrendStrategy` has no `band` / `trend_voltarget` leaks band to the overlay.

- [ ] **Step 3: Write minimal implementation**

In `strategies/features/trend.py`, add the `band` parameter and the gate. The signature becomes
`def trend_signal(spot, signal_type="tsmom", lookback=252, band=0.0):`, and just before
`sig.index.name = "date"` add:
```python
    if band > 0:
        strength = (spot / spot.shift(lookback) - 1.0).abs()
        sig = sig.mask(strength < band, 0.0)
```

In `strategies/trend.py`, `TrendStrategy`: add `band=0.0` to `__init__` (store `self.band`), pass it into `trend_signal(..., self.band)`, add `"band": self.band` to `params()`, and add `"band": Float(0.0, 0.10)` to `search_space()` (import `Float` alongside `Categorical`/`Int`). In `TrendVolTarget.build`, change the base-key tuple to `("signal_type", "lookback", "band")`.

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_trend.py tests/test_trend_strategy.py tests/test_discovery.py -v && python -m pytest -q`
Expected: PASS (new tests + whole suite green — `band=0` default keeps existing trend/blend tests byte-identical).

- [ ] **Step 5: Commit**

```bash
git add strategies/features/trend.py strategies/trend.py tests/test_trend.py tests/test_trend_strategy.py tests/test_discovery.py
git commit -m "feat: tri-state neutral band on trend (band=0 no-op, hyperopt-tunable)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- Both features are no-ops by default; the full suite must stay green (no existing test's assertion should change). If one does, STOP — something non-additive happened.
- The band gate uses `.mask(strength < band, 0.0)` (NOT `.where`): `NaN < band` is `False`, so warm-up rows keep their existing NaN and stay flat.
- `TrendVolTarget.build`'s base-key tuple MUST include `"band"` or a `band` param leaks to `VolTargetOverlay.__init__` and errors.
- Discovery uses the default `"strategies"` package now (post-move); the new discovery test passes `"strategies"` explicitly, matching the others.

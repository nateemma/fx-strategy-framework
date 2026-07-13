# Combined Multi-Factor Blend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `BlendStrategy` (risk-parity inverse-vol blend of sub-strategies) and register `carry_trend`, `carry_trend_value`, and their `_voltarget` variants, with every sub-parameter hyperopt-able (prefixed) and defaulted to the validated bests.

**Architecture:** `BlendStrategy` holds `{prefix: sub-strategy}`, weights each sub by inverse trailing EWMA vol (normalized, monthly-stepped) and sums `Σ w_i·L_i`. It exposes prefixed sub-params via `params`/`search_space`. Registry builders route prefixed params to the right sub, applying per-sub default params equal to the hyperopt bests.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. No new dependencies.

## Global Constraints

- No new runtime dependencies; pandas + numpy + stdlib only.
- Risk weight `L_i(t) = (1/vol_i) / Σ_j(1/vol_j)` from `ewma_vol` of each sub's `backtest` returns, stepped at `cadence` (default `"MS"`); combined weights `Σ_i w_i·L_i` via `out.add(sub_w[p].mul(norm[p], axis=0), fill_value=0.0)`.
- Params are **prefixed** by component key (`carry_n_long`, `trend_lookback`, `value_window`, …); prefixes are the component dict keys.
- Registry per-sub defaults = validated bests: carry `{n_long:3, n_short:3}`, trend `{signal_type:"ema", lookback:108}`, value `{window:42, n_long:4, n_short:4}`.
- Blend is directional (non-neutral) — do not force dollar-neutrality.
- Causality: sub weights + `backtest` returns + trailing `ewma_vol` + `resample(cadence).first()` are all causal; `blend`/`*_voltarget` must pass `causal-check`.
- Match the existing compact code style (see `forex/strategies/overlay.py`).
- Stage only the files each task touches — never `git add -A`.
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: `BlendStrategy`

**Files:**
- Create: `forex/strategies/blend.py`
- Test: `tests/test_blend.py`

**Interfaces:**
- Consumes: `Strategy`, `DataView`, `ewma_vol` from `forex.features.volforecast`, `backtest` from `forex.run.backtest`; sub-strategies (`CarryStrategy`, `TrendStrategy`) for tests.
- Produces: `BlendStrategy(components: dict, lam=0.94, cadence="MS", cost_bps=1.0)` with `.components`; `fit`, `target_weights`, `params` (prefixed), `search_space` (prefixed).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_blend.py
import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.core.space import Int, Categorical
from forex.strategies.blend import BlendStrategy
from forex.strategies.carry import CarryStrategy
from forex.strategies.trend import TrendStrategy
from forex.diagnostics.causal import assert_causal
from forex.run.backtest import backtest
from forex.core.result import Result

def _view():
    idx = pd.date_range("2016-01-01", periods=500, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,500), "EUR": 1.1+np.linspace(0,0.05,500),
                         "SEK": 1.0+np.linspace(0,-0.1,500)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_single_component_reproduces_the_sub():
    v = _view()
    carry = CarryStrategy(1, 1)
    b = BlendStrategy({"carry": CarryStrategy(1, 1)}).target_weights(v)
    cw = carry.target_weights(v)
    both = b.dropna(how="all").index.intersection(cw.dropna(how="all").index)
    assert (b.loc[both] - cw.loc[both]).abs().max().max() < 1e-9   # single -> L=1 -> equals sub

def test_two_identical_components_reproduce_the_sub():
    v = _view()
    b = BlendStrategy({"a": CarryStrategy(1, 1), "c": CarryStrategy(1, 1)}).target_weights(v)
    cw = CarryStrategy(1, 1).target_weights(v)
    both = b.dropna(how="all").index.intersection(cw.dropna(how="all").index)
    assert (b.loc[both] - cw.loc[both]).abs().max().max() < 1e-9   # 0.5w + 0.5w = w

def test_two_different_subs_are_convex_combination():
    v = _view()
    carry, trend = CarryStrategy(1, 1), TrendStrategy("ema", 40)
    b = BlendStrategy({"carry": carry, "trend": trend}).target_weights(v)
    wc, wt = carry.target_weights(v), trend.target_weights(v)
    assert b.index.equals(wc.index) and list(b.columns) == list(wc.columns)
    t = v.calendar[400]                              # post warm-up
    lo = pd.concat([wc.loc[t], wt.loc[t]], axis=1).min(axis=1)
    hi = pd.concat([wc.loc[t], wt.loc[t]], axis=1).max(axis=1)
    assert ((b.loc[t] >= lo - 1e-9) & (b.loc[t] <= hi + 1e-9)).all()   # convex per currency

def test_prefixed_params_and_search_space():
    b = BlendStrategy({"carry": CarryStrategy(3, 3), "trend": TrendStrategy("ema", 108)})
    p = b.params()
    assert p["carry_n_long"] == 3 and p["trend_signal_type"] == "ema" and p["trend_lookback"] == 108
    space = b.search_space()
    assert space["carry_n_long"] == Int(2, 4)
    assert space["trend_signal_type"] == Categorical(["tsmom", "ema", "donchian"])

def test_blend_is_causal():
    v = _view()
    b = BlendStrategy({"carry": CarryStrategy(1, 1), "trend": TrendStrategy("ema", 40)})
    assert_causal(b, v, v.calendar[[200, 350, 499]])

def test_backtest_produces_finite_result():
    v = _view()
    b = BlendStrategy({"carry": CarryStrategy(1, 1), "trend": TrendStrategy("ema", 40)})
    r = backtest(b, v, cost_bps=1.0)
    assert isinstance(r, Result)
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_blend.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'forex.strategies.blend'`.

- [ ] **Step 3: Write minimal implementation**

```python
# forex/strategies/blend.py
import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.volforecast import ewma_vol

class BlendStrategy(Strategy):
    def __init__(self, components: dict, lam: float = 0.94,
                 cadence: str = "MS", cost_bps: float = 1.0):
        self.components = components
        self.lam = lam
        self.cadence = cadence
        self.cost_bps = cost_bps

    def fit(self, train: DataView) -> None:
        for sub in self.components.values():
            sub.fit(train)

    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import backtest
        sub_w = {p: s.target_weights(view) for p, s in self.components.items()}
        any_w = next(iter(sub_w.values()))
        idx, cols = any_w.index, any_w.columns
        inv = {}
        for p, s in self.components.items():
            r = backtest(s, view, cost_bps=self.cost_bps).returns
            inv[p] = 1.0 / ewma_vol(r, lam=self.lam).reindex(idx).ffill()
        inv_df = pd.DataFrame(inv, index=idx)
        norm = inv_df.div(inv_df.sum(axis=1), axis=0)
        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        for p in self.components:
            out = out.add(sub_w[p].mul(norm[p], axis=0), fill_value=0.0)
        return out

    def params(self) -> dict:
        return {f"{p}_{k}": v for p, s in self.components.items()
                for k, v in s.params().items()}

    def search_space(self) -> dict:
        return {f"{p}_{k}": sp for p, s in self.components.items()
                for k, sp in s.search_space().items()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_blend.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add forex/strategies/blend.py tests/test_blend.py
git commit -m "feat: BlendStrategy (risk-parity inverse-vol multi-factor blend)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Registry — named blends + hyperopt'd defaults

**Files:**
- Modify: `forex/strategies/registry.py`
- Modify: `tests/test_registry.py`

**Interfaces:**
- Consumes: `BlendStrategy` from Task 1; `CarryStrategy`/`TrendStrategy`/`ValueStrategy`/`VolTargetOverlay` (already imported).
- Produces: registry names `carry_trend`, `carry_trend_value`, `carry_trend_voltarget`, `carry_trend_value_voltarget`, each building the blend with per-sub default params = validated bests; prefixed params override sub params; voltarget variants wrap the blend in `VolTargetOverlay` (overlay params = the non-prefixed keys). `available()` includes all four.

- [ ] **Step 1: Update the failing tests**

In `tests/test_registry.py`, add the import and tests, and update the `available()` assertion.

Add near the top imports:
```python
from forex.strategies.blend import BlendStrategy
from forex.strategies.trend import TrendStrategy
```
(If `TrendStrategy` is already imported from the earlier trend task, do not duplicate the import.)

Append these tests:
```python
def test_build_carry_trend_uses_hyperopt_defaults():
    s = build_strategy("carry_trend")
    assert isinstance(s, BlendStrategy)
    assert s.components["carry"].n_long == 3 and s.components["carry"].n_short == 3
    assert s.components["trend"].signal_type == "ema" and s.components["trend"].lookback == 108

def test_build_carry_trend_overrides_prefixed_param():
    s = build_strategy("carry_trend", {"trend_lookback": 50})
    assert s.components["trend"].lookback == 50           # override applied
    assert s.components["trend"].signal_type == "ema"     # default kept

def test_build_carry_trend_value_has_three_components():
    s = build_strategy("carry_trend_value")
    assert set(s.components) == {"carry", "trend", "value"}
    assert s.components["value"].window == 42 and s.components["value"].n_long == 4

def test_build_carry_trend_voltarget_wraps_blend():
    s = build_strategy("carry_trend_voltarget", {"target_vol": 0.12})
    assert isinstance(s, VolTargetOverlay) and isinstance(s.base, BlendStrategy)
    assert s.target_vol == 0.12
    assert s.base.components["trend"].signal_type == "ema"
```

Update the `available()` assertion inside `test_unknown_raises_and_available_lists` to add the four new names (the full set becomes):
```python
    assert set(available()) == {"carry", "carry_voltarget", "carry_voltarget_ml",
                                "momentum", "momentum_voltarget", "value", "value_voltarget",
                                "trend", "trend_voltarget",
                                "carry_trend", "carry_trend_value",
                                "carry_trend_voltarget", "carry_trend_value_voltarget"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_registry.py -v`
Expected: FAIL — the four `test_build_carry_trend*` with `KeyError: "unknown strategy 'carry_trend'"`, and the `available()` set assertion fails.

- [ ] **Step 3: Write minimal implementation**

In `forex/strategies/registry.py`, add the import, the blend specs, the helper, the builders, and extend `_BUILDERS`:
```python
from forex.strategies.blend import BlendStrategy

_BLEND_SPECS = {
    "carry_trend": [
        ("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
        ("trend", TrendStrategy, {"signal_type": "ema", "lookback": 108}),
    ],
    "carry_trend_value": [
        ("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
        ("trend", TrendStrategy, {"signal_type": "ema", "lookback": 108}),
        ("value", ValueStrategy, {"window": 42, "n_long": 4, "n_short": 4}),
    ],
}

def _build_components(specs: list, p: dict) -> dict:
    comps = {}
    for prefix, cls, defaults in specs:
        sub_p = dict(defaults)
        for k, v in p.items():
            if k.startswith(prefix + "_"):
                sub_p[k[len(prefix) + 1:]] = v
        comps[prefix] = cls(**sub_p)
    return comps

def _blend(name: str):
    specs = _BLEND_SPECS[name]
    return lambda p: BlendStrategy(_build_components(specs, p))

def _blend_voltarget(name: str):
    specs = _BLEND_SPECS[name]
    prefixes = tuple(pre for pre, _, _ in specs)
    def build(p):
        blend_p = {k: v for k, v in p.items() if any(k.startswith(pre + "_") for pre in prefixes)}
        overlay_p = {k: v for k, v in p.items() if k not in blend_p}
        return VolTargetOverlay(BlendStrategy(_build_components(specs, blend_p)), **overlay_p)
    return build
```
Add to `_BUILDERS`:
```python
    "carry_trend": _blend("carry_trend"),
    "carry_trend_value": _blend("carry_trend_value"),
    "carry_trend_voltarget": _blend_voltarget("carry_trend"),
    "carry_trend_value_voltarget": _blend_voltarget("carry_trend_value"),
```
Ensure `TrendStrategy` is imported at the top of `registry.py` (it was added by the trend task). Leave `build_strategy` and `available` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (whole suite green). If any pre-existing test fails, STOP and report BLOCKED with the failure — do not commit a red suite.

- [ ] **Step 6: Commit**

```bash
git add forex/strategies/registry.py tests/test_registry.py
git commit -m "feat: register carry_trend(+value) blends with hyperopt'd defaults

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes for the executor
- The blend is directional (trend leg) — `directional`/non-neutral weights are correct; do not "fix" toward dollar-neutral.
- `_build_components` applies each sub's default params (the validated bests) THEN overrides with any prefixed params from `p` — so `build_strategy("carry_trend")` with no params yields the validated blend.
- The `_blend_voltarget` split sends prefixed keys to the blend and everything else (`target_vol`, `cap`) to the overlay — keep that partition.
- Do not touch `basket_weights`, the backtest, walk-forward, hyperopt, causal-check, or the CLI.

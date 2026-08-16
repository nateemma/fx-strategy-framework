# Carry-Trend Crash Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `CarryTrendCrash` blend that tilts weight from carry toward trend when the carry factor is in drawdown, plus its vol-targeted sibling, to test whether state-conditioned trend weighting beats the static carry+trend blend on OOS drawdown/Calmar.

**Architecture:** Refactor `BlendStrategy.target_weights` (byte-identical) into reusable `_sub_weights` / `_base_norm` / `_combine` helpers, then a `CarryTrendCrash(BlendStrategy)` subclass injects a carry-drawdown tilt between the base weights and the combine.

**Tech Stack:** pandas, numpy (no new deps).

## Global Constraints
- The `BlendStrategy` refactor must be **byte-identical**: `carry_trend`, `carry_trend_value`, and their vol-targeted variants produce numerically unchanged weights.
- At `tilt=0`, `CarryTrendCrash` must equal the static `carry_trend` blend exactly.
- Stress signal is the **carry factor's own drawdown** (endogenous, causal): `dd = eq/eq.cummax() − 1` from `returns_of(carry_sub_weights)`; `s = clip((−dd − dd_threshold)/dd_threshold, 0, 1)`; shift `tilt·s` of weight carry→trend, clip [0,1], renormalize, resample at cadence, combine.
- `dd_threshold` and `tilt` are in `params()` and `search_space()` (`Float(0.02,0.15)` and `Float(0.0,0.5)`); they are the hyperopt levers.
- Both new variants must pass `assert_causal`.
- Framework (`forex/`) imports zero concrete strategies (unchanged — only `strategies/` + tests).
- Run `python -m pytest -q` before each commit; commit messages end with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`; stage only files each task touches (never `git add -A`).

---

### Task 1: BlendStrategy byte-identical refactor

**Files:**
- Modify: `strategies/blend.py` (`BlendStrategy.target_weights` → `_sub_weights` + `_base_norm` + `_combine` + slim `target_weights`)
- Test: `tests/test_blend.py`

**Interfaces:**
- Produces: `BlendStrategy._sub_weights(view) -> (sub_w: dict, idx, cols)`,
  `_base_norm(view, sub_w, idx) -> pd.DataFrame` (daily normalized inverse-vol weights, pre-resample),
  `_combine(sub_w, norm, idx, cols) -> pd.DataFrame`. `target_weights` unchanged in behavior.

- [ ] **Step 1: Write the byte-identical guard test**

Add to `tests/test_blend.py`:
```python
def test_refactor_matches_inline_blend():
    from forex.run.backtest import returns_of
    from forex.features.volforecast import ewma_vol
    v = _view()
    comps = {"carry": CarryStrategy(2, 2), "trend": TrendStrategy("ema", 60)}
    b = BlendStrategy(comps)
    sub_w = {p: s.target_weights(v) for p, s in comps.items()}
    idx = next(iter(sub_w.values())).index
    cols = next(iter(sub_w.values())).columns
    inv = {p: 1.0 / ewma_vol(returns_of(sub_w[p], v, b.cost_bps), lam=b.lam).reindex(idx).ffill()
           for p in comps}
    norm = pd.DataFrame(inv, index=idx)
    norm = norm.div(norm.sum(axis=1), axis=0).resample(b.cadence).first().reindex(idx, method="ffill")
    ref = pd.DataFrame(0.0, index=idx, columns=cols)
    for p in comps:
        ref = ref.add(sub_w[p].mul(norm[p], axis=0), fill_value=0.0)
    got = b.target_weights(v)
    assert (got - ref).abs().max().max() < 1e-12
```

- [ ] **Step 2: Run it (passes against current inline code)**

Run: `python -m pytest tests/test_blend.py::test_refactor_matches_inline_blend -q`
Expected: PASS (the reference reproduces the current logic). This is the guard the refactor must keep green.

- [ ] **Step 3: Refactor `target_weights` into helpers**

In `strategies/blend.py`, replace `BlendStrategy.target_weights` with:
```python
    def _sub_weights(self, view: DataView):
        sub_w = {p: s.target_weights(view) for p, s in self.components.items()}
        any_w = next(iter(sub_w.values()))
        return sub_w, any_w.index, any_w.columns

    def _base_norm(self, view: DataView, sub_w, idx) -> pd.DataFrame:
        from forex.run.backtest import returns_of
        inv = {}
        for p in self.components:
            r = returns_of(sub_w[p], view, self.cost_bps)
            inv[p] = 1.0 / ewma_vol(r, lam=self.lam).reindex(idx).ffill()
        inv_df = pd.DataFrame(inv, index=idx)
        return inv_df.div(inv_df.sum(axis=1), axis=0)

    def _combine(self, sub_w, norm, idx, cols) -> pd.DataFrame:
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        for p in self.components:
            out = out.add(sub_w[p].mul(norm[p], axis=0), fill_value=0.0)
        return out

    def target_weights(self, view: DataView) -> pd.DataFrame:
        sub_w, idx, cols = self._sub_weights(view)
        norm = self._base_norm(view, sub_w, idx)
        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
        return self._combine(sub_w, norm, idx, cols)
```
(Remove the old inline `target_weights` body; keep the `from forex.run.backtest import returns_of` import inside `_base_norm`.)

- [ ] **Step 4: Run the full blend suite**

Run: `python -m pytest tests/test_blend.py -q`
Expected: PASS (all existing tests + the new guard — refactor is behavior-preserving).

- [ ] **Step 5: Commit**

```bash
git add strategies/blend.py tests/test_blend.py
git commit -m "refactor: extract BlendStrategy weighting helpers (byte-identical)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: CarryTrendCrash + vol-targeted variant

**Files:**
- Modify: `strategies/blend.py` (add `CarryTrendCrash`, `CarryTrendCrashVolTarget`)
- Test: `tests/test_blend.py`, `tests/test_discovery.py` (count +2)

**Interfaces:**
- Consumes: Task 1's `_sub_weights` / `_base_norm` / `_combine`; `CarryTrend.SPECS`; `split_params`,
  `split_prefixed`, `build_components` (import as needed); `VolTargetOverlay`.
- Produces: strategies `carry_trend_crash` and `carry_trend_crash_voltarget`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_blend.py` (note the new imports at top: `split_*` are used only inside the classes, so tests just need `CarryTrendCrash`):
```python
def _crash_view():
    # high-rate AUD (carry goes long) depreciates -> carry draws down -> stress engages
    idx = pd.date_range("2016-01-01", periods=500, freq="B")
    spot = pd.DataFrame({"AUD": 1.0 - np.linspace(0, 0.30, 500), "EUR": 1.1 + np.linspace(0, 0.02, 500),
                         "SEK": 1.0 + np.linspace(0, 0.01, 500)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_crash_tilt_zero_equals_static_blend():
    from strategies.blend import CarryTrendCrash
    v = _view()
    comps = {"carry": CarryStrategy(1, 1), "trend": TrendStrategy("ema", 40)}
    static = BlendStrategy(dict(comps)).target_weights(v)
    crash = CarryTrendCrash(dict(comps), tilt=0.0).target_weights(v)
    assert (crash - static).abs().max().max() < 1e-12          # tilt=0 -> identical

def test_crash_tilt_shifts_weight_under_carry_drawdown():
    from strategies.blend import CarryTrendCrash
    v = _crash_view()
    comps = lambda: {"carry": CarryStrategy(1, 1), "trend": TrendStrategy("ema", 40)}
    static = CarryTrendCrash(comps(), tilt=0.0).target_weights(v)          # == static blend
    crash = CarryTrendCrash(comps(), dd_threshold=0.02, tilt=0.4).target_weights(v)
    diff = (crash - static).abs().to_numpy()
    diff = diff[~np.isnan(diff)]
    assert diff.max() > 1e-6            # on a carry-drawdown view the tilt engaged and changed the mix
    # (tilt=0 identical everywhere is asserted separately; direction carry->trend is by construction)

def test_crash_variants_are_causal():
    from strategies.blend import CarryTrendCrash
    v = _view()
    ov = CarryTrendCrash({"carry": CarryStrategy(1, 1), "trend": TrendStrategy("ema", 40)},
                         dd_threshold=0.03, tilt=0.3)
    assert_causal(ov, v, v.calendar[[200, 350, 499]])
    assert_causal(build_strategy("carry_trend_crash_voltarget"), v, v.calendar[[300, 450, 499]])

def test_crash_variant_hyperopt_levers_present():
    ov = build_strategy("carry_trend_crash")
    p, sp = ov.params(), ov.search_space()
    assert "dd_threshold" in p and "tilt" in p
    assert "dd_threshold" in sp and "tilt" in sp
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_blend.py -k "crash" -q`
Expected: FAIL (`cannot import name 'CarryTrendCrash'` / unknown strategy).

- [ ] **Step 3: Add the crash classes**

In `strategies/blend.py`: extend the compose import to
`from forex.core.compose import split_prefixed, build_components, split_params`, and after
`CarryTrendVolTarget` add:
```python
class CarryTrendCrash(BlendStrategy):
    NAME = "carry_trend_crash"
    SPECS = CarryTrend.SPECS
    def __init__(self, components, dd_threshold: float = 0.05, tilt: float = 0.30, **kw):
        super().__init__(components, **kw)
        self.dd_threshold = dd_threshold
        self.tilt = tilt

    def _crash_stress(self, view, sub_w, idx):
        from forex.run.backtest import returns_of
        rc = returns_of(sub_w["carry"], view, self.cost_bps).reindex(idx).fillna(0.0)
        eq = (1.0 + rc).cumprod()
        depth = -(eq / eq.cummax() - 1.0)
        return ((depth - self.dd_threshold) / self.dd_threshold).clip(lower=0.0, upper=1.0)

    def target_weights(self, view: DataView) -> pd.DataFrame:
        sub_w, idx, cols = self._sub_weights(view)
        norm = self._base_norm(view, sub_w, idx).copy()
        shift = self.tilt * self._crash_stress(view, sub_w, idx)
        norm["trend"] = (norm["trend"] + shift).clip(lower=0.0, upper=1.0)
        norm["carry"] = (norm["carry"] - shift).clip(lower=0.0, upper=1.0)
        norm = norm.div(norm.sum(axis=1), axis=0)
        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
        return self._combine(sub_w, norm, idx, cols)

    def params(self) -> dict:
        return {**super().params(), "dd_threshold": self.dd_threshold, "tilt": self.tilt}

    def search_space(self) -> dict:
        from forex.core.space import Float
        return {**super().search_space(),
                "dd_threshold": Float(0.02, 0.15), "tilt": Float(0.0, 0.5)}

    @classmethod
    def build(cls, params):
        own, comps = split_params(params, ("dd_threshold", "tilt"))
        return cls(build_components(cls.SPECS, comps), **own)

class CarryTrendCrashVolTarget(VolTargetOverlay):
    NAME = "carry_trend_crash_voltarget"
    DEFAULTS = {"target_vol": 0.062, "cap": 1.20}
    @classmethod
    def build(cls, params):
        crash_p, rest = split_params(params, ("dd_threshold", "tilt"))
        blend_p, overlay = split_prefixed(rest, ("carry", "trend"))
        inner = CarryTrendCrash(build_components(CarryTrend.SPECS, blend_p), **crash_p)
        return cls(inner, **{**cls.DEFAULTS, **overlay})
```

- [ ] **Step 4: Update discovery count + run full suite**

In `tests/test_discovery.py`, bump the strategy-count assertion by **+2** and add
`carry_trend_crash` and `carry_trend_crash_voltarget` to any explicit name set / parametrize list
(match the existing pattern).
Run: `python -m pytest -q`
Expected: PASS (existing blends unchanged; 5 new crash tests + discovery green).

- [ ] **Step 5: Commit**

```bash
git add strategies/blend.py tests/test_blend.py tests/test_discovery.py
git commit -m "feat: carry_trend_crash — carry-drawdown-tilted trend crash overlay

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review
- **Spec coverage:** byte-identical refactor (Task 1 + guard test) ✓; `tilt=0` == static (Task 2 test) ✓;
  drawdown tilt engages (Task 2 test) ✓; causality both variants (Task 2 test) ✓; hyperopt levers present
  (Task 2 test) ✓; vol-targeted sibling (Task 2) ✓; discovery count (Task 2) ✓.
- **Placeholder scan:** none — all steps carry concrete code/commands.
- **Type consistency:** `_base_norm` returns a daily DataFrame consumed by `_combine` and the tilt;
  `_crash_stress` returns a [0,1] Series aligned to `idx`; component keys `"carry"`/`"trend"` match
  `CarryTrend.SPECS`; NAMEs `carry_trend_crash` / `carry_trend_crash_voltarget` consistent throughout.

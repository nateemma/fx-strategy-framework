# Carry-Trend Crash Overlay (v5) — Design Spec

*Design spec. Status: approved 2026-07-14. After the ML-vol crash lever (#4) closed negative, crash
management routes to the trend factor (#11). A diagnostic confirmed the premise on G10 spot: trend is a
**convex crisis hedge** for carry — carry↔trend correlation deepens from −0.10 (carry-up months) to
−0.30 (carry-down months); trend's mean monthly return rises 8× in the worst-decile carry months (+0.48%
vs +0.06%), positive in 6 of carry's 8 worst months (2008-10: carry −8%, trend +11%); convexity coef on
carry² is +4.5. A naive 50/50 carry+trend already halves carry's max drawdown (−25% → −11.5%) at ~equal
Sharpe. So the **static** blend already harvests most of the hedge — the open question is whether a
**state-conditioned** trend weight beats it.*

## Goal & success criteria
- A `CarryTrendCrash` blend that **tilts weight from carry toward trend when the carry factor is in
  drawdown**, and its vol-targeted sibling `CarryTrendCrashVolTarget`.
- A byte-identical refactor of `BlendStrategy` exposing the reusable weighting steps.
- **Benchmark = the static `carry_trend` / `carry_trend_voltarget`.** This is factor-timing, which
  overfits easily, so the **ship gate** is strict: the dynamic overlay must beat the static blend on
  **OOS drawdown / Calmar under distant-window validation**. Otherwise the static blend stands and this
  is recorded as "the static blend already captures the carry-trend crash hedge."
- Property: at `tilt=0` the overlay is identical to the static `carry_trend` blend (a test anchor).

## Mechanism
The stress signal is the **carry factor's own drawdown** (endogenous, causal, no new data):
1. `rc = returns_of(carry_sub_weights, view, cost)`; equity `= (1+rc).cumprod()`; drawdown
   `dd = equity/equity.cummax() − 1` (≤ 0); `depth = −dd`.
2. Ramp to a stress fraction `s = clip((depth − dd_threshold)/dd_threshold, 0, 1)` — 0 until carry is
   `dd_threshold` underwater, linearly to 1 at `2·dd_threshold`. Smooth (not a hard switch) to avoid
   whipsaw.
3. Shift `tilt·s` of blend weight from carry to trend on top of the base inverse-vol weights, clip to
   [0,1], renormalize — then resample at the blend cadence and combine (same as the static blend).

Two structural params: `dd_threshold` (carry drawdown that starts the tilt) and `tilt` (max weight
moved at full stress). Both are in `params()`/`search_space()` (they're the levers to hyperopt).

### Causality
`dd` at date *t* uses only `rc[≤t]` (cumulative product + running max); the tilt is applied then
resampled at cadence exactly like the static blend. `carry_trend_crash` (and `_voltarget`) must pass
`assert_causal` (truncation-invariance) — mirrors the existing `test_blend.py` checks.

## Components

### 1. `BlendStrategy` refactor (`strategies/blend.py`) — byte-identical
Extract three helpers from the current `target_weights` so a subclass can inject a tilt between the base
weights and the combine:
```python
def _sub_weights(self, view):
    sub_w = {p: s.target_weights(view) for p, s in self.components.items()}
    any_w = next(iter(sub_w.values()))
    return sub_w, any_w.index, any_w.columns

def _base_norm(self, view, sub_w, idx):
    from forex.run.backtest import returns_of
    inv = {}
    for p in self.components:
        r = returns_of(sub_w[p], view, self.cost_bps)
        inv[p] = 1.0 / ewma_vol(r, lam=self.lam).reindex(idx).ffill()
    inv_df = pd.DataFrame(inv, index=idx)
    return inv_df.div(inv_df.sum(axis=1), axis=0)

def _combine(self, sub_w, norm, idx, cols):
    out = pd.DataFrame(0.0, index=idx, columns=cols)
    for p in self.components:
        out = out.add(sub_w[p].mul(norm[p], axis=0), fill_value=0.0)
    return out

def target_weights(self, view):
    sub_w, idx, cols = self._sub_weights(view)
    norm = self._base_norm(view, sub_w, idx)
    norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
    return self._combine(sub_w, norm, idx, cols)
```
Same operations, same order → existing `carry_trend` / `carry_trend_value` / their vol-targeted variants
are numerically unchanged (verified by the existing suite + a byte-identical guard test).

### 2. `CarryTrendCrash` (`strategies/blend.py`)
```python
class CarryTrendCrash(BlendStrategy):
    NAME = "carry_trend_crash"
    SPECS = CarryTrend.SPECS                       # same carry+trend components
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

    def target_weights(self, view):
        sub_w, idx, cols = self._sub_weights(view)
        norm = self._base_norm(view, sub_w, idx).copy()
        shift = self.tilt * self._crash_stress(view, sub_w, idx)
        norm["trend"] = (norm["trend"] + shift).clip(lower=0.0, upper=1.0)
        norm["carry"] = (norm["carry"] - shift).clip(lower=0.0, upper=1.0)
        norm = norm.div(norm.sum(axis=1), axis=0)
        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
        return self._combine(sub_w, norm, idx, cols)

    def params(self):
        return {**super().params(), "dd_threshold": self.dd_threshold, "tilt": self.tilt}

    def search_space(self):
        from forex.core.space import Float
        return {**super().search_space(),
                "dd_threshold": Float(0.02, 0.15), "tilt": Float(0.0, 0.5)}

    @classmethod
    def build(cls, params):
        own, comps = split_params(params, ("dd_threshold", "tilt"))
        return cls(build_components(cls.SPECS, comps), **own)
```
`tilt=0` ⇒ `shift=0` ⇒ identical to the static `carry_trend` blend (test anchor).

### 3. `CarryTrendCrashVolTarget` (`strategies/blend.py`)
```python
class CarryTrendCrashVolTarget(VolTargetOverlay):
    NAME = "carry_trend_crash_voltarget"
    DEFAULTS = {"target_vol": 0.062, "cap": 1.20}       # inherit the tuned vol-target as a start
    @classmethod
    def build(cls, params):
        crash_p, rest = split_params(params, ("dd_threshold", "tilt"))
        blend_p, overlay = split_prefixed(rest, ("carry", "trend"))
        inner = CarryTrendCrash(build_components(CarryTrend.SPECS, blend_p), **crash_p)
        return cls(inner, **{**cls.DEFAULTS, **overlay})
```

## Testing (offline, no network)
- **Refactor byte-identical:** `carry_trend` weights before/after equal (guard test comparing to a
  recomputed reference, or assert the existing blend tests still pass unchanged).
- **`tilt=0` equivalence:** `CarryTrendCrash(components, tilt=0.0)` produces weights equal to the static
  `CarryTrend` blend on a synthetic view.
- **Tilt engages under drawdown:** on a synthetic view engineered so carry draws down, the crash
  overlay's trend weight exceeds the static blend's trend weight in the stressed span.
- **Causality:** `assert_causal` for `carry_trend_crash` and `carry_trend_crash_voltarget` (mirror
  `test_blend.py`).
- **Discovery:** both new names build via discovery; count +2.
- Full suite green.

## Validation (post-merge)
Walk-forward `--timerange 1997-01-01: --train-days 2520 --test-days 504`:
`carry_trend` vs `carry_trend_crash` (and `carry_trend_voltarget` vs `carry_trend_crash_voltarget`), at
the v1 defaults, then **hyperopt `dd_threshold`+`tilt` only** (one space) with an added **distant-window**
check (the memory lesson: adjacent windows share a regime). Decision:
- Dynamic beats static on **OOS Calmar / max-drawdown** *and* the edge survives the distant window →
  ship `carry_trend_crash_voltarget` as the deployable book.
- Otherwise → record "the static blend already captures the carry-trend crash hedge; no state-timing
  edge"; `carry_trend_voltarget` stands; the crash variants remain registered as documented negatives.

## Out of scope (YAGNI)
- The exogenous risk-off (VIX/credit) trigger variant — only if the endogenous v1 shows promise.
- Re-tuning the component signals or the vol-target `target_vol`/`cap` jointly with the tilt (joint
  hyperopt overfits — tune the tilt space alone first, per the one-space-at-a-time lesson).
- Applying the crash tilt to `carry_trend_value` — prove it on carry+trend first.

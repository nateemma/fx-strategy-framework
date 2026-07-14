# `returns_of` Primitive — Eliminate Redundant Re-Backtesting

*Design spec. Status: approved 2026-07-13. A behaviour-preserving optimization: the vol-target overlay
and the risk-parity blend each recompute their sub-strategies' `target_weights` when fetching the
return series for vol-sizing (via `backtest`, which re-derives the weights). Extracting a
`returns_of(weights, view)` primitive lets them reuse the weights they already hold, cutting the deep
sub-strategy re-evaluation (~4× → 1× for `carry_trend_voltarget`).*

## Goal & success criteria
- Add a framework primitive `returns_of(weights, view, cost_bps) -> pd.Series` (the "weights → return
  series" step), refactor `backtest` to use it, and rewire the two hot call sites (`VolTargetOverlay`
  and `BlendStrategy`) to compute their base/sub returns from their *already-computed* weights.
- **Byte-identical behaviour:** `returns_of(strategy.target_weights(view), view, c)` equals
  `backtest(strategy, view, c).returns` by construction, so no result changes; the full suite stays
  green. This is a pure speed refactor.
- Success: the full suite passes unchanged; `carry_trend_voltarget` hyperopt is materially faster (the
  deep sub-strategy re-evaluation is removed).

## The redundancy (confirmed)
- `VolTargetOverlay.target_weights`: `w = self.base.target_weights(view)` then
  `base_ret = backtest(self.base, view, …).returns` — `backtest` recomputes `self.base.target_weights`
  → the base runs **twice**.
- `BlendStrategy.target_weights`: `sub_w = {p: s.target_weights(view)}` then, per sub,
  `backtest(s, view, …).returns` — recomputes `s.target_weights` → each sub runs **twice**.
- `carry_trend_voltarget` = overlay(blend): the overlay computes `blend.target_weights` (subs ×2 inside)
  *and* `backtest(blend)` (recomputes blend → subs ×2 again) → subs evaluated **~4×** per call.

## Design

### `forex/run/backtest.py`
Extract the post-weights P&L step into `returns_of`, and have `backtest` call it (DRY — the only
change to `backtest` is delegation; its result is identical):
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

### `strategies/overlay.py` — `VolTargetOverlay.target_weights`
```python
    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import returns_of
        w = self.base.target_weights(view)
        base_ret = returns_of(w, view, self.cost_bps)          # was backtest(self.base, view).returns
        vf = self._vol_forecast(base_ret).reindex(w.index).ffill()
        raw = (self.target_vol / vf).clip(upper=self.cap)
        L = raw.resample(self.cadence).first().reindex(w.index, method="ffill")
        return w.mul(L, axis=0)
```
`MLVolTargetOverlay` inherits this `target_weights` unchanged → benefits automatically. Its separate
`fit()` (which backtests the base once per walk-forward fold to fit the HAR model) is **left as-is** —
a much smaller cost and it needs the *fitted* base return stream, not a precomputed-weights shortcut.

### `strategies/blend.py` — `BlendStrategy.target_weights`
```python
    def target_weights(self, view: DataView) -> pd.DataFrame:
        from forex.run.backtest import returns_of
        sub_w = {p: s.target_weights(view) for p, s in self.components.items()}
        any_w = next(iter(sub_w.values()))
        idx, cols = any_w.index, any_w.columns
        inv = {}
        for p in self.components:
            r = returns_of(sub_w[p], view, self.cost_bps)      # was backtest(s, view).returns
            inv[p] = 1.0 / ewma_vol(r, lam=self.lam).reindex(idx).ffill()
        inv_df = pd.DataFrame(inv, index=idx)
        norm = inv_df.div(inv_df.sum(axis=1), axis=0)
        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")
        out = pd.DataFrame(0.0, index=idx, columns=cols)
        for p in self.components:
            out = out.add(sub_w[p].mul(norm[p], axis=0), fill_value=0.0)
        return out
```
(The loop over `self.components` no longer needs the strategy object `s`, since `sub_w[p]` is already
computed — iterate the prefixes.)

## Correctness / causality
- `returns_of` is exactly the body `backtest` ran after `target_weights`, so
  `returns_of(base.target_weights(view), view, c) == backtest(base, view, c).returns` **byte-for-byte**.
  The overlay/blend pass their own `target_weights` output as `weights`, so their vol-sizing input is
  unchanged. No result changes.
- Causality is unaffected: `returns_of` applies the same `simulate` (single `shift(1)`), and the
  weights it consumes are the same causal weights as before. `causal-check` still passes.

## Testing (all offline, no network)
- **`returns_of` equals the old path** — `returns_of(strat.target_weights(view), view, c)` equals
  `backtest(strat, view, c).returns` for `carry`/`carry_trend`/`carry_trend_voltarget` on a synthetic
  view (the byte-identical guarantee).
- **Behaviour preserved** — the full existing suite (overlay/blend/backtest/discovery/causal tests)
  passes unchanged; `assert_causal` still holds for `carry_trend_voltarget`.
- (Optional) a redundancy guard — a spy counting `target_weights` calls confirms a sub-strategy is
  evaluated once, not twice, inside a blend `target_weights`. Nice-to-have, not required.

## Out of scope (YAGNI)
- Memoizing across hyperopt samples (each candidate is a different strategy → nothing to share).
- Optimizing `MLVolTargetOverlay.fit`'s per-fold base backtest (small; needs the fitted stream).
- Any change to `simulate`, `metrics`, the drivers, or the CLI beyond the `backtest` delegation.

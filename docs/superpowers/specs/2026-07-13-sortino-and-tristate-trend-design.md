# Sortino Objective + Tri-State Trend — Design Spec

*Design spec. Status: approved 2026-07-13. Two small, independent enhancements from an ML-in-FX article
(the two ideas that survived scrutiny): a Sortino risk-adjusted metric/objective, and a tri-state
neutral band on the trend strategy. Both default to no-ops; judged on the trend hyperopt OOS.*

## Goal & success criteria
- **Sortino:** add a downside-risk-adjusted metric so hyperopt can optimize for it (`--objective sortino`).
- **Tri-state trend:** add a neutral "flat" band to the trend signal so it stops trading currencies with
  a too-small recent move (reduces whipsaws in sideways markets), tunable by hyperopt, `band=0` = today's
  behaviour.
- Success: `sortino` appears in every metrics dict; `--objective sortino` works; `trend` gains a `band`
  param searchable in hyperopt; `band=0.0` is byte-identical to the current trend; full suite green.
- **Ship gate (research, post-merge):** re-run `forex hyperopt --strategy trend` searching
  `signal_type`/`lookback`/`band` under BOTH `--objective sharpe` and `--objective sortino`, and compare
  the winning config's OOS Sharpe/Calmar/drawdown to the current trend (band=0). Keep the band only if it
  improves OOS.

## Part A — Sortino metric + objective

### `forex/backtest/portfolio.py` → `metrics()`
Add a `sortino` key. Downside deviation uses a MAR (minimum acceptable return) of 0, over all periods
(positive returns contribute 0), annualized like `ann_vol`:
```python
    downside = r.clip(upper=0.0)                              # min(r, 0) per period
    dd = (downside.pow(2).mean() ** 0.5) * np.sqrt(252) if len(r) else 0.0
    sortino = (ann_return / dd) if dd > 0 else 0.0
    # ... add "sortino": sortino to the returned dict
```
- Same shape/guards as the existing `sharpe = ann_return / ann_vol`. `dd == 0` (no downside) → `sortino
  = 0.0` (mirrors the `ann_vol == 0 → sharpe 0.0` convention).
- **Objective wiring is free:** `optimize` scores with `wf.metrics.get(objective, -inf)`, so once
  `sortino` is a metric key, `--objective sortino` works with no hyperopt change.

## Part B — Tri-state neutral band on trend

### `strategies/features/trend.py` → `trend_signal(spot, signal_type="tsmom", lookback=252, band=0.0)`
After the existing per-type ±1 `sig` is computed, apply a **uniform strength gate** — flat any currency
whose trailing move over `lookback` is smaller than `band`:
```python
    if band > 0:
        strength = (spot / spot.shift(lookback) - 1.0).abs()
        sig = sig.mask(strength < band, 0.0)      # flat where |lookback return| < band
```
- `.mask(strength < band, 0.0)` sets the signal to 0 where the trailing move is too small. `NaN <
  band` is `False`, so **warm-up rows (NaN sig / NaN strength) are preserved** and the composed
  `directional_weights` still leaves them flat. `band=0.0` skips the block entirely → **byte-identical to
  today**.
- Uniform gate rationale: it is exactly the canonical tri-state dead-zone for `tsmom` (which *is* the
  sign of that return); for `ema`/`donchian` it's a "confirm the move actually happened" filter. One
  `band` param, one meaning.
- Causal: the gate uses only the trailing `lookback` return → `causal-check` still passes.

### `strategies/trend.py` → `TrendStrategy`
```python
class TrendStrategy(Strategy):
    NAME = "trend"
    def __init__(self, signal_type="tsmom", lookback=252, band=0.0):
        self.signal_type = signal_type; self.lookback = lookback; self.band = band
    def target_weights(self, view):
        sig = trend_signal(view.spot[view.codes], self.signal_type, self.lookback, self.band)
        return directional_weights(sig)
    def params(self):
        return {"signal_type": self.signal_type, "lookback": self.lookback, "band": self.band}
    def search_space(self):
        from forex.core.space import Categorical, Int, Float
        return {"signal_type": Categorical(["tsmom", "ema", "donchian"]),
                "lookback": Int(21, 252), "band": Float(0.0, 0.10)}
```

### `strategies/trend.py` → `TrendVolTarget` base keys
`TrendVolTarget.build` currently splits base keys `("signal_type", "lookback")`. **It must add
`"band"`** so the new param routes to the `TrendStrategy` base, not the overlay:
```python
        base, overlay = split_params(params, ("signal_type", "lookback", "band"))
```

### Blends — automatic
`carry_trend*` blends reach trend via the `("trend", TrendStrategy, {"signal_type":"ema","lookback":108})`
SPEC; `band` defaults to `0.0`, so the blend's trend leg is unchanged. `BlendStrategy.search_space`
delegates to `TrendStrategy.search_space`, so a prefixed `trend_band` becomes hyperopt-tunable in the
blends for free — no SPEC or blend change needed.

## Testing (all offline, no network)
- **`sortino` metric** — on a return series with known negatives: `sortino` is present, finite, and
  equals `ann_return / (annualized downside deviation)`; a series with no negative returns gives
  `sortino == 0.0` (the `dd == 0` guard); `sortino > sharpe` for a right-skewed series (downside dev <
  total std). Assert against a hand-computed small case.
- **`trend_signal` band** — with `band=0`, output is identical to the no-band call (no-op). With a
  `band` above a currency's trailing-move magnitude, that currency's signal is `0` at a post-warm-up
  date even though `sign` would be ±1; a currency whose move exceeds `band` keeps its ±1. Warm-up rows
  stay NaN.
- **`TrendStrategy` band** — `params()` includes `band`; `search_space()` has `band == Float(0.0, 0.10)`;
  a `TrendStrategy(band=0.05)` flattens weak-trend currencies; `assert_causal` still passes for each
  signal type with `band>0`.
- **`trend_voltarget` routing** — `build_strategy("trend_voltarget", {"band": 0.05, "target_vol": 0.1})`
  → base `TrendStrategy.band == 0.05`, overlay `target_vol == 0.1` (band did NOT leak to the overlay).
- Full suite stays green (`band=0` default keeps all existing trend/blend tests byte-identical).

## Out of scope (YAGNI)
- Per-signal-type strength measures (uniform gate chosen).
- A differentiable Sortino *training loss* — only relevant to a future trained predictive strategy (the
  cross-asset/regime or crypto-derivatives tracks); not built here.
- Changing the default hyperopt objective (stays `sharpe`; Sortino is opt-in via `--objective`).
- Any change to the deployed `carry_trend_voltarget` config (band defaults to 0 there).

## References
- The article's two survivable ideas: customized financial loss (Sortino) over cross-entropy; three-value
  labeling (−1/0/+1) with a neutral state.

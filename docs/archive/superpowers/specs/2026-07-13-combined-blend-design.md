# Combined Multi-Factor Blend — Design Spec

*Design spec. Status: approved 2026-07-13. The capstone strategy on the FX framework
(`docs/superpowers/specs/2026-07-11-framework-architecture-design.md`). Backlog #3 (combined factor
portfolio). Risk-parity-blends carry + trend (+ value) into the deployable, vol-targetable book that
clears the ~8-10% / Sharpe-~0.5 return bar.*

## Goal & success criteria
Combine the validated factors into one strategy. The diagnostic showed carry+trend (risk-parity) ≈
Sharpe 0.5 with a −14% drawdown — roughly double carry alone — because trend is a real ~0.32-OOS-Sharpe
factor negatively correlated to carry; value adds further drawdown cushioning. This builds a
`BlendStrategy` that risk-parity-blends any set of sub-strategies, registers the specific named blends
(`carry_trend`, `carry_trend_value`, and their `_voltarget` variants), and exposes every sub-parameter
to hyperopt (defaulted to the validated bests). Success: the four names build; `forex backtest` /
`walkforward` / `causal-check` / `hyperopt` all work on them; all units unit-tested offline.

## Design decisions (confirmed with user)
- **Dynamic inverse-vol risk-parity** weighting (each sub scaled to ~equal risk contribution), reusing
  the framework's `ewma_vol`, stepped at a monthly cadence like the overlay.
- **Sub-parameters are hyperopt-able, prefixed** (`carry_n_long`, `trend_lookback`, …), with **defaults
  set to the current hyperopt bests** (carry 3/3, trend ema/108, value 42/4/4). "Easier to add the knob
  now than backfit later."
- **Composes with `VolTargetOverlay`** for portfolio vol-targeting (`*_voltarget` variants) — the
  deployable, leverage-scaled book.
- **Directional** (trend makes the blend non-neutral); `simulate` already handles this.

## Overfitting caveat (baked in)
The full joint blend space is wide (up to ~9 params for `carry_trend_value_voltarget`). Per the crypto
lesson (`feedback_hyperopt_one_space_at_a_time`), joint hyperopt of the whole space overfits. The
**defaults are the validated bests**, and the intended discipline is to **tune incrementally, one
sub-space at a time** (e.g. `--tune trend_signal_type,trend_lookback`), not blast all params at once.
The capability is exposed; the discipline is documented, not enforced.

## Components

### 1. `forex/strategies/blend.py` — `BlendStrategy`
```python
import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.volforecast import ewma_vol

class BlendStrategy(Strategy):
    def __init__(self, components: dict, lam: float = 0.94,
                 cadence: str = "MS", cost_bps: float = 1.0):
        self.components = components          # {prefix: Strategy}
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
        norm = inv_df.div(inv_df.sum(axis=1), axis=0)                        # L_i(t), sum 1 per date
        norm = norm.resample(self.cadence).first().reindex(idx, method="ffill")   # step monthly
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
- **Risk-parity:** `L_i(t) = (1/vol_i) / Σ_j(1/vol_j)` — normalized so each sub contributes ~equal
  risk; combined weights `Σ_i w_i · L_i` (L broadcast across currencies), stepped monthly.
- **Causality:** sub weights are causal; sub returns come from the causal `backtest`; `ewma_vol` is
  trailing; `resample(cadence).first()` is causal (same pattern the overlay passes `causal-check`
  with). `blend`/`*_voltarget` must pass `causal-check`.
- **Warm-up:** while a sub's returns/weights are NaN, its `L_i` is NaN and `out.add(..., fill_value=0)`
  makes it contribute 0; the other subs carry the book (normalization uses `sum(axis=1)` skipna).
- **Prefixed params:** `carry` and `value` both have `n_long`; prefixing (`carry_n_long`,
  `value_n_long`) avoids the collision. Prefixes are the component keys.

### 2. `forex/strategies/registry.py` — named blends
Per-sub default params = the hyperopt bests; the builder applies defaults then overrides with any
supplied prefixed params, so `build_strategy("carry_trend")` (no params) yields the validated blend and
hyperopt can override any subset.
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

_BUILDERS = {
    ...,
    "carry_trend": _blend("carry_trend"),
    "carry_trend_value": _blend("carry_trend_value"),
    "carry_trend_voltarget": _blend_voltarget("carry_trend"),
    "carry_trend_value_voltarget": _blend_voltarget("carry_trend_value"),
}
```

## Testing (all offline, no network)
- **Single-component blend reproduces the sub** — `BlendStrategy({"carry": CarryStrategy(1,1)})`
  target_weights equals `CarryStrategy(1,1).target_weights` (single component → `L = 1`).
- **Two identical components reproduce the sub** — `BlendStrategy({"a": CarryStrategy(1,1),
  "b": CarryStrategy(1,1)})` equals the single carry weights (each `L = 0.5`, `0.5·w + 0.5·w = w`) —
  proves the normalization + combination arithmetic.
- **Convex combination of two different subs** — for `{"carry": CarryStrategy(1,1),
  "trend": TrendStrategy("ema", 40)}`, at a post-warm-up date each currency's blend weight lies between
  the two subs' weights (`min ≤ blend ≤ max`), and index/columns are preserved.
- **Prefixed params / search space** — `params()` keys include `carry_n_long`, `trend_signal_type`;
  `search_space()` keys include `carry_n_long` (an `Int`) and `trend_signal_type` (a `Categorical`).
- **Causality** — `assert_causal` passes for a two-component `BlendStrategy` on a multi-year view.
- **Integration** — a backtest of the blend produces finite metrics.
- **Registry** — `build_strategy("carry_trend")` (no params) builds a `BlendStrategy` whose `trend`
  component has `signal_type="ema"`, `lookback=108` (defaults = bests) and `carry` has `n_long=3`;
  a supplied `{"trend_lookback": 50}` overrides to 50; `build_strategy("carry_trend_voltarget",
  {"target_vol": 0.12})` returns a `VolTargetOverlay` wrapping a `BlendStrategy` with `target_vol=0.12`;
  `available()` includes all four names.

## Validation (post-merge, separate research step)
Walk-forward `carry` vs `carry_trend` vs `carry_trend_value` vs `carry_trend_voltarget` on the cached
data — confirm the ~0.5 Sharpe / halved-drawdown holds OOS (the risk-parity numbers so far are
full-sample). Record the deployable config and its honest OOS metrics.

## Out of scope (YAGNI / v2)
- Non-EWMA / non-inverse-vol weighting schemes (equal-weight, mean-variance).
- Correlation-aware risk allocation (full risk-parity with the covariance matrix); v1 uses marginal
  vols only.
- Blending arbitrary strategies via the CLI (the named blends are fixed sets; new blends are new
  registry entries).
- No change to `basket_weights`, the backtest, walk-forward, hyperopt, causal-check, or the CLI.

## References
- Asness, Moskowitz, Pedersen (2013), *Value and Momentum Everywhere* (multi-factor combination).
- Baz et al., *Dissecting Investment Strategies* (risk-parity factor blending).

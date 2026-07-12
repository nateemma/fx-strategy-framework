# Cross-Sectional Momentum — Design Spec

*Design spec. Status: approved 2026-07-12. Second reference strategy on the FX strategy framework
(`docs/superpowers/specs/2026-07-11-framework-architecture-design.md`). Adds a cross-sectional
momentum factor that mirrors the carry strategy, swapping only the ranking signal. Tier-1 item #1 in
`docs/strategy-research-backlog.md`.*

## Goal & success criteria
Add a cross-sectional momentum `Strategy` that ranks G10 currencies by trailing spot return and holds
a dollar-neutral basket (long top-N winners / short bottom-N losers), reusing the framework's existing
basket construction, backtest, walk-forward, hyperopt, and causal-check unchanged. Success: `forex
backtest --strategy momentum` and `forex walkforward --strategy momentum` run and report metrics;
`forex causal-check --strategy momentum` passes (no lookahead); `momentum` and `momentum_voltarget` are
both registered; all new units are unit-tested offline.

## Why this shape
The framework's carry strategy is `basket_weights(carry_signal(...))`. Momentum is the *same* basket
construction over a *different* signal — trailing spot return instead of rate differential. The two
factors are low-correlated (Menkhoff, Sarno, Schmeling, Schrimpf 2012, *Currency Momentum
Strategies*), so momentum diversifies the book and proves the "second strategy drops onto the
framework cleanly" path. No new data: `view.spot` is already loaded.

## Momentum specification (decided)
- **Signal:** `momentum_signal(spot, lookback) = spot / spot.shift(lookback) - 1` — the trailing return
  over `lookback` business days, one column per currency, indexed by date.
- **Formation window:** default `lookback = 63` business days (~3 months), the robust mid-point of the
  FX momentum literature.
- **No skip.** The equity "12-1" skip-the-recent-month convention is not used (weak effect in FX);
  there is no `skip` parameter.
- **Basket:** reuse `basket_weights(signal[view.codes], n_long, n_short)` unchanged — sort by signal
  descending, long the top `n_long` at `+1/n_long`, short the bottom `n_short` at `-1/n_short`,
  dollar-neutral. Rows with fewer than `n_long + n_short` valid (non-NaN) names are left flat.
- **Warm-up:** the first `lookback` rows of the signal are NaN; `basket_weights` already drops NaN per
  row, so warm-up rows produce no positions. No special handling needed.

## Causality
The weight at date *t* is formed from `spot[t]` and `spot[t-lookback]` — information available at *t*.
This matches `carry_signal`, which reads rates as-of *t*; the backtest applies the single one-period
shift before multiplying weights by realized returns. `momentum` must therefore pass `causal-check`
with no changes to the checker.

## Sign convention (pinned by test)
The momentum signal and the backtest P&L both derive from the **same `view.spot` series in the same
direction**. "Long the currencies whose recent spot return was positive" is therefore self-consistent
regardless of the USD quote orientation of the spot panel — no orientation assumption is baked into
the strategy. A unit test pins this: on a synthetic panel where one currency strictly appreciated over
the window, that currency receives the top (positive) signal and a long weight.

## Components

### 1. `forex/features/momentum.py`
```python
def momentum_signal(spot: pd.DataFrame, lookback: int = 63) -> pd.DataFrame:
    """Trailing spot return over `lookback` rows; NaN for the warm-up rows."""
    out = spot / spot.shift(lookback) - 1.0
    out.index.name = "date"
    return out
```

### 2. `forex/strategies/momentum.py`
```python
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

### 3. `forex/strategies/registry.py`
Add two builders mirroring the carry pair. Momentum's base keys are `(lookback, n_long, n_short)`;
`momentum_voltarget` splits those to the base and the remaining params to the generic
`VolTargetOverlay` (exactly as `carry_voltarget` does).
```python
_MOM_KEYS = ("lookback", "n_long", "n_short")

def _momentum(p): return MomentumStrategy(**p)

def _momentum_voltarget(p):
    base = MomentumStrategy(**{k: p[k] for k in _MOM_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _MOM_KEYS}
    return VolTargetOverlay(base, **overlay)

_BUILDERS = {..., "momentum": _momentum, "momentum_voltarget": _momentum_voltarget}
```

## Testing (all offline, no network)
- **`momentum_signal`** — on a small synthetic spot panel with known values: assert the trailing return
  equals the hand-computed value at a sampled date, and that the first `lookback` rows are NaN.
- **`MomentumStrategy.target_weights`** — on a synthetic panel engineered so the ranking is
  unambiguous: the top-mover currency gets `+1/n_long`, the bottom-mover gets `-1/n_short`, each row's
  weights sum to ≈ 0 (dollar-neutral), and warm-up rows are flat.
- **Sign-convention test** — a currency that strictly appreciates over the window receives a positive
  signal and a long weight (pins the "no orientation assumption" claim).
- **`params` / `search_space`** — return the expected keys and `Int` ranges.
- **Registry** — `build_strategy("momentum", {...})` returns a `MomentumStrategy`;
  `build_strategy("momentum_voltarget", {...})` returns a `VolTargetOverlay` wrapping a
  `MomentumStrategy` with the base params routed correctly; `available()` includes both names.
- **Integration** — a backtest over an injected `DataView` produces a `Result` with finite metrics;
  `causal-check` on `momentum` passes.

## Out of scope (YAGNI)
- No `skip` parameter (no-skip chosen).
- No per-strategy rebalance cadence (carry has none; the overlay owns cadence).
- No new data source (spot already loaded).
- No changes to `basket_weights`, the backtest, walk-forward, hyperopt, causal-check, or the CLI —
  momentum plugs into all of them through the existing `Strategy` interface and the registry.

## References
- Menkhoff, Sarno, Schmeling, Schrimpf (2012), *Currency Momentum Strategies*.
- Asness, Moskowitz, Pedersen (2013), *Value and Momentum Everywhere* (carry–momentum–value low
  correlation, motivating the eventual combined portfolio, backlog #3).

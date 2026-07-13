# Time-Series Trend — Design Spec

*Design spec. Status: approved 2026-07-13. Fourth reference strategy on the FX strategy framework
(`docs/superpowers/specs/2026-07-11-framework-architecture-design.md`). Adds a per-currency directional
trend follower with the signal definition selectable by hyperopt. Backlog #11 (promoted); the
crisis-alpha diversifier queued after the value/blend verdict.*

## Goal & success criteria
Add a **directional** time-series trend strategy: each currency independently long if it is trending up
vs USD, short if trending down. Three signal definitions are implemented behind one interface and the
choice is a **hyperopt `Categorical`** (per the user's request — don't pre-select one). Success:
`forex backtest --strategy trend` and `forex walkforward --strategy trend` run; `forex causal-check
--strategy trend` passes for each signal type; `trend` and `trend_voltarget` are registered; all units
are unit-tested offline. Judge (post-merge) on OOS Sharpe **and** correlation-to-carry — diversification
is the point (crisis-alpha, catches dollar macro trends), not standalone return.

## The shape — directional, NOT dollar-neutral
Unlike carry/value/momentum (cross-sectional dollar-neutral baskets via `basket_weights`), trend takes
**outright per-currency positions**, so the book can be net long or short USD (when most currencies
trend up vs the dollar, the book is net short USD). This is intentional — it is what captures dollar
macro trends and gives the crisis-alpha diversification. `simulate` already handles non-neutral weights
(it applies `held·(spot+carry)`), and a held currency correctly accrues its carry. Trend does **not**
use `basket_weights`; it uses a new equal-weight directional constructor.

## Decisions (confirmed with the user)
- **All three signal types implemented; choice is a hyperopt `Categorical`.**
- **Equal-weight ±1/N sizing** (v1). Per-pair vol-scaling is a documented refinement; portfolio-level
  risk-scaling is available by composing with the existing vol-target overlay (`trend_voltarget`).
- **One `lookback` param** interpreted per signal type (EMA fast window derived as `lookback//4`),
  rather than separate fast/slow/channel params — keeps the hyperopt space tractable.

## Components

### 1. `forex/features/trend.py`
```python
import numpy as np
import pandas as pd

def trend_signal(spot: pd.DataFrame, signal_type: str = "tsmom",
                 lookback: int = 252) -> pd.DataFrame:
    if signal_type == "tsmom":
        sig = np.sign(spot / spot.shift(lookback) - 1.0)
    elif signal_type == "ema":
        fast = max(2, lookback // 4)
        ef = spot.ewm(span=fast, min_periods=fast).mean()
        es = spot.ewm(span=lookback, min_periods=lookback).mean()
        sig = np.sign(ef - es)
    elif signal_type == "donchian":
        hi = spot.rolling(lookback).max()
        lo = spot.rolling(lookback).min()
        raw = pd.DataFrame(np.nan, index=spot.index, columns=spot.columns)
        raw = raw.mask(spot >= hi, 1.0).mask(spot <= lo, -1.0)   # +1 new high, -1 new low; NaN in warm-up
        sig = raw.ffill()
    else:
        raise ValueError(f"unknown signal_type '{signal_type}'")
    sig.index.name = "date"
    return sig

def directional_weights(signal: pd.DataFrame) -> pd.DataFrame:
    return signal / float(signal.shape[1])       # equal-weight +-1/N per currency
```
- **±1 signals** for all three types (comparable); NaN during warm-up (`shift`/`min_periods`/rolling
  before the first breakout), which `directional_weights` passes through as NaN (flat).
- **Donchian** is stateful-but-vectorized: `.mask(spot >= hi, 1.0)` marks a new `lookback`-window high,
  `.mask(spot <= lo, -1.0)` a new low, else NaN — then `ffill` to hold between breakouts. During warm-up
  the rolling max/min are NaN, so `spot >= hi` / `spot <= lo` are `False` and the rows stay NaN (no
  spurious signal). Causal (trailing rolling + ffill).
- **Causality:** every branch uses only trailing data. `trend` must pass `causal-check` for each
  `signal_type`.

### 2. `forex/strategies/trend.py`
```python
import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.trend import trend_signal, directional_weights

class TrendStrategy(Strategy):
    def __init__(self, signal_type: str = "tsmom", lookback: int = 252):
        self.signal_type = signal_type
        self.lookback = lookback

    def target_weights(self, view: DataView) -> pd.DataFrame:
        sig = trend_signal(view.spot[view.codes], self.signal_type, self.lookback)
        return directional_weights(sig)

    def params(self) -> dict:
        return {"signal_type": self.signal_type, "lookback": self.lookback}

    def search_space(self) -> dict:
        from forex.core.space import Categorical, Int
        return {"signal_type": Categorical(["tsmom", "ema", "donchian"]),
                "lookback": Int(21, 252)}
```

### 3. `forex/strategies/registry.py`
Add `trend` and `trend_voltarget` (compose with the generic `VolTargetOverlay`). Base keys are
`(signal_type, lookback)`:
```python
_TREND_KEYS = ("signal_type", "lookback")

def _trend(p): return TrendStrategy(**p)

def _trend_voltarget(p):
    base = TrendStrategy(**{k: p[k] for k in _TREND_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _TREND_KEYS}
    return VolTargetOverlay(base, **overlay)

_BUILDERS = {..., "trend": _trend, "trend_voltarget": _trend_voltarget}
```

## Testing (all offline, no network)
- **`trend_signal` per type** — on a synthetic panel with a clearly rising currency and a clearly
  falling one, sampled at a post-warm-up date: `tsmom`, `ema`, and `donchian` each give `+1` for the
  riser and `-1` for the faller. Warm-up rows are NaN.
- **`directional_weights`** — a signal row `[+1, +1, -1]` (3 currencies) maps to `[1/3, 1/3, -1/3]`
  (equal-weight, sign preserved, gross = 1, net = 1/3); a NaN signal cell maps to NaN.
- **`TrendStrategy` params / search_space** — keys `{signal_type, lookback}`; `search_space` has a
  `Categorical(["tsmom","ema","donchian"])` and `Int(21, 252)`.
- **Causality** — `assert_causal` passes for `TrendStrategy` with EACH `signal_type` on a multi-year
  injected view (loop over the three types).
- **Integration** — a backtest over an injected view produces finite metrics for each signal type.
- **Registry** — `build_strategy("trend", {...})` returns a `TrendStrategy`;
  `build_strategy("trend_voltarget", {...})` returns a `VolTargetOverlay` wrapping a `TrendStrategy`
  with base params routed correctly; `available()` includes both names.

## Out of scope (YAGNI / v2)
- Per-pair vol-scaled sizing (equal-weight chosen; portfolio vol-targeting via the overlay covers risk
  scaling).
- Separate fast/slow/channel window params (one `lookback` drives all three types).
- Blending multiple lookbacks; continuous (non-±1) trend strength.
- No change to `basket_weights`, the backtest, walk-forward, hyperopt, causal-check, or the CLI.

## References
- Moskowitz, Ooi, Pedersen (2012), *Time Series Momentum*.
- Baz et al., *Dissecting Investment Strategies* (trend/momentum construction).

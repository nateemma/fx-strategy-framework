# Value / PPP Factor — Design Spec

*Design spec. Status: approved 2026-07-12. Third reference strategy on the FX strategy framework
(`docs/superpowers/specs/2026-07-11-framework-architecture-design.md`). Adds a value factor that ranks
G10 currencies by real-exchange-rate over/undervaluation, mirroring carry/momentum. Tier-1 item #2 in
`docs/strategy-research-backlog.md`; the diversifier that meaningfully lifts the carry blend toward the
~8–10% / Sharpe-0.8 return bar.*

## Goal & success criteria
Add a cross-sectional value `Strategy` that ranks currencies by how far each sits below/above its own
long-run real-exchange-rate (REER) mean, holding a dollar-neutral basket (long undervalued winners /
short overvalued losers), reusing the framework's `basket_weights`, backtest, walk-forward, hyperopt,
and causal-check. Success: `forex backtest --strategy value` and `forex walkforward --strategy value`
run and report metrics; `forex causal-check --strategy value` passes; `value` and `value_voltarget`
are both registered; all new units are unit-tested offline.

## Why this factor
Momentum proved too weak on G10 spot to matter in the blend (uncorrelated to carry but Sharpe ~0.07 —
adds ~nothing). Value is a stronger standalone factor (literature Sharpe ~0.3–0.5, Asness–Moskowitz–
Pedersen 2013) and also low-correlated to carry, so a carry+value blend ≈ √(0.30² + 0.35²) ≈ 0.46 —
the first combination that moves toward the return bar. Value is slow and low-turnover, so it avoids
the daily-rebalance cost trap that sank momentum.

## Value specification (decided)
- **Data:** BIS Real Broad Effective Exchange Rate, one monthly series per currency, via FRED
  (`RB<CC>BIS`). Already CPI-deflated and trade-weighted — the literature-standard "real exchange
  rate" in one clean series. Loads like `rates` (as-of join + publication lag).
- **Signal:** `signal[c] = -(log REER[c] - rolling_mean(log REER[c], window))`. A currency **below**
  its own trailing mean is undervalued → positive signal → longed. Uses the **level** (deviation from
  a trailing fair-value anchor), not the endpoint change, so it captures persistent misvaluation.
- **Window:** `window` is in **months** (REER is monthly). Default `60` (5 years). `min_periods =
  window` (require a full window), so the first `window` months of each series are NaN.
- **Publication lag:** a module constant `REER_PUB_LAG_DAYS = 45` fed to `asof_join` (BIS releases
  ~mid-month for the prior month). One shared constant, not per-currency.
- **Basket:** reuse `basket_weights(signal[view.codes], n_long, n_short)` unchanged — sort by signal
  descending, long top `n_long` at `+1/n_long`, short bottom `n_short` at `-1/n_short`, dollar-neutral;
  rows with fewer than `n_long + n_short` valid names left flat.

## Causality
The signal at date *t* uses REER values dated ≤ `t - REER_PUB_LAG_DAYS` (via `asof_join`) and a
**trailing** rolling mean — information available at *t*. Matches the carry/momentum convention; the
backtest applies the single one-period shift. `value` must pass `causal-check` unchanged.

## Components

### 1. `forex/config.py`
Add `reer_fred: str | None` to the `Currency` dataclass and populate it for each currency (BIS Real
Broad REER; `None` for USD, which value does not use). Verify each ID at
`https://fred.stlouisfed.org/series/<ID>` before the first live fetch, exactly like the rates note;
tests use fixtures and do not depend on live IDs.

```python
@dataclass(frozen=True)
class Currency:
    code: str
    spot_fred: str | None
    spot_invert: bool
    rate_fred: str
    pub_lag_days: int
    reer_fred: str | None    # BIS Real Broad REER (RB<CC>BIS); None for USD
```

Candidate REER IDs (verify at fetch): USD `RBUSBIS` (unused), EUR `RBXMBIS`, JPY `RBJPBIS`,
GBP `RBGBBIS`, CHF `RBCHBIS`, AUD `RBAUBIS`, NZD `RBNZBIS`, CAD `RBCABIS`, NOK `RBNOBIS`,
SEK `RBSEBIS`.

### 2. `forex/core/dataview.py`
Add a `reer` field with a **default empty dict** so every existing `DataView(spot=, rates=)`
constructor in the codebase and tests keeps working unchanged. `from_fred` populates it for the
non-USD codes; `truncate` clips it alongside `rates`.

```python
from dataclasses import dataclass, field

@dataclass
class DataView:
    spot: pd.DataFrame
    rates: dict
    reer: dict = field(default_factory=dict)

    def truncate(self, asof) -> "DataView":
        asof = pd.Timestamp(asof)
        spot = self.spot.loc[:asof]
        rates = {k: v.loc[:asof] for k, v in self.rates.items()}
        reer = {k: v.loc[:asof] for k, v in self.reer.items()}
        return DataView(spot=spot, rates=rates, reer=reer)
```

In `from_fred`, after building `rates`, load REER for each non-USD code:
```python
        reer = {c: loader(CURRENCIES[c].reer_fred, cache_dir=cache_dir) for c in codes}
        return cls(spot=spot, rates=rates, reer=reer)
```
(REER is an index level, not a rate — do **not** divide by 100.)

### 3. `forex/features/value.py`
```python
import numpy as np
import pandas as pd
from forex.data.store import asof_join

REER_PUB_LAG_DAYS = 45

def value_signal(calendar, reer: dict, window: int = 60,
                 pub_lag_days: int = REER_PUB_LAG_DAYS) -> pd.DataFrame:
    cal = pd.DatetimeIndex(calendar)
    cols = {}
    for code, s in reer.items():
        logr = np.log(s.astype("float64"))
        dev = logr - logr.rolling(window, min_periods=window).mean()
        cols[code] = asof_join(cal, (-dev).rename(code), pub_lag_days)
    out = pd.DataFrame(cols, index=cal)
    out.index.name = "date"
    return out
```
The rolling mean runs on the **monthly** REER series (window in months) before the as-of join to the
daily calendar.

### 4. `forex/strategies/value.py`
```python
import pandas as pd
from forex.core.strategy import Strategy
from forex.core.dataview import DataView
from forex.features.value import value_signal
from forex.features.carry import basket_weights

class ValueStrategy(Strategy):
    def __init__(self, window: int = 60, n_long: int = 3, n_short: int = 3):
        self.window = window
        self.n_long = n_long
        self.n_short = n_short

    def target_weights(self, view: DataView) -> pd.DataFrame:
        signal = value_signal(view.calendar, view.reer, self.window)
        return basket_weights(signal[view.codes], n_long=self.n_long, n_short=self.n_short)

    def params(self) -> dict:
        return {"window": self.window, "n_long": self.n_long, "n_short": self.n_short}

    def search_space(self) -> dict:
        from forex.core.space import Int
        return {"window": Int(36, 84), "n_long": Int(2, 4), "n_short": Int(2, 4)}
```

### 5. `forex/strategies/registry.py`
Add two builders mirroring the carry/momentum pairs. Value's base keys are `(window, n_long,
n_short)`; `value_voltarget` splits those to the base and the rest to the generic `VolTargetOverlay`.
```python
_VAL_KEYS = ("window", "n_long", "n_short")

def _value(p): return ValueStrategy(**p)

def _value_voltarget(p):
    base = ValueStrategy(**{k: p[k] for k in _VAL_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _VAL_KEYS}
    return VolTargetOverlay(base, **overlay)

_BUILDERS = {..., "value": _value, "value_voltarget": _value_voltarget}
```

## Testing (all offline, no network)
- **`value_signal`** — synthetic monthly REER dict: a currency whose latest level is below its trailing
  mean gets a **positive** signal; a currency above gets negative; the first `window` months are NaN;
  confirm the log transform (a fixed proportional gap maps to the expected log deviation). Sample a
  known date and assert the deviation value.
- **`ValueStrategy.target_weights`** — `DataView` with `reer` engineered so ranking is unambiguous
  (one clearly-cheap, one clearly-rich, one mid): cheap gets `+1/n_long`, rich gets `-1/n_short`, mid
  excluded, row sums ≈ 0; warm-up rows flat.
- **`params` / `search_space`** — expected keys and `Int` ranges (`window` Int(36,84)).
- **`assert_causal`** — `value` passes on a multi-year injected view (no lookahead).
- **Registry** — `build_strategy("value", …)` → `ValueStrategy`; `build_strategy("value_voltarget", …)`
  → `VolTargetOverlay` wrapping `ValueStrategy` with base params routed correctly; `available()`
  includes both names.
- **`DataView`** — `reer` defaults to empty (`DataView(spot=, rates=)` still valid); `truncate` clips
  `reer` to `≤ asof`; `from_fred` with an injected loader populates `reer` for the non-USD codes.

## Out of scope (YAGNI)
- No macro-bag generalization of `DataView` (deferred until a 3rd data source, e.g. VIX/COT for the
  regime overlay).
- No per-currency REER publication lag (one shared constant).
- No CPI-built real-rate fallback (REER chosen).
- No changes to `basket_weights`, the backtest, walk-forward, hyperopt, causal-check, or the CLI —
  value plugs into all of them through the `Strategy` interface and the registry.

## References
- Asness, Moskowitz, Pedersen (2013), *Value and Momentum Everywhere*.
- BIS effective exchange rate indices (real broad), via FRED.

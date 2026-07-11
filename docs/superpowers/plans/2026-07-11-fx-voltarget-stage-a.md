# FX Carry Vol-Target Overlay — Stage A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the EWMA volatility-targeting overlay to the existing bare G10 carry basket — forecast the basket's volatility with an EWMA, scale exposure by `min(cap, target_vol/σ̂)`, and produce an end-to-end report comparing the overlay to bare carry (the Stage-A yardstick the later ML stage must beat).

**Architecture:** Three small units that reuse the merged baseline. `forex/features/volforecast.py` computes an annualized EWMA vol from a return series. `forex/backtest/voltarget.py` applies a vol-scale to a return series (no-lookahead, capped, stepped at a cadence, with leverage-turnover cost). `forex/research/overlay.py` wires `run_baseline` → EWMA vol → vol-target and reports both vs the distant-era check. Fully offline — operates on the bare-carry daily returns; no new data sources (those are Stage B).

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. Reuses `forex.research.carry_baseline.run_baseline` and `forex.backtest.portfolio.metrics`.

## Global Constraints

- Project root `~/Documents/forex`; importable code under `forex/`, tests under `tests/`; use the venv at `~/Documents/forex/.venv` (`.venv/bin/python -m pytest`).
- **No lookahead:** the vol-scale applied on day *t* must derive only from data through *t−1* (implemented as `scale.shift(1)`, mirroring `simulate`'s `weights.shift(1)`).
- **Judge on out-of-sample risk-adjusted P&L, not forecast accuracy.** Baselines to beat: bare carry **Sharpe 0.34 / maxDD −27%**.
- v1 defaults: horizon implicit in EWMA `lam=0.94`; `target_vol=0.10`; `cap=1.5`; `cadence="MS"` (monthly); `cost_bps=1.0`.
- Tests must not hit the network. Commit after every task (conventional commits).

---

## File Structure
- `forex/features/volforecast.py` — `ewma_vol(returns, lam, periods_per_year)`.
- `forex/backtest/voltarget.py` — `vol_target(carry_ret, vol_forecast, target_vol, cap, cadence, cost_bps)`.
- `forex/research/overlay.py` — `run_overlay(...)` + a `__main__` report.
- `tests/test_volforecast.py`, `tests/test_voltarget.py`, `tests/test_overlay.py`.

---

### Task 1: EWMA volatility forecaster

**Files:**
- Create: `forex/features/volforecast.py`, `tests/test_volforecast.py`

**Interfaces:**
- Consumes: nothing (pure pandas).
- Produces: `ewma_vol(returns: pd.Series, lam: float = 0.94, periods_per_year: int = 252) -> pd.Series`
  — annualized EWMA volatility per date. EWMA of squared returns with `adjust=False`
  (`σ²_t = λ·σ²_{t-1} + (1−λ)·r²_t`), then annualized `sqrt(σ²·periods_per_year)`. Same index as input.

- [ ] **Step 1: Write the failing test**

`tests/test_volforecast.py`:
```python
import pandas as pd
from forex.features.volforecast import ewma_vol

def test_ewma_vol_annualizes_first_value():
    r = pd.Series([0.01, -0.01, 0.01, -0.01],
                  index=pd.date_range("2020-01-01", periods=4, freq="D"))
    v = ewma_vol(r, lam=0.94, periods_per_year=252)
    assert len(v) == 4
    # adjust=False => first EWMA(r^2) value is r_0^2, so vol_0 = |0.01|*sqrt(252)
    assert round(v.iloc[0], 6) == round(0.01 * (252 ** 0.5), 6)
    assert (v > 0).all()

def test_ewma_vol_rises_with_bigger_shocks():
    calm = pd.Series([0.001] * 50, index=pd.date_range("2020-01-01", periods=50, freq="D"))
    wild = pd.Series([0.05] * 50, index=pd.date_range("2020-01-01", periods=50, freq="D"))
    assert ewma_vol(wild).iloc[-1] > ewma_vol(calm).iloc[-1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_volforecast.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.features.volforecast'`.

- [ ] **Step 3: Write minimal implementation**

`forex/features/volforecast.py`:
```python
import pandas as pd

def ewma_vol(returns: pd.Series, lam: float = 0.94,
             periods_per_year: int = 252) -> pd.Series:
    """Annualized RiskMetrics EWMA volatility of a return series.

    EWMA variance with adjust=False: var_t = lam*var_{t-1} + (1-lam)*r_t^2.
    Causality is the caller's responsibility — the vol-target overlay applies
    this forecast with a .shift(1) so day t is sized from data through t-1.
    """
    var = returns.pow(2).ewm(alpha=1.0 - lam, adjust=False).mean()
    return (var * periods_per_year) ** 0.5
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_volforecast.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add forex/features/volforecast.py tests/test_volforecast.py
git commit -m "feat: EWMA volatility forecaster"
```

---

### Task 2: Vol-target overlay mechanism

**Files:**
- Create: `forex/backtest/voltarget.py`, `tests/test_voltarget.py`

**Interfaces:**
- Consumes: `forex.features.volforecast.ewma_vol` (in a test), `forex.backtest.portfolio.metrics` (in a test).
- Produces: `vol_target(carry_ret: pd.Series, vol_forecast: pd.Series, target_vol: float = 0.10, cap: float = 1.5, cadence: str = "MS", cost_bps: float = 1.0) -> pd.Series`
  — overlaid daily returns, named `ret`. Scale `s = clip(target_vol/vol_forecast, upper=cap)`, stepped
  at `cadence` (pandas resample rule, e.g. `"MS"` monthly / `"D"` daily), applied to the NEXT day
  (`s.shift(1)`), minus leverage-turnover cost `cost_bps/1e4 · |Δs|` (the first period's onset from 0→s
  is charged).

- [ ] **Step 1: Write the failing test**

`tests/test_voltarget.py`:
```python
import pandas as pd
from forex.backtest.voltarget import vol_target
from forex.features.volforecast import ewma_vol
from forex.backtest.portfolio import metrics

def test_cap_and_no_lookahead():
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    carry = pd.Series([0.0, 0.02, 0.0], index=idx)
    vf = pd.Series([0.05, 0.05, 0.05], index=idx)  # target/vf = 0.10/0.05 = 2.0 -> capped to 1.5
    out = vol_target(carry, vf, target_vol=0.10, cap=1.5, cadence="D", cost_bps=0.0)
    # day2 return = day1 scale (1.5, from day0->carry not used until shifted) * 0.02 = 0.03
    assert round(out.iloc[1], 4) == 0.03   # cap enforced (1.5 not 2.0) AND lagged scale

def test_first_period_leverage_cost_charged():
    idx = pd.date_range("2020-01-01", periods=2, freq="D")
    carry = pd.Series([0.0, 0.0], index=idx)
    vf = pd.Series([0.10, 0.10], index=idx)  # scale = 1.0
    out = vol_target(carry, vf, target_vol=0.10, cap=1.5, cadence="D", cost_bps=10.0)
    # day0: leverage 0->1.0, turnover 1.0, cost = 10/1e4 * 1.0 = 0.001; no P&L -> -0.001
    assert round(out.iloc[0], 6) == -0.001

def test_overlay_reduces_realized_vol_when_base_is_wild():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    base = pd.Series([0.02, -0.02] * 150, index=idx)   # ~31% annualized vol
    vf = ewma_vol(base)
    out = vol_target(base, vf, target_vol=0.10, cap=1.5, cadence="D", cost_bps=0.0)
    assert metrics(out)["ann_vol"] < metrics(base)["ann_vol"]   # de-risked toward target
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_voltarget.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.backtest.voltarget'`.

- [ ] **Step 3: Write minimal implementation**

`forex/backtest/voltarget.py`:
```python
import pandas as pd

def vol_target(carry_ret: pd.Series, vol_forecast: pd.Series,
               target_vol: float = 0.10, cap: float = 1.5,
               cadence: str = "MS", cost_bps: float = 1.0) -> pd.Series:
    """Scale carry returns to a volatility target.

    scale = clip(target_vol / vol_forecast, upper=cap), stepped at `cadence`
    (held constant between steps), applied to the NEXT day via .shift(1) so
    there is no lookahead, minus turnover cost on leverage changes.
    """
    vf = vol_forecast.reindex(carry_ret.index).ffill()
    raw = (target_vol / vf).clip(upper=cap)
    stepped = raw.resample(cadence).first().reindex(carry_ret.index, method="ffill")
    held = stepped.shift(1).fillna(0.0)                 # no lookahead
    turnover = stepped.diff().abs().fillna(stepped.abs())
    cost = (cost_bps / 1e4) * turnover
    out = (held * carry_ret - cost).rename("ret")
    out.index.name = "date"
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_voltarget.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add forex/backtest/voltarget.py tests/test_voltarget.py
git commit -m "feat: vol-target overlay mechanism (capped, no-lookahead, cadence-stepped)"
```

---

### Task 3: End-to-end overlay wiring + report

**Files:**
- Create: `forex/research/overlay.py`, `tests/test_overlay.py`

**Interfaces:**
- Consumes: `forex.research.carry_baseline.run_baseline`, `forex.features.volforecast.ewma_vol`,
  `forex.backtest.voltarget.vol_target`, `forex.backtest.portfolio.metrics`.
- Produces: `run_overlay(cache_dir, loader=load_series, codes=None, n_long=3, n_short=3, cost_bps=1.0, target_vol=0.10, cap=1.5, cadence="MS", lam=0.94) -> dict`
  with keys `bare` (Series), `overlay` (Series), `metrics_bare` (dict), `metrics_overlay` (dict).
  A `__main__` block runs it against the real FRED cache and prints both metric sets + the distant-era
  comparison.

- [ ] **Step 1: Write the failing test**

`tests/test_overlay.py`:
```python
import numpy as np, pandas as pd
from forex.research.overlay import run_overlay

def _synthetic_loader():
    dates = pd.date_range("2018-01-01", periods=600, freq="B")
    series = {
        "DEXUSAL": pd.Series(1.0 + np.linspace(0, 0.2, 600), index=dates, name="value"),
        "DEXUSEU": pd.Series(1.1 + np.zeros(600), index=dates, name="value"),
        "IR3TIB01USM156N": pd.Series(1.0, index=dates, name="value"),  # percent units
        "IR3TIB01AUM156N": pd.Series(6.0, index=dates, name="value"),
        "IR3TIB01EZM156N": pd.Series(0.0, index=dates, name="value"),
    }
    def loader(series_id, *, cache_dir, client=None):
        return series[series_id]
    return loader

def test_run_overlay_returns_bare_and_overlay():
    out = run_overlay(cache_dir="unused", loader=_synthetic_loader(),
                      codes=["AUD", "EUR"], n_long=1, n_short=1, cadence="D")
    assert set(out) == {"bare", "overlay", "metrics_bare", "metrics_overlay"}
    assert isinstance(out["bare"], pd.Series) and isinstance(out["overlay"], pd.Series)
    assert "sharpe" in out["metrics_bare"] and "sharpe" in out["metrics_overlay"]
    assert len(out["overlay"]) == len(out["bare"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_overlay.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'forex.research.overlay'`.

- [ ] **Step 3: Write minimal implementation**

`forex/research/overlay.py`:
```python
from forex.data.fred import load_series
from forex.research.carry_baseline import run_baseline
from forex.features.volforecast import ewma_vol
from forex.backtest.voltarget import vol_target
from forex.backtest.portfolio import metrics

def run_overlay(cache_dir, loader=load_series, codes=None, n_long=3, n_short=3,
                cost_bps=1.0, target_vol=0.10, cap=1.5, cadence="MS", lam=0.94):
    bare, m_bare = run_baseline(cache_dir, loader=loader, codes=codes,
                                n_long=n_long, n_short=n_short, cost_bps=cost_bps)
    vf = ewma_vol(bare, lam=lam)
    overlay = vol_target(bare, vf, target_vol=target_vol, cap=cap,
                         cadence=cadence, cost_bps=cost_bps)
    return {"bare": bare, "overlay": overlay,
            "metrics_bare": m_bare, "metrics_overlay": metrics(overlay)}

if __name__ == "__main__":
    from forex.backtest.validation import distant_window
    out = run_overlay(cache_dir="data_cache")
    bare, overlay = out["bare"], out["overlay"]
    print("=" * 64)
    print("CARRY + EWMA VOL-TARGET OVERLAY  (target 10% ann, cap 1.5x, monthly)")
    print("=" * 64)
    active = overlay.loc[overlay != 0]
    first = active.index[0] if len(active) else overlay.index[0]
    for label, m in [("bare carry     ", out["metrics_bare"]),
                     ("vol-target     ", out["metrics_overlay"])]:
        print(f"{label}  total {m['total_return']*100:+.0f}%  ann {m['ann_return']*100:+.1f}%  "
              f"vol {m['ann_vol']*100:.1f}%  Sharpe {m['sharpe']:.2f}  "
              f"maxDD {m['max_drawdown']*100:.0f}%  Calmar {m['calmar']:.2f}")
    recent, dist = distant_window(overlay.loc[first:].index, holdout_years=3)
    ov = overlay.loc[first:]
    print(f"\nDISTANT-ERA (earliest 3y) vol-target: "
          f"{((1+ov.iloc[dist]).prod()-1)*100:+.1f}%   "
          f"recent: {((1+ov.iloc[recent]).prod()-1)*100:+.1f}%")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_overlay.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add forex/research/overlay.py tests/test_overlay.py
git commit -m "feat: end-to-end EWMA vol-target overlay + report"
```

- [ ] **Step 6: Full suite + live sanity run (manual)**

Run `.venv/bin/python -m pytest -q` (all green). Then, with the FRED cache populated (from the
baseline run), run `.venv/bin/python -m forex.research.overlay` and record the two metric rows.
**Success for Stage A = the vol-target row beats bare carry's Sharpe/Calmar and cuts maxDD** below
−27%, and holds up on the distant era. Record these numbers — they are the Stage-A result and the
new yardstick the ML stage (next plan) must beat.

---

## Self-Review

**1. Spec coverage.** Spec §2 overlay mechanism → Task 2 (`vol_target`, capped, no-lookahead, cadence,
turnover cost) ✓. §3 Stage A EWMA → Task 1 (`ewma_vol`) ✓. §6 evaluation (vs bare carry + distant-era,
judged on risk-adjusted P&L) → Task 3 `run_overlay` + `__main__` + Step 6 ✓. §8 defaults
(lam 0.94 / target_vol 0.10 / cap 1.5 / monthly) → carried as the function defaults ✓. Explicitly OUT
of scope (Stage B, correctly deferred to the next plan): the GBM model, the cross-asset/COT feature
builders, and the VIX/MOVE/credit/COT loaders.

**2. Placeholder scan.** No TBD/TODO; every code step has complete code; every test step has a real
assertion. The one manual step (Task 3 Step 6) is a live-cache run that cannot be unit-tested offline
and is labeled as such.

**3. Type consistency.** `ewma_vol(returns, lam, periods_per_year)` consistent (Tasks 1, 2, 3).
`vol_target(carry_ret, vol_forecast, target_vol, cap, cadence, cost_bps)` consistent (Tasks 2, 3).
`run_overlay(...)` returns the exact `{bare, overlay, metrics_bare, metrics_overlay}` dict the test
asserts. `run_baseline` and `metrics` are consumed with their existing merged signatures.

---

## What the next plan covers (Stage B, not this one)
The ML vol forecaster: VIX/MOVE/credit (FRED) + CFTC COT loaders, the cross-asset feature builders,
`HistGradientBoostingRegressor` + walk-forward CV, and the overlaid backtest that ships only if it
beats this Stage-A EWMA vol-target OOS on a distant era.

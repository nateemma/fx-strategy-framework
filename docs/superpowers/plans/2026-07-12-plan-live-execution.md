# Live Execution (Paper) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a strategy forward on cache-backed data with reconciled paper orders — the `Execution` seam, a fully-testable `SimExecution`, the `rebalance_now` runner, and the `dryrun`/`download` CLI modes — sharing the same `Strategy` objects as backtest. The real ib_async broker adapter is a stubbed interface, deferred.

**Architecture:** An `Execution` protocol where the executor *owns current state* (`SimExecution` in a JSON portfolio file; a future `LiveExecution` from the broker). `rebalance_now(strategy, view, execution)` is a pure function: compute the latest target weights, take the latest prices, hand both to the executor. The CLI `dryrun` mode drives it with `SimExecution`; a decoupled `download` mode force-refreshes the FRED cache.

**Tech Stack:** Python 3.11+ stdlib (`json`, `dataclasses`, `typing.Protocol`), pandas, pytest. No new dependencies (ib_async is deferred). Reuses `DataView`, `Strategy`, `build_strategy`, `load_series`, `CURRENCIES`, and the existing CLI plumbing.

## Global Constraints
- Project root `~/Documents/forex`; code under `forex/`, tests under `tests/`; venv `~/Documents/forex/.venv`.
- **The executor owns current state** (sim = file, live = broker); the runner never tracks positions.
- **No lookahead:** the runner computes targets from `view.truncate(<latest date>)` — the same causal path as backtest.
- **Offline:** every test uses temp files / mock executors / injected loaders — no network, no broker.
- ib_async `LiveExecution` is an interface-only stub (raises `NotImplementedError`). Real-money `live` mode is a later plan.
- Commit after every task (conventional commits).

---

## File Structure
- `forex/data/fred.py` — add a `force` param to `load_series` (MODIFY).
- `forex/data/refresh.py` — `refresh_cache` (CREATE).
- `forex/run/execution.py` — `RebalanceReport`, `Execution` protocol, `SimExecution`, `LiveExecution` stub (CREATE).
- `forex/run/live.py` — `rebalance_now` (CREATE).
- `forex/core/env.py` — add `starting_equity` (MODIFY).
- `forex/cli.py` — `download` + `dryrun` modes (MODIFY).
- tests alongside each.

---

### Task 1: `load_series` force-refetch + `refresh_cache`

**Files:** Modify `forex/data/fred.py`. Create `forex/data/refresh.py`, `tests/test_refresh.py`

**Interfaces:**
- `load_series(series_id, *, cache_dir, client=None, force=False) -> pd.Series` — when `force=True`, skip the cache read and always fetch + overwrite.
- `refresh_cache(cache_dir, codes=None, loader=load_series) -> list[str]` — force-fetches every FRED series for the universe (USD rate + each currency's rate and spot series) and returns the list of series IDs fetched.

- [ ] **Step 1: Write the failing test**

`tests/test_refresh.py`:
```python
import pandas as pd
from forex.config import CURRENCIES
from forex.data.fred import load_series
from forex.data.refresh import refresh_cache

class _FakeFred:
    def __init__(self, value): self.value = value
    def get_series(self, series_id):
        return pd.Series([self.value], index=pd.to_datetime(["2020-01-01"]))

def test_force_refetches_over_cache(tmp_path):
    load_series("X", cache_dir=tmp_path, client=_FakeFred(1.0))          # populate cache = 1.0
    cached = load_series("X", cache_dir=tmp_path, client=_FakeFred(2.0)) # no force -> stale cache
    assert cached.iloc[0] == 1.0
    forced = load_series("X", cache_dir=tmp_path, client=_FakeFred(2.0), force=True)
    assert forced.iloc[0] == 2.0                                        # force overwrote

def test_refresh_cache_forces_all_universe_series(tmp_path):
    seen = []
    def loader(series_id, *, cache_dir, client=None, force=False):
        seen.append((series_id, force))
        return pd.Series([1.0], index=pd.to_datetime(["2020-01-01"]))
    ids = refresh_cache(tmp_path, codes=["AUD", "EUR"], loader=loader)
    assert CURRENCIES["USD"].rate_fred in ids
    assert CURRENCIES["AUD"].rate_fred in ids and CURRENCIES["AUD"].spot_fred in ids
    assert all(force is True for _, force in seen)      # every fetch forced
```

- [ ] **Step 2: Run** → `.venv/bin/python -m pytest tests/test_refresh.py -v` → FAIL.

- [ ] **Step 3: Implement**

In `forex/data/fred.py`, change the `load_series` signature and the cache-read guard:
```python
def load_series(series_id: str, *, cache_dir, client=None, force: bool = False) -> pd.Series:
    if not force:
        cached = _read_cache(cache_dir, series_id)
        if cached is not None:
            return cached
    if client is None:
        client = _default_client()
    raw = client.get_series(series_id)
    s = pd.Series(raw, dtype="float64").dropna().sort_index()
    s.index = pd.DatetimeIndex(s.index).tz_localize(None)
    s.index.name = "date"
    s.name = "value"
    _write_cache(cache_dir, series_id, s)
    return s
```
(Only the signature's `force` param and the `if not force:` wrapper around the cache read change; the fetch/write body is unchanged.)

`forex/data/refresh.py`:
```python
from forex.config import CURRENCIES
from forex.data.fred import load_series

def refresh_cache(cache_dir, codes=None, loader=load_series) -> list:
    """Force-refetch every FRED series the universe needs, overwriting the cache."""
    if codes is None:
        codes = [c for c in CURRENCIES if c != "USD"]
    ids = [CURRENCIES["USD"].rate_fred]
    for c in codes:
        cur = CURRENCIES[c]
        ids.append(cur.rate_fred)
        if cur.spot_fred:
            ids.append(cur.spot_fred)
    for sid in ids:
        loader(sid, cache_dir=cache_dir, force=True)
    return ids
```

- [ ] **Step 4: Run** → both tests PASS. Then full suite `.venv/bin/python -m pytest -q` (the `load_series` change must not break existing fred/data tests) → all green.

- [ ] **Step 5: Commit**
```bash
git add forex/data/fred.py forex/data/refresh.py tests/test_refresh.py
git commit -m "feat: load_series force-refetch + refresh_cache (for forex download)"
```

---

### Task 2: Execution seam (RebalanceReport, Execution, SimExecution, LiveExecution stub)

**Files:** Create `forex/run/execution.py`, `tests/test_execution.py`

**Interfaces:**
- `RebalanceReport` dataclass: `orders: dict`, `positions: dict`, `equity: float`, `turnover: float`, `cost: float`, `applied: bool`.
- `Execution` (Protocol): `rebalance(target_weights: pd.Series, prices: pd.Series) -> RebalanceReport`.
- `SimExecution(portfolio_path, starting_equity=10000.0, cost_bps=1.0, max_position_weight=None, preview=False)` — persists `{equity, weights, last_prices, last_date}` JSON; `rebalance` marks-to-market (spot P&L since last run), optionally clips to `±max_position_weight`, charges turnover cost, computes per-currency notional orders, and (unless `preview`) writes the new state.
- `LiveExecution` — stub whose `rebalance` raises `NotImplementedError`.

- [ ] **Step 1: Write the failing test**

`tests/test_execution.py`:
```python
import pandas as pd, pytest
from forex.run.execution import SimExecution, LiveExecution, RebalanceReport

def test_first_rebalance_inits_and_applies(tmp_path):
    pf = tmp_path / "pf.json"
    ex = SimExecution(pf, starting_equity=10000.0, cost_bps=0.0)
    r = ex.rebalance(pd.Series({"AUD": 1.0, "EUR": -1.0}), pd.Series({"AUD": 1.0, "EUR": 1.1}))
    assert r.applied and pf.exists()
    assert r.positions == {"AUD": 1.0, "EUR": -1.0}
    assert round(r.turnover, 6) == 2.0                # 0->1 and 0->-1
    assert round(r.orders["AUD"], 2) == 10000.0       # weight delta * equity
    assert round(r.equity, 2) == 10000.0              # cost 0, no prior book to mark

def test_second_rebalance_marks_to_market(tmp_path):
    pf = tmp_path / "pf.json"
    ex = SimExecution(pf, starting_equity=10000.0, cost_bps=0.0)
    ex.rebalance(pd.Series({"AUD": 1.0}), pd.Series({"AUD": 1.0}))       # long AUD @ 1.0
    r = ex.rebalance(pd.Series({"AUD": 1.0}), pd.Series({"AUD": 1.10}))  # AUD +10%, same weight
    assert round(r.equity, 2) == 11000.0              # 10000 * 1.10, no turnover -> no cost

def test_preview_writes_nothing(tmp_path):
    pf = tmp_path / "pf.json"
    r = SimExecution(pf, preview=True).rebalance(pd.Series({"AUD": 1.0}), pd.Series({"AUD": 1.0}))
    assert r.applied is False and not pf.exists()

def test_max_position_weight_clips(tmp_path):
    r = SimExecution(tmp_path / "pf.json", max_position_weight=0.5, cost_bps=0.0
                     ).rebalance(pd.Series({"AUD": 1.0}), pd.Series({"AUD": 1.0}))
    assert r.positions["AUD"] == 0.5

def test_live_execution_is_not_implemented():
    with pytest.raises(NotImplementedError):
        LiveExecution().rebalance(pd.Series(dtype=float), pd.Series(dtype=float))
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

`forex/run/execution.py`:
```python
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import pandas as pd

@dataclass
class RebalanceReport:
    orders: dict
    positions: dict
    equity: float
    turnover: float
    cost: float
    applied: bool

class Execution(Protocol):
    def rebalance(self, target_weights: pd.Series, prices: pd.Series) -> RebalanceReport:
        ...

class SimExecution:
    """Paper executor. Owns its portfolio in a JSON file; marks the book to market with the
    prices passed each rebalance (spot P&L only — the backtest is the precise P&L model)."""
    def __init__(self, portfolio_path, starting_equity: float = 10000.0, cost_bps: float = 1.0,
                 max_position_weight=None, preview: bool = False):
        self.portfolio_path = Path(portfolio_path)
        self.starting_equity = starting_equity
        self.cost_bps = cost_bps
        self.max_position_weight = max_position_weight
        self.preview = preview

    def _load(self) -> dict:
        if self.portfolio_path.exists():
            return json.loads(self.portfolio_path.read_text())
        return {"equity": self.starting_equity, "weights": {}, "last_prices": {}, "last_date": None}

    def rebalance(self, target_weights: pd.Series, prices: pd.Series) -> RebalanceReport:
        state = self._load()
        equity = float(state["equity"])
        weights = {k: float(v) for k, v in state["weights"].items()}
        last_prices = state["last_prices"]

        pnl = 0.0                                        # mark-to-market: spot P&L since last run
        for c, w in weights.items():
            if c in last_prices and last_prices[c] and c in prices.index:
                pnl += w * (float(prices[c]) / float(last_prices[c]) - 1.0)
        equity *= (1.0 + pnl)

        target = {c: float(target_weights[c]) for c in target_weights.index}
        if self.max_position_weight is not None:
            cap = self.max_position_weight
            target = {c: max(-cap, min(cap, w)) for c, w in target.items()}

        keys = set(target) | set(weights)
        turnover = sum(abs(target.get(c, 0.0) - weights.get(c, 0.0)) for c in keys)
        cost = (self.cost_bps / 1e4) * turnover * equity
        equity_after = equity - cost
        orders = {c: (target.get(c, 0.0) - weights.get(c, 0.0)) * equity for c in keys}

        applied = not self.preview
        if applied:
            new_state = {
                "equity": equity_after,
                "weights": target,
                "last_prices": {c: float(prices[c]) for c in prices.index},
                "last_date": str(prices.name) if prices.name is not None else None,
            }
            self.portfolio_path.parent.mkdir(parents=True, exist_ok=True)
            self.portfolio_path.write_text(json.dumps(new_state))

        return RebalanceReport(orders=orders, positions=target, equity=equity_after,
                               turnover=turnover, cost=cost, applied=applied)

class LiveExecution:
    """ib_async broker adapter — NOT IMPLEMENTED (deferred until a TWS/IBKR paper account exists).
    Intended flow: query current positions + NAV from IB; target units = target_weight * NAV / price;
    place IDEALPRO orders to reach target; reconcile fills. Same Execution protocol as SimExecution."""
    def __init__(self, *args, **kwargs):
        pass
    def rebalance(self, target_weights: pd.Series, prices: pd.Series) -> RebalanceReport:
        raise NotImplementedError("LiveExecution (ib_async) is deferred; use SimExecution (paper).")
```

- [ ] **Step 4: Run** → all 5 tests PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/run/execution.py tests/test_execution.py
git commit -m "feat: Execution seam — RebalanceReport, SimExecution (paper), LiveExecution stub"
```

---

### Task 3: `rebalance_now` runner

**Files:** Create `forex/run/live.py`, `tests/test_live_runner.py`

**Interfaces:**
- `rebalance_now(strategy, view, execution) -> RebalanceReport` — computes
  `target = strategy.target_weights(view.truncate(view.calendar[-1])).iloc[-1]` and
  `prices = view.spot.iloc[-1]`, then returns `execution.rebalance(target, prices)`.

- [ ] **Step 1: Write the failing test**

`tests/test_live_runner.py`:
```python
import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.strategies.carry import CarryStrategy
from forex.run.live import rebalance_now
from forex.run.execution import RebalanceReport

def _view():
    idx = pd.date_range("2018-01-01", periods=300, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.2,300), "EUR": 1.1+np.zeros(300)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

class _MockExecution:
    def __init__(self): self.calls = []
    def rebalance(self, target_weights, prices):
        self.calls.append((target_weights, prices))
        return RebalanceReport(orders={}, positions=dict(target_weights),
                               equity=1.0, turnover=0.0, cost=0.0, applied=True)

def test_rebalance_now_passes_latest_target_and_prices():
    view = _view()
    ex = _MockExecution()
    rep = rebalance_now(CarryStrategy(1, 1), view, ex)
    tw, px = ex.calls[0]
    assert set(tw.index) == set(view.codes)              # a target per traded currency
    assert px.name == view.spot.index[-1]                # prices are the LAST spot row
    assert float(px["AUD"]) == float(view.spot["AUD"].iloc[-1])
    assert rep.positions == dict(tw)                     # returns the executor's report
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

`forex/run/live.py`:
```python
def rebalance_now(strategy, view, execution):
    """Compute the strategy's target weights as of the latest available date and reconcile them
    against the executor. The one 'compute-target-and-reconcile' seam shared by dry-run and live."""
    weights = strategy.target_weights(view.truncate(view.calendar[-1]))
    target = weights.iloc[-1]
    prices = view.spot.iloc[-1]
    return execution.rebalance(target, prices)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/run/live.py tests/test_live_runner.py
git commit -m "feat: rebalance_now runner (compute latest target + reconcile via Execution)"
```

---

### Task 4: CLI `download` mode

**Files:** Modify `forex/cli.py`. Test: `tests/test_cli_download.py`

**Interfaces:**
- `build_parser` gains a `download` subcommand (shares the common flags; uses `--universe`/`--cache-dir`).
- `run(cfg, env, "download")` early-returns (before building a view, since the cache may be empty):
  `{"download": {"series": refresh_cache(env.data_cache_dir, codes=cfg.universe), "cache_dir": env.data_cache_dir}}`.
- `_format` prints a `downloaded N series to <dir>` line.

- [ ] **Step 1: Write the failing test**

`tests/test_cli_download.py`:
```python
import forex.cli as cli
import forex.data.refresh as refmod
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def test_run_download(monkeypatch):
    monkeypatch.setattr(refmod, "refresh_cache", lambda cache_dir, codes=None, loader=None: ["S1", "S2"])
    out = cli.run(RunConfig(universe=["AUD"]), EnvConfig(data_cache_dir="/tmp/x"), "download")
    assert out["download"]["series"] == ["S1", "S2"] and out["download"]["cache_dir"] == "/tmp/x"

def test_main_download_prints(monkeypatch, capsys):
    monkeypatch.setattr(refmod, "refresh_cache", lambda cache_dir, codes=None, loader=None: ["S1"])
    rc = cli.main(["download", "--universe", "AUD"])
    assert rc == 0 and "downloaded 1 series" in capsys.readouterr().out
```

- [ ] **Step 2: Run** → `.venv/bin/python -m pytest tests/test_cli_download.py -v` → FAIL.

- [ ] **Step 3: Modify `forex/cli.py`**

In `build_parser`, add `"download"` to the modes tuple:
```python
    for mode in ("backtest", "walkforward", "causal-check", "hyperopt", "download"):
```

In `run`, add this as the **very first** branch (before `view = _build_view(cfg, env)`):
```python
    if mode == "download":
        from forex.data.refresh import refresh_cache
        series = refresh_cache(env.data_cache_dir, codes=cfg.universe)
        return {"download": {"series": series, "cache_dir": env.data_cache_dir}}
```

In `_format`, add this branch before the `str(out)` fallback:
```python
    if "download" in out:
        d = out["download"]
        return f"downloaded {len(d['series'])} series to {d['cache_dir']}"
```

- [ ] **Step 4: Run** → `tests/test_cli_download.py` PASS. Then full suite → all green.

- [ ] **Step 5: Commit**
```bash
git add forex/cli.py tests/test_cli_download.py
git commit -m "feat: CLI download mode (force-refresh FRED cache)"
```

---

### Task 5: `EnvConfig.starting_equity` + CLI `dryrun` mode

**Files:** Modify `forex/core/env.py`, `forex/core/config.py`, `forex/cli.py`. Test: `tests/test_cli_dryrun.py`

**Interfaces:**
- `EnvConfig` gains `starting_equity: float = 10000.0` (env var `FOREX_STARTING_EQUITY`, coerced to float).
- `RunConfig` gains `preview: bool = False`.
- `build_parser` gains a `dryrun` subcommand with `--preview` (flag) and `--equity` (float); `resolve` maps `--preview` into `RunConfig.preview` and `--equity` into `EnvConfig.starting_equity`.
- `run(cfg, env, "dryrun")` builds a `SimExecution` (portfolio at `env.output_dir/portfolio.json`,
  `starting_equity=env.starting_equity`, `cost_bps=cfg.cost_bps`, `preview=cfg.preview`) and returns
  `{"dryrun": rebalance_now(build_strategy(cfg.strategy, cfg.strategy_params), view, ex)}`.
- `_format` prints the rebalance report (equity/turnover/cost + non-zero orders; PREVIEW when not applied).

- [ ] **Step 1: Write the failing test**

`tests/test_cli_dryrun.py`:
```python
import numpy as np, pandas as pd
import forex.cli as cli
from forex.cli import build_parser, resolve
from forex.core.dataview import DataView
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def _view():
    idx = pd.date_range("2018-01-01", periods=300, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.2,300), "EUR": 1.1+np.zeros(300)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_env_starting_equity_default_and_override():
    assert EnvConfig.load(environ={}).starting_equity == 10000.0
    assert EnvConfig.load(environ={"FOREX_STARTING_EQUITY": "5000"}).starting_equity == 5000.0

def test_resolve_dryrun_flags():
    cfg, env, mode = resolve(build_parser().parse_args(
        ["dryrun", "--strategy", "carry", "--preview", "--equity", "5000"]))
    assert mode == "dryrun" and cfg.preview is True and env.starting_equity == 5000.0

def test_run_dryrun_preview(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", strategy_params={"n_long": 1, "n_short": 1}, preview=True),
                  EnvConfig(output_dir=str(tmp_path)), "dryrun")
    rep = out["dryrun"]
    assert rep.applied is False and set(rep.positions) == {"AUD", "EUR"}
    assert not (tmp_path / "portfolio.json").exists()      # preview wrote nothing

def test_main_dryrun_prints(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    rc = cli.main(["dryrun", "--strategy", "carry", "--param", "n_long=1", "--param", "n_short=1", "--preview"])
    assert rc == 0 and "rebalance" in capsys.readouterr().out
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

In `forex/core/env.py`, add the field to `EnvConfig` (after `dry_run`):
```python
    starting_equity: float = 10000.0
```
and in `load`, add to the `env_map` dict and coerce it (alongside the existing `ib_port` coercion):
```python
            "starting_equity": environ.get("FOREX_STARTING_EQUITY"),
```
then after the `if "ib_port" in d:` block:
```python
        if "starting_equity" in d:
            d["starting_equity"] = float(d["starting_equity"])
```

In `forex/core/config.py`, add to `RunConfig` (after `tune`):
```python
    preview: bool = False
```

In `forex/cli.py` `build_parser`, add `"dryrun"` to the modes tuple and its flags:
```python
    for mode in ("backtest", "walkforward", "causal-check", "hyperopt", "download", "dryrun"):
        ...
        if mode == "dryrun":
            sp.add_argument("--preview", action="store_true")
            sp.add_argument("--equity", type=float)
```
In `resolve`, `--preview` is a `RunConfig` field so it goes in the **overrides dict** (before
`cfg = cfg.merge(overrides)`), alongside the other flag→override mappings:
```python
    if getattr(args, "preview", False):
        overrides["preview"] = True
```
`--equity` mutates the **`EnvConfig`**, so it goes **after** `env = EnvConfig.load()` — right next to
the existing `--cache-dir` handling (both use `dataclasses.replace`, already imported):
```python
    equity = getattr(args, "equity", None)
    if equity is not None:
        env = replace(env, starting_equity=equity)
```
(Do NOT put the `--equity` block near the overrides — `env` doesn't exist until after the merge.)

Add the `dryrun` branch to `run` (after the `hyperopt` branch, before the final `raise`):
```python
    if mode == "dryrun":
        import os
        from forex.run.execution import SimExecution
        from forex.run.live import rebalance_now
        pf = os.path.join(env.output_dir, "portfolio.json")
        ex = SimExecution(pf, starting_equity=env.starting_equity, cost_bps=cfg.cost_bps,
                          preview=cfg.preview)
        rep = rebalance_now(build_strategy(cfg.strategy, cfg.strategy_params), view, ex)
        return {"dryrun": rep}
```

Add the `dryrun` branch to `_format` (before the `str(out)` fallback):
```python
    if "dryrun" in out:
        rep = out["dryrun"]
        head = f"{'PREVIEW ' if not rep.applied else ''}rebalance -> equity {rep.equity:.2f}  " \
               f"turnover {rep.turnover:.3f}  cost {rep.cost:.2f}"
        lines = [head, "orders (notional):"]
        for c, v in sorted(rep.orders.items(), key=lambda kv: -abs(kv[1])):
            if abs(v) > 1e-6:
                lines.append(f"  {c:5} {v:+.2f}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run** → `tests/test_cli_dryrun.py` PASS (all four). Then full suite → all green.

- [ ] **Step 5: Commit**
```bash
git add forex/core/env.py forex/core/config.py forex/cli.py tests/test_cli_dryrun.py
git commit -m "feat: CLI dryrun mode (paper rebalance) + EnvConfig.starting_equity"
```

- [ ] **Step 6: Live sanity (manual, venv active)**

Against the real cache: `forex dryrun --strategy carry_voltarget --param n_long=3 --param n_short=3 --preview`
prints the paper orders + target book without writing. Then a non-preview run writes
`runs/portfolio.json`; a second run marks it to market. And `forex download --universe AUD,EUR,SEK`
(with `FRED_API_KEY` set) re-fetches those series. Record the dryrun output.

---

## Self-Review

**1. Spec coverage.** Execution seam (protocol + SimExecution + LiveExecution stub) → Task 2 ✓.
`rebalance_now` pure core → Task 3 ✓. `dryrun` CLI (+ preview, equity, portfolio file) → Task 5 ✓.
`download` CLI + `refresh_cache` + `load_series` force → Tasks 1, 4 ✓. `EnvConfig.starting_equity` →
Task 5 ✓. Safety (`--preview`, `max_position_weight`, `dry_run`) → Tasks 2, 5 ✓. Offline testing (temp
files, mock executor, injected loader, monkeypatched view) → all tasks ✓. Deferred (per spec): real
ib_async `LiveExecution` (stub only), `live` mode, daemon scheduler, carry-accrual in paper P&L.

**2. Placeholder scan.** No TBD/TODO; complete code in every step; every test asserts real behavior.
The one manual step (Task 5 Step 6) is a live-cache run, labeled.

**3. Type consistency.** `load_series(..., force=False)` consistent (1, 4). `refresh_cache(cache_dir, codes, loader)` consistent (1, 4). `RebalanceReport(orders, positions, equity, turnover, cost, applied)` consistent (2, 3, 5). `Execution.rebalance(target_weights, prices) -> RebalanceReport` consistent (2, 3, 5). `SimExecution(portfolio_path, starting_equity, cost_bps, max_position_weight, preview)` consistent (2, 5). `rebalance_now(strategy, view, execution)` consistent (3, 5). Reuses `DataView`/`build_strategy`/`_build_view`/`resolve`/`run`/`_format` with their current shapes.

---

## What the next plan covers (not this one)
- The real **ib_async `LiveExecution`** adapter + a **`live`** (real-money) CLI mode with a kill-switch,
  hard notional/position limits, and an explicit live-confirmation gate — once a TWS/paper account exists.

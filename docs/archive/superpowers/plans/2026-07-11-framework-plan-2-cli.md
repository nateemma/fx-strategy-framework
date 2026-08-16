# FX Framework — Plan 2: Config + Registry + CLI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the framework driveable from the command line and from reproducible config files: `RunConfig` (experiment) + `EnvConfig` (infra/secrets), a strategy registry, and a thin argparse CLI (`python -m forex <mode> …`) for the `backtest`, `walkforward`, and `causal-check` modes.

**Architecture:** `RunConfig`/`EnvConfig` are dataclasses that load from TOML (stdlib `tomllib`) and merge with precedence defaults←file←env←flags. A registry maps a strategy name → a builder that turns a params dict into a `Strategy` (including the composed `carry_voltarget`). The CLI resolves the two configs, builds a `DataView` + `Strategy`, and calls the existing drivers (`backtest`/`walk_forward`/`assert_causal`) — one code path shared with hand-written scripts.

**Tech Stack:** Python 3.11+ stdlib (`argparse`, `tomllib`, `dataclasses`), pandas, pytest. No new dependencies. Reuses Plan-1 `DataView`, `CarryStrategy`, `VolTargetOverlay`, `backtest`, `walk_forward`, `assert_causal`.

## Global Constraints
- Project root `~/Documents/forex`; code under `forex/`, tests under `tests/`; venv `~/Documents/forex/.venv`.
- **Two-tier config:** `RunConfig` = experiment params (versioned, TOML + flags); `EnvConfig` = infra/secrets (env vars + optional TOML), never the place for experiment params.
- **Precedence:** defaults < config file < env vars < CLI flags.
- **Format:** TOML via stdlib `tomllib` (read-only); no new dependency.
- Tests must not hit the network (inject env dicts, monkeypatch the view builder). Commit after every task (conventional commits).

**Deferred (NOT this plan):** the `Execution` protocol / `SimExecution` / `LiveExecution` / `LiveRunner` seam (interface-only, unused until the ib_async live plan) and the `plot`/`dryrun`/`live` CLI modes.

---

## File Structure
- `forex/core/config.py` — `RunConfig`.
- `forex/core/env.py` — `EnvConfig`.
- `forex/strategies/registry.py` — `build_strategy` / `available`.
- `forex/cli.py` — arg parsing, config resolution, dispatch (`main`).
- `forex/__main__.py` — entrypoint calling `cli.main`.
- tests alongside each.

---

### Task 1: RunConfig

**Files:** Create `forex/core/config.py`, `tests/test_runconfig.py`

**Interfaces:**
- Produces: `RunConfig` dataclass — fields `strategy: str="carry"`, `strategy_params: dict={}`, `universe: list|None=None`, `timerange: list|None=None`, `cost_bps: float=1.0`, `cadence: str="MS"`, `train_days: int=1000`, `test_days: int=500`. Classmethods `from_dict(d)` (ignores unknown keys), `from_toml(path)`. Method `merge(overrides: dict) -> RunConfig` — non-None overrides win; `strategy_params` merged key-wise.

- [ ] **Step 1: Write the failing test**

`tests/test_runconfig.py`:
```python
from forex.core.config import RunConfig

def test_defaults_and_from_dict():
    c = RunConfig.from_dict({"strategy": "carry_voltarget", "cost_bps": 2.0, "junk": 1})
    assert c.strategy == "carry_voltarget" and c.cost_bps == 2.0
    assert c.cadence == "MS"                      # default preserved
    assert not hasattr(c, "junk")                 # unknown keys ignored

def test_merge_overrides_and_params_merge():
    base = RunConfig(strategy_params={"n_long": 3, "n_short": 3})
    m = base.merge({"cost_bps": 5.0, "strategy_params": {"n_long": 1}, "cadence": None})
    assert m.cost_bps == 5.0
    assert m.strategy_params == {"n_long": 1, "n_short": 3}   # key-wise merge
    assert m.cadence == "MS"                                   # None override ignored

def test_from_toml(tmp_path):
    p = tmp_path / "run.toml"
    p.write_text('strategy = "carry"\ncost_bps = 3.0\n[strategy_params]\nn_long = 2\n')
    c = RunConfig.from_toml(p)
    assert c.strategy == "carry" and c.cost_bps == 3.0 and c.strategy_params == {"n_long": 2}
```

- [ ] **Step 2: Run** → `.venv/bin/python -m pytest tests/test_runconfig.py -v` → FAIL (`No module named 'forex.core.config'`).

- [ ] **Step 3: Write minimal implementation**

`forex/core/config.py`:
```python
from dataclasses import dataclass, field, asdict
import tomllib

@dataclass
class RunConfig:
    strategy: str = "carry"
    strategy_params: dict = field(default_factory=dict)
    universe: list | None = None
    timerange: list | None = None
    cost_bps: float = 1.0
    cadence: str = "MS"
    train_days: int = 1000
    test_days: int = 500

    @classmethod
    def from_dict(cls, d: dict) -> "RunConfig":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})

    @classmethod
    def from_toml(cls, path) -> "RunConfig":
        with open(path, "rb") as fh:
            return cls.from_dict(tomllib.load(fh))

    def merge(self, overrides: dict) -> "RunConfig":
        d = asdict(self)
        for k, v in overrides.items():
            if v is None:
                continue
            if k == "strategy_params":
                d["strategy_params"] = {**d["strategy_params"], **v}
            else:
                d[k] = v
        return RunConfig.from_dict(d)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/core/config.py tests/test_runconfig.py
git commit -m "feat: RunConfig (experiment config, TOML + merge)"
```

---

### Task 2: EnvConfig

**Files:** Create `forex/core/env.py`, `tests/test_envconfig.py`

**Interfaces:**
- Produces: `EnvConfig` dataclass — `data_cache_dir: str="data_cache"`, `fred_api_key: str|None=None`, `output_dir: str="runs"`, `ib_host: str="127.0.0.1"`, `ib_port: int=7497`, `ib_client_id: int=1`, `ib_account: str|None=None`, `dry_run: bool=True`. Classmethod `load(path=None, environ=None) -> EnvConfig` — starts from an optional TOML file, then env vars override (`FRED_API_KEY`, `FOREX_DATA_CACHE_DIR`, `FOREX_OUTPUT_DIR`, `FOREX_IB_HOST`, `FOREX_IB_PORT`, `FOREX_IB_ACCOUNT`); `ib_port` coerced to int. `environ` defaults to `os.environ` (injectable for tests). The IB fields are carried for the later live plan; nothing consumes them yet.

- [ ] **Step 1: Write the failing test**

`tests/test_envconfig.py`:
```python
from forex.core.env import EnvConfig

def test_defaults_when_empty_environ():
    e = EnvConfig.load(environ={})
    assert e.data_cache_dir == "data_cache" and e.dry_run is True and e.fred_api_key is None

def test_env_vars_override():
    e = EnvConfig.load(environ={"FRED_API_KEY": "abc", "FOREX_DATA_CACHE_DIR": "/tmp/c",
                                "FOREX_IB_PORT": "4002"})
    assert e.fred_api_key == "abc" and e.data_cache_dir == "/tmp/c" and e.ib_port == 4002

def test_env_overrides_file(tmp_path):
    p = tmp_path / "env.toml"
    p.write_text('data_cache_dir = "from_file"\noutput_dir = "of"\n')
    e = EnvConfig.load(path=p, environ={"FOREX_DATA_CACHE_DIR": "from_env"})
    assert e.data_cache_dir == "from_env"      # env beats file
    assert e.output_dir == "of"                # file value kept where no env
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/core/env.py`:
```python
import os
import tomllib
from dataclasses import dataclass

@dataclass
class EnvConfig:
    data_cache_dir: str = "data_cache"
    fred_api_key: str | None = None
    output_dir: str = "runs"
    ib_host: str = "127.0.0.1"
    ib_port: int = 7497
    ib_client_id: int = 1
    ib_account: str | None = None
    dry_run: bool = True

    @classmethod
    def load(cls, path=None, environ=None) -> "EnvConfig":
        environ = os.environ if environ is None else environ
        data = {}
        if path and os.path.exists(path):
            with open(path, "rb") as fh:
                data.update(tomllib.load(fh))
        env_map = {
            "data_cache_dir": environ.get("FOREX_DATA_CACHE_DIR"),
            "fred_api_key": environ.get("FRED_API_KEY"),
            "output_dir": environ.get("FOREX_OUTPUT_DIR"),
            "ib_host": environ.get("FOREX_IB_HOST"),
            "ib_port": environ.get("FOREX_IB_PORT"),
            "ib_account": environ.get("FOREX_IB_ACCOUNT"),
        }
        for k, v in env_map.items():
            if v is not None:
                data[k] = v
        known = set(cls.__dataclass_fields__)
        d = {k: v for k, v in data.items() if k in known}
        if "ib_port" in d:
            d["ib_port"] = int(d["ib_port"])
        return cls(**d)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/core/env.py tests/test_envconfig.py
git commit -m "feat: EnvConfig (infra/secrets, env + TOML)"
```

---

### Task 3: Strategy registry

**Files:** Create `forex/strategies/registry.py`, `tests/test_registry.py`

**Interfaces:**
- Consumes: `CarryStrategy`, `VolTargetOverlay`.
- Produces: `build_strategy(name: str, params: dict|None=None) -> Strategy` and `available() -> list[str]`. Registered names: `"carry"` → `CarryStrategy(**params)`; `"carry_voltarget"` → `VolTargetOverlay(CarryStrategy(**base_params), **overlay_params)` where `base_params` are the `n_long`/`n_short` keys and the rest are overlay params. Unknown name → `KeyError`.

- [ ] **Step 1: Write the failing test**

`tests/test_registry.py`:
```python
import pytest
from forex.strategies.registry import build_strategy, available
from forex.strategies.carry import CarryStrategy
from forex.strategies.overlay import VolTargetOverlay

def test_build_carry():
    s = build_strategy("carry", {"n_long": 2, "n_short": 2})
    assert isinstance(s, CarryStrategy) and s.n_long == 2

def test_build_composed_splits_params():
    s = build_strategy("carry_voltarget", {"n_long": 1, "n_short": 1, "target_vol": 0.08, "cap": 2.0})
    assert isinstance(s, VolTargetOverlay)
    assert isinstance(s.base, CarryStrategy) and s.base.n_long == 1
    assert s.target_vol == 0.08 and s.cap == 2.0

def test_unknown_raises_and_available_lists():
    with pytest.raises(KeyError):
        build_strategy("nope")
    assert set(available()) == {"carry", "carry_voltarget"}
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/strategies/registry.py`:
```python
from forex.strategies.carry import CarryStrategy
from forex.strategies.overlay import VolTargetOverlay

_BASE_KEYS = ("n_long", "n_short")

def _carry(p: dict):
    return CarryStrategy(**p)

def _carry_voltarget(p: dict):
    base = CarryStrategy(**{k: p[k] for k in _BASE_KEYS if k in p})
    overlay = {k: v for k, v in p.items() if k not in _BASE_KEYS}
    return VolTargetOverlay(base, **overlay)

_BUILDERS = {"carry": _carry, "carry_voltarget": _carry_voltarget}

def build_strategy(name: str, params: dict | None = None):
    if name not in _BUILDERS:
        raise KeyError(f"unknown strategy '{name}'; available: {sorted(_BUILDERS)}")
    return _BUILDERS[name](params or {})

def available() -> list:
    return sorted(_BUILDERS)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/strategies/registry.py tests/test_registry.py
git commit -m "feat: strategy registry (build_strategy incl composed carry_voltarget)"
```

---

### Task 4: CLI arg parsing + config resolution

**Files:** Create `forex/cli.py`, `tests/test_cli_resolve.py`

**Interfaces:**
- Consumes: `RunConfig`, `EnvConfig`.
- Produces: `build_parser() -> argparse.ArgumentParser` with subcommands `backtest|walkforward|causal-check`, each accepting `--config --strategy --universe --timerange --cost-bps --cadence --param (repeatable k=v) --cache-dir`. `resolve(args) -> (RunConfig, EnvConfig, str)` — `RunConfig` from `--config` (or defaults) then merged with the flag overrides (universe split on `,`; timerange split on `:` into `[start,end]`; params parsed `k=v` with type coercion int→float→bool→str); `EnvConfig` from `EnvConfig.load()` with `--cache-dir` overriding `data_cache_dir`; returns the mode string too. `_coerce(s)` does the scalar typing.

- [ ] **Step 1: Write the failing test**

`tests/test_cli_resolve.py`:
```python
from forex.cli import build_parser, resolve

def _resolve(argv):
    return resolve(build_parser().parse_args(argv))

def test_flags_override_into_runconfig():
    cfg, env, mode = _resolve(["backtest", "--strategy", "carry_voltarget",
                               "--param", "n_long=2", "--param", "target_vol=0.08",
                               "--cost-bps", "2.0", "--universe", "AUD,EUR", "--cache-dir", "/tmp/c"])
    assert mode == "backtest"
    assert cfg.strategy == "carry_voltarget"
    assert cfg.strategy_params == {"n_long": 2, "target_vol": 0.08}   # int + float coerced
    assert cfg.cost_bps == 2.0 and cfg.universe == ["AUD", "EUR"]
    assert env.data_cache_dir == "/tmp/c"

def test_timerange_split():
    cfg, _, _ = _resolve(["walkforward", "--timerange", "2000-01-01:2020-12-31"])
    assert cfg.timerange == ["2000-01-01", "2020-12-31"]

def test_config_file_then_flag(tmp_path):
    p = tmp_path / "r.toml"
    p.write_text('strategy = "carry"\ncost_bps = 9.0\n')
    cfg, _, _ = _resolve(["backtest", "--config", str(p), "--cost-bps", "1.0"])
    assert cfg.strategy == "carry"    # from file
    assert cfg.cost_bps == 1.0        # flag beats file
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/cli.py`:
```python
import argparse
from dataclasses import replace
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def _coerce(s: str):
    for f in (int, float):
        try:
            return f(s)
        except ValueError:
            pass
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    return s

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="forex")
    sub = p.add_subparsers(dest="mode", required=True)
    for mode in ("backtest", "walkforward", "causal-check"):
        sp = sub.add_parser(mode)
        sp.add_argument("--config")
        sp.add_argument("--strategy")
        sp.add_argument("--universe")
        sp.add_argument("--timerange")
        sp.add_argument("--cost-bps", type=float, dest="cost_bps")
        sp.add_argument("--cadence")
        sp.add_argument("--param", action="append", default=[], dest="params")
        sp.add_argument("--cache-dir", dest="cache_dir")
    return p

def resolve(args):
    cfg = RunConfig.from_toml(args.config) if args.config else RunConfig()
    overrides = {}
    if args.strategy is not None:
        overrides["strategy"] = args.strategy
    if args.universe is not None:
        overrides["universe"] = args.universe.split(",")
    if args.timerange is not None:
        a, b = args.timerange.split(":")
        overrides["timerange"] = [a or None, b or None]
    if args.cost_bps is not None:
        overrides["cost_bps"] = args.cost_bps
    if args.cadence is not None:
        overrides["cadence"] = args.cadence
    if args.params:
        sp = {}
        for kv in args.params:
            k, v = kv.split("=", 1)
            sp[k] = _coerce(v)
        overrides["strategy_params"] = sp
    cfg = cfg.merge(overrides)
    env = EnvConfig.load()
    if args.cache_dir:
        env = replace(env, data_cache_dir=args.cache_dir)
    return cfg, env, args.mode
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/cli.py tests/test_cli_resolve.py
git commit -m "feat: CLI arg parsing + config resolution (defaults<file<env<flags)"
```

---

### Task 5: CLI dispatch + entrypoint

**Files:** Modify `forex/cli.py` (add `_build_view`, `run`, `main`). Create `forex/__main__.py`, `tests/test_cli_run.py`

**Interfaces:**
- Consumes: everything above + `DataView`, `build_strategy`, `backtest`, `walk_forward`, `assert_causal`.
- Produces: `_build_view(cfg, env) -> DataView` (from `DataView.from_fred(env.data_cache_dir, codes=cfg.universe)`, sliced to `cfg.timerange` if set); `run(cfg, env, mode) -> dict` (backtest/walkforward → `{"metrics": …}`, causal-check → `{"causal": "PASS"}`); `main(argv=None) -> int` (parse → resolve → run → print). `forex/__main__.py` calls `main`.

- [ ] **Step 1: Write the failing test**

`tests/test_cli_run.py`:
```python
import numpy as np, pandas as pd
import forex.cli as cli
from forex.core.dataview import DataView
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def _view():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.zeros(400)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_run_backtest(monkeypatch):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", strategy_params={"n_long":1,"n_short":1}),
                  EnvConfig(), "backtest")
    assert "sharpe" in out["metrics"]

def test_run_causal_check(monkeypatch):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", strategy_params={"n_long":1,"n_short":1}),
                  EnvConfig(), "causal-check")
    assert out["causal"] == "PASS"

def test_main_end_to_end(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    rc = cli.main(["backtest", "--strategy", "carry", "--param", "n_long=1", "--param", "n_short=1"])
    assert rc == 0
    assert "sharpe" in capsys.readouterr().out
```

- [ ] **Step 2: Run** → FAIL (`run`/`main` not defined).

- [ ] **Step 3: Add to `forex/cli.py`** (append these functions)

```python
def _build_view(cfg, env):
    from forex.core.dataview import DataView
    view = DataView.from_fred(env.data_cache_dir, codes=cfg.universe)
    if cfg.timerange:
        s, e = cfg.timerange
        spot = view.spot.loc[s:e]
        rates = {k: v.loc[s:e] for k, v in view.rates.items()}
        view = DataView(spot=spot, rates=rates)
    return view

def run(cfg, env, mode) -> dict:
    from forex.strategies.registry import build_strategy
    from forex.run.backtest import backtest
    from forex.run.walkforward import walk_forward
    from forex.diagnostics.causal import assert_causal
    view = _build_view(cfg, env)
    if mode == "backtest":
        r = backtest(build_strategy(cfg.strategy, cfg.strategy_params), view, cfg.cost_bps)
        return {"metrics": r.metrics}
    if mode == "walkforward":
        r = walk_forward(lambda: build_strategy(cfg.strategy, cfg.strategy_params),
                         view, cfg.train_days, cfg.test_days, cfg.cost_bps)
        return {"metrics": r.metrics}
    if mode == "causal-check":
        strat = build_strategy(cfg.strategy, cfg.strategy_params)
        n = len(view.calendar)
        assert_causal(strat, view, view.calendar[[n // 4, n // 2, n - 1]])
        return {"causal": "PASS"}
    raise ValueError(f"unknown mode {mode}")

def _format(out: dict) -> str:
    if "metrics" in out:
        m = out["metrics"]
        keys = ["total_return", "ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar"]
        return "  ".join(f"{k}={m[k]:.4f}" for k in keys if k in m)
    return str(out)

def main(argv=None) -> int:
    cfg, env, mode = resolve(build_parser().parse_args(argv))
    print(_format(run(cfg, env, mode)))
    return 0
```

`forex/__main__.py`:
```python
from forex.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run** → `.venv/bin/python -m pytest tests/test_cli_run.py -v` → PASS (all three).

- [ ] **Step 5: Commit**
```bash
git add forex/cli.py forex/__main__.py tests/test_cli_run.py
git commit -m "feat: CLI dispatch + entrypoint (backtest/walkforward/causal-check)"
```

- [ ] **Step 6: Full suite + live CLI sanity (manual)**

Run `.venv/bin/python -m pytest -q` (all green). Then against the real cache:
`.venv/bin/python -m forex --help` (shows the subcommands),
`.venv/bin/python -m forex backtest --strategy carry_voltarget --param n_long=3 --param n_short=3`
and confirm it prints metrics matching the overlay report (Sharpe ~0.35). Record it.

---

## Self-Review

**1. Spec coverage.** RunConfig (experiment config, TOML+merge) → Task 1 ✓. EnvConfig (infra/secrets, env+TOML, precedence) → Task 2 ✓. Registry (name→Strategy, incl composed) → Task 3 ✓. Thin argparse CLI, defaults<file<env<flags, `python -m forex <mode>` → Tasks 4–5 ✓. Modes backtest/walkforward/causal-check ✓. Explicitly deferred (noted): the Execution/LiveRunner seam and plot/dryrun/live modes. TOML via stdlib `tomllib`, no new dep ✓.

**2. Placeholder scan.** No TBD/TODO; every code step is complete; every test asserts real behavior. The one manual step (Task 5 Step 6) is a live-cache CLI run, labeled.

**3. Type consistency.** `RunConfig` fields/`from_dict`/`from_toml`/`merge` consistent (1,4,5). `EnvConfig.load(path, environ)` consistent (2,4). `build_strategy(name, params)`/`available()` consistent (3,4,5). `resolve(args) -> (RunConfig, EnvConfig, mode)` consistent (4,5). `run(cfg, env, mode)` + `_build_view(cfg, env)` consistent (5). Reuses Plan-1 `DataView.from_fred(cache_dir, codes)`, `backtest`, `walk_forward`, `assert_causal` with their merged signatures.

---

## What the next plans cover (not this one)
- **Plan 3 — hyperopt:** `Space` types + the walk-forward-scored optimizer that outputs a `RunConfig`, and a `hyperopt` CLI mode.
- **Live plan:** the `Execution` protocol + `SimExecution` + `LiveExecution`/`LiveRunner` (ib_async) seam + `dryrun`/`live` CLI modes.

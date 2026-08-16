# FX Framework — Plan 3: Hyperopt

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hyperparameter optimization: `Space` types, `search_space()` on the strategies, a random-search optimizer scored on **walk-forward OOS** (the crypto in-sample-overfit lesson baked in) whose output is a reproducible `RunConfig`, and a `hyperopt` CLI mode.

**Architecture:** A strategy declares tunable ranges via `search_space() -> {name: Space}` (metadata, decoupled from values). The optimizer samples the space (stdlib `random`, seeded), builds a strategy per sample via the registry, scores it with the `walk_forward` driver, and returns the best params + OOS metrics + the in-sample-vs-OOS gap. The winner is printed as a `RunConfig` TOML block (visible, versionable — no hidden override).

**Tech Stack:** Python 3.11+ stdlib (`random`, `dataclasses`, `tomllib`), pandas, pytest. No new dependencies. Reuses `walk_forward`, `backtest`, `build_strategy`, `RunConfig`.

## Global Constraints
- Project root `~/Documents/forex`; code under `forex/`, tests under `tests/`; venv `~/Documents/forex/.venv`.
- **OOS objective by default:** hyperopt scores on `walk_forward` (not in-sample); the result reports the in-sample-vs-OOS gap as the overfit indicator.
- **Output is a `RunConfig`** (visible TOML), not a hidden override file.
- **Reproducible:** sampling uses `random.Random(seed)`; same seed → same result.
- Stdlib random search (spaces are tiny); `search_space()` stays optimizer-agnostic. No new deps. Tests offline. Commit after every task.

---

## File Structure
- `forex/core/space.py` — `Float` / `Int` / `Categorical`.
- `forex/strategies/carry.py`, `forex/strategies/overlay.py` — add `search_space()` (MODIFY).
- `forex/core/config.py` — add `to_toml_str()` + hyperopt fields (MODIFY).
- `forex/run/hyperopt.py` — `optimize(...)`.
- `forex/cli.py` — add the `hyperopt` mode (MODIFY).
- tests alongside each.

---

### Task 1: Space types

**Files:** Create `forex/core/space.py`, `tests/test_space.py`

**Interfaces:**
- Produces: `Float(low, high)`, `Int(low, high)`, `Categorical(choices)` dataclasses, each with `sample(rng: random.Random)` — `Float`→`rng.uniform`, `Int`→`rng.randint` (inclusive), `Categorical`→`rng.choice`.

- [ ] **Step 1: Write the failing test**

`tests/test_space.py`:
```python
import random
from forex.core.space import Float, Int, Categorical

def test_ranges_respected():
    rng = random.Random(0)
    assert 0.0 <= Float(0.0, 1.0).sample(rng) <= 1.0
    assert 2 <= Int(2, 5).sample(rng) <= 5
    assert Categorical(["a", "b", "c"]).sample(rng) in ("a", "b", "c")

def test_deterministic_with_seed():
    a, b = random.Random(42), random.Random(42)
    assert Float(0, 10).sample(a) == Float(0, 10).sample(b)
    assert Int(0, 100).sample(a) == Int(0, 100).sample(b)
```

- [ ] **Step 2: Run** → `.venv/bin/python -m pytest tests/test_space.py -v` → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/core/space.py`:
```python
import random
from dataclasses import dataclass

@dataclass
class Float:
    low: float
    high: float
    def sample(self, rng: random.Random) -> float:
        return rng.uniform(self.low, self.high)

@dataclass
class Int:
    low: int
    high: int
    def sample(self, rng: random.Random) -> int:
        return rng.randint(self.low, self.high)

@dataclass
class Categorical:
    choices: list
    def sample(self, rng: random.Random):
        return rng.choice(self.choices)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/core/space.py tests/test_space.py
git commit -m "feat: hyperopt Space types (Float/Int/Categorical)"
```

---

### Task 2: search_space() on the strategies

**Files:** Modify `forex/strategies/carry.py`, `forex/strategies/overlay.py`. Test: `tests/test_search_space.py`

**Interfaces:**
- `CarryStrategy.search_space()` → `{"n_long": Int(2,4), "n_short": Int(2,4)}`.
- `VolTargetOverlay.search_space()` → `{**self.base.search_space(), "target_vol": Float(0.06,0.15), "cap": Float(1.0,2.0)}` (merges the base's space, so the composed strategy is tunable in one flat dict that `build_strategy` re-splits).

- [ ] **Step 1: Write the failing test**

`tests/test_search_space.py`:
```python
from forex.strategies.carry import CarryStrategy
from forex.strategies.overlay import VolTargetOverlay
from forex.core.space import Int, Float

def test_carry_search_space():
    s = CarryStrategy().search_space()
    assert set(s) == {"n_long", "n_short"} and isinstance(s["n_long"], Int)

def test_overlay_merges_base_space():
    s = VolTargetOverlay(CarryStrategy()).search_space()
    assert set(s) == {"n_long", "n_short", "target_vol", "cap"}   # base keys + overlay knobs
    assert isinstance(s["target_vol"], Float) and isinstance(s["n_long"], Int)
```

- [ ] **Step 2: Run** → FAIL (base `Strategy.search_space` returns `{}`).

- [ ] **Step 3: Add the methods**

Append to the `CarryStrategy` class in `forex/strategies/carry.py`:
```python
    def search_space(self) -> dict:
        from forex.core.space import Int
        return {"n_long": Int(2, 4), "n_short": Int(2, 4)}
```

Append to the `VolTargetOverlay` class in `forex/strategies/overlay.py`:
```python
    def search_space(self) -> dict:
        from forex.core.space import Float
        return {**self.base.search_space(),
                "target_vol": Float(0.06, 0.15), "cap": Float(1.0, 2.0)}
```

- [ ] **Step 4: Run** → `.venv/bin/python -m pytest tests/test_search_space.py -v` → PASS.

- [ ] **Step 5: Commit**
```bash
git add forex/strategies/carry.py forex/strategies/overlay.py tests/test_search_space.py
git commit -m "feat: search_space() on CarryStrategy and VolTargetOverlay"
```

---

### Task 3: RunConfig — to_toml_str() + hyperopt fields

**Files:** Modify `forex/core/config.py`. Test: `tests/test_runconfig_toml.py`

**Interfaces:**
- Add fields to `RunConfig`: `n_samples: int = 200`, `seed: int = 0`, `objective: str = "sharpe"`, `tune: list | None = None`.
- Add method `to_toml_str() -> str` — emits a valid TOML block for the flat config: top-level scalars `strategy`, `cost_bps` (and `universe` if set), then a `[strategy_params]` table. Strings quoted, bools lowercased, lists as TOML arrays.

- [ ] **Step 1: Write the failing test**

`tests/test_runconfig_toml.py`:
```python
import tomllib
from forex.core.config import RunConfig

def test_hyperopt_fields_default():
    c = RunConfig()
    assert c.n_samples == 200 and c.seed == 0 and c.objective == "sharpe" and c.tune is None

def test_to_toml_str_roundtrips():
    c = RunConfig(strategy="carry_voltarget", cost_bps=2.0,
                  strategy_params={"n_long": 3, "target_vol": 0.083}, universe=["AUD", "EUR"])
    parsed = tomllib.loads(c.to_toml_str())
    assert parsed["strategy"] == "carry_voltarget"
    assert parsed["cost_bps"] == 2.0
    assert parsed["universe"] == ["AUD", "EUR"]
    assert parsed["strategy_params"] == {"n_long": 3, "target_vol": 0.083}
```

- [ ] **Step 2: Run** → `.venv/bin/python -m pytest tests/test_runconfig_toml.py -v` → FAIL.

- [ ] **Step 3: Modify `forex/core/config.py`**

Add the four fields to the `RunConfig` dataclass (after `test_days`):
```python
    n_samples: int = 200
    seed: int = 0
    objective: str = "sharpe"
    tune: list | None = None
```

Add this method to the `RunConfig` class:
```python
    def to_toml_str(self) -> str:
        def fmt(v):
            if isinstance(v, bool):
                return str(v).lower()
            if isinstance(v, str):
                return f'"{v}"'
            if isinstance(v, list):
                return "[" + ", ".join(fmt(x) for x in v) + "]"
            return str(v)
        lines = [f"strategy = {fmt(self.strategy)}", f"cost_bps = {fmt(self.cost_bps)}"]
        if self.universe is not None:
            lines.append(f"universe = {fmt(self.universe)}")
        if self.strategy_params:
            lines.append("[strategy_params]")
            for k, v in self.strategy_params.items():
                lines.append(f"{k} = {fmt(v)}")
        return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run** → both tests PASS. Then the full suite: `.venv/bin/python -m pytest -q` (the new RunConfig fields must not break existing config tests) → all green.

- [ ] **Step 5: Commit**
```bash
git add forex/core/config.py tests/test_runconfig_toml.py
git commit -m "feat: RunConfig.to_toml_str() + hyperopt fields (n_samples/seed/objective/tune)"
```

---

### Task 4: hyperopt optimizer

**Files:** Create `forex/run/hyperopt.py`, `tests/test_hyperopt.py`

**Interfaces:**
- Consumes: `build_strategy`, `walk_forward`, `backtest`, `Space.sample`.
- Produces: `optimize(strategy_name, view, *, train_days, test_days, n_samples=200, seed=0, cost_bps=1.0, base_params=None, tune=None, objective="sharpe") -> dict`. Samples the strategy's `search_space()` (restricted to `tune` keys if given) `n_samples` times with `random.Random(seed)`; for each candidate params dict (base_params overlaid with the samples), scores `walk_forward(...).metrics[objective]`; keeps the best. Returns `{"best_params", "score", "objective", "oos" (best walk-forward metrics), "in_sample" (full backtest metrics of the winner), "n_samples"}`.

- [ ] **Step 1: Write the failing test**

`tests/test_hyperopt.py`:
```python
import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.run.hyperopt import optimize

def _view():
    idx = pd.date_range("2016-01-01", periods=900, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.4,900), "EUR": 1.1+np.zeros(900),
                         "SEK": 1.0+np.linspace(0,0.2,900), "NZD": 1.0+np.linspace(0,0.3,900)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.04, index=idx),
             "NZD": pd.Series(0.05, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_optimize_returns_best_and_gap():
    r = optimize("carry", _view(), train_days=250, test_days=125,
                 n_samples=8, seed=1, tune=["n_long", "n_short"])
    assert 2 <= r["best_params"]["n_long"] <= 4          # sampled within the Int space
    assert r["objective"] == "sharpe"
    assert "sharpe" in r["oos"] and "sharpe" in r["in_sample"]
    assert r["n_samples"] == 8

def test_optimize_is_deterministic():
    v = _view()
    a = optimize("carry", v, train_days=250, test_days=125, n_samples=6, seed=7, tune=["n_long","n_short"])
    b = optimize("carry", v, train_days=250, test_days=125, n_samples=6, seed=7, tune=["n_long","n_short"])
    assert a["best_params"] == b["best_params"] and a["score"] == b["score"]
```

- [ ] **Step 2: Run** → `.venv/bin/python -m pytest tests/test_hyperopt.py -v` → FAIL.

- [ ] **Step 3: Write minimal implementation**

`forex/run/hyperopt.py`:
```python
import random
from forex.strategies.registry import build_strategy
from forex.run.walkforward import walk_forward
from forex.run.backtest import backtest

def optimize(strategy_name, view, *, train_days, test_days, n_samples=200, seed=0,
             cost_bps=1.0, base_params=None, tune=None, objective="sharpe") -> dict:
    base_params = dict(base_params or {})
    space = build_strategy(strategy_name, base_params).search_space()
    if tune is not None:
        space = {k: space[k] for k in tune}
    rng = random.Random(seed)
    best = None
    for _ in range(n_samples):
        cand = dict(base_params)
        for k, sp in space.items():
            cand[k] = sp.sample(rng)
        wf = walk_forward(lambda c=cand: build_strategy(strategy_name, c),
                          view, train_days, test_days, cost_bps)
        score = wf.metrics.get(objective, float("-inf"))
        if best is None or score > best["score"]:
            best = {"score": score, "params": cand, "oos": wf.metrics}
    is_metrics = backtest(build_strategy(strategy_name, best["params"]), view, cost_bps).metrics
    return {"best_params": best["params"], "score": best["score"], "objective": objective,
            "oos": best["oos"], "in_sample": is_metrics, "n_samples": n_samples}
```
Note: for a rule-based strategy (no `fit`), `walk_forward`'s OOS closely tracks a full backtest, so the in-sample-vs-OOS gap is near zero — correct and expected; the gap becomes meaningful once a fitted strategy (the future ML overlay) is tuned. The `lambda c=cand:` default-arg binding avoids the late-binding closure bug.

- [ ] **Step 4: Run** → PASS (both).

- [ ] **Step 5: Commit**
```bash
git add forex/run/hyperopt.py tests/test_hyperopt.py
git commit -m "feat: hyperopt optimizer (random search, walk-forward OOS objective)"
```

---

### Task 5: hyperopt CLI mode

**Files:** Modify `forex/cli.py`. Test: `tests/test_cli_hyperopt.py`

**Interfaces:**
- Adds `"hyperopt"` to the CLI modes, with extra args `--n-samples --seed --objective --tune` (comma list). `resolve` maps them into the `RunConfig` (via `getattr(args, …, None)` so non-hyperopt modes are unaffected). `run(cfg, env, "hyperopt")` calls `optimize(...)` (threading `cfg.n_samples/seed/objective/tune/train_days/test_days/cost_bps` and `base_params=cfg.strategy_params`) and returns `{"hyperopt": {**result, "strategy": cfg.strategy, "cost_bps": cfg.cost_bps}}`. `_format` prints the best OOS score, the OOS-vs-in-sample gap, and the winning `RunConfig` TOML block.

- [ ] **Step 1: Write the failing test**

`tests/test_cli_hyperopt.py`:
```python
import numpy as np, pandas as pd
import forex.cli as cli
from forex.core.dataview import DataView
from forex.core.config import RunConfig
from forex.core.env import EnvConfig

def _view():
    idx = pd.date_range("2016-01-01", periods=900, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.4,900), "EUR": 1.1+np.zeros(900),
                         "SEK": 1.0+np.linspace(0,0.2,900), "NZD": 1.0+np.linspace(0,0.3,900)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.04, index=idx),
             "NZD": pd.Series(0.05, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_resolve_hyperopt_args():
    from forex.cli import build_parser, resolve
    cfg, _, mode = resolve(build_parser().parse_args(
        ["hyperopt", "--strategy", "carry", "--n-samples", "8", "--seed", "3",
         "--tune", "n_long,n_short", "--train-days", "250", "--test-days", "125"]))
    assert mode == "hyperopt" and cfg.n_samples == 8 and cfg.seed == 3
    assert cfg.tune == ["n_long", "n_short"] and cfg.train_days == 250

def test_run_hyperopt(monkeypatch):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    out = cli.run(RunConfig(strategy="carry", n_samples=6, seed=1, tune=["n_long","n_short"],
                            train_days=250, test_days=125), EnvConfig(), "hyperopt")
    r = out["hyperopt"]
    assert "best_params" in r and r["strategy"] == "carry"
    assert "sharpe" in r["oos"]

def test_main_hyperopt_prints_winning_config(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_build_view", lambda cfg, env: _view())
    rc = cli.main(["hyperopt", "--strategy", "carry", "--n-samples", "6", "--seed", "1",
                   "--tune", "n_long,n_short", "--train-days", "250", "--test-days", "125"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "strategy = \"carry\"" in out and "[strategy_params]" in out   # winning RunConfig TOML
```

- [ ] **Step 2: Run** → `.venv/bin/python -m pytest tests/test_cli_hyperopt.py -v` → FAIL.

- [ ] **Step 3: Modify `forex/cli.py`**

Replace `build_parser` with (adds `hyperopt` + its extra args, and `--train-days`/`--test-days` for walkforward+hyperopt):
```python
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="forex")
    sub = p.add_subparsers(dest="mode", required=True)
    for mode in ("backtest", "walkforward", "causal-check", "hyperopt"):
        sp = sub.add_parser(mode)
        sp.add_argument("--config")
        sp.add_argument("--strategy")
        sp.add_argument("--universe")
        sp.add_argument("--timerange")
        sp.add_argument("--cost-bps", type=float, dest="cost_bps")
        sp.add_argument("--param", action="append", default=[], dest="params")
        sp.add_argument("--cache-dir", dest="cache_dir")
        if mode in ("walkforward", "hyperopt"):
            sp.add_argument("--train-days", type=int, dest="train_days")
            sp.add_argument("--test-days", type=int, dest="test_days")
        if mode == "hyperopt":
            sp.add_argument("--n-samples", type=int, dest="n_samples")
            sp.add_argument("--seed", type=int)
            sp.add_argument("--objective")
            sp.add_argument("--tune")
    return p
```

In `resolve`, add these override mappings just before `cfg = cfg.merge(overrides)`:
```python
    for attr in ("train_days", "test_days", "n_samples", "seed", "objective"):
        v = getattr(args, attr, None)
        if v is not None:
            overrides[attr] = v
    tune = getattr(args, "tune", None)
    if tune is not None:
        overrides["tune"] = tune.split(",")
```

Add the `hyperopt` branch to `run` (before the final `raise`):
```python
    if mode == "hyperopt":
        from forex.run.hyperopt import optimize
        res = optimize(cfg.strategy, view, train_days=cfg.train_days, test_days=cfg.test_days,
                       n_samples=cfg.n_samples, seed=cfg.seed, cost_bps=cfg.cost_bps,
                       base_params=cfg.strategy_params, tune=cfg.tune, objective=cfg.objective)
        return {"hyperopt": {**res, "strategy": cfg.strategy, "cost_bps": cfg.cost_bps}}
```

Add the `hyperopt` branch to `_format` (before the `str(out)` fallback):
```python
    if "hyperopt" in out:
        from forex.core.config import RunConfig
        r = out["hyperopt"]
        best = RunConfig(strategy=r["strategy"], cost_bps=r["cost_bps"],
                         strategy_params=r["best_params"])
        gap = r["in_sample"]["sharpe"] - r["oos"]["sharpe"]
        return ("\n".join([
            f"best {r['objective']} (OOS) = {r['score']:.4f}   [n_samples={r['n_samples']}]",
            f"OOS       sharpe={r['oos']['sharpe']:.3f} calmar={r['oos']['calmar']:.3f} "
            f"maxDD={r['oos']['max_drawdown']:.3f}",
            f"in-sample sharpe={r['in_sample']['sharpe']:.3f}  (IS-OOS gap {gap:+.3f})",
            "--- winning config ---",
            best.to_toml_str().rstrip(),
        ]))
```

- [ ] **Step 4: Run** → `.venv/bin/python -m pytest tests/test_cli_hyperopt.py -v` → PASS (all three). Then full suite `.venv/bin/python -m pytest -q` → all green.

- [ ] **Step 5: Commit**
```bash
git add forex/cli.py tests/test_cli_hyperopt.py
git commit -m "feat: hyperopt CLI mode (walk-forward OOS search -> winning RunConfig)"
```

- [ ] **Step 6: Live CLI sanity (manual)**

With the venv active, against the real cache:
`forex hyperopt --strategy carry_voltarget --tune target_vol,cap --n-samples 30 --train-days 1500 --test-days 750`
and confirm it prints a best OOS Sharpe, the IS-OOS gap, and a copy-pasteable winning `[strategy_params]` TOML block. Record it.

---

## Self-Review

**1. Spec coverage.** `Space` types (Float/Int/Categorical) → Task 1 ✓. `search_space()` metadata on strategies → Task 2 ✓. Optimizer samples the space, scores OOS via `walk_forward`, reports IS-OOS gap → Task 4 ✓. Output is a `RunConfig` (TOML block, visible) → Tasks 3 (`to_toml_str`) + 5 (`_format`) ✓. Subset tuning ("one space at a time") via `tune=` → Tasks 4, 5 ✓. `hyperopt` CLI mode → Task 5 ✓. Stdlib random search, seeded/reproducible, no new dep ✓. Values still flow through `RunConfig` (no hidden override) ✓.

**2. Placeholder scan.** No TBD/TODO; complete code in every step; every test asserts real behavior. The one manual step (Task 5 Step 6) is a live-cache CLI run, labeled.

**3. Type consistency.** `Space.sample(rng)` consistent (1,2,4). `search_space() -> {str: Space}` consistent (2,4). `optimize(strategy_name, view, *, train_days, test_days, n_samples, seed, cost_bps, base_params, tune, objective)` consistent (4,5). `RunConfig` new fields (`n_samples/seed/objective/tune`) + `to_toml_str()` consistent (3,5). Reuses `build_strategy`, `walk_forward`, `backtest`, and the existing CLI `build_parser`/`resolve`/`run`/`_format`/`main` with their merged shapes.

---

## What the next plan covers (not this one)
- **Live plan:** the `Execution`/`LiveRunner` seam + ib_async + `dryrun`/`live` CLI modes.

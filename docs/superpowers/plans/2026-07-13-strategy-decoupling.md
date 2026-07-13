# Strategy Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple strategies into a discoverable sibling `strategies/` package with a self-describing `Strategy.NAME`/`build` contract, so `forex/` imports zero concrete strategies. Pure refactor — the full suite stays green at every task.

**Architecture:** Add `NAME`/`build` to the `Strategy` ABC + `compose` helpers + an eager `discovery` loader (forex/core). Convert the registry's builders into `NAME`+`build` subclasses co-located with each factor; delete the registry. Dependency-inject the builder into hyperopt. Then physically move strategies + strategy-features to a sibling `strategies/` package.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest. No new dependencies.

## Global Constraints

- **Pure refactor:** no behaviour change. The full suite (`python -m pytest -q`) must be green at the end of every task. Metrics, weights, and backtest results are byte-identical.
- The 13 strategy names are preserved exactly: `carry`, `carry_voltarget`, `carry_voltarget_ml`, `momentum`, `momentum_voltarget`, `value`, `value_voltarget`, `trend`, `trend_voltarget`, `carry_trend`, `carry_trend_value`, `carry_trend_voltarget`, `carry_trend_value_voltarget`.
- Discovery collects classes where `issubclass(obj, Strategy) and "NAME" in obj.__dict__ and obj.NAME` (NAME defined **directly on the class**), raising on a genuine duplicate (same NAME, different class object).
- `carry_signal` stays in `forex/features/carry.py` (framework: backtest accrual); `ewma_vol` stays in `forex/features/volforecast.py`. `basket_weights`, `momentum_signal`, `value_signal`, `trend_signal`/`directional_weights`, and `HARVolForecaster` move to `strategies/features/`.
- No new dependencies. Match the existing compact style.
- Stage only the files each task touches — never `git add -A`.
- End every commit message with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

### Task 1: `Strategy.NAME`/`build` contract + `compose` helpers

**Files:**
- Modify: `forex/core/strategy.py`
- Create: `forex/core/compose.py`
- Test: `tests/test_compose.py`

**Interfaces:**
- Produces: `Strategy.NAME: str | None = None`; `Strategy.build(cls, params) -> Strategy` (default `cls(**params)`). `split_params(params, base_keys) -> (base, rest)`; `split_prefixed(params, prefixes) -> (inside, outside)`; `build_components(specs, params) -> {prefix: cls(**merged)}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compose.py
from forex.core.compose import split_params, split_prefixed, build_components

def test_split_params():
    base, rest = split_params({"n_long": 3, "n_short": 3, "target_vol": 0.1}, ("n_long", "n_short"))
    assert base == {"n_long": 3, "n_short": 3} and rest == {"target_vol": 0.1}

def test_split_prefixed():
    inside, outside = split_prefixed({"carry_n_long": 3, "trend_lookback": 50, "target_vol": 0.1},
                                     ("carry", "trend"))
    assert inside == {"carry_n_long": 3, "trend_lookback": 50} and outside == {"target_vol": 0.1}

def test_build_components_applies_defaults_then_overrides():
    class Dummy:
        def __init__(self, a=1, b=2): self.a, self.b = a, b
    comps = build_components([("x", Dummy, {"a": 9})], {"x_b": 7, "ignore": 1})
    assert comps["x"].a == 9 and comps["x"].b == 7      # default a=9 kept, b overridden to 7

def test_strategy_defaults():
    from forex.core.strategy import Strategy
    assert Strategy.NAME is None and hasattr(Strategy, "build")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_compose.py -v`
Expected: FAIL (`No module named 'forex.core.compose'`).

- [ ] **Step 3: Write minimal implementation**

Add to `forex/core/strategy.py` (inside `class Strategy`, keep everything else):
```python
    NAME: str | None = None

    @classmethod
    def build(cls, params: dict) -> "Strategy":
        return cls(**params)
```

Create `forex/core/compose.py`:
```python
def split_params(params: dict, base_keys) -> tuple[dict, dict]:
    base = {k: params[k] for k in base_keys if k in params}
    rest = {k: v for k, v in params.items() if k not in base_keys}
    return base, rest

def split_prefixed(params: dict, prefixes) -> tuple[dict, dict]:
    inside = {k: v for k, v in params.items() if any(k.startswith(p + "_") for p in prefixes)}
    outside = {k: v for k, v in params.items() if k not in inside}
    return inside, outside

def build_components(specs, params: dict) -> dict:
    comps = {}
    for prefix, cls, defaults in specs:
        sub_p = dict(defaults)
        for k, v in params.items():
            if k.startswith(prefix + "_"):
                sub_p[k[len(prefix) + 1:]] = v
        comps[prefix] = cls(**sub_p)
    return comps
```

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_compose.py -v && python -m pytest -q`
Expected: PASS (new tests + whole suite still green — additive change).

- [ ] **Step 5: Commit**

```bash
git add forex/core/strategy.py forex/core/compose.py tests/test_compose.py
git commit -m "feat: Strategy.NAME/build contract + compose helpers

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `NAME` + `build` on every strategy (composed subclasses absorb the registry)

**Files:**
- Modify: `forex/strategies/carry.py`, `momentum.py`, `value.py`, `trend.py`, `blend.py`

**Interfaces:**
- Consumes: `split_params`/`split_prefixed`/`build_components` from Task 1.
- Produces: the 4 primitives gain `NAME`; 9 composed `NAME`+`build` subclasses are added (co-located with their factor). The registry still exists and is unchanged (both coexist → suite stays green).

- [ ] **Step 1: Add `NAME` to the four primitives**

In each of `carry.py`/`momentum.py`/`value.py`/`trend.py`, add the class attribute at the top of the class body: `NAME = "carry"` / `"momentum"` / `"value"` / `"trend"` respectively. (Their `__init__` already takes flat params, so the inherited default `build` is correct — no `build` override needed.)

- [ ] **Step 2: Add the composed subclasses**

In `forex/strategies/carry.py` (add imports `from forex.strategies.overlay import VolTargetOverlay`, `from forex.strategies.mloverlay import MLVolTargetOverlay`, `from forex.core.compose import split_params`):
```python
class CarryVolTarget(VolTargetOverlay):
    NAME = "carry_voltarget"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base), **overlay)

class CarryVolTargetML(MLVolTargetOverlay):
    NAME = "carry_voltarget_ml"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base), **overlay)
```

In `forex/strategies/momentum.py` (import `VolTargetOverlay` + `split_params`):
```python
class MomentumVolTarget(VolTargetOverlay):
    NAME = "momentum_voltarget"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("lookback", "n_long", "n_short"))
        return cls(MomentumStrategy(**base), **overlay)
```

In `forex/strategies/value.py`:
```python
class ValueVolTarget(VolTargetOverlay):
    NAME = "value_voltarget"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("window", "n_long", "n_short"))
        return cls(ValueStrategy(**base), **overlay)
```

In `forex/strategies/trend.py`:
```python
class TrendVolTarget(VolTargetOverlay):
    NAME = "trend_voltarget"
    @classmethod
    def build(cls, params):
        base, overlay = split_params(params, ("signal_type", "lookback"))
        return cls(TrendStrategy(**base), **overlay)
```

In `forex/strategies/blend.py` (import the three factor classes + `VolTargetOverlay` + `split_prefixed`/`build_components`):
```python
class CarryTrend(BlendStrategy):
    NAME = "carry_trend"
    SPECS = [("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
             ("trend", TrendStrategy, {"signal_type": "ema", "lookback": 108})]
    @classmethod
    def build(cls, params):
        return cls(build_components(cls.SPECS, params))

class CarryTrendValue(BlendStrategy):
    NAME = "carry_trend_value"
    SPECS = [("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
             ("trend", TrendStrategy, {"signal_type": "ema", "lookback": 108}),
             ("value", ValueStrategy, {"window": 42, "n_long": 4, "n_short": 4})]
    @classmethod
    def build(cls, params):
        return cls(build_components(cls.SPECS, params))

class CarryTrendVolTarget(VolTargetOverlay):
    NAME = "carry_trend_voltarget"
    @classmethod
    def build(cls, params):
        blend_p, overlay = split_prefixed(params, ("carry", "trend"))
        return cls(BlendStrategy(build_components(CarryTrend.SPECS, blend_p)), **overlay)

class CarryTrendValueVolTarget(VolTargetOverlay):
    NAME = "carry_trend_value_voltarget"
    @classmethod
    def build(cls, params):
        blend_p, overlay = split_prefixed(params, ("carry", "trend", "value"))
        return cls(BlendStrategy(build_components(CarryTrendValue.SPECS, blend_p)), **overlay)
```
(`blend.py` already imports `CarryStrategy`/`TrendStrategy`/`ValueStrategy` for its old `registry` usage? No — those were in `registry.py`. Add `from forex.strategies.carry import CarryStrategy`, `from forex.strategies.trend import TrendStrategy`, `from forex.strategies.value import ValueStrategy`, `from forex.strategies.overlay import VolTargetOverlay`, `from forex.core.compose import split_prefixed, build_components`. No import cycle: `carry`→`overlay`/`mloverlay` (neither imports `blend`/`carry`); `blend`→`carry`/`trend`/`value`/`overlay`.)

- [ ] **Step 3: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (additive — registry unchanged, new classes/attrs don't break anything). If an import cycle appears, STOP and report BLOCKED with the traceback.

- [ ] **Step 4: Commit**

```bash
git add forex/strategies/carry.py forex/strategies/momentum.py forex/strategies/value.py forex/strategies/trend.py forex/strategies/blend.py
git commit -m "feat: NAME/build on strategies (composed subclasses absorb registry builders)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Discovery loader; delete the registry

**Files:**
- Create: `forex/core/discovery.py`
- Test: `tests/test_discovery.py`
- Modify: `forex/cli.py`, `forex/run/hyperopt.py`
- Delete: `forex/strategies/registry.py`, `tests/test_registry.py`

**Interfaces:**
- Produces: `build_strategy(name, params=None, package="forex.strategies") -> Strategy`; `available(package="forex.strategies") -> list`; `load_strategies(package) -> dict[str, type]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_discovery.py
import pytest
from forex.core.discovery import build_strategy, available, load_strategies

def test_available_lists_all_13():
    assert set(available("forex.strategies")) == {
        "carry", "carry_voltarget", "carry_voltarget_ml", "momentum", "momentum_voltarget",
        "value", "value_voltarget", "trend", "trend_voltarget",
        "carry_trend", "carry_trend_value", "carry_trend_voltarget", "carry_trend_value_voltarget"}

def test_build_primitive_and_composed():
    from forex.strategies.carry import CarryStrategy
    from forex.strategies.overlay import VolTargetOverlay
    assert isinstance(build_strategy("carry", {"n_long": 2, "n_short": 2}, "forex.strategies"), CarryStrategy)
    s = build_strategy("carry_voltarget", {"n_long": 1, "n_short": 1, "target_vol": 0.1}, "forex.strategies")
    assert isinstance(s, VolTargetOverlay) and s.base.n_long == 1 and s.target_vol == 0.1

def test_composed_default_and_override():
    s = build_strategy("carry_trend", {"trend_lookback": 50}, "forex.strategies")
    assert s.components["trend"].lookback == 50 and s.components["trend"].signal_type == "ema"
    assert s.components["carry"].n_long == 3

def test_unknown_raises():
    with pytest.raises(KeyError):
        build_strategy("nope", package="forex.strategies")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_discovery.py -v`
Expected: FAIL (`No module named 'forex.core.discovery'`).

- [ ] **Step 3: Write the discovery loader**

```python
# forex/core/discovery.py
import importlib
import pkgutil
from forex.core.strategy import Strategy

_CACHE: dict[str, dict] = {}

def load_strategies(package: str = "strategies") -> dict:
    if package in _CACHE:
        return _CACHE[package]
    mod = importlib.import_module(package)
    reg: dict[str, type] = {}
    for info in pkgutil.iter_modules(mod.__path__, mod.__name__ + "."):
        if info.ispkg:
            continue                                    # skip features/ and research/
        m = importlib.import_module(info.name)
        for obj in vars(m).values():
            if (isinstance(obj, type) and issubclass(obj, Strategy)
                    and "NAME" in obj.__dict__ and obj.NAME):
                if obj.NAME in reg and reg[obj.NAME] is not obj:
                    raise ValueError(f"duplicate strategy NAME '{obj.NAME}'")
                reg[obj.NAME] = obj
    _CACHE[package] = reg
    return reg

def build_strategy(name: str, params: dict | None = None, package: str = "strategies") -> Strategy:
    reg = load_strategies(package)
    if name not in reg:
        raise KeyError(f"unknown strategy '{name}'; available: {sorted(reg)}")
    return reg[name].build(params or {})

def available(package: str = "strategies") -> list:
    return sorted(load_strategies(package))
```

- [ ] **Step 4: Repoint the two call sites, delete the registry**

In `forex/cli.py`, change `from forex.strategies.registry import build_strategy` →
`from forex.core.discovery import build_strategy` and (since the default package is `"strategies"` but the code is still physically in `forex.strategies` until Task 5) pass the package explicitly at each call: `build_strategy(cfg.strategy, cfg.strategy_params, "forex.strategies")`. (Task 5 removes the explicit `"forex.strategies"` when the code moves and the default `"strategies"` becomes correct.)

In `forex/run/hyperopt.py`, change `from forex.strategies.registry import build_strategy` →
`from forex.core.discovery import build_strategy`, and its two call sites to pass `"forex.strategies"` as the package argument.

Delete `forex/strategies/registry.py` and `tests/test_registry.py`.

- [ ] **Step 5: Run tests + full suite**

Run: `python -m pytest tests/test_discovery.py -v && python -m pytest -q`
Expected: PASS (discovery replaces the registry; behaviour identical). If a NAME is missing/duplicated, STOP and report BLOCKED.

- [ ] **Step 6: Commit**

```bash
git add forex/core/discovery.py tests/test_discovery.py forex/cli.py forex/run/hyperopt.py
git rm forex/strategies/registry.py tests/test_registry.py
git commit -m "feat: discovery loader replaces the registry

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Dependency-inject the builder into hyperopt

**Files:**
- Modify: `forex/run/hyperopt.py`, `forex/cli.py`
- Test: `tests/test_hyperopt.py`, `tests/test_cli_hyperopt.py`

**Interfaces:**
- Produces: `optimize(build, view, *, train_days, test_days, n_samples=200, seed=0, cost_bps=1.0, base_params=None, tune=None, objective="sharpe", on_step=None)` where `build: Callable[[dict], Strategy]`. `forex/run/hyperopt.py` imports no strategy/discovery symbol.

- [ ] **Step 1: Update the failing tests**

In `tests/test_hyperopt.py`, the existing tests call `optimize("carry", _view(), ...)`. Change them to pass a builder: define `build = lambda p: build_strategy("carry", p, "forex.strategies")` (import `from forex.core.discovery import build_strategy`) and call `optimize(build, _view(), ...)`. Update the `on_step` tests likewise. (The rest of each assertion is unchanged.)

In `tests/test_cli_hyperopt.py`, the CLI tests already go through `cli.run`/`cli.main` — they should still pass unchanged once the CLI injects the builder (Step 3). If any test imports `optimize` directly, update it to the builder signature.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hyperopt.py -v`
Expected: FAIL (`optimize()` first positional is now `build`, old `"carry"` string call errors).

- [ ] **Step 3: Convert `optimize` to take the builder; CLI injects it**

In `forex/run/hyperopt.py`, remove the `from forex.core.discovery import build_strategy` import and change the signature + call sites:
```python
def optimize(build, view, *, train_days, test_days, n_samples=200, seed=0,
             cost_bps=1.0, base_params=None, tune=None, objective="sharpe", on_step=None) -> dict:
    base_params = dict(base_params or {})
    space = build(base_params).search_space()
    if tune is not None:
        space = {k: space[k] for k in tune}
    rng = random.Random(seed)
    best = None
    for i in range(1, n_samples + 1):
        cand = dict(base_params)
        for k, sp in space.items():
            cand[k] = sp.sample(rng)
        wf = walk_forward(lambda c=cand: build(c), view, train_days, test_days, cost_bps)
        score = wf.metrics.get(objective, float("-inf"))
        improved = best is None or score > best["score"]
        if improved:
            best = {"score": score, "params": cand, "oos": wf.metrics}
        if on_step is not None:
            on_step(i, n_samples, score, cand, improved)
    is_metrics = backtest(build(best["params"]), view, cost_bps).metrics
    return {"best_params": best["params"], "score": best["score"], "objective": objective,
            "oos": best["oos"], "in_sample": is_metrics, "n_samples": n_samples}
```
In `forex/cli.py`'s `hyperopt` branch, build the injected callable and pass it:
```python
        build = lambda p: build_strategy(cfg.strategy, p, "forex.strategies")
        res = optimize(build, view, train_days=cfg.train_days, test_days=cfg.test_days,
                       n_samples=cfg.n_samples, seed=cfg.seed, cost_bps=cfg.cost_bps,
                       base_params=cfg.strategy_params, tune=cfg.tune, objective=cfg.objective,
                       on_step=_on_step)
```
(keep the existing `_on_step` stderr closure).

- [ ] **Step 4: Run tests + full suite**

Run: `python -m pytest tests/test_hyperopt.py tests/test_cli_hyperopt.py -v && python -m pytest -q`
Expected: PASS. `forex/run/hyperopt.py` now imports nothing strategy-related.

- [ ] **Step 5: Commit**

```bash
git add forex/run/hyperopt.py forex/cli.py tests/test_hyperopt.py tests/test_cli_hyperopt.py
git commit -m "refactor: dependency-inject the builder into optimize()

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Physical move to the `strategies/` sibling package

**Files:** moves + import rewrites across `forex/strategies/*`, `forex/features/*`, `forex/research/*`, and ~20 test files; `pyproject.toml`.

This task is mechanical: relocate the code, split `features`, rewrite imports, and run the suite until green. Do it as `git mv` + edits.

- [ ] **Step 1: Create the sibling package + move the strategy modules**

```bash
mkdir -p strategies/features strategies/research
: > strategies/__init__.py ; : > strategies/features/__init__.py ; : > strategies/research/__init__.py
git mv forex/strategies/carry.py forex/strategies/momentum.py forex/strategies/value.py \
       forex/strategies/trend.py forex/strategies/overlay.py forex/strategies/mloverlay.py \
       forex/strategies/blend.py strategies/
git mv forex/research/carry_baseline.py forex/research/overlay.py strategies/research/
rmdir forex/strategies forex/research 2>/dev/null || true
```

- [ ] **Step 2: Split `forex/features/` — move the strategy-side features**

- Keep `forex/features/carry.py` but **remove `basket_weights`** from it (leave only `carry_signal`).
- Create `strategies/features/basket.py` containing the `basket_weights` function (moved verbatim from the old `forex/features/carry.py`).
- `git mv forex/features/momentum.py forex/features/value.py forex/features/trend.py forex/features/mlvol.py strategies/features/`.
- `forex/features/volforecast.py` stays.

- [ ] **Step 3: Rewrite imports (the mapping)**

Apply these rules across `strategies/**` and `tests/**` (source in `forex/` other than the moved files needs no change — verify `forex/run/backtest.py` still does `from forex.features.carry import carry_signal`, which is unchanged):

| Old import | New import |
|---|---|
| `from forex.strategies.X import …` | `from strategies.X import …` |
| `from forex.features.carry import basket_weights` | `from strategies.features.basket import basket_weights` |
| `from forex.features.carry import carry_signal` | *(unchanged — stays `forex.features.carry`)* |
| `from forex.features.momentum import …` | `from strategies.features.momentum import …` |
| `from forex.features.value import …` | `from strategies.features.value import …` |
| `from forex.features.trend import …` | `from strategies.features.trend import …` |
| `from forex.features.mlvol import …` | `from strategies.features.mlvol import …` |
| `from forex.features.volforecast import …` | *(unchanged)* |
| `from forex.research.X import …` | `from strategies.research.X import …` |

A file that imports **both** `carry_signal` and `basket_weights` from `forex.features.carry` (e.g. `tests/test_carry.py`) must be split into two imports per the table.

- [ ] **Step 4: Point discovery's default package at `strategies`**

In `forex/core/discovery.py` the default `package="strategies"` is already correct. Update the two call sites that passed `"forex.strategies"` explicitly (added in Tasks 3–4) back to the default: `forex/cli.py` and `forex/run/hyperopt.py`'s `build` closure → `build_strategy(cfg.strategy, cfg.strategy_params)` / `build_strategy(cfg.strategy, p)`. Update `tests/test_discovery.py` and `tests/test_hyperopt.py` to drop the `"forex.strategies"` argument (use the default) OR pass `"strategies"`.

- [ ] **Step 5: Packaging so `strategies` is importable**

In `pyproject.toml`: `[tool.setuptools.packages.find]` → `include = ["forex*", "strategies*"]`. Reinstall editable so both packages resolve:
```bash
pip install -e ".[dev]" >/dev/null
```

- [ ] **Step 6: Run the full suite until green**

Run: `python -m pytest -q`
Expected: PASS (138). If any `ModuleNotFoundError`/`ImportError` remains, fix the offending import per the mapping table and re-run. Do not change any logic — imports only.

- [ ] **Step 7: Verify the framework imports no strategies**

Run: `grep -rn "import" forex/ | grep -E "strateg" ; echo "exit=$?"`
Expected: no matches (the only allowed hit is the dynamic `importlib.import_module(package)` in `discovery.py`, which is a string, not an `import strategies` statement). Confirm `forex/` has zero static strategy imports.

- [ ] **Step 8: Commit**

```bash
git add -A -- forex strategies tests pyproject.toml
git commit -m "refactor: move strategies + strategy-features to sibling strategies/ package

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
(Here `git add -A` is scoped to the refactor paths; there are no concurrent unrelated edits in this task.)

---

### Task 6: Packaging + CLI end-to-end verification

**Files:** none (verification only), unless a packaging fix is needed.

- [ ] **Step 1: Reinstall + import smoke**

Run: `pip install -e ".[dev]" >/dev/null && python -c "import forex, strategies; from forex.core.discovery import available; print(len(available()))"`
Expected: prints `13`.

- [ ] **Step 2: CLI smoke (console script)**

Run: `forex causal-check --strategy carry_trend_voltarget` (uses the cached data if present; a clean "no data" message is acceptable if the cache is absent — the point is the console script resolves the strategy via discovery without error).
Expected: the command runs and resolves `carry_trend_voltarget` (causal PASS, or a clean no-data message — NOT an unknown-strategy or import error).

- [ ] **Step 3: Full suite once more**

Run: `python -m pytest -q`
Expected: PASS (138).

- [ ] **Step 4: Commit (only if a packaging fix was needed)**

If Steps 1–3 required a `pyproject`/`__init__` fix, commit it:
```bash
git add pyproject.toml
git commit -m "chore: packaging fixes for the strategies sibling package

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
Otherwise, no commit — this task is verification.

---

## Notes for the executor
- **Green-at-every-task is the contract.** Tasks 1–2 are additive (registry still present). Task 3 swaps registry→discovery. Task 4 is the DI. Task 5 is the physical move. If any task can't reach green, STOP and report BLOCKED rather than changing logic to force it.
- The behaviour must be byte-identical — this is imports/wiring only. `carry_signal` (framework) and `ewma_vol` (framework) do NOT move; `basket_weights`/signal features/`HARVolForecaster` do.
- After Task 5, `forex/run/backtest.py`'s `from forex.features.carry import carry_signal` is unchanged and correct — do not touch it.
- Watch for import cycles when adding the composed subclasses (Task 2) and after the move (Task 5): `carry`→`overlay`/`mloverlay`; `blend`→`carry`/`trend`/`value`/`overlay`. None of `overlay`/`mloverlay` import a factor, so there is no cycle.

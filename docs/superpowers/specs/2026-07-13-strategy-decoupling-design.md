# Strategy Decoupling — Design Spec

*Design spec. Status: approved 2026-07-13. Architecture restructure (concerns 1+2 from
`docs/architecture-review.md`): pull strategies into a discoverable sibling package and replace the
central registry with a self-describing `Strategy.NAME`/`build` contract + eager discovery, so the
framework imports zero concrete strategies. A **pure refactor** — the 138 tests stay green with only
import-path/wiring changes; no behaviour change.*

## Goal & success criteria
- `forex/` is a strategy-agnostic framework that **statically imports no concrete strategy**.
- Strategies live in a sibling `strategies/` package that imports `forex`.
- A strategy is **self-describing**: a `Strategy` subclass with a class-level `NAME` and a `build`
  classmethod. Adding a strategy = drop a file; no central edit.
- A discovery loader (eager package scan) replaces `registry.py`; `build_strategy(name, params)` and
  `available()` work as before.
- Success: full suite green (138 tests, imports/wiring updated only); `forex backtest/walkforward/
  causal-check/hyperopt --strategy <any of the 13 names>` works unchanged; `registry.py` is deleted;
  `grep -r "import" forex/` shows no `strategies`/`from forex.strategies` static imports.

## The contract (`forex/core/strategy.py`)
```python
class Strategy(ABC):
    NAME: str | None = None                        # set on directly-usable named strategies; None on bases
    @classmethod
    def build(cls, params: dict) -> "Strategy":     # default cls(**params); override for composition/defaults/routing
        return cls(**params)
    @abstractmethod
    def target_weights(self, view): ...
    def fit(self, train): return None
    def params(self) -> dict: return {}
    def search_space(self) -> dict: return {}
```
- Composition bases (`VolTargetOverlay`, `MLVolTargetOverlay`, `BlendStrategy`) keep `NAME = None` and
  are **not** discoverable. Directly-usable strategies set `NAME`.
- `build` defaults to `cls(**params)` (fine for primitives whose `__init__` takes flat params);
  composed/defaulted strategies override it.

## Discovery (`forex/core/discovery.py`)
Eager scan of a package (default `"strategies"`), memoized:
```python
def load_strategies(package="strategies") -> dict[str, type]:
    # importlib.import_module(package); pkgutil.iter_modules(mod.__path__, mod.__name__+".")
    # skip subpackages (info.ispkg) so features/ and research/ are not scanned
    # collect classes where issubclass(obj, Strategy) and "NAME" in obj.__dict__ and obj.NAME
    # raise ValueError on duplicate NAME
def build_strategy(name, params=None, package="strategies"): ...   # reg[name].build(params or {})
def available(package="strategies"): ...                            # sorted(reg)
```
- **`"NAME" in obj.__dict__`** (defined directly on the class) prevents an unnamed subclass from
  inheriting a parent's NAME and causing a phantom duplicate.
- The framework imports the strategies package **by string name at runtime** — no static strategy
  import. `package` is overridable (an escape hatch; default `"strategies"`).

## Composition helpers (`forex/core/compose.py`)
Moved out of `registry.py`, framework-side, importing no strategies (the caller passes classes):
```python
def split_params(params, base_keys):        # -> (base_params, rest)
def split_prefixed(params, prefixes):        # -> (prefixed_params, other) for blend/overlay partition
def build_components(specs, params):         # specs: [(prefix, cls, defaults)] -> {prefix: cls(**merged)}
```

## Composed named strategies become thin subclasses
The ~9 composed names currently built in `registry.py` become `NAME`+`build` subclasses co-located with
their factor, reusing the helpers. Examples:
```python
# strategies/carry.py
class CarryStrategy(Strategy):
    NAME = "carry"
    ...   # __init__ already takes flat params -> inherits default build

class CarryVolTarget(VolTargetOverlay):
    NAME = "carry_voltarget"
    @classmethod
    def build(cls, params):
        base_p, overlay_p = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base_p), **overlay_p)

class CarryVolTargetML(MLVolTargetOverlay):
    NAME = "carry_voltarget_ml"
    @classmethod
    def build(cls, params):
        base_p, overlay_p = split_params(params, ("n_long", "n_short"))
        return cls(CarryStrategy(**base_p), **overlay_p)

# strategies/blend.py
class CarryTrend(BlendStrategy):
    NAME = "carry_trend"
    SPECS = [("carry", CarryStrategy, {"n_long": 3, "n_short": 3}),
             ("trend", TrendStrategy, {"signal_type": "ema", "lookback": 108})]
    @classmethod
    def build(cls, params):
        return cls(build_components(cls.SPECS, params))

class CarryTrendVolTarget(VolTargetOverlay):
    NAME = "carry_trend_voltarget"
    @classmethod
    def build(cls, params):
        blend_p, overlay_p = split_prefixed(params, ("carry", "trend"))
        return cls(BlendStrategy(build_components(CarryTrend.SPECS, blend_p)), **overlay_p)
```
- Composed subclasses inherit `params()`/`search_space()` from their base (which delegate to the
  wrapped/sub strategies), so only `NAME` + `build` are added.
- All 13 names preserved: `carry`, `carry_voltarget`, `carry_voltarget_ml`, `momentum`,
  `momentum_voltarget`, `value`, `value_voltarget`, `trend`, `trend_voltarget`, `carry_trend`,
  `carry_trend_value`, `carry_trend_voltarget`, `carry_trend_value_voltarget`.

## Dependency injection for hyperopt (`forex/run/hyperopt.py`)
`optimize` currently imports `build_strategy` from the registry. Change it to take an injected builder:
```python
def optimize(build, view, *, train_days, test_days, n_samples=200, seed=0, cost_bps=1.0,
             base_params=None, tune=None, objective="sharpe", on_step=None) -> dict:
    # build: Callable[[dict], Strategy]
    space = build(base_params).search_space()   # (was build_strategy(name, base_params))
    ...
    wf = walk_forward(lambda c=cand: build(c), view, train_days, test_days, cost_bps)
    ...
    is_metrics = backtest(build(best["params"]), view, cost_bps).metrics
```
The CLI (composition root) passes `build = lambda p: build_strategy(cfg.strategy, p)`. `forex/run/`
then imports nothing strategy-related. `walk_forward` already takes a factory — only its CLI call
site swaps the import to `forex.core.discovery`.

## Package layout (end state)
```
forex/                       # framework — imports NO concrete strategy
  core/  strategy.py compose.py(NEW) discovery.py(NEW) dataview.py result.py config.py env.py space.py
  backtest/  portfolio.py validation.py voltarget.py
  run/  backtest.py walkforward.py hyperopt.py(DI) live.py execution.py
  data/  fred.py store.py prices.py refresh.py
  diagnostics/ causal.py
  features/  volforecast.py (ewma_vol)   carry.py (carry_signal ONLY)
  config.py (CURRENCIES)   cli.py   __main__.py
strategies/                  # sibling package — imports forex
  __init__.py
  carry.py momentum.py value.py trend.py     # primitives + their composed NAME/build subclasses
  overlay.py mloverlay.py blend.py           # composition bases (NAME=None) + blend's composed names
  features/  __init__.py basket.py momentum.py value.py trend.py mlvol.py
  research/  __init__.py carry_baseline.py overlay.py
```

## Features decomposition (the two flagged calls)
- **`carry_signal` (rate differential) STAYS in `forex/features/carry.py`** — the *backtest* uses it to
  accrue carry P&L on any held position, so it is a framework (accounting) primitive. `forex/run/
  backtest.py`'s import is unchanged. `CarryStrategy` imports it from `forex`.
- **`basket_weights` MOVES to `strategies/features/basket.py`** — only carry/momentum/value strategies
  use it. Carry/momentum/value import it from `strategies.features.basket`.
- **`ewma_vol` STAYS in `forex/features/volforecast.py`** — a generic vol estimator the framework
  provides; strategies (overlay/blend/mloverlay) import it from `forex`.
- **`HARVolForecaster` MOVES to `strategies/features/mlvol.py`** — a fitted model used only by the ML
  overlay.
- `momentum_signal`/`value_signal`/`trend_signal`/`directional_weights` MOVE to `strategies/features/`.
- `CURRENCIES` (`forex/config.py`) and `data/prices.py` STAY — FX *data* config, shared by all.

## Deletions & wiring
- Delete `forex/strategies/registry.py` and its test `tests/test_registry.py`; add
  `tests/test_discovery.py` (build_strategy/available over the strategies package; the NAME/build
  contract; duplicate-NAME raises; a composed name routes params correctly).
- `forex/cli.py`: `from forex.core.discovery import build_strategy`; hyperopt branch injects `build`.
- `pyproject.toml`: `[tool.setuptools.packages.find] include = ["forex*", "strategies*"]`.
- `forex/research/` → `strategies/research/`; update `tests/test_carry_baseline.py` /
  `tests/test_overlay.py` imports.
- Every test importing `forex.strategies.*` / the moved features updates to `strategies.*` /
  `strategies.features.*` (mechanical).

## Implementation approach (phased so the suite is green at every step)
1. **Contract + discovery, in place** — add `NAME`/`build` to `Strategy`; add `compose.py` +
   `discovery.py`; add `NAME`+`build` to the existing `forex/strategies/*` classes (incl. the composed
   subclasses that absorb `registry.py`'s builders); repoint BOTH `cli.py` and `run/hyperopt.py`'s
   `build_strategy` import at discovery over the `"forex.strategies"` package (still name-based);
   delete `registry.py`/`test_registry.py`; add `test_discovery.py`. Suite green — strategies still
   physically in `forex/`, but now discovery-based.
2. **DI for hyperopt** — convert `optimize` to take an injected `build` callable (removing its
   discovery import); the CLI injects it. Suite green.
3. **Physical move** — relocate `forex/strategies/` → `strategies/`, split `forex/features/` per the
   decomposition, change discovery's default package to `"strategies"`, rewrite all imports, move
   `research/`. Suite green.
4. **Packaging** — `pyproject` includes `strategies*`; verify `pip install -e .` exposes both packages
   and the `forex` CLI. Suite green.

## Out of scope (YAGNI / later)
- Pure `--strategy path/to/file.py` path-loading (the `package` override is the escape hatch; full
  path-loading deferred).
- README rewrite (Concern 3 — separate follow-up, done after this lands).
- Any behaviour change to a strategy, the backtest, or the metrics — this is a refactor only.

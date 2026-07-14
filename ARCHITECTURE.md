# Architecture

The living architecture reference for the **framework** (`forex/`). It supersedes the original design
spec (`docs/superpowers/specs/2026-07-11-framework-architecture-design.md`), which is kept as the
historical record.

> **Keep this current.** Update this file whenever the *framework* changes — a new core abstraction, a
> new driver/mode, a change to the `Strategy` contract, the config tiers, the P&L model, or the data
> layer. **Do not** document individual strategies here; strategies live in the sibling `strategies/`
> package and are described by their own specs under `docs/superpowers/specs/`. If a change would make a
> sentence below false, fix the sentence in the same commit.

---

## 1. What this is

A general, **strategy-agnostic** research framework for systematic FX trading. The framework — data,
backtesting, walk-forward evaluation, a lookahead-bias check, hyperopt, config, and a CLI — makes **no
assumption about carry, the G10 universe, or any particular signal**. Its only contract with a strategy
is the atom:

> **point-in-time data → target currency weights.**

The design goal is **one strategy definition, every mode**: the same `Strategy` object is driven by
backtest, walk-forward, the causal check, hyperopt (and paper/live later), so signal logic can never
silently drift between research and execution.

### Framework vs strategies (the load-bearing boundary)

Two packages, one dependency direction — **`strategies → forex`, never the reverse**:

- **`forex/`** — the framework. Imports **zero** concrete strategies. Strategy-specific knowledge (a
  signal, a universe assumption, a factor) must never appear here.
- **`strategies/`** — the strategy library (a sibling package that imports `forex`). All the
  carry/momentum/value/trend/overlay/blend code and its signal maths live here.

The one deliberate exception: **carry accrual** in the backtest. Holding any FX position earns its
interest-rate differential — a market fact, not a strategy property — so it is computed framework-side
from the `DataView` and applied to every strategy uniformly (see §7). A driver or `DataView` that
"knows" about a specific signal is a design smell.

---

## 2. Core concepts (vocabulary)

These are the nouns the whole codebase is built from. Understand these five and the rest follows.

### `DataView` — the "view" (`forex/core/dataview.py`)
The aligned, **point-in-time** data bundle a strategy sees. A frozen-ish dataclass holding:
- `spot: pd.DataFrame` — the spot panel, **dates × currency codes**, quoted so that `pct_change()` is a
  currency's appreciation vs USD. This defines the universe (`.codes = spot.columns`) and the calendar
  (`.calendar = spot.index`).
- `rates: dict[str, pd.Series]` — short rates per currency (decimal), incl. `"USD"`.
- `reer: dict[str, pd.Series]` — BIS real effective exchange rates per currency (default empty; loaded
  when a strategy needs them, e.g. value).

Two things make it the *causal* substrate:
- **`truncate(asof) -> DataView`** clips every series to `≤ asof`. This is how causality is *structural*:
  live feeds `truncate(now)`; the bias check truncates at sampled dates; a strategy literally cannot see
  the future because the data isn't in the view.
- **`from_fred(cache_dir, loader, codes)`** builds it from the cached FRED series for a universe.

`DataView` is extensible: new point-in-time inputs (VIX, credit, positioning) are added as new fields
that `truncate` also clips — never as ad-hoc reads inside a strategy.

### Weights — the atom's output
A strategy returns **target weights**: a `pd.DataFrame` of **dates × currencies**, where each cell is
the target portfolio weight in that currency on that date. Key properties:
- **Causal rows** — row *t* uses only data through *t*. The backtest applies the one-day execution lag
  (`shift(1)`), so a weight decided on *t* acts on *t+1*'s return. Strategies therefore return
  *un-shifted* weights.
- **Sign & neutrality are the strategy's choice** — a dollar-neutral basket has rows summing to ~0
  (`+1/n` longs, `−1/n` shorts); a directional strategy (e.g. trend) can be net long/short. The
  framework imposes neither.
- **NaN/0 = flat** — warm-up or "no position" cells are NaN or 0; the simulator treats both as flat.

### `Strategy` — the atom (`forex/core/strategy.py`, ABC)
```python
class Strategy(ABC):
    NAME: str | None = None                          # set on directly-usable named strategies (discovery)
    def fit(self, train: DataView) -> None: ...       # default no-op; real for fitted models (per WF window)
    @abstractmethod
    def target_weights(self, view: DataView) -> pd.DataFrame: ...   # THE atom (causal, vectorized)
    def params(self) -> dict: ...                     # current param VALUES (reporting/reproducibility)
    def search_space(self) -> dict: ...               # tunable RANGES (Space objects) — decoupled from values
    @classmethod
    def build(cls, params: dict) -> "Strategy":       # default cls(**params); override for composition/routing
        return cls(**params)
```
`NAME` + `build` are the discovery contract (§4); `target_weights` is the only required method.

### `Result` (`forex/core/result.py`)
One dataclass — `returns: pd.Series`, `weights: pd.DataFrame`, `metrics: dict` — the common output of
every driver, consumed by reporting/hyperopt.

### `Space` (`forex/core/space.py`)
Hyperopt range metadata: `Float(low, high)`, `Int(low, high)`, `Categorical([...])`, each with
`.sample(rng)`. Returned (keyed by param name) from `search_space()`, decoupled from the current values.

---

## 3. Framework layout (`forex/`)

```
core/         Strategy (ABC + NAME/build), DataView, Result, compose, discovery, config, env, space
backtest/     portfolio (simulate + metrics + attribution), validation (walk-forward splits), voltarget
run/          drivers: backtest, walkforward, hyperopt, live, execution
data/         FRED loaders (fred), point-in-time as-of join (store), spot panel (prices), refresh
diagnostics/  causal (assert_causal, the truncation-invariance check)
features/     generic estimators: volforecast (ewma_vol); carry (carry_signal — used by P&L accrual)
config.py     the CURRENCIES universe (G10 FRED series IDs)
cli.py        the CLI (the composition root that wires framework + strategy catalog)
```

`core/backtest/run/data/diagnostics` import no strategies. `cli.py` reaches strategies only *by name*
through `discovery` (§4). `features/` holds only framework-side maths (a generic vol estimator, and the
rate-differential used for carry accrual); strategy signal maths live in `strategies/features/`.

---

## 4. Strategy discovery & composition

There is **no central registry**. A strategy is self-describing and discovered by scanning the
`strategies` package.

- **Contract:** a `Strategy` subclass with a class-level `NAME` (and, if composed/defaulted, a `build`
  classmethod). Bases that are not directly usable (`VolTargetOverlay`, `MLVolTargetOverlay`,
  `BlendStrategy`) leave `NAME = None` and are **not** discoverable.
- **Discovery** (`forex/core/discovery.py`): `load_strategies(package="strategies")` eagerly imports the
  package's top-level modules (skipping subpackages), collects every class with `"NAME" in cls.__dict__
  and cls.NAME`, de-dupes by identity, and raises on a genuine duplicate `NAME`. `build_strategy(name,
  params, package)` → `reg[name].build(params)`; `available(package)` lists the names. The framework
  imports the strategies package **by string name at runtime** — hence zero static strategy imports.
- **Composition helpers** (`forex/core/compose.py`): `split_params(params, base_keys)`,
  `split_prefixed(params, prefixes)`, `build_components(specs, params)`. Composed named strategies
  (e.g. `carry_voltarget`, `carry_trend`) are thin subclasses that set `NAME` and override `build` to
  route params (a base's params → the base, the rest → the overlay; or prefixed params → each blend
  component). Their `params()`/`search_space()` are inherited from the base and delegate to the wrapped
  strategies (blends expose sub-params **prefixed**, e.g. `trend_lookback`).

**To add a strategy: drop a file in `strategies/` with a `NAME`d `Strategy` subclass.** It is then
usable from every mode with no other change.

---

## 5. Modes (drivers over the atom)

Every mode reduces to calling `target_weights` differently. Drivers live in `forex/run/`.

- **`backtest(strategy, view, cost_bps) -> Result`** — `target_weights` → `simulate` → `metrics`, over
  all history.
- **`walk_forward(strategy_factory, view, train_days, test_days, cost_bps) -> Result`** — for each
  rolling split: build a fresh strategy, `fit()` on the train window (truncated view), backtest, keep
  only the **test-slice** returns, and stitch the out-of-sample pieces. This is the honest estimate for
  any strategy that fits parameters; rule-based strategies (no-op `fit`) collapse to a normal backtest.
- **`optimize(build, view, *, train_days, test_days, n_samples, seed, cost_bps, base_params, tune,
  objective, on_step) -> dict`** (hyperopt) — random search: sample `search_space()` (a subset via
  `tune` → "one space at a time"), score each candidate on **walk-forward OOS** (in-sample overfits — a
  hard-won crypto lesson), and return the best `params` + the IS-vs-OOS gap. `objective` is any metric
  key (`sharpe` default, `sortino`, `calmar`, …). **The builder is injected** (`build: params →
  Strategy`), so `run/hyperopt.py` imports nothing strategy-related; the CLI passes it. The printed
  winning config *is* a re-runnable `[strategy_params]` TOML block.
- **`assert_causal(strategy, view, sample_dates)`** (`forex/diagnostics/causal.py`) — the truncation-
  invariance check: for each sampled *t*, weights at *t* on the full view must equal weights at *t* on
  `truncate(t)`. Any difference is lookahead.
- **`download`** — force-refresh the FRED cache for the universe (spot, rates, REER) via
  `data/refresh.py` (the only mode needing `FRED_API_KEY`).
- **`dryrun`** — paper reconcile: `rebalance_now(strategy, view, execution)` (`run/live.py`) computes
  today's target weights and reconciles them against a persisted paper book via the `Execution`
  protocol (`run/execution.py`: `SimExecution` implemented; `LiveExecution`/ib_async is the deferred
  seam that guarantees backtest≡live parity).

The CLI (`forex <mode> …`) resolves `RunConfig` (defaults ← file ← env ← flags) + `EnvConfig`, builds
the `DataView` and the strategy (by name, via discovery), calls the driver, and prints/saves the
`Result`. The Python API stays primary for exploration; the CLI is the reproducible shell over it.

---

## 6. The backtest engine (`forex/backtest/portfolio.py`)

**`simulate(weights, spot_rets, carry, cost_bps) -> returns`** is the P&L model, and the single source
of truth for how weights become money:
- `held = weights.shift(1)` — yesterday's weights act on today's return (**the one-day execution lag; no
  lookahead**).
- `gross = Σ_c held[c] · (spot_ret[c] + carry[c]/252)` — each held position earns its spot move **plus
  its daily carry accrual** (the rate differential, framework-side; see §7).
- `cost = cost_bps/1e4 · Σ_c |Δweights[c]|` — turnover cost on rebalancing.
- `return = gross − cost`.

**`metrics(returns) -> dict`** — `total_return`, `ann_return`, `ann_vol`, `sharpe`
(`ann_return/ann_vol`), `sortino` (`ann_return / annualized-downside-deviation`, MAR=0),
`max_drawdown`, `calmar` (`ann_return/|max_drawdown|`). All judged **out-of-sample**, never on
in-sample fit.

`vol_target`/`ewma_vol` provide the framework's leverage mechanism and vol estimator that overlay
strategies build on.

---

## 7. Causality (the non-negotiable discipline)

A signal at date *t* may use **only** data available at *t*. This is the single most important rule (it
caused the prior crypto program's worst bugs). The framework enforces it three ways:
1. **Structural** — a strategy only ever sees a `DataView`; `truncate(asof)` removes future data, and
   macro series are stamped with their *release* date via the as-of join (`data/store.py`), so a value
   dated *T* is visible only at *T + publication_lag*.
2. **Tested** — `assert_causal` proves truncation-invariance on sampled dates; the causal-check CLI mode
   runs it per strategy.
3. **Execution lag** — `simulate` shifts weights by one day, so even a same-day signal trades next day.

**Carry accrual is the one framework-side "signal".** It is not a strategy property — any position in a
currency earns its rate differential — so `backtest` computes it from `view.rates` and feeds it to
`simulate` for every strategy uniformly. It stays in `forex/features/carry.py` (framework), while the
carry *strategy's* ranking (`basket_weights`) lives in `strategies/`.

---

## 8. Configuration (two tiers, deliberately separated)

freqtrade conflated experiment params, infrastructure, and secrets in one file (the timeframe-override
footgun). We split them; **precedence: defaults < `--config` file < env vars < CLI flags**; format is
TOML via stdlib `tomllib`.

- **`RunConfig`** (`forex/core/config.py`) — the *experiment*: `strategy` (name) + `strategy_params`,
  `timerange`, `universe`, `cost_bps`, and mode fields (train/test days, `n_samples`, `seed`,
  `objective`, `tune`). Serializable to a versioned TOML and CLI-overridable — the reproducible,
  git-tracked "what strategy, what period, what params". Hyperopt's output *is* a `RunConfig`.
- **`EnvConfig`** (`forex/core/env.py`) — *infrastructure & secrets*: `FRED_API_KEY`, cache/output dirs,
  IBKR host/port/client-id/account, dry-vs-live. From env vars + an optional gitignored file, never
  version-controlled. Research modes need almost none of it. The same `RunConfig` runs against different
  `EnvConfig`s (laptop paper vs server live) without editing the experiment.

**Values vs search space are separated too:** values flow only through `RunConfig.strategy_params` (no
hidden override file — the crypto footgun); tunable ranges are declared as metadata via
`Strategy.search_space()`. Hyperopt samples the ranges, never mutates a hidden file.

---

## 9. Data layer (`forex/data/`, `forex/config.py`)

- **`config.py`** — `CURRENCIES`: the G10 universe with each currency's FRED series IDs (spot, rate,
  REER) and publication lag. This is FX *data* config (framework-side), shared by all strategies.
- **`fred.py`** — cached FRED series loader (`load_series(..., force=False)`), parquet cache.
- **`store.py`** — `asof_join(calendar, series, pub_lag_days)`: the point-in-time join that stamps each
  observation with its release date (the causality primitive for lagged macro data).
- **`prices.py`** — `build_spot_panel` (USD-per-currency, inverting the FX-per-USD series) and
  `spot_returns`.
- **`refresh.py`** — `refresh_cache` (force-refetch the universe; the `download` mode).

Everything is free (FRED) and cached; once `data_cache/` is populated the whole framework — including the
test suite — runs offline with no key.

---

## 10. Extension points & invariants

**Where to add things:**
- A **new strategy** → a file in `strategies/` (a `NAME`d `Strategy` subclass). Nothing else.
- A **new signal/feature** → `strategies/features/` (strategy-side) unless it's genuinely
  framework-generic (an estimator or a market fact), which goes in `forex/features/`.
- A **new point-in-time input** (VIX/credit/COT) → a new `DataView` field + its loader in `forex/data/`,
  clipped by `truncate`.
- A **new mode** → a driver in `forex/run/` + a CLI branch; keep it a thin call over the atom.
- A **new metric** → `forex/backtest/portfolio.py::metrics` (it becomes a hyperopt objective for free).

**Invariants (a change that breaks one is a design smell):**
1. `forex/` statically imports **no** concrete strategy (dependency direction is `strategies → forex`).
2. Strategies only ever receive a `DataView`; they never read data directly or reach "now".
3. `target_weights` rows are causal; the *only* time-shift is `simulate`'s single `shift(1)`.
4. Carry accrual is the sole framework-side market fact applied to all strategies; no other
   strategy-specific logic lives in the drivers or core.
5. Experiment params live in `RunConfig` (visible, versioned); secrets/infra in `EnvConfig`; ranges in
   `search_space()`. No hidden override files.

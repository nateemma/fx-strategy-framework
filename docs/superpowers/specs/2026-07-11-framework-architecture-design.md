# FX Strategy Framework Architecture — Design Spec

*Design spec. Status: approved 2026-07-11. Refactors the two existing strategies (bare carry,
carry + vol-target overlay) onto a shared framework so one strategy definition runs across all
operational modes. Next step: a behavior-preserving refactor plan (writing-plans).*

## Motivation
The two strategies today are ad-hoc functional pipelines (`run_baseline`, `run_overlay`) that only
do vectorized backtesting. There is no shared `Strategy` abstraction and no execution seam, so the
later live path would be tempted to re-express signal logic — the backtest≠live drift that bit the
prior crypto program (the config-override bug). This spec introduces a framework, derived from the
operations we need, so **one strategy definition drives research, backtest, walk-forward, hyperopt,
lookahead-check, dry-run, and live** — the reuse and consistency goal, without copying freqtrade's
per-pair-per-candle model (a poor fit for portfolio/cross-sectional FX).

## Operations → the atom
Every mode reduces to one atom: *given data available as of time t, what are the target weights?*
Each mode is a **driver** that calls that atom differently — over all history (backtest), over
rolling windows (walk-forward), at "now" (live), or truncated-at-t (bias check).

## Core abstractions
- **`DataView`** (`forex/core/dataview.py`) — the aligned, point-in-time data bundle (spot panel,
  rates; extensible to vol/COT features) plus **`truncate(asof) -> DataView`** clipping every series
  to release-date ≤ asof, and construction that takes a **timerange + universe**. Causality is
  structural: live feeds `truncate(now)`, and the bias check truncates at sampled t.
- **`Strategy`** (`forex/core/strategy.py`, ABC) — the atom:
  - `fit(train: DataView) -> None` — default no-op (rule-based); real for model strategies.
  - `target_weights(view: DataView) -> pd.DataFrame` — causal dates×currency target weights
    (vectorized: each row uses only data through its own date).
  - `params() -> dict` — the current parameter *values* (for reporting/reproducibility; default `{}`).
  - `search_space() -> dict[str, Space]` — the tunable parameters' *ranges* (metadata, decoupled from
    values; default `{}`). See Hyperopt below.
- **`Result`** (`forex/core/result.py`) — one dataclass (`returns`, `weights`, `metrics`, optional
  trades) consumed by reporting / plotting / hyperopt.

## Strategies (thin wrappers over the existing, unchanged functions)
- **`CarryStrategy`** (`forex/strategies/carry.py`) — wraps `carry_signal` + `basket_weights`.
- **`VolTargetOverlay`** (`forex/strategies/overlay.py`) — wraps a **base `Strategy`**. In
  `target_weights` it computes the base weights, derives the base's realized return series (needs the
  view's prices → internally simulates the base — a documented, bounded coupling, because a
  risk-based overlay inherently needs the P&L stream), forecasts vol (`ewma_vol`), and returns
  `L_t · base_weights`. It remains a real weight matrix, so it runs unchanged in live.

## Drivers (the modes)
- **`backtest(strategy, view, cost_bps) -> Result`** (`forex/run/backtest.py`) — `target_weights` →
  `simulate` → `metrics`.
- **`walk_forward(strategy_factory, view, train_days, test_days, cost_bps) -> Result`**
  (`forex/run/walkforward.py`) — fit on each train window, evaluate on test, stitch OOS. First-class
  (freqtrade's weak spot); distant-window and CV are configurations. Rule-based strategies (no fit)
  collapse to a one-shot backtest.
- **`Execution` protocol + `SimExecution`** (`forex/run/execution.py`) —
  `rebalance(current_weights, target_weights, prices) -> fills/cost`. **Backtest backend implemented
  now**; `LiveExecution` (ib_async) is the interface only — the seam that guarantees parity.
- **`LiveRunner`** (`forex/run/live.py`) — **interface sketched, not implemented**: schedule →
  `strategy.target_weights(view.truncate(now))` → last row → `Execution.rebalance`. ib_async plugs in
  here later, driving the same strategy object.
- **`assert_causal(strategy, view, sample_dates)`** (`forex/diagnostics/causal.py`) — the crypto
  truncation-invariance lesson as a first-class op: for sampled t, weights on the full view at t must
  equal weights on `truncate(t)` at t.

## Configuration (two tiers — deliberately separated)
freqtrade conflated experiment params, infrastructure, and secrets in one `config.json` (the source
of the timeframe-override footgun). We split them:

- **Experiment config = `RunConfig`** (`forex/core/config.py`) — one structured object: `strategy`
  (name) + `strategy_params`, `timerange` (start/end), `universe` (codes), `cost_bps`, `cadence`, and
  mode-specific fields (walk-forward train/test sizes, hyperopt space). **Serializable to a versioned
  file** (`--config run.toml`) *and* overridable by CLI flags. This is the reproducible, git-tracked
  "what strategy, what period, what params". `RunConfig` ⇄ plain dict (so a JSON preset also works).
- **Environment config = `EnvConfig`** (`forex/core/env.py`) — infrastructure and **secrets**: IBKR
  host/port/clientId/account, `FRED_API_KEY`, data-cache dir, output dir, dry-vs-live. Loaded from
  **env vars + an optional gitignored TOML file**, never version-controlled. Backtest/research need
  almost none of it (just the data dir); only data-fetch and dry/live modes touch IBKR/keys. The same
  `RunConfig` runs against different `EnvConfig`s (laptop paper vs server live) without editing the
  experiment.
- **Precedence:** defaults < config file < env vars < CLI flags.
- **Format:** TOML, read via stdlib `tomllib` (no new dependency, matches `pyproject.toml`,
  comment-friendly).

## Scripting / argument interface
- **Strategy registry** (`forex/core/registry.py`) — `name → Strategy class`; strategies
  self-register so runs can address them by name (`carry`, `carry_voltarget`).
- **Thin argparse CLI** (`forex/__main__.py`) — `python -m forex <mode> [--config run.toml] --strategy … --timerange … --universe … --param k=v … --cost-bps N`, where `<mode>` ∈ `backtest | walkforward | hyperopt | causal-check | plot` (later `dryrun | live`). It resolves `RunConfig` (defaults ← file ← flags) + `EnvConfig` (env ← file) → builds `DataView` + `Strategy` (from the registry) → calls the driver → prints/saves the `Result`. **The Python API stays primary for exploratory research; the CLI is the reproducible, shell-scriptable shell over it.** One code path: CLI and scripts both go through `RunConfig`/`EnvConfig` → driver → `Result`.

## Hyperopt parameters
Separate the *values* from the *search space* (freqtrade fused them, which caused the
`<Strategy>.json`-silently-overrides footgun):
- **Values** flow only through `RunConfig.strategy_params` — a strategy always runs with whatever's
  in its (visible, versioned) `RunConfig`. No hidden override file.
- **Search space** is declared as metadata via `Strategy.search_space() -> dict[str, Space]`, where
  `Space` (`forex/core/space.py`) is `Float(low, high)` / `Int(low, high)` / `Categorical([...])`.
  Only tunable params appear; it is decoupled from the values.
- **Hyperopt driver** (`forex/run/hyperopt.py`) samples `search_space()` (a subset can be selected →
  "one space at a time"), builds `RunConfig` variants, runs **`walk_forward`** (OOS objective by
  DEFAULT — in-sample hyperopt overfits, a hard-won crypto lesson), scores Sharpe/Calmar, and returns
  the best `strategy_params`. **Its output *is* a `RunConfig` (TOML) — reproducible and diffable, not
  a magic override.** It reports the OOS-vs-in-sample gap (and Sortino) as the overfit indicator.
- **Optimizer engine:** stdlib random/grid search for v1 (spaces are tiny, zero-dependency);
  `search_space()` is engine-agnostic so optuna/skopt can drop in later.

## How each mode maps (the payoff)
`backtest` / `walk_forward` / hyperopt (samples `search_space()`, scores an OOS objective via
`walk_forward`) / `assert_causal` / plot (renders `Result`) / dry-run + live (`LiveRunner` on
`truncate(now)`) — all drive the **same `Strategy.target_weights`**.

## Scope of the first (refactor) plan
- Build: `DataView` (+`truncate`), `Strategy` ABC, `Result`, `CarryStrategy`, `VolTargetOverlay`,
  `backtest`, `walk_forward`, `Execution` protocol + `SimExecution`, `assert_causal`, `RunConfig`
  (+ TOML load), `EnvConfig` (env + TOML load), the registry, and the thin argparse CLI.
- The `Strategy` ABC includes the `search_space()` hook (default `{}`), but the hyperopt driver +
  `Space` classes + optimizer are a LATER increment (they build on `walk_forward`).
- Define but do NOT implement: `LiveExecution` / `LiveRunner` (interfaces only — the parity seam).
  `EnvConfig` carries the IBKR fields, but nothing consumes them yet (no broker backend this plan).
- **Behavior-preserving:** the strategies wrap the existing unchanged functions (`carry_signal`,
  `basket_weights`, `ewma_vol`, `vol_target`, `simulate`, `metrics`). `run_baseline` / `run_overlay`
  are reimplemented to delegate to the new drivers while keeping their signatures and outputs, so
  **all 27 existing tests stay green** as the characterization net; new tests cover the abstractions,
  `assert_causal`, `RunConfig`, and the CLI.

## Acid test (built later, but the design must support it)
The Stage-B ML vol overlay must be expressible as a `Strategy` with a real `fit`, driven by
`walk_forward`, scored by hyperopt over `params()` — the combination freqtrade could not express
cleanly. The interfaces above are shaped so it drops in without change.

## Non-goals (this spec)
- The ib_async live/paper execution backend (interface only here).
- The Stage-B ML overlay implementation.
- A polished CLI framework (typer/click) — stdlib argparse only for now.

## Open items for the implementation plan
- Exact `DataView` construction (what raw panels it holds; how `truncate` treats monthly vs daily
  series) and whether it owns the `asof_join` lags or the strategies do.
- The precise `RunConfig` / `EnvConfig` field sets, the `--param k=v` parsing/typing rules, and the
  exact defaults←file←env←flags merge order implementation.
- Registry mechanism (decorator vs explicit dict) and where strategies register.
- The `Space` type set and the random/grid optimizer + objective wiring (hyperopt increment).
- How `run_baseline`/`run_overlay` are re-expressed on the drivers without changing their outputs.
- The `Execution.rebalance` signature that both `SimExecution` (now) and `LiveExecution` (later)
  must satisfy.

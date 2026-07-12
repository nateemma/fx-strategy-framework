# Live Execution (Paper) — Design Spec

*Design spec. Status: approved 2026-07-12. Sub-project of the FX strategy framework
(`docs/superpowers/specs/2026-07-11-framework-architecture-design.md`). Builds the execution seam,
a fully-testable paper executor, the live runner, and the `dryrun`/`download` CLI modes. The real
ib_async broker adapter is deferred (no TWS/IBKR account available to integration-test against yet).*

## Scope & the no-broker reality
You don't have TWS / IB Gateway / an IBKR account running, so **ib_async broker code cannot be
integration-tested here**. This plan therefore builds the parts that are fully testable offline — the
`Execution` seam, a paper `SimExecution`, the `LiveRunner`, and the `dryrun`/`download` CLI — and
**defers the real ib_async `LiveExecution` adapter** to a focused follow-up once a paper account +
TWS are available. Every unit here is unit-tested with mocks / injected data / temp files, no network.

## Goal & success criteria
Make a strategy *runnable forward* on live-updating data with reconciled orders, on paper, sharing the
same `Strategy` objects and signal path as backtest (the backtest≡live parity goal). Success: a
`forex dryrun` run computes today's target weights, reconciles them against a persisted paper
portfolio, and reports the resulting orders + book — deterministically and offline in tests.

## 1. The Execution seam (`forex/run/execution.py`)
One protocol shared by paper and (later) live:
- **`RebalanceReport`** (dataclass): `orders: dict[str, float]` (per-currency notional delta),
  `positions: dict[str, float]` (resulting target weights), `equity: float`, `turnover: float`,
  `cost: float`, `applied: bool`.
- **`Execution`** (Protocol): `rebalance(target_weights: pd.Series, prices: pd.Series) -> RebalanceReport`.
  The implementation **owns "current state"** — `SimExecution` from a file, `LiveExecution` from the
  broker — so the runner never tracks positions itself.
- **`SimExecution`** (paper, fully testable):
  `SimExecution(portfolio_path, starting_equity=10000.0, cost_bps=1.0, max_position_weight=None, preview=False)`.
  Persists `{equity, weights, last_prices, last_date}` as JSON at `portfolio_path`. On `rebalance`:
  1. Load state (or initialize flat at `starting_equity` on first run).
  2. **Mark-to-market**: spot P&L since last run = `Σ weights[c] · (prices[c]/last_prices[c] − 1)`;
     `equity *= (1 + pnl)`. (Spot-only in v1 — carry accrual is a documented refinement; the *backtest*
     remains the precise P&L model. The paper sim's job is to prove the compute→diff→order→persist loop.)
  3. Optionally clip target weights to `±max_position_weight`.
  4. **Turnover** = `Σ |target − weights|`; `cost = cost_bps/1e4 · turnover · equity`; `equity -= cost`.
  5. `orders[c] = (target[c] − weights[c]) · equity` (notional to trade per currency).
  6. If not `preview`: set `weights = target`, `last_prices = prices`, save. If `preview`: change nothing
     on disk (`applied=False`).
  7. Return the `RebalanceReport`.
- **`LiveExecution`** (ib_async) — **interface-only stub this plan** (raises `NotImplementedError` with
  a docstring of the intended flow: query positions + NAV, compute target units, place IDEALPRO
  orders, reconcile). Slots into the same protocol later.

## 2. The runner (`forex/run/live.py`)
- **`rebalance_now(strategy, view, execution) -> RebalanceReport`** — a *pure function*:
  `target = strategy.target_weights(view.truncate(<latest view date>)).iloc[-1]`;
  `prices = view.spot.iloc[-1]`; `return execution.rebalance(target, prices)`.
  This "compute-target-and-reconcile" core is the reusable seam: a future daemon, a
  higher-frequency strategy, or a manual trigger all call this one function. (`truncate` uses the
  latest available date in the view — "now" in a cache-backed live run.)

## 3. CLI (`forex/cli.py`)
- **`forex dryrun --strategy … [--preview] [--equity N]`** — reads the FRED cache, builds the
  strategy (registry) + a `SimExecution` (portfolio file at `EnvConfig.output_dir/portfolio.json`,
  starting equity from `EnvConfig.starting_equity` or `--equity`), calls `rebalance_now`, prints the
  orders + resulting book. `--preview` runs `SimExecution(preview=True)` (compute and show, write
  nothing).
- **`forex download [--universe …]`** — force-refreshes the FRED series for the universe into the
  cache (needs `FRED_API_KEY`). Decoupled from execution — run manually or via cron. Requires a
  `load_series(..., force=False)` re-fetch path (bypass the cache when `force=True`) and a
  `refresh_cache(cache_dir, codes, loader)` helper.

## 4. Config
- **`EnvConfig`** gains `starting_equity: float = 10000.0` (account-level, like a dry-run wallet).
  `output_dir` already exists (portfolio file lives there); `dry_run` already exists (paper is
  inherently dry). The IB fields (`ib_host`/`ib_port`/`ib_client_id`/`ib_account`) already exist,
  unused until the live adapter.

## 5. Safety (paper now, shaped for live)
`--preview` (no writes), the `max_position_weight` cap, and `EnvConfig.dry_run`. Real-money guards —
a kill-switch, hard notional/position limits, and an explicit live-confirmation prompt — are
documented as requirements for the ib_async `live` plan, not built here.

## 6. Testing (all offline)
- `SimExecution`: against a **temp portfolio file** — first rebalance initializes at `starting_equity`
  and applies target; a second rebalance marks-to-market with new prices, charges turnover, and
  updates the file; `preview=True` writes nothing; `max_position_weight` clips.
- `rebalance_now`: with a **mock `Execution`** + an injected `DataView` — asserts it passes the latest
  target-weights row and latest prices to `execution.rebalance` and returns its report.
- `forex download`: with an **injected loader** (no network) — asserts every universe series is
  (re)written to the cache dir.
- CLI `dryrun`: monkeypatch the view builder — asserts a report is produced and printed.

## Deferred / revisit (recorded so it isn't lost)
- The real **ib_async `LiveExecution`** adapter + a **`live`** (real-money) CLI mode with the safety
  guards above — the next plan, once TWS/paper account exists.
- A **daemon / higher-frequency scheduler** — the run-once/cron model is a choice we may revisit for a
  strategy that trades more often (`rebalance_now` is already the reusable core for it).
- **Carry accrual** in the paper mark-to-market (spot-only in v1).

## Open items for the implementation plan
- The exact `RebalanceReport` field types and the portfolio-JSON schema/versioning.
- The `load_series` `force` parameter and the `refresh_cache` signature.
- How `dryrun`/`download` slot into the existing `build_parser`/`resolve`/`run`/`_format` without
  disturbing backtest/walkforward/causal-check/hyperopt.
- The `max_position_weight` default (likely `None` = off for the dollar-neutral basket) and where it's
  configured (CLI flag vs config).

# forex — A Systematic FX Strategy Framework

A general research framework for systematic **foreign-exchange (FX)** trading strategies. The
framework — data, backtesting, walk-forward evaluation, lookahead-bias checks, hyperopt, config, and
a CLI — is **strategy-agnostic**: any strategy that maps point-in-time data to target currency
weights plugs in and gets every mode for free.

The **first reference implementation** is the G10 **carry trade** with a volatility-targeting
overlay — but that is *one strategy running on the framework*, not the purpose of it. New strategies
(momentum, value, mean-reversion, ML-based; any currency universe) are added by implementing a single
interface and registering a name; everything else — backtest, walk-forward, hyperopt, the CLI —
works unchanged. See *[Adding a strategy](#adding-a-strategy)*.

It is the successor to a prior crypto ML program; the hard-won methodology carries over —
**walk-forward + distant-window validation, point-in-time causality, and judging on realised P&L
rather than model fit**.

The design goal is *one strategy definition, every mode*: the same `Strategy` object is driven by
backtest, walk-forward, a lookahead-bias check, and hyperopt today (and paper/live later), so the
signal logic can never silently drift between research and execution.

All data is free (FRED), the stack is stdlib-heavy (pandas + a little sklearn later), and the whole
test suite runs offline in ~1 second.

> **Status:** research-grade, not deploy-ready. Live/paper execution is designed but not yet built.
> Results are on a short, survivor-biased sample — see *Caveats*.

---

## Forex concepts

If you're new to FX, these are the ideas the code implements. Some are **framework-general** (they
apply to *any* strategy): leverage, volatility targeting, point-in-time causality, walk-forward,
distant-window validation, and the metrics. Others — **carry**, the **basket**, and the **overlay** —
belong to the first reference strategy and are the concepts you'd swap out when writing a different
one.

- **Exchange rate** — the price of one currency in another (e.g. USD per 1 EUR). Going "long AUD"
  means holding Australian dollars and profiting if AUD appreciates vs USD.

- **Carry** — the **interest-rate differential** between two currencies. If Australian short rates
  are 6% and US rates are 1%, holding AUD (funded in USD) earns ~5%/year in *carry* — regardless of
  whether the exchange rate moves. Carry is the core edge this project harvests. Its risk: the
  exchange rate can move against you faster than the carry accrues.

- **Carry trade / basket** — rank the currencies by their carry, go **long the highest-yielders and
  short the lowest-yielders**, sized so the dollar exposure nets to zero (**dollar-neutral**). This
  isolates the rate differential from broad USD moves. Bare carry historically runs a Sharpe around
  0.3–0.5 with deep, sudden drawdowns (the "picking up nickels in front of a steamroller" profile).

- **Leverage** — scaling position size up or down. Here leverage is *not* a fixed multiplier; it is
  set dynamically by the vol-target overlay (below), and capped.

- **Volatility (vol) targeting** — sizing positions so the strategy's *realised* volatility stays
  near a chosen target. When markets are calm (low vol) you size up; when they're turbulent (high
  vol) you size down. Because crashes are high-vol events, vol-targeting **automatically de-risks
  ahead of and during trouble**. Formula used here: `leverage = min(cap, target_vol / forecast_vol)`.

- **Overlay** — a **wrapper strategy that modifies a base strategy's positions**. The vol-target
  overlay takes the carry basket's target weights and multiplies them by the leverage factor above,
  so it *composes*: `VolTargetOverlay(CarryStrategy(...))` is itself a `Strategy`. It emits real
  weights, so the same object works in backtest and (eventually) live.

- **EWMA volatility** — the vol *forecast* the overlay uses: an exponentially-weighted moving average
  of squared returns (RiskMetrics, λ≈0.94), annualised. A cheap, robust vol estimator.

- **Point-in-time / no lookahead** — a signal at date *t* may use **only data available at *t***.
  Macro data is released with a lag (CPI weeks later, positioning weekly), so every series is stamped
  with its *release* date. This is the single most important discipline; the framework enforces it
  structurally (`DataView.truncate`) and tests it (`assert_causal`).

- **Walk-forward** — evaluate a strategy by repeatedly **fitting on a training window and testing on
  the next, unseen window**, then rolling forward and stitching the out-of-sample (OOS) pieces
  together. This is the honest performance estimate for any strategy that *fits* parameters. (For
  purely rule-based strategies it collapses to a normal backtest.)

- **Distant-window validation** — before trusting an edge, confirm it survives on a **temporally
  distant era**, not just the most recent window. Two adjacent windows share a market regime and give
  false confidence.

- **Metrics** — **Sharpe** (return per unit of volatility), **Calmar** (return per unit of max
  drawdown), **max drawdown** (worst peak-to-trough loss). We judge strategies on these OOS, never on
  in-sample fit.

---

## Where the strategy code lives

The **actual strategies** — the thing you'd read or modify to change trading behaviour:

| File | What it is |
|---|---|
| **`forex/strategies/carry.py`** | `CarryStrategy` — the dollar-neutral G10 carry basket. |
| **`forex/strategies/overlay.py`** | `VolTargetOverlay` — the vol-targeting leverage overlay (wraps any base strategy). |
| `forex/strategies/registry.py` | Name → strategy builder (`carry`, `carry_voltarget`); splits params for composed strategies. |

The **signal maths** the strategies call:

| File | What it computes |
|---|---|
| `forex/features/carry.py` | The carry signal (rate differential) and the long/short **basket weights**. |
| `forex/features/volforecast.py` | `ewma_vol` — the annualised EWMA volatility forecast. |
| `forex/backtest/voltarget.py` | The vol-target leverage mechanism (capped, no-lookahead). |

The **framework** the strategies plug into:

- `forex/core/` — `DataView` (point-in-time data bundle + `truncate`), `Strategy` (the ABC:
  `fit`/`target_weights`/`params`/`search_space`), `Result`, `RunConfig`/`EnvConfig` (config),
  `Space` (hyperopt ranges).
- `forex/data/` — FRED loaders (`fred.py`), point-in-time join (`store.py`), the G10 spot panel
  (`prices.py`). The currency universe lives in `forex/config.py` (`CURRENCIES`).
- `forex/backtest/` — the vectorised portfolio simulator + metrics (`portfolio.py`), walk-forward
  split generator (`validation.py`), vol-target mechanism (`voltarget.py`).
- `forex/run/` — the **drivers**: `backtest.py`, `walkforward.py`, `hyperopt.py`.
- `forex/diagnostics/causal.py` — `assert_causal`, the truncation-invariance lookahead check.
- `forex/research/` — end-to-end report scripts: `carry_baseline.py`, `overlay.py`.
- `forex/cli.py` + `forex/__main__.py` — the command-line interface.
- `docs/superpowers/` — the design **specs** and implementation **plans** (the full rationale).

### Adding a strategy

A strategy is any class implementing the `Strategy` interface (`forex/core/strategy.py`):

- **`target_weights(view) -> DataFrame`** (required) — given a point-in-time `DataView`, return the
  target weight per currency for each date. Rows must be **causal** (use only data up to their own
  date); the backtester applies the one-day execution lag and cost model.
- `fit(train)` (optional) — for strategies that estimate parameters or fit a model; a no-op by
  default. The walk-forward driver calls it on each training window.
- `params()` / `search_space()` (optional) — expose current parameter values and the hyperopt-tunable
  ranges (`Float`/`Int`/`Categorical`).

Register a builder name in `forex/strategies/registry.py`, and the strategy is immediately usable from
the CLI (`forex backtest --strategy yourname …`), walk-forward, hyperopt, and the lookahead check —
**no other code changes**. `CarryStrategy` and `VolTargetOverlay` are the worked examples, including
how one strategy (the overlay) *composes* another. The framework never assumes carry, G10, or any
particular universe.

---

## Setup & data

```bash
cd ~/Documents/forex
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # installs the package + the `forex` command + pytest
```

Everything runs inside the activated venv (which puts the `forex` command and all packages on your
path together). Data is fetched from **FRED** (free) — set a key once:

```bash
export FRED_API_KEY="your_key"       # from https://fred.stlouisfed.org/docs/api/api_key.html
```

The first run downloads ~19 series (G10 spot from FRED's H.10, short rates from OECD) into
`data_cache/` and reuses them thereafter. Populate the cache with either research script:

```bash
python -m forex.research.carry_baseline    # bare carry report + per-currency attribution
python -m forex.research.overlay           # bare carry vs the vol-target overlay
```

Run the tests any time:

```bash
pytest -q          # ~65 tests, offline (no network/API key needed)
```

---

## CLI commands

With the venv active, the `forex` command drives the framework. Four modes:

```bash
# 1) Backtest a strategy over history
forex backtest --strategy carry_voltarget --param n_long=3 --param n_short=3

# 2) Walk-forward (out-of-sample) evaluation
forex walkforward --strategy carry --train-days 1000 --test-days 500

# 3) Lookahead-bias check (truncation invariance — proves no future data leaks)
forex causal-check --strategy carry

# 4) Hyperopt — random search, scored on walk-forward OOS, prints a re-runnable winning config
forex hyperopt --strategy carry_voltarget --tune target_vol,cap --n-samples 30 \
      --train-days 2500 --test-days 1500
```

**Common flags** (all modes):

| Flag | Meaning |
|---|---|
| `--strategy NAME` | `carry` or `carry_voltarget`. |
| `--param k=v` | A strategy parameter (repeatable); typed automatically (int/float/bool/str). E.g. `--param target_vol=0.08`. |
| `--universe A,B,C` | Restrict to these currency codes (default: all G10). |
| `--timerange START:END` | ISO dates, either side optional (e.g. `2000-01-01:`). |
| `--cost-bps N` | Transaction cost in basis points per unit turnover (default 1.0). |
| `--config run.toml` | Load a saved `RunConfig` (flags then override it). |
| `--cache-dir DIR` | Where the FRED parquet cache lives (default `data_cache`). |

**Mode-specific:** `--train-days`/`--test-days` (walkforward, hyperopt);
`--n-samples`/`--seed`/`--objective`/`--tune` (hyperopt).

**Config precedence:** defaults < `--config` file < environment variables < CLI flags. Experiment
parameters live in a versioned `RunConfig` (TOML); secrets/infra (FRED key, data dir, and — later —
broker settings) live separately in `EnvConfig` (env vars), never mixed with experiment params.

Hyperopt's output *is* a config: it prints a `[strategy_params]` TOML block you paste into a
`run.toml` and re-run with `--config` — no hidden override files.

> Note: hyperopt on the overlay is compute-heavy (nested walk-forward backtests over decades of daily
> data). Narrow `--timerange`, `--universe`, or `--n-samples` for fast iteration.

---

## First reference strategy — results (research, not advice)

These are results for the *first* strategy on the framework (G10 carry + vol overlay), included to
show the pipeline end-to-end — not a statement about the framework's ceiling.

- **Bare G10 carry** (1982–2026, tradeable window): Sharpe ≈ 0.34, max drawdown ≈ −27%. The edge is
  carry income; the exchange-rate leg is a net drag — textbook.
- **EWMA vol-target overlay** (defaults 10% / cap 1.5×): Sharpe ≈ 0.36, drawdown ≈ −25%.
- **Hyperopt'd overlay** (target ≈ 7%, cap ≈ 1.0): OOS Sharpe ≈ 0.40, drawdown ≈ −17% — targeting the
  basket's natural vol with minimal leverage beats levering up the calm periods.

## Caveats

Short (~40-year, one-cycle) sample on surviving currencies; bare carry has deep, fast drawdowns by
nature; the vol overlay operates on the baseline's already-cost-netted returns. This is a research
sandbox for understanding FX carry structurally — **not** deployable trading advice.

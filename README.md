# forex — A Systematic FX Strategy Framework

A general research framework for systematic **foreign-exchange (FX)** trading strategies. The framework
— data, backtesting, walk-forward evaluation, lookahead-bias checks, hyperopt, config, and a CLI — is
**strategy-agnostic**: any strategy that maps point-in-time data to target currency weights plugs in
and gets every mode for free.

The design goal is **one strategy definition, every mode**: the same `Strategy` object is driven by
backtest, walk-forward, a lookahead-bias check, and hyperopt today (and paper/live later), so the
signal logic can never silently drift between research and execution.

It carries the methodology of a prior crypto ML program — **walk-forward + distant-window validation,
point-in-time causality, and judging on realised P&L rather than model fit**. All data is free (FRED),
the stack is pandas + numpy + stdlib, and the whole test suite runs offline with no API key.

> **Status:** research-grade, not deploy-ready. Live/paper execution is designed but not yet built.
> Results are on a long but survivor-biased G10 sample — see *Caveats*.

---

## Architecture

Two packages, one dependency direction (`strategies → forex`, never the reverse):

```
forex/                # THE FRAMEWORK (imports no concrete strategy)
  core/       Strategy ABC + NAME/build contract, DataView, compose, discovery, config, space
  backtest/   vectorised portfolio simulator + metrics, walk-forward splits
  run/        drivers: backtest, walkforward, hyperopt, live
  data/       FRED loaders, point-in-time join, the G10 universe
  diagnostics/  the lookahead (truncation-invariance) check
  features/   generic estimators (ewma_vol) + carry_signal (used by P&L accrual)
  cli.py      the command-line interface (the composition root)
strategies/           # THE STRATEGY LIBRARY (imports forex)
  carry.py momentum.py value.py trend.py overlay.py mloverlay.py blend.py
  features/   signal maths (basket_weights, momentum/value/trend signals, HAR vol model)
  research/   end-to-end report scripts
```

A strategy is **self-describing**: a `Strategy` subclass with a class-level `NAME` and (for composed
strategies) a `build` classmethod. An eager discovery loader (`forex/core/discovery.py`) scans the
`strategies` package and maps `NAME → class`. **To add a strategy you drop a file in `strategies/`** —
there is no central registry to edit. The framework resolves strategies purely by name at runtime, so
`forex/` imports zero concrete strategies.

---

## Strategy library

Twenty-two strategies ship as reference implementations. Each is usable by name from every mode. (The
carry universe is G10 by default; pass `--universe EUR,JPY,…,MXN,ZAR,PLN,HUF,CZK,ILS` to trade the
deliverable EM-inclusive book.)

| Name | Kind | What it does |
|---|---|---|
| `carry` | factor | Dollar-neutral carry basket: long high-yielders, short low-yielders. |
| `positioning` | factor | Contrarian CFTC COT: fade crowded speculative positioning (net non-commercial). |
| `carry_mom` | factor | Carry-momentum: rank by the 12-month change in the rate differential (widening carry). |
| `momentum` | factor | Cross-sectional momentum: rank by trailing return, long winners / short losers. |
| `value` | factor | REER mean-reversion: long undervalued / short overvalued vs the trailing real-rate mean. |
| `trend` | factor | Per-currency directional time-series trend (tsmom / EMA / Donchian; signal chosen by hyperopt). |
| **`carry_cot`, `carry_cot_mom`** | blend | Risk-parity carry + COT positioning (+ carry-momentum) — **the deployable books**. |
| `carry_voltarget`, `momentum_voltarget`, `value_voltarget`, `trend_voltarget` | overlay | The factor with an EWMA vol-target leverage overlay. |
| `carry_voltarget_ml` | overlay | Carry with a learned (HAR-RV) vol forecaster driving the leverage. |
| `carry_trend`, `carry_trend_value` | blend | Risk-parity (inverse-vol) blend of the named factors. |
| `carry_trend_voltarget`, `carry_trend_value_voltarget` | blend | The blend with the vol-target overlay. |
| `carry_voltarget_xasset`, `carry_voltarget_xasset_anchored`, `carry_voltarget_xasset_gbm` | overlay | Cross-asset / EWMA-anchored / nonlinear-GBM ML vol forecasters — **documented negatives** (all lose to plain EWMA), kept for reproducibility. |
| `carry_trend_crash`, `carry_trend_crash_voltarget` | blend | Carry-drawdown-triggered tilt toward trend — **documented negative** (static blend already captures the hedge). |

`forex causal-check --strategy <name>` proves any of them uses only point-in-time data.

---

## Results (research, not advice)

Walk-forward, out-of-sample, over the full G10 history (FRED). **Read the caveat below the table — the
headline is honest, and it isn't flattering.**

| Strategy | OOS Sharpe (1997+) | Calmar | max DD |
|---|---|---|---|
| `carry` | 0.10 | 0.03 | −27% |
| `carry_trend` | 0.17 | 0.07 | −11% |
| **`carry_trend_voltarget`** (deployable) | **0.15** | 0.06 | −13% |

**The edge is a pre-2010 artifact.** Split by era, `carry_trend_voltarget` runs Sharpe **0.82 (1997–2009)
→ 0.07 (2010–2017) → 0.006 (2018–2026)**: G10 carry worked until the GFC and has been ~dead since, as
zero-rate policy compressed the rate differentials the factor feeds on. The pooled 1997+ Sharpe is
carried entirely by the first era — the book has **no meaningful modern edge**, and live deployment on
G10 spot is not currently justified.

Within the (historical) stack the relative story still holds: time-series trend is a real diversifier
negatively correlated to carry — its correlation *deepens* in carry drawdowns (a convex crash hedge) —
so a risk-parity carry+trend blend beats either leg and roughly halves the drawdown. Honest negatives:
**value does not robustly add Sharpe** (it wins in a pooled window only via the 2008 crisis; an era-split
rejects it — negative since 2018); cross-sectional **momentum is too weak** (~0.03); and a learned vol
forecaster (HAR / cross-asset macro / nonlinear GBM) **loses to a one-parameter EWMA** — always-on beats
timed.

*(An earlier version of this table showed ~0.52 — measured on a stale data cache. The numbers here are
validated against current FRED data, reproducible and matching FRED to the digit.)*

### Emerging-market carry — the tradeable modern edge

The pre-2010 death is a *G10*-differential-compression story, so the question was whether **EM carry** —
where rate differentials survived ZIRP — still pays. It does, and it clears the cost/liquidity wall that
kills most FX edges. Adding the IBKR-tradeable EM (**MXN, ZAR**) to the carry universe lifts the
modern-era Sharpe from **0.27 (G10-only) to 0.68 (G10+MXN+ZAR), 2018–2026** — cost-modeled at 3 bp,
current through 2026, and **positive in each modern sub-era**. It's the first fully-tradeable,
in-regime-positive book in the stack. Caveats kept honest: EM carry is **crash-prone** (fat left tails in
EM-stress years — a broad basket de-concentrates it); a wider 5-EM set (incl. BRL/INR) scores higher but
BRL/INR are **NDF-only, not IBKR-deliverable**; and risk overlays (vol-target, trend) *don't* improve it
in-regime — plain broad carry is the book. Everything here is judged **in the deployment regime**
(post-2010, era-split), not full history.

### The deployable book: carry + positioning + carry-momentum (`carry_cot_mom`)

Two **non-price** signals extend the tradeable EM-carry book into the best construction in the stack — a
risk-parity blend of three sleeves, each orthogonal to the others:

- **CFTC COT positioning** (`positioning`) — fade crowded speculative positioning (net non-commercial,
  free CFTC data). The **first non-price edge in the program**: modern cross-sectional Sharpe ~0.7,
  uncorrelated to carry (0.09).
- **Carry-momentum** (`carry_mom`) — rank by the 12-month *change* in the rate differential (is the carry
  *widening*?). Orthogonal to both carry (0.03) and positioning; robustness-validated across lookbacks.

Blended over the broadened deliverable universe (**G10 + MXN/ZAR/PLN/HUF/CZK/ILS**, IBKR spot + FRED
rates), **`carry_cot_mom`** walk-forwards to **Sharpe 1.15, Calmar 1.03, maxDD −2.9%** — versus
single-factor carry (0.82 / 0.38 / −18%). Run it with `--strategy carry_cot_mom`; `build_carry_view`
auto-loads the COT positioning.

**The factor-search rule this converged on:** carry is the dominant axis, and additional edge comes *only*
from signals **orthogonal** to carry (positioning, rate-differential-change) — never from another
carry-flavored factor. Value, yield-curve slope, and skewness were each tested and **rejected as
carry-redundant** (they dilute the book). Regime conditioning and central-bank NLP were likewise closed
(anticipated policy is priced). See [`docs/strategy-research-backlog.md`](docs/strategy-research-backlog.md).

**Where `carry_cot_mom` lives** — blends are **named classes discovered by their `NAME`, not files**, so
there is no `carry_cot_mom.py`; the blend wires three sleeves defined across the tree:

| Piece | File | Role |
|---|---|---|
| `carry_cot_mom` (blend) | `strategies/blend.py` (`CarryCotMom`) | risk-parity of the three sleeves |
| ├ `carry` | `strategies/carry.py` (`CarryStrategy`) | rate-differential basket |
| ├ `positioning` | `strategies/positioning.py` (`PositioningStrategy`) | COT contrarian |
| └ `carry_mom` | `strategies/carrymom.py` (`CarryMomStrategy`) | 12-month differential change |
| positioning signal | `forex/features/positioning.py` | −z of net-spec, publication-lagged |
| COT data loader | `forex/data/cftc.py` | weekly net non-commercial (CFTC) |
| view builder | `forex/data/ibkr.py` (`build_carry_view`) | IBKR spot + FRED rates, auto-loads COT |

Run it (the universe is the deliverable EM-inclusive book):

```bash
forex backtest --strategy carry_cot_mom \
  --universe EUR,JPY,GBP,CHF,AUD,NZD,CAD,NOK,SEK,MXN,ZAR,PLN,HUF,CZK,ILS
```

### Live execution (IBKR)

`forex dryrun --strategy <name> --universe … --broker ib` connects to IBKR (`ib_async`), reads account
NAV, prices each pair from historical midpoints, and rebalances to the target weights. `--preview` places
nothing; `--confirm` places, behind five guards (paper-account check, per-order and gross caps, min-order
size, explicit TIF) with auto-unwind on partial failure and a pre-trade odd-lot warning below the IdealPro
$25k minimum. The full preview → guarded placement → reconcile → rollback path is **paper-validated** on
IBKR (all deliverable legs qualify, fill, and flatten clean); the **live** gate (`allow_live` + a `U…`
account + live port) is a separate, deliberate decision. Tradeability verified first-hand through the API
(G10 + MXN/ZAR/PLN/HUF/CZK/ILS deliverable; BRL/INR NDF-only, not).

### Intraday — investigated, nothing tradeable

We assessed a broad set of intraday FX ideas (currency-strength ranking, vol-spike mean-reversion,
cointegration/stat-arb, session breakouts) on IBKR 1h data. **None survives cost on liquid majors.**
Currency-strength *momentum* is rejected outright (strength reverts intraday, not persists); the reversion
that exists is real in gross terms (Sharpe ~1.5) but smaller than the round-trip spread — every variant
(always-on cross-sectional, vol-spike-selective, cointegration) is net-negative once cost is charged. A
slow (~10-day) CHF-cross reversion surfaced as a lead but was **refuted** out-of-sample (it was an SNB-peg
statistical artifact, with a Jan-2015 de-peg tail). The consistent conclusion — matching the carry work
and the earlier crypto research — is that **the only edge here is slow and cross-sectional**; intraday
directional and reversion on majors are cost-dominated. Full method and results:
[`docs/intraday-fx-assessment-plan.md`](docs/intraday-fx-assessment-plan.md).

---

## Forex concepts

The ideas the code implements. Some are **framework-general** (apply to *any* strategy): leverage,
volatility targeting, point-in-time causality, walk-forward, distant-window validation, the metrics.
Others — **carry**, the **basket**, the **overlay**, **REER value**, **time-series trend** — belong to
specific strategies and are what you swap when writing a different one.

- **Exchange rate** — the price of one currency in another (USD per 1 EUR). "Long AUD" profits if AUD
  appreciates vs USD.
- **Carry** — the **interest-rate differential** between two currencies. Holding a 6% currency funded
  in a 1% currency earns ~5%/yr regardless of the exchange rate. Its risk: the rate can move against
  you faster than the carry accrues.
- **Basket (cross-sectional, dollar-neutral)** — rank currencies by a signal, go long the top and short
  the bottom, sized so the net dollar exposure is zero. Isolates the factor from broad USD moves.
- **Value / REER** — the *real* effective exchange rate (CPI-deflated, trade-weighted). A currency far
  below its own long-run REER is "cheap" and tends to revert.
- **Time-series trend (directional)** — each currency independently long if it's trending up vs USD,
  short if down. Unlike the baskets this is **not** dollar-neutral, which is what lets it catch big
  dollar trends and provide crisis-alpha.
- **Leverage / volatility targeting** — sizing so the strategy's *realised* vol stays near a target:
  size up when calm, down when turbulent (`leverage = min(cap, target_vol / forecast_vol)`). Because
  crashes are high-vol events, this de-risks ahead of trouble.
- **Overlay** — a wrapper strategy that modifies a base's positions and is itself a `Strategy`
  (`VolTargetOverlay(CarryStrategy(...))`), so it composes and works in every mode.
- **Point-in-time / no lookahead** — a signal at date *t* may use only data available at *t*; macro
  series are stamped with their *release* date. Enforced structurally (`DataView.truncate`) and tested
  (`assert_causal`).
- **Walk-forward** — fit on a training window, test on the next unseen window, roll forward, stitch the
  out-of-sample pieces. The honest estimate for any strategy that fits parameters.
- **Distant-window validation** — confirm an edge survives a *temporally distant* era, not just the
  recent window (adjacent windows share a regime and give false confidence).
- **Metrics** — **Sharpe** (return / vol), **Calmar** (return / max drawdown), **max drawdown**. Judged
  OOS, never on in-sample fit.

---

## CLI

With the venv active, the `forex` command drives the framework. Six modes:

```bash
forex backtest    --strategy carry_trend_voltarget
forex walkforward --strategy carry_trend --train-days 2520 --test-days 504
forex causal-check --strategy trend
forex hyperopt    --strategy trend --tune signal_type,lookback --n-samples 30 \
                  --train-days 2520 --test-days 504
forex download    # force-refresh the FRED cache (needs FRED_API_KEY)
forex dryrun      --strategy carry_trend_voltarget   # paper reconcile (no live broker yet)
```

`--strategy NAME` accepts any of the 13 names above. **Common flags** (all modes): `--param k=v`
(repeatable; typed automatically, e.g. `--param target_vol=0.08` or the prefixed blend params like
`--param trend_lookback=90`), `--universe A,B,C`, `--timerange START:END`, `--cost-bps N`,
`--config run.toml`, `--cache-dir DIR`. **Mode-specific:** `--train-days`/`--test-days` (walkforward,
hyperopt); `--n-samples`/`--seed`/`--objective`/`--tune` (hyperopt); `--preview`/`--equity` (dryrun).

**Config precedence:** defaults < `--config` file < environment variables < CLI flags. Experiment
parameters live in a versioned `RunConfig` (TOML); secrets/infra (FRED key, data dir, broker settings)
live in `EnvConfig` (env vars), never mixed with experiment params. Hyperopt's output *is* a config: it
prints a `[strategy_params]` TOML block you paste into a `run.toml` and re-run with `--config`.

> Hyperopt caveat: the full joint blend space is wide — tune **one sub-space at a time** (e.g.
> `--tune trend_signal_type,trend_lookback`) rather than all params at once, to avoid overfitting.

---

## Adding a strategy

A strategy is a class implementing the `Strategy` interface (`forex/core/strategy.py`):

```python
from forex.core.strategy import Strategy

class MyStrategy(Strategy):
    NAME = "mystrat"                      # discovery uses this; drop the file in strategies/
    def target_weights(self, view):       # required: point-in-time DataView -> target weights per date
        ...                               # rows must be causal (use only data up to their own date)
    # fit(train)          optional: for strategies that fit a model (called per walk-forward window)
    # params()/search_space()  optional: current params + hyperopt-tunable ranges (Float/Int/Categorical)
```

Drop the file in `strategies/`, and `mystrat` is immediately usable from every mode
(`forex backtest --strategy mystrat …`) — **no other code changes, no registry to edit.** Composed
strategies (an overlay wrapping a base, a blend of several) set `NAME` and override the `build`
classmethod, using the helpers in `forex/core/compose.py`; the existing overlay/blend classes are the
worked examples. The framework never assumes carry, G10, or any particular universe.

---

## Accounts & API keys

| Credential | Needed for | Required? | Cost |
|---|---|---|---|
| **FRED API key** | Downloading FX & interest-rate data | **Yes** (to fetch; cached runs & tests need nothing) | Free |
| **Interactive Brokers account** | Paper/live execution | Not yet — arrives with the live plan | Free to open |

**FRED** (Federal Reserve Economic Data) — the free source for spot rates (H.10), short rates (OECD),
and real effective exchange rates (BIS). Request a key at
<https://fred.stlouisfed.org/docs/api/api_key.html> and `export FRED_API_KEY="your_key"`. It's only
needed to *fetch*; once `data_cache/` is populated the whole framework — including the test suite —
runs offline with no key.

**Interactive Brokers** *(planned)* — the broker for execution. No research mode needs it. When the
live plan lands you'll need an IBKR account (paper first) with TWS/IB Gateway; the connection settings
are `EnvConfig` fields supplied via environment variables, never a versioned config file.

---

## Setup

```bash
cd ~/Documents/forex
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # installs both packages + the `forex` command + pytest
export FRED_API_KEY="your_key"    # from https://fred.stlouisfed.org/docs/api/api_key.html
forex download                    # populate data_cache/ (spot H.10, OECD rates, BIS REER)
pytest -q                         # ~148 tests, offline (no network/API key needed)
```

Example end-to-end report scripts live in `strategies/research/`
(`python -m strategies.research.carry_baseline`, `... overlay`).

---

## Caveats

Long but survivor-biased G10 sample; carry-type factors have deep, fast drawdowns by nature; the vol
overlay operates on already-cost-netted returns; the learned vol model was evaluated but does not beat
EWMA on price-only features. This is a research sandbox for understanding systematic FX structurally —
**not** deployable trading advice.

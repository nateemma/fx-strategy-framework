# Implementation Plan: Financing Cost in the Backtest

**Branch**: none — work proceeds on `main`; `specs/003-financing-in-backtest/` is the feature identity
**Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

## Summary

Add an optional per-currency financing charge to the portfolio simulator, encode IBKR's published
credit/debit spreads, and measure what it does to `carry_cot_mom`'s walk-forward Sharpe.

The maths reduces to something small. For a held weight `w` in currency C:

- `w > 0`: realised differential = `(r_C − r_USD) − long_spread_C`
- `w < 0`: realised differential = `(r_C − r_USD) + short_spread_C`

Contribution is `w × differential` in both cases, so the penalty collapses to

```
cost = |w| × spread_side / 252
```

— always a cost, on both sides, proportional to position size. That is one term added to `simulate`.

Where the spreads come from:

```
long_spread_C  = min(r_C, credit_spread_C) + debit_spread_USD
short_spread_C = debit_spread_C + min(r_USD, credit_spread_USD)
```

The `min(rate, spread)` is the broker's zero floor on credit, and it is exact rather than an
approximation: NZD's published 2.5% spread against a 2.098% benchmark floors to earning nothing,
which is precisely what the account measures. ILS, which pays 0% on all balances, falls out of the
same expression with an infinite credit spread.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: pandas, numpy — no new dependency.
**Storage**: none. Rate levels come from the existing `DataView`.
**Testing**: pytest, offline.
**Target Platform**: CLI / library.
**Project Type**: Research framework.
**Performance Goals**: None — one extra elementwise term per simulation.
**Constraints**: Off by default; every prior result must reproduce exactly (FR-006).
**Scale/Scope**: One new framework module, two touched functions, one CLI flag, one findings doc.

## Constitution Check

| Principle | Applies? | How satisfied |
|---|---|---|
| **I. Framework/Strategy Separation** | Yes | Financing is a market/broker fact, not a strategy property — the same category as carry accrual, which the constitution already names as the deliberate framework-side exception. It goes in `forex/backtest/`, knows no strategy, and applies uniformly. **PASS** |
| **II. Point-in-Time Causality** | **Yes — engaged** | The cost uses rate levels and the same `shift(1)` held-weight convention as the existing simulation, so it can see nothing the strategy could not. `forex causal-check` must still pass. **PASS, and must be verified** |
| **III. Tested and Linted** | Yes | Pure functions, offline tests, ruff clean. |
| **IV. Paper-Trading Safety** | Not engaged | Research path only; no execution code touched. **N/A** |
| **V. Planning State in the Repo** | Yes | Spec, plan, tasks, findings all committed. |

**Gate result: PASS.** Principle II is the one to watch: adding a data source to the return
calculation is exactly where lookahead creeps in.

## Project Structure

```text
forex/backtest/
├── financing.py     # NEW — IBKR schedule + spread computation
└── portfolio.py     # MODIFIED — optional financing term in simulate()

forex/run/
└── backtest.py      # MODIFIED — build spreads from the view, pass them through

forex/core/config.py # MODIFIED — `financing` field
forex/cli.py         # MODIFIED — `--financing` flag

tests/test_financing_cost.py   # NEW
docs/financing-spread-findings.md  # MODIFIED — the measured impact
```

**Structure Decision**: The schedule lives in `forex/backtest/financing.py` beside the simulator that
consumes it. `returns_of` is the single choke point through which backtest, walk-forward, and hyperopt
all flow, so one change there reaches every mode.

## Design Decisions

1. **Cost as `|w| × spread`.** Falls out of the algebra above; means the simulator needs no notion of
   sides, only magnitudes, and makes FR-002 (never a credit) structural rather than a check.
2. **Zero floor via `min(rate, spread)`.** Exact, not approximate — validated against NZD and ILS,
   whose published rates are the limiting cases.
3. **Off by default.** FR-006 requires prior results to reproduce. A default-on flag would silently
   invalidate every committed number in the README.
4. **Fail on an unknown currency.** A missing entry silently charging zero would understate cost
   exactly where a new, exotic currency is most likely to be expensive.
5. **The zero-interest tranche is not modelled.** It needs account size, which the framework does not
   have. This makes the result a lower bound, stated in the module and the spec.

## Risks

| Risk | Mitigation |
|---|---|
| Applying today's spreads across decades of history | Stated as the central assumption; the schedule is overridable so sensitivity can be tested. The output is framed as "under today's terms", not a historical reconstruction. |
| Lookahead via rate levels | Rate levels are already point-in-time on the `DataView`; the same `shift(1)` convention applies. Causal-check must pass — a task, not an assumption. |
| The result may invalidate the deployable book | That is the point. FR-010 requires reporting it faithfully either way. |
| Lower-bound cost read as the true cost | Documented in the module, the spec, and the findings doc. |

## Next Command

`/speckit.tasks` — generated below as `tasks.md`.

# Implementation Plan: Financing-Spread Diagnosis

**Branch**: none — work proceeds on `main`; `specs/002-financing-spread/` is the feature identity
**Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

## Summary

Measure what the account actually accrues per currency against the FRED benchmark the backtest
assumes, quantify the gap as an annual drag, repair the carry/spot split so IBKR's monthly interest
posting cannot corrupt it, and write the finding down with its caveats.

The method rests on one observation: `accrued / balance = realised_rate × period`, and **every
currency in a snapshot shares the same period**. So `(accrued/balance) / benchmark_rate` is
period-independent, and a divergence between the long and short medians is a financing asymmetry that
survives not knowing when interest last posted.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: pandas (cached FRED reads), `ib_async` for the live snapshot only. No new dependency.
**Storage**: read-only — `data_cache/*.parquet` for benchmarks, live account values for realised.
**Testing**: pytest, offline. Measurement logic takes plain data structures so it needs no broker.
**Target Platform**: macOS/Linux CLI.
**Project Type**: Research framework + CLI tooling.
**Performance Goals**: None meaningful — 15 currencies.
**Constraints**: Read-only against the broker (Constitution IV). Measurement logic offline-testable (III).
**Scale/Scope**: One new framework module, one new script, one fix to `fxtrack.py`, one findings doc.

## Constitution Check

| Principle | Applies? | How satisfied |
|---|---|---|
| **I. Framework/Strategy Separation** | Yes | `forex/run/financing.py` holds account-level maths, not signal logic. It reads rates and balances; it knows nothing about carry ranking or any strategy. **PASS** |
| **II. Point-in-Time Causality** | Not engaged | Ex-post measurement of realised interest. No signal, no weights, nothing feeding a trade. **N/A** |
| **III. Tested and Linted** | Yes | Pure functions take plain dicts; the broker call lives only in the script. Offline tests; ruff clean. **PASS** |
| **IV. Paper-Trading Safety** | Yes | Read-only. `connect_with_retry(..., readonly=True)`, no order path touched. **PASS** |
| **V. Planning State in the Repo** | Yes | Spec, plan, tasks, and a durable findings doc all committed. **PASS** |

**Execution & Data Safety** also applies: research verdicts must be judged honestly. The dominant risk
here is not a coding error but **over-claiming from a paper account**, which `docs/income-enhancements.md`
records may simulate cash interest. FR-006 and SC-005 exist specifically to constrain that.

**Gate result: PASS.** No violations; Complexity Tracking omitted.

**Post-design re-evaluation: PASS.** One module of pure functions, one thin script, one bug fix. No
new dependency, no configuration surface.

## Project Structure

```text
specs/002-financing-spread/
├── spec.md, plan.md, tasks.md
└── checklists/requirements.md

forex/run/
├── financing.py        # NEW — realised vs benchmark, medians, annualised gap
└── fxtrack.py          # MODIFIED — posting detection + carry estimation

scripts/
└── financing_report.py # NEW — live diagnostic (read-only)

tests/
├── test_financing.py   # NEW — offline
└── test_fxtrack.py     # MODIFIED — posting-reset cases

docs/
└── financing-spread-findings.md   # NEW — the durable record
```

**Structure Decision**: Same split as features 001: pure logic in `forex/run/`, broker access confined
to `scripts/`. That is what keeps the measurement offline-testable.

## Design Decisions

1. **Period-independent ratio as the headline.** The accrual period is not observable from a single
   snapshot, so any absolute annualised rate is assumption-laden. The cross-currency ratio is not.
   Report the ratio as the finding and the annualised drag as a *range* (FR-005).

2. **Exclude near-zero benchmarks from medians.** CHF at −0.045% produces a ratio of −0.88 purely
   from dividing by ~0. A threshold (|rate| < 0.5%) drops such legs from the medians and reports them
   separately — they are still shown, just not allowed to move the summary.

3. **Posting detection by reset-toward-zero.** A posting shows as `|accrued|` collapsing while
   `net_base` stays continuous. Rule: `|accrued_t| < 0.5 × |accrued_{t-1}|` with a magnitude floor to
   avoid firing on noise. On such an observation, carry is *estimated* from the trailing median daily
   accrual and spot takes the residual — so the components still reconcile exactly (FR-008), and the
   estimate is counted and reported (FR-009).

   Rejected: excluding posting observations outright. That would break the carry+spot=total identity
   feature 001 guarantees. Rejected: reconstructing the posted amount from cash, since cash also moves
   with FX revaluation and the two cannot be separated without a marker (Backlog #14).

## Risks

| Risk | Mitigation |
|---|---|
| **Paper-account financing may be simulated** — the whole finding could be an artifact | FR-006/SC-005 force the caveat into every conclusion; the findings doc states what a live check would require. This is the dominant risk and cannot be resolved from this account. |
| Benchmark rates are monthly and some are stale (EUR/GBP at 2026-01) | Every rate is reported with its as-of date (FR-001); staleness shifts a ratio but not the long/short asymmetry, which is the finding. |
| A single snapshot could be unrepresentative | Accrual is now recorded daily by `snapshot_nav.py`; the diagnostic is re-runnable and the finding is checkable over time. |
| Posting estimation introduces a modelled number into a measurement | Counted and reported, never silent; interest accrues smoothly so the estimate is tight. |

## Next Command

`/speckit.tasks` — already generated below as `tasks.md`.

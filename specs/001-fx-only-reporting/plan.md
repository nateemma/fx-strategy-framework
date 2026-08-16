# Implementation Plan: FX-Only Performance Reporting

**Branch**: none — work proceeds on `main`; `specs/001-fx-only-reporting/` is the feature identity
**Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-fx-only-reporting/spec.md`

## Summary

Split the forward-track report into two clearly labelled sections — whole account, and the FX book
alone — so the deployed `carry_cot_mom` strategy can be judged against its walk-forward Sharpe of
~1.15 rather than against ETF sleeve performance that dominates account NAV.

The approach: derive a daily FX P&L series from `fx_net_base` (already recorded), express returns on
gross FX exposure, decompose P&L into carry accrual and spot revaluation, exclude rebalance-flow
observations detected via unsettled-trade counts, and suppress ratio statistics until the sample can
support them. All pure functions over the recorded history; no new data, no broker access.

## Technical Context

**Language/Version**: Python 3.12 (project requires >= 3.11)

**Primary Dependencies**: pandas, numpy — both already core dependencies. No new dependency.

**Storage**: `nav.csv` — read-only. No schema change; the required columns were added 2026-08-16.

**Testing**: pytest. New pure functions live in `forex/run/` so they are unit-testable offline,
following the `basket_track.py` / `fxbook.py` precedent.

**Target Platform**: macOS/Linux CLI, run on demand from the repo root.

**Project Type**: Research framework + CLI tooling. Single project, two packages
(`forex/` framework, `strategies/` library).

**Performance Goals**: None meaningful — the input is a handful of rows per day and will remain under
a few thousand for years. Correctness and legibility dominate.

**Constraints**: MUST run offline with no network, broker, or API key (FR-011). MUST NOT alter the
existing whole-account output for FX-less histories (FR-010).

**Scale/Scope**: ~18 snapshot rows today, growing one per day. One new module, one modified script,
one new test file.

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1 design.*

| Principle | Applies? | How this work satisfies it |
|---|---|---|
| **I. Framework/Strategy Separation** | Yes | New logic goes in `forex/run/` — framework side, strategy-agnostic. It reads account records, not signals; it imports no strategy and encodes no carry-specific knowledge. The `~1.15` expectation is a display string in the script, not framework logic. **PASS** |
| **II. Point-in-Time Causality** | Not engaged | This is ex-post performance reporting over recorded history, not signal generation. No `DataView`, no weights, nothing feeding a trading decision. No causal-check applies. **N/A** |
| **III. Tested and Linted** | Yes | Pure functions extracted into `forex/run/` for offline unit tests; no broker import; `ruff check .` must add no new violations. **PASS** |
| **IV. Paper-Trading Safety** | Yes | The report is strictly read-only over a CSV. It opens no broker connection, places no order, and touches no execution path or guard. **PASS** |
| **V. Planning State in the Repo** | Yes | Spec, research, data model, contract, and quickstart are all committed under `specs/001-fx-only-reporting/`. **PASS** |

**Additional constraints from Execution & Data Safety**: the report reads a git-ignored runtime
artifact (`nav.csv`). It must therefore degrade gracefully when that file is missing or partially
populated rather than assuming a complete record — covered by FR-006, FR-007, FR-010.

**Gate result: PASS.** No violations, so Complexity Tracking is omitted.

**Post-Phase-1 re-evaluation: PASS.** The design adds one framework module of pure functions and one
script edit. It introduces no abstraction beyond the entities the spec already names, no new
dependency, and no configuration surface — the contract explicitly rejects flags and machine-readable
output as speculative.

## Project Structure

### Documentation (this feature)

```text
specs/001-fx-only-reporting/
├── spec.md                    # Feature specification
├── plan.md                    # This file
├── research.md                # Phase 0 — rebalance detection, contamination size, sample gate
├── data-model.md              # Phase 1 — Snapshot -> FxObservation -> FxPerformance
├── contracts/
│   └── cli-output.md          # Phase 1 — invocation + printed-output contract
├── quickstart.md              # Phase 1 — six validation scenarios
├── checklists/
│   └── requirements.md        # Spec quality checklist (16/16)
└── tasks.md                   # Phase 2 — created by /speckit.tasks, NOT by this command
```

### Source Code (repository root)

```text
forex/
└── run/
    ├── fxbook.py              # EXISTING — values the FX book from account values
    └── fxtrack.py             # NEW — pure functions: snapshots -> FxPerformance

scripts/
├── snapshot_nav.py            # UNCHANGED — already records the required columns
└── track_report.py            # MODIFIED — add the FX section, preserve existing output

tests/
└── test_fxtrack.py            # NEW — offline unit tests over constructed histories
```

**Structure Decision**: Pure logic lands in `forex/run/fxtrack.py`, mirroring the established pattern
where `forex/run/basket_track.py` and `forex/run/fxbook.py` hold testable logic while `scripts/`
holds thin drivers. This keeps the new code inside the framework's offline-testable boundary and out
of a script that cannot be unit-tested. `track_report.py` stays a presentation layer: it reads the
CSV, calls `fxtrack`, and formats.

## Design Decisions Carried From Research

Each is recorded with rationale in [research.md](./research.md):

1. **Rebalance detection via unsettled-trade count** (R1) — validated against the real 2026-08-12
   rebalance: 7 orders placed, `stock_positions` 13 → 20 → back to 13 at T+2. Rejected alternatives
   include outlier-dropping, which would have biased Sharpe upward by discarding exactly the fat
   tails this strategy carries.
2. **Flow contamination is second-order** (R2) — the book is dollar-neutral to 0.013% of gross, so
   `fx_net_base` is very nearly pure cumulative P&L. Exclusion is cheap insurance, not a critical
   correction.
3. **20-observation gate for ratios** (R3) — the existing 3-snapshot gate is too permissive for
   Sharpe and volatility.
4. **Returns on prior-period gross exposure** (R4) — matches the basis of the walk-forward
   expectation, and avoids a denominator the period's own P&L has already moved.

## Risks

| Risk | Mitigation |
|---|---|
| ETF baseline for rebalance detection is ambiguous in the earliest rows | Those rows have no FX data and are excluded anyway; a trailing-window baseline handles the live series. Documented as a known limitation in R1. |
| A future sleeve change shifts the ETF baseline and trips false positives | Trailing window adapts. An explicit rebalance marker written at trade time is the robust fix — flagged as a follow-up backlog item, not built here. |
| One live FX observation means end-to-end truth is weeks away | Validation runs against constructed histories; the live smoke test only asserts single-observation mode. |
| The first real reading may look alarming (FX ~flat, carry negative) | The report's job is to show it. Corroborates Backlog #4; the sample-size gate prevents it reading as a verdict. |

## Next Command

`/speckit.tasks` — to generate `tasks.md` from this plan.

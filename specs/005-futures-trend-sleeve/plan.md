# Implementation Plan: Cross-Asset Trend Sleeve (Futures)

**Branch**: none — work proceeds on `main`; `specs/005-futures-trend-sleeve/` is the feature identity
**Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

## Summary

A third executor — futures — following the shape of the two that already work, plus the trend
construction the A2 gate validated, run monthly and watched like every other sleeve.

The engineering is patterned rather than novel. `LiveExecution` (FX `Forex`) and `BasketExecution`
(`Stock`/SMART) already encode the guard set: preview-by-default, explicit confirm, paper-account
check, per-order cap as an atomic pre-pass, reconcile-by-conId, never-raising unwind. `FuturesExecution`
is that same shape over `Future` contracts, with two genuinely new problems: **contract roll** and
**margin**.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: pandas, numpy, `ib_async` — no new dependency.
**Storage**: a positions CSV per run, like the other sleeves. Price history cached under `data_cache/`.
**Testing**: pytest, offline, using the established fake-IB pattern from `tests/test_live_execution.py`.
**Target Platform**: macOS + launchd, IB Gateway on 4002.
**Project Type**: Research framework + execution tooling.
**Performance Goals**: none — 8 markets, monthly.
**Constraints**: paper account only (Constitution IV); all sizing logic offline-testable (III).
**Scale/Scope**: one new executor, one weights module, one runner, installer + healthcheck changes.

## Constitution Check

| Principle | Applies? | How satisfied |
|---|---|---|
| **I. Framework/Strategy Separation** | Yes | `FuturesExecution` goes in `forex/run/` and knows contracts, not signals. The trend weights are strategy logic and belong in `strategies/`, consumed by a thin runner. **PASS** |
| **II. Point-in-Time Causality** | **Yes — engaged** | The signal drives real orders. Weights must be computed from data strictly before the rebalance date, the same `shift`-based discipline the gate used. |
| **III. Tested and Linted** | Yes | Weights and sizing are pure functions; broker access is behind injectable factories so tests never import `ib_async`. |
| **IV. Paper-Trading Safety (NON-NEGOTIABLE)** | **Yes — the centre of this work** | A new asset class is a new way to lose money. The full guard set is FR-001, and it is the highest-priority user story rather than an afterthought. |
| **V. Planning State in the Repo** | Yes | Spec, plan, tasks, and the gate findings all committed. |

**Gate result: PASS.** Principle IV dominates: this feature's risk is concentrated in execution, not
in research, which is the reverse of everything else built recently.

## Project Structure

```text
forex/run/
├── futures.py           # NEW — FuturesExecution: guards, reconcile, roll, margin check
└── futures_roll.py      # NEW — pure: which contract is front, when to roll

strategies/
└── trend_book.py        # NEW — pure: ensemble signal -> inverse-vol weights -> contracts

scripts/
├── trend_sleeve.py      # NEW — runner
└── install_schedules.sh # MODIFIED — a monthly trend agent

forex/run/health.py      # MODIFIED — watch the new sleeve
tests/                   # NEW: test_futures_execution.py, test_trend_book.py, test_futures_roll.py
```

**Structure Decision**: The universe table (symbol, exchange, multiplier, ETF proxy) lives with the
strategy, not the executor — the executor should be able to trade any futures book, not just this one.

## Design Decisions

1. **Reuse the guard shape verbatim.** Every deviation from `BasketExecution`'s structure is a place
   a reviewer has to think again. The per-order cap is an atomic pre-pass, as it was fixed to be in
   `basket.py`; reconciliation is by conId; the unwind never raises.
2. **Roll is a separate pure module.** "Which contract should I hold today" is a calendar question,
   testable without a broker, and getting it wrong silently doubles or zeroes a position. It does not
   belong tangled in placement logic.
3. **A roll is not a signal change.** The reconciler must compare target-vs-held *per market*, not
   per contract, or every roll looks like a full round-trip and pays spread twice.
4. **Report rounding error, always.** At a ~$200k risk base the smallest market is ~1.5 contracts.
   Hiding that would misrepresent how faithfully the tested construction is being run.
5. **Refuse rather than degrade.** No market data ⇒ no signal ⇒ no trade. The A1 gate showed the
   failure mode is 7 bars rather than an error, which would otherwise produce a confident, meaningless
   signal.

## Risks

| Risk | Mitigation |
|---|---|
| **A new asset class is a new way to lose money** | Guards first (US1), fake-broker tests before any live preview, and a live preview before any placement. |
| Roll handled wrongly — double or zero exposure | Roll is its own tested module; reconciliation is per market, not per contract. |
| Margin call from a levered futures book | Explicit available-funds floor checked before placing (FR-008). Excess liquidity is ~$755k today, so headroom is large — but that is a fact to verify, not assume. |
| Signal evidence is ETF-proxy, implementation is futures | Acknowledged in the spec. The first months of realised data are the test; SC-004 makes the comparison explicit. |
| Integer rounding degrades the tested construction | Reported every run; universe was chosen for granularity and re-validated (feasible-8 beat the full 16). |
| Market-data subscription lapses | Manifests as the refuse-to-trade path, and the healthcheck sees the sleeve go stale. |

## Prerequisite (blocking, and not code)

**A CME/CBOT/NYMEX market-data subscription must be active before any of this can be validated.**
Without it there is no price history: the A1 gate measured 7 daily bars on a front-month contract.
Nothing in US2 or US3 can be verified against live data until it is in place.

## Next Command

`/speckit.tasks` — generated below as `tasks.md`.

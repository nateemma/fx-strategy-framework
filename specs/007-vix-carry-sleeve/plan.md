# Implementation Plan: VIX Carry Satellite Sleeve

**Branch**: none — `specs/007-vix-carry-sleeve/` is the feature identity
**Date**: 2026-08-19 | **Spec**: [spec.md](./spec.md)

## Summary

A daily in-or-out sleeve: hold SVXY when the volatility curve is in contango, stand aside otherwise.
Pure signal logic in `strategies/`, placement through the existing `BasketExecution`, scheduled daily
before the open and watched like every other sleeve.

Small feature. The engineering is a thin layer over machinery that already works — the interesting
parts are the execution lag and the tail, both of which are constraints rather than code.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: pandas; the existing FRED loader. No new dependency.
**Storage**: `vix_carry_positions.csv`; term-structure series cached under `data_cache/`.
**Testing**: pytest, offline against fixtures.
**Constraints**: cash-funded only (FR-007); signal offline-testable (FR-010).
**Scale/Scope**: one signal module, one runner, installer and healthcheck entries.

## Constitution Check

| Principle | Applies? | How satisfied |
|---|---|---|
| **I. Framework/Strategy Separation** | Yes | The contango rule is strategy logic and lives in `strategies/`; `BasketExecution` stays generic. **PASS** |
| **II. Point-in-Time Causality** | **Yes — engaged** | The signal drives real orders. It must use only data published before the position is taken, and refuse when that data is stale (FR-002, FR-003). |
| **III. Tested and Linted** | Yes | Signal is a pure function of two series; broker access is behind the existing injectable factories. |
| **IV. Paper-Trading Safety** | **Yes** | Real orders on a new sleeve. Reuses the full guard set, including the single-symbol cap fix that made the cash sleeve placeable. |
| **V. Planning State in the Repo** | Yes | Spec, plan, tasks, and the A1 gate committed. |

**Gate result: PASS.**

## Design Decisions

1. **Reuse `BasketExecution` with `max_order_frac=1.0`.** A single-symbol sleeve is 100% of its
   allocation by definition; the default 0.6 cap made the cash sleeve literally unplaceable until it
   was fixed. Same trap, same fix, applied deliberately rather than rediscovered.
2. **In-or-out, no partial sizing.** That is what the gate tested. A scaled position would be a
   different strategy with no evidence behind it.
3. **Refuse on stale data rather than reuse the last signal.** A stale term structure during a
   volatility event is exactly when a wrong position is most expensive.
4. **Daily evaluation, not daily trading.** Contango holds ~92% of days, so the signal flips roughly
   5–15 times a year. The job runs daily; it trades rarely, and reconciliation makes a no-change day
   free.
5. **Cash-funded, never margin.** The whole reason this sleeve survives retail terms is that it
   borrows nothing.

## Risks

| Risk | Mitigation |
|---|---|
| **The tail the instrument has never seen.** SVXY at −0.5x began the week after the blowup that killed its predecessor, which lost 83% in a day. | Size at the low end of the gate's range. The gate is not a tail guard — it was out for Feb 2018 but fully in for Brexit. This is a sizing constraint, not something code can fix. |
| Execution lag the gate did not model — prior close's signal, next open's fill | Small for a signal flipping ~5–15 times a year, but real. The realised record settles it; SC-005 makes flips countable. |
| Mistaking it for diversification | Stated in the spec's Out of Scope. It is +0.58 to SPY and loses on the book's worst days. |
| Whipsaw in a volatile week driving repeated flips | Turnover is visible in the positions record; the gate charged cost on flips and still passed. |

## Next Command

`/speckit.tasks`

# Implementation Plan: Futures History via LEAN

**Branch**: none — work proceeds on `main`; `specs/006-lean-futures-data/` is the feature identity
**Date**: 2026-08-17 | **Spec**: [spec.md](./spec.md)

## Summary

Obtain daily futures history for the eight trend markets from LEAN, cache it where the framework
already looks, and stop. A gate first, a loader second, nothing else.

## Technical Context

**Language/Version**: Python 3.12 for the loader; LEAN CLI runs in Docker.
**Primary Dependencies**: pandas only. LEAN is invoked as an external tool, not imported.
**Storage**: `data_cache/*.parquet`, matching the FRED loader.
**Testing**: pytest, offline, against fixtures.
**Constraints**: the framework must not gain a LEAN dependency (FR-006).
**Scale/Scope**: one gate document, one loader module, one test file.

## Constitution Check

| Principle | Applies? | How satisfied |
|---|---|---|
| **I. Framework/Strategy Separation** | Yes | A data loader in `forex/data/`, alongside `fred.py` and `ibkr.py`. It knows markets, not strategies. **PASS** |
| **II. Point-in-Time Causality** | Indirectly | The loader supplies price history; the roll convention is *recorded* because an unadjusted series would inject fake returns at every roll — the artifact that made commodity carry untestable. |
| **III. Tested and Linted** | Yes | Offline fixture tests; the suite must stay network-free. |
| **IV. Paper-Trading Safety** | Not engaged | Read-only data acquisition, no broker, no orders. **N/A** |
| **V. Planning State in the Repo** | Yes | Gate findings and this plan are committed, including a negative result. |

**Gate result: PASS.**

## Design Decisions

1. **Gate before build, as always.** Stage 0 is a document, not code. Every idea in this program has
   been gated this way and it has repeatedly saved the build — the CBOE archive stopping in 2018 and
   IBKR's 7-bar response were both found this way.
2. **Translation layer, not dependency inversion.** LEAN writes its own on-disk format; the loader
   reads it and writes parquet. Nothing in `forex/` learns that LEAN exists, so removing it later is
   deleting one file.
3. **Roll convention is data, not a footnote.** It is recorded next to the series, because an
   unadjusted continuous series silently invalidates anything built on it.
4. **Fail loudly on short data.** The exact failure this program keeps meeting: IBKR returned 7 bars
   rather than an error, and the trend runner refuses on that. The loader inherits the same stance.

## Risks

| Risk | Mitigation |
|---|---|
| Data is unadjusted continuous, so unusable | The gate's central question; a negative closes the feature cheaply. |
| Coverage too short for the 2007+ window | Reported per market by the gate; may narrow the usable window rather than kill it. |
| Cost is higher than expected | Costed in the gate before any build. |
| Scope creep into a migration | The spec's Out of Scope section, and the staged plan's explicit stop-decision. |

## Next Command

`/speckit.tasks`

# Implementation Plan: Scheduled-Job Healthcheck

**Branch**: none — work proceeds on `main`; `specs/004-schedule-healthcheck/` is the feature identity
**Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

## Summary

A read-only check that each scheduled job has written its artifact within its cadence plus grace,
reporting every overdue job at once, raising a desktop notification when something is wrong, writing a
durable status file every run, and exiting non-zero on failure. Installed as a fourth launchd agent by
the existing installer.

The detection is deliberately dumb: **artifact modification time versus an expected interval**. It
needs no log parsing, no broker connection, and no cooperation from the jobs themselves — which is
what makes it robust to the failure mode it exists to catch, where the job never ran at all.

## Technical Context

**Language/Version**: Python 3.12 for the check; bash for installer changes.
**Primary Dependencies**: stdlib only. No new dependency.
**Storage**: reads artifact mtimes; writes one status file.
**Testing**: pytest, offline. Staleness logic takes an injected "now" so tests need not wait.
**Target Platform**: macOS (launchd + `osascript` notifications).
**Project Type**: Operational tooling around the research framework.
**Performance Goals**: None — three `stat` calls.
**Constraints**: Read-only (FR-010). Must not require the Gateway. Notification failure must not
suppress the status file or exit code (FR-008).
**Scale/Scope**: One new module, one new script, one installer change, one test file.

## Constitution Check

| Principle | Applies? | How satisfied |
|---|---|---|
| **I. Framework/Strategy Separation** | Yes | Pure logic goes in `forex/run/health.py`; it knows about artifacts and clocks, not strategies. **PASS** |
| **II. Point-in-Time Causality** | Not engaged | No signal, no weights, no returns. **N/A** |
| **III. Tested and Linted** | Yes | Staleness logic is a pure function of (artifact times, now, schedule) — fully offline-testable with an injected clock. |
| **IV. Paper-Trading Safety** | Yes | Strictly read-only: no broker connection at all, so it cannot place an order even in principle. **PASS** |
| **V. Planning State in the Repo** | Yes | Spec, plan, tasks committed. The status file itself is a runtime artifact and git-ignored like its peers. |

**Gate result: PASS.**

## Project Structure

```text
forex/run/health.py            # NEW — WATCHED schedule + pure staleness check
scripts/healthcheck.py         # NEW — driver: run check, notify, write status, exit code
scripts/install_schedules.sh   # MODIFIED — install/remove a fourth agent
tests/test_health.py           # NEW — offline, injected clock
.gitignore                     # MODIFIED — ignore the status file
```

**Structure Decision**: Same split as everywhere else — pure logic in `forex/run/`, side effects
(notification, file write, exit code) in `scripts/`. That is what lets the staleness rules be tested
without a clock, a notifier, or a filesystem full of stale files.

## Design Decisions

1. **Artifact mtime, not log parsing.** The failure being guarded is "the job never ran", which
   produces no log to parse. An absent or stale file is the signal that survives every failure mode,
   including ones not yet seen.
2. **Cadence and grace as data, one table.** `WATCHED` lists each job with its interval and grace, so
   SC-004 is satisfied by construction and tuning never touches detection logic.
3. **Grace sized against real noise, not theory.** Daily 2 days (weekend/asleep), monthly 5 days
   (the check runs after the job, plus holidays), quarterly 10 days. A false alarm is worse than a
   slow one here: it teaches the operator to ignore the channel.
4. **Notification is best-effort, status file is not.** `osascript` may fail in a headless or
   restricted context. Wrapped so the durable outputs always happen (FR-008).
5. **Status file is git-ignored.** It is runtime state like `nav.csv`, and versioning it would produce
   a diff on every run.

## Risks

| Risk | Mitigation |
|---|---|
| False alarms train the operator to ignore alerts | Generous grace, and healthy runs are silent (SC-003) so any notification means something. |
| The healthcheck itself silently stops running | Its own status file goes stale, which is visible at session start via the working agreement. Not fully self-guarding — noted honestly rather than solved by a watcher-watcher. |
| `basket_positions.csv` is git-ignored and only written on placement | It is still the right artifact — its absence is exactly what "the quarterly job did not run" looks like. |
| A quarterly cadence means a broken basket job takes ~3 months to surface | Inherent to the cadence. The daily NAV check is the earlier warning, since both need the Gateway. |

## Next Command

`/speckit.tasks` — generated below as `tasks.md`.

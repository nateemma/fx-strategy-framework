# Implementation Plan: Truthful Outage Detection

**Branch**: `008-outage-detection` | **Date**: 2026-10-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-outage-detection/spec.md`

## Summary

Two small, independent changes, kept deliberately separate because they fix different defects and carry
different risk.

1. **Point the healthcheck at evidence of success.** The FX rebalance runner writes a success-only marker
   after its work completes; the watched job asserts on that marker instead of on the catch-all shell log
   a failure also writes. The existing schedule-relative comparison is untouched — it was never the bug.
2. **Add a probe-only watchdog that cannot be starved.** A short-lived job runs every 5 minutes, checks
   whether the API port is serving, and alerts the operator after the outage outlasts the nightly restart
   window. It never starts, kills, or logs into anything.

The existing `local.ibc-gateway` agent is **kept exactly as it is**. Its timer starvation only occurs while
IBC is alive — when IBC dies the exec'd process exits, the job completes, and the timer fires again — so it
already handles the cold-start case correctly, and that is the only case the operator has approved
automating. Leaving it alone means nothing in this feature can start a second Gateway.

## Technical Context

**Language/Version**: Python 3.12 (`.venv/bin/python`), plus two Bash runners and one launchd plist.

**Primary Dependencies**: **None new.** Standard library only — `socket` for the port probe, `json` for
watchdog state, `pathlib`/`datetime` as already used. Deliberately *not* `ib_async`: a raw TCP connect
answers "is the API serving" without opening a broker session, so the probe cannot contribute to the
duplicate-login state that silently kills market data.

**Storage**: Local files, git-ignored like the other forward-record artifacts — a new success marker
(`fx_rebalance_status.csv`) and watchdog state/status files.

**Testing**: pytest, offline. The port probe and the process check are injected, so no test opens a socket.

**Target Platform**: macOS (launchd), single operator machine.

**Project Type**: Library (`forex/`) plus scripts; no service, no UI.

**Performance Goals**: Not a factor. The probe is one TCP connect with a 2-second timeout, every 5 minutes.

**Constraints**: Detection within 1 hour (SC-002) while raising zero false alarms across ~30 nightly
restarts a month (SC-004). Those two pull against each other and the debounce is where they are balanced.

**Scale/Scope**: 7 watched jobs, 1 port, 1 machine. Roughly 150 lines of new Python and ~3 lines of Bash.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Engaged? | How this feature satisfies it |
|---|---|---|
| **I. Framework/Strategy separation** | Yes | New code lives in `forex/run/`, imports zero strategies, and knows nothing about any signal. The dependency direction is unchanged. |
| **II. Point-in-time causality** | No | This feature computes no signal and touches no `DataView`. |
| **III. Tested and linted** | Yes | Every new behaviour gets a test. The probe and process check are injectable callables, so the suite stays offline with no network, no key, no broker — and no `ib_async` import, since a `socket` connect suffices. `ruff` run before commit. |
| **IV. Paper-trading safety** | Yes — and this is the one to watch | Nothing here places an order, and no new path can reach a real-money account. The probe is a read-only TCP connect to the paper port only. **Per operator decision (2026-10-09) the watchdog never kills a process, never restarts a live instance, and never attempts a login**, so it cannot induce the duplicate-login state. The existing cold-start agent is left untouched rather than reimplemented, so the single-instance guarantee is not re-derived. |
| **V. Planning state in the repo** | Yes | Spec, plan, research, and tasks are committed. The launchd plist and watchdog wrapper live outside the repo by necessity (`~/Library/LaunchAgents`, `~/ibc`), so **copies are vendored under `scripts/` and installed from there**, which is how the existing schedules already work. |

**Gate result: PASS.** No violations, so Complexity Tracking is omitted.

One pre-existing deviation noted but not fixed here: `CLAUDE.md` cites the constitution as v1.0.0 while
`.specify/memory/constitution.md` is v1.1.0.

## Project Structure

### Documentation (this feature)

```text
specs/008-outage-detection/
├── plan.md              # This file
├── spec.md
├── research.md          # Phase 0 — the three decisions that needed evidence
├── data-model.md        # Phase 1 — records and state transitions
├── quickstart.md        # Phase 1 — how to prove it works without waiting for an outage
├── contracts/
│   └── interfaces.md    # Phase 1 — function, file, and exit-code contracts
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
forex/run/
├── health.py                  # MODIFIED: Job gains a success-evidence rule; check_health gains an
│                              #   injectable reachability probe with a distinct "unknown" outcome
└── gateway_watchdog.py        # NEW: pure decision logic — given port state, process state, prior
                               #   state and now, decide {quiet, alert, start} and the next state

scripts/
├── healthcheck.py             # MODIFIED: passes a real probe; renders reachability in the status file
├── monthly_paper_rebalance.sh # MODIFIED: writes the success marker after the work completes
├── gateway_watchdog.py        # NEW: thin runner — probes, calls the decision function, alerts, persists
├── launchagents/
│   └── local.fx-gateway-watchdog.plist   # NEW: vendored plist, StartInterval 300
└── install_schedules.sh       # MODIFIED: installs the new agent alongside the existing six

tests/
├── test_health.py             # MODIFIED: existing 26 keep passing; new cases for success-evidence
│                              #   and for the three-state reachability rendering
└── test_gateway_watchdog.py   # NEW: the decision table, debounce, rate limit, and the never-kill rule
```

**Structure Decision**: The repo's established split is followed exactly — **pure, testable logic in
`forex/run/`, I/O and side effects in `scripts/`**. This is the same shape as `health.py` versus
`healthcheck.py` and is what lets the suite stay offline. `forex/run/gateway_watchdog.py` is a pure
function of (port state, process state, prior state, now); the runner does the socket call, the
`osascript` alert, and the state write. Splitting it this way is what makes the debounce and rate-limit
rules — the parts most likely to be wrong — testable without waiting 5 minutes or faking a clock.

The launchd plist is **vendored into `scripts/launchagents/`** rather than only existing in
`~/Library/LaunchAgents`. The 2026-08-01 missed rebalance was caused by schedule state that lived only
outside the repo, and the existing supervisor script still does — so vendoring the new one is a
deliberate narrowing of that class of failure, not gold-plating.

## Phase 0 — Research

See [research.md](./research.md). Three questions needed evidence rather than judgement: what success
signal the FX runner can emit for free, how long the nightly restart window actually is (which sets the
debounce floor), and whether a TCP probe can be mistaken for a competing login. All three resolved; no
`NEEDS CLARIFICATION` remains.

## Phase 1 — Design

See [data-model.md](./data-model.md) for the records and the watchdog state machine,
[contracts/interfaces.md](./contracts/interfaces.md) for the function signatures, file formats and exit
codes, and [quickstart.md](./quickstart.md) for how to verify the whole thing without waiting for a real
outage.

**Post-design Constitution re-check: PASS.** The design added no dependency, no network call in tests, and
no execution path. The only new side effects are a file write and an `osascript` alert, both already used
by `scripts/healthcheck.py`.

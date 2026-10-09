# Tasks: Truthful Outage Detection

**Input**: Design documents from `/specs/008-outage-detection/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/interfaces.md](./contracts/interfaces.md)

**Tests**: **REQUIRED** (Constitution III). Here they are the deliverable, not a formality — the thing
being fixed is monitoring that reported success through a total outage, so a test that fails before the
fix and passes after *is* the evidence the fix works. Test tasks precede their implementations.

**⚠️ OUT OF SCOPE — MUST NOT BE TOUCHED**: `~/ibc/gateway_supervisor.sh` and
`~/Library/LaunchAgents/local.ibc-gateway.plist`. They keep sole responsibility for cold-starting IBC.
Leaving them alone is what guarantees nothing here can start a second Gateway, whose duplicate login
silently cuts market data to the API for every symbol.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Add the new runtime forward-record artifacts to `.gitignore`: `fx_rebalance_status.csv`, `gateway_status.txt`, `gateway_watchdog_state.json`, `gateway_watchdog.log` (Constitution: Execution & Data Safety classes these as local records, not versioned)

---

## Phase 2: Foundational (Blocking Prerequisites)

**None required.** Recorded deliberately rather than left blank: the two work streams touch different
functions in `forex/run/health.py` (US1 changes the `Job` record and `WATCHED`; US3 changes
`check_health`'s signature and `format_report`'s output) and US2 is an entirely new module. There is no
shared prerequisite to build first, so inventing a foundational phase would only add a false dependency.

The one ordering constraint that does exist is recorded in Dependencies below: US1 and US3 both edit
`health.py`, so they should not be done concurrently by two people.

---

## Phase 3: User Story 1 — A failed run is reported as failed (Priority: P1) 🎯 MVP

**Goal**: `health_status.txt` stops reporting `ok` for a job that fired, failed, and placed nothing.

**Independent Test**: `pytest tests/test_health.py` — simulate a job whose log was written by a failure
and assert the report marks it failed. Offline, no broker, `now` injected as the existing tests already do.

> **This phase alone closes the silent failure.** US2 and US3 shorten and explain an outage; this one is
> the only part that makes an invisible failure visible, which is why it is the MVP and why it ships first.

### Tests for User Story 1 ⚠️ write first, confirm they FAIL

- [X] T002 [P] [US1] Write a failing test that a job whose watched artifact was touched **after** the last due time by a *failure* is reported failed — the exact 2026-10-01 case — in `tests/test_health.py`
- [X] T003 [P] [US1] Write a failing test that a run which succeeded while correctly placing **zero** orders is reported `ok`, so the fix cannot introduce a false alarm on a legitimate no-op reconcile (SC-004) — in `tests/test_health.py`
- [X] T004 [P] [US1] Write a failing test that every **enabled** job in `WATCHED` has a non-empty `success_evidence`, so a new watched job cannot be added without stating why a failing run cannot write its artifact (FR-002) — in `tests/test_health.py`

### Implementation for User Story 1

- [X] T005 [US1] Add `success_evidence: str` to `Job`, inserted **before** the defaulted `enabled`, and fill it for all seven `WATCHED` entries — in `forex/run/health.py` (see [contracts/interfaces.md](./contracts/interfaces.md) §A.1; every entry is constructed positionally, so all seven must change in this task or the module will not import)
- [X] T006 [US1] Repoint `paper-rebalance` from `track.log` to `fx_rebalance_status.csv` in `WATCHED` — in `forex/run/health.py`
- [X] T007 [US1] Extend the `forex/run/health.py` module docstring with the rule that a watched artifact MUST be one only a successful run writes, naming `track.log` as the counter-example that caused this (the docstring is where this module already explains its own design decisions)
- [X] T008 [US1] Append the success marker after the `{ … } >> track.log 2>&1` block closes in `scripts/monthly_paper_rebalance.sh`, with a comment stating that `set -euo pipefail` is what makes it success-only
- [X] T009 [US1] Update any positional `Job(...)` constructions in `tests/test_health.py` for the new field, and confirm all 26 pre-existing tests still pass unchanged in intent (FR-015)

**Checkpoint**: a failed rebalance is now reported as failed. Verified by `pytest tests/test_health.py`.

---

## Phase 4: User Story 2 — A dead Gateway is noticed within the hour (Priority: P2)

**Goal**: a watchdog whose timer cannot be starved detects "process alive, port not serving" and alerts
the operator, having stayed silent through the nightly restart.

**Independent Test**: `pytest tests/test_gateway_watchdog.py` — drive `decide()` through the decision
table with the probe and process check injected. No sockets.

> **The debounce is the part most likely to be wrong**, and it is wrong in both directions: too eager
> alarms on every restart (~30 false alarms a month, which trains the operator to ignore the channel —
> the exact failure this feature exists to prevent), too lax misses the outage. The two measured
> durations it must clear are a **45-second** automatic re-login (observed 2026-10-08 21:52→21:53) and a
> **2m06s** cold start (measured in commit `bb6a431`). See [research.md](./research.md) R2.

### Tests for User Story 2 ⚠️ write first, confirm they FAIL

- [X] T010 [P] [US2] Write failing tests for each row of the `decide()` decision table in [contracts/interfaces.md](./contracts/interfaces.md) §B — serving, not-serving-with-process, not-serving-without-process — in `tests/test_gateway_watchdog.py`
- [X] T011 [P] [US2] Write a failing test that **one** failed probe stays quiet and **two consecutive** failures alert, so a 45s re-login cannot alarm (FR-008) — in `tests/test_gateway_watchdog.py`
- [X] T012 [P] [US2] Write a failing test that a continuing outage alerts at most once per `RATE_LIMIT`, so a 25-day outage cannot produce thousands of alerts (FR-009, SC-005) — in `tests/test_gateway_watchdog.py`
- [X] T013 [P] [US2] Write a failing test that `serving=False, process_alive=False` yields `start` and never `alert`, proving the watchdog distinguishes "nothing running" from "running but wedged" — in `tests/test_gateway_watchdog.py`
- [X] T014 [P] [US2] Write failing tests for the two safety invariants: **no input produces an action that kills or restarts anything** (FR-011, the operator-confirmed alert-only constraint), and `decide()` is pure — in `tests/test_gateway_watchdog.py`
- [X] T015 [P] [US2] Write a failing test that a missing or unparseable state file is treated as a fresh start rather than crashing or suppressing alerts — in `tests/test_gateway_watchdog.py`

### Implementation for User Story 2

- [X] T016 [US2] Implement `WatchdogState`, `WatchdogDecision`, `decide()` and the four constants (`ALERT_AFTER=2`, `RATE_LIMIT=3600`, `PROBE_TIMEOUT=2`, documented `PROBE_INTERVAL=300`) — in `forex/run/gateway_watchdog.py`, pure: no sockets, no subprocess, no file I/O
- [X] T017 [US2] Implement the runner — `socket.create_connection(("127.0.0.1", port), timeout=2)` probe closed immediately with **no API handshake**, injectable process check, state load/save, `gateway_status.txt` written on **every** run so its own mtime proves the watchdog is alive, and the exit-code contract (0 quiet, 1 alerted) — in `scripts/gateway_watchdog.py`
- [X] T018 [US2] Reuse `alert_command` from `forex/run/health.py` for the modal alert, treating the banner as best-effort — in `scripts/gateway_watchdog.py` (the banner channel is already known to be silently dropped on this machine while `osascript` exits 0)
- [X] T019 [US2] Add the `--self-test` flag mirroring `scripts/healthcheck.py --self-test`, so the alert path can be proven without waiting for an outage — in `scripts/gateway_watchdog.py`
- [X] T020 [US2] Catch unhandled exceptions, write them to the durable record, and exit non-zero, so a crashing watchdog cannot fail silently — in `scripts/gateway_watchdog.py`
- [X] T021 [P] [US2] ~~Vendored plist in `scripts/launchagents/`~~ **Changed during implementation**: `install_schedules.sh` *generates* all plists inline with heredocs, so it is already the in-repo source of truth and a vendored file would have created a second one that can drift. The plist is generated there instead (`com.fx.gateway-watchdog`), with the `StartInterval`-not-`KeepAlive` comment as planned. `scripts/launchagents/` was never created.
- [X] T022 [US2] Install the new agent alongside the existing six in `scripts/install_schedules.sh`, without touching the `local.ibc-gateway` agent

**Checkpoint**: a wedged Gateway alerts within ~10 minutes, and the nightly restart does not.

---

## Phase 5: User Story 3 — The status page names the cause (Priority: P3)

**Goal**: the daily status says the broker is unreachable instead of leaving the operator to infer it from
several stale files.

**Independent Test**: render the report with the probe stubbed three ways and compare output.

### Tests for User Story 3 ⚠️ write first, confirm they FAIL

- [X] T023 [P] [US3] Write failing tests for the three reachability outcomes — `available`, `unavailable`, `unknown` — in `tests/test_health.py`
- [X] T024 [P] [US3] Write a failing test that `unknown` does **not** make the report unhealthy and that no probe supplied yields `unknown` rather than a failure (FR-013) — in `tests/test_health.py`
- [X] T025 [P] [US3] Write a failing test that a probe which **raises** degrades to `unknown`, so a probe bug cannot manufacture an outage — in `tests/test_health.py`
- [X] T026 [P] [US3] Write a failing test that per-job verdicts are byte-identical regardless of the probe's result — reachability explains, it never decides (FR-013) — in `tests/test_health.py`

### Implementation for User Story 3

- [X] T027 [US3] Add the optional `probe=None` parameter to `check_health` and a `reachability` field to `HealthReport`, keeping the function read-only and the per-job logic untouched — in `forex/run/health.py`
- [X] T028 [US3] Render one broker line above the existing per-job block in `format_report`, leaving the per-job line format unchanged — in `forex/run/health.py`
- [X] T029 [US3] Pass a real socket probe from `scripts/healthcheck.py`, reusing the same probe helper as the watchdog rather than writing a second one

**Checkpoint**: all three stories independently functional.

---

## Phase 6: Polish & Validation

- [X] T030 Run `.venv/bin/python -m pytest -q` and `python -m ruff check .`; confirm green and no new violations
- [X] T031 Run [quickstart.md](./quickstart.md) steps 1–5 and confirm each expectation
- [X] T032 Run `scripts/gateway_watchdog.py --self-test` and confirm a modal alert actually appears (quickstart step 6) — a silent pass here is a known-possible state and means the channel is broken
- [X] T033 Install the agent and **verify the timer re-fires** by confirming `gateway_status.txt`'s mtime advances across a >5-minute gap — this is the precise defect being fixed, so confirm it rather than assuming it
- [X] T034 Update `specs/000-baseline/baseline.md`: close Backlog #19 and #20, and record the feature under Completed with what remains unverified
- [X] T035 Commit and push spec, plan, tasks and implementation (Constitution V — planning state that exists on one machine does not exist)

---

> **T033 measured 2026-10-09**: `gateway_status.txt` mtime advanced from 11:00:22 to 11:05:22 — exactly
> 300s — so the agent is genuinely being re-scheduled rather than having run once at load. This is the
> precise property the old supervisor lost (its port check had not run in 40 days), so it is recorded as a
> measurement rather than an assumption. `gateway_watchdog.log` shows the repeated runs.
>
> **T032 verified by the operator 2026-10-09**: `--self-test` returned `alert delivered` and the modal
> appeared. This step cannot be self-verified — it needs someone present to see and dismiss the dialog —
> and it matters, because a dropped alert is a known-possible state here: Notification Centre banners were
> silently discarded on this machine while `osascript` still exited 0. The modal path is confirmed to get
> through, so an alert raised by the watchdog will actually reach someone.

## Dependencies & Execution Order

```text
Phase 1 (setup)
   └─> US1 (P1) ── MVP, closes the silent failure
   └─> US2 (P2) ── independent: new module + new agent, touches no existing logic
   └─> US3 (P3) ── shares health.py with US1, so sequence after it
        └─> Phase 6 (validation)
```

- **US1 and US2 are genuinely independent** — different files, no shared state — and could be done in
  either order or concurrently.
- **US3 must follow US1**, not for logical reasons but because both edit `forex/run/health.py` and
  `tests/test_health.py`; doing them concurrently just creates conflicts.
- Phase 6 depends on whichever stories were taken.

### Parallel Opportunities

- T002–T004 (US1 tests) are all in `tests/test_health.py` but independent in content.
- T010–T015 (US2 tests) are all in a new file and fully parallel.
- T021 (plist) is parallel with all US2 Python work.
- US1 and US2 in parallel if two people.

---

## Implementation Strategy

**MVP = Phase 1 + US1.** That is six tasks and it closes the defect that actually cost something: a job
that fails and reports success. Stop there and validate if time is short — the remaining two stories
reduce an outage from "found within a day" to "found within ten minutes", which is valuable but strictly
less so than going from "never found" to "found".

**Then US2**, because the five weeks of lost data came from the detection delay, not from the silent
report alone.

**US3 last.** It is diagnostic polish: by then the operator already knows something is wrong and has an
alert naming the Gateway.

> **The success criterion that most constrains the implementation is SC-004: zero false alarms.** It is
> specified at the same severity as a missed alarm because a channel that cries wolf gets ignored, which
> recreates the original failure. Two tasks exist solely to defend it — T003 (a correct no-op must read
> `ok`) and T011 (one failed probe must stay quiet) — and neither should be weakened to make another test
> pass.

## Notes

- `[P]` = different file or independent content, no dependency on an incomplete task.
- Verify each test fails before implementing it; a test that passes immediately is testing the wrong thing.
- Nothing in this feature places an order or opens a broker API session.

# Tasks: Scheduled-Job Healthcheck

**Input**: Design documents from `/specs/004-schedule-healthcheck/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md)

**Tests**: **REQUIRED** (Constitution III). Test tasks precede their implementations.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Add a test helper creating temp artifacts with controllable modification times in `tests/test_health.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T002 Write failing tests for the watched-job table — every scheduled job present, each with a cadence and a grace, all positive — in `tests/test_health.py`
- [X] T003 Define the `WATCHED` table (job, artifact, cadence, grace) in `forex/run/health.py`

**Checkpoint**: The schedule is data and inspectable.

---

## Phase 3: User Story 1 — Find out that a job did not run (Priority: P1) 🎯 MVP

- [X] T004 [P] [US1] Write failing tests for staleness — fresh passes, stale fails, exactly-at-the-boundary passes, and an injected clock drives it all (FR-001) — in `tests/test_health.py`
- [X] T005 [US1] Implement `check_health(now, root)` returning a per-job verdict in `forex/run/health.py`
- [X] T006 [P] [US1] Write failing tests that a missing artifact is overdue not skipped, and that all overdue jobs are reported together (FR-003, FR-004) — in `tests/test_health.py`
- [X] T007 [US1] Handle missing artifacts and aggregate an overall verdict in `forex/run/health.py`
- [X] T008 [P] [US1] Write a failing test that a monthly job checked hours before it is due is not flagged (edge case: cadence boundary) — in `tests/test_health.py`

**Checkpoint**: A silent job failure is detectable.

---

## Phase 4: User Story 2 — Be told without going looking (Priority: P2)

- [X] T009 [US2] Implement `scripts/healthcheck.py` — run the check, print a per-job table, exit non-zero when overdue (FR-005)
- [X] T010 [US2] Raise a desktop notification naming the overdue jobs, wrapped so a notifier failure cannot suppress the status file or exit code (FR-006, FR-008), in `scripts/healthcheck.py`
- [X] T011 [US2] Write the durable status file on every run, pass or fail (FR-007), in `scripts/healthcheck.py`
- [X] T012 [US2] Add the status file to `.gitignore` alongside the other runtime artifacts

**Checkpoint**: A failure reaches the operator two ways.

---

## Phase 5: User Story 3 — The check runs itself (Priority: P3)

- [X] T013 [US3] Install a `com.fx.healthcheck` agent in `scripts/install_schedules.sh`, and remove it on uninstall (FR-009)
- [X] T014 [US3] Update the installer's header comment to describe the fourth agent

---

## Phase 6: Polish

- [X] T015 Run the healthcheck against the real repo and confirm it reports the true current state
- [X] T016 Verify the notification path fires by forcing a failing check
- [X] T017 Run `.venv/bin/python -m pytest -q` and `ruff check .`; confirm green and no new violations beyond the 21 pre-existing
- [X] T018 Update `specs/000-baseline/baseline.md` — close Backlog #2 and note that #1 is now automated
- [X] T019 Document the healthcheck in `docs/scheduled-paper-track.md`, and fix that document's stale `~/Documents/forex` paths while there (Backlog #9)

---

## Dependencies

```
Phase 1 -> Phase 2 (T002-T003) BLOCKS all
   └─> US1 (T004-T008)   MVP — detection
        └─> US2 (T009-T012)   delivery needs a verdict to deliver
             └─> US3 (T013-T014)   scheduling needs something to schedule
                  └─> Phase 6
```

Unlike previous features the stories are genuinely sequential: each needs the one before.

## Implementation Strategy

**MVP = Phases 1–3.** Detection alone is already useful run by hand, and it is the part that has to be
right — a wrong verdict delivered promptly is worse than no verdict.

**T019 folds in Backlog #9** (`docs/scheduled-paper-track.md` still documents `~/Documents/forex`
paths). That staleness *caused* the 2026-08-01 failure this feature exists to catch, and the doc has to
be opened anyway to describe the new agent. Fixing it here rather than leaving a known-wrong document
naming the exact trap that was fallen into.

**The deadline is real.** 2026-09-01 is the first unattended test of the launchd path fix. This should
be installed before then, or that test is unobserved too.

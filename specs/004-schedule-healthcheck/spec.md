# Feature Specification: Scheduled-Job Healthcheck

**Feature Branch**: none — work proceeds on `main`; `specs/004-schedule-healthcheck/` is the feature identity

**Created**: 2026-08-16

**Status**: Draft

**Input**: Backlog #2 — alert on a missed/failed scheduled job

## Context

On 2026-08-01 the monthly FX rebalance did not run. The repo had moved from `~/Documents/forex` to
`~/projects/forex` and the launchd plists still pointed at the old path. Nothing said so. The failure
was found **11 days later**, by accident, while reading logs for an unrelated reason.

It stayed silent because every signal was passive: `launchd.err` is git-ignored and only written when
a job fails, `launchctl list` reported exit 0 throughout, and the absence of a `track.log` entry looks
exactly like a quiet month. Meanwhile the FX book sat on a stale target for four weeks.

The same fix has still never been exercised by launchd — the 2026-08-12 run was manual. **2026-09-01
is the first real test**, and today there is still nothing that would tell you if it failed again.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Find out that a job did not run (Priority: P1)

As the operator, I want to be told when a scheduled job has not produced its expected output within
its cadence, so a silent failure cannot persist for weeks.

**Why this priority**: This is the failure that actually happened, and it is unguarded today.

**Independent Test**: Point the check at a history where an artifact is older than its cadence allows
and confirm it reports that job as overdue.

**Acceptance Scenarios**:

1. **Given** an artifact last written longer ago than its cadence plus grace, **When** the check runs,
   **Then** that job is reported as overdue with how long it has been.
2. **Given** every artifact is current, **When** the check runs, **Then** it reports healthy and says
   nothing further.
3. **Given** an artifact that has never been written at all, **Then** the job is reported as overdue
   rather than skipped.
4. **Given** several jobs are overdue, **Then** all of them are reported, not just the first.

---

### User Story 2 - Be told without going looking (Priority: P2)

As the operator, I want a failing check to reach me rather than waiting in a log, so I do not have to
remember to inspect anything.

**Why this priority**: A check nobody reads reproduces the original failure. But the check has to be
correct before its delivery matters.

**Independent Test**: Force a failing check and confirm both a visible notification and a durable
status file result; force a passing one and confirm no notification.

**Acceptance Scenarios**:

1. **Given** a failing check, **When** it runs, **Then** a desktop notification appears naming what is
   overdue.
2. **Given** a failing check, **Then** a durable status file records the result, so it is still
   discoverable after the notification is gone.
3. **Given** a passing check, **Then** no notification appears and the status file records health.
4. **Given** the notification mechanism is unavailable, **Then** the check still writes its status and
   still reports failure through its exit code.

---

### User Story 3 - The check runs itself (Priority: P3)

As the operator, I want the healthcheck scheduled alongside the jobs it watches, so it needs no
discipline from me.

**Why this priority**: Completes the loop. The check is useful manually, but the failure mode being
guarded is precisely "nobody remembered to look".

**Independent Test**: Install the schedules and confirm the healthcheck agent is registered and runs.

**Acceptance Scenarios**:

1. **Given** the installer runs, **Then** a healthcheck schedule is installed alongside the existing
   three and appears in the loaded agent list.
2. **Given** the uninstall path runs, **Then** the healthcheck schedule is removed with the others.
3. **Given** the installer is re-run, **Then** it updates rather than duplicating.

---

### Edge Cases

- **A cadence boundary**: a monthly job checked on the 1st, hours before it is due, must not be
  reported overdue. Grace must exceed the gap between the job's scheduled time and the check's.
- **A quarterly job**: three months of silence is normal; the check must not cry wolf for a whole
  quarter between basket rebalances.
- **A job that ran but failed part-way**, leaving a stale artifact: indistinguishable from not running,
  and must be reported the same way — the operator needs to look either way.
- **The healthcheck itself failing** (missing file, unreadable artifact) must be visible, not silent.
- **A machine that was asleep**: launchd runs a missed job on wake, so a brief overdue window is
  expected and grace should absorb it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The check MUST verify that each scheduled job has produced its expected output within
  its own cadence plus a grace period.
- **FR-002**: Each job's cadence and grace MUST be stated explicitly and be inspectable, not implied
  by a magic number in code.
- **FR-003**: An artifact that has never been produced MUST be reported as overdue.
- **FR-004**: The check MUST report every overdue job in one run, not stop at the first.
- **FR-005**: The check MUST report a non-zero exit status when any job is overdue.
- **FR-006**: A failing check MUST raise a desktop notification naming the overdue jobs.
- **FR-007**: The check MUST write a durable status file on every run, pass or fail, so the result
  outlives the notification.
- **FR-008**: A failure of the notification mechanism MUST NOT prevent the status file being written
  or the exit status being set.
- **FR-009**: A healthcheck schedule MUST be installable and removable by the existing installer,
  alongside the jobs it watches.
- **FR-010**: The check MUST run read-only: it inspects artifacts and MUST NOT connect to the broker,
  place orders, or modify any tracked data.
- **FR-011**: The staleness logic MUST be unit-testable offline, without waiting for real time to pass.

### Key Entities

- **Watched job**: a scheduled task, its expected output artifact, its cadence, and its grace period.
- **Cadence**: how often the job is expected to write — daily, monthly, quarterly.
- **Grace**: allowance beyond cadence before overdue, absorbing sleep, holidays, and the gap between
  the job's schedule and the check's.
- **Status**: the result of one run — per-job age and verdict, plus an overall pass/fail.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A repeat of the 2026-08-01 failure is surfaced within one day rather than eleven.
- **SC-002**: The operator can tell which job is overdue and by how long, without reading any log.
- **SC-003**: A healthy system produces no notification, so an alert always means something.
- **SC-004**: Cadence and grace for every job can be read in one place and changed without touching
  detection logic.
- **SC-005**: The check never modifies the state it inspects.

## Assumptions

- A job's output artifact is a faithful proxy for the job having run. A job that ran and failed leaves
  a stale artifact, which is reported identically — correct, since either way it needs attention.
- Artifact modification time is the freshness signal. It is simpler than parsing each file's format
  and works for logs and CSVs alike.
- Grace periods: generous enough that a sleeping machine or a holiday does not produce noise, since a
  false alarm trains the operator to ignore real ones.
- The daily NAV snapshot is the earliest warning for everything: it needs the Gateway, so if it goes
  stale, the monthly rebalance is likely to fail too.
- Desktop notification via the OS is sufficient reach. Remote alerting was considered and declined —
  it needs a mail path and another secret outside the repo.

## Dependencies

- The existing scheduled jobs and their artifacts: `nav.csv` (daily), `track.log` (monthly),
  `basket_positions.csv` (quarterly).
- `scripts/install_schedules.sh` for scheduling, which already manages three agents.

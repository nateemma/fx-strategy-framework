# Feature Specification: Truthful Outage Detection

**Feature Branch**: `008-outage-detection`

**Created**: 2026-10-09

**Status**: Draft

**Input**: Backlog #19 and #20 in `specs/000-baseline/baseline.md`, raised by the 2026-09-13 → 2026-10-08
Gateway outage recorded as In-flight #6.

## Why this exists

For 25 days every scheduled job that needed the broker failed, and the monitoring said things were fine.
Two independent defects had to line up for that, and both are still present:

1. The daily healthcheck decides a job is alive by looking at **when its output file was last written**.
   The monthly FX rebalance writes its traceback to that same file, so a run that placed nothing refreshed
   its own proof of life. On 2026-10-01 it was reported `ok`.
2. The Gateway supervisor only runs its port check **when launchd starts it**, and launchd will not start
   it while the previous instance is still running. The previous instance `exec`s the broker software and
   never exits, so after the first start the check never runs again. It had not run in 40 days.

The operator found out by asking. This feature is about the monitoring telling the truth, not about
preventing the outage — the root cause is a periodic credential expiry that IBKR requires a human to
clear, so **the target is detection in hours, not prevention**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A run that did not do its job is reported as failed (Priority: P1)

The operator reads one line in `health_status.txt` and learns whether each scheduled job actually did what
it exists to do. A job that started, failed, and wrote an error is reported as **failed**, not as current.

**Why this priority**: This is the channel the project's own working agreement calls "the channel that
cannot be suppressed", and it is the one that lied. Every other alerting improvement is worth less while
the status page can report green through a total outage. It is also the only story that fixes a *silent*
failure; the others shorten a *noisy* one.

**Independent Test**: Simulate a job whose log was written by a failure and assert the report marks it
failed. Fully testable offline, with no broker and no clock dependency, by injecting `now` as the existing
tests already do.

**Acceptance Scenarios**:

1. **Given** a job whose watched file was touched after the last due time but whose run did not succeed,
   **When** the healthcheck runs, **Then** that job is reported as failed and the overall verdict is not
   healthy.
2. **Given** a job that ran and succeeded, **When** the healthcheck runs, **Then** it is reported `ok`.
3. **Given** a job that ran, succeeded, and correctly placed **zero** orders because its target had not
   moved, **When** the healthcheck runs, **Then** it is reported `ok` — doing nothing on purpose is success.
4. **Given** a job that has never run, **When** the healthcheck runs, **Then** it is reported as never run,
   as it is today.

---

### User Story 2 - A Gateway that stopped serving is noticed within the hour (Priority: P2)

The broker connection dies at 03:00 and the operator learns about it the same morning rather than five
weeks later.

**Why this priority**: Second because it shortens an outage rather than revealing one — once Story 1 lands,
the outage is already visible within a day. This takes it to minutes, which is the difference between
losing one scheduled run and losing a monthly rebalance.

**Independent Test**: Run the watchdog against a closed port with a stubbed process check and assert it
reports unavailable and raises the alert; run it against an open port and assert it stays silent. Offline,
by injecting the probe.

**Acceptance Scenarios**:

1. **Given** the broker software is running but not serving its API port, **When** the watchdog runs,
   **Then** the operator is alerted and a durable record is written.
2. **Given** the API port is serving, **When** the watchdog runs, **Then** nothing is alerted and nothing
   noisy is logged.
3. **Given** the port has been unavailable since the previous check only, **When** the watchdog runs,
   **Then** it does **not** alert yet — a single miss is indistinguishable from the nightly restart.
4. **Given** the port has been unavailable for longer than the restart window, **When** the watchdog runs,
   **Then** it alerts, and it does not re-alert on every subsequent check while the same outage continues.
5. **Given** the broker software is not running at all, **When** the watchdog runs, **Then** it starts it,
   as the current supervisor does.

---

### User Story 3 - The status page names the cause, not just the symptom (Priority: P3)

When jobs are failing because the broker is unreachable, the daily status says so directly instead of
leaving the operator to infer it from several stale files.

**Why this priority**: Diagnostic quality rather than detection. Stories 1 and 2 already surface the
failure; this shortens the time from "something is wrong" to "I know what to do".

**Independent Test**: Render the report with the reachability probe stubbed both ways and compare output.

**Acceptance Scenarios**:

1. **Given** the broker is unreachable, **When** the healthcheck runs, **Then** the status file states that
   directly, alongside the per-job lines.
2. **Given** the broker is reachable, **When** the healthcheck runs, **Then** the status file says so and
   the per-job verdicts are unchanged.
3. **Given** the healthcheck runs where probing is impossible, **When** it reports, **Then** it says the
   reachability of the broker is unknown and does not treat unknown as failure.

---

### Edge Cases

- **A legitimate no-op run.** Every execution path here reconciles, so an unchanged target places zero
  orders. That is a success and MUST NOT be reported as failure. This is the single most likely way a fix
  to Story 1 introduces a false alarm.
- **The nightly 03:00 broker restart.** The API port is legitimately absent for a short window every night.
  The watchdog must not alert on it, and that window is the lower bound on how fast detection can be.
- **A sleeping or powered-off machine.** Produces a gap in checks that must not itself be an alarm; this
  is why the existing design carries per-job grace and why the watchdog debounces.
- **Alert fatigue during a long outage.** A 25-day outage must not produce 18,000 alerts. Re-alerting is
  rate-limited while a single outage persists.
- **The alert channel itself being broken.** Already a known failure here: Notification Centre banners were
  silently dropped on this machine while `osascript` still exited 0. Durable status files and exit codes
  remain the primary record; alerts are an accelerator, never the only channel.
- **A job whose success marker is written but whose output is not**, or vice versa. The two signals can
  disagree; the report must be explicit about which it is asserting on.
- **Weekend and holiday runs.** A daily job on a non-trading day may legitimately do nothing.
- **Two watchdog instances overlapping**, if one run is slow. Starting the broker software twice is a known
  hazard: a duplicate login silently cuts market data to the API for every symbol.

## Requirements *(mandatory)*

### Functional Requirements

**Job success detection (Story 1)**

- **FR-001**: The healthcheck MUST decide a job's verdict from evidence that the job **succeeded**, not from
  the modification time of a file that a failure also writes.
- **FR-002**: Every watched job MUST have a success signal that a failing run cannot produce. Where a job's
  current artifact already has that property it MUST be kept; where it does not, the job MUST be changed to
  emit one.
- **FR-003**: A run that completes successfully while correctly taking no action MUST be recorded as success.
- **FR-004**: A job that has never produced a success signal MUST remain distinguishable from one whose last
  success is merely old.
- **FR-005**: The existing schedule-relative logic — comparing against the last due time with per-job grace,
  rather than against an age threshold — MUST be preserved. It is the part of the current design that works.

**Broker reachability (Stories 2 and 3)**

- **FR-006**: A watchdog MUST check whether the broker API port is serving, on a schedule that continues to
  fire regardless of how long any broker process has been running.
- **FR-007**: The watchdog MUST NOT depend on the liveness of the broker software as a proxy for the API
  being available. Detecting "process alive, port not serving" is the specific failure it exists to catch.
- **FR-008**: The watchdog MUST require more than one consecutive unavailable check before alerting, so the
  nightly restart window cannot raise an alarm.
- **FR-009**: While a single outage persists, the watchdog MUST rate-limit repeat alerts.
- **FR-010**: The watchdog MUST write a durable record of broker availability that survives a dropped alert.
- **FR-011**: The watchdog MUST NOT start the broker software while an instance is already running. A
  duplicate login silently disables market data for every symbol, which presents as a missing subscription.
- **FR-012**: When no broker process is running at all, the watchdog MUST start it, preserving today's
  behaviour.
- **FR-013**: The healthcheck MUST report broker reachability in its status output, with "unknown" as a
  distinct outcome from "unreachable", and MUST NOT treat unknown as a failure.

**Non-negotiables inherited from the constitution**

- **FR-014**: The test suite MUST remain fully offline — no network, no broker, no API key. Reachability
  probing and process inspection MUST be injectable so tests never perform real I/O (Principle III).
- **FR-015**: All 26 existing tests in `tests/test_health.py` MUST continue to pass, or any change to their
  expectations MUST be justified as a corrected assumption rather than a weakened one.
- **FR-016**: Nothing in this feature may place an order, and no new code path may reach a real-money
  account. Probing is read-only and connects to the paper port only (Principle IV).

### Key Entities

- **Job**: a scheduled unit of work with a name, a schedule, a grace allowance, and — new — a success
  signal distinct from its log output.
- **Job verdict**: succeeded / failed / never run / not yet due, per job, as of a given moment.
- **Broker availability**: available / unavailable / unknown, plus how long the current state has held.
- **Durable status record**: the file that outlives any notification and is the channel of record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A scheduled run that fires and fails to do its work is reported as failed in the next daily
  status, in 100% of simulated cases. Today this case reports `ok`.
- **SC-002**: A broker outage beginning at any time of day is surfaced to the operator within **1 hour**.
  The 2026-09-13 outage took **25 days**.
- **SC-003**: The operator can determine from the status record alone whether jobs are failing because the
  broker is unreachable, without reading any log or inspecting any process.
- **SC-004**: Across a normal month of operation — including ~30 nightly restarts, weekends, and at least
  one no-op reconcile — the system raises **zero** false alarms. A false alarm is treated as a defect of the
  same severity as a missed one, because it trains the operator to ignore the channel.
- **SC-005**: A single continuous outage produces at most **one alert per hour**, never one per check.
- **SC-006**: The full test suite still runs offline and green, with no network access and no broker.

## Assumptions

- **A failed job's own log is not a usable success signal**, so success is asserted from a separate signal
  that only a completed run writes. Four of the seven watched jobs already have this property incidentally
  (their positions CSVs are written only on success); the FX rebalance, which watches a catch-all shell log,
  is the one that does not and is therefore the main subject of Story 1.
- **A wedged Gateway is alerted, not automatically recovered.** When the broker software is alive but not
  serving, the watchdog alerts and leaves it alone. This is the deliberate default because the root cause is
  a credential expiry that requires a human login, and because both automated remedies are known to be
  harmful here: starting a second instance triggers a duplicate-login state that silently cuts market data,
  and a hard kill leaves the session registered server-side, after which the next login was measured waiting
  3h42m for release. Auto-starting when **no** instance is running is retained, since that case is safe and
  is what the current supervisor already does. **Confirmed by the operator 2026-10-09**, so this is settled
  scope rather than a default: the watchdog never kills, never restarts a live instance, and never attempts
  a login. It trades recovery speed for not making a bad state worse.
- **Detection latency is bounded below by the nightly restart window**, since a short absence must be
  tolerated to avoid a nightly false alarm. One hour is comfortably above that floor and far below the
  horizon that matters (the next scheduled job).
- The alert mechanism reuses the existing modal-alert path, which is the channel already verified to get
  through on this machine; banners remain best-effort.
- Scope is the paper account on the paper port only. Going live is a separate gated decision.
- Out of scope: fixing the credential expiry itself (not possible — IBKR requires a manual login),
  upgrading the broker software ahead of its 2026-12-15 desupport (Backlog #22), and the `bond_ladder.py`
  default-symbols trap (Backlog #21). Each is tracked separately.

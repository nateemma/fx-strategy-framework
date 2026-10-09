# Phase 1 Data Model: Truthful Outage Detection

No database and no schema migration. Four records, two of them already existing and extended.

---

## 1. `Job` (extended — `forex/run/health.py`)

The existing `NamedTuple` gains one field. Everything else is unchanged.

| Field | Type | Change | Meaning |
|---|---|---|---|
| `name` | str | — | Stable identifier used in the status file and alerts. |
| `artifact` | str | **meaning tightened** | Repo-relative path whose mtime is the job's **proof of success**. MUST be a file that only a completed run writes. |
| `kind` | str | — | `daily` / `monthly` / `quarterly`. |
| `hour`, `minute` | int | — | Local scheduled time. |
| `grace_days` | float | — | Allowance after the due time before overdue. |
| `description` | str | — | Operator-facing text. |
| `enabled` | bool | — | A job that cannot run yet must not alarm. |
| `success_evidence` | str | **NEW** | Why this artifact cannot be written by a failing run. Free text, required and non-empty for every enabled job; asserted by a test. |

**Why a text field rather than a boolean**: a boolean that is always `True` documents nothing and cannot
fail review. Requiring the author to *write down why* is what would have caught the original defect — the
honest answer for `track.log` is "it can't, the shell block appends tracebacks to it", which is unwriteable
without noticing the bug. The test asserts non-empty; the review value is in the content.

**Changed rows in `WATCHED`**:

| Job | Artifact before | Artifact after | `success_evidence` |
|---|---|---|---|
| `paper-rebalance` | `track.log` | **`fx_rebalance_status.csv`** | Appended after the `set -e` block closes, so a failed `forex dryrun --confirm` aborts first. |
| *all others* | unchanged | unchanged | nav.csv / positions CSVs are appended only after a successful broker round-trip. |

---

## 2. `FX rebalance success marker` (new file — `fx_rebalance_status.csv`)

Git-ignored, append-only, one row per successful run. Same idiom as the sleeves' `*_positions.csv`.

```text
timestamp,status
2026-11-01T16:00:04Z,ok
```

Only the mtime is load-bearing; the rows are for the human reading the forward record. Append-only so the
history of successful rebalances survives.

---

## 3. `Reachability` (new, three-valued — `forex/run/health.py`)

| Value | Meaning | Operator action |
|---|---|---|
| `available` | The probe connected. | None. |
| `unavailable` | The probe ran and could not connect. | Log in to the Gateway. |
| `unknown` | No probe was supplied, or probing raised. | None — this is **not** a failure. |

`unknown` exists so the healthcheck remains runnable and honest in a context where probing is impossible,
and so a probe bug cannot manufacture an outage. Per FR-013 it MUST NOT make the report unhealthy.

**Interaction with job verdicts**: reachability is reported **alongside** per-job verdicts and never
overrides them. A reachable broker does not excuse a stale job, and an unreachable one does not by itself
mark any job failed — it explains them.

---

## 4. `WatchdogState` (new — persisted JSON)

The watchdog is a pure decision function over this state. Everything needed to decide is in here, which is
what makes the debounce and rate-limit testable without a clock.

| Field | Type | Meaning |
|---|---|---|
| `consecutive_failures` | int | Probes that failed in a row. Reset to 0 on any success. |
| `first_failure_at` | ISO 8601 or null | When the current outage began; null when available. |
| `last_alert_at` | ISO 8601 or null | When the operator was last alerted about the current outage. |
| `last_state` | str | `available` / `unavailable`, for transition detection and logging. |

A missing or unparseable state file is treated as a fresh start (`consecutive_failures = 0`), never as an
error — a corrupt state file must not be able to suppress alerting or crash the job.

### State transitions

```text
                  probe ok
   ┌──────────────────────────────────────────┐
   │                                          │
   ▼                                          │
AVAILABLE ──probe fails──▶ FAILING(n=1) ──probe fails──▶ FAILING(n=2)
   ▲                           │                             │
   │                           │ probe ok                    │ n >= ALERT_AFTER
   └───────────────────────────┘                             ▼
                                                        ALERTED ──probe fails──▶ ALERTED
                                                           │                    (re-alert only if
                                                           │ probe ok            now - last_alert
                                                           ▼                     >= RATE_LIMIT)
                                                       AVAILABLE
                                                    (recovery is recorded,
                                                     and is not an alert)
```

**Decision outputs** — exactly one per probe:

| Output | When |
|---|---|
| `quiet` | Probe succeeded, or failures so far are below `ALERT_AFTER`, or already alerted within the rate limit. |
| `alert` | `consecutive_failures >= ALERT_AFTER` **and** (never alerted for this outage **or** `now - last_alert_at >= RATE_LIMIT`). |
| `start` | Probe failed **and** no broker process is running at all. Delegated to the existing agent — see note. |

**Note on `start`**: the operator-confirmed constraint is alert-only, so the watchdog itself performs no
start. The `start` output exists in the decision table because the *condition* is meaningful and worth
asserting in tests (it proves the watchdog can tell "nothing running" from "running but wedged"), and
because the runner must do nothing in that case rather than alert about a Gateway the existing agent is
about to bring up. Treating it as a distinct outcome keeps that silence deliberate rather than accidental.

### Constants

| Constant | Value | Source |
|---|---|---|
| `PROBE_INTERVAL` | 300s (launchd `StartInterval`) | Balance of detection latency against wakeups. |
| `ALERT_AFTER` | 2 consecutive failures | ≥5 min outage; clears the 45s re-login and the 2m06s cold start measured in [research.md](./research.md) R2. |
| `RATE_LIMIT` | 3600s | SC-005: at most one alert per hour for a single continuous outage. |
| `PROBE_TIMEOUT` | 2s | A local port either answers immediately or is not serving. |

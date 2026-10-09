# Phase 1 Contracts: Truthful Outage Detection

This project exposes a library (`forex/`) consumed by scripts, plus launchd-invoked CLIs. The contracts
that matter are therefore function signatures, file formats, and exit codes.

---

## A. `forex/run/health.py`

### A.1 `Job` — extended

```python
class Job(NamedTuple):
    name: str
    artifact: str
    kind: str
    hour: int
    minute: int
    grace_days: float
    description: str
    success_evidence: str          # NEW — why a failing run cannot write `artifact`
    enabled: bool = True
```

**Breaking-change note**: `success_evidence` is inserted **before** `enabled`, which has a default. Every
`Job(...)` in `WATCHED` is constructed positionally today, so each entry must be updated in the same
commit. Tests that construct `Job` positionally will also need the new argument — that is intentional:
a new watched job must not be addable without stating its success evidence.

### A.2 `check_health` — extended signature

```python
def check_health(now, root=Path("."), probe=None) -> HealthReport
```

| Parameter | Contract |
|---|---|
| `now` | Unchanged. Injected datetime; all comparisons are relative to it. |
| `root` | Unchanged. |
| `probe` | **NEW, optional.** A zero-argument callable returning `True` (serving) / `False` (not serving). `None` ⇒ reachability is `unknown`. If it raises, the result is `unknown` — a probe bug MUST NOT manufacture an outage. |

**Guarantees**:

- Remains **pure and read-only** with respect to the filesystem: it stats files and calls `probe`, and
  writes nothing.
- Per-job verdicts are computed **identically to today** and do not depend on `probe` in any way.
- `HealthReport` gains a `reachability` field (`"available" | "unavailable" | "unknown"`).
- `report.healthy` is `False` if and only if at least one enabled job is overdue. **Reachability does not
  affect it** (FR-013) — the daily status explains, the per-job verdicts decide.

### A.3 `format_report` — extended output

Adds exactly one line above the existing per-job block. The per-job line format is unchanged, because the
operator reads this file at a glance and the existing shape is already familiar:

```text
broker API (port 4002): UNAVAILABLE — jobs needing the Gateway will fail until it is logged in
  ok      basket-rebalance   last output 2026-10-08 08:57   due 2026-10-01 09:30   basket_positions.csv
```

For `unknown` the line states that reachability was not checked, so the absence of a verdict is explicit
rather than looking like a pass.

---

## B. `forex/run/gateway_watchdog.py` (new)

Pure decision logic. No sockets, no subprocesses, no file I/O — all of that belongs to the runner.

```python
ALERT_AFTER   = 2        # consecutive failed probes
RATE_LIMIT    = 3600     # seconds between repeat alerts for one outage

class WatchdogState(NamedTuple):
    consecutive_failures: int = 0
    first_failure_at: datetime | None = None
    last_alert_at: datetime | None = None
    last_state: str = "available"

class WatchdogDecision(NamedTuple):
    action: str                  # "quiet" | "alert" | "start"
    state: WatchdogState         # the state to persist
    message: str                 # operator-facing text; "" when action == "quiet"

def decide(serving: bool, process_alive: bool, state: WatchdogState, now: datetime) -> WatchdogDecision
```

**Contract**:

| Given | Then |
|---|---|
| `serving=True` | `action="quiet"`; counters reset; a recovery from a previously alerted outage is reflected in `message` for the log but still does **not** alert. |
| `serving=False`, `process_alive=False` | `action="start"` — the "nothing is running" case, handled by the existing agent. The runner takes no action. |
| `serving=False`, `process_alive=True`, failures < `ALERT_AFTER` | `action="quiet"` — inside the restart window. |
| `serving=False`, `process_alive=True`, failures ≥ `ALERT_AFTER`, no prior alert this outage | `action="alert"` |
| same, but alerted < `RATE_LIMIT` ago | `action="quiet"` |
| same, but alerted ≥ `RATE_LIMIT` ago | `action="alert"`, `last_alert_at` advanced |

**Invariants** (each gets a test):

1. `decide` **never** returns an action that kills or restarts anything. `"start"` is the strongest action
   and the runner implements it as a no-op plus a log line.
2. `decide` is a pure function: calling it twice with the same arguments yields the same result.
3. Its message always names the outage duration derived from `first_failure_at`, so an alert is actionable
   without consulting a log.

---

## C. `scripts/gateway_watchdog.py` (new runner)

```text
.venv/bin/python scripts/gateway_watchdog.py [--self-test]
```

| Concern | Contract |
|---|---|
| Probe | `socket.create_connection(("127.0.0.1", 4002), timeout=2)`, closed immediately. No API handshake — see [research.md](./research.md) R3. |
| Process check | Is a Gateway/IBC process running. Injectable; implemented by inspecting the process table. |
| Port | `IB_PORT` env, default `4002`. Paper only. |
| Alerting | Reuses `alert_command` from `health.py` — the modal path already verified to get through on this machine. Banner is best-effort and its failure is ignored. |
| Durable record | Writes `gateway_status.txt` **every run**, available or not, so the file's own mtime proves the watchdog is alive. State persists to `gateway_watchdog_state.json`. |
| Exit code | `0` when serving or quiet; `1` when it alerted. Never non-zero merely because the broker is down inside the debounce window, so launchd's error log stays meaningful. |
| `--self-test` | Fires a test alert and exits, mirroring `healthcheck.py --self-test`. Proves the channel without waiting for an outage. |
| Failure mode | A crash must not be silent: unhandled exceptions are caught, written to the durable record, and exited non-zero. |

---

## D. `scripts/monthly_paper_rebalance.sh` (modified)

One line added **after** the `{ ... } >> track.log 2>&1` block closes:

```bash
printf '%s,ok\n' "$STAMP" >> fx_rebalance_status.csv
```

**Contract**: reached only when every command inside the block succeeded, because the script runs under
`set -euo pipefail`. Verified against the forward record — 5 run headers, 4 `--- done ---` lines, the
missing one being the failed 2026-10-01 run.

---

## E. `scripts/launchagents/local.fx-gateway-watchdog.plist` (new, vendored)

| Key | Value | Why |
|---|---|---|
| `Label` | `local.fx-gateway-watchdog` | — |
| `StartInterval` | `300` | **Not `KeepAlive`.** A fast-exiting poll script looks like a crash loop to `KeepAlive`, which applied escalating backoff measured at 3h47m — the trap recorded in the existing plist's own comment. |
| `RunAtLoad` | `true` | Probe immediately on login rather than waiting 5 minutes. |
| `StandardOutPath` / `StandardErrorPath` | `gateway_watchdog.log` | — |

**Explicitly unchanged**: `~/Library/LaunchAgents/local.ibc-gateway.plist` and
`~/ibc/gateway_supervisor.sh`. They keep sole responsibility for cold-starting IBC. Not touching them is
what guarantees this feature cannot start a second Gateway.

# Phase 0 Research: Truthful Outage Detection

**Date**: 2026-10-09. Three questions needed evidence rather than judgement. All resolved; no
`NEEDS CLARIFICATION` remains.

---

## R1 — What success signal can the FX rebalance emit, and does it cost anything?

**Decision**: The runner writes a one-line marker to a new `fx_rebalance_status.csv` **after** its
`{ ... } >> track.log` block closes. The watched job asserts on that file's mtime. `check_health`'s
comparison logic is not touched.

**Rationale**: `scripts/monthly_paper_rebalance.sh` runs under `set -euo pipefail`, so a non-zero exit
from the `forex dryrun --confirm` step aborts the script before anything after the block runs. That is
not inferred — it is visible in the forward record: `track.log` holds **5 run headers but only 4
`--- done ---` lines**, and the missing one is the 2026-10-01 failure. The same mechanism that swallowed
the `done` line will swallow a marker write, which is exactly the property wanted. Cost is one line of
Bash and one file.

**Alternatives considered**:

- *Parse `track.log` for a success pattern.* Rejected. It works — the absent `--- done ---` is already a
  valid signal — but it requires parsing timestamps out of a free-text log to decide whether the success
  belongs to the current cycle, which replaces a well-tested mtime comparison with a brittle text one. The
  26 existing tests cover the mtime path; this would put new logic under the part that already works.
- *Have the Python CLI write the marker.* Rejected on Principle I: `forex/cli.py` is framework code and a
  forward-track status file is a property of this particular deployment, not of the framework.
- *Make every job write a marker.* Rejected as unnecessary. Five of the seven watched artifacts
  (`nav.csv`, four `*_positions.csv`) are already written only on success. Changing them would be churn
  for no behaviour change; the rule is instead documented so the next job added cannot repeat the mistake.

---

## R2 — How long is a legitimate broker outage, and should the watchdog exclude a time window?

**Decision**: **Debounce on duration, not on wall-clock time.** Alert only after N consecutive failed
probes. With a 5-minute interval and N=2, the shortest outage that can alert is ~5 minutes and the longest
undetected one is ~10 minutes. Do **not** special-case 03:00.

**Rationale**: the assumption that restarts happen at 03:00 is false. `AutoRestartTime=03:00` is set in
`~/ibc/config.ini`, but the most recent re-login happened at **21:52 on 2026-10-08** — IBC detected a
dialog entitled *"Re-login is required"*, clicked through it, and logged "Login has completed" at
21:53:30, about **45 seconds** end to end. A time-window exclusion built around 03:00 would have missed
this entirely and would alarm on it.

Two measured durations bound the debounce:

| Event | Duration | Source |
|---|---|---|
| Automatic re-login (dialog handled by IBC) | ~45s | `ibc-…_Saturday.txt:3035-3044`, 2026-10-08 |
| Cold start after a hard kill | 2m06s | commit `bb6a431`, measured by the operator |

A 5-minute floor clears both with margin, and 10-minute worst-case detection is far inside SC-002's
one-hour target and far inside the gap to the next scheduled job.

**Alternatives considered**:

- *Alert on the first failed probe.* Rejected: it would fire on every nightly restart and on the 45-second
  re-login above, i.e. ~30+ false alarms a month. SC-004 treats that as a defect of equal severity to a
  missed alarm, because it is what trains an operator to ignore the channel.
- *Suppress alerts between 02:55 and 03:10.* Rejected on the evidence above — restarts are not confined to
  that window — and it adds a timezone-dependent branch for no gain over duration debouncing.
- *Probe more often (60s) with N=5.* Equivalent detection, five times the wakeups, no benefit.

---

## R3 — Can a port probe be mistaken for a competing IBKR login?

**Decision**: Probe with a bare `socket` TCP connect-and-close. Do not use `ib_async`, and do not open an
API session.

**Rationale**: this matters because error **10197** ("competing live session") silently cuts market data to
the API for *every* symbol and presents exactly like a missing subscription — it has already cost this
project one wrong diagnosis (`memory/ibkr-futures-history-is-too-short.md`). But 10197 is triggered by a
duplicate *IBKR account login* — Client Portal, the mobile app, TWS elsewhere — not by an API client
attaching to a local port. Every sleeve already attaches API clients routinely with no such effect. A TCP
connect that sends no API handshake and immediately closes is strictly weaker than that: it establishes
nothing the Gateway would register as a session.

This also removes a dependency and keeps the probe trivially injectable, which is what lets the suite
stay offline per Principle III.

**Alternatives considered**:

- *Connect with `ib_async` and call `managedAccounts()`.* Richer — it would distinguish "port serving but
  account data broken" from "port serving" — but it opens a real API session on a schedule, for a
  diagnosis the daily healthcheck already provides, and it imports a broker library into a monitoring
  path. Rejected as a worse risk/benefit trade. Noted as a possible later refinement if a
  serving-but-useless Gateway is ever actually observed.
- *Shell out to `nc -z`, as the current supervisor does.* Works, but spawning a process per probe is
  harder to inject in tests than a function returning a bool.

---

## Resolved: what this feature deliberately does not do

Carried from the spec's Assumptions and confirmed by the operator on 2026-10-09 — recorded here because it
shaped the design more than anything else:

**The watchdog never kills a process, never restarts a live instance, and never attempts a login.** The
cold-start case is left to the *existing, unmodified* `local.ibc-gateway` agent, whose timer starvation
only occurs while IBC is alive: when IBC exits, the job completes and the interval timer fires again. So
the one recovery action the operator approved is already correctly implemented and is not re-derived here.
The practical consequence is that **nothing in this feature can start a second Gateway**, which is the
failure mode with the worst and most deniable blast radius.

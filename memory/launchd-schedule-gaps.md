---
name: launchd-schedule-gaps
description: Only 3 of the sleeves/jobs are scheduled in launchd; the monthly FX rebalance silently failed on 2026-08-01 after the repo move and is unvalidated until 2026-09-01
metadata: 
  node_type: memory
  type: project
  originSessionId: 844844bf-ae57-49de-90f7-44d806550f05
  modified: 2026-08-16T21:28:38.542Z
---

Unattended operation on this machine is **partially wired**. Installed launchd agents (all loaded,
last exit 0):

| Agent | Schedule | Next |
|---|---|---|
| `com.fx.paper-rebalance` | day 1, 09:00 | 2026-09-01 |
| `com.fx.basket-rebalance` | quarterly Jan/Apr/Jul/Oct 1, 09:30 | 2026-10-01 |
| `com.fx.nav-snapshot` | daily 21:00 | daily |

**Not scheduled at all:** the bond-ladder, income, and cash sleeves. They are manual-only runners.

**The 2026-08-01 silent failure.** The repo moved from `~/Documents/forex` to `~/projects/forex`. The
plists still pointed at the old path, and `launchd.err` recorded
`/Users/philprice95/Documents/forex/scripts/monthly_paper_rebalance.sh: Operation not permitted` at
09:00 on 2026-08-01 — so **that month's FX rebalance never ran**. The plists were rewritten at 09:56
the same day. The 2026-08-12 rebalance in `track.log` was a *manual* run (21:49 UTC), so **the fix has
never been exercised by launchd**; 2026-09-01 is the first real test.

Two things that made it silent: `launchd.err` is gitignored and only written on failure, and
`launchctl list` still reported exit 0. Nothing alerts on a missed rebalance.

Also: `com.fx.paper-rebalance.plist` carries the **FRED API key in cleartext** in
`EnvironmentVariables`. The file is mode 0600 so it is not exposed to other users, but it sits outside
the EnvConfig-via-environment discipline the README describes.

**Why:** a missed monthly rebalance leaves the FX book stale for a month with no signal that anything
went wrong — the forward record silently stops being a record of the strategy.

**How to apply:** after 2026-09-01, check `track.log` for a 09:00-local entry before trusting the
schedule. When anything moves the repo, re-run `scripts/install_schedules.sh` — the plists hardcode
absolute paths. See [[paper-track-live-state]] and [[cash-sleeve-never-deployed]].

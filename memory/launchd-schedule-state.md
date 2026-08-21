---
name: launchd-schedule-state
description: Six launchd agents now scheduled and verified; the 2026-08-01 FX rebalance silently failed after the repo move and launchd has still never exercised the fix
metadata:
  node_type: memory
  type: project
---

Unattended operation is wired. Six agents installed and verified loaded (2026-08-21, all exit 0):

| Agent | Schedule |
|---|---|
| `com.fx.paper-rebalance` | day 1, 09:00 |
| `com.fx.basket-rebalance` | quarterly Jan/Apr/Jul/Oct 1, 09:30 |
| `com.fx.nav-snapshot` | daily 21:00 |
| `com.fx.healthcheck` | daily |
| `com.fx.vix-carry` | daily (contango gate) |
| `com.fx.trend-sleeve` | monthly — **watching an undeployed sleeve**, so it carries an `enabled` flag |

**The 2026-08-01 silent failure, still unclosed.** The repo moved from `~/Documents/forex` to
`~/projects/forex`; the plists still pointed at the old path and `launchd.err` recorded
`Operation not permitted` at 09:00 — that month's FX rebalance never ran. Plists were rewritten the
same day, but the 2026-08-12 rebalance was a **manual** run, so **launchd has never exercised the
fix**. 2026-09-01 is the first real test: confirm `track.log` carries a 09:00-local entry, which is
what distinguishes a scheduled run from a manual one. (Backlog #1.)

Two things made it silent: `launchd.err` is gitignored and only written on failure, and
`launchctl list` still reported exit 0.

**`launchctl load` exits 0 for a file that does not exist**, so the installer once reported "loaded"
for an agent it had never created. `scripts/install_schedules.sh` now verifies with awk after loading.

macOS **Notification Centre banners are silently suppressed** here — the healthcheck fired with exit 0
and nothing appeared. It uses a modal `display alert ... giving up after` instead.

`com.fx.paper-rebalance.plist` carries the **FRED API key in cleartext** in `EnvironmentVariables`
(mode 0600, so not exposed to other users, but outside the EnvConfig discipline).

**How to apply:** when anything moves the repo, re-run `scripts/install_schedules.sh` — plists hardcode
absolute paths, and a move is exactly what caused the one real outage. See [[paper-track-live-state]]
and [[sleeve-table-is-design-not-deployment]].

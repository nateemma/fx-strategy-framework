# Scheduled Forward Paper Track

Run the deployable book (`carry_cot_mom` on the deliverable EM-inclusive universe) forward on the **IBKR
paper account** on a monthly cadence, to accrue an out-of-sample, real-execution track you compare against
the backtest. Uses `scripts/monthly_paper_rebalance.sh` (the validated CLI placement path — it reconciles,
so a repeat run with an unchanged target trades nothing; validated 2026-07-17: `carry_cot_mom` placed on
paper, reconcile turnover 0.756→0.015). It first runs `scripts/refresh_track_data.py` to refresh all three
data sources the book needs (IBKR daily spot + FRED rates + CFTC COT). Note the diffuse 3-sleeve book has a
few small legs that skip below the 20k-unit min-order / route as odd lots (NZD, ZAR at ~$1M NAV) — the
pre-trade odd-lot warning logs exactly which.

## Cadence & why monthly
Carry's signal is monthly (interbank rates), so the book only changes ~monthly — a faster schedule would
just re-confirm the same target and trade nothing. One meaningful rebalance per month; the track builds
slowly (that's inherent to forward paper trading vs a backtest).

## Tracking performance
Two records accrue:
- **`track.log`** — one block per rebalance (orders placed, turnover, cost). The *activity* log.
- **`nav.csv`** — the *equity curve*. `scripts/snapshot_nav.py` appends a dated row (NAV, unrealized P&L,
  open-leg count). **Run it DAILY** (its own cron/launchd, separate from the monthly rebalance) so the
  curve has enough points to measure. FX shows as multi-currency *cash* (so IBKR `GrossPositionValue`
  reads 0); the equity that matters is **NetLiquidation (NAV)**, which revalues those balances into USD —
  that is the strategy's P&L.

`scripts/track_report.py` reads `nav.csv` on demand and prints since-inception total/annualized return,
vol, Sharpe, and max drawdown, against the backtest expectation (walk-forward Sharpe ~1.15; ~8–10%/yr
levered to 10% vol). Judge on **Sharpe vs 1.15** once the sample is months, not days — a paper track needs
real elapsed time before its stats mean anything. (`track.log` and `nav.csv` are git-ignored — they're
your local forward record; back them up separately if you want history preserved.)

## Prerequisites (the operational reality)
1. **IB Gateway, always-on, auto-restart + auto-login** — NOT TWS. TWS auto-restarts daily and needs a
   re-login, so a monthly cron will usually find it down (we hit exactly this). Gateway paper port = 4002.
2. **`FRED_API_KEY`** available to the scheduled job's environment (the script refreshes rates first).
3. The project venv at `.venv`.
The script fails loudly (non-zero, logged to `track.log`) if Gateway is down or the key is missing.

## Is it still running? (`com.fx.healthcheck`)

On **2026-08-01** the monthly rebalance did not fire: the repo had moved from `~/Documents/forex` to
`~/projects/forex` and these plists still named the old path. Nothing said so, and it went unnoticed
for two weeks. Every signal was passive — `launchd.err` is written only on failure and is git-ignored,
`launchctl list` reported exit 0 throughout, and a missing `track.log` entry looks exactly like a
quiet month.

`scripts/healthcheck.py` closes that hole. It asks, for each job, whether its **output is newer than
the last time the job was due to fire** — the one signal that survives a job that never ran at all.
Age alone is not enough: a monthly artifact is legitimately up to 31 days old, so an age threshold
could not flag a missed run for three more weeks.

```bash
.venv/bin/python scripts/healthcheck.py     # read-only; no broker, no network
```

Overdue jobs raise a **modal alert** and set a non-zero exit code; every run writes
`health_status.txt` so the result outlives the alert.

> **Why a modal and not a notification banner.** Banners are delivered under Script Editor's
> notification permission. On this machine that permission is not granted, so `osascript` exited 0
> while nothing appeared — a silently-suppressed alert, which is worse than none. A modal is an app
> window and cannot be suppressed that way; it bounds itself with `giving up after` so an unattended
> machine dismisses it rather than blocking the job. A banner is still fired as a bonus, and will
> start working if you grant Script Editor notification permission in System Settings → Notifications.
>
> Verify the channel any time without waiting for a failure:
> ```bash
> .venv/bin/python scripts/healthcheck.py --self-test
> ```

A healthy run is silent, so an alert always means something. Installed by `install_schedules.sh` to
run daily at **22:00**, an hour after the NAV snapshot.

Grace periods (in `forex/run/health.py`, alongside the schedule): daily 1.5 days — one missed snapshot
is a harmless gap, so an alert means two consecutive misses, which is what a dead Gateway looks like;
monthly 3 days; quarterly 5 days. Generous on purpose — a false alarm teaches you to ignore the
channel, which recreates the original failure.

**One limitation worth knowing:** it checks that the artifact is fresh, not *how* it got fresh. A
manual run satisfies the check exactly as a scheduled one does. That is why the 2026-08-12 manual
rebalance leaves the current status healthy even though the scheduled job has still never been
exercised since the fix.

## Install — one command (recommended)
```bash
./scripts/install_schedules.sh            # run from a normal terminal (reads $FRED_API_KEY from your env)
```
Generates all four launchd plists into `~/Library/LaunchAgents` with this repo's absolute paths and your
`$FRED_API_KEY` baked into the monthly job (chmod 600), and loads them. Re-run to update; `install_schedules.sh
uninstall` removes them all. Verify with `launchctl list | grep com.fx`. Override the port with `IB_PORT=… ./scripts/install_schedules.sh`.
The raw plists below are what it generates — for reference or manual install.

## Install — macOS launchd (the generated plists, for reference)
Monthly rebalance — `~/Library/LaunchAgents/com.fx.paper-rebalance.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fx.paper-rebalance</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>/Users/philprice95/projects/forex/scripts/monthly_paper_rebalance.sh</string></array>
  <key>EnvironmentVariables</key>
  <dict><key>FRED_API_KEY</key><string>__YOUR_KEY__</string><key>IB_PORT</key><string>4002</string></dict>
  <key>StartCalendarInterval</key><dict><key>Day</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardErrorPath</key><string>/Users/philprice95/projects/forex/launchd.err</string>
</dict></plist>
```
`launchctl load ~/Library/LaunchAgents/com.fx.paper-rebalance.plist` to enable.
(Prefer not to put the key in the plist? Point the job at a wrapper that `source`s it from a 600-perm
file outside the repo. Never commit the key.)

## Install — daily NAV snapshot (launchd, runs 21:00 local every day)
Builds the equity curve (`nav.csv`) — read-only, no FRED key needed.
`~/Library/LaunchAgents/com.fx.nav-snapshot.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fx.nav-snapshot</string>
  <key>WorkingDirectory</key><string>/Users/philprice95/projects/forex</string>
  <key>ProgramArguments</key>
  <array><string>/Users/philprice95/projects/forex/.venv/bin/python</string><string>scripts/snapshot_nav.py</string></array>
  <key>EnvironmentVariables</key><dict><key>IB_PORT</key><string>4002</string></dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>21</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/Users/philprice95/projects/forex/snapshot.log</string>
  <key>StandardErrorPath</key><string>/Users/philprice95/projects/forex/snapshot.log</string>
</dict></plist>
```
`launchctl load ~/Library/LaunchAgents/com.fx.nav-snapshot.plist` to enable. (Requires Gateway up at
21:00; a missed day just leaves a gap in the curve — harmless.)

## Install — cron (alternative)
```
0 9 1 * *  FRED_API_KEY=__YOUR_KEY__ IB_PORT=4002 /Users/philprice95/projects/forex/scripts/monthly_paper_rebalance.sh
0 21 * * * IB_PORT=4002 /Users/philprice95/projects/forex/.venv/bin/python /Users/philprice95/projects/forex/scripts/snapshot_nav.py >> /Users/philprice95/projects/forex/snapshot.log 2>&1
```

## Reading the track
- **`track.log`** — each rebalance's placed orders / turnover / cost (the activity log).
- **`nav.csv`** — the equity curve (daily NAV + open-leg count from the snapshot job).
- **`python scripts/track_report.py`** — since-inception return / vol / Sharpe / max-drawdown vs the
  backtest expectation (WF Sharpe ~1.15). Judge on **Sharpe vs 1.15 once the sample is months**, not days.

The point of the forward track is catching real-execution drift (spreads, fills, data staleness, the
diffuse book's marginal-leg churn) that a backtest can't show — not re-deriving the edge.

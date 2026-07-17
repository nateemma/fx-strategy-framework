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

## Prerequisites (the operational reality)
1. **IB Gateway, always-on, auto-restart + auto-login** — NOT TWS. TWS auto-restarts daily and needs a
   re-login, so a monthly cron will usually find it down (we hit exactly this). Gateway paper port = 4002.
2. **`FRED_API_KEY`** available to the scheduled job's environment (the script refreshes rates first).
3. The project venv at `.venv`.
The script fails loudly (non-zero, logged to `track.log`) if Gateway is down or the key is missing.

## Install — macOS launchd (runs 1st of each month, 09:00 local)
`~/Library/LaunchAgents/com.fx.paper-rebalance.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fx.paper-rebalance</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>/Users/philprice95/Documents/forex/scripts/monthly_paper_rebalance.sh</string></array>
  <key>EnvironmentVariables</key>
  <dict><key>FRED_API_KEY</key><string>__YOUR_KEY__</string><key>IB_PORT</key><string>4002</string></dict>
  <key>StartCalendarInterval</key><dict><key>Day</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardErrorPath</key><string>/Users/philprice95/Documents/forex/launchd.err</string>
</dict></plist>
```
`launchctl load ~/Library/LaunchAgents/com.fx.paper-rebalance.plist` to enable.
(Prefer not to put the key in the plist? Point the job at a wrapper that `source`s it from a 600-perm
file outside the repo. Never commit the key.)

## Install — cron (alternative)
```
0 9 1 * *  FRED_API_KEY=__YOUR_KEY__ IB_PORT=4002 /Users/philprice95/Documents/forex/scripts/monthly_paper_rebalance.sh
```

## Reading the track
`track.log` records each run's placed orders / NAV; the **IBKR paper account statements** are the P&L
curve. Compare realized fills/turnover against the backtest's expectations — the point of the forward
track is catching real-execution drift (spreads, fills, data), not re-deriving the edge.

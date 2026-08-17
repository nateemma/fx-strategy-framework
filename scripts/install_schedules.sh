#!/usr/bin/env bash
# Install (or uninstall) the forward-paper-track launchd schedules:
#   - com.fx.paper-rebalance    : monthly FX rebalance (1st of month, 09:00 local)      [needs FRED_API_KEY]
#   - com.fx.basket-rebalance   : quarterly rebalance of ALL FOUR ETF sleeves (1st Jan/Apr/Jul/Oct,
#                                 09:30) — basket, bond ladder, income, cash          [no key]
#   - com.fx.nav-snapshot       : daily NAV snapshot (21:00 local)                      [read-only, no key]
#   - com.fx.trend-sleeve       : monthly cross-asset trend sleeve, futures (1st, 10:00)  [no key]
#                                 NEEDS a CME/CBOT/NYMEX market-data subscription
#   - com.fx.healthcheck        : daily scheduled-job healthcheck (22:00 local)         [read-only, no key]
#                                 notifies + writes health_status.txt when a job is overdue
# Generates the plists into ~/Library/LaunchAgents with this repo's absolute paths, then loads them.
# The FRED key is written to ~/.config/forex/env (0600) and read by the runner at fire time — it is
# deliberately NOT put in the plist, because launchd EnvironmentVariables are readable by any
# process via `launchctl print`. Re-run any time to update (idempotent). "install_schedules.sh uninstall"
# removes them. Override the port with IB_PORT=... (default 4002).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
IB_PORT="${IB_PORT:-4002}"
TREND_RISK_BASE="${TREND_RISK_BASE:-200000}"
LA="$HOME/Library/LaunchAgents"
FOREX_ENV="$HOME/.config/forex/env"
REBAL_PLIST="$LA/com.fx.paper-rebalance.plist"
BASKET_PLIST="$LA/com.fx.basket-rebalance.plist"
SNAP_PLIST="$LA/com.fx.nav-snapshot.plist"
HEALTH_PLIST="$LA/com.fx.healthcheck.plist"
TREND_PLIST="$LA/com.fx.trend-sleeve.plist"

if [ "${1:-}" = "uninstall" ]; then
  for pl in "$REBAL_PLIST" "$BASKET_PLIST" "$SNAP_PLIST" "$HEALTH_PLIST" "$TREND_PLIST"; do
    launchctl unload "$pl" 2>/dev/null || true
    rm -f "$pl" && echo "removed: $pl"
  done
  exit 0
fi

[ -x "$PY" ] || { echo "venv python not found at $PY — create the venv first" >&2; exit 1; }
# The FRED key goes to a 0600 file OUTSIDE the repo, never into the plist: launchd
# EnvironmentVariables are readable by any process via `launchctl print`.
if [ -n "${FRED_API_KEY:-}" ]; then
  mkdir -p "$(dirname "$FOREX_ENV")"
  umask 077 && printf 'export FRED_API_KEY=%s\n' "$FRED_API_KEY" > "$FOREX_ENV"
  chmod 600 "$FOREX_ENV"
  echo "wrote FRED key -> $FOREX_ENV (0600)"
elif [ -f "$FOREX_ENV" ]; then
  echo "using existing $FOREX_ENV for the FRED key"
else
  echo "no FRED_API_KEY in the environment and no $FOREX_ENV — set one before running" >&2
  exit 1
fi
mkdir -p "$LA"

cat > "$REBAL_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fx.paper-rebalance</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$REPO/scripts/monthly_paper_rebalance.sh</string></array>
  <key>EnvironmentVariables</key>
  <dict><key>IB_PORT</key><string>$IB_PORT</string></dict>
  <key>StartCalendarInterval</key><dict><key>Day</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardErrorPath</key><string>$REPO/launchd.err</string>
</dict></plist>
EOF
chmod 600 "$REBAL_PLIST"          # owner-only on principle; no secret in it any more

cat > "$BASKET_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fx.basket-rebalance</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$REPO/scripts/quarterly_sleeves.sh</string></array>
  <key>EnvironmentVariables</key><dict><key>IB_PORT</key><string>$IB_PORT</string></dict>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Month</key><integer>1</integer><key>Day</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Month</key><integer>4</integer><key>Day</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Month</key><integer>7</integer><key>Day</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Month</key><integer>10</integer><key>Day</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>30</integer></dict>
  </array>
  <key>StandardErrorPath</key><string>$REPO/launchd.err</string>
</dict></plist>
EOF

cat > "$SNAP_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fx.nav-snapshot</string>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>scripts/snapshot_nav.py</string></array>
  <key>EnvironmentVariables</key><dict><key>IB_PORT</key><string>$IB_PORT</string></dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>21</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$REPO/snapshot.log</string>
  <key>StandardErrorPath</key><string>$REPO/snapshot.log</string>
</dict></plist>
EOF

cat > "$HEALTH_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fx.healthcheck</string>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>scripts/healthcheck.py</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>22</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$REPO/health.log</string>
  <key>StandardErrorPath</key><string>$REPO/health.log</string>
</dict></plist>
EOF

cat > "$TREND_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fx.trend-sleeve</string>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>ProgramArguments</key>
  <array><string>$PY</string><string>scripts/trend_sleeve.py</string>
         <string>--risk-base</string><string>$TREND_RISK_BASE</string><string>--confirm</string></array>
  <key>EnvironmentVariables</key><dict><key>IB_PORT</key><string>$IB_PORT</string></dict>
  <key>StartCalendarInterval</key><dict><key>Day</key><integer>1</integer><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$REPO/trend.log</string>
  <key>StandardErrorPath</key><string>$REPO/trend.log</string>
</dict></plist>
EOF

for pl in "$REBAL_PLIST" "$BASKET_PLIST" "$SNAP_PLIST" "$HEALTH_PLIST" "$TREND_PLIST"; do
  launchctl unload "$pl" 2>/dev/null || true    # unload-first so re-running updates cleanly
  launchctl load "$pl"
  echo "loaded: $(basename "$pl")"
done
echo "installed. FX rebalance = 1st 09:00 ; basket rebalance = 1st Jan/Apr/Jul/Oct 09:30 ; NAV snapshot = 21:00 ;"
echo "           healthcheck = 22:00 daily ; trend sleeve = 1st 10:00 (risk base $TREND_RISK_BASE) ; port=$IB_PORT"
echo "verify:  launchctl list | grep com.fx"
echo "remove:  $0 uninstall"

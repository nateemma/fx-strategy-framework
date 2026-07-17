#!/usr/bin/env bash
# Install (or uninstall) the forward-paper-track launchd schedules:
#   - com.fx.paper-rebalance : monthly rebalance (1st of month, 09:00 local)  [needs FRED_API_KEY]
#   - com.fx.nav-snapshot    : daily NAV snapshot (21:00 local)               [read-only, no key]
# Generates both plists into ~/Library/LaunchAgents with this repo absolute paths and your
# $FRED_API_KEY baked in (read from the environment; it is in your .zshrc, so run this from a normal
# terminal), then loads them. Re-run any time to update (idempotent). "install_schedules.sh uninstall"
# removes them. Override the port with IB_PORT=... (default 4002).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="$REPO/.venv/bin/python"
IB_PORT="${IB_PORT:-4002}"
LA="$HOME/Library/LaunchAgents"
REBAL_PLIST="$LA/com.fx.paper-rebalance.plist"
SNAP_PLIST="$LA/com.fx.nav-snapshot.plist"

if [ "${1:-}" = "uninstall" ]; then
  for pl in "$REBAL_PLIST" "$SNAP_PLIST"; do
    launchctl unload "$pl" 2>/dev/null || true
    rm -f "$pl" && echo "removed: $pl"
  done
  exit 0
fi

[ -x "$PY" ] || { echo "venv python not found at $PY — create the venv first" >&2; exit 1; }
: "${FRED_API_KEY:?set FRED_API_KEY in your environment before running this (it is in your .zshrc)}"
mkdir -p "$LA"

cat > "$REBAL_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.fx.paper-rebalance</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$REPO/scripts/monthly_paper_rebalance.sh</string></array>
  <key>EnvironmentVariables</key>
  <dict><key>FRED_API_KEY</key><string>$FRED_API_KEY</string><key>IB_PORT</key><string>$IB_PORT</string></dict>
  <key>StartCalendarInterval</key><dict><key>Day</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardErrorPath</key><string>$REPO/launchd.err</string>
</dict></plist>
EOF
chmod 600 "$REBAL_PLIST"          # contains the FRED key -> owner-only

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

for pl in "$REBAL_PLIST" "$SNAP_PLIST"; do
  launchctl unload "$pl" 2>/dev/null || true    # unload-first so re-running updates cleanly
  launchctl load "$pl"
  echo "loaded: $(basename "$pl")"
done
echo "installed. monthly rebalance = 1st 09:00 ; daily NAV snapshot = 21:00 ; port=$IB_PORT"
echo "verify:  launchctl list | grep com.fx"
echo "remove:  $0 uninstall"

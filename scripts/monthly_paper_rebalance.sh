#!/usr/bin/env bash
# Monthly forward paper-track rebalance of the deployable carry book on the IBKR PAPER account.
# It PLACES REAL PAPER ORDERS via the validated CLI path (reconciles: only trades when the target moves).
#
# REQUIRES at fire time:
#   - IB Gateway (recommended: headless + always-on + auto-restart) OR TWS, logged into the PAPER account,
#     API enabled, on $IB_PORT. Gateway is strongly preferred for unattended runs — TWS auto-restarts
#     daily and needs a re-login, so a monthly cron against TWS will often find it down.
#   - FRED_API_KEY in the environment (to refresh rates so the target is current).
#   - The project venv.
# Safety: --confirm (arms placement), --max-order-frac 0.4 (per-order cap; 3/3 legs are 33%),
#   and LiveExecution's DU-paper-account guard (refuses a live account without allow_live).
# Appends each run to track.log — that file (+ the IBKR paper statements) is your forward record.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

IB_PORT="${IB_PORT:-4002}"          # Gateway paper=4002 ; TWS paper=7497
G10="EUR,JPY,GBP,CHF,AUD,NZD,CAD,NOK,SEK"
UNIVERSE="$G10,MXN,ZAR"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
  echo "=== $STAMP  monthly paper rebalance (port $IB_PORT) ==="
  forex download                                    # refresh FRED rates (needs FRED_API_KEY)
  forex dryrun --strategy carry --universe "$UNIVERSE" --broker ib --ib-port "$IB_PORT" \
      --confirm --max-order-frac 0.4
  echo "--- done $STAMP ---"
} >> track.log 2>&1

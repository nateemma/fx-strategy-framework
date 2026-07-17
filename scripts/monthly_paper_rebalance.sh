#!/usr/bin/env bash
# Monthly forward paper-track rebalance of the deployable book (carry_cot_mom) on the IBKR PAPER account.
# It PLACES REAL PAPER ORDERS via the validated CLI path (reconciles: only trades when the target moves).
#
# REQUIRES at fire time:
#   - IB Gateway (recommended: headless + always-on + auto-restart) OR TWS, logged into the PAPER account,
#     API enabled (Read-Only API OFF, so placement is allowed), on $IB_PORT. Gateway is strongly preferred
#     for unattended runs — TWS auto-restarts daily and needs a re-login.
#   - FRED_API_KEY in the environment (to refresh the 3-month rates).
#   - The project venv.
# Data: carry_cot_mom pulls THREE sources — IBKR daily spot, FRED rates, CFTC COT — refreshed by
#   refresh_track_data.py (each independently; a stale source falls back to last-good cache + logs it).
# Safety: --confirm (arms placement) + LiveExecution guards (DU-paper-account check, per-order/gross caps,
#   min-order skip, pre-trade odd-lot warning). The diffuse 3-sleeve book's largest leg is ~12% of NAV, so
#   the default 0.25 per-order cap is not binding (no --max-order-frac override needed).
# Appends each run to track.log — that file (+ the IBKR paper statements) is your forward record.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

IB_PORT="${IB_PORT:-4002}"          # Gateway paper=4002 ; TWS paper=7497
export IB_PORT
UNIVERSE="EUR,JPY,GBP,CHF,AUD,NZD,CAD,NOK,SEK,MXN,ZAR,PLN,HUF,CZK,ILS"   # deliverable EM-inclusive book
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
  echo "=== $STAMP  monthly paper rebalance: carry_cot_mom (port $IB_PORT) ==="
  python scripts/refresh_track_data.py              # IBKR spot + FRED rates + CFTC COT
  forex dryrun --strategy carry_cot_mom --universe "$UNIVERSE" --broker ib --ib-port "$IB_PORT" --confirm
  echo "--- done $STAMP ---"
} >> track.log 2>&1

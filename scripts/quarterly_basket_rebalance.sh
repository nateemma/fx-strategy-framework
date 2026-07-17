#!/usr/bin/env bash
# Quarterly forward paper-track rebalance of the ETF BASKET sleeve (SPY/TLT/IEF/GLD/DBC, inverse-vol, $400k)
# on the IBKR PAPER account. It PLACES REAL PAPER ORDERS via the validated CLI (reconciles: only trades the
# diff from current positions — no over-trade on re-run).
#
# REQUIRES at fire time:
#   - IB Gateway (recommended: headless + always-on) OR TWS, logged into the PAPER account, API enabled
#     (Read-Only API OFF, so placement is allowed), on $IB_PORT. Gateway strongly preferred for unattended.
#   - The project venv. NO FRED key needed (the basket uses IBKR historical bars only).
# Safety: --confirm arms placement + BasketExecution guards (DU-paper-account check, per-order-cap pre-pass,
#   min-order skip, reconcile-by-conId anti-overtrade, best-effort rollback). Client id 24 (FX book uses 23).
# Appends each run to basket.log — that file (+ basket_positions.csv + IBKR paper statements) is the record.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

IB_PORT="${IB_PORT:-4002}"          # Gateway paper=4002 ; TWS paper=7497
export IB_PORT
ALLOCATION="${BASKET_ALLOCATION:-400000}"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
  echo "=== $STAMP  quarterly basket rebalance: SPY/TLT/IEF/GLD/DBC \$${ALLOCATION} (port $IB_PORT) ==="
  python scripts/basket_rebalance.py --confirm --allocation "$ALLOCATION" --port "$IB_PORT"
  echo "--- done $STAMP ---"
} 2>&1 | tee -a basket.log

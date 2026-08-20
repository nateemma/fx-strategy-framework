#!/usr/bin/env bash
# Quarterly rebalance of ALL FOUR ETF sleeves on the IBKR PAPER account. PLACES REAL PAPER ORDERS via
# the validated BasketExecution path (reconciles by conId: an unchanged target trades nothing).
#
#   basket  SPY/TLT/IEF/GLD/DBC  inverse-vol      client 24
#   ladder  IBTG..IBTL           equal-weight     client 27
#   income  BIZD/JEPI            equal-weight     client 28
#   cash    SGOV                 the residual     client 26   <- runs LAST, it soaks up what is left
#
# Allocations default to what is actually deployed, NOT to aspirational figures. They sum to ~$951k
# against ~$1,007k NAV, leaving a small USD buffer. The basket was trimmed 298k -> 268k on 2026-08-20
# to fund the VIX carry sleeve ($30k, daily agent com.fx.vix-carry — NOT part of this quarterly job). Raising one without lowering another pushes the
# ETF book above NAV and funds the difference by borrowing at BM+1.5% — see
# docs/financing-spread-findings.md for why that is expensive.
#
# REQUIRES: IB Gateway on $IB_PORT logged into the PAPER account, API enabled (Read-Only OFF).
#   No FRED key — these sleeves use IBKR historical bars only.
# Sleeve symbols MUST stay disjoint: reconcile is by conId against the whole account and cannot tell
#   one sleeve's IEF from another's.
# A failing sleeve does not stop the others; the script exits non-zero if any failed, and the
#   healthcheck sees that sleeve's CSV go stale.
set -uo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

IB_PORT="${IB_PORT:-4002}"
export IB_PORT
BASKET_ALLOCATION="${BASKET_ALLOCATION:-268000}"   # trimmed 2026-08-20 to fund the VIX sleeve
LADDER_ALLOCATION="${LADDER_ALLOCATION:-300000}"
INCOME_ALLOCATION="${INCOME_ALLOCATION:-298000}"
CASH_ALLOCATION="${CASH_ALLOCATION:-85000}"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
failed=0

run_sleeve() {           # name, script, allocation
  echo "--- $1: \$$3 ---"
  if python "scripts/$2" --confirm --allocation "$3" --port "$IB_PORT"; then
    echo "--- $1 ok ---"
  else
    echo "!!! $1 FAILED (exit $?) — other sleeves continue !!!"
    failed=1
  fi
}

{
  echo "=== $STAMP  quarterly sleeve rebalance (port $IB_PORT) ==="
  run_sleeve basket basket_rebalance.py "$BASKET_ALLOCATION"
  run_sleeve ladder bond_ladder.py      "$LADDER_ALLOCATION"
  run_sleeve income income_sleeve.py    "$INCOME_ALLOCATION"
  run_sleeve cash   cash_sleeve.py      "$CASH_ALLOCATION"   # last: it is the residual
  echo "--- done $STAMP (failed=$failed) ---"
} 2>&1 | tee -a basket.log

exit "$failed"

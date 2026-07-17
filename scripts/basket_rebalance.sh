#!/usr/bin/env bash
# Quarterly rebalance of the ETF risk-parity basket sleeve (SPY/TLT/IEF/GLD/DBC, $400k allocation).
# PLACES REAL PAPER ORDERS via the validated CLI path on the IBKR PAPER account.
#
# REQUIRES at run time:
#   - IB Gateway (recommended: headless + always-on) logged into the PAPER account,
#     API enabled (Read-Only API OFF), on $IB_PORT (default 4002).
#   - The project venv.
# Coexists with the FX book (carry_cot_mom) in the same paper account: ETFs use cash, FX uses margin.
# Per-sleeve position logging appends to basket_positions.csv; whole-account NAV is tracked by snapshot_nav.py.
# Safety: --confirm (arms placement) + BasketExecution guards (DU-paper-account check, per-order/gross caps).

set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate

IB_PORT="${IB_PORT:-4002}"
export IB_PORT

python scripts/basket_rebalance.py "$@"

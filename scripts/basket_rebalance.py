#!/usr/bin/env python
"""Rebalance the ETF risk-parity basket sleeve on IBKR paper account."""

import argparse
import os
from datetime import datetime, timezone

from forex.run.basket import BasketExecution
from forex.run.basket_track import log_basket_positions


def main():
    parser = argparse.ArgumentParser(
        description="Rebalance the ETF risk-parity basket (SPY/TLT/IEF/GLD/DBC) on IBKR"
    )
    parser.add_argument("--allocation", type=float, default=400000.0,
                        help="Allocation in USD (default 400000)")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirm and place orders (default: preview mode)")
    parser.add_argument("--port", type=int, default=4002,
                        help="IB Gateway port (default 4002)")
    parser.add_argument("--client-id", type=int, default=24,
                        help="IB client ID (default 24)")
    parser.add_argument("--allow-live", action="store_true",
                        help="Allow placement on live accounts (not recommended)")
    parser.add_argument("--account", type=str,
                        default=os.environ.get("FOREX_IB_ACCOUNT", "DUQ218063"),
                        help="IB account identifier")
    parser.add_argument("--csv", type=str, default="basket_positions.csv",
                        help="CSV file for position logging (default basket_positions.csv)")

    args = parser.parse_args()

    preview = not args.confirm  # Default to preview; --confirm arms placement

    exec_obj = BasketExecution(
        host="127.0.0.1",
        port=args.port,
        client_id=args.client_id,
        preview=preview,
        confirm=args.confirm,
        allow_live=args.allow_live,
    )

    print(f"Rebalancing basket: allocation=${args.allocation:,.0f} "
          f"(account {args.account}, {'PREVIEW' if preview else 'PLACEMENT'})")

    report = exec_obj.rebalance(args.allocation)

    # Print summary
    print(f"  NAV: ${report.equity:,.2f}")
    print(f"  Weights: {dict(sorted(report.weights.items()))}")
    print(f"  Target positions: {dict(sorted(report.positions.items()))}")
    if report.orders:
        print(f"  Orders: {dict(sorted(report.orders.items()))}")
    if report.skipped:
        print(f"  Skipped (below min_order_usd): {dict(sorted(report.skipped.items()))}")
    print(f"  Applied: {report.applied}, Complete: {report.complete}")

    # Log to CSV if applied
    if report.applied:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log_basket_positions(report, args.csv, timestamp, args.account)
        print(f"  Position snapshot logged to {args.csv}")


if __name__ == "__main__":
    main()

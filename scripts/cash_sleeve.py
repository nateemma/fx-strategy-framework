#!/usr/bin/env python
"""Park the cash buffer in a short-Treasury ETF (default SGOV) on the IBKR account.

The income design's cash sleeve should sit in SGOV (~4.3%, state-tax-exempt, auto-rolling, liquid) rather
than idle cash. This reuses BasketExecution (a single symbol gets weight 1.0), so all its safety guards apply
(DU-account check, per-order cap, min-order skip, reconcile-by-conId, rollback). Default is PREVIEW; --confirm
arms placement. Client id 26 (FX=23, basket=24; keep distinct so sleeves can coexist).

Note: real cash/lending yield only accrues on a REAL account — on the paper account this places/tracks the
SGOV position but the income is simulated. See docs/income-enhancements.md.
"""

import argparse
import os
from datetime import datetime, timezone

from forex.run.basket import BasketExecution
from forex.run.basket_track import log_basket_positions


def main():
    parser = argparse.ArgumentParser(
        description="Park the cash buffer in a short-Treasury ETF (default SGOV) on IBKR"
    )
    parser.add_argument("--allocation", type=float, required=True,
                        help="USD to hold in the cash ETF (required)")
    parser.add_argument("--symbol", type=str, default="SGOV",
                        help="Cash ETF symbol (default SGOV)")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirm and place orders (default: preview mode)")
    parser.add_argument("--port", type=int, default=4002,
                        help="IB Gateway port (default 4002)")
    parser.add_argument("--client-id", type=int, default=26,
                        help="IB client ID (default 26)")
    parser.add_argument("--allow-live", action="store_true",
                        help="Allow placement on live accounts (not recommended)")
    parser.add_argument("--account", type=str,
                        default=os.environ.get("FOREX_IB_ACCOUNT", "DUQ218063"),
                        help="IB account identifier")
    parser.add_argument("--csv", type=str, default="cash_positions.csv",
                        help="CSV file for position logging (default cash_positions.csv)")

    args = parser.parse_args()

    preview = not args.confirm  # Default to preview; --confirm arms placement

    exec_obj = BasketExecution(
        symbols=[args.symbol],
        host="127.0.0.1",
        port=args.port,
        client_id=args.client_id,
        preview=preview,
        confirm=args.confirm,
        allow_live=args.allow_live,
    )

    print(f"Cash sleeve: hold ${args.allocation:,.0f} of {args.symbol} "
          f"(account {args.account}, {'PREVIEW' if preview else 'PLACEMENT'})")

    report = exec_obj.rebalance(args.allocation)

    print(f"  NAV: ${report.equity:,.2f}")
    print(f"  Target position: {dict(sorted(report.positions.items()))}")
    if report.orders:
        print(f"  Orders: {dict(sorted(report.orders.items()))}")
    if report.skipped:
        print(f"  Skipped (below min_order_usd): {dict(sorted(report.skipped.items()))}")
    print(f"  Applied: {report.applied}, Complete: {report.complete}")

    if report.applied:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log_basket_positions(report, args.csv, timestamp, report.account or args.account)
        print(f"  Position snapshot logged to {args.csv}")


if __name__ == "__main__":
    main()

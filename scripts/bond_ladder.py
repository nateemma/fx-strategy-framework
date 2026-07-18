#!/usr/bin/env python
"""Hold an EQUAL-WEIGHT Treasury bond ladder on the IBKR account.

A bond ladder = equal exposure across staggered maturities. Proxy it with constant-maturity Treasury ETFs
(default SHY 1-3y / IEI 3-7y / IEF 7-10y ~= a 1-10y ladder), or pass defined-maturity iBonds
(--symbols IBTF,IBTG,IBTH,IBTI,IBTJ,IBTK,IBTL,IBTM) for a true ladder that returns principal at each rung.
Reuses BasketExecution with equal_weight=True (equal rung exposure, not inverse-vol) so all its guards apply.
Default PREVIEW; --confirm arms placement. client_id 27 (FX=23, basket=24, cash=26). Real yield only on a
real account. See scratchpad bond_ladder.py for the performance study.
"""

import argparse
import os
from datetime import datetime, timezone

from forex.run.basket import BasketExecution
from forex.run.basket_track import log_basket_positions


def main():
    parser = argparse.ArgumentParser(description="Hold an equal-weight Treasury bond ladder on IBKR")
    parser.add_argument("--allocation", type=float, required=True,
                        help="USD to hold across the ladder (required)")
    parser.add_argument("--symbols", type=str, default="SHY,IEI,IEF",
                        help="Comma-separated ladder ETFs (default SHY,IEI,IEF ~ 1-10y)")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirm and place orders (default: preview mode)")
    parser.add_argument("--port", type=int, default=4002, help="IB Gateway port (default 4002)")
    parser.add_argument("--client-id", type=int, default=27, help="IB client ID (default 27)")
    parser.add_argument("--allow-live", action="store_true",
                        help="Allow placement on live accounts (not recommended)")
    parser.add_argument("--account", type=str,
                        default=os.environ.get("FOREX_IB_ACCOUNT", "DUQ218063"),
                        help="IB account identifier")
    parser.add_argument("--csv", type=str, default="bond_ladder_positions.csv",
                        help="CSV file for position logging")

    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    preview = not args.confirm

    exec_obj = BasketExecution(
        symbols=symbols,
        host="127.0.0.1",
        port=args.port,
        client_id=args.client_id,
        preview=preview,
        confirm=args.confirm,
        allow_live=args.allow_live,
        equal_weight=True,
    )

    print(f"Bond ladder: hold ${args.allocation:,.0f} equal-weight across {symbols} "
          f"(account {args.account}, {'PREVIEW' if preview else 'PLACEMENT'})")

    report = exec_obj.rebalance(args.allocation)

    print(f"  NAV: ${report.equity:,.2f}")
    print(f"  Weights: {dict(sorted(report.weights.items()))}")
    print(f"  Target positions: {dict(sorted(report.positions.items()))}")
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

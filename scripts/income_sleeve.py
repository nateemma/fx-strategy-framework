#!/usr/bin/env python
"""Hold an equal-weight income sleeve (default ½ BIZD BDC + ½ JEPI covered-call) on the IBKR account.

The measured high-yield sleeve of the diversified income book — it supplies the cash yield (~9%), while the
FX carry + basket (Treasuries/gold) anchor cushions its equity/credit crash risk. Equal-weight via
BasketExecution(equal_weight=True), so all guards/reconcile/rollback apply. Default PREVIEW; --confirm arms.
client_id 28 (FX=23, basket=24, cash=26, ladder=27). Real yield only on a real account; this sleeve carries
real credit/equity risk (BDCs/covered-calls fell 30-50%+ in 2008) — sized small and anchored deliberately.
See scratchpad income_book.py for the sizing study.
"""

import argparse
import os
from datetime import datetime, timezone

from forex.run.basket import BasketExecution
from forex.run.basket_track import log_basket_positions


def main():
    parser = argparse.ArgumentParser(description="Hold an equal-weight income sleeve (BDC + covered-call) on IBKR")
    parser.add_argument("--allocation", type=float, required=True,
                        help="USD to hold across the income sleeve (required)")
    parser.add_argument("--symbols", type=str, default="BIZD,JEPI",
                        help="Comma-separated income ETFs (default BIZD,JEPI)")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirm and place orders (default: preview mode)")
    parser.add_argument("--port", type=int, default=4002, help="IB Gateway port (default 4002)")
    parser.add_argument("--client-id", type=int, default=28, help="IB client ID (default 28)")
    parser.add_argument("--allow-live", action="store_true",
                        help="Allow placement on live accounts (not recommended)")
    parser.add_argument("--account", type=str,
                        default=os.environ.get("FOREX_IB_ACCOUNT", "DUQ218063"),
                        help="IB account identifier")
    parser.add_argument("--csv", type=str, default="income_sleeve_positions.csv",
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

    print(f"Income sleeve: hold ${args.allocation:,.0f} equal-weight across {symbols} "
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

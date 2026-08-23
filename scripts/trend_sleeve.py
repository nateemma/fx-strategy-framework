#!/usr/bin/env python
"""Cross-asset trend sleeve on IBKR futures. Default is PREVIEW; --confirm arms placement.

Implements the A2 gate (docs/cross-asset-trend-findings.md): an eight-market trend book that is the
account's only equity-uncorrelated return source. Futures only — the same book in margined ETFs
returns less than cash once IBKR financing is charged.

    python scripts/trend_sleeve.py --risk-base 200000            # preview
    python scripts/trend_sleeve.py --risk-base 200000 --confirm  # place

REQUIRES a CME/CBOT/NYMEX market-data subscription. Without one IBKR returns a handful of bars
rather than an error, so the sleeve refuses to trade rather than acting on a meaningless signal.
"""
import argparse
import os
from datetime import date, datetime, timezone

import pandas as pd

from forex.run.futures import FuturesExecution
from forex.run.futures_roll import front_expiry
from forex.run.ibconnect import connect_with_retry
from strategies.trend_book import MIN_HISTORY, UNIVERSE, trend_targets


def fetch_history(port, client_id, asof, days=500):
    """Daily closes per market from the front contract. Read-only."""
    from ib_async import IB, Future
    ib = IB()
    connect_with_retry(ib, "127.0.0.1", port, client_id, readonly=True, timeout=25)
    try:
        series = {}
        for m in UNIVERSE:
            details = ib.reqContractDetails(Future(symbol=m.symbol, exchange=m.exchange,
                                                   currency="USD"))
            if not details:
                raise RuntimeError(f"no contracts for {m.symbol} on {m.exchange}")
            by_expiry = {datetime.strptime(d.contract.lastTradeDateOrContractMonth[:8],
                                           "%Y%m%d").date(): d.contract for d in details}
            front = front_expiry(by_expiry, asof) or sorted(by_expiry)[-1]
            bars = ib.reqHistoricalData(by_expiry[front], "", f"{days} D", "1 day",
                                        "TRADES", useRTH=True)
            series[m.symbol] = pd.Series({b.date: float(b.close) for b in bars})
            print(f"  {m.symbol:5s} {len(bars):>4d} bars")
        return pd.DataFrame(series).sort_index()
    finally:
        ib.disconnect()


def main():
    p = argparse.ArgumentParser(description="Cross-asset trend sleeve (IBKR futures)")
    p.add_argument("--risk-base", type=float, required=True,
                   help="notional capital the vol target is computed against (e.g. 200000)")
    p.add_argument("--confirm", action="store_true", help="arm placement (default: preview)")
    p.add_argument("--port", type=int, default=int(os.environ.get("IB_PORT", "4002")))
    p.add_argument("--client-id", type=int, default=29)
    p.add_argument("--allow-live", action="store_true")
    p.add_argument("--max-order-frac", type=float, default=0.5)
    p.add_argument("--min-available-funds", type=float, default=100_000.0)
    p.add_argument("--csv", type=str, default="trend_positions.csv")
    p.add_argument("--account", type=str, default=os.environ.get("FOREX_IB_ACCOUNT", "DUQ218063"))
    args = p.parse_args()

    asof = date.today()
    print(f"trend sleeve — risk base ${args.risk_base:,.0f}  "
          f"({'PLACEMENT' if args.confirm else 'PREVIEW'})\nfetching history:")
    prices = fetch_history(args.port, args.client_id + 50, asof)

    if len(prices) < MIN_HISTORY:
        raise SystemExit(
            f"\nREFUSING TO TRADE: only {len(prices)} bars, need {MIN_HISTORY}.\n"
            f"This is EXPECTED and is not a subscription problem (verified 2026-08-21/23: the\n"
            f"market-data entitlement is live and returns bars). History is fetched from the FRONT\n"
            f"MONTH only, so it is capped at that contract's own listed life — MESU6 tops out near\n"
            f"294 bars, M6EU6 near 110. No front contract can ever reach {MIN_HISTORY}. Running this\n"
            f"needs a stitched, back-adjusted continuous series (and data deep enough to stitch);\n"
            f"see docs/lean-data-gate.md. Zero bars across ALL markets usually means something else:\n"
            f"IBKR pacing (>60 historical requests/10min) or a competing login. Acting on a short\n"
            f"signal would be worse than not trading.")

    targets, diag = trend_targets(prices, {m.symbol: m.multiplier for m in UNIVERSE}, args.risk_base)

    print(f"\nas of {diag['asof']}   leverage {diag['leverage']:.2f}x   "
          f"gross notional ${diag['gross_notional']:,.0f}")
    print(f"{'market':7s} {'signal':>7s} {'weight':>8s} {'target':>7s} {'rounding':>9s}")
    for m in UNIVERSE:
        s = m.symbol
        print(f"{s:7s} {diag['signal'][s]:>+7.2f} {diag['weights'][s]:>+8.3f} "
              f"{targets[s]:>7d} {diag['rounding'][s]:>9.2f}")
    worst = max(diag["rounding"], key=diag["rounding"].get)
    print(f"  worst rounding error: {worst} at {diag['rounding'][worst]:.2f} contracts "
          f"— material at this risk base, reported rather than hidden")

    ex = FuturesExecution(
        markets=[(m.symbol, m.exchange, m.multiplier) for m in UNIVERSE],
        port=args.port, client_id=args.client_id, preview=not args.confirm, confirm=args.confirm,
        allow_live=args.allow_live, max_order_frac=args.max_order_frac,
        min_available_funds=args.min_available_funds)
    rep = ex.rebalance(targets, risk_base=args.risk_base, asof=asof)

    print(f"\nNAV ${rep.equity:,.0f}   orders {rep.orders or '(none — already at target)'}")
    if rep.rolled:
        print(f"  rolled: {', '.join(rep.rolled)}")
    print(f"  applied {rep.applied}   complete {rep.complete}")

    if rep.applied:
        from forex.run.basket_track import log_basket_positions
        from types import SimpleNamespace
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log_basket_positions(
            SimpleNamespace(positions=targets, weights=diag["weights"], allocation=args.risk_base,
                            applied=True, complete=rep.complete,
                            account=rep.account or args.account),
            args.csv, stamp, rep.account or args.account)
        print(f"  position snapshot -> {args.csv}")


if __name__ == "__main__":
    main()

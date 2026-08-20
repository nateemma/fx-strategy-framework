#!/usr/bin/env python
"""VIX carry satellite sleeve. Default is PREVIEW; --confirm arms placement.

Holds SVXY while the volatility curve is in contango, stands aside otherwise (A1 gate,
docs/vix-carry-findings.md). Long-only cash ETF — no margin, no borrow, so the ~2%/yr financing drag
that killed the FX book does not apply.

    python scripts/vix_carry_sleeve.py --allocation 50000            # preview
    python scripts/vix_carry_sleeve.py --allocation 50000 --confirm  # place

NOT a diversifier: +0.58 to SPY, and it loses on the book's worst days. Size for the tail the
instrument has never seen — its predecessor lost 83% in one day, and the contango gate is an
improvement, not a tail guard.
"""
import argparse
import os
from datetime import date, datetime, timezone

from forex.run.basket import BasketExecution
from strategies.vix_carry import vix_carry_target

VIX_SERIES, VIX3M_SERIES = "VIXCLS", "VXVCLS"


def load(series_id, cache_dir, refresh=True):
    """Fetch the series, refreshing from FRED by default.

    A daily sleeve must act on a current curve. Reading a stale cache would trip the staleness
    guard — correct behaviour, but for the wrong reason: the guard exists for when FRED itself is
    behind, not for when we simply did not ask.
    """
    from pathlib import Path
    from forex.data.fred import load_series
    try:
        return load_series(series_id, cache_dir=Path(cache_dir), force=refresh)
    except Exception as exc:                 # network/API failure -> fall back to cache, let the
        print(f"  (refresh of {series_id} failed: {type(exc).__name__}; using cache)")
        return load_series(series_id, cache_dir=Path(cache_dir))


def main():
    p = argparse.ArgumentParser(description="VIX carry satellite sleeve (SVXY, contango-gated)")
    p.add_argument("--allocation", type=float, required=True,
                   help="USD held when in the trade (0 when the curve is in backwardation)")
    p.add_argument("--symbol", default="SVXY")
    p.add_argument("--confirm", action="store_true", help="arm placement (default: preview)")
    p.add_argument("--port", type=int, default=int(os.environ.get("IB_PORT", "4002")))
    p.add_argument("--client-id", type=int, default=31)
    p.add_argument("--allow-live", action="store_true")
    p.add_argument("--cache-dir", default=os.environ.get("FOREX_DATA_CACHE", "data_cache"))
    p.add_argument("--csv", default="vix_carry_positions.csv")
    p.add_argument("--account", default=os.environ.get("FOREX_IB_ACCOUNT", "DUQ218063"))
    args = p.parse_args()

    vix, vix3m = load(VIX_SERIES, args.cache_dir), load(VIX3M_SERIES, args.cache_dir)
    t = vix_carry_target(vix, vix3m, args.allocation, asof=date.today())

    state = "IN CONTANGO -> hold" if t.in_trade else "BACKWARDATION -> stand aside"
    print(f"VIX carry sleeve ({'PLACEMENT' if args.confirm else 'PREVIEW'})")
    print(f"  term structure {t.asof}:  VIX {t.vix:.2f}   VIX3M {t.vix3m:.2f}   "
          f"contango {t.contango:+.1%}")
    print(f"  {state}   target ${t.allocation:,.0f} of {args.symbol}")

    ex = BasketExecution(
        symbols=[args.symbol], port=args.port, client_id=args.client_id,
        preview=not args.confirm, confirm=args.confirm, allow_live=args.allow_live,
        # A single-symbol sleeve is 100% of its allocation by definition. The default 0.6 cap made
        # the cash sleeve literally unplaceable until it was fixed; same trap, fixed deliberately.
        max_order_frac=1.0)
    rep = ex.rebalance(t.allocation)

    print(f"  NAV ${rep.equity:,.0f}   orders {rep.orders or '(none — already correct)'}")
    print(f"  applied {rep.applied}   complete {rep.complete}")

    if rep.applied:
        from types import SimpleNamespace
        from forex.run.basket_track import log_basket_positions
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        log_basket_positions(
            SimpleNamespace(positions=rep.positions, weights=rep.weights,
                            allocation=t.allocation, applied=True, complete=rep.complete,
                            account=rep.account or args.account),
            args.csv, stamp, rep.account or args.account)
        print(f"  position snapshot -> {args.csv}")


if __name__ == "__main__":
    main()

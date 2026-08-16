"""Snapshot the IBKR paper account's equity (NAV + the FX book) to nav.csv.
Run DAILY (cron/launchd) to build the forward equity curve for track_report.py. Read-only.

NAV mixes the FX book with the ETF sleeves, which are ~90% of it, so NAV alone measures the sleeves
rather than the strategy. `fx_net_base` isolates the FX book: ETF trades move only base-currency
cash and leave it untouched, so its change between snapshots is FX-only P&L — except on a day the
book was rebalanced, when it also carries that day's net flow.

`stock_positions` is the ETF sleeve holding count. It is NOT the FX leg count: settled FX spot lives
in CashBalance, never in positions() (see forex/run/fxbook.py). It was called `open_legs` until
2026-08-16 and was mistaken for the FX legs.
"""
import csv, os
from pathlib import Path
from datetime import datetime, timezone
from ib_async import IB
from forex.run.ibconnect import connect_with_retry
from forex.run.fxbook import fx_book

FIELDS = ["timestamp", "account", "nav", "unrealized_pnl", "realized_pnl", "stock_positions",
          "fx_legs", "fx_net_base", "fx_gross_base", "fx_accrued_base"]

port = int(os.environ.get("IB_PORT", "4002"))
ib = IB()
connect_with_retry(ib, "127.0.0.1", port, 94, readonly=True, timeout=20)
try:
    summ = {v.tag: v.value for v in ib.accountSummary()}
    acct = (ib.managedAccounts() or [""])[0]
    book = fx_book(ib.accountValues())
    ib.reqPositions(); ib.sleep(1.0)
    n_stk = sum(1 for p in ib.positions() if abs(p.position) > 1e-6)   # ETF sleeves; FX is cash
finally:
    ib.disconnect()

def g(tag):
    try:
        return float(summ.get(tag, "nan"))
    except (TypeError, ValueError):
        return float("nan")

p = Path("nav.csv")
prev_net = None
if p.exists():
    with p.open() as f:
        rows = list(csv.DictReader(f))
    if rows:
        try:
            prev_net = float(rows[-1]["fx_net_base"])
        except (KeyError, ValueError, TypeError):
            prev_net = None                       # first run after the schema change

stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
row = {
    "timestamp": stamp, "account": acct,
    "nav": g("NetLiquidation"), "unrealized_pnl": g("UnrealizedPnL"), "realized_pnl": g("RealizedPnL"),
    "stock_positions": n_stk, "fx_legs": book.legs,
    "fx_net_base": round(book.net_base, 2), "fx_gross_base": round(book.gross_base, 2),
    "fx_accrued_base": round(book.accrued_base, 2),
}
new = not p.exists()
with p.open("a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new:
        w.writeheader()
    w.writerow(row)

fx_pnl = "n/a (no prior snapshot)" if prev_net is None else f"{book.net_base - prev_net:+,.0f}"
print(f"{stamp}  NAV={row['nav']:,.0f}  stocks={n_stk}  fx_legs={book.legs}  "
      f"fx_gross={book.gross_base:,.0f}  fx_net={book.net_base:,.0f}  fx_pnl={fx_pnl}  -> nav.csv")

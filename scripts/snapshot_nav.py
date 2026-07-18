"""Snapshot the IBKR paper account's equity (NAV + P&L + gross exposure) to nav.csv.
Run DAILY (cron/launchd) to build the forward equity curve for track_report.py. Read-only."""
import csv, os
from pathlib import Path
from datetime import datetime, timezone
from ib_async import IB
from forex.run.ibconnect import connect_with_retry

port = int(os.environ.get("IB_PORT", "4002"))
ib = IB()
connect_with_retry(ib, "127.0.0.1", port, 94, readonly=True, timeout=20)
try:
    summ = {v.tag: v.value for v in ib.accountSummary()}
    acct = (ib.managedAccounts() or [""])[0]
    ib.reqPositions(); ib.sleep(1.0)
    n_pos = sum(1 for p in ib.positions() if abs(p.position) > 1e-6)   # open FX legs (FX = cash, so gross=0)
finally:
    ib.disconnect()

def g(tag):
    try:
        return float(summ.get(tag, "nan"))
    except (TypeError, ValueError):
        return float("nan")

stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
row = [stamp, acct, g("NetLiquidation"), g("UnrealizedPnL"), g("RealizedPnL"), n_pos]
p = Path("nav.csv"); new = not p.exists()
with p.open("a", newline="") as f:
    w = csv.writer(f)
    if new:
        w.writerow(["timestamp", "account", "nav", "unrealized_pnl", "realized_pnl", "open_legs"])
    w.writerow(row)
print(f"{stamp}  NAV={row[2]:,.0f}  unrealizedPnL={row[3]:,.0f}  open_legs={n_pos}  -> nav.csv")

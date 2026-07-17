"""Performance report for the forward paper track: reads nav.csv (from snapshot_nav.py) and prints
since-inception return / vol / Sharpe / drawdown, vs the backtest expectation. Run on demand."""
import sys
import numpy as np, pandas as pd
from pathlib import Path

p = Path("nav.csv")
if not p.exists():
    sys.exit("no nav.csv yet — run scripts/snapshot_nav.py (daily) to build the equity curve first")
df = pd.read_csv(p, parse_dates=["timestamp"]).sort_values("timestamp")
nav = df.set_index("timestamp")["nav"].dropna()
navd = nav.resample("D").last().dropna()          # one point per day (last snapshot of the day)

print(f"forward paper track — carry_cot_mom  ({df.account.iloc[-1]})")
print(f"snapshots: {len(nav)} over {navd.index[0].date()} -> {navd.index[-1].date()}  ({len(navd)} days)")
print(f"NAV: {navd.iloc[0]:,.0f} -> {navd.iloc[-1]:,.0f}")

if len(navd) < 3:
    print("\n(need >=3 daily snapshots for return/Sharpe/drawdown stats — check back after a few days)")
    sys.exit(0)

ret = navd.pct_change().dropna()
total = navd.iloc[-1] / navd.iloc[0] - 1
days = max(1, (navd.index[-1] - navd.index[0]).days)
ann = (1 + total) ** (365 / days) - 1
vol = ret.std() * np.sqrt(252)
sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() else float("nan")
eq = navd / navd.iloc[0]; dd = (eq / eq.cummax() - 1).min()

print(f"\nsince inception ({days} days):")
print(f"  total return : {total:+.2%}")
print(f"  annualized   : {ann:+.1%}")
print(f"  vol (ann)    : {vol:.1%}")
print(f"  Sharpe       : {sharpe:.2f}")
print(f"  max drawdown : {dd:.1%}")
print("\nbacktest expectation (walk-forward): Sharpe ~1.15; unlevered ~3%/yr at ~2.6% vol,")
print("  ~8-10%/yr levered to 10% vol. Judge on Sharpe vs 1.15 once the sample is meaningful (months).")

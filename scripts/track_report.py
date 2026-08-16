"""Performance report for the forward paper track: reads nav.csv (from snapshot_nav.py) and prints
since-inception return / vol / Sharpe / drawdown, vs the backtest expectation. Run on demand.

Two sections. WHOLE ACCOUNT covers everything in the account, which is mostly the ETF sleeves.
FX BOOK ONLY isolates carry_cot_mom from its recorded values, so the deployed strategy can be judged
against its walk-forward expectation rather than against the sleeves. Read-only; no broker needed."""
import csv
import sys
import numpy as np, pandas as pd
from pathlib import Path

from forex.run.fxtrack import MIN_OBS_STATS, fx_performance

p = Path("nav.csv")
if not p.exists():
    sys.exit("no nav.csv yet — run scripts/snapshot_nav.py (daily) to build the equity curve first")
df = pd.read_csv(p, parse_dates=["timestamp"]).sort_values("timestamp")
nav = df.set_index("timestamp")["nav"].dropna()
navd = nav.resample("D").last().dropna()          # one point per day (last snapshot of the day)

print(f"forward paper track — carry_cot_mom  ({df.account.iloc[-1]})")

print("\nWHOLE ACCOUNT  (FX book + ETF sleeves)")
print(f"  snapshots    : {len(nav)} over {navd.index[0].date()} -> {navd.index[-1].date()}  ({len(navd)} days)")
print(f"  NAV          : {navd.iloc[0]:,.0f} -> {navd.iloc[-1]:,.0f}")

if len(navd) < 3:
    print("  (need >=3 daily snapshots for return/Sharpe/drawdown stats — check back after a few days)")
else:
    ret = navd.pct_change().dropna()
    total = navd.iloc[-1] / navd.iloc[0] - 1
    days = max(1, (navd.index[-1] - navd.index[0]).days)
    ann = (1 + total) ** (365 / days) - 1
    vol = ret.std() * np.sqrt(252)
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() else float("nan")
    eq = navd / navd.iloc[0]; dd = (eq / eq.cummax() - 1).min()
    print(f"  total return : {total:+.2%}")
    print(f"  annualized   : {ann:+.1%}")
    print(f"  vol (ann)    : {vol:.1%}")
    print(f"  Sharpe       : {sharpe:.2f}")
    print(f"  max drawdown : {dd:.1%}")
print("  note: the ETF sleeves dominate account value, so these figures mostly measure them,")
print("        not the FX strategy. Judge carry_cot_mom on the FX section below.")

with p.open() as f:
    fx = fx_performance(list(csv.DictReader(f)))

print("\nFX BOOK ONLY  (carry_cot_mom)")
if fx.n_fx_days == 0:
    print("  unavailable — no snapshot in this history records FX values.")
    print("  FX columns were added 2026-08-16; earlier rows cannot be reconstructed.")
else:
    snaps = "snapshot" if fx.n_fx_days == 1 else "snapshots"
    print(f"  observations : {fx.n_fx_days} FX {snaps} over {fx.period_start} -> {fx.period_end}")
    print(f"  net value    : {fx.net_base:,.0f}   gross exposure: {fx.gross_base:,.0f}   "
          f"accrued: {fx.accrued_base:,.0f}")

if fx.n_fx_days == 1:
    print("  P&L needs at least 2 observations to difference — not shown.")
elif fx.n_fx_days > 1:
    print(f"  P&L          : {fx.total_pnl:+,.0f}   (carry {fx.carry_pnl:+,.0f}  +  spot {fx.spot_pnl:+,.0f})")
    if fx.n_excluded:
        print(f"  excluded     : {fx.n_excluded} observation(s) carrying rebalance flow or spanning a curve gap")
    if fx.n_carry_estimated:
        print(f"  estimated    : {fx.n_carry_estimated} observation(s) where interest posted — "
              f"carry estimated from recent days, not measured")
    if fx.sharpe is None:
        if fx.n_obs < MIN_OBS_STATS:
            print(f"  return / vol / Sharpe / drawdown need >= {MIN_OBS_STATS} observations "
                  f"(have {fx.n_obs}) — not shown.")
        else:
            print("  Sharpe undefined — the return series has no variation.")
    else:
        print(f"  total return : {fx.total_return:+.2%}   (on gross FX exposure)")
        print(f"  annualized   : {fx.ann_return:+.1%}")
        print(f"  vol (ann)    : {fx.ann_vol:.1%}")
        print(f"  Sharpe       : {fx.sharpe:.2f}   [{fx.n_obs} observations]")
        print(f"  max drawdown : {fx.max_drawdown:.1%}")
        print("\n  backtest expectation (walk-forward): Sharpe ~1.15; unlevered ~3%/yr at ~2.6% vol.")
        print("  Judge on Sharpe vs 1.15 once the sample is months, not days.")

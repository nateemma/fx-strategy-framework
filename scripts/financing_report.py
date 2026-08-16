"""Compare what the account actually accrues per currency against the benchmark the backtest assumes.

The backtest accrues the full FRED interbank differential with no broker financing spread. This
measures the difference. Read-only; needs IB Gateway up and the cached FRED rates.

    .venv/bin/python scripts/financing_report.py
"""
import os

from ib_async import IB

from forex.config import CURRENCIES
from forex.run.financing import MIN_ABS_BENCHMARK, benchmark_rate, financing_summary
from forex.run.ibconnect import connect_with_retry

# Accrual since IBKR last posted interest is not observable from a snapshot. Interest posts monthly,
# so the elapsed window is somewhere between a few days and a full month — report the range.
PERIOD_RANGE = {"2 weeks": 14 / 365.0, "3 weeks": 21 / 365.0, "1 month": 30 / 365.0}


port = int(os.environ.get("IB_PORT", "4002"))
ib = IB()
connect_with_retry(ib, "127.0.0.1", port, 81, readonly=True, timeout=20)
try:
    acct = (ib.managedAccounts() or [""])[0]
    tags = {}
    for v in ib.accountValues():
        tags.setdefault(v.tag, {})[v.currency] = v.value
finally:
    ib.disconnect()


def val(tag, ccy):
    try:
        return float(tags.get(tag, {}).get(ccy, 0) or 0)
    except ValueError:
        return 0.0


legs = []
for ccy in sorted(tags.get("CashBalance", {})):
    if ccy in ("BASE", "USD") or ccy not in CURRENCIES:
        continue
    bal, rate = val("CashBalance", ccy), val("ExchangeRate", ccy)
    if not bal or not rate:
        continue
    bench, asof = benchmark_rate(ccy)
    if bench is None:
        print(f"  (no cached benchmark for {ccy} — skipped)")
        continue
    legs.append({"ccy": ccy, "balance": bal, "accrued": val("AccruedCash", ccy),
                 "rate": rate, "benchmark": bench, "asof": asof})

s = financing_summary(legs)

print(f"financing diagnosis — {acct}\n")
print(f"{'ccy':5s} {'side':6s} {'USD exposure':>14s} {'accrued':>10s} {'bench':>7s} "
      f"{'as-of':>11s} {'realised/bench':>15s}")
for r in sorted(s.ratios, key=lambda r: (r.side, r.ratio if r.ratio is not None else 0)):
    flag = ""
    if abs(r.benchmark) < MIN_ABS_BENCHMARK:
        flag = "  (excluded: benchmark ~0)"
    elif r not in s.ratios_used:
        flag = "  (excluded: negligible)"
    ratio = "n/a" if r.ratio is None else f"{r.ratio:.4f}"
    print(f"{r.ccy:5s} {r.side:6s} {r.usd:>14,.0f} {r.accrued_usd:>10,.2f} "
          f"{r.benchmark * 100:>6.2f}% {r.asof:>11s} {ratio:>15s}{flag}")

print("\nThe ratio is (accrued/balance) / benchmark. Every leg shares one accrual window, so the")
print("window cancels: if financing were at benchmark, every ratio would be the same number.")
print(f"\n  LONG  median : {s.long_median:.4f}" if s.long_median is not None else "\n  LONG  median : n/a")
print(f"  SHORT median : {s.short_median:.4f}" if s.short_median is not None else "  SHORT median : n/a")
if s.asymmetry:
    print(f"  asymmetry    : {s.asymmetry:.1f}x  (shorts charged this much more, relative to benchmark)")
print(f"  excluded     : {s.n_excluded_near_zero} near-zero benchmark, {s.n_excluded_small} negligible")

print(f"\ngross exposure          : {s.gross_usd:,.0f}")
print(f"benchmark annual carry  : {s.benchmark_annual:+,.0f}   "
      f"({s.benchmark_annual / s.gross_usd:+.2%} of gross) — what the backtest assumes")
print("\nrealised, by assumed accrual window (the window is not observable from one snapshot):")
for label, period in PERIOD_RANGE.items():
    r = financing_summary(legs, period_years=period)
    print(f"  if {label:8s}: realised {r.realised_annual:+,.0f}/yr   "
          f"gap {r.gap_annual:+,.0f}/yr   ({r.gap_pct_of_gross:+.2%} of gross)")

print("\n" + "=" * 78)
print("CAVEAT: this is a PAPER account. docs/income-enhancements.md records that its cash")
print("interest is simulated, so these figures may not reproduce live IBKR economics. This")
print("measures what the paper account does; it does not establish what a funded account would.")
print("=" * 78)

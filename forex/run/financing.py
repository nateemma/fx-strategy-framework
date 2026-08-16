"""Compare what the account actually accrues per currency against the benchmark the backtest assumes.

`forex/backtest/portfolio.py` accrues the full interbank differential (`forex/features/carry.py`)
with no broker financing spread. Live, longs are paid below benchmark and shorts charged at or above
it, on both legs of a dollar-neutral book — so a book the model shows earning carry can pay it.

The method: `accrued / balance = realised_rate * period`. Every currency in one snapshot shares the
same period, so `(accrued/balance) / benchmark` is **period-independent**. A divergence between the
long and short medians is a financing asymmetry that holds without knowing when interest last posted.
Absolute annualised figures DO need a period assumption — report them as a range, never a point.
"""
from pathlib import Path
from statistics import median
from typing import NamedTuple

from forex.config import CURRENCIES

MIN_ABS_BENCHMARK = 0.005   # below |0.5%/yr| the ratio is noise divided by noise
MIN_ABS_USD = 100.0         # legs smaller than this must not move a median


class LegRatio(NamedTuple):
    ccy: str
    side: str               # LONG | SHORT
    usd: float              # exposure in base currency
    accrued_usd: float
    benchmark: float        # FRED 3-month interbank rate, decimal
    asof: str               # as-of date of that benchmark
    ratio: float | None     # (accrued/balance) / benchmark; None when unmeasurable


class FinancingSummary(NamedTuple):
    ratios: list            # every leg, including excluded ones
    ratios_used: list       # only those behind the medians
    long_median: float | None
    short_median: float | None
    asymmetry: float | None       # short_median / long_median
    n_excluded_near_zero: int
    n_excluded_small: int
    gross_usd: float
    benchmark_annual: float       # what the backtest assumes this book earns per year
    realised_annual: float | None # annualised from the assumed accrual period
    gap_annual: float | None
    gap_pct_of_gross: float | None
    period_years: float | None


def leg_ratios(legs):
    """Per-leg realised/benchmark ratio. `legs` hold ccy, balance, accrued, rate, benchmark, asof."""
    out = []
    for leg in legs:
        balance, benchmark = float(leg["balance"]), float(leg["benchmark"])
        accrued, rate = float(leg["accrued"]), float(leg["rate"])
        implied = (accrued / balance) if balance else None
        out.append(LegRatio(
            ccy=leg["ccy"],
            side="LONG" if balance > 0 else "SHORT",
            usd=balance * rate,
            accrued_usd=accrued * rate,
            benchmark=benchmark,
            asof=str(leg.get("asof", "")),
            ratio=(implied / benchmark) if (implied is not None and benchmark) else None,
        ))
    return out


def annual_carry(legs):
    """What the backtest's own assumption says this book earns per year, in base currency."""
    return sum(float(leg["balance"]) * float(leg["rate"]) * float(leg["benchmark"]) for leg in legs)


def financing_summary(legs, period_years: float | None = None) -> FinancingSummary:
    """Summarise the financing gap. Medians exclude legs a ratio cannot describe."""
    ratios = leg_ratios(legs)

    near_zero = [r for r in ratios if abs(r.benchmark) < MIN_ABS_BENCHMARK]
    small = [r for r in ratios if abs(r.usd) < MIN_ABS_USD and r not in near_zero]
    used = [r for r in ratios
            if r.ratio is not None and r not in near_zero and r not in small]

    longs = [r.ratio for r in used if r.side == "LONG"]
    shorts = [r.ratio for r in used if r.side == "SHORT"]
    long_med = median(longs) if longs else None
    short_med = median(shorts) if shorts else None

    gross = sum(abs(r.usd) for r in ratios)
    benchmark_annual = annual_carry(legs)
    accrued_total = sum(r.accrued_usd for r in ratios)
    realised = (accrued_total / period_years) if period_years else None

    return FinancingSummary(
        ratios=ratios, ratios_used=used,
        long_median=long_med, short_median=short_med,
        asymmetry=(short_med / long_med) if (long_med and short_med) else None,
        n_excluded_near_zero=len(near_zero), n_excluded_small=len(small),
        gross_usd=gross,
        benchmark_annual=benchmark_annual,
        realised_annual=realised,
        gap_annual=(realised - benchmark_annual) if realised is not None else None,
        gap_pct_of_gross=((realised - benchmark_annual) / gross)
        if (realised is not None and gross) else None,
        period_years=period_years,
    )


def benchmark_rate(code, cache_dir=Path("data_cache")):
    """The cached FRED 3-month interbank rate for `code`, as (decimal_rate, as_of_date).

    This is the same series the backtest's carry signal uses, so the comparison is against the
    model's own assumption. Returns (None, None) when the series is not cached — the caller reports
    the gap rather than substituting a guess.
    """
    spec = CURRENCIES.get(code)
    if spec is None:
        return None, None
    path = Path(cache_dir) / f"{spec.rate_fred}.parquet"
    if not path.exists():
        return None, None
    import pandas as pd
    s = pd.read_parquet(path).iloc[:, 0].dropna()
    if s.empty:
        return None, None
    return float(s.iloc[-1]) / 100.0, str(s.index[-1].date())

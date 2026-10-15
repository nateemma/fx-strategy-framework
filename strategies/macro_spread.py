"""Candidates B5 (TIPS breakeven) and B6 (credit spread) — one module, because one shape. Spec 009.

Both are the same trade in different clothing: a spread that FRED publishes drives a two-instrument
position, long the premium-bearing leg and short a duration hedge. The signal is the spread's level
relative to its own history, which makes this carry-shaped mean reversion rather than a price
forecast — the shape that has worked in this repo.

Not a `Strategy` subclass: that contract returns currency weights. Precedent is
`strategies/trend_book.py` — plain functions, no registry (Principle I).

**Both candidates need a SHORT ETF leg, which this repo cannot cost.** `financing.py` is keyed by
currency and there is no equity-borrow data here, so any result is an upper bound that assumes free
shorting. The gate caps such a verdict at `inconclusive`. A candidate that loses even on that
generous basis is dead with certainty, which is the useful half.
"""
import pandas as pd

LOOKBACK = 250
MIN_PERIODS = 250


def spread_signal(spread: pd.Series, lookback: int = LOOKBACK) -> pd.Series:
    """Position in [-1, +1] from the spread's z-score against its own trailing window.

    Positive means the premium is unusually wide, so take it. Rolling rather than full-sample, so a
    value at *t* cannot change when later data arrives (Constitution II). A flat spread has no
    dispersion and therefore no view.
    """
    s = spread.astype("float64")
    mean = s.rolling(lookback, min_periods=MIN_PERIODS).mean()
    std = s.rolling(lookback, min_periods=MIN_PERIODS).std()
    z = (s - mean) / std.where(std > 1e-12)
    z = z.where(std > 1e-12, 0.0)
    z = z.where(mean.notna())
    return z.clip(-1.0, 1.0)


def pair_returns(signal: pd.Series, risk_leg: pd.Series, hedge_leg: pd.Series) -> pd.Series:
    """Daily return of the long-risk / short-hedge pair, positions lagged one day.

    Dollar-neutral here rather than duration-neutral: for a credit or breakeven premium the thing
    being harvested is the spread between two similar-duration instruments, so equal dollars is the
    natural construction. The one-day lag is not cosmetic — a signal from today's close cannot earn
    today's return, and omitting it is the commonest way a backtest invents an edge.
    """
    pos = signal.shift(1)
    return (pos * (risk_leg.pct_change() - hedge_leg.pct_change())).dropna()

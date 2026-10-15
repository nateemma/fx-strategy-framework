"""Candidate A3 — the 2s10s Treasury curve trade. Spec 009.

A steepener is long the short end and short the long end; a flattener is the reverse. The signal is
the slope's own level relative to its recent history, which makes this a slow mean-reversion /
carry-shaped position rather than a price forecast. That matters because the shape is the only one
with a track record in this repo: carry worked, every intraday price-prediction idea died.

NOT a `Strategy` subclass. That contract maps point-in-time data to target CURRENCY weights and
does not fit a two-leg rates trade. The precedent followed here is `strategies/trend_book.py`:
plain functions, no registry (Principle I forbids adding one).

**Duration-neutral, not dollar-neutral.** Equal dollars in a 2-year and a 10-year instrument is not
a curve position — it is a large net duration bet that happens to have two legs, and its P&L would
be dominated by the level of rates rather than the slope. The legs are therefore sized so their
duration contributions cancel.
"""
import pandas as pd

LOOKBACK = 250        # ~1 year of business days; slow by design
MIN_PERIODS = 250     # no value before the window is full, or the early signal is lookahead


def curve_signal(slope: pd.Series, lookback: int = LOOKBACK) -> pd.Series:
    """Position in [-1, +1] from the slope's z-score against its own trailing window.

    Positive means steepen. The z-score uses only data up to and including each date — a rolling
    window, never a full-sample mean — so the value at *t* cannot move when later data arrives
    (Constitution II). A flat series has zero dispersion and therefore takes no position rather
    than dividing by zero.
    """
    s = slope.astype("float64")
    mean = s.rolling(lookback, min_periods=MIN_PERIODS).mean()
    std = s.rolling(lookback, min_periods=MIN_PERIODS).std()
    z = (s - mean) / std.where(std > 1e-12)
    z = z.where(std > 1e-12, 0.0)       # no dispersion -> no view
    z = z.where(mean.notna())           # keep NaN until the window is full
    return z.clip(-1.0, 1.0)


def two_leg_weights(signal: float, short_end_duration: float,
                    long_end_duration: float) -> dict:
    """Duration-neutral weights for one unit of steepener risk.

    The short-end leg carries the sign of the signal; the long-end leg is scaled by the duration
    ratio so the net duration is zero. Returned as weights on the two instruments, which the gate
    turns into a return series.
    """
    if signal == 0.0:
        return {"short_end": 0.0, "long_end": 0.0}
    ratio = short_end_duration / long_end_duration
    return {"short_end": float(signal), "long_end": -float(signal) * ratio}


def spread_returns(signal: pd.Series, short_end: pd.Series, long_end: pd.Series,
                   short_end_duration: float, long_end_duration: float) -> pd.Series:
    """Daily return of the duration-neutral curve position, positions lagged by one day.

    The lag is not cosmetic: a signal computed from today's close cannot earn today's return, and
    omitting the lag is the most common way a backtest invents an edge.
    """
    ratio = short_end_duration / long_end_duration
    r_short = short_end.pct_change()
    r_long = long_end.pct_change()
    pos = signal.shift(1)
    return (pos * (r_short - ratio * r_long)).dropna()

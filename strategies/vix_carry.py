"""VIX carry satellite: hold a short-volatility ETP while the curve is in contango, else stand aside.

From the A1 gate (docs/vix-carry-findings.md). The volatility curve is in contango ~92% of days with
a mean depth of ~13%, and gating a short-vol position on `VIX3M > VIX` improves every era on both
instruments, in both Sharpe and drawdown, from one unoptimised rule.

TWO THINGS THIS SLEEVE IS NOT.

It is NOT a diversifier. It correlates +0.58 to SPY and, on the ETF book's twenty worst days, averages
-1.89% while being positive only 5% of the time. It is return enhancement bolted onto equity beta,
sized small enough that its tail does not dominate. It does not reduce the book's need for a genuinely
uncorrelated sleeve.

The gate is NOT a tail guard. It would have been out of the trade for 2018-02-06, when the -1x
predecessor instrument lost 83% in a single day — but it was fully IN for Brexit, which cost 26% in a
day. The current instrument has never experienced an event of that size at its present leverage,
because it was re-levered the week after the last one. Sizing must assume that event, not the eight
calm years since.

The position is IN or OUT. A scaled position would be a different strategy with no evidence behind it.
"""
from datetime import date
from typing import NamedTuple

import pandas as pd

MAX_STALE_DAYS = 5      # a long weekend plus a holiday; beyond this the signal is not current


class TermStructure(NamedTuple):
    in_trade: bool
    allocation: float       # the cash allocation when in, 0 when out
    vix: float
    vix3m: float
    contango: float         # vix3m/vix - 1; positive is contango
    asof: date              # the session the decision was made from


def vix_carry_target(vix: pd.Series, vix3m: pd.Series, allocation: float,
                     asof: date, max_stale_days: int = MAX_STALE_DAYS) -> TermStructure:
    """The sleeve's target for `asof`, decided from the last session published BEFORE it.

    Raises when the data is missing or stale: a stale term structure during a volatility event is
    exactly when holding the wrong position is most expensive, so refusing beats guessing.
    """
    cutoff = pd.Timestamp(asof)

    def before(s):
        s = s.dropna()
        if s.empty:                      # an empty series has no comparable index
            return s
        return s.loc[pd.DatetimeIndex(s.index) < cutoff]

    v, v3 = before(vix), before(vix3m)
    if v.empty or v3.empty:
        raise ValueError("no volatility term-structure data available before the decision date")

    stamp = min(v.index[-1], v3.index[-1])
    age = (cutoff - stamp).days
    if age > max_stale_days:
        raise ValueError(
            f"term structure is stale: last value {stamp.date()} is {age} days before {asof} "
            f"(tolerance {max_stale_days}). Refusing to trade on an old signal.")

    near, far = float(v.loc[:stamp].iloc[-1]), float(v3.loc[:stamp].iloc[-1])
    in_trade = far > near                      # strict: a flat curve stands aside
    return TermStructure(in_trade=in_trade, allocation=allocation if in_trade else 0,
                         vix=near, vix3m=far, contango=far / near - 1.0 if near else 0.0,
                         asof=stamp.date())

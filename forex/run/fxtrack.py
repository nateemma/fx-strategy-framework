"""Derive the FX book's own P&L series from the recorded snapshot history (nav.csv).

Whole-account NAV is dominated by the ETF sleeves, so judging the FX strategy needs a series built
only from the recorded FX values. ETF trades move only base-currency cash and therefore leave
`fx_net_base` untouched — that is what makes these figures structurally independent of the sleeves
rather than merely intended to be.

`fx_net_base` is the P&L *level* (see forex/run/fxbook.py): its change between snapshots is FX P&L,
plus flow on a day the book was rebalanced. Rebalance days are detected via unsettled FX trades
briefly appearing in the broker's position count.
"""
from collections import Counter
from datetime import date
from math import sqrt
from typing import NamedTuple

TRADING_DAYS = 252
MIN_OBS_PNL = 2       # two levels to difference
MIN_OBS_STATS = 20    # ~one month; below this a Sharpe is noise with a decimal point
MAX_GAP_DAYS = 4      # Fri->Mon is 3; beyond this the curve has a hole
BASELINE_WINDOW = 10  # trailing days used to infer the quiet ETF position count

_FX_FIELDS = ("fx_net_base", "fx_gross_base", "fx_accrued_base")


class FxObservation(NamedTuple):
    date: str
    net_base: float
    gross_base: float
    accrued_base: float
    pnl: float
    carry_pnl: float
    spot_pnl: float
    ret: float | None       # None when the prior gross was zero/absent
    gap_days: int
    contaminated: bool      # carries rebalance flow, not pure P&L
    excluded_gap: bool      # spans a hole in the daily curve


class FxPerformance(NamedTuple):
    n_fx_days: int
    period_start: str | None
    period_end: str | None
    net_base: float | None
    gross_base: float | None
    accrued_base: float | None
    total_pnl: float | None
    carry_pnl: float | None
    spot_pnl: float | None
    total_return: float | None
    n_obs: int              # observations behind the ratio statistics
    n_excluded: int         # dropped for rebalance flow or a curve gap
    ann_return: float | None
    ann_vol: float | None
    sharpe: float | None
    max_drawdown: float | None


def _num(value):
    """Parse a CSV cell to float, treating blank/garbage/NaN as absent."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def _is_fx_bearing(row):
    return all(_num(row.get(f)) is not None for f in _FX_FIELDS)


def _fx_days(rows):
    """FX-bearing rows, one per day (the day's last), ordered by date."""
    by_day = {}
    for r in sorted(rows, key=lambda r: r.get("timestamp", "")):
        if _is_fx_bearing(r):
            by_day[r["timestamp"][:10]] = r
    return [by_day[d] for d in sorted(by_day)]


def _baseline(counts, i):
    """The quiet ETF position count, inferred from the trailing window before day i.

    A rebalance is rare relative to quiet days, so the mode of recent counts is the ETF-only level;
    anything above it is an unsettled FX trade. Falls back to the whole series early on.
    """
    prior = [c for c in counts[max(0, i - BASELINE_WINDOW):i] if c is not None]
    if len(prior) < 3:
        prior = [c for c in counts if c is not None]
    return Counter(prior).most_common(1)[0][0] if prior else None


def fx_observations(rows):
    """Daily FX observations derived from consecutive FX-bearing snapshots."""
    days = _fx_days(rows)
    if len(days) < MIN_OBS_PNL:
        return []

    counts = [_num(d.get("stock_positions")) for d in days]
    unsettled = []
    for i, c in enumerate(counts):
        base = _baseline(counts, i)
        unsettled.append(c is not None and base is not None and c > base)

    obs = []
    for i in range(1, len(days)):
        prev, cur = days[i - 1], days[i]
        net, prev_net = _num(cur["fx_net_base"]), _num(prev["fx_net_base"])
        accrued, prev_accrued = _num(cur["fx_accrued_base"]), _num(prev["fx_accrued_base"])
        prev_gross = _num(prev["fx_gross_base"])

        pnl = net - prev_net
        carry = accrued - prev_accrued
        gap = (date.fromisoformat(cur["timestamp"][:10])
               - date.fromisoformat(prev["timestamp"][:10])).days
        obs.append(FxObservation(
            date=cur["timestamp"][:10],
            net_base=net, gross_base=_num(cur["fx_gross_base"]), accrued_base=accrued,
            pnl=pnl, carry_pnl=carry, spot_pnl=pnl - carry,
            ret=(pnl / prev_gross) if prev_gross else None,
            gap_days=gap,
            # either endpoint holding an unsettled trade means this move carries flow
            contaminated=unsettled[i] or unsettled[i - 1],
            excluded_gap=gap > MAX_GAP_DAYS,
        ))
    return obs


def _max_drawdown(returns):
    equity, peak, worst = 1.0, 1.0, 0.0
    for r in returns:
        equity *= 1.0 + r
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return worst


def fx_performance(rows):
    """Summarise the FX book. Ratio statistics are withheld below MIN_OBS_STATS."""
    days = _fx_days(rows)
    empty = FxPerformance(0, None, None, None, None, None, None, None, None, None,
                          0, 0, None, None, None, None)
    if not days:
        return empty

    first, last = days[0], days[-1]
    levels = dict(
        n_fx_days=len(days),
        period_start=first["timestamp"][:10], period_end=last["timestamp"][:10],
        net_base=_num(last["fx_net_base"]), gross_base=_num(last["fx_gross_base"]),
        accrued_base=_num(last["fx_accrued_base"]),
    )

    obs = fx_observations(rows)
    if len(days) < MIN_OBS_PNL or not obs:
        return empty._replace(**levels)

    # Cumulative P&L comes from the endpoints — they are levels, so exclusions must not clip them.
    total_pnl = _num(last["fx_net_base"]) - _num(first["fx_net_base"])
    carry_pnl = _num(last["fx_accrued_base"]) - _num(first["fx_accrued_base"])
    first_gross = _num(first["fx_gross_base"])
    perf = empty._replace(
        **levels,
        total_pnl=total_pnl, carry_pnl=carry_pnl, spot_pnl=total_pnl - carry_pnl,
        total_return=(total_pnl / first_gross) if first_gross else None,
    )

    usable = [o for o in obs if o.ret is not None and not o.contaminated and not o.excluded_gap]
    perf = perf._replace(n_obs=len(usable), n_excluded=len(obs) - len(usable))
    if len(usable) < MIN_OBS_STATS:
        return perf

    rets = [o.ret for o in usable]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    sd = sqrt(var)
    span = max(1, (date.fromisoformat(perf.period_end)
                   - date.fromisoformat(perf.period_start)).days)
    return perf._replace(
        ann_return=(1.0 + perf.total_return) ** (365.0 / span) - 1.0 if perf.total_return is not None else None,
        ann_vol=sd * sqrt(TRADING_DAYS),
        sharpe=(mean / sd * sqrt(TRADING_DAYS)) if sd else None,
        max_drawdown=_max_drawdown(rets),
    )

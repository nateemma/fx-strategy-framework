"""One verdict, computed the same way for every candidate. Spec 009.

This exists so the rules that decide a standalone verdict are enforced by code rather than
remembered six times. Three of them encode specific past failures in this repo:

- **Two eras, both of them.** An edge in one window is a ghost of a dead regime. The FX factor
  search repeatedly produced full-history numbers carried entirely by a pre-2010 era.
- **Net, always.** There is no code path here that computes a metric on gross returns, because
  gross-of-cost figures are what made the FX book look like Sharpe 1.15 when financing made it
  0.17. There is nowhere to put a gross number.
- **An uncostable short leg caps the verdict.** `financing.py` is keyed by currency and this repo
  has no equity-borrow data, so an ETF-pair result assumes free shorting. That is not a result, so
  `borrow_excluded=True` can never yield `pass` — but it can still yield `reject`, because a
  candidate that loses even WITHOUT its borrow cost is dead with certainty.

The bar is comparative rather than absolute: beat a named simpler alternative. This repo's own
history is why — the momentum basket died by losing to equal-weight of its own names and RSP died
by losing to SPY, neither by missing a threshold.
"""
from typing import NamedTuple

import pandas as pd

from forex.backtest.portfolio import metrics
from forex.backtest.validation import distant_window

TRADING_DAYS = 252


class WindowResult(NamedTuple):
    label: str
    start: pd.Timestamp
    end: pd.Timestamp
    n_days: int
    sharpe_net: float          # every figure here is NET — see the module docstring
    return_net: float
    max_dd: float
    benchmark_sharpe: float
    beats_benchmark: bool


class GateVerdict(NamedTuple):
    candidate_id: str
    verdict: str               # "pass" | "reject" | "inconclusive"
    per_window: tuple
    benchmark: str
    cost_basis: str
    borrow_excluded: bool
    reasoning: str


def _charge(returns: pd.Series, cost_bps: float, financing_annual: float,
            turnover: pd.Series = None) -> pd.Series:
    """Apply trading cost and financing BEFORE any metric is computed.

    `turnover` is the per-day absolute change in gross position, and callers SHOULD pass it: it is
    the quantity cost is actually charged on. When it is omitted the fallback infers trading from
    the return series, which is a poor proxy — a return series does not know when a position moved —
    so the fallback exists only to keep the pure-logic tests simple and should not be relied on for
    a real verdict.

    Financing is charged continuously on gross exposure, because that is how the broker charges it:
    daily, not per trade. Charging it per trade is part of how the FX book's cost was understated.
    """
    r = returns.dropna().astype("float64")
    daily_financing = financing_annual / TRADING_DAYS
    if turnover is None:
        turn = r.ne(0).astype("float64").diff().abs().fillna(0.0)
    else:
        turn = turnover.reindex(r.index).fillna(0.0).abs().astype("float64")
    return r - turn * (cost_bps / 1e4) - daily_financing


def _window(label, idx, net, bench) -> WindowResult:
    m, bm = metrics(net), metrics(bench)
    return WindowResult(
        label=label, start=idx[0], end=idx[-1], n_days=len(idx),
        sharpe_net=m["sharpe"], return_net=m["ann_return"], max_dd=m["max_drawdown"],
        benchmark_sharpe=bm["sharpe"], beats_benchmark=m["sharpe"] > bm["sharpe"])


def evaluate(returns: pd.Series, benchmark: pd.Series, *, holdout_years: int,
             cost_bps: float, financing_annual: float, turnover: pd.Series = None,
             borrow_excluded: bool = False, candidate_id: str = "",
             benchmark_name: str = "benchmark") -> GateVerdict:
    """Judge `returns` against `benchmark` across two temporally distant windows, net of cost.

    `holdout_years` is REQUIRED. `distant_window`'s own default of 3 is tuned to the FX sample and
    would split a 24-year history 3-versus-21, where the early era is too short to measure and the
    late era averages over the regimes the split exists to separate.
    """
    if benchmark is None or len(benchmark) == 0:
        raise ValueError("a benchmark is required — absolute performance is not a verdict (FR-002)")

    net = _charge(returns, cost_bps, financing_annual, turnover)
    bench = benchmark.reindex(net.index).fillna(0.0).astype("float64")
    cost_basis = (f"{cost_bps:.1f}bps turnover + {financing_annual:.2%}/yr financing on gross"
                  + (" (SHORT BORROW EXCLUDED — upper bound)" if borrow_excluded else ""))

    # distant_window returns (recent, distant) — RECENT FIRST, which reads backwards for its name.
    # Unpacking it the other way round silently swaps the era labels on every verdict.
    recent, distant = distant_window(net.index, holdout_years)
    windows = []
    for label, sl in (("distant", distant), ("recent", recent)):
        idx = net.index[sl]
        if len(idx) < TRADING_DAYS:          # too short to say anything about
            continue
        windows.append(_window(label, idx, net.loc[idx], bench.loc[idx]))

    if len(windows) < 2:
        return GateVerdict(candidate_id, "inconclusive", tuple(windows), benchmark_name,
                           cost_basis, borrow_excluded,
                           f"only {len(windows)} usable window(s); FR-004 requires two temporally "
                           f"distant ones, so no verdict is available")

    beaten = [w.beats_benchmark for w in windows]
    if not all(beaten):
        return GateVerdict(candidate_id, "reject", tuple(windows), benchmark_name, cost_basis,
                           borrow_excluded,
                           f"beats {benchmark_name} in {sum(beaten)} of {len(beaten)} eras net of "
                           f"cost; an edge in one era is a dead-regime ghost")

    if borrow_excluded:
        return GateVerdict(candidate_id, "inconclusive", tuple(windows), benchmark_name, cost_basis,
                           borrow_excluded,
                           f"beats {benchmark_name} in every era, but the short leg's borrow cost "
                           f"could not be costed, so this is an UPPER BOUND rather than a result. "
                           f"Worth pricing properly in futures or with real borrow data")

    return GateVerdict(candidate_id, "pass", tuple(windows), benchmark_name, cost_basis,
                       borrow_excluded,
                       f"beats {benchmark_name} net of cost in every era tested")

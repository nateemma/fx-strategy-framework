"""The standalone-gate evaluator. These tests encode the rules that decide a verdict.

Spec 009's bar is comparative, not absolute: beat a stated simpler alternative, net of cost and
financing, in BOTH eras. Two of the rules below exist because of specific past failures in this
repo — a one-era edge is a dead-regime ghost, and a figure reported gross of cost is what made the
FX book look like Sharpe 1.15 when it was 0.17.
"""
import numpy as np
import pandas as pd
import pytest

from forex.backtest.gate import evaluate
from forex.backtest.validation import distant_window

IDX = pd.date_range("2002-01-01", periods=252 * 24, freq="B")


# Fixtures carry NOISE deliberately. A constant return series has zero volatility, so its Sharpe is
# degenerate (measured 6.2e16 on the first draft of these tests) and any assertion about Sharpe
# becomes meaningless. Seeded, so the suite stays deterministic.
VOL = 0.004          # ~6.3%/yr, a plausible spread-trade vol
_RNG = np.random.default_rng(20261015)
_NOISE = pd.Series(_RNG.normal(0.0, VOL, len(IDX)), index=IDX, dtype="float64")


def series(per_day, index=IDX):
    """A flat benchmark. Zero drift and zero vol gives benchmark_sharpe 0.0, which is the
    'hold cash' comparator."""
    return pd.Series([per_day] * len(index), index=index, dtype="float64")


def two_era_series(early, late, holdout_years=12):
    """A noisy series with a different drift in each era the split will produce."""
    recent, distant = distant_window(IDX, holdout_years)
    s = _NOISE.copy()
    s.iloc[distant] += early
    s.iloc[recent] += late
    return s


FLAT = dict(holdout_years=12, cost_bps=0.0, financing_annual=0.0)


# ------------------------------------------------- the era split and its LABELLING

def test_distant_window_returns_recent_first(tmp_path=None):
    """Pinning the return ORDER, which reads backwards for a function of that name.

    `distant_window` returns (recent, distant). An inverted unpack would silently swap the era
    labels on every verdict, and none of the rule tests below would notice — they check the rule,
    not the labels. Spec 009 analyze finding I1.
    """
    recent, distant = distant_window(IDX, 12)
    assert IDX[distant][0] == IDX[0], "the SECOND slice must be the EARLY era"
    assert IDX[recent][-1] == IDX[-1], "the FIRST slice must be the LATE era"
    assert IDX[distant][-1] < IDX[recent][0]


def test_the_verdict_labels_eras_in_chronological_order():
    v = evaluate(two_era_series(0.001, 0.001), series(0.0), **FLAT)
    starts = [w.start for w in v.per_window]
    assert starts == sorted(starts), "windows must be reported earliest-first"


def test_fewer_than_two_windows_is_inconclusive():
    short = pd.date_range("2024-01-01", periods=200, freq="B")
    v = evaluate(series(0.001, short), series(0.0, short),
                 holdout_years=12, cost_bps=0.0, financing_annual=0.0)
    assert v.verdict == "inconclusive"
    assert len(v.per_window) < 2


# ------------------------------------------------- the verdict rules

def test_beating_the_benchmark_in_both_eras_passes():
    v = evaluate(two_era_series(0.001, 0.001), series(0.0), **FLAT)
    assert v.verdict == "pass"
    assert all(w.beats_benchmark for w in v.per_window)


def test_beating_it_in_only_one_era_is_a_reject_never_a_pass():
    """The dead-regime ghost. One good era is worth nothing."""
    v = evaluate(two_era_series(0.002, -0.001), series(0.0), **FLAT)
    assert v.verdict == "reject"
    assert sum(w.beats_benchmark for w in v.per_window) == 1


def test_losing_in_both_eras_is_a_reject():
    v = evaluate(two_era_series(-0.001, -0.001), series(0.0), **FLAT)
    assert v.verdict == "reject"


# ------------------------------------------------- the honest-limit rule (research R2)

def test_borrow_excluded_can_never_pass():
    """A result that assumes free shorting is not a result. It is capped at inconclusive even when
    the numbers are good in every era."""
    v = evaluate(two_era_series(0.002, 0.002), series(0.0), borrow_excluded=True, **FLAT)
    assert v.verdict == "inconclusive"
    assert v.borrow_excluded


def test_borrow_excluded_can_still_reject():
    """Capping the upside must not blunt the downside — a loser is still dead."""
    v = evaluate(two_era_series(-0.002, -0.002), series(0.0), borrow_excluded=True, **FLAT)
    assert v.verdict == "reject"


# ------------------------------------------------- costs, financing, and the benchmark

def test_costs_and_financing_are_applied_before_any_metric():
    """A thin gross edge must not survive the financing that killed the FX book."""
    gross = two_era_series(0.00003, 0.00003)      # ~0.76%/yr gross drift
    free = evaluate(gross, series(0.0), **FLAT)
    charged = evaluate(gross, series(0.0), holdout_years=12, cost_bps=0.0, financing_annual=0.02)
    assert free.verdict == "pass", "the gross series should look fine before costs"
    assert charged.per_window[0].sharpe_net < free.per_window[0].sharpe_net
    assert charged.verdict == "reject", "0.76%/yr gross must not survive 2%/yr financing"


def test_a_window_result_exposes_no_gross_figure():
    """SC-004 structurally: there is nowhere to put a gross number."""
    w = evaluate(two_era_series(0.001, 0.001), series(0.0), **FLAT).per_window[0]
    assert not [f for f in w._fields if "gross" in f.lower()]


def test_a_missing_benchmark_is_rejected_as_input():
    """FR-002 makes the comparator mandatory. Absolute performance is not a verdict."""
    with pytest.raises((TypeError, ValueError)):
        evaluate(two_era_series(0.001, 0.001), None, **FLAT)
    with pytest.raises(ValueError):
        evaluate(two_era_series(0.001, 0.001), pd.Series(dtype="float64"), **FLAT)


def test_holdout_years_is_required():
    """Research R3: the underlying default of 3 is tuned to the FX sample and would split a
    24-year history 3-versus-21."""
    with pytest.raises(TypeError):
        evaluate(two_era_series(0.001, 0.001), series(0.0), cost_bps=0.0, financing_annual=0.0)


# ------------------------------------------------- purity

def test_evaluate_is_pure():
    r, b = two_era_series(0.001, 0.0005), series(0.0)
    first, second = evaluate(r, b, **FLAT), evaluate(r, b, **FLAT)
    assert first == second
    assert not r.isna().any() and np.isfinite(r).all(), "inputs must not be mutated"

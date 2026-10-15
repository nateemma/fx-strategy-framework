"""The shared two-leg macro-spread signal, serving B5 (TIPS breakeven) and B6 (credit). Spec 009.

Both candidates are the same shape — a FRED-published spread series drives a two-instrument
position — so they share one module rather than two near-identical ones.
"""
import numpy as np
import pandas as pd
import pytest

from strategies.macro_spread import pair_returns, spread_signal

IDX = pd.date_range("2004-01-01", periods=1500, freq="B")


def ser(values):
    return pd.Series(values, index=IDX[: len(values)], dtype="float64")


def test_a_widening_spread_gives_a_positive_signal():
    assert spread_signal(ser(np.linspace(1.0, 5.0, 900)), lookback=250).dropna().iloc[-1] > 0


def test_a_narrowing_spread_gives_a_negative_signal():
    assert spread_signal(ser(np.linspace(5.0, 1.0, 900)), lookback=250).dropna().iloc[-1] < 0


def test_a_flat_spread_gives_no_position():
    s = spread_signal(ser(np.full(900, 2.0)), lookback=250)
    assert s.dropna().abs().max() == pytest.approx(0.0, abs=1e-9)


def test_the_signal_is_bounded_and_waits_for_its_window():
    s = spread_signal(ser(np.concatenate([np.full(700, 2.0), np.full(200, 99.0)])), lookback=250)
    assert s.dropna().abs().max() <= 1.0 + 1e-9
    assert s.iloc[:249].isna().all()


def test_the_signal_is_causal():
    full = ser(np.linspace(1.0, 5.0, 900))
    cut = 700
    a = spread_signal(full, lookback=250).iloc[:cut].dropna()
    b = spread_signal(full.iloc[:cut], lookback=250).dropna()
    pd.testing.assert_series_equal(a, b, check_names=False)


def test_pair_returns_are_long_risk_short_hedge_when_the_signal_is_positive():
    """A positive signal means the premium is wide, so take it: long the risk leg, short the hedge."""
    risk = pd.Series(np.linspace(100, 110, 300), index=IDX[:300], dtype="float64")
    hedge = pd.Series(np.full(300, 100.0), index=IDX[:300], dtype="float64")
    sig = pd.Series(1.0, index=IDX[:300], dtype="float64")
    assert pair_returns(sig, risk, hedge).sum() > 0


def test_positions_are_lagged_so_a_signal_cannot_earn_the_same_days_return():
    risk = pd.Series([100.0, 110.0, 110.0], index=IDX[:3], dtype="float64")
    hedge = pd.Series([100.0, 100.0, 100.0], index=IDX[:3], dtype="float64")
    sig = pd.Series([1.0, 0.0, 0.0], index=IDX[:3], dtype="float64")
    r = pair_returns(sig, risk, hedge)
    # The +10% move happens on day 2; only a position held from day 1 earns it.
    assert r.iloc[0] == pytest.approx(0.10)


def test_a_zero_signal_earns_nothing():
    risk = pd.Series(np.linspace(100, 200, 300), index=IDX[:300], dtype="float64")
    hedge = pd.Series(np.full(300, 100.0), index=IDX[:300], dtype="float64")
    sig = pd.Series(0.0, index=IDX[:300], dtype="float64")
    assert pair_returns(sig, risk, hedge).abs().sum() == pytest.approx(0.0)

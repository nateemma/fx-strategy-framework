"""The 2s10s curve signal (candidate A3). Spec 009.

A steepener is long the short end and short the long end, sized so the two legs offset in duration
terms rather than in dollars. The signal is the slope's own level relative to its history — slow,
and not a price prediction, which is the only signal shape with a track record in this repo.
"""
import numpy as np
import pandas as pd
import pytest

from strategies.curve_spread import curve_signal, two_leg_weights

IDX = pd.date_range("2002-01-01", periods=1200, freq="B")


def slope(values):
    return pd.Series(values, index=IDX[: len(values)], dtype="float64")


# ------------------------------------------------- the signal

def test_a_steepening_curve_gives_a_positive_signal():
    s = curve_signal(slope(np.linspace(-0.5, 2.5, 800)), lookback=250)
    assert s.dropna().iloc[-1] > 0


def test_an_inverting_curve_gives_a_negative_signal():
    s = curve_signal(slope(np.linspace(2.5, -0.5, 800)), lookback=250)
    assert s.dropna().iloc[-1] < 0


def test_a_flat_unchanging_curve_gives_no_position():
    """No information, no position. A signal that takes a view on a constant is fitting noise."""
    s = curve_signal(slope(np.full(800, 1.0)), lookback=250)
    assert s.dropna().abs().max() == pytest.approx(0.0, abs=1e-9)


def test_the_signal_is_bounded():
    """An unbounded z-score would size a position on an outlier. Bounded to [-1, 1]."""
    noisy = np.concatenate([np.full(600, 1.0), np.full(200, 50.0)])
    s = curve_signal(slope(noisy), lookback=250).dropna()
    assert s.abs().max() <= 1.0 + 1e-9


def test_the_signal_has_no_value_before_its_lookback_is_filled():
    s = curve_signal(slope(np.linspace(0, 2, 800)), lookback=250)
    assert s.iloc[:249].isna().all(), "a signal before its window is filled would be lookahead"


# ------------------------------------------------- causality (Constitution II)

def test_the_signal_at_t_is_unchanged_when_later_data_is_removed():
    """The structural test. Truncating the future must not move a past signal value."""
    full = slope(np.linspace(-0.5, 2.5, 800))
    cut = 600
    s_full = curve_signal(full, lookback=250)
    s_trunc = curve_signal(full.iloc[:cut], lookback=250)
    pd.testing.assert_series_equal(
        s_full.iloc[:cut].dropna(), s_trunc.dropna(), check_names=False)


# ------------------------------------------------- the two legs

def test_a_steepener_is_long_the_short_end_and_short_the_long_end():
    w = two_leg_weights(1.0, short_end_duration=1.9, long_end_duration=7.6)
    assert w["short_end"] > 0 and w["long_end"] < 0


def test_a_flattener_reverses_both_legs():
    w = two_leg_weights(-1.0, short_end_duration=1.9, long_end_duration=7.6)
    assert w["short_end"] < 0 and w["long_end"] > 0


def test_the_legs_are_duration_neutral_not_dollar_neutral():
    """Dollar-neutral would leave a large net duration position, which is a rates bet rather than a
    curve bet — the trade would be dominated by the level, not the slope."""
    d_short, d_long = 1.9, 7.6
    w = two_leg_weights(1.0, short_end_duration=d_short, long_end_duration=d_long)
    net_duration = w["short_end"] * d_short + w["long_end"] * d_long
    assert net_duration == pytest.approx(0.0, abs=1e-9)
    assert abs(w["short_end"]) != pytest.approx(abs(w["long_end"]))


def test_a_zero_signal_gives_a_zero_position():
    w = two_leg_weights(0.0, short_end_duration=1.9, long_end_duration=7.6)
    assert w["short_end"] == 0.0 and w["long_end"] == 0.0

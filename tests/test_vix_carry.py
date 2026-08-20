from datetime import date, timedelta

import pandas as pd
import pytest

from strategies.vix_carry import MAX_STALE_DAYS, TermStructure, vix_carry_target


def series(pairs):
    """pairs: {date: value} -> Series"""
    return pd.Series({pd.Timestamp(d): v for d, v in pairs.items()}).sort_index()


TODAY = date(2026, 8, 19)


def curve(vix, vix3m, asof=date(2026, 8, 18)):
    return series({asof: vix}), series({asof: vix3m})


# ---------------------------------------------------------------- the contango rule

def test_contango_means_in_the_trade():
    v, v3 = curve(15.0, 18.0)
    t = vix_carry_target(v, v3, allocation=50_000, asof=TODAY)
    assert t.in_trade is True
    assert t.allocation == 50_000


def test_backwardation_means_stand_aside():
    v, v3 = curve(30.0, 22.0)
    t = vix_carry_target(v, v3, allocation=50_000, asof=TODAY)
    assert t.in_trade is False
    assert t.allocation == 0


def test_a_flat_curve_stands_aside():
    """Equal is not contango; the rule is strict."""
    v, v3 = curve(20.0, 20.0)
    assert vix_carry_target(v, v3, 50_000, TODAY).in_trade is False


def test_the_decision_reports_the_values_behind_it():
    v, v3 = curve(15.0, 18.0)
    t = vix_carry_target(v, v3, 50_000, TODAY)
    assert t.vix == 15.0 and t.vix3m == 18.0
    assert t.contango == pytest.approx(18.0 / 15.0 - 1.0)
    assert t.asof == date(2026, 8, 18)


# ---------------------------------------------------------------- causality

def test_only_data_published_before_the_decision_is_used():
    """A value dated today must not influence a position taken today."""
    v = series({pd.Timestamp("2026-08-18"): 30.0, pd.Timestamp("2026-08-19"): 15.0})
    v3 = series({pd.Timestamp("2026-08-18"): 22.0, pd.Timestamp("2026-08-19"): 18.0})
    t = vix_carry_target(v, v3, 50_000, asof=TODAY)
    assert t.asof == date(2026, 8, 18)
    assert t.in_trade is False, "used today's contango instead of yesterday's backwardation"


def test_future_data_is_ignored_entirely():
    v = series({pd.Timestamp("2026-08-18"): 15.0, pd.Timestamp("2026-09-01"): 40.0})
    v3 = series({pd.Timestamp("2026-08-18"): 18.0, pd.Timestamp("2026-09-01"): 25.0})
    assert vix_carry_target(v, v3, 50_000, TODAY).in_trade is True


# ---------------------------------------------------------------- staleness

def test_stale_data_refuses_rather_than_trading_on_an_old_signal():
    stale = date(2026, 8, 19) - timedelta(days=MAX_STALE_DAYS + 3)
    v, v3 = curve(15.0, 18.0, asof=stale)
    with pytest.raises(ValueError, match="stale"):
        vix_carry_target(v, v3, 50_000, TODAY)


def test_data_inside_the_staleness_window_is_accepted():
    recent = date(2026, 8, 19) - timedelta(days=MAX_STALE_DAYS - 1)
    v, v3 = curve(15.0, 18.0, asof=recent)
    assert vix_carry_target(v, v3, 50_000, TODAY).in_trade is True


def test_a_weekend_gap_does_not_count_as_stale():
    """Friday's close driving Monday's position is normal, not stale."""
    friday = date(2026, 8, 14)
    v, v3 = curve(15.0, 18.0, asof=friday)
    assert vix_carry_target(v, v3, 50_000, date(2026, 8, 17)).in_trade is True


def test_no_data_at_all_refuses():
    empty = pd.Series(dtype=float)
    with pytest.raises(ValueError):
        vix_carry_target(empty, empty, 50_000, TODAY)


# ---------------------------------------------------------------- shape of the position

def test_the_sleeve_has_no_partial_position():
    """In or out is what the gate tested; a scaled position would be a different strategy."""
    for vix, v3m in [(15.0, 18.0), (15.0, 15.1), (15.0, 30.0)]:
        t = vix_carry_target(*curve(vix, v3m), allocation=50_000, asof=TODAY)
        assert t.allocation in (0, 50_000)


def test_the_live_curve_shape_is_in_the_trade():
    """2026-08-13 actuals from the A1 gate: VIX 14.63, VIX3M 18.61 — deep contango."""
    t = vix_carry_target(*curve(14.63, 18.61), allocation=50_000, asof=TODAY)
    assert t.in_trade is True
    assert t.contango > 0.25


def test_term_structure_record_is_returned_for_logging():
    t = vix_carry_target(*curve(15.0, 18.0), allocation=50_000, asof=TODAY)
    assert isinstance(t, TermStructure)

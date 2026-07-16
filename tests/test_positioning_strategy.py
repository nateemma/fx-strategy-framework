import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.features.positioning import positioning_signal
from strategies.positioning import PositioningStrategy


def _view():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    spot = pd.DataFrame({"EUR": 1.1, "JPY": 0.009, "GBP": 1.3}, index=idx)
    widx = pd.date_range("2018-06-05", periods=140, freq="W-TUE")     # weekly, pre-dates spot
    pos = {"EUR": pd.Series(np.linspace(-100, 100, 140), index=widx),  # trending to crowded LONG
           "JPY": pd.Series(np.zeros(140), index=widx),
           "GBP": pd.Series(np.linspace(100, -100, 140), index=widx)}  # trending to crowded SHORT
    return DataView(spot=spot, rates={}, positioning=pos)


def test_positioning_signal_is_contrarian():
    v = _view()
    sig = positioning_signal(v.calendar, v.positioning, window=52)
    last = sig[["EUR", "GBP"]].dropna().iloc[-1]    # JPY is degenerate (all-zero -> NaN z) by construction
    assert last["EUR"] < 0 and last["GBP"] > 0     # fade the crowded long, buy the crowded short


def test_positioning_strategy_dollar_neutral_unit_gross():
    w = PositioningStrategy(window=52).target_weights(_view()).dropna()
    row = w.iloc[-1]
    assert abs(row.sum()) < 1e-9                    # dollar-neutral
    assert abs(row.abs().sum() - 1.0) < 1e-6        # unit gross
    assert row["EUR"] < 0 and row["GBP"] > 0


def test_empty_positioning_yields_zero_weights():
    idx = pd.date_range("2020-01-01", periods=50, freq="B")
    v = DataView(spot=pd.DataFrame({"EUR": 1.1, "JPY": 0.009}, index=idx), rates={}, positioning={})
    w = PositioningStrategy().target_weights(v)
    assert (w.fillna(0.0) == 0.0).all().all()       # graceful fallback -> blend degrades to carry-only


def test_carry_cot_blend_registered():
    from forex.core.discovery import build_strategy
    s = build_strategy("carry_cot", {}, "strategies")
    assert "carry" in s.components and "positioning" in s.components

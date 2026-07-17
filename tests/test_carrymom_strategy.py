import numpy as np, pandas as pd
from forex.core.dataview import DataView
from strategies.carrymom import CarryMomStrategy


def _view():
    idx = pd.date_range("2020-01-01", periods=400, freq="B")
    spot = pd.DataFrame({c: 1.0 for c in ["EUR", "JPY", "GBP", "CHF"]}, index=idx)
    ridx = pd.date_range("2019-01-01", periods=30, freq="MS")
    rates = {"USD": pd.Series(0.02, index=ridx),
             "EUR": pd.Series(np.linspace(0.02, 0.06, 30), index=ridx),   # differential WIDENING vs USD
             "JPY": pd.Series(np.linspace(0.06, 0.02, 30), index=ridx),   # NARROWING
             "GBP": pd.Series(0.03, index=ridx), "CHF": pd.Series(0.03, index=ridx)}
    return DataView(spot=spot, rates=rates)


def test_carry_mom_longs_widening_shorts_narrowing():
    w = CarryMomStrategy(lookback=126, n_long=1, n_short=1).target_weights(_view()).dropna()
    row = w.iloc[-1]
    assert row["EUR"] > 0 and row["JPY"] < 0     # long the widening differential, short the narrowing


def test_carry_cot_mom_blend_registered():
    from forex.core.discovery import build_strategy
    s = build_strategy("carry_cot_mom", {}, "strategies")
    assert set(s.components) == {"carry", "positioning", "carrymom"}
    assert s.components["carrymom"].lookback == 126

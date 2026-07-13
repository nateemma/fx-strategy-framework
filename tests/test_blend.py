import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.core.space import Int, Categorical
from strategies.blend import BlendStrategy
from strategies.carry import CarryStrategy
from strategies.trend import TrendStrategy
from forex.diagnostics.causal import assert_causal
from forex.run.backtest import backtest
from forex.core.result import Result
from forex.core.discovery import build_strategy

def _view():
    idx = pd.date_range("2016-01-01", periods=500, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,500), "EUR": 1.1+np.linspace(0,0.05,500),
                         "SEK": 1.0+np.linspace(0,-0.1,500)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_single_component_reproduces_the_sub():
    v = _view()
    carry = CarryStrategy(1, 1)
    b = BlendStrategy({"carry": CarryStrategy(1, 1)}).target_weights(v)
    cw = carry.target_weights(v)
    both = b.dropna(how="all").index.intersection(cw.dropna(how="all").index)
    assert (b.loc[both] - cw.loc[both]).abs().max().max() < 1e-9   # single -> L=1 -> equals sub

def test_two_identical_components_reproduce_the_sub():
    v = _view()
    b = BlendStrategy({"a": CarryStrategy(1, 1), "c": CarryStrategy(1, 1)}).target_weights(v)
    cw = CarryStrategy(1, 1).target_weights(v)
    both = b.dropna(how="all").index.intersection(cw.dropna(how="all").index)
    assert (b.loc[both] - cw.loc[both]).abs().max().max() < 1e-9   # 0.5w + 0.5w = w

def test_two_different_subs_are_convex_combination():
    v = _view()
    carry, trend = CarryStrategy(1, 1), TrendStrategy("ema", 40)
    b = BlendStrategy({"carry": carry, "trend": trend}).target_weights(v)
    wc, wt = carry.target_weights(v), trend.target_weights(v)
    assert b.index.equals(wc.index) and list(b.columns) == list(wc.columns)
    t = v.calendar[400]                              # post warm-up
    lo = pd.concat([wc.loc[t], wt.loc[t]], axis=1).min(axis=1)
    hi = pd.concat([wc.loc[t], wt.loc[t]], axis=1).max(axis=1)
    assert ((b.loc[t] >= lo - 1e-9) & (b.loc[t] <= hi + 1e-9)).all()   # convex per currency

def test_prefixed_params_and_search_space():
    b = BlendStrategy({"carry": CarryStrategy(3, 3), "trend": TrendStrategy("ema", 108)})
    p = b.params()
    assert p["carry_n_long"] == 3 and p["trend_signal_type"] == "ema" and p["trend_lookback"] == 108
    space = b.search_space()
    assert space["carry_n_long"] == Int(2, 4)
    assert space["trend_signal_type"] == Categorical(["tsmom", "ema", "donchian"])

def test_blend_is_causal():
    v = _view()
    b = BlendStrategy({"carry": CarryStrategy(1, 1), "trend": TrendStrategy("ema", 40)})
    assert_causal(b, v, v.calendar[[200, 350, 499]])

def test_backtest_produces_finite_result():
    v = _view()
    b = BlendStrategy({"carry": CarryStrategy(1, 1), "trend": TrendStrategy("ema", 40)})
    r = backtest(b, v, cost_bps=1.0)
    assert isinstance(r, Result)
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])

def test_voltarget_wrapped_blend_is_causal():
    v = _view()
    s = build_strategy("carry_trend_voltarget")
    assert_causal(s, v, v.calendar[[300, 450, 499]])

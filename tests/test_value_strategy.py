import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.core.space import Int
from forex.strategies.value import ValueStrategy
from forex.diagnostics.causal import assert_causal
from forex.run.backtest import backtest
from forex.core.result import Result

def test_longs_undervalued_shorts_overvalued_dollar_neutral():
    # monotonic REER through 2019-12; daily calendar well past REER end + 45d lag
    midx = pd.date_range("2018-01-01", periods=24, freq="MS")
    reer = {
        "AUD": pd.Series(100.0 + np.arange(24), index=midx),   # rising -> above mean -> rich -> short
        "EUR": pd.Series([100.0] * 24, index=midx),            # flat -> mid -> excluded
        "SEK": pd.Series(100.0 - np.arange(24), index=midx),   # falling -> below mean -> cheap -> long
    }
    idx = pd.date_range("2020-03-02", periods=6, freq="B")
    spot = pd.DataFrame({"AUD": [1.0]*6, "EUR": [1.1]*6, "SEK": [1.0]*6}, index=idx)
    rates = {c: pd.Series(0.0, index=idx) for c in ["USD", "AUD", "EUR", "SEK"]}
    w = ValueStrategy(window=3, n_long=1, n_short=1).target_weights(
        DataView(spot=spot, rates=rates, reer=reer))
    last = w.loc[idx[-1]]
    assert last["SEK"] == 1.0     # undervalued -> long
    assert last["AUD"] == -1.0    # overvalued -> short
    assert last["EUR"] == 0.0
    assert abs(last.sum()) < 1e-9

def test_params_and_search_space():
    s = ValueStrategy(60, 3, 3)
    assert s.params() == {"window": 60, "n_long": 3, "n_short": 3}
    space = s.search_space()
    assert set(space) == {"window", "n_long", "n_short"}
    assert space["window"] == Int(36, 84)
    assert space["n_long"] == Int(2, 4) and space["n_short"] == Int(2, 4)

def _view():
    idx = pd.date_range("2018-01-01", periods=520, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.2,520), "EUR": 1.1+np.zeros(520),
                         "SEK": 1.0+np.linspace(0,-0.1,520)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.03, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.02, index=idx)}
    midx = pd.date_range("2016-06-01", periods=40, freq="MS")
    reer = {"AUD": pd.Series(100.0+np.arange(40), index=midx),
            "EUR": pd.Series([100.0]*40, index=midx),
            "SEK": pd.Series(100.0-np.arange(40), index=midx)}
    return DataView(spot=spot, rates=rates, reer=reer)

def test_value_is_causal():
    v = _view()
    assert_causal(ValueStrategy(3, 1, 1), v, v.calendar[[100, 300, 519]])  # no raise

def test_backtest_produces_finite_result():
    r = backtest(ValueStrategy(3, 1, 1), _view(), cost_bps=1.0)
    assert isinstance(r, Result)
    assert len(r.returns) == len(r.weights)
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])

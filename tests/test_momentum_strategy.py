import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.core.space import Int
from forex.strategies.momentum import MomentumStrategy
from forex.diagnostics.causal import assert_causal
from forex.run.backtest import backtest
from forex.core.result import Result

def test_longs_winner_shorts_loser_dollar_neutral():
    idx = pd.date_range("2020-01-01", periods=4, freq="B")
    spot = pd.DataFrame(
        {"AUD": [1.0, 1.1, 1.2, 1.3],   # strictly rising -> top signal -> long
         "EUR": [1.1, 1.1, 1.1, 1.1],   # flat -> middle -> excluded
         "SEK": [1.0, 0.95, 0.9, 0.85]}, # strictly falling -> bottom -> short
        index=idx,
    )
    rates = {"USD": pd.Series(0.0, index=idx), "AUD": pd.Series(0.0, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.0, index=idx)}
    w = MomentumStrategy(lookback=2, n_long=1, n_short=1).target_weights(DataView(spot=spot, rates=rates))
    last = w.loc[idx[-1]]
    assert last["AUD"] == 1.0      # appreciating currency is longed (sign convention)
    assert last["SEK"] == -1.0     # depreciating currency is shorted
    assert last["EUR"] == 0.0
    assert abs(last.sum()) < 1e-9  # dollar-neutral

def test_params_and_search_space():
    s = MomentumStrategy(63, 3, 3)
    assert s.params() == {"lookback": 63, "n_long": 3, "n_short": 3}
    space = s.search_space()
    assert set(space) == {"lookback", "n_long", "n_short"}
    assert space["lookback"] == Int(21, 126)
    assert space["n_long"] == Int(2, 4) and space["n_short"] == Int(2, 4)

def _view():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.zeros(400),
                         "SEK": 1.0+np.linspace(0,-0.1,400)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_momentum_is_causal():
    v = _view()
    assert_causal(MomentumStrategy(63, 1, 1), v, v.calendar[[100, 200, 399]])  # no raise

def test_backtest_produces_finite_result():
    r = backtest(MomentumStrategy(63, 1, 1), _view(), cost_bps=1.0)
    assert isinstance(r, Result)
    assert len(r.returns) == len(r.weights)
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])

import numpy as np, pandas as pd
import pytest
from forex.core.dataview import DataView
from forex.core.space import Categorical, Int
from strategies.trend import TrendStrategy
from forex.diagnostics.causal import assert_causal
from forex.run.backtest import backtest
from forex.core.result import Result

def _view():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.linspace(0,0.05,400),
                         "SEK": 1.0+np.linspace(0,-0.1,400)}, index=idx)   # EUR mild up so all 3 active
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_params_and_search_space():
    s = TrendStrategy("tsmom", 252)
    assert s.params() == {"signal_type": "tsmom", "lookback": 252}
    space = s.search_space()
    assert space["signal_type"] == Categorical(["tsmom", "ema", "donchian"])
    assert space["lookback"] == Int(21, 252)

def test_directional_weights_from_signal():
    v = _view()
    w = TrendStrategy("tsmom", 20).target_weights(v)
    last = w.loc[v.calendar[-1]]
    assert last["AUD"] > 0 and last["SEK"] < 0        # AUD up -> long, SEK down -> short
    assert abs(last.abs().sum() - 1.0) < 1e-9         # gross = 1 (all 3 active, equal 1/3)

@pytest.mark.parametrize("stype", ["tsmom", "ema", "donchian"])
def test_trend_is_causal(stype):
    v = _view()
    assert_causal(TrendStrategy(stype, 20), v, v.calendar[[100, 250, 399]])

@pytest.mark.parametrize("stype", ["tsmom", "ema", "donchian"])
def test_backtest_produces_finite_result(stype):
    r = backtest(TrendStrategy(stype, 20), _view(), cost_bps=1.0)
    assert isinstance(r, Result)
    assert np.isfinite(r.metrics["total_return"]) and np.isfinite(r.metrics["sharpe"])

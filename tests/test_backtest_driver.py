import numpy as np, pandas as pd
from forex.core.dataview import DataView
from strategies.carry import CarryStrategy
from forex.run.backtest import backtest
from forex.core.result import Result

def _view():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.2,300), "EUR": 1.1+np.zeros(300)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_backtest_returns_result_with_positive_carry():
    r = backtest(CarryStrategy(1,1), _view(), cost_bps=1.0)
    assert isinstance(r, Result)
    assert r.metrics["total_return"] > 0            # long high-carry rising AUD, short flat EUR
    assert len(r.returns) == len(r.weights)
    assert "sharpe" in r.metrics

def test_returns_of_matches_backtest_returns():
    from forex.run.backtest import returns_of
    from strategies.carry import CarryStrategy
    from forex.core.discovery import build_strategy
    v = _view()
    for strat in (CarryStrategy(1, 1),
                  build_strategy("carry_trend", package="strategies"),
                  build_strategy("carry_trend_voltarget", package="strategies")):
        w = strat.target_weights(v)
        r = returns_of(w, v, 1.0)
        assert (r.round(12) == backtest(strat, v, 1.0).returns.round(12)).all()   # byte-identical

import numpy as np, pandas as pd
from forex.core.dataview import DataView
from strategies.carry import CarryStrategy
from forex.run.walkforward import walk_forward
from forex.run.backtest import backtest
from forex.core.result import Result

def _view():
    idx = pd.date_range("2018-01-01", periods=800, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.4,800), "EUR": 1.1+np.zeros(800)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_walk_forward_stitches_oos_and_is_subset_of_full():
    v = _view()
    r = walk_forward(lambda: CarryStrategy(1,1), v, train_days=250, test_days=125)
    assert isinstance(r, Result)
    # OOS series is a proper subset of the full-history backtest dates
    full = backtest(CarryStrategy(1,1), v)
    assert set(r.returns.index).issubset(set(full.returns.index))
    assert len(r.returns) > 0 and "sharpe" in r.metrics

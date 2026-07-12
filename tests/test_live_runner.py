import numpy as np, pandas as pd
from forex.core.dataview import DataView
from forex.strategies.carry import CarryStrategy
from forex.run.live import rebalance_now
from forex.run.execution import RebalanceReport

def _view():
    idx = pd.date_range("2018-01-01", periods=300, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.2,300), "EUR": 1.1+np.zeros(300)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx)}
    return DataView(spot=spot, rates=rates)

class _MockExecution:
    def __init__(self): self.calls = []
    def rebalance(self, target_weights, prices):
        self.calls.append((target_weights, prices))
        return RebalanceReport(orders={}, positions=dict(target_weights),
                               equity=1.0, turnover=0.0, cost=0.0, applied=True)

def test_rebalance_now_passes_latest_target_and_prices():
    view = _view()
    ex = _MockExecution()
    rep = rebalance_now(CarryStrategy(1, 1), view, ex)
    tw, px = ex.calls[0]
    assert set(tw.index) == set(view.codes)              # a target per traded currency
    assert px.name == view.spot.index[-1]                # prices are the LAST spot row
    assert float(px["AUD"]) == float(view.spot["AUD"].iloc[-1])
    assert rep.positions == dict(tw)                     # returns the executor's report

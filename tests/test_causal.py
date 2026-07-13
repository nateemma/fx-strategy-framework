import numpy as np, pandas as pd, pytest
from forex.core.dataview import DataView
from forex.core.strategy import Strategy
from strategies.carry import CarryStrategy
from forex.diagnostics.causal import assert_causal

def _view():
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    spot = pd.DataFrame({"AUD": 1.0+np.linspace(0,0.3,400), "EUR": 1.1+np.zeros(400),
                         "SEK": 1.0+np.linspace(0,-0.1,400)}, index=idx)
    rates = {"USD": pd.Series(0.01, index=idx), "AUD": pd.Series(0.06, index=idx),
             "EUR": pd.Series(0.0, index=idx), "SEK": pd.Series(0.03, index=idx)}
    return DataView(spot=spot, rates=rates)

class _Leaky(Strategy):
    def target_weights(self, view):
        # BAD: uses the FULL-sample max (a future value) -> not causal
        m = view.spot.max()
        return (view.spot == m).astype(float)

def test_carry_strategy_is_causal():
    v = _view()
    assert_causal(CarryStrategy(1,1), v, v.calendar[[100, 200, 399]])   # no raise

def test_leaky_strategy_is_flagged():
    v = _view()
    with pytest.raises(AssertionError):
        assert_causal(_Leaky(), v, v.calendar[[100, 200]])

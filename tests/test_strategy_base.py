import pandas as pd
from forex.core.strategy import Strategy
from forex.core.result import Result
from forex.core.dataview import DataView

class _Const(Strategy):
    def target_weights(self, view):
        return pd.DataFrame(1.0, index=view.calendar, columns=view.codes)

def _view():
    idx = pd.date_range("2020-01-01", periods=3, freq="D")
    return DataView(spot=pd.DataFrame({"AUD": [1.0]*3}, index=idx), rates={"USD": pd.Series([0.0]*3, index=idx)})

def test_defaults():
    s = _Const()
    assert s.params() == {} and s.search_space() == {}
    assert s.fit(_view()) is None                       # no-op default
    w = s.target_weights(_view())
    assert list(w.columns) == ["AUD"] and (w == 1.0).all().all()

def test_result_holds_fields():
    r = Result(returns=pd.Series([0.1]), weights=pd.DataFrame({"AUD":[1.0]}), metrics={"sharpe": 1.0})
    assert r.metrics["sharpe"] == 1.0

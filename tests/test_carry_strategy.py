import pandas as pd
from forex.core.dataview import DataView
from forex.strategies.carry import CarryStrategy

def test_carry_strategy_weights_are_dollar_neutral():
    idx = pd.date_range("2020-01-01", periods=2, freq="D")
    spot = pd.DataFrame({"AUD":[1.0,1.0], "EUR":[1.1,1.1]}, index=idx)
    rates = {"USD": pd.Series([0.01,0.01], index=idx),
             "AUD": pd.Series([0.06,0.06], index=idx),   # high carry -> long
             "EUR": pd.Series([0.0,0.0], index=idx)}      # low carry -> short
    w = CarryStrategy(n_long=1, n_short=1).target_weights(DataView(spot=spot, rates=rates))
    assert w.loc[idx[0], "AUD"] == 1.0 and w.loc[idx[0], "EUR"] == -1.0
    assert abs(w.loc[idx[0]].sum()) < 1e-9
    assert CarryStrategy(2, 2).params() == {"n_long": 2, "n_short": 2}

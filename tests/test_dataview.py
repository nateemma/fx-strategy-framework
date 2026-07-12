import pandas as pd
from forex.core.dataview import DataView

def _view():
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    spot = pd.DataFrame({"AUD": range(5), "EUR": range(5)}, index=idx).astype(float)
    rates = {"USD": pd.Series([0.01]*5, index=idx), "AUD": pd.Series([0.05]*5, index=idx),
             "EUR": pd.Series([0.0]*5, index=idx)}
    return DataView(spot=spot, rates=rates)

def test_codes_and_calendar():
    v = _view()
    assert v.codes == ["AUD", "EUR"]
    assert len(v.calendar) == 5

def test_truncate_clips_spot_and_rates():
    v = _view().truncate("2020-01-03")
    assert v.spot.index.max() == pd.Timestamp("2020-01-03")
    assert v.rates["AUD"].index.max() == pd.Timestamp("2020-01-03")

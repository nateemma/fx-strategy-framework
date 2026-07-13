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


def test_reer_defaults_empty_and_truncate_clips_it():
    # existing DataView(spot=, rates=) construction still works (reer optional)
    assert _view().reer == {}
    idx = pd.date_range("2020-01-01", periods=5, freq="D")
    spot = pd.DataFrame({"AUD": range(5)}, index=idx).astype(float)
    reer = {"AUD": pd.Series([100.0]*5, index=idx)}
    v = DataView(spot=spot, rates={"USD": pd.Series([0.01]*5, index=idx)}, reer=reer)
    t = v.truncate("2020-01-03")
    assert t.reer["AUD"].index.max() == pd.Timestamp("2020-01-03")

def test_from_fred_loads_reer(tmp_path):
    midx = pd.date_range("2015-01-01", periods=24, freq="MS")
    def fake_loader(series_id, *, cache_dir=None, **kw):
        return pd.Series(range(1, 25), index=midx, dtype="float64", name="value")
    v = DataView.from_fred(tmp_path, loader=fake_loader, codes=["AUD", "EUR"])
    assert set(v.reer) == {"AUD", "EUR"}
    assert not v.reer["AUD"].empty
    assert v.reer["AUD"].iloc[0] == 1.0    # REER is an index level, not divided by 100

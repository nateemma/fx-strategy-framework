import pandas as pd
from forex.data.prices import build_spot_panel, spot_returns

def make_loader(data):
    def _loader(series_id, *, cache_dir, client=None):
        return data[series_id]
    return _loader

def test_inversion_and_returns():
    idx = pd.to_datetime(["2020-01-02", "2020-01-03"])
    data = {
        "DEXUSEU": pd.Series([1.10, 1.21], index=idx, name="value"),  # already USD/EUR
        "DEXJPUS": pd.Series([100.0, 125.0], index=idx, name="value"),# JPY/USD -> invert
    }
    # restrict the universe to EUR+JPY for the test by monkeypatching is unnecessary:
    panel = build_spot_panel(cache_dir="unused", loader=make_loader(data),
                             codes=["EUR", "JPY"])
    # EUR: unchanged; JPY inverted -> USD/JPY = 1/100 then 1/125
    assert round(panel.loc["2020-01-02", "EUR"], 4) == 1.10
    assert round(panel.loc["2020-01-02", "JPY"], 6) == round(1/100, 6)
    rets = spot_returns(panel)
    assert round(rets.loc["2020-01-03", "EUR"], 4) == 0.10      # +10%
    assert round(rets.loc["2020-01-03", "JPY"], 4) == -0.20     # 1/125 vs 1/100 = -20%

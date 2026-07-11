import pandas as pd
from forex.features.volforecast import ewma_vol

def test_ewma_vol_annualizes_first_value():
    r = pd.Series([0.01, -0.01, 0.01, -0.01],
                  index=pd.date_range("2020-01-01", periods=4, freq="D"))
    v = ewma_vol(r, lam=0.94, periods_per_year=252)
    assert len(v) == 4
    # adjust=False => first EWMA(r^2) value is r_0^2, so vol_0 = |0.01|*sqrt(252)
    assert round(v.iloc[0], 6) == round(0.01 * (252 ** 0.5), 6)
    assert (v > 0).all()

def test_ewma_vol_rises_with_bigger_shocks():
    calm = pd.Series([0.001] * 50, index=pd.date_range("2020-01-01", periods=50, freq="D"))
    wild = pd.Series([0.05] * 50, index=pd.date_range("2020-01-01", periods=50, freq="D"))
    assert ewma_vol(wild).iloc[-1] > ewma_vol(calm).iloc[-1]

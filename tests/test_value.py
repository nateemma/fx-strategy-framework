import pandas as pd
from strategies.features.value import value_signal

def test_value_signal_sign_and_warmup():
    midx = pd.date_range("2019-01-01", periods=6, freq="MS")
    reer = {
        "CHEAP": pd.Series([100, 100, 100, 100, 100, 90.0], index=midx),   # dropped below mean
        "RICH":  pd.Series([100, 100, 100, 100, 100, 110.0], index=midx),  # rose above mean
        "FLAT":  pd.Series([100.0] * 6, index=midx),                        # at its mean
    }
    cal = pd.date_range("2019-08-01", periods=2, freq="D")   # past 2019-06 REER + 45d lag
    sig = value_signal(cal, reer, window=3, pub_lag_days=45)
    assert sig["CHEAP"].iloc[-1] > 0        # undervalued -> positive signal (long)
    assert sig["RICH"].iloc[-1] < 0         # overvalued -> negative signal (short)
    assert abs(sig["FLAT"].iloc[-1]) < 1e-9 # at its mean -> ~zero
    # a calendar date before any released valid signal is NaN
    early = value_signal(pd.date_range("2019-01-05", periods=1, freq="D"),
                         reer, window=3, pub_lag_days=45)
    assert early["CHEAP"].isna().all()

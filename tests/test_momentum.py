import pandas as pd
from forex.features.momentum import momentum_signal

def test_signal_is_trailing_return_with_nan_warmup():
    idx = pd.date_range("2020-01-01", periods=4, freq="B")
    spot = pd.DataFrame(
        {"AUD": [1.0, 1.1, 1.2, 1.3], "EUR": [1.1, 1.1, 1.1, 1.1]},
        index=idx,
    )
    sig = momentum_signal(spot, lookback=2)
    # first `lookback` rows are warm-up NaN
    assert sig.iloc[0].isna().all()
    assert sig.iloc[1].isna().all()
    # row 2 = value/value[t-2] - 1
    assert round(sig.iloc[2]["AUD"], 4) == 0.2      # 1.2/1.0 - 1
    assert round(sig.iloc[2]["EUR"], 4) == 0.0      # flat
    assert sig.index.name == "date"

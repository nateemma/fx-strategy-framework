import numpy as np, pandas as pd
import pytest
from forex.features.trend import trend_signal, directional_weights

def _panel():
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    return pd.DataFrame({"AUD": 1.0 + np.linspace(0, 0.4, 20),      # steadily rising
                         "SEK": 1.0 - np.linspace(0, 0.3, 20)},     # steadily falling
                        index=idx)

@pytest.mark.parametrize("stype", ["tsmom", "ema", "donchian"])
def test_signal_is_long_uptrend_short_downtrend(stype):
    spot = _panel()
    sig = trend_signal(spot, stype, lookback=5)
    last = sig.iloc[-1]
    assert last["AUD"] == 1.0     # rising -> long
    assert last["SEK"] == -1.0    # falling -> short

def test_tsmom_warmup_is_nan():
    sig = trend_signal(_panel(), "tsmom", lookback=5)
    assert sig.iloc[:5].isna().all().all()      # first `lookback` rows NaN

def test_unknown_signal_type_raises():
    with pytest.raises(ValueError):
        trend_signal(_panel(), "nope", lookback=5)

def test_directional_weights_equal_weight_signed():
    idx = pd.date_range("2020-01-01", periods=1, freq="B")
    sig = pd.DataFrame({"A": [1.0], "B": [1.0], "C": [-1.0]}, index=idx)
    w = directional_weights(sig)
    row = w.iloc[0]
    assert abs(row["A"] - 1/3) < 1e-9 and abs(row["B"] - 1/3) < 1e-9
    assert abs(row["C"] + 1/3) < 1e-9
    assert abs(row.sum() - 1/3) < 1e-9          # net = mean signal; gross = 1

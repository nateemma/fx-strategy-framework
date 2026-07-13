import numpy as np
import pandas as pd

def trend_signal(spot: pd.DataFrame, signal_type: str = "tsmom",
                 lookback: int = 252) -> pd.DataFrame:
    if signal_type == "tsmom":
        sig = np.sign(spot / spot.shift(lookback) - 1.0)
    elif signal_type == "ema":
        fast = max(2, lookback // 4)
        ef = spot.ewm(span=fast, min_periods=fast).mean()
        es = spot.ewm(span=lookback, min_periods=lookback).mean()
        sig = np.sign(ef - es)
    elif signal_type == "donchian":
        hi = spot.rolling(lookback).max()
        lo = spot.rolling(lookback).min()
        raw = pd.DataFrame(np.nan, index=spot.index, columns=spot.columns)
        raw = raw.mask(spot >= hi, 1.0).mask(spot <= lo, -1.0)
        sig = raw.ffill()
    else:
        raise ValueError(f"unknown signal_type '{signal_type}'")
    sig.index.name = "date"
    return sig

def directional_weights(signal: pd.DataFrame) -> pd.DataFrame:
    return signal / float(signal.shape[1])

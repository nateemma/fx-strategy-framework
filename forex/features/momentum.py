import pandas as pd

def momentum_signal(spot: pd.DataFrame, lookback: int = 63) -> pd.DataFrame:
    out = spot / spot.shift(lookback) - 1.0
    out.index.name = "date"
    return out

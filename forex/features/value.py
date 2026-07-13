import numpy as np
import pandas as pd
from forex.data.store import asof_join

REER_PUB_LAG_DAYS = 45

def value_signal(calendar, reer: dict, window: int = 60,
                 pub_lag_days: int = REER_PUB_LAG_DAYS) -> pd.DataFrame:
    cal = pd.DatetimeIndex(calendar)
    cols = {}
    for code, s in reer.items():
        logr = np.log(s.astype("float64"))
        dev = logr - logr.rolling(window, min_periods=window).mean()
        cols[code] = asof_join(cal, (-dev).rename(code), pub_lag_days)
    out = pd.DataFrame(cols, index=cal)
    out.index.name = "date"
    return out

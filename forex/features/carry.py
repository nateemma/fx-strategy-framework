import numpy as np
import pandas as pd
from forex.config import CURRENCIES

def carry_signal(calendar, rates: dict[str, pd.Series]) -> pd.DataFrame:
    from forex.data.store import asof_join
    cal = pd.DatetimeIndex(calendar)
    usd = asof_join(cal, rates["USD"], CURRENCIES["USD"].pub_lag_days)
    cols = {}
    for code, s in rates.items():
        if code == "USD":
            continue
        r = asof_join(cal, s, CURRENCIES[code].pub_lag_days)
        cols[code] = r - usd
    out = pd.DataFrame(cols, index=cal)
    out.index.name = "date"
    return out

def basket_weights(signal: pd.DataFrame, n_long: int = 3,
                   n_short: int = 3) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=signal.index, columns=signal.columns)
    for dt, row in signal.iterrows():
        r = row.dropna()
        if len(r) < n_long + n_short:
            continue
        ranked = r.sort_values(ascending=False)
        longs = ranked.index[:n_long]
        shorts = ranked.index[-n_short:]
        w.loc[dt, longs] = 1.0 / n_long
        w.loc[dt, shorts] = -1.0 / n_short
    return w

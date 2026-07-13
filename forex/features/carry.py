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

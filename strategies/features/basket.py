import pandas as pd

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

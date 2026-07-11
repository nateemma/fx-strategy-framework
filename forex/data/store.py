import pandas as pd

def asof_join(calendar: pd.DatetimeIndex, series: pd.Series,
              pub_lag_days: int) -> pd.Series:
    """As-of (backward) join that respects a publication lag: a value dated T is
    only visible on/after T + pub_lag_days."""
    released = series.copy()
    released.index = series.index + pd.Timedelta(days=pub_lag_days)
    released = released.sort_index()
    left = pd.DataFrame(index=pd.DatetimeIndex(calendar).sort_values())
    right = released.rename("value").to_frame()
    merged = pd.merge_asof(left, right, left_index=True, right_index=True,
                           direction="backward")
    out = merged["value"]
    out.name = series.name
    out = out.reindex(calendar)
    out.index.name = "date"
    return out

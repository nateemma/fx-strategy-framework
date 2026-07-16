import pandas as pd

def positioning_signal(calendar, positioning: dict[str, pd.Series],
                       window: int = 156, lag_days: int = 6) -> pd.DataFrame:
    """Contrarian speculative-positioning signal: -1 * rolling z-score of CFTC net non-commercial
    position per currency (fade crowding), publication-lagged and as-of joined to the calendar.
    `positioning` is a dict of weekly net-spec series; `window` is in weeks."""
    from forex.data.store import asof_join
    cal = pd.DatetimeIndex(calendar)
    mp = max(2, window // 3)
    cols = {}
    for code, s in positioning.items():
        s = s.sort_index()
        z = (s - s.rolling(window, min_periods=mp).mean()) / s.rolling(window, min_periods=mp).std()
        cols[code] = asof_join(cal, -z, lag_days)          # contrarian + release lag
    out = pd.DataFrame(cols, index=cal)
    out.index.name = "date"
    return out

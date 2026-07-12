import os
from pathlib import Path
import pandas as pd

def _cache_path(cache_dir: Path, series_id: str) -> Path:
    return Path(cache_dir) / f"{series_id}.parquet"

def _read_cache(cache_dir: Path, series_id: str) -> pd.Series | None:
    p = _cache_path(cache_dir, series_id)
    if not p.exists():
        return None
    return pd.read_parquet(p)["value"]

def _write_cache(cache_dir: Path, series_id: str, s: pd.Series) -> None:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    s.rename("value").to_frame().to_parquet(_cache_path(cache_dir, series_id))

def _default_client():
    from fredapi import Fred
    return Fred(api_key=os.environ["FRED_API_KEY"])

def load_series(series_id: str, *, cache_dir: Path, client=None, force: bool = False) -> pd.Series:
    if not force:
        cached = _read_cache(cache_dir, series_id)
        if cached is not None:
            return cached
    if client is None:
        client = _default_client()
    raw = client.get_series(series_id)
    s = pd.Series(raw, dtype="float64").dropna().sort_index()
    s.index = pd.DatetimeIndex(s.index).tz_localize(None)
    s.index.name = "date"
    s.name = "value"
    _write_cache(cache_dir, series_id, s)
    return s

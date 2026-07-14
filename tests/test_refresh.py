import pandas as pd
from forex.config import CURRENCIES
from forex.data.fred import load_series
from forex.data.refresh import refresh_cache

class _FakeFred:
    def __init__(self, value): self.value = value
    def get_series(self, series_id):
        return pd.Series([self.value], index=pd.to_datetime(["2020-01-01"]))

def test_force_refetches_over_cache(tmp_path):
    load_series("X", cache_dir=tmp_path, client=_FakeFred(1.0))          # populate cache = 1.0
    cached = load_series("X", cache_dir=tmp_path, client=_FakeFred(2.0)) # no force -> stale cache
    assert cached.iloc[0] == 1.0
    forced = load_series("X", cache_dir=tmp_path, client=_FakeFred(2.0), force=True)
    assert forced.iloc[0] == 2.0                                        # force overwrote

def test_refresh_cache_forces_all_universe_series(tmp_path):
    seen = []
    def loader(series_id, *, cache_dir, client=None, force=False):
        seen.append((series_id, force))
        return pd.Series([1.0], index=pd.to_datetime(["2020-01-01"]))
    ids = refresh_cache(tmp_path, codes=["AUD", "EUR"], loader=loader)
    assert CURRENCIES["USD"].rate_fred in ids
    assert CURRENCIES["AUD"].rate_fred in ids and CURRENCIES["AUD"].spot_fred in ids
    assert CURRENCIES["AUD"].reer_fred in ids and CURRENCIES["EUR"].reer_fred in ids
    assert all(force is True for _, force in seen)      # every fetch forced


def test_refresh_cache_includes_macro(tmp_path):
    from forex.config import MACRO_SERIES
    seen = []
    def loader(series_id, *, cache_dir, client=None, force=False):
        seen.append(series_id)
        return pd.Series([1.0], index=pd.to_datetime(["2020-01-01"]))
    ids = refresh_cache(tmp_path, codes=["AUD", "EUR"], loader=loader)
    assert all(sid in ids for sid in MACRO_SERIES.values())

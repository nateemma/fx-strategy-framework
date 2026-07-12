from forex.config import CURRENCIES
from forex.data.fred import load_series

def refresh_cache(cache_dir, codes=None, loader=load_series) -> list:
    """Force-refetch every FRED series the universe needs, overwriting the cache."""
    if codes is None:
        codes = [c for c in CURRENCIES if c != "USD"]
    ids = [CURRENCIES["USD"].rate_fred]
    for c in codes:
        cur = CURRENCIES[c]
        ids.append(cur.rate_fred)
        if cur.spot_fred:
            ids.append(cur.spot_fred)
    for sid in ids:
        loader(sid, cache_dir=cache_dir, force=True)
    return ids

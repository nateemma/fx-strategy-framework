from forex.config import CURRENCIES, MACRO_SERIES, DEFAULT_CODES
from forex.data.fred import load_series

def refresh_cache(cache_dir, codes=None, loader=load_series, on_step=None) -> list:
    """Force-refetch every FRED series the universe needs, overwriting the cache."""
    if codes is None:
        codes = DEFAULT_CODES
    ids = [CURRENCIES["USD"].rate_fred]
    for c in codes:
        cur = CURRENCIES[c]
        ids.append(cur.rate_fred)
        if cur.spot_fred:
            ids.append(cur.spot_fred)
        if cur.reer_fred:
            ids.append(cur.reer_fred)
    ids += list(MACRO_SERIES.values())
    for i, sid in enumerate(ids, 1):
        if on_step:
            on_step(i, len(ids), sid)
        loader(sid, cache_dir=cache_dir, force=True)
    return ids

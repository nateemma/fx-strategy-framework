"""Free daily prices for equities and ETFs, cached. Deliberately the same shape as `fred.py`.

WHY THIS EXISTS IN THE FRAMEWORK. Prior equity research here (the RSP-vs-SPY gate, the momentum
basket) fetched prices with throwaway scratchpad scripts that were written and discarded each time.
Spec 009 needs the same loader six times, so it lives here once.

THE TRAP THIS GUARDS. Requesting `range=max&interval=1d` returns a response that CLAIMS to be daily
and is actually monthly — measured 2026-10-15 at 292 bars for IEF against 6,093 from an explicit
period range. Nothing errors. A daily strategy backtested on 292 monthly bars yields a plausible,
entirely wrong number. So this module always sends an explicit period range, and always asserts the
granularity the response reports back. That assertion is the most important line in the file.

ADJUSTED CLOSES, ALWAYS. Every instrument spec 009 touches is a distributing bond, TIPS or credit
ETF. Raw closes omit most of the total return, and for a carry-like spread trade that omission IS
the signal. A response without an adjusted series is an error rather than a reason to fall back.

No new dependency: the default client is `urllib.request`. The client is injected so the test suite
performs no network I/O (Constitution III).
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
DEFAULT_START = date(1990, 1, 1)
_DAILY = ("1d",)


def _cache_path(cache_dir, symbol: str) -> Path:
    return Path(cache_dir) / f"{symbol}.parquet"


def _read_cache(cache_dir, symbol: str):
    p = _cache_path(cache_dir, symbol)
    if not p.exists():
        return None
    return pd.read_parquet(p)["value"]


def _write_cache(cache_dir, symbol: str, s: pd.Series) -> None:
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    s.rename("value").to_frame().to_parquet(_cache_path(cache_dir, symbol))


def _default_client(url: str) -> bytes:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _build_url(symbol: str, start: date) -> str:
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    p2 = int(datetime.now(timezone.utc).timestamp())
    # period1/period2 + interval=1d, NEVER range=max — see the module docstring.
    return f"{CHART_URL.format(symbol=symbol)}?period1={p1}&period2={p2}&interval=1d"


def _parse(raw: bytes, symbol: str) -> pd.Series:
    doc = json.loads(raw)
    result = (doc.get("chart") or {}).get("result") or []
    if not result:
        raise ValueError(f"{symbol}: no chart result in response")
    r = result[0]

    reported = (r.get("meta") or {}).get("dataGranularity")
    if reported not in _DAILY:
        raise ValueError(
            f"{symbol}: response granularity is {reported!r}, not daily. The source silently "
            f"coarsens the interval for wide ranges; a non-daily series must never be used here.")

    stamps = r.get("timestamp") or []
    adj = (r.get("indicators") or {}).get("adjclose") or []
    values = (adj[0].get("adjclose") if adj else None) or []
    if not values:
        raise ValueError(f"{symbol}: response carries no adjusted closes; raw closes are not usable "
                         f"for distributing ETFs")
    if not stamps or len(stamps) != len(values):
        raise ValueError(f"{symbol}: {len(stamps)} timestamps against {len(values)} values")

    # NORMALISE TO MIDNIGHT. The API stamps each bar at the market open (13:30 UTC for US equities),
    # so an un-normalised index will not intersect a FRED series dated at midnight — the symptom is
    # a silent zero-length join, which is how this was found.
    idx = (pd.to_datetime(pd.Series(stamps), unit="s", utc=True)
           .dt.tz_localize(None).dt.normalize())
    s = pd.Series(values, index=pd.DatetimeIndex(idx), name=symbol, dtype="float64")
    s = s[~s.index.duplicated(keep="last")]
    s = s[s.notna()]
    if s.empty:
        raise ValueError(f"{symbol}: adjusted close series is empty")
    return s.sort_index()


def load_prices(symbol: str, cache_dir="data_cache/yahoo", force: bool = False,
                client=None, start: date = DEFAULT_START) -> pd.Series:
    """Adjusted daily closes for `symbol`, cached as parquet.

    `force=False` returns the cache when present without calling the client at all. `force=True`
    refetches; if that fails and a cache exists, the cache is returned rather than raising — a stale
    verdict is better than no verdict, and the cache is what makes a verdict reproducible (FR-013).
    """
    if not force:
        cached = _read_cache(cache_dir, symbol)
        if cached is not None:
            return cached.rename(symbol)

    fetch = client or _default_client
    try:
        s = _parse(fetch(_build_url(symbol, start)), symbol)
    except Exception:
        cached = _read_cache(cache_dir, symbol)
        if cached is not None:
            print(f"  ({symbol}: refresh failed, using cached series)")
            return cached.rename(symbol)
        raise

    _write_cache(cache_dir, symbol, s)
    return s

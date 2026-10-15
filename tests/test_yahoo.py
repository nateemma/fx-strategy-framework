"""The free price loader. The load-bearing test is the granularity assertion.

Spec 009 research R1 measured the obvious call — `range=max&interval=1d` — returning **292 monthly
bars** for IEF while reporting itself as daily, against 6,093 real daily bars from an explicit
period range. Nothing errors in that case. A daily strategy backtested on monthly bars would produce
a plausible number with no indication anything was wrong, which is this repo's actual failure mode:
a silently wrong figure, not a crash.

Every test here injects a client, so the suite performs no network I/O (Constitution III).
"""
import json

import pandas as pd
import pytest

from forex.data.yahoo import load_prices


def _payload(n=600, granularity="1d", adjclose=True, start=1_000_000_000):
    """A chart-API-shaped response. 86400s steps = daily."""
    ts = [start + i * 86400 for i in range(n)]
    closes = [100.0 + i * 0.01 for i in range(n)]
    ind = {"quote": [{"close": closes}]}
    if adjclose:
        ind["adjclose"] = [{"adjclose": [c * 0.9 for c in closes]}]
    return json.dumps({"chart": {"result": [{
        "meta": {"dataGranularity": granularity, "symbol": "TEST"},
        "timestamp": ts, "indicators": ind}], "error": None}}).encode()


def client_returning(payload):
    calls = []

    def _client(url):
        calls.append(url)
        return payload

    _client.calls = calls
    return _client


# ------------------------------------------------- the granularity guard (research R1)

def test_a_non_daily_granularity_raises(tmp_path):
    """The whole point. A response that says it is monthly must stop the run, not be averaged in."""
    client = client_returning(_payload(n=292, granularity="1mo"))
    with pytest.raises(ValueError, match="granularity"):
        load_prices("IEF", cache_dir=tmp_path, client=client)


def test_a_weekly_granularity_also_raises(tmp_path):
    """Anything that is not daily is wrong here, not just monthly."""
    client = client_returning(_payload(n=500, granularity="1wk"))
    with pytest.raises(ValueError, match="granularity"):
        load_prices("IEF", cache_dir=tmp_path, client=client)


def test_a_daily_granularity_is_accepted(tmp_path):
    s = load_prices("IEF", cache_dir=tmp_path, client=client_returning(_payload()))
    assert len(s) == 600
    assert isinstance(s.index, pd.DatetimeIndex)


def test_the_request_never_uses_range_max(tmp_path):
    """`range=max` is what silently coarsens the interval, so the URL must not contain it."""
    client = client_returning(_payload())
    load_prices("IEF", cache_dir=tmp_path, client=client)
    url = client.calls[0]
    assert "range=max" not in url
    assert "period1=" in url and "period2=" in url and "interval=1d" in url


def test_the_index_is_normalised_to_midnight(tmp_path):
    """The API stamps bars at the market open, so an un-normalised index silently fails to join a
    FRED series dated at midnight. Found by a zero-length intersection during the A3 gate."""
    # 1_000_000_000 is 2001-09-09 01:46:40 UTC — deliberately not midnight.
    s = load_prices("IEF", cache_dir=tmp_path, client=client_returning(_payload()))
    assert (s.index == s.index.normalize()).all()
    assert s.index.hour.max() == 0 and s.index.minute.max() == 0


# ------------------------------------------------- adjusted closes (research R4)

def test_adjusted_closes_are_returned_not_raw(tmp_path):
    """Every instrument here is a distributing bond/TIPS/credit ETF. Raw closes omit most of the
    return, which for a carry-like spread IS the signal."""
    s = load_prices("IEF", cache_dir=tmp_path, client=client_returning(_payload()))
    assert s.iloc[0] == pytest.approx(90.0)        # 100.0 * 0.9, the adjusted series
    assert s.iloc[0] != pytest.approx(100.0)       # not the raw close


def test_a_response_without_adjclose_raises(tmp_path):
    """Falling back to raw closes silently would reintroduce exactly the error R4 guards against."""
    client = client_returning(_payload(adjclose=False))
    with pytest.raises(ValueError, match="adjusted"):
        load_prices("IEF", cache_dir=tmp_path, client=client)


# ------------------------------------------------- the cache contract

def test_a_cached_read_performs_no_client_calls(tmp_path):
    first = client_returning(_payload())
    load_prices("IEF", cache_dir=tmp_path, client=first)
    assert len(first.calls) == 1

    second = client_returning(_payload())
    s = load_prices("IEF", cache_dir=tmp_path, client=second)
    assert second.calls == [], "a cached symbol must not be refetched"
    assert len(s) == 600


def test_force_refetches_and_rewrites(tmp_path):
    load_prices("IEF", cache_dir=tmp_path, client=client_returning(_payload(n=600)))
    client = client_returning(_payload(n=700))
    s = load_prices("IEF", cache_dir=tmp_path, force=True, client=client)
    assert len(client.calls) == 1
    assert len(s) == 700, "force must overwrite the cache, not ignore the new data"
    assert len(load_prices("IEF", cache_dir=tmp_path, client=client_returning(_payload()))) == 700


# ------------------------------------------------- failure behaviour

def test_a_failed_fetch_falls_back_to_cache(tmp_path):
    load_prices("IEF", cache_dir=tmp_path, client=client_returning(_payload()))

    def boom(url):
        raise OSError("network down")

    s = load_prices("IEF", cache_dir=tmp_path, force=True, client=boom)
    assert len(s) == 600, "a cached series should survive a failed refresh"


def test_a_failed_fetch_with_no_cache_raises(tmp_path):
    def boom(url):
        raise OSError("network down")

    with pytest.raises(OSError):
        load_prices("NOPE", cache_dir=tmp_path, client=boom)


def test_an_empty_response_raises_rather_than_returning_a_short_series(tmp_path):
    """A silently short series is the same class of bug as the wrong granularity."""
    client = client_returning(_payload(n=0))
    with pytest.raises(ValueError):
        load_prices("IEF", cache_dir=tmp_path, client=client)
